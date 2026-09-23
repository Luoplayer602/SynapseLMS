import secrets
from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DB, Actor, Manager, audit, auth_guard, lock_actor
from app.api.schemas import (
    AcceptNewInvitation,
    InvitationReason,
    MembershipInviteCreate,
    MembershipInviteResend,
    TokenInput,
)
from app.core.account_actions import invalidate_tokens
from app.core.errors import APIError
from app.core.invitation_mail import send_invitation
from app.core.security import digest, now, password_hasher, utc
from app.db.expressions import EmailKey
from app.models import (
    AuditLog,
    MembershipInvitation,
    Organization,
    SupportSession,
    User,
    UserMembership,
)

router = APIRouter(dependencies=[Depends(auth_guard)])
BASE = "/organization/membership-invitations"
PUBLIC = "/membership-invitations"


def invite_status(item):
    if item.status == "pending" and utc(item.expires_at) <= now():
        return "expired"
    return item.status


def view(item, root):
    return {
        "id": item.id,
        "email": item.email,
        "display_name": item.display_name,
        "role": item.role,
        "status": invite_status(item),
        "expires_at": utc(item.expires_at),
        "created_at": utc(item.created_at),
        "delivery_status": item.delivery_status,
        "sent_at": utc(item.sent_at) if item.sent_at else None,
        "accepted_at": utc(item.accepted_at) if item.accepted_at else None,
        "can_manage": root or item.role != "organization_manager",
    }


