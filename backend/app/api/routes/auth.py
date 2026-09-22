import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DB, Actor, Identity, audit, auth_guard
from app.api.schemas import Login, PasswordChange, Register
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import (
    DUMMY_HASH,
    access_token,
    digest,
    now,
    password_hasher,
    utc,
    verify_password,
)
from app.db.expressions import EmailKey
from app.models import (
    AuthSession,
    Organization,
    OrganizationInvite,
    RefreshToken,
    User,
    UserMembership,
)

router = APIRouter()
COOKIE = "synapse_refresh"


def cookie_path():
    return get_settings().api_v1_prefix + "/auth"


def token_response(response, user, login, raw_token):
    settings = get_settings()
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        COOKIE,
        raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=cookie_path(),
        max_age=max(0, int((utc(login.expires_at) - now()).total_seconds())),
    )
    return {
        "access_token": access_token(user.id, login.id),
        "token_type": "bearer",
        "expires_in": settings.access_minutes * 60,
    }


def new_refresh(db, login):
    raw = secrets.token_urlsafe(48)
    db.add(RefreshToken(session_id=login.id, token_hash=digest(raw), expires_at=login.expires_at))
    return raw


@router.get("/organizations/public")
def public_organizations(db: DB, limit: Annotated[int, Query(ge=1, le=100)] = 100):
    rows = db.scalars(
        select(Organization)
        .where(
            Organization.is_active.is_(True),
            Organization.is_public.is_(True),
            Organization.registration_enabled.is_(True),
        )
        .order_by(Organization.name)
        .limit(limit)
    )
    return [{"id": row.id, "name": row.name, "slug": row.slug} for row in rows]


@router.post("/auth/register", status_code=201, dependencies=[Depends(auth_guard)])
def register(data: Register, db: DB):
    invite = None
    if data.invite_code:
        invite = db.scalar(
            select(OrganizationInvite)
            .where(OrganizationInvite.token_hash == digest(data.invite_code))
            .with_for_update()
        )
        if (
            not invite
            or invite.revoked_at is not None
            or utc(invite.expires_at) <= now()
            or invite.uses >= invite.max_uses
        ):
            raise APIError(400, "REGISTRATION_UNAVAILABLE")
    org = db.scalar(
        select(Organization)
        .where(Organization.id == (invite.organization_id if invite else data.organization_id))
        .with_for_update()
    )
    if (
        not org
        or not org.is_active
        or not org.registration_enabled
        or (not invite and not org.is_public)
    ):
        raise APIError(400, "REGISTRATION_UNAVAILABLE")
    user = User(
        email=str(data.email),
        display_name=data.display_name,
        password_hash=password_hasher.hash(data.password),
    )
    try:
        db.add(user)
        db.flush()
        db.add(UserMembership(user_id=user.id, organization_id=org.id, role="student"))
        if invite:
            invite.uses += 1
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "ACCOUNT_CONFLICT") from error
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@router.post("/auth/login", dependencies=[Depends(auth_guard)])
def login(data: Login, response: Response, db: DB):
    user = db.scalar(
        select(User).where(EmailKey(User.email) == str(data.email).lower()).with_for_update()
    )
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.is_active:
        raise APIError(401, "INVALID_CREDENTIALS")
    login = AuthSession(
        user_id=user.id, expires_at=now() + timedelta(days=get_settings().session_days)
    )
    db.add(login)
    db.flush()
    raw = new_refresh(db, login)
    audit(db, Identity(user, login), "auth.login", target_id=login.id)
    db.commit()
    return token_response(response, user, login, raw)


@router.get("/auth/me")
def me(db: DB, actor: Actor, response: Response):
    response.headers["Cache-Control"] = "no-store"
    member = db.scalar(
        select(UserMembership).where(
            UserMembership.user_id == actor.user.id,
            UserMembership.is_active.is_(True),
            UserMembership.ended_at.is_(None),
        )
    )
    org = db.get(Organization, member.organization_id) if member else None
    return {
        "id": actor.user.id,
        "email": actor.user.email,
        "display_name": actor.user.display_name,
        "is_root_admin": actor.user.is_root_admin,
        "membership": {
            "id": member.id,
            "organization_id": org.id,
            "organization_name": org.name,
            "role": member.role,
            "tenant_available": org.is_active,
        }
        if member and org and not actor.user.is_root_admin
        else None,
    }


@router.post("/auth/refresh", dependencies=[Depends(auth_guard)])
def refresh(request: Request, response: Response, db: DB):
    raw = request.cookies.get(COOKIE, "")
    token = (
        db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest(raw)))
        if raw
        else None
    )
    if not token:
        raise APIError(401, "INVALID_SESSION")
    owner_id = db.scalar(select(AuthSession.user_id).where(AuthSession.id == token.session_id))
    user = db.scalar(select(User).where(User.id == owner_id).with_for_update())
    login = db.scalar(
        select(AuthSession).where(AuthSession.id == token.session_id).with_for_update()
    )
    # Reload after the lock: a concurrent request may have consumed this token while waiting.
    db.refresh(token)
    if (
        not user
        or not user.is_active
        or not login
        or login.revoked_at is not None
        or utc(login.expires_at) <= now()
        or utc(token.expires_at) <= now()
    ):
        raise APIError(401, "INVALID_SESSION")
    if token.consumed_at is not None:
        login.revoked_at = now()
        audit(db, Identity(user, login), "auth.refresh_replay", target_id=login.id)
        db.commit()  # Revocation must survive the error response.
        raise APIError(401, "INVALID_SESSION")
    token.consumed_at = now()
    replacement = new_refresh(db, login)
    db.commit()
    return token_response(response, user, login, replacement)


@router.post("/auth/logout", status_code=204, dependencies=[Depends(auth_guard)])
def logout(request: Request, response: Response, db: DB):
    raw = request.cookies.get(COOKIE, "")
    token = (
        db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest(raw)))
        if raw
        else None
    )
    if token:
        db.execute(
            update(AuthSession)
            .where(AuthSession.id == token.session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now())
        )
        db.commit()
    response.delete_cookie(
        COOKIE,
        path=cookie_path(),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"


@router.post("/auth/password", status_code=204, dependencies=[Depends(auth_guard)])
def change_password(data: PasswordChange, actor: Actor, db: DB, response: Response):
    user = db.scalar(select(User).where(User.id == actor.user.id).with_for_update())
    if not verify_password(data.current_password, user.password_hash):
        raise APIError(401, "INVALID_CREDENTIALS")
    user.password_hash = password_hasher.hash(data.password)
    user.password_changed_at = now()
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    audit(db, actor, "auth.password_change", target_id=user.id)
    db.commit()
    response.delete_cookie(
        COOKIE,
        path=cookie_path(),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )
