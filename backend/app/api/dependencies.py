import time
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import decode_access, digest, now, utc
from app.db.sync import get_session
from app.models import (
    AuditLog,
    AuthRateBucket,
    AuthSession,
    Organization,
    SupportSession,
    User,
    UserMembership,
)

DB = Annotated[Session, Depends(get_session)]
bearer = HTTPBearer(auto_error=False)


def browser_guard(request: Request):
    origins = {str(origin).rstrip("/") for origin in get_settings().cors_origins}
    origin = request.headers.get("origin")
    if request.headers.get("x-synapse-client") != "web" or (origin and origin not in origins):
        raise APIError(403, "INVALID_ORIGIN")


def auth_guard(request: Request, db: DB):
    browser_guard(request)
    limits = {
        "login": 10,
        "register": 5,
        "refresh": 30,
        "logout": 30,
        "forgot-password": 5,
        "request-verification": 5,
        "membership-invitations": 5,
        "resend": 5,
        "accept-new": 5,
        "preview": 30,
    }
    action = request.url.path.rsplit("/", 1)[-1]
    stamp = int(time.time())
    # Do not trust X-Forwarded-For supplied by clients.
    host = request.client.host if request.client else "unknown"
    key = digest(f"{request.method}:{action}:{host}:{stamp // 60}")
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    statement = insert(AuthRateBucket).values(key=key, count=1, expires_at=stamp + 120)
    count = db.scalar(
        statement.on_conflict_do_update(
            index_elements=[AuthRateBucket.key], set_={"count": AuthRateBucket.count + 1}
        ).returning(AuthRateBucket.count)
    )
    db.execute(delete(AuthRateBucket).where(AuthRateBucket.expires_at < stamp))
    db.commit()
    if count > (60 if request.method == "GET" else limits.get(action, 10)):
        raise APIError(429, "RATE_LIMITED")


@dataclass
class Identity:
    user: User
    session: AuthSession


def current_identity(
    db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
):
    if credentials is None:
        raise APIError(401, "INVALID_SESSION")
    claims = decode_access(credentials.credentials)
    try:
        user_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
    except (ValueError, TypeError, AttributeError) as error:
        raise APIError(401, "INVALID_SESSION") from error
    user = db.get(User, user_id)
    session = db.get(AuthSession, session_id)
    if (
        not user
        or not user.is_active
        or not session
        or session.user_id != user.id
        or session.revoked_at is not None
        or utc(session.expires_at) <= now()
    ):
        raise APIError(401, "INVALID_SESSION")
    return Identity(user, session)


Actor = Annotated[Identity, Depends(current_identity)]


def lock_actor(db, actor):
    """Recheck identity after acquiring the same user lock used by reset/refresh/login."""
    user = db.scalar(
        select(User)
        .where(User.id == actor.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    db.refresh(actor.session)
    if (
        not user.is_active
        or actor.session.revoked_at is not None
        or utc(actor.session.expires_at) <= now()
    ):
        raise APIError(401, "INVALID_SESSION")
    return user


def root_identity(actor: Actor):
    if not actor.user.is_root_admin:
        raise APIError(403, "FORBIDDEN")
    return actor


Root = Annotated[Identity, Depends(root_identity)]


def audit(db, actor, action, organization_id=None, target_id=None, **details):
    db.add(
        AuditLog(
            actor_id=actor.user.id,
            action=action,
            organization_id=organization_id,
            target_id=target_id,
            details=details,
        )
    )


@dataclass
class TenantAccess:
    actor: Identity
    organization: Organization
    role: str


def tenant_access(
    request: Request,
    db: DB,
    actor: Actor,
    x_support_session: Annotated[UUID | None, Header()] = None,
):
    if actor.user.is_root_admin:
        support = db.get(SupportSession, x_support_session) if x_support_session else None
        if (
            not support
            or support.user_id != actor.user.id
            or support.auth_session_id != actor.session.id
            or support.revoked_at is not None
            or utc(support.expires_at) <= now()
        ):
            raise APIError(403, "SUPPORT_SESSION_REQUIRED")
        org_id, role = support.organization_id, "organization_manager"
        # Audit INSERT takes FK key-share locks (actor, then organization).
        # Take the tenant lock first, matching org -> actor -> support in handlers;
        # otherwise parallel root reads can deadlock with those handlers.
        db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
        audit(
            db,
            actor,
            "support.access",
            org_id,
            support.id,
            method=request.method,
            path=request.url.path,
        )
        db.commit()
    else:
        membership = db.scalar(
            select(UserMembership).where(
                UserMembership.user_id == actor.user.id,
                UserMembership.is_active.is_(True),
                UserMembership.ended_at.is_(None),
            )
        )
        if not membership:
            raise APIError(403, "TENANT_UNAVAILABLE")
        org_id, role = membership.organization_id, membership.role
    org = db.get(Organization, org_id)
    if not org or not org.is_active:
        raise APIError(403, "TENANT_UNAVAILABLE")
    return TenantAccess(actor, org, role)


Tenant = Annotated[TenantAccess, Depends(tenant_access)]


def manager_access(tenant: Tenant):
    if tenant.role != "organization_manager":
        raise APIError(403, "FORBIDDEN")
    return tenant


Manager = Annotated[TenantAccess, Depends(manager_access)]
