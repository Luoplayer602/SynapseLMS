from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.api.admission_schemas import AttendanceInput
from app.api.dependencies import DB, Tenant, auth_guard
from app.api.routes.admissions import page, view
from app.api.routes.courses import Limit, Offset, authorize
from app.api.routes.schedules import session_view
from app.core.errors import APIError
from app.core.security import now, utc
from app.models import (
    AttendanceSheet,
    BusinessOperation,
    ClassSession,
    Enrollment,
    SessionTeacher,
    StudentProfile,
    TeacherProfile,
)
from app.services import admissions as svc
from app.services.enrollment_lifecycle import active_clause

router = APIRouter(prefix="/attendance", dependencies=[Depends(auth_guard)])


def authorize_teacher(db, tenant, request, response):
    authorize(db, tenant, request, response, "attendance")
    teacher = db.scalar(
        select(TeacherProfile).where(
            TeacherProfile.organization_id == tenant.organization.id,
            TeacherProfile.user_id == tenant.actor.user.id,
            TeacherProfile.archived_at.is_(None),
        )
    )
    if not teacher:
        raise APIError(403, "FORBIDDEN")
    return teacher


def teaching(db, tenant, teacher, session_id):
    row = svc.scoped(db, ClassSession, tenant, session_id)
    if not db.scalar(
        select(SessionTeacher.id).where(
            SessionTeacher.session_id == row.id, SessionTeacher.teacher_profile_id == teacher.id
        )
    ):
        raise APIError(404, "BUSINESS_NOT_FOUND")
    return row


def roster(db, session):
    return list(
        db.scalars(
            select(StudentProfile)
            .join(Enrollment, Enrollment.student_id == StudentProfile.id)
            .where(
                Enrollment.class_id == session.class_id,
                active_clause(session.starts_at),
            )
            .order_by(StudentProfile.full_name, StudentProfile.id)
        )
    )


def sheet_view(db, session):
    sheet = db.scalar(select(AttendanceSheet).where(AttendanceSheet.session_id == session.id))
    records = {r["student_id"]: r for r in sheet.records} if sheet else {}
    return {
        "session": session_view(db, session),
        "version": sheet.version if sheet else 0,
        "finalized": sheet.finalized if sheet else False,
        "can_edit": session.status == "scheduled" and utc(session.starts_at) <= now(),
        "records": [
            {
                "student_id": str(s.id),
                "student_name": s.full_name,
                "status": records.get(str(s.id), {}).get("status", "unmarked"),
                "note": records.get(str(s.id), {}).get("note", ""),
            }
            for s in roster(db, session)
        ],
    }


@router.get("/sessions")
def sessions(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    teacher = authorize_teacher(db, tenant, request, response)
    query = (
        select(ClassSession)
        .join(SessionTeacher, SessionTeacher.session_id == ClassSession.id)
        .where(SessionTeacher.teacher_profile_id == teacher.id, ClassSession.status == "scheduled")
        .order_by(ClassSession.starts_at.desc(), ClassSession.id)
    )
    return page(db, query, limit, offset, lambda s: session_view(db, s))


@router.get("/sessions/{session_id}")
def detail(session_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    teacher = authorize_teacher(db, tenant, request, response)
    return sheet_view(db, teaching(db, tenant, teacher, session_id))


@router.put("/sessions/{session_id}")
def save(
    session_id: UUID,
    body: AttendanceInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    teacher = authorize_teacher(db, tenant, request, response)
    row = teaching(db, tenant, teacher, session_id)
    fp, old = svc.replay(db, tenant, "attendance.save", session_id, body)
    if old is not None:
        return old
    if row.status != "scheduled" or utc(row.starts_at) > now():
        raise APIError(409, "ATTENDANCE_NOT_STARTED")
    sheet = db.scalar(select(AttendanceSheet).where(AttendanceSheet.session_id == row.id))
    svc.expected(sheet, body.version)
    ids = [r.student_id for r in body.records]
    if len(ids) != len(set(ids)) or set(ids) != {s.id for s in roster(db, row)}:
        raise APIError(409, "ATTENDANCE_ROSTER_CHANGED")
    if body.finalized and any(r.status == "unmarked" for r in body.records):
        raise APIError(422, "ATTENDANCE_UNMARKED")
    if sheet and sheet.finalized and (not body.finalized or len(body.reason) < 3):
        raise APIError(422, "BUSINESS_REASON_REQUIRED")
    before = {**sheet_view(db, row), "correction_reason": body.reason}
    if not sheet:
        sheet = AttendanceSheet(
            organization_id=tenant.organization.id, session_id=row.id, class_id=row.class_id
        )
        db.add(sheet)
    sheet.records = [r.model_dump(mode="json") for r in body.records]
    sheet.finalized, sheet.version = body.finalized, body.version + 1
    db.flush()
    return svc.finish(db, tenant, "attendance.save", row.id, body, fp, sheet_view(db, row), before)


@router.get("/sessions/{session_id}/history")
def history(
    session_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    teacher = authorize_teacher(db, tenant, request, response)
    teaching(db, tenant, teacher, session_id)
    return page(
        db,
        select(BusinessOperation)
        .where(
            BusinessOperation.organization_id == tenant.organization.id,
            BusinessOperation.target_id == session_id,
            BusinessOperation.action == "attendance.save",
        )
        .order_by(BusinessOperation.created_at.desc(), BusinessOperation.id),
        limit,
        offset,
        lambda x: view(x, "id actor_id created_at before result"),
    )


@router.get("/mine")
def mine(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response, "catalog")
    profile = svc.own_student(db, tenant)
    query = (
        select(ClassSession)
        .join(Enrollment, Enrollment.class_id == ClassSession.class_id)
        .where(
            Enrollment.student_id == profile.id,
            active_clause(ClassSession.starts_at),
            ClassSession.status == "scheduled",
            ClassSession.starts_at <= now(),
        )
        .order_by(ClassSession.starts_at.desc(), ClassSession.id)
    )
    # Only finalized marks count; unmarked and excused are excluded from the denominator.
    counts = {k: 0 for k in ["unmarked", "present", "late", "absent", "excused"]}

    def mark(session):
        sheet = db.scalar(
            select(AttendanceSheet).where(
                AttendanceSheet.session_id == session.id, AttendanceSheet.finalized.is_(True)
            )
        )
        found = (
            next((r for r in sheet.records if r["student_id"] == str(profile.id)), None)
            if sheet
            else None
        )
        return {
            "session": session_view(db, session),
            "status": found["status"] if found else "unmarked",
            "note": found["note"] if found else "",
        }

    for session in db.scalars(query):
        counts[mark(session)["status"]] += 1
    denominator = counts["present"] + counts["late"] + counts["absent"]
    return {
        **page(db, query, limit, offset, mark),
        "counts": counts,
        "attendance_percent": round(100 * (counts["present"] + counts["late"]) / denominator, 1)
        if denominator
        else None,
    }
