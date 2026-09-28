"""Rules run under the existing organization/actor lock; never commit here."""

import json

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select

from app.core.errors import APIError
from app.core.security import digest, now, utc
from app.models import (
    AttendanceSheet,
    Branch,
    ClassSession,
    Enrollment,
    EnrollmentOperation,
    EnrollmentPeriod,
    Invoice,
    InvoiceAdjustment,
    LearningClass,
    Payment,
    RefundCase,
    RefundPolicy,
    Room,
    SessionTeacher,
    StudentProfile,
    TeacherProfile,
)


def fingerprint(value):
    return digest(json.dumps(jsonable_encoder(value), sort_keys=True))


def active_clause(at):
    return (
        select(EnrollmentPeriod.id)
        .where(
            EnrollmentPeriod.enrollment_id == Enrollment.id,
            EnrollmentPeriod.organization_id == Enrollment.organization_id,
            EnrollmentPeriod.starts_at <= at,
            or_(EnrollmentPeriod.ends_at.is_(None), EnrollmentPeriod.ends_at > at),
        )
        .correlate(Enrollment, ClassSession)
        .exists()
    )


def attendees(db, class_id, at):
    return list(
        db.scalars(
            select(Enrollment).where(
                Enrollment.class_id == class_id,
                active_clause(at),
            )
        )
    )


def peak_count(db, class_id):
    sessions = db.scalars(
        select(ClassSession).where(
            ClassSession.class_id == class_id,
            ClassSession.status == "scheduled",
            ClassSession.ends_at > now(),
        )
    )
    return max((len(attendees(db, class_id, s.starts_at)) for s in sessions), default=0)


def offset(db, invoice):
    return int(
        db.scalar(
            select(func.coalesce(func.sum(InvoiceAdjustment.amount), 0)).where(
                InvoiceAdjustment.invoice_id == invoice.id,
            )
        )
    )


def settled(db, request_id):
    return db.scalar(select(RefundCase.id).where(RefundCase.settled_request_id == request_id))


def policy(db, org):
    row = db.scalar(select(RefundPolicy).where(RefundPolicy.organization_id == org))
    return (
        {"kind": row.kind, "value": row.value, "version": row.version}
        if row
        else {
            "kind": "fixed",
            "value": 0,
            "version": 0,
        }
    )


def sessions_snapshot(db, class_id):
    return [
        {
            "id": str(s.id),
            "starts_at": utc(s.starts_at).isoformat(),
            "ends_at": utc(s.ends_at).isoformat(),
            "status": s.status,
            "version": s.version,
        }
        for s in db.scalars(
            select(ClassSession)
            .where(ClassSession.class_id == class_id)
            .order_by(ClassSession.starts_at, ClassSession.id)
        )
    ]


def enrollment_for(db, request_id):
    return db.scalar(select(Enrollment).where(Enrollment.request_id == request_id))


def resume_guard(db, enrollment, start):
    from app.api.routes.schedules import teacher_view
    from app.services.admissions import session_conflict

    item = db.get(LearningClass, enrollment.class_id)
    if item.status != "draft" or db.get(Branch, item.branch_id).archived_at:
        raise APIError(409, "LIFECYCLE_CLASS_UNAVAILABLE")
    sessions = list(
        db.scalars(
            select(ClassSession).where(
                ClassSession.class_id == item.id,
                ClassSession.starts_at >= start,
                ClassSession.status == "scheduled",
            )
        )
    )
    for s in sessions:
        teachers = list(
            db.scalars(
                select(TeacherProfile)
                .join(
                    SessionTeacher,
                    SessionTeacher.teacher_profile_id == TeacherProfile.id,
                )
                .where(SessionTeacher.session_id == s.id)
            )
        )
        room = db.get(Room, s.room_id) if s.room_id else None
        if (
            not teachers
            or any(not teacher_view(db, item, t)["active"] for t in teachers)
            or (
                s.format != "online"
                and (not room or room.archived_at or room.capacity < s.capacity)
            )
        ):
            raise APIError(409, "LIFECYCLE_CLASS_UNAVAILABLE")
        if len(attendees(db, item.id, s.starts_at)) >= min(item.capacity, s.capacity):
            raise APIError(409, "ADMISSION_NO_SEAT")
    if not sessions or session_conflict(db, enrollment.student_id, sessions):
        raise APIError(409, "ADMISSION_STUDENT_CONFLICT")


