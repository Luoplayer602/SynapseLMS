from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.api.classroom_schemas import (
    BranchChange,
    BranchCreate,
    ClassChange,
    ClassCreate,
    ClassState,
    FacilityState,
    RoomChange,
    RoomCreate,
)
from app.api.course_schemas import CatalogCodeAction
from app.api.dependencies import DB, Tenant, audit, auth_guard
from app.api.routes.courses import Limit, Offset, Search, authorize, course_view
from app.core.errors import APIError
from app.core.security import now
from app.models import Branch, Course, LearningClass, Room

router = APIRouter(dependencies=[Depends(auth_guard)])
Facility = Literal["branches", "rooms"]
FACILITIES = {"branches": Branch, "rooms": Room}


def scoped(db, model, tenant, item_id):
    item = db.scalar(
        select(model).where(model.id == item_id, model.organization_id == tenant.organization.id)
    )
    if not item:
        raise APIError(404, "CLASS_RESOURCE_NOT_FOUND")
    return item


def expected(item, version):
    if item.version != version:
        raise APIError(409, "CLASS_RESOURCE_CONFLICT")


def active(item):
    if item.archived_at:
        raise APIError(409, "FACILITY_ARCHIVED")


def commit(db):
    try:
        db.commit()
    except (IntegrityError, StaleDataError) as error:
        db.rollback()
        raise APIError(409, "CLASS_RESOURCE_CONFLICT") from error


def save(db, tenant, item, action, fields=None, reason=None):
    try:
        db.flush()
        details = {}
        if fields is not None:
            details["fields"] = list(fields)
        if reason is not None:
            details["reason"] = reason
        audit(db, tenant.actor, action, tenant.organization.id, item.id, **details)
        commit(db)
    except (IntegrityError, StaleDataError) as error:
        db.rollback()
        raise APIError(409, "CLASS_RESOURCE_CONFLICT") from error


def facility_view(db, item):
    result = {key: getattr(item, key) for key in ("id", "code", "name", "version")}
    result["archived"] = item.archived_at is not None
    if isinstance(item, Branch):
        result.update(address=item.address, timezone=item.timezone)
    else:
        branch = db.get(Branch, item.branch_id)
        result.update(
            branch_id=item.branch_id,
            branch_name=branch.name,
            capacity=item.capacity,
            notes=item.notes,
            branch_archived=branch.archived_at is not None,
        )
    return result


def class_view(db, item):
    result = {
        key: getattr(item, key)
        for key in (
            "id",
            "code",
            "name",
            "version",
            "course_id",
            "branch_id",
            "room_id",
            "capacity",
            "starts_on",
            "ends_on",
            "format",
            "status",
            "course_snapshot",
        )
    }
    branch = db.get(Branch, item.branch_id)
    room = db.get(Room, item.room_id) if item.room_id else None
    course = db.get(Course, item.course_id)
    result.update(
        branch_name=branch.name,
        branch_archived=branch.archived_at is not None,
        timezone=branch.timezone,
        room_name=room.name if room else None,
        room_archived=bool(room and room.archived_at),
        course_status=course.status,
    )
    return result


