import secrets
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DB, Manager, Root, Tenant, audit, browser_guard
from app.api.schemas import (
    InviteCreate,
    MemberChange,
    MemberCreate,
    OrganizationChange,
    OrganizationCreate,
    SupportCreate,
    UserChange,
)
from app.core.errors import APIError
from app.core.security import digest, now, password_hasher
from app.models import (
    AuthSession,
    Organization,
    OrganizationInvite,
    SupportSession,
    User,
    UserMembership,
)

router = APIRouter(dependencies=[Depends(browser_guard)])


@router.patch("/admin/users/{user_id}")
def change_user(user_id: UUID, data: UserChange, db: DB, root: Root):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        raise APIError(404, "NOT_FOUND")
    if user.is_root_admin:
        raise APIError(403, "FORBIDDEN")
    user.is_active = data.is_active
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    audit(
        db,
        root,
        "user.status_change",
        target_id=user.id,
        reason=data.reason,
        is_active=data.is_active,
    )
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


def organization_view(org):
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "is_active": org.is_active,
        "is_public": org.is_public,
        "registration_enabled": org.registration_enabled,
    }


def commit(db):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "RESOURCE_CONFLICT") from error


@router.get("/admin/organizations")
def organizations(db: DB, root: Root, limit: Annotated[int, Query(ge=1, le=100)] = 100):
    return [
        organization_view(o)
        for o in db.scalars(select(Organization).order_by(Organization.name).limit(limit))
    ]


@router.post("/admin/organizations", status_code=201)
def create_organization(data: OrganizationCreate, db: DB, root: Root):
    org = Organization(**data.model_dump())
    db.add(org)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "RESOURCE_CONFLICT") from error
    audit(db, root, "organization.create", org.id, org.id)
    commit(db)
    return organization_view(org)


@router.patch("/admin/organizations/{organization_id}")
def change_organization(organization_id: UUID, data: OrganizationChange, db: DB, root: Root):
    org = db.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )
    if not org:
        raise APIError(404, "NOT_FOUND")
    for key, value in data.model_dump(exclude={"reason"}).items():
        setattr(org, key, value)
    audit(db, root, "organization.change", org.id, org.id, reason=data.reason)
    commit(db)
    return organization_view(org)


@router.post("/admin/support-sessions", status_code=201)
def start_support(data: SupportCreate, db: DB, root: Root):
    org = db.scalar(
        select(Organization).where(Organization.id == data.organization_id).with_for_update()
    )
    if not org or not org.is_active:
        raise APIError(404, "NOT_FOUND")
    support = SupportSession(
        user_id=root.user.id,
        auth_session_id=root.session.id,
        organization_id=org.id,
        reason=data.reason,
        expires_at=now() + timedelta(minutes=data.minutes),
    )
    db.add(support)
    db.flush()
    audit(db, root, "support.start", org.id, support.id, reason=data.reason)
    db.commit()
    return {"id": support.id, "organization_id": org.id, "expires_at": support.expires_at}


@router.delete("/admin/support-sessions/{support_id}", status_code=204)
def end_support(support_id: UUID, db: DB, root: Root):
    support = db.scalar(
        select(SupportSession).where(
            SupportSession.id == support_id,
            SupportSession.user_id == root.user.id,
            SupportSession.auth_session_id == root.session.id,
        )
    )
    if not support:
        raise APIError(404, "NOT_FOUND")
    # Match tenant handler lock order before updating support or inserting audit.
    db.scalar(
        select(Organization).where(Organization.id == support.organization_id).with_for_update()
    )
    db.refresh(support)
    support.revoked_at = now()
    audit(db, root, "support.end", support.organization_id, support.id)
    db.commit()


@router.get("/organization")
def current_organization(tenant: Tenant):
    return organization_view(tenant.organization)


@router.post("/organization/invites", status_code=201)
def invite(data: InviteCreate, db: DB, manager: Manager):
    raw = secrets.token_urlsafe(32)
    item = OrganizationInvite(
        organization_id=manager.organization.id,
        token_hash=digest(raw),
        expires_at=now() + timedelta(days=data.expires_days),
        max_uses=data.max_uses,
    )
    db.add(item)
    db.flush()
    audit(db, manager.actor, "invite.create", manager.organization.id, item.id)
    db.commit()
    return {"id": item.id, "code": raw, "expires_at": item.expires_at, "max_uses": item.max_uses}


@router.delete("/organization/invites/{invite_id}", status_code=204)
def revoke_invite(invite_id: UUID, db: DB, manager: Manager):
    item = db.scalar(
        select(OrganizationInvite)
        .where(
            OrganizationInvite.id == invite_id,
            OrganizationInvite.organization_id == manager.organization.id,
        )
        .with_for_update()
    )
    if not item:
        raise APIError(404, "NOT_FOUND")
    item.revoked_at = now()
    audit(db, manager.actor, "invite.revoke", manager.organization.id, item.id)
    db.commit()


def member_view(user, member):
    return {
        "id": member.id,
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": member.role,
        "is_active": member.is_active,
    }


@router.get("/members")
def members(db: DB, manager: Manager, limit: Annotated[int, Query(ge=1, le=100)] = 100):
    rows = db.execute(
        select(User, UserMembership)
        .join(UserMembership, UserMembership.user_id == User.id)
        .where(
            UserMembership.organization_id == manager.organization.id,
            UserMembership.ended_at.is_(None),
        )
        .order_by(User.email)
        .limit(limit)
    )
    return [member_view(user, member) for user, member in rows]


@router.post("/members", status_code=201)
def create_member(data: MemberCreate, db: DB, manager: Manager):
    if data.role == "organization_manager" and not manager.actor.user.is_root_admin:
        raise APIError(403, "FORBIDDEN")
    user = User(
        email=str(data.email),
        display_name=data.display_name,
        password_hash=password_hasher.hash(data.password),
    )
    db.add(user)
    try:
        db.flush()
        member = UserMembership(
            user_id=user.id, organization_id=manager.organization.id, role=data.role
        )
        db.add(member)
        db.flush()
        audit(
            db,
            manager.actor,
            "member.create",
            manager.organization.id,
            member.id,
            reason=data.reason,
            role=data.role,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "ACCOUNT_CONFLICT") from error
    return member_view(user, member)


@router.patch("/members/{member_id}")
def change_member(member_id: UUID, data: MemberChange, db: DB, manager: Manager):
    # Scope the lookup before revealing whether the ID exists.
    member = db.scalar(
        select(UserMembership).where(
            UserMembership.id == member_id,
            UserMembership.organization_id == manager.organization.id,
            UserMembership.ended_at.is_(None),
        )
    )
    if not member:
        raise APIError(404, "NOT_FOUND")
    user = db.scalar(select(User).where(User.id == member.user_id).with_for_update())
    db.refresh(member)
    if user.is_root_admin or user.id == manager.actor.user.id:
        raise APIError(403, "FORBIDDEN")
    if (
        member.role == "organization_manager" or data.role == "organization_manager"
    ) and not manager.actor.user.is_root_admin:
        raise APIError(403, "FORBIDDEN")
    member.role = data.role
    member.is_active = data.is_active
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    audit(
        db,
        manager.actor,
        "member.change",
        manager.organization.id,
        member.id,
        reason=data.reason,
        role=data.role,
        is_active=data.is_active,
    )
    commit(db)
    return member_view(user, member)
