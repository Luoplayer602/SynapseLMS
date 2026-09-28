"""Shared transactional rules, called only after tenant/actor authorization lock."""

import json
from datetime import time
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import audit
from app.core.errors import APIError
from app.core.security import digest, now, utc
from app.models import (
    AdmissionOpening,
    Branch,
    BusinessOperation,
    ClassSession,
    CourseLevel,
    Enrollment,
    Invoice,
    LearningClass,
    Notification,
    Payment,
    Room,
    SessionTeacher,
    StudentIdentity,
    StudentProficiency,
    StudentProfile,
    TeacherProfile,
    User,
    UserMembership,
)


def scoped(db, model, tenant, target):
    row = db.scalar(
        select(model).where(model.id == target, model.organization_id == tenant.organization.id)
    )
    if not row:
        raise APIError(404, "BUSINESS_NOT_FOUND")
    return row


def expected(row, version):
    if (row.version if row else 0) != version:
        raise APIError(409, "BUSINESS_STALE")


def replay(db, tenant, action, target, body):
    fingerprint = digest(
        json.dumps(
            jsonable_encoder({"action": action, "target": target, "body": body.model_dump()}),
            sort_keys=True,
        )
    )
    row = db.scalar(
        select(BusinessOperation).where(
            BusinessOperation.organization_id == tenant.organization.id,
            BusinessOperation.request_key == body.request_key,
        )
    )
    if row and (row.fingerprint != fingerprint or row.actor_id != tenant.actor.user.id):
        raise APIError(409, "BUSINESS_KEY_REUSED")
    return fingerprint, row.result if row else None


def finish(db, tenant, action, target, body, fingerprint, result, before=None):
    result = jsonable_encoder(result)
    db.add(
        BusinessOperation(
            organization_id=tenant.organization.id,
            actor_id=tenant.actor.user.id,
            request_key=body.request_key,
            fingerprint=fingerprint,
            action=action,
            target_id=target,
            created_at=now(),
            before=jsonable_encoder(before or {}),
            result=result,
        )
    )
    audit(
        db, tenant.actor, action, tenant.organization.id, target, request_key=str(body.request_key)
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "BUSINESS_CONFLICT") from error
    return result


def student_user(db, profile):
    return db.get(StudentIdentity, profile.identity_id).user_id


def student_ready(db, tenant, profile):
    uid = student_user(db, profile)
    user = db.scalar(
        select(User)
        .where(User.id == uid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    member = db.scalar(
        select(UserMembership).where(
            UserMembership.user_id == uid,
            UserMembership.organization_id == tenant.organization.id,
            UserMembership.role == "student",
            UserMembership.is_active.is_(True),
            UserMembership.ended_at.is_(None),
        )
    )
    if profile.archived_at or not user.is_active or not member:
        raise APIError(409, "STUDENT_UNAVAILABLE")
    if not profile.full_name or not profile.phone or not profile.date_of_birth:
        raise APIError(422, "ADMISSION_PROFILE_REQUIRED")


def own_student(db, tenant):
    profile = db.scalar(
        select(StudentProfile)
        .join(StudentIdentity, StudentIdentity.id == StudentProfile.identity_id)
        .where(
            StudentProfile.organization_id == tenant.organization.id,
            StudentIdentity.user_id == tenant.actor.user.id,
        )
    )
    if not profile:
        raise APIError(404, "ADMISSION_PROFILE_REQUIRED")
    return profile


def paid(db, invoice):
    return db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice.id, Payment.reversed_at.is_(None)
        )
    )


def debt(db, student_id):
    return sum(
        i.total - paid(db, i)
        for i in db.scalars(select(Invoice).where(Invoice.student_id == student_id))
    )


def notify(db, org_id, user_ids, kind, target, event_key):
    # An in-app row is the durable event; no network call occurs during the transaction.
    for uid in set(user_ids):
        db.add(
            Notification(
                organization_id=org_id,
                user_id=uid,
                kind=kind,
                target_id=target,
                event_key=event_key,
                created_at=now(),
            )
        )


def staff_ids(db, org_id):
    return list(
        db.scalars(
            select(UserMembership.user_id)
            .join(User, User.id == UserMembership.user_id)
            .where(
                UserMembership.organization_id == org_id,
                UserMembership.role.in_(["staff", "organization_manager"]),
                UserMembership.is_active.is_(True),
                UserMembership.ended_at.is_(None),
                User.is_active.is_(True),
            )
        )
    )