def preview(db, req, body):
    from app.services.admissions import expected

    enrollment = enrollment_for(db, req.id)
    expected(enrollment or req, body.version)
    if req.cancelled_at or (enrollment and enrollment.state == "cancelled"):
        raise APIError(409, "LIFECYCLE_STATE")
    if settled(db, req.id):
        raise APIError(409, "REFUND_SETTLED")
    if not enrollment:
        if req.status != "waiting" or body.action != "cancel" or body.session_id:
            raise APIError(409, "LIFECYCLE_STATE")
        source = {
            "request_id": req.id,
            "version": req.version,
            "action": "cancel",
            "session_id": None,
            "sessions": [],
            "total_sessions": 0,
            "unused_sessions": 0,
        }
    else:
        if (body.action == "suspend" and enrollment.state != "active") or (
            body.action == "resume" and enrollment.state != "suspended"
        ):
            raise APIError(409, "LIFECYCLE_STATE")
        session = db.get(ClassSession, body.session_id) if body.session_id else None
        if (
            not session
            or session.class_id != enrollment.class_id
            or session.organization_id != req.organization_id
            or session.status != "scheduled"
            or utc(session.starts_at) <= now()
        ):
            raise APIError(409, "LIFECYCLE_SESSION")
        periods = list(
            db.scalars(
                select(EnrollmentPeriod)
                .where(
                    EnrollmentPeriod.enrollment_id == enrollment.id,
                )
                .order_by(EnrollmentPeriod.starts_at)
            )
        )
        if not periods:
            raise APIError(409, "LIFECYCLE_STATE")
        last = periods[-1]
        boundary = utc(last.ends_at or last.starts_at)
        if utc(session.starts_at) < boundary:
            raise APIError(409, "LIFECYCLE_SESSION")
        if body.action == "resume":
            resume_guard(db, enrollment, session.starts_at)
        # Never invalidate even an unexpected future sheet silently.
        if body.action != "resume" and db.scalar(
            select(AttendanceSheet.id)
            .join(
                ClassSession,
                ClassSession.id == AttendanceSheet.session_id,
            )
            .where(
                ClassSession.class_id == enrollment.class_id,
                ClassSession.starts_at >= session.starts_at,
            )
            .limit(1)
        ):
            raise APIError(409, "LIFECYCLE_ATTENDANCE_EXISTS")
        sessions = sessions_snapshot(db, enrollment.class_id)
        scheduled = [s for s in sessions if s["status"] == "scheduled"]
        source = {
            "request_id": req.id,
            "version": enrollment.version,
            "state": enrollment.state,
            "action": body.action,
            "session_id": session.id,
            "effective_at": utc(session.starts_at),
            "sessions": sessions,
            "total_sessions": len(scheduled),
            "unused_sessions": sum(
                s["starts_at"] >= utc(session.starts_at).isoformat() for s in scheduled
            ),
            "periods": [
                {"starts_at": utc(p.starts_at), "ends_at": utc(p.ends_at) if p.ends_at else None}
                for p in periods
            ],
        }
    return {**jsonable_encoder(source), "source_digest": fingerprint(source)}


def operate(db, tenant, req, body):
    from app.services import admissions as svc

    source = preview(db, req, body)
    if source["source_digest"] != body.source_digest:
        raise APIError(409, "BUSINESS_STALE")
    enrollment = enrollment_for(db, req.id)
    effective = db.get(ClassSession, body.session_id).starts_at if body.session_id else now()
    if enrollment:
        if body.action == "resume":
            db.add(
                EnrollmentPeriod(
                    organization_id=req.organization_id,
                    enrollment_id=enrollment.id,
                    starts_at=effective,
                )
            )
            for case in db.scalars(
                select(RefundCase).where(
                    RefundCase.request_id == req.id,
                    RefundCase.status == "proposed",
                )
            ):
                case.status, case.version = "cancelled", case.version + 1
        else:
            for period in db.scalars(
                select(EnrollmentPeriod).where(
                    EnrollmentPeriod.enrollment_id == enrollment.id,
                    EnrollmentPeriod.ends_at.is_(None),
                )
            ):
                period.ends_at = effective
        enrollment.state = {"suspend": "suspended", "resume": "active", "cancel": "cancelled"}[
            body.action
        ]
        enrollment.version += 1
    else:
        req.cancelled_at = now()
        req.version += 1
    op = EnrollmentOperation(
        organization_id=req.organization_id,
        request_id=req.id,
        session_id=body.session_id,
        action=body.action,
        effective_at=effective,
        actor_id=tenant.actor.user.id,
        created_at=now(),
        reason=body.reason,
        snapshot=source,
    )
    db.add(op)
    db.flush()
    svc.notify(
        db,
        req.organization_id,
        [svc.student_user(db, db.get(StudentProfile, req.student_id))],
        "enrollment." + body.action,
        req.id,
        "enrollment:" + str(op.id),
    )
    return source


