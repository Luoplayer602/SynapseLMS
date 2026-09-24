from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import DB, Tenant, audit, auth_guard, lock_actor
from app.api.student_schemas import (
    ArchiveStudent,
    PersonalChange,
    PersonalProfile,
    StudentChange,
    StudentCreate,
)
from app.core.errors import APIError
from app.core.security import now
from app.models import (
    GuardianContact,
    Organization,
    StudentIdentity,
    StudentProfile,
    User,
    UserMembership,
)

router = APIRouter(prefix="/students", dependencies=[Depends(auth_guard)])


def access(db, tenant, request, response, personal=False):
    """Serialize tenant writes and recheck authority under the identity lock.

    Read requests use the same short lock to avoid returning data after a concurrent
    suspension or support revocation. Lock order matches invitations: org -> actor.
    """
    response.headers["Cache-Control"] = "no-store"
    db.scalar(
        select(Organization)
        .where(Organization.id == tenant.organization.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    lock_actor(db, tenant.actor)
    # tenant_access audits/commits root reads, so use it only as the initial dependency.
    if tenant.actor.user.is_root_admin:
        from app.models import SupportSession

        support = db.scalar(
            select(SupportSession)
            .where(
                SupportSession.id == UUID(request.headers["x-support-session"]),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        from app.core.security import utc

        if (
            not support
            or support.revoked_at
            or utc(support.expires_at) <= now()
            or support.auth_session_id != tenant.actor.session.id
            or support.organization_id != tenant.organization.id
        ):
            raise APIError(403, "SUPPORT_SESSION_REQUIRED")
    else:
        member = db.scalar(
            select(UserMembership)
            .where(
                UserMembership.user_id == tenant.actor.user.id,
                UserMembership.organization_id == tenant.organization.id,
                UserMembership.is_active.is_(True),
                UserMembership.ended_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        if not member:
            raise APIError(403, "TENANT_UNAVAILABLE")
        tenant.role = member.role
    if not tenant.organization.is_active:
        raise APIError(403, "TENANT_UNAVAILABLE")
    if (personal and (tenant.actor.user.is_root_admin or tenant.role != "student")) or (
        not personal and tenant.role not in {"organization_manager", "staff"}
    ):
        raise APIError(403, "FORBIDDEN")


def commit(db):
    try:
        db.commit()
    except (IntegrityError, StaleDataError) as error:
        db.rollback()
        raise APIError(409, "STUDENT_CONFLICT") from error


def personal_id(db, tenant):
    item = db.scalar(
        select(StudentProfile)
        .join(StudentIdentity)
        .where(
            StudentProfile.organization_id == tenant.organization.id,
            StudentIdentity.user_id == tenant.actor.user.id,
        )
    )
    if not item:
        raise APIError(404, "STUDENT_NOT_FOUND")
    return item


def scoped(db, tenant, profile_id):
    item = db.scalar(
        select(StudentProfile).where(
            StudentProfile.id == profile_id,
            StudentProfile.organization_id == tenant.organization.id,
        )
    )
    if not item:
        raise APIError(404, "STUDENT_NOT_FOUND")
    return item


def view(db, item, personal=False, detail=True):
    identity = db.get(StudentIdentity, item.identity_id)
    result = {
        "id": item.id,
        "code": identity.code,
        "full_name": item.full_name,
        "archived": item.archived_at is not None,
        "version": item.version,
    }
    if not detail:
        return result
    user = db.get(User, identity.user_id)
    result.update(
        user_id=user.id,
        email=user.email,
        date_of_birth=item.date_of_birth,
        phone=item.phone,
        address=item.address,
        missing_fields=[] if item.phone else ["phone"],
    )
    result["guardians"] = [
        {
            "full_name": contact.full_name,
            "relationship": contact.relationship,
            "phone": contact.phone,
            "email": contact.email,
            "is_primary": contact.is_primary,
        }
        for contact in db.scalars(
            select(GuardianContact)
            .where(
                GuardianContact.student_profile_id == item.id,
            )
            .order_by(
                GuardianContact.is_primary.desc(), GuardianContact.full_name, GuardianContact.id
            )
        )
    ]
    if not personal:
        result["internal_notes"] = item.internal_notes
    return result


def write_fields(db, item, data):
    fields = data.model_dump(exclude={"guardians", "user_id", "version"})
    for field, value in fields.items():
        setattr(item, field, value)
    db.execute(delete(GuardianContact).where(GuardianContact.student_profile_id == item.id))
    for contact in data.guardians:
        db.add(GuardianContact(student_profile_id=item.id, **contact.model_dump(mode="json")))
    return [*fields, "guardians"]


def create_profile(db, tenant, data, user_id, personal=False):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    member = db.scalar(
        select(UserMembership.id).where(
            UserMembership.user_id == user_id,
            UserMembership.organization_id == tenant.organization.id,
            UserMembership.role == "student",
            UserMembership.is_active.is_(True),
            UserMembership.ended_at.is_(None),
        )
    )
    if not user or not user.is_active or user.is_root_admin or not member:
        raise APIError(404, "STUDENT_ACCOUNT_UNAVAILABLE")
    try:
        identity = db.scalar(select(StudentIdentity).where(StudentIdentity.user_id == user_id))
        if not identity:
            identity = StudentIdentity(user_id=user_id, code=f"SL-{uuid4().hex[:12].upper()}")
            db.add(identity)
            db.flush()
        if db.scalar(
            select(StudentProfile.id).where(
                StudentProfile.identity_id == identity.id,
                StudentProfile.organization_id == tenant.organization.id,
            )
        ):
            raise APIError(409, "STUDENT_EXISTS")
        item = StudentProfile(
            organization_id=tenant.organization.id,
            identity_id=identity.id,
            full_name=data.full_name,
        )
        db.add(item)
        db.flush()
        fields = write_fields(db, item, data)
        audit(db, tenant.actor, "student.create", tenant.organization.id, item.id, fields=fields)
        commit(db)
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "STUDENT_CONFLICT") from error
    return view(db, item, personal)


def change_profile(db, tenant, item, data, personal=False):
    if item.archived_at:
        raise APIError(409, "STUDENT_ARCHIVED")
    if data.version != item.version:
        raise APIError(409, "STUDENT_CONFLICT")
    fields = write_fields(db, item, data)
    item.version += 1  # Also protect guardian-only changes with the parent's version.
    audit(db, tenant.actor, "student.update", tenant.organization.id, item.id, fields=fields)
    commit(db)
    return view(db, item, personal)


Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Search = Annotated[str, Query(max_length=100)]


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
    conditions = [StudentProfile.organization_id == tenant.organization.id]
    if status != "all":
        conditions.append(
            StudentProfile.archived_at.is_(None)
            if status == "active"
            else StudentProfile.archived_at.is_not(None)
        )
    if q.strip():
        conditions.append(
            or_(
                StudentProfile.full_name.icontains(q.strip(), autoescape=True),
                StudentIdentity.code.icontains(q.strip(), autoescape=True),
            )
        )
    query = select(StudentProfile).join(StudentIdentity).where(*conditions)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(StudentProfile.created_at.desc(), StudentProfile.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [view(db, item, detail=False) for item in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


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
        select(StudentProfile.id)
        .join(StudentIdentity)
        .where(
            StudentProfile.organization_id == tenant.organization.id,
            StudentIdentity.user_id == User.id,
        )
    )
    query = (
        select(User)
        .join(UserMembership, UserMembership.user_id == User.id)
        .where(
            UserMembership.organization_id == tenant.organization.id,
            UserMembership.role == "student",
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
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            {"id": u.id, "email": u.email, "display_name": u.display_name}
            for u in db.scalars(query.order_by(User.email).limit(limit).offset(offset))
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
def create(data: StudentCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    access(db, tenant, request, response)
    return create_profile(db, tenant, data, data.user_id)


@router.get("/me")
def me(db: DB, tenant: Tenant, request: Request, response: Response):
    access(db, tenant, request, response, personal=True)
    return view(db, personal_id(db, tenant), personal=True)


@router.post("/me", status_code=201)
def create_me(data: PersonalProfile, db: DB, tenant: Tenant, request: Request, response: Response):
    access(db, tenant, request, response, personal=True)
    return create_profile(db, tenant, data, tenant.actor.user.id, personal=True)


@router.patch("/me")
def change_me(data: PersonalChange, db: DB, tenant: Tenant, request: Request, response: Response):
    access(db, tenant, request, response, personal=True)
    return change_profile(db, tenant, personal_id(db, tenant), data, personal=True)


@router.get("/{profile_id}")
def detail(profile_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    access(db, tenant, request, response)
    return view(db, scoped(db, tenant, profile_id))


@router.patch("/{profile_id}")
def change(
    profile_id: UUID,
    data: StudentChange,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    access(db, tenant, request, response)
    return change_profile(db, tenant, scoped(db, tenant, profile_id), data)


@router.post("/{profile_id}/archive")
def archive(
    profile_id: UUID,
    data: ArchiveStudent,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    access(db, tenant, request, response)
    item = scoped(db, tenant, profile_id)
    if item.version != data.version:
        raise APIError(409, "STUDENT_CONFLICT")
    item.archived_at = now() if data.archived else None
    item.version += 1
    audit(
        db,
        tenant.actor,
        "student.archive" if data.archived else "student.restore",
        tenant.organization.id,
        item.id,
        reason=data.reason,
    )
    commit(db)
    return view(db, item)
