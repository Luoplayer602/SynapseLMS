"""Tenant-scoped individual session operations and a bounded weekly agenda."""

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select

from app.api.dependencies import DB, Tenant, auth_guard
from app.api.routes import classrooms, schedules
from app.api.routes.courses import Limit, Offset, authorize
from app.api.schedule_schemas import SessionOperation
from app.core.errors import APIError
from app.core.security import digest, now, utc
from app.models import (
    Branch,
    ClassSession,
    Enrollment,
    LearningClass,
    Room,
    SessionHistory,
    SessionTeacher,
    StudentIdentity,
    StudentProfile,
    TeacherProfile,
)
from app.services import admissions as admissions_service
from app.services import enrollment_lifecycle as lifecycle

router = APIRouter(dependencies=[Depends(auth_guard)])


def teachers_of(db, row):
    return list(
        db.scalars(
            select(SessionTeacher.teacher_profile_id)
            .where(SessionTeacher.session_id == row.id)
            .order_by(SessionTeacher.teacher_profile_id)
        )
    )


def snapshot(db, row):
    return jsonable_encoder(
        {**schedules.session_view(db, row), "override_reason": row.override_reason}
    )


def detail(db, row):
    item = db.get(LearningClass, row.class_id)
    teachers, rooms = schedules.options(db, item)
    return {
        "session": schedules.session_view(db, row),
        "class": classrooms.class_view(db, item),
        "teachers": teachers,
        "rooms": rooms,
        "override_reason": row.override_reason,
        "can_edit": utc(row.starts_at) > now(),
        "server_now": now(),
    }


@router.get("/class-sessions/options")
def agenda_options(db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response)
    result = {}
    for key, model, label in [
        ("branches", Branch, "name"),
        ("rooms", Room, "name"),
        ("teachers", TeacherProfile, "full_name"),
    ]:
        result[key] = [
            {"id": row.id, "name": getattr(row, label)}
            for row in db.scalars(
                select(model)
                .where(model.organization_id == tenant.organization.id)
                .order_by(getattr(model, label), model.id)
            )
        ]
    return result


@router.get("/class-sessions")
def agenda(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    starts_on: date,
    ends_on: date,
    branch_id: UUID | None = None,
    room_id: UUID | None = None,
    teacher_id: UUID | None = None,
    status: Literal["scheduled", "cancelled", "all"] = "scheduled",
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response)
    if not 0 <= (ends_on - starts_on).days <= 30:
        raise APIError(422, "SESSION_AGENDA_RANGE")
    for model, value in [(Branch, branch_id), (Room, room_id), (TeacherProfile, teacher_id)]:
        if value:
            classrooms.scoped(db, model, tenant, value)
    query = select(ClassSession).where(ClassSession.organization_id == tenant.organization.id)
    if status != "all":
        query = query.where(ClassSession.status == status)
    if branch_id:
        query = query.where(ClassSession.branch_id == branch_id)
    if room_id:
        query = query.where(ClassSession.room_id == room_id)
    if teacher_id:
        query = query.where(
            ClassSession.id.in_(
                select(SessionTeacher.session_id).where(
                    SessionTeacher.teacher_profile_id == teacher_id
                )
            )
        )
    # Coarse indexed UTC bounds then exact branch-local date. Mixed branch zones
    # must not be interpreted using the browser's timezone.
    query = query.where(
        ClassSession.starts_at >= datetime.combine(starts_on, time(), UTC) - timedelta(days=1),
        ClassSession.starts_at < datetime.combine(ends_on, time(), UTC) + timedelta(days=2),
    )
    ids = [
        r.id
        for r in db.scalars(query.order_by(ClassSession.starts_at, ClassSession.id))
        if starts_on <= utc(r.starts_at).astimezone(ZoneInfo(r.timezone)).date() <= ends_on
    ]
    selected = ids[offset : offset + limit]
    by_id = (
        {r.id: r for r in db.scalars(select(ClassSession).where(ClassSession.id.in_(selected)))}
        if selected
        else {}
    )
    return {
        "items": [schedules.session_view(db, by_id[i]) for i in selected],
        "total": len(ids),
        "limit": limit,
        "offset": offset,
    }


@router.get("/class-sessions/{session_id}")
def session_detail(session_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response)
    return detail(db, classrooms.scoped(db, ClassSession, tenant, session_id))


@router.get("/class-sessions/{session_id}/history")
def history(
    session_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response)
    classrooms.scoped(db, ClassSession, tenant, session_id)
    query = (
        select(SessionHistory)
        .where(SessionHistory.session_id == session_id)
        .order_by(SessionHistory.version.desc())
    )
    return classrooms.page(
        db,
        query,
        lambda h: {
            k: getattr(h, k)
            for k in ("id", "actor_id", "created_at", "action", "reason", "before", "after")
        },
        limit,
        offset,
    )