def refund_quote(db, req):
    from app.services import admissions as svc

    enrollment = enrollment_for(db, req.id)
    if (enrollment and enrollment.state == "active") or (not enrollment and not req.cancelled_at):
        raise APIError(409, "LIFECYCLE_STATE")
    if settled(db, req.id):
        raise APIError(409, "REFUND_SETTLED")
    # Use the latest operation by business version (timestamps may share test clock).
    ops = list(
        db.scalars(select(EnrollmentOperation).where(EnrollmentOperation.request_id == req.id))
    )
    op = max(ops, key=lambda x: x.snapshot["version"]) if ops else None
    if not op or op.action not in {"suspend", "cancel"}:
        raise APIError(409, "LIFECYCLE_STATE")
    invoice = db.scalar(select(Invoice).where(Invoice.request_id == req.id))
    if not invoice:
        raise APIError(409, "LIFECYCLE_STATE")
    n, total = op.snapshot["unused_sessions"], op.snapshot["total_sessions"]
    if enrollment and not total:
        raise APIError(409, "LIFECYCLE_SESSION")
    unused = invoice.total * n // total if enrollment else invoice.total
    paid = svc.paid(db, invoice)
    rule = policy(db, req.organization_id)
    eligible = min(paid, unused)
    fee = rule["value"] if rule["kind"] == "fixed" else eligible * rule["value"] // 100
    proposed = max(0, eligible - fee)
    remaining = invoice.total - paid - offset(db, invoice)
    source = {
        "request_id": str(req.id),
        "invoice_id": str(invoice.id),
        "operation_id": str(op.id),
        "total": invoice.total,
        "paid": paid,
        "remaining": remaining,
        "unused": unused,
        "total_sessions": total,
        "unused_sessions": n,
        "policy": rule,
        "fee": fee,
        "proposed": proposed,
        "offset_amount": min(proposed, remaining),
        "cash_amount": max(0, proposed - remaining),
        "sessions": sessions_snapshot(db, enrollment.class_id) if enrollment else [],
        "source_sessions": op.snapshot["sessions"],
        "payments": [
            {
                "id": str(p.id),
                "amount": p.amount,
                "reversed_at": utc(p.reversed_at).isoformat() if p.reversed_at else None,
            }
            for p in db.scalars(
                select(Payment).where(Payment.invoice_id == invoice.id).order_by(Payment.id)
            )
        ],
    }
    return {**source, "source_digest": fingerprint(source)}


def protect_session_boundary(db, row, candidate):
    if utc(row.starts_at) != utc(candidate["starts_at"]) or row.status != candidate["status"]:
        if db.scalar(
            select(EnrollmentOperation.id).where(EnrollmentOperation.session_id == row.id).limit(1)
        ):
            raise APIError(409, "LIFECYCLE_BOUNDARY_LOCKED")


def archive_guard(db, student_id):
    from app.services.admissions import debt

    if (
        debt(db, student_id) > 0
        or db.scalar(
            select(Enrollment.id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.state == "suspended",
            )
            .limit(1)
        )
        or db.scalar(
            select(RefundCase.id)
            .join(Invoice, Invoice.id == RefundCase.invoice_id)
            .where(
                Invoice.student_id == student_id,
                RefundCase.status == "pending",
            )
            .limit(1)
        )
    ):
        raise APIError(409, "STUDENT_ENROLLMENT_IN_USE")