def page(db, query, view, limit, offset):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return {
        "items": [view(item) for item in db.scalars(query.limit(limit).offset(offset))],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/facilities/{kind}")
def facilities(
    kind: Facility,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    q: Search = "",
    status: Literal["active", "archived", "all"] = "active",
    branch_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response)
    model = FACILITIES[kind]
    query = select(model).where(
        model.organization_id == tenant.organization.id,
        or_(
            model.name.icontains(q.strip(), autoescape=True),
            model.code.icontains(q.strip(), autoescape=True),
        ),
    )
    if status != "all":
        query = query.where(
            model.archived_at.is_(None) if status == "active" else model.archived_at.is_not(None)
        )
    if kind == "rooms" and branch_id:
        query = query.where(Room.branch_id == branch_id)
    return page(
        db,
        query.order_by(model.code, model.id),
        lambda item: facility_view(db, item),
        limit,
        offset,
    )


@router.get("/facilities/{kind}/{item_id}")
def facility_detail(
    kind: Facility, item_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response)
    return facility_view(db, scoped(db, FACILITIES[kind], tenant, item_id))


@router.post("/facilities/branches", status_code=201)
def create_branch(data: BranchCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    item = Branch(organization_id=tenant.organization.id, **data.model_dump())
    db.add(item)
    save(db, tenant, item, "branch.create")
    return facility_view(db, item)


@router.post("/facilities/rooms", status_code=201)
def create_room(data: RoomCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    active(scoped(db, Branch, tenant, data.branch_id))
    item = Room(organization_id=tenant.organization.id, **data.model_dump())
    db.add(item)
    save(db, tenant, item, "room.create")
    return facility_view(db, item)


@router.patch("/facilities/branches/{item_id}")
def change_branch(
    item_id: UUID, data: BranchChange, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, Branch, tenant, item_id)
    active(item)
    expected(item, data.version)
    fields = data.model_dump(exclude={"version"})
    for key, value in fields.items():
        setattr(item, key, value)
    item.version += 1
    save(db, tenant, item, "branch.update", fields)
    return facility_view(db, item)


@router.patch("/facilities/rooms/{item_id}")
def change_room(
    item_id: UUID, data: RoomChange, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, Room, tenant, item_id)
    active(item)
    active(scoped(db, Branch, tenant, item.branch_id))
    expected(item, data.version)
    if db.scalar(
        select(LearningClass.id)
        .where(
            LearningClass.room_id == item.id,
            LearningClass.status == "draft",
            LearningClass.capacity > data.capacity,
        )
        .limit(1)
    ):
        raise APIError(409, "ROOM_CAPACITY_IN_USE")
    fields = data.model_dump(exclude={"version"})
    for key, value in fields.items():
        setattr(item, key, value)
    item.version += 1
    save(db, tenant, item, "room.update", fields)
    return facility_view(db, item)


def facility_unused(db, item, active_only=False):
    conditions = (
        [LearningClass.branch_id == item.id]
        if isinstance(item, Branch)
        else [LearningClass.room_id == item.id]
    )
    if active_only:
        conditions.append(LearningClass.status == "draft")
    used = db.scalar(select(LearningClass.id).where(*conditions).limit(1))
    if isinstance(item, Branch):
        rooms = select(Room.id).where(Room.branch_id == item.id)
        if active_only:
            rooms = rooms.where(Room.archived_at.is_(None))
        used = used or db.scalar(rooms.limit(1))
    if used:
        raise APIError(409, "FACILITY_IN_USE")


@router.post("/facilities/{kind}/{item_id}/state")
def facility_state(
    kind: Facility,
    item_id: UUID,
    data: FacilityState,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, FACILITIES[kind], tenant, item_id)
    expected(item, data.version)
    if data.archived:
        facility_unused(db, item, active_only=True)
    elif isinstance(item, Room):
        active(scoped(db, Branch, tenant, item.branch_id))
    item.archived_at = now() if data.archived else None
    item.version += 1
    save(
        db,
        tenant,
        item,
        f"{kind}.archive" if data.archived else f"{kind}.restore",
        reason=data.reason,
    )
    return facility_view(db, item)


@router.patch("/facilities/{kind}/{item_id}/code")
def facility_code(
    kind: Facility,
    item_id: UUID,
    data: CatalogCodeAction,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, FACILITIES[kind], tenant, item_id)
    active(item)
    if isinstance(item, Room):
        active(scoped(db, Branch, tenant, item.branch_id))
    expected(item, data.version)
    facility_unused(db, item)
    item.code = data.code
    item.version += 1
    save(db, tenant, item, f"{kind}.code_change", fields=["code"], reason=data.reason)
    return facility_view(db, item)


@router.get("/classes")
def classes(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    q: Search = "",
    status: Literal["draft", "archived", "all"] = "draft",
    course_id: UUID | None = None,
    branch_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response)
    query = select(LearningClass).where(
        LearningClass.organization_id == tenant.organization.id,
        or_(
            LearningClass.code.icontains(q.strip(), autoescape=True),
            LearningClass.name.icontains(q.strip(), autoescape=True),
        ),
    )
    if status != "all":
        query = query.where(LearningClass.status == status)
    if course_id:
        query = query.where(LearningClass.course_id == course_id)
    if branch_id:
        query = query.where(LearningClass.branch_id == branch_id)
    return page(
        db,
        query.order_by(LearningClass.created_at.desc(), LearningClass.id),
        lambda item: class_view(db, item),
        limit,
        offset,
    )


def validate_facilities(db, tenant, data):
    active(scoped(db, Branch, tenant, data.branch_id))
    if data.room_id:
        room = scoped(db, Room, tenant, data.room_id)
        active(room)
        if room.branch_id != data.branch_id:
            raise APIError(422, "CLASS_ROOM_MISMATCH")
        if data.capacity > room.capacity:
            raise APIError(409, "CLASS_CAPACITY_EXCEEDED")


@router.post("/classes", status_code=201)
def create_class(data: ClassCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response)
    course = scoped(db, Course, tenant, data.course_id)
    if course.status != "published":
        raise APIError(409, "CLASS_PUBLISHED_COURSE_REQUIRED")
    validate_facilities(db, tenant, data)
    snapshot = jsonable_encoder(course_view(db, course, catalog=True))
    snapshot["captured_at"] = now().isoformat()
    item = LearningClass(
        organization_id=tenant.organization.id,
        **data.model_dump(),
        course_snapshot=snapshot,
        **{
            key: getattr(course, key)
            for key in ("language_id", "framework_id", "entry_level_id", "exit_level_id")
        },
    )
    db.add(item)
    save(db, tenant, item, "class.create")
    return class_view(db, item)


@router.get("/classes/{item_id}")
def class_detail(item_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response)
    return class_view(db, scoped(db, LearningClass, tenant, item_id))


def draft(item):
    if item.status != "draft":
        raise APIError(409, "CLASS_DRAFT_REQUIRED")


@router.patch("/classes/{item_id}")
def change_class(
    item_id: UUID, data: ClassChange, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response)
    item = scoped(db, LearningClass, tenant, item_id)
    expected(item, data.version)
    draft(item)
    validate_facilities(db, tenant, data)
    fields = data.model_dump(exclude={"version"})
    for key, value in fields.items():
        setattr(item, key, value)
    item.version += 1
    save(db, tenant, item, "class.update", fields)
    return class_view(db, item)


@router.post("/classes/{item_id}/state")
def class_state(
    item_id: UUID, data: ClassState, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response)
    item = scoped(db, LearningClass, tenant, item_id)
    expected(item, data.version)
    if data.status == "draft":
        validate_facilities(db, tenant, item)
    item.status = data.status
    item.version += 1
    save(
        db,
        tenant,
        item,
        "class.archive" if data.status == "archived" else "class.restore",
        reason=data.reason,
    )
    return class_view(db, item)


@router.patch("/classes/{item_id}/code")
def class_code(
    item_id: UUID,
    data: CatalogCodeAction,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response)
    item = scoped(db, LearningClass, tenant, item_id)
    expected(item, data.version)
    draft(item)
    validate_facilities(db, tenant, item)
    # Extend this guard BEFORE opening enrollment/session modules.
    item.code = data.code
    item.version += 1
    save(db, tenant, item, "class.code_change", fields=["code"], reason=data.reason)
    return class_view(db, item)