def session_conflict(db, student_id, candidate_sessions, exclude_session=None):
    existing = list(
        db.scalars(
            select(ClassSession)
            .join(Enrollment, Enrollment.class_id == ClassSession.class_id)
            .where(
                Enrollment.student_id == student_id,
                ClassSession.status == "scheduled",
                ClassSession.ends_at > now(),
            )
        )
    )
    return any(
        old.id != exclude_session
        and utc(old.starts_at) < utc(new.ends_at)
        and utc(old.ends_at) > utc(new.starts_at)
        for old in existing
        for new in candidate_sessions
    )


def candidates(db, tenant, req):
    """Hard constraints never bypassed; soft eligibility requires manual explanation."""
    rows = db.scalars(
        select(LearningClass)
        .join(AdmissionOpening, AdmissionOpening.class_id == LearningClass.id)
        .where(
            LearningClass.organization_id == tenant.organization.id,
            LearningClass.course_id == req.course_id,
            LearningClass.status == "draft",
            AdmissionOpening.enabled.is_(True),
        )
        .order_by(LearningClass.starts_on, LearningClass.id)
    )
    result = []
    for item in rows:
        if db.get(Branch, item.branch_id).archived_at:
            continue
        if (
            req.branch_id
            and item.branch_id != req.branch_id
            or req.format != "any"
            and item.format != req.format
        ):
            continue
        from app.api.routes.schedules import teacher_view

        sessions = list(
            db.scalars(
                select(ClassSession)
                .where(ClassSession.class_id == item.id, ClassSession.status == "scheduled")
                .order_by(ClassSession.starts_at)
            )
        )
        unavailable = False
        for session in sessions:
            room = db.get(Room, session.room_id) if session.room_id else None
            teachers = list(
                db.scalars(
                    select(TeacherProfile)
                    .join(
                        SessionTeacher,
                        SessionTeacher.teacher_profile_id == TeacherProfile.id,
                    )
                    .where(SessionTeacher.session_id == session.id)
                )
            )
            if (
                session.format != "online"
                and (not room or room.archived_at or room.capacity < session.capacity)
            ) or not teachers:
                unavailable = True
                break
            if any(not teacher_view(db, item, teacher)["active"] for teacher in teachers):
                unavailable = True
                break
        if unavailable:
            continue
        # Any begun session, including a cancelled one, excludes mid-course intake.
        begun = db.scalar(
            select(ClassSession.id)
            .where(ClassSession.class_id == item.id, ClassSession.starts_at <= now())
            .limit(1)
        )
        count = db.scalar(
            select(func.count()).select_from(Enrollment).where(Enrollment.class_id == item.id)
        )
        if (
            not sessions
            or begun
            or count >= min([item.capacity, *(s.capacity for s in sessions)])
            or session_conflict(db, req.student_id, sessions)
        ):
            continue
        warnings = []
        if item.entry_level_id:
            p = db.scalar(
                select(StudentProficiency).where(
                    StudentProficiency.student_profile_id == req.student_id,
                    StudentProficiency.framework_id == item.framework_id,
                )
            )
            level = db.get(CourseLevel, p.verified_level_id) if p and p.verified_level_id else None
            if not level or level.rank < db.get(CourseLevel, item.entry_level_id).rank:
                warnings.append("ADMISSION_LEVEL_REVIEW")
        if not req.availability:
            warnings.append("ADMISSION_AVAILABILITY_REVIEW")
        else:
            for session in sessions:
                start, end = (
                    utc(session.starts_at).astimezone(ZoneInfo(session.timezone)),
                    utc(session.ends_at).astimezone(ZoneInfo(session.timezone)),
                )
                if not any(
                    a["weekday"] == start.weekday()
                    and time.fromisoformat(a["starts_at"]) <= start.time()
                    and time.fromisoformat(a["ends_at"]) >= end.time()
                    for a in req.availability
                ):
                    warnings.append("ADMISSION_AVAILABILITY_REVIEW")
                    break
        result.append(
            {
                "id": item.id,
                "name": item.name,
                "code": item.code,
                "seats_left": item.capacity - count,
                "warnings": warnings,
            }
        )
    return result


def place(db, tenant, req, class_id):
    db.add(
        Enrollment(
            organization_id=tenant.organization.id,
            request_id=req.id,
            student_id=req.student_id,
            class_id=class_id,
            effective_at=now(),
        )
    )
    req.status = "placed"
    db.flush()


def enrollment_session_guard(db, row, candidate):
    """Used by individual session edits after their existing resource checks."""
    if candidate["status"] != "scheduled":
        return
    from types import SimpleNamespace

    new = SimpleNamespace(starts_at=candidate["starts_at"], ends_at=candidate["ends_at"])
    for student_id in db.scalars(
        select(Enrollment.student_id).where(Enrollment.class_id == row.class_id)
    ):
        if session_conflict(db, student_id, [new], exclude_session=row.id):
            raise APIError(409, "ADMISSION_STUDENT_CONFLICT")
