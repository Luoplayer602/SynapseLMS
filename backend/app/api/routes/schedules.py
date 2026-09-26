"""One editable weekly plan per class; confirmation creates immutable reservations."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select

from app.api.dependencies import DB, Tenant, auth_guard
from app.api.routes import classrooms, students
from app.api.routes.courses import Limit, Offset, authorize
from app.api.schedule_schemas import (
    ScheduleConfirmation,
    ScheduleDraft,
    TeacherAssignment,
    WeeklySlot,
)
from app.core.errors import APIError
from app.core.security import digest, now, utc
from app.models import (
    Branch,
    ClassSession,
    ClassTeacher,
    LearningClass,
    Room,
    SchedulePlan,
    SessionTeacher,
    TeacherProfile,
    TeachingCapability,
    TeachingCapabilityLevel,
    User,
    UserMembership,
)

router = APIRouter(dependencies=[Depends(auth_guard)])


def assigned(db, item):
    return list(
        db.scalars(
            select(ClassTeacher)
            .where(ClassTeacher.class_id == item.id)
            .order_by(ClassTeacher.teacher_profile_id)
        )
    )


def has_sessions(db, class_id):
    return (
        db.scalar(select(ClassSession.id).where(ClassSession.class_id == class_id).limit(1))
        is not None
    )


def unlocked(db, item):
    classrooms.draft(item)
    if has_sessions(db, item.id):
        raise APIError(409, "SCHEDULE_LOCKED")


def teacher_view(db, item, teacher):
    member = db.scalar(
        select(UserMembership).where(
            UserMembership.organization_id == item.organization_id,
            UserMembership.user_id == teacher.user_id,
            UserMembership.is_active.is_(True),
            UserMembership.ended_at.is_(None),
            UserMembership.role == "teacher",
        )
    )
    user = db.get(User, teacher.user_id)
    available = bool(
        member and user.is_active and not user.is_root_admin and not teacher.archived_at
    )
    qualified = (
        db.scalar(
            select(TeachingCapabilityLevel.id)
            .join(
                TeachingCapability, TeachingCapability.id == TeachingCapabilityLevel.capability_id
            )
            .where(
                TeachingCapability.teacher_profile_id == teacher.id,
                TeachingCapability.revoked_at.is_(None),
                TeachingCapability.language_id == item.language_id,
                TeachingCapabilityLevel.level_id == item.exit_level_id,
            )
        )
        is not None
    )
    return {
        "id": str(teacher.id),
        "name": teacher.full_name,
        "active": available,
        "qualified": qualified,
        "version": teacher.version,
    }


def options(db, item):
    teachers = [
        teacher_view(db, item, teacher)
        for teacher in db.scalars(
            select(TeacherProfile)
            .where(TeacherProfile.organization_id == item.organization_id)
            .order_by(TeacherProfile.full_name, TeacherProfile.id)
        )
    ]
    rooms = [
        classrooms.facility_view(db, room)
        for room in db.scalars(
            select(Room)
            .where(Room.organization_id == item.organization_id, Room.branch_id == item.branch_id)
            .order_by(Room.code, Room.id)
        )
    ]
    return teachers, rooms


def lock_teachers(db, profile_ids):
    # Account suspension is global, not protected by a tenant lock. Acquire target
    # accounts in stable order after org/actor, matching admin user mutations.
    user_ids = select(TeacherProfile.user_id).where(TeacherProfile.id.in_(profile_ids))
    list(
        db.scalars(
            select(User)
            .where(User.id.in_(user_ids), User.is_root_admin.is_(False))
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def plan_for(db, item):
    return db.scalar(select(SchedulePlan).where(SchedulePlan.class_id == item.id))


def session_view(db, row):
    item = db.get(LearningClass, row.class_id)
    room = db.get(Room, row.room_id) if row.room_id else None
    branch = db.get(Branch, row.branch_id)
    teachers = list(
        db.scalars(
            select(TeacherProfile)
            .join(SessionTeacher, SessionTeacher.teacher_profile_id == TeacherProfile.id)
            .where(SessionTeacher.session_id == row.id)
            .order_by(TeacherProfile.full_name, TeacherProfile.id)
        )
    )
    return {
        "id": row.id,
        "class_id": item.id,
        "class_name": item.name,
        "class_code": item.code,
        "branch_name": branch.name,
        "room_name": room.name if room else None,
        "starts_at": utc(row.starts_at),
        "ends_at": utc(row.ends_at),
        "timezone": row.timezone,
        "format": row.format,
        "teachers": [{"id": x.id, "name": x.full_name} for x in teachers],
    }


def context(db, item):
    plan = plan_for(db, item)
    teachers, rooms = options(db, item)
    return {
        "class": classrooms.class_view(db, item),
        "teachers": teachers,
        "rooms": rooms,
        "assignments": [
            {"teacher_id": x.teacher_profile_id, "override_reason": x.override_reason}
            for x in assigned(db, item)
        ],
        "plan": None
        if not plan
        else {
            "starts_on": plan.starts_on,
            "ends_on": plan.ends_on,
            "slots": plan.slots,
            "confirmed_at": plan.confirmed_at,
        },
        "sessions": [
            session_view(db, row)
            for row in db.scalars(
                select(ClassSession)
                .where(ClassSession.class_id == item.id)
                .order_by(ClassSession.starts_at, ClassSession.id)
            )
        ],
    }


@router.get("/classes/{class_id}/planning")
def planning(class_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response)
    return context(db, classrooms.scoped(db, LearningClass, tenant, class_id))


@router.put("/classes/{class_id}/teachers")
def assign_teachers(
    class_id: UUID,
    data: TeacherAssignment,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response)
    item = classrooms.scoped(db, LearningClass, tenant, class_id)
    classrooms.expected(item, data.version)
    unlocked(db, item)
    profiles = [
        classrooms.scoped(db, TeacherProfile, tenant, teacher_id) for teacher_id in data.teacher_ids
    ]
    lock_teachers(db, [teacher.id for teacher in profiles])
    views = [teacher_view(db, item, teacher) for teacher in profiles]
    if any(not x["active"] for x in views):
        raise APIError(409, "SCHEDULE_TEACHER_UNAVAILABLE")
    if any(not x["qualified"] for x in views) and len(data.override_reason) < 3:
        raise APIError(422, "SCHEDULE_OVERRIDE_REQUIRED")
    db.execute(delete(ClassTeacher).where(ClassTeacher.class_id == item.id))
    for teacher in profiles:
        db.add(
            ClassTeacher(
                organization_id=item.organization_id,
                class_id=item.id,
                teacher_profile_id=teacher.id,
                override_reason=data.override_reason,
            )
        )
    item.version += 1
    classrooms.save(
        db, tenant, item, "class.teachers", fields=["teacher_ids"], reason=data.override_reason
    )
    return context(db, item)


@router.put("/classes/{class_id}/schedule")
def save_draft(
    class_id: UUID,
    data: ScheduleDraft,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response)
    item = classrooms.scoped(db, LearningClass, tenant, class_id)
    classrooms.expected(item, data.version)
    unlocked(db, item)
    classrooms.active(classrooms.scoped(db, Branch, tenant, item.branch_id))
    if data.starts_on < item.starts_on or data.ends_on > item.ends_on:
        raise APIError(422, "SCHEDULE_DATE_RANGE")
    teacher_ids = {x.teacher_profile_id for x in assigned(db, item)}
    for slot in data.slots:
        if not set(slot.teacher_ids) <= teacher_ids:
            raise APIError(422, "SCHEDULE_UNASSIGNED_TEACHER")
        if item.format == "online" and slot.room_id:
            raise APIError(422, "SCHEDULE_ONLINE_ROOM")
        if slot.room_id:
            room = classrooms.scoped(db, Room, tenant, slot.room_id)
            if room.branch_id != item.branch_id:
                raise APIError(422, "CLASS_ROOM_MISMATCH")
    plan = plan_for(db, item)
    if not plan:
        plan = SchedulePlan(organization_id=item.organization_id, class_id=item.id)
        db.add(plan)
    plan.starts_on, plan.ends_on = data.starts_on, data.ends_on
    plan.slots = jsonable_encoder(data.slots)
    item.version += 1
    classrooms.save(db, tenant, item, "schedule.draft", fields=["starts_on", "ends_on", "slots"])
    return context(db, item)


def local_instant(day, clock, zone):
    """Reject nonexistent AND ambiguous local wall times rather than guessing DST."""
    naive = datetime.combine(day, clock)
    candidates = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        if aware.astimezone(zone).replace(tzinfo=None) == naive:
            candidates.add(aware)
    if len(candidates) != 1:
        raise APIError(422, "SCHEDULE_DST_TIME")
    return candidates.pop()


def overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def preview(db, item, plan):
    if not plan:
        raise APIError(409, "SCHEDULE_DRAFT_REQUIRED")
    branch = db.get(Branch, item.branch_id)
    teachers, rooms = options(db, item)
    teacher_map = {x["id"]: x for x in teachers}
    room_map = {str(x["id"]): x for x in rooms}
    assignment_map = {str(x.teacher_profile_id): x for x in assigned(db, item)}
    zone = ZoneInfo(branch.timezone)
    entries, issues = [], []
    if item.status != "draft" or branch.archived_at:
        issues.append({"code": "SCHEDULE_CLASS_UNAVAILABLE"})
    if plan.starts_on < item.starts_on or plan.ends_on > item.ends_on:
        issues.append({"code": "SCHEDULE_DATE_RANGE"})
    day = plan.starts_on
    while day <= plan.ends_on:
        for index, raw in enumerate(plan.slots):
            slot = WeeklySlot.model_validate(raw)
            if day.weekday() != slot.weekday:
                continue
            start = local_instant(day, slot.starts_at, zone)
            end = local_instant(day, slot.ends_at, zone)
            if end <= start:
                raise APIError(422, "SCHEDULE_DST_TIME")
            entry = {
                "slot": index,
                "date": str(day),
                "starts_at": start,
                "ends_at": end,
                "room_id": str(slot.room_id) if slot.room_id else None,
                "teacher_ids": sorted(str(x) for x in slot.teacher_ids),
            }
            entries.append(entry)
            if len(entries) > 500:
                raise APIError(422, "SCHEDULE_TOO_LARGE")
        day += timedelta(days=1)
    if not entries:
        issues.append({"code": "SCHEDULE_EMPTY"})
    # Validate each slot, including slots with no occurrence in this date range.
    for index, raw in enumerate(plan.slots):
        room = room_map.get(raw["room_id"])
        if item.format == "online" and raw["room_id"]:
            issues.append({"slot": index, "code": "SCHEDULE_ONLINE_ROOM"})
        elif item.format != "online" and (
            not room or room["archived"] or room["capacity"] < item.capacity
        ):
            issues.append({"slot": index, "code": "SCHEDULE_ROOM_UNAVAILABLE"})
        if not raw["teacher_ids"]:
            issues.append({"slot": index, "code": "SCHEDULE_TEACHER_REQUIRED"})
        for teacher_id in raw["teacher_ids"]:
            teacher = teacher_map.get(teacher_id)
            assignment = assignment_map.get(teacher_id)
            if not teacher or not teacher["active"] or not assignment:
                issues.append(
                    {
                        "slot": index,
                        "code": "SCHEDULE_TEACHER_UNAVAILABLE",
                        "teacher_id": teacher_id,
                    }
                )
            elif not teacher["qualified"] and len(assignment.override_reason) < 3:
                issues.append(
                    {"slot": index, "code": "SCHEDULE_OVERRIDE_REQUIRED", "teacher_id": teacher_id}
                )
    entries.sort(key=lambda x: (x["starts_at"], x["slot"]))
    sessions = []
    if entries:
        sessions = list(
            db.scalars(
                select(ClassSession)
                .where(
                    ClassSession.organization_id == item.organization_id,
                    ClassSession.starts_at < max(x["ends_at"] for x in entries),
                    ClassSession.ends_at > entries[0]["starts_at"],
                )
                .order_by(ClassSession.starts_at, ClassSession.id)
            )
        )
    session_teacher_map = {
        row.id: set(
            db.scalars(
                select(SessionTeacher.teacher_profile_id).where(SessionTeacher.session_id == row.id)
            )
        )
        for row in sessions
    }
    conflicts = []
    room_checks = [
        {
            "slot": i,
            "unavailable_room_ids": [
                str(x["id"]) for x in rooms if x["archived"] or x["capacity"] < item.capacity
            ],
        }
        for i in range(len(plan.slots))
    ]
    for pos, entry in enumerate(entries):
        for other in entries[:pos]:
            if overlap(entry["starts_at"], entry["ends_at"], other["starts_at"], other["ends_at"]):
                conflicts.append(
                    {
                        "slot": entry["slot"],
                        "date": entry["date"],
                        "type": "class",
                        "class_code": item.code,
                        "starts_at": other["starts_at"],
                        "ends_at": other["ends_at"],
                    }
                )
        for row in sessions:
            if not overlap(
                entry["starts_at"], entry["ends_at"], utc(row.starts_at), utc(row.ends_at)
            ):
                continue
            if row.room_id:
                room_checks[entry["slot"]]["unavailable_room_ids"].append(str(row.room_id))
            types = []
            if entry["room_id"] and entry["room_id"] == str(row.room_id):
                types.append("room")
            if set(entry["teacher_ids"]) & {str(x) for x in session_teacher_map[row.id]}:
                types.append("teacher")
            if row.class_id == item.id:
                types.append("class")
            for kind in types:
                conflicts.append(
                    {
                        "slot": entry["slot"],
                        "date": entry["date"],
                        "type": kind,
                        "class_code": db.get(LearningClass, row.class_id).code,
                        "starts_at": utc(row.starts_at),
                        "ends_at": utc(row.ends_at),
                    }
                )
    for check in room_checks:
        check["unavailable_room_ids"] = sorted(set(check["unavailable_room_ids"]))
    fingerprint = digest(
        json.dumps(
            jsonable_encoder(
                {
                    "class_id": item.id,
                    "version": item.version,
                    "timezone": branch.timezone,
                    "entries": entries,
                    "teachers": teachers,
                    "rooms": rooms,
                }
            ),
            sort_keys=True,
        )
    )
    return {
        "version": item.version,
        "timezone": branch.timezone,
        "sessions": entries,
        "issues": issues,
        "conflicts": conflicts,
        "room_checks": room_checks,
        "can_confirm": not issues and not conflicts,
        "preview_digest": fingerprint,
    }


@router.get("/classes/{class_id}/schedule/preview")
def preview_schedule(
    class_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    version: int | None = Query(default=None, ge=1),
):
    authorize(db, tenant, request, response)
    item = classrooms.scoped(db, LearningClass, tenant, class_id)
    unlocked(db, item)
    if version is not None:
        classrooms.expected(item, version)
    return preview(db, item, plan_for(db, item))


@router.post("/classes/{class_id}/schedule/confirm")
def confirm_schedule(
    class_id: UUID,
    data: ScheduleConfirmation,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response)
    item = classrooms.scoped(db, LearningClass, tenant, class_id)
    plan = plan_for(db, item)
    if plan and plan.confirmed_at:
        if (
            plan.confirmation_key == data.confirmation_key
            and plan.preview_digest == data.preview_digest
        ):
            return context(db, item)
        raise APIError(409, "SCHEDULE_LOCKED")
    classrooms.expected(item, data.version)
    unlocked(db, item)
    lock_teachers(db, [row.teacher_profile_id for row in assigned(db, item)])
    result = preview(db, item, plan)
    if not result["can_confirm"]:
        raise APIError(409, "SCHEDULE_CONFLICT")
    if data.preview_digest != result["preview_digest"]:
        raise APIError(409, "SCHEDULE_PREVIEW_STALE")
    for entry in result["sessions"]:
        row = ClassSession(
            organization_id=item.organization_id,
            class_id=item.id,
            branch_id=item.branch_id,
            room_id=UUID(entry["room_id"]) if entry["room_id"] else None,
            starts_at=entry["starts_at"],
            ends_at=entry["ends_at"],
            timezone=result["timezone"],
            capacity=item.capacity,
            format=item.format,
        )
        db.add(row)
        db.flush()
        for teacher_id in entry["teacher_ids"]:
            db.add(
                SessionTeacher(
                    organization_id=item.organization_id,
                    class_id=item.id,
                    session_id=row.id,
                    teacher_profile_id=UUID(teacher_id),
                )
            )
    plan.confirmed_at = now()
    plan.confirmation_key = data.confirmation_key
    plan.preview_digest = data.preview_digest
    item.version += 1
    classrooms.save(db, tenant, item, "schedule.confirm", fields=["sessions"])
    return context(db, item)


@router.get("/teaching-sessions")
def my_sessions(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    students.access(db, tenant, request, response, personal=True, personal_role="teacher")
    query = (
        select(ClassSession)
        .join(SessionTeacher, SessionTeacher.session_id == ClassSession.id)
        .join(TeacherProfile, TeacherProfile.id == SessionTeacher.teacher_profile_id)
        .where(
            ClassSession.organization_id == tenant.organization.id,
            TeacherProfile.user_id == tenant.actor.user.id,
        )
    )
    return classrooms.page(
        db,
        query.order_by(ClassSession.starts_at, ClassSession.id),
        lambda row: session_view(db, row),
        limit,
        offset,
    )