def candidate(db, tenant, row, data):
    classrooms.expected(row, data.version)
    if utc(row.starts_at) <= now():
        raise APIError(409, "SESSION_PAST")
    if (data.action == "restore") != (row.status == "cancelled"):
        raise APIError(409, "SESSION_STATE")
    item = db.get(LearningClass, row.class_id)
    start, end, room_id = utc(row.starts_at), utc(row.ends_at), row.room_id
    ids = data.teacher_ids if data.action == "substitute" else teachers_of(db, row)
    override = data.override_reason if data.action == "substitute" else row.override_reason
    status = "cancelled" if data.action == "cancel" else "scheduled"
    if data.action == "reschedule":
        if not item.starts_on <= data.day <= item.ends_on:
            raise APIError(422, "SCHEDULE_DATE_RANGE")
        start = schedules.local_instant(data.day, data.starts_at, ZoneInfo(row.timezone))
        end = schedules.local_instant(data.day, data.ends_at, ZoneInfo(row.timezone))
        room_id = data.room_id
    if start <= now() or end <= start:
        raise APIError(409, "SESSION_PAST")
    issues, conflicts = [], []
    if status == "scheduled":
        branch = db.get(Branch, row.branch_id)
        if item.status != "draft" or branch.archived_at:
            issues.append("SCHEDULE_CLASS_UNAVAILABLE")
        room = classrooms.scoped(db, Room, tenant, room_id) if room_id else None
        if row.format == "online":
            if room:
                issues.append("SCHEDULE_ONLINE_ROOM")
        elif (
            not room
            or room.branch_id != row.branch_id
            or room.archived_at
            or room.capacity < row.capacity
        ):
            issues.append("SCHEDULE_ROOM_UNAVAILABLE")
        if not ids:
            issues.append("SCHEDULE_TEACHER_REQUIRED")
        for teacher_id in ids:
            teacher = classrooms.scoped(db, TeacherProfile, tenant, teacher_id)
            view = schedules.teacher_view(db, item, teacher)
            if not view["active"]:
                issues.append("SCHEDULE_TEACHER_UNAVAILABLE")
            if not view["qualified"] and len(override) < 3:
                issues.append("SCHEDULE_OVERRIDE_REQUIRED")
        conflicts, _ = schedules.resource_conflicts(
            db,
            item,
            [
                {
                    "slot": 0,
                    "date": str(start.astimezone(ZoneInfo(row.timezone)).date()),
                    "starts_at": start,
                    "ends_at": end,
                    "room_id": str(room_id) if room_id else None,
                    "teacher_ids": [str(i) for i in ids],
                }
            ],
            exclude_id=row.id,
        )
    try:
        admissions_service.enrollment_session_guard(
            db, row, {"status": status, "starts_at": start, "ends_at": end}
        )
    except APIError as error:
        issues.append(error.code)
    return {
        "starts_at": start,
        "ends_at": end,
        "room_id": room_id,
        "teacher_ids": ids,
        "override_reason": override,
        "status": status,
        "issues": sorted(set(issues)),
        "conflicts": conflicts,
        "can_apply": not issues and not conflicts,
    }


@router.post("/class-sessions/{session_id}/preview")
def preview_operation(
    session_id: UUID,
    data: SessionOperation,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response)
    row = classrooms.scoped(db, ClassSession, tenant, session_id)
    return {"before": schedules.session_view(db, row), "after": candidate(db, tenant, row, data)}


@router.post("/class-sessions/{session_id}/operations")
def apply_operation(
    session_id: UUID,
    data: SessionOperation,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response)
    row = classrooms.scoped(db, ClassSession, tenant, session_id)
    fingerprint = digest(
        json.dumps({"session_id": str(session_id), **data.model_dump(mode="json")}, sort_keys=True)
    )
    previous = db.scalar(
        select(SessionHistory).where(
            SessionHistory.organization_id == tenant.organization.id,
            SessionHistory.request_key == data.request_key,
        )
    )
    if previous:
        if previous.request_digest != fingerprint:
            raise APIError(409, "SESSION_REQUEST_REUSED")
        return {"session": previous.after, "replayed": True}
    if data.action != "cancel":
        schedules.lock_teachers(
            db, data.teacher_ids if data.action == "substitute" else teachers_of(db, row)
        )
    result = candidate(db, tenant, row, data)
    if not result["can_apply"]:
        raise APIError(409, "SCHEDULE_CONFLICT")
    before = snapshot(db, row)
    for key in ("starts_at", "ends_at", "room_id", "override_reason", "status"):
        setattr(row, key, result[key])
    if data.action == "substitute":
        db.execute(delete(SessionTeacher).where(SessionTeacher.session_id == row.id))
        for teacher_id in result["teacher_ids"]:
            db.add(
                SessionTeacher(
                    organization_id=row.organization_id,
                    class_id=row.class_id,
                    session_id=row.id,
                    teacher_profile_id=teacher_id,
                )
            )
    row.version += 1
    db.flush()
    recipients = list(
        db.scalars(
            select(StudentIdentity.user_id)
            .join(StudentProfile, StudentProfile.identity_id == StudentIdentity.id)
            .join(Enrollment, Enrollment.student_id == StudentProfile.id)
            .where(
                Enrollment.class_id == row.class_id,
                lifecycle.active_clause(row.starts_at)
                | lifecycle.active_clause(datetime.fromisoformat(before["starts_at"])),
            )
        )
    )
    teacher_ids = set(teachers_of(db, row)) | {UUID(t["id"]) for t in before["teachers"]}
    recipients.extend(
        db.scalars(select(TeacherProfile.user_id).where(TeacherProfile.id.in_(teacher_ids)))
    )
    admissions_service.notify(
        db,
        row.organization_id,
        recipients,
        "session." + data.action,
        row.id,
        f"session:{row.id}:{row.version}",
    )
    after = snapshot(db, row)
    db.add(
        SessionHistory(
            organization_id=row.organization_id,
            class_id=row.class_id,
            session_id=row.id,
            actor_id=tenant.actor.user.id,
            created_at=now(),
            action=data.action,
            reason=data.reason,
            request_key=data.request_key,
            request_digest=fingerprint,
            version=row.version,
            before=before,
            after=after,
        )
    )
    classrooms.save(db, tenant, row, "session." + data.action, reason=data.reason)
    return {"session": after, "replayed": False}
