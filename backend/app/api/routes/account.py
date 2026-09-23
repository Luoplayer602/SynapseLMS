from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy import select, update

from app.api.dependencies import DB, Actor, audit, auth_guard, lock_actor
from app.api.routes.auth import COOKIE, cookie_path
from app.api.schemas import EmailRequest, PasswordReset, RevokeSessions, TokenInput
from app.core.account_actions import invalidate_tokens, issue_email_action, token_is_valid
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import digest, now, password_hasher, utc
from app.models import AccountToken, AuditLog, AuthSession, User

router = APIRouter(prefix="/auth", dependencies=[Depends(auth_guard)])


def no_store(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


def clear_cookie(response):
    response.delete_cookie(
        COOKIE,
        path=cookie_path(),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )


@router.post("/request-verification", status_code=202)
def request_verification(data: EmailRequest, db: DB, tasks: BackgroundTasks, response: Response):
    no_store(response)
    tasks.add_task(issue_email_action, db.get_bind(), str(data.email), "verify_email")
    return {"status": "accepted"}


@router.post("/forgot-password", status_code=202)
def forgot_password(data: EmailRequest, db: DB, tasks: BackgroundTasks, response: Response):
    no_store(response)
    tasks.add_task(issue_email_action, db.get_bind(), str(data.email), "reset_password")
    return {"status": "accepted"}


def consume(db, raw, purpose):
    token = db.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == digest(raw),
            AccountToken.purpose == purpose,
        )
    )
    if not token:
        raise APIError(400, "INVALID_ACCOUNT_LINK")
    user = db.scalar(
        select(User)
        .where(User.id == token.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    db.refresh(token)
    if not user or not token_is_valid(token, user):
        raise APIError(400, "INVALID_ACCOUNT_LINK")
    # Conditional update also prevents double consumption on SQLite.
    used = db.execute(
        update(AccountToken)
        .where(
            AccountToken.id == token.id,
            AccountToken.consumed_at.is_(None),
            AccountToken.revoked_at.is_(None),
            AccountToken.expires_at > now(),
        )
        .values(consumed_at=now())
        .execution_options(synchronize_session="fetch")
    )
    if used.rowcount != 1:
        raise APIError(400, "INVALID_ACCOUNT_LINK")
    return user, token


@router.post("/verify-email", status_code=204)
def verify_email(data: TokenInput, db: DB, response: Response):
    no_store(response)
    user, token = consume(db, data.token, "verify_email")
    user.email_verified_at = now()
    invalidate_tokens(db, user.id, "verify_email")
    db.add(AuditLog(actor_id=user.id, action="auth.email_verified", target_id=token.id, details={}))
    db.commit()


@router.post("/reset-password", status_code=204)
def reset_password(data: PasswordReset, db: DB, response: Response):
    no_store(response)
    user, token = consume(db, data.token, "reset_password")
    user.password_hash = password_hasher.hash(data.password)
    user.password_changed_at = now()
    invalidate_tokens(db, user.id)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now())
    )
    db.add(AuditLog(actor_id=user.id, action="auth.password_reset", target_id=token.id, details={}))
    db.commit()
    clear_cookie(response)


@router.get("/sessions")
def sessions(actor: Actor, db: DB, response: Response):
    no_store(response)
    rows = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == actor.user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now(),
        )
        .order_by(AuthSession.created_at.desc(), AuthSession.id.desc())
    )
    return [
        {
            "id": row.id,
            "created_at": utc(row.created_at),
            "expires_at": utc(row.expires_at),
            "user_agent": row.user_agent,
            "is_current": row.id == actor.session.id,
        }
        for row in rows
    ]


@router.post("/sessions/revoke", status_code=204)
def revoke_sessions(data: RevokeSessions, actor: Actor, db: DB, response: Response):
    no_store(response)
    lock_actor(db, actor)
    statement = update(AuthSession).where(
        AuthSession.user_id == actor.user.id,
        AuthSession.revoked_at.is_(None),
    )
    if data.scope == "others":
        statement = statement.where(AuthSession.id != actor.session.id)
    db.execute(statement.values(revoked_at=now()))
    audit(db, actor, "auth.sessions_revoked", target_id=actor.user.id, scope=data.scope)
    db.commit()
    if data.scope == "all":
        clear_cookie(response)


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: UUID, actor: Actor, db: DB, response: Response):
    no_store(response)
    lock_actor(db, actor)
    session = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == actor.user.id,
        )
        .execution_options(populate_existing=True)
    )
    if not session:
        raise APIError(404, "NOT_FOUND")
    if session.revoked_at is None:
        session.revoked_at = now()
        audit(db, actor, "auth.session_revoked", target_id=session.id)
    db.commit()
    if session.id == actor.session.id:
        clear_cookie(response)
