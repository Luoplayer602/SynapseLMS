from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import DB, Tenant, audit, auth_guard
from app.api.routes import students
from app.api.routes.courses import MODELS, Kind
from app.api.routes.proficiencies import label
from app.api.routes.students import Limit, Offset, Search
from app.api.teacher_schemas import (
    CapabilityChange,
    CapabilityCreate,
    CredentialChange,
    CredentialFields,
    PersonalTeacherChange,
    TeacherArchive,
    TeacherChange,
    TeacherCreate,
    TeacherRecordState,
)
from app.core.errors import APIError
from app.core.security import now, utc
from app.models import (
    CourseLanguage,
    CourseLevel,
    LevelFramework,
    TeacherCredential,
    TeacherHistory,
    TeacherHistoryLevel,
    TeacherProfile,
    TeachingCapability,
    TeachingCapabilityLevel,
    User,
    UserMembership,
)

router = APIRouter(prefix="/teachers", dependencies=[Depends(auth_guard)])
RecordKind = Literal["capabilities", "credentials"]
RECORDS = {"capabilities": TeachingCapability, "credentials": TeacherCredential}


def access(db, tenant, request, response, personal=False):
    students.access(db, tenant, request, response, personal=personal, personal_role="teacher")


def profile_for(db, tenant, request, response, profile_ref, writing=False):
    personal = profile_ref == "me"
    access(db, tenant, request, response, personal)
    query = select(TeacherProfile).where(TeacherProfile.organization_id == tenant.organization.id)
    if personal:
        query = query.where(TeacherProfile.user_id == tenant.actor.user.id)
    else:
        try:
            query = query.where(TeacherProfile.id == UUID(profile_ref))
        except ValueError as error:
            raise APIError(404, "TEACHER_NOT_FOUND") from error
    item = db.scalar(query)
    if not item:
        raise APIError(404, "TEACHER_NOT_FOUND")
    if writing and item.archived_at:
        raise APIError(409, "TEACHER_ARCHIVED")
    return item, personal


def expected(item, version):
    if item.version != version:
        raise APIError(409, "TEACHER_CONFLICT")


def commit(db):
    try:
        db.commit()
    except (IntegrityError, StaleDataError) as error:
        db.rollback()
        raise APIError(409, "TEACHER_CONFLICT") from error


def profile_view(db, item, personal=False):
    user = db.get(User, item.user_id)
    data = {
        field: getattr(item, field)
        for field in ("id", "user_id", "full_name", "phone", "introduction", "version")
    }
    data.update(email=user.email, archived=item.archived_at is not None)
    if not personal:
        data["internal_notes"] = item.internal_notes
    return data