def manager_lock(db, manager, request):
    org = db.scalar(
        select(Organization)
        .where(Organization.id == manager.organization.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not org or not org.is_active:
        raise APIError(403, "TENANT_UNAVAILABLE")
    user = lock_actor(db, manager.actor)
    if user.is_root_admin:
        support_id = UUID(request.headers["x-support-session"])
        support = db.scalar(
            select(SupportSession)
            .where(
                SupportSession.id == support_id,
                SupportSession.user_id == user.id,
                SupportSession.auth_session_id == manager.actor.session.id,
                SupportSession.organization_id == org.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not support or support.revoked_at or utc(support.expires_at) <= now():
            raise APIError(403, "SUPPORT_SESSION_REQUIRED")
    else:
        member = db.scalar(
            select(UserMembership.id).where(
                UserMembership.user_id == user.id,
                UserMembership.organization_id == org.id,
                UserMembership.is_active.is_(True),
                UserMembership.ended_at.is_(None),
                UserMembership.role == "organization_manager",
            )
        )
        if not member:
            raise APIError(403, "FORBIDDEN")


def role_guard(role, manager):
    if role == "organization_manager" and not manager.actor.user.is_root_admin:
        raise APIError(403, "FORBIDDEN")


def commit(db, code="INVITATION_CONFLICT"):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, code) from error


def retire_expired(db, org_id, email):
    db.execute(
        update(MembershipInvitation)
        .where(
            MembershipInvitation.organization_id == org_id,
            MembershipInvitation.email == email,
            MembershipInvitation.status == "pending",
            MembershipInvitation.expires_at <= now(),
        )
        .values(status="expired")
        .execution_options(synchronize_session="fetch")
    )


@router.get(BASE)
def list_invitations(
    db: DB,
    manager: Manager,
    response: Response,
    status: Literal["pending", "accepted", "revoked", "expired"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    response.headers["Cache-Control"] = "no-store"
    conditions = [MembershipInvitation.organization_id == manager.organization.id]
    if status == "expired":
        conditions.append(
            or_(
                MembershipInvitation.status == "expired",
                (MembershipInvitation.status == "pending")
                & (MembershipInvitation.expires_at <= now()),
            )
        )
    elif status:
        conditions.append(MembershipInvitation.status == status)
        if status == "pending":
            conditions.append(MembershipInvitation.expires_at > now())
    total = db.scalar(select(func.count()).select_from(MembershipInvitation).where(*conditions))
    items = db.scalars(
        select(MembershipInvitation)
        .where(*conditions)
        .order_by(MembershipInvitation.created_at.desc(), MembershipInvitation.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [view(item, manager.actor.user.is_root_admin) for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post(BASE, status_code=201)
def create_invitation(
    data: MembershipInviteCreate,
    db: DB,
    manager: Manager,
    request: Request,
    response: Response,
    tasks: BackgroundTasks,
):
    response.headers["Cache-Control"] = "no-store"
    manager_lock(db, manager, request)
    role_guard(data.role, manager)
    email = str(data.email).lower()
    member = db.scalar(
        select(UserMembership.id)
        .join(User, User.id == UserMembership.user_id)
        .where(
            EmailKey(User.email) == email,
            UserMembership.organization_id == manager.organization.id,
            UserMembership.ended_at.is_(None),
        )
    )
    if member:
        raise APIError(409, "INVITATION_MEMBER_EXISTS")
    retire_expired(db, manager.organization.id, email)
    raw = secrets.token_urlsafe(48)
    item = MembershipInvitation(
        organization_id=manager.organization.id,
        created_by=manager.actor.user.id,
        email=email,
        display_name=data.display_name,
        role=data.role,
        reason=data.reason,
        token_hash=digest(raw),
        expires_at=now() + timedelta(days=data.expires_days),
        last_requested_at=now(),
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "INVITATION_CONFLICT") from error
    audit(
        db,
        manager.actor,
        "membership_invitation.create",
        manager.organization.id,
        item.id,
        role=item.role,
        reason=data.reason,
    )
    commit(db)
    tasks.add_task(send_invitation, db.get_bind(), item.id, raw)
    return view(item, manager.actor.user.is_root_admin)


def managed_invitation(db, manager, request, invitation_id):
    manager_lock(db, manager, request)
    item = db.scalar(
        select(MembershipInvitation)
        .where(
            MembershipInvitation.id == invitation_id,
            MembershipInvitation.organization_id == manager.organization.id,
        )
        .with_for_update()
    )
    if not item:
        raise APIError(404, "NOT_FOUND")
    role_guard(item.role, manager)
    return item


@router.post(BASE + "/{invitation_id}/resend")
def resend(
    invitation_id: UUID,
    data: MembershipInviteResend,
    db: DB,
    manager: Manager,
    request: Request,
    response: Response,
    tasks: BackgroundTasks,
):
    response.headers["Cache-Control"] = "no-store"
    item = managed_invitation(db, manager, request, invitation_id)
    if item.status not in {"pending", "expired"}:
        raise APIError(409, "INVITATION_NOT_PENDING")
    if utc(item.last_requested_at) > now() - timedelta(seconds=60):
        raise APIError(429, "INVITATION_COOLDOWN")
    retire_expired(db, item.organization_id, item.email)
    raw = secrets.token_urlsafe(48)
    item.token_hash = digest(raw)
    item.status, item.delivery_status, item.sent_at = "pending", "queued", None
    item.expires_at, item.last_requested_at = now() + timedelta(days=data.expires_days), now()
    audit(
        db,
        manager.actor,
        "membership_invitation.resend",
        item.organization_id,
        item.id,
        reason=data.reason,
    )
    commit(db)
    tasks.add_task(send_invitation, db.get_bind(), item.id, raw)
    return view(item, manager.actor.user.is_root_admin)


@router.post(BASE + "/{invitation_id}/revoke", status_code=204)
def revoke(
    invitation_id: UUID,
    data: InvitationReason,
    db: DB,
    manager: Manager,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    item = managed_invitation(db, manager, request, invitation_id)
    if item.status == "accepted":
        raise APIError(409, "INVITATION_NOT_PENDING")
    if item.status != "revoked":
        item.status = "revoked"
        audit(
            db,
            manager.actor,
            "membership_invitation.revoke",
            item.organization_id,
            item.id,
            reason=data.reason,
        )
        commit(db)


def valid_invitation(db, raw, lock=False):
    hashed = digest(raw)
    item = db.scalar(select(MembershipInvitation).where(MembershipInvitation.token_hash == hashed))
    if not item:
        raise APIError(400, "INVALID_INVITATION")
    query = select(Organization).where(Organization.id == item.organization_id)
    org = db.scalar(query.with_for_update() if lock else query)
    if lock:
        item = db.scalar(
            select(MembershipInvitation)
            .where(MembershipInvitation.id == item.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if (
        not item
        or item.token_hash != hashed
        or invite_status(item) != "pending"
        or item.delivery_status == "failed"
        or not org
        or not org.is_active
    ):
        raise APIError(400, "INVALID_INVITATION")
    return item, org


@router.post(PUBLIC + "/preview")
def preview(data: TokenInput, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    item, org = valid_invitation(db, data.token)
    existing = db.scalar(select(User.id).where(EmailKey(User.email) == item.email))
    return {
        "email": item.email,
        "display_name": item.display_name,
        "role": item.role,
        "organization_name": org.name,
        "expires_at": utc(item.expires_at),
        "existing_account": existing is not None,
    }


def finish_acceptance(db, item, user):
    if not user.is_active or user.is_root_admin:
        raise APIError(403, "FORBIDDEN")
    # Suspended, non-ended memberships must not be bypassed through an invitation.
    member = db.scalar(
        select(UserMembership)
        .where(
            UserMembership.user_id == user.id,
            UserMembership.ended_at.is_(None),
        )
        .order_by(UserMembership.is_active.desc())
    )
    if member:
        code = (
            "INVITATION_MEMBER_EXISTS"
            if member.organization_id == item.organization_id
            else "INVITATION_TRANSFER_REQUIRED"
        )
        raise APIError(409, code)
    result = db.execute(
        update(MembershipInvitation)
        .where(
            MembershipInvitation.id == item.id,
            MembershipInvitation.status == "pending",
            MembershipInvitation.token_hash == item.token_hash,
            MembershipInvitation.expires_at > now(),
        )
        .values(status="accepted", accepted_at=now(), accepted_by=user.id)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise APIError(400, "INVALID_INVITATION")
    db.add(UserMembership(user_id=user.id, organization_id=item.organization_id, role=item.role))
    if user.email_verified_at is None:
        user.email_verified_at = now()
    invalidate_tokens(db, user.id, "verify_email")
    db.add(
        AuditLog(
            actor_id=user.id,
            organization_id=item.organization_id,
            action="membership_invitation.accept",
            target_id=item.id,
            details={"role": item.role},
        )
    )
    commit(db)
    return {"status": "accepted"}


@router.post(PUBLIC + "/accept-new", status_code=201)
def accept_new(data: AcceptNewInvitation, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    item, _org = valid_invitation(db, data.token, lock=True)
    if db.scalar(select(User.id).where(EmailKey(User.email) == item.email)):
        raise APIError(409, "INVITATION_LOGIN_REQUIRED")
    user = User(
        email=item.email,
        display_name=data.display_name,
        password_hash=password_hasher.hash(data.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "INVITATION_LOGIN_REQUIRED") from error
    return finish_acceptance(db, item, user)


@router.post(PUBLIC + "/accept")
def accept_existing(data: TokenInput, actor: Actor, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    item, _org = valid_invitation(db, data.token, lock=True)
    user = lock_actor(db, actor)
    if user.email.strip().lower() != item.email:
        raise APIError(403, "INVITATION_EMAIL_MISMATCH")
    return finish_acceptance(db, item, user)