def page(db, query, view, limit, offset):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return {
        "items": [view(row) for row in db.scalars(query.limit(limit).offset(offset))],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("")
def listing(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    q: Search = "",
    status: Literal["active", "archived", "all"] = "active",
    limit: Limit = 20,
    offset: Offset = 0,
):
    access(db, tenant, request, response)
    query = (
        select(TeacherProfile)
        .join(User)
        .where(
            TeacherProfile.organization_id == tenant.organization.id,
            or_(
                TeacherProfile.full_name.icontains(q.strip(), autoescape=True),
                User.email.icontains(q.strip(), autoescape=True),
            ),
        )
    )
    if status != "all":
        query = query.where(
            TeacherProfile.archived_at.is_(None)
            if status == "active"
            else TeacherProfile.archived_at.is_not(None)
        )
    return page(
        db,
        query.order_by(TeacherProfile.full_name, TeacherProfile.id),
        lambda row: {
            k: v
            for k, v in profile_view(db, row).items()
            if k in {"id", "full_name", "email", "archived", "version"}
        },
        limit,
        offset,
    )


@router.get("/candidates")
def candidates(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    q: Search = "",
    limit: Limit = 20,
    offset: Offset = 0,
):
    access(db, tenant, request, response)
    has_profile = exists(
        select(TeacherProfile.id).where(
            TeacherProfile.user_id == User.id,
            TeacherProfile.organization_id == tenant.organization.id,
        )
    )
    query = (
        select(User)
        .join(UserMembership, UserMembership.user_id == User.id)
        .where(
            UserMembership.organization_id == tenant.organization.id,
            UserMembership.role == "teacher",
            UserMembership.is_active.is_(True),
            UserMembership.ended_at.is_(None),
            User.is_active.is_(True),
            User.is_root_admin.is_(False),
            ~has_profile,
            or_(
                User.email.icontains(q.strip(), autoescape=True),
                User.display_name.icontains(q.strip(), autoescape=True),
            ),
        )
        .order_by(User.email, User.id)
    )
    return page(
        db,
        query,
        lambda u: {"id": u.id, "email": u.email, "display_name": u.display_name},
        limit,
        offset,
    )


@router.get("/options/{kind}")
def options(
    kind: Kind,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 100,
    offset: Offset = 0,
):
    access(db, tenant, request, response, personal=tenant.role == "teacher")
    model = MODELS[kind]
    query = select(model).where(model.organization_id == tenant.organization.id).order_by(model.id)
    return page(
        db,
        query,
        lambda item: {
            field: getattr(item, field)
            for field in ("id", "code", "name", "language_id", "framework_id", "rank")
            if hasattr(item, field)
        },
        limit,
        offset,
    )


@router.post("", status_code=201)
def create(data: TeacherCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    access(db, tenant, request, response)
    user = db.scalar(select(User).where(User.id == data.user_id).with_for_update())
    member = db.scalar(
        select(UserMembership.id).where(
            UserMembership.user_id == data.user_id,
            UserMembership.organization_id == tenant.organization.id,
            UserMembership.role == "teacher",
            UserMembership.is_active.is_(True),
            UserMembership.ended_at.is_(None),
        )
    )
    if not user or not user.is_active or user.is_root_admin or not member:
        raise APIError(404, "TEACHER_ACCOUNT_UNAVAILABLE")
    item = TeacherProfile(organization_id=tenant.organization.id, **data.model_dump())
    db.add(item)
    try:
        db.flush()
        audit(db, tenant.actor, "teacher.create", tenant.organization.id, item.id)
        commit(db)
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "TEACHER_CONFLICT") from error
    return profile_view(db, item)


@router.get("/{profile_ref}")
def detail(profile_ref: str, db: DB, tenant: Tenant, request: Request, response: Response):
    item, personal = profile_for(db, tenant, request, response, profile_ref)
    return profile_view(db, item, personal)


def change_fields(db, tenant, item, data, personal=False):
    expected(item, data.version)
    fields = data.model_dump(exclude={"version"})
    for key, value in fields.items():
        setattr(item, key, value)
    item.version += 1
    audit(db, tenant.actor, "teacher.update", tenant.organization.id, item.id, fields=list(fields))
    commit(db)
    return profile_view(db, item, personal)


@router.patch("/me")
def change_me(
    data: PersonalTeacherChange, db: DB, tenant: Tenant, request: Request, response: Response
):
    item, _ = profile_for(db, tenant, request, response, "me", writing=True)
    return change_fields(db, tenant, item, data, personal=True)


@router.patch("/{profile_id}")
def change(
    profile_id: UUID,
    data: TeacherChange,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    item, _ = profile_for(db, tenant, request, response, str(profile_id), writing=True)
    return change_fields(db, tenant, item, data)


@router.post("/{profile_id}/archive")
def archive(
    profile_id: UUID,
    data: TeacherArchive,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    item, _ = profile_for(db, tenant, request, response, str(profile_id))
    expected(item, data.version)
    item.archived_at = now() if data.archived else None
    item.version += 1
    audit(
        db,
        tenant.actor,
        "teacher.archive" if data.archived else "teacher.restore",
        tenant.organization.id,
        item.id,
        reason=data.reason,
    )
    commit(db)
    return profile_view(db, item)


def record_view(db, item, personal=False):
    result = {
        "id": item.id,
        "version": item.version,
        "revoked_at": utc(item.revoked_at) if item.revoked_at else None,
        "source": "center",
    }
    if isinstance(item, TeachingCapability):
        result.update(
            language_id=item.language_id, language=label(db, CourseLanguage, item.language_id)
        )
        result["levels"] = [
            {
                **label(db, CourseLevel, ref.level_id),
                "framework": label(db, LevelFramework, ref.framework_id),
            }
            for ref in db.scalars(
                select(TeachingCapabilityLevel)
                .where(TeachingCapabilityLevel.capability_id == item.id)
                .order_by(TeachingCapabilityLevel.level_id)
            )
        ]
    else:
        result.update(
            {key: getattr(item, key) for key in ("name", "issuer", "issued_on", "expires_on")}
        )
        result["expired"] = bool(item.expires_on and item.expires_on < now().date())
        if not personal:
            result["internal_notes"] = item.internal_notes
    return result


def history_record(db, tenant, item, kind, action, reason):
    try:
        db.flush()
        timestamp = now()
        snapshot = jsonable_encoder(record_view(db, item, personal=True))
        snapshot.update(
            kind=kind,
            action=action,
            actor_name=tenant.actor.user.display_name,
            actor_role="root" if tenant.actor.user.is_root_admin else tenant.role,
            occurred_at=timestamp.isoformat(),
        )
        event = TeacherHistory(
            created_at=timestamp,
            organization_id=item.organization_id,
            teacher_profile_id=item.teacher_profile_id,
            capability_id=item.id if kind == "capabilities" else None,
            credential_id=item.id if kind == "credentials" else None,
            language_id=item.language_id if kind == "capabilities" else None,
            actor_id=tenant.actor.user.id,
            version=item.version,
            public_snapshot=snapshot,
            internal_snapshot={
                "reason": reason,
                "internal_notes": getattr(item, "internal_notes", ""),
            },
        )
        db.add(event)
        db.flush()
        if kind == "capabilities":
            for level in db.scalars(
                select(TeachingCapabilityLevel).where(
                    TeachingCapabilityLevel.capability_id == item.id
                )
            ):
                db.add(
                    TeacherHistoryLevel(
                        history_id=event.id,
                        organization_id=item.organization_id,
                        language_id=item.language_id,
                        framework_id=level.framework_id,
                        level_id=level.level_id,
                    )
                )
        audit(
            db,
            tenant.actor,
            f"teacher.{kind}.{action}",
            item.organization_id,
            item.id,
            version=item.version,
        )
        commit(db)
    except (IntegrityError, StaleDataError) as error:
        db.rollback()
        raise APIError(409, "TEACHER_CONFLICT") from error


@router.get("/{profile_ref}/history")
def history(
    profile_ref: str,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    profile, personal = profile_for(db, tenant, request, response, profile_ref)
    query = (
        select(TeacherHistory)
        .where(
            TeacherHistory.teacher_profile_id == profile.id,
            TeacherHistory.organization_id == profile.organization_id,
        )
        .order_by(TeacherHistory.created_at.desc(), TeacherHistory.id.desc())
    )
    return page(
        db,
        query,
        lambda row: {
            **row.public_snapshot,
            "id": row.id,
            **({} if personal else {"internal": row.internal_snapshot}),
        },
        limit,
        offset,
    )


@router.get("/{profile_ref}/{kind}")
def records(
    profile_ref: str,
    kind: RecordKind,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    profile, personal = profile_for(db, tenant, request, response, profile_ref)
    model = RECORDS[kind]
    return page(
        db,
        select(model)
        .where(
            model.teacher_profile_id == profile.id, model.organization_id == profile.organization_id
        )
        .order_by(model.created_at, model.id),
        lambda row: record_view(db, row, personal),
        limit,
        offset,
    )


def staff_profile(db, tenant, request, response, profile_id):
    return profile_for(db, tenant, request, response, str(profile_id), writing=True)[0]


def scoped_record(db, profile, kind, item_id, version):
    model = RECORDS[kind]
    item = db.scalar(
        select(model).where(
            model.id == item_id,
            model.teacher_profile_id == profile.id,
            model.organization_id == profile.organization_id,
        )
    )
    if not item:
        raise APIError(404, "TEACHER_RECORD_NOT_FOUND")
    expected(item, version)
    return item


def replace_levels(db, item, level_ids):
    levels = list(
        db.scalars(
            select(CourseLevel).where(
                CourseLevel.id.in_(level_ids),
                CourseLevel.organization_id == item.organization_id,
                CourseLevel.language_id == item.language_id,
            )
        )
    )
    if len(levels) != len(level_ids):
        raise APIError(422, "TEACHER_LEVEL_MISMATCH")
    db.execute(
        delete(TeachingCapabilityLevel).where(TeachingCapabilityLevel.capability_id == item.id)
    )
    for level in levels:
        db.add(
            TeachingCapabilityLevel(
                capability_id=item.id,
                organization_id=item.organization_id,
                language_id=item.language_id,
                framework_id=level.framework_id,
                level_id=level.id,
            )
        )


@router.post("/{profile_id}/capabilities", status_code=201)
def add_capability(
    profile_id: UUID,
    data: CapabilityCreate,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    profile = staff_profile(db, tenant, request, response, profile_id)
    if not db.scalar(
        select(CourseLanguage.id).where(
            CourseLanguage.id == data.language_id,
            CourseLanguage.organization_id == profile.organization_id,
        )
    ):
        raise APIError(422, "TEACHER_LEVEL_MISMATCH")
    item = TeachingCapability(
        organization_id=profile.organization_id,
        teacher_profile_id=profile.id,
        language_id=data.language_id,
    )
    db.add(item)
    try:
        db.flush()
        replace_levels(db, item, data.level_ids)
        history_record(db, tenant, item, "capabilities", "create", data.reason)
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "TEACHER_CONFLICT") from error
    return record_view(db, item)


@router.patch("/{profile_id}/capabilities/{item_id}")
def change_capability(
    profile_id: UUID,
    item_id: UUID,
    data: CapabilityChange,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    profile = staff_profile(db, tenant, request, response, profile_id)
    item = scoped_record(db, profile, "capabilities", item_id, data.version)
    if item.revoked_at:
        raise APIError(409, "TEACHER_RECORD_REVOKED")
    replace_levels(db, item, data.level_ids)
    item.version += 1
    history_record(db, tenant, item, "capabilities", "update", data.reason)
    return record_view(db, item)


@router.post("/{profile_id}/credentials", status_code=201)
def add_credential(
    profile_id: UUID,
    data: CredentialFields,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    profile = staff_profile(db, tenant, request, response, profile_id)
    item = TeacherCredential(
        organization_id=profile.organization_id,
        teacher_profile_id=profile.id,
        **data.model_dump(exclude={"reason"}),
    )
    db.add(item)
    history_record(db, tenant, item, "credentials", "create", data.reason)
    return record_view(db, item)


@router.patch("/{profile_id}/credentials/{item_id}")
def change_credential(
    profile_id: UUID,
    item_id: UUID,
    data: CredentialChange,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    profile = staff_profile(db, tenant, request, response, profile_id)
    item = scoped_record(db, profile, "credentials", item_id, data.version)
    if item.revoked_at:
        raise APIError(409, "TEACHER_RECORD_REVOKED")
    for key, value in data.model_dump(exclude={"reason", "version"}).items():
        setattr(item, key, value)
    item.version += 1
    history_record(db, tenant, item, "credentials", "update", data.reason)
    return record_view(db, item)


@router.post("/{profile_id}/{kind}/{item_id}/state")
def record_state(
    profile_id: UUID,
    kind: RecordKind,
    item_id: UUID,
    data: TeacherRecordState,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    profile = staff_profile(db, tenant, request, response, profile_id)
    item = scoped_record(db, profile, kind, item_id, data.version)
    item.revoked_at = now() if data.revoked else None
    item.version += 1
    history_record(db, tenant, item, kind, "revoke" if data.revoked else "restore", data.reason)
    return record_view(db, item)
