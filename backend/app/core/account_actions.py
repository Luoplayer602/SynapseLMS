import logging
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import mail
from app.core.config import get_settings
from app.core.security import digest, now, utc
from app.db.expressions import EmailKey
from app.models import AccountToken, AuditLog, User

logger = logging.getLogger(__name__)


def invalidate_tokens(db, user_id, purpose=None):
    statement = update(AccountToken).where(
        AccountToken.user_id == user_id,
        AccountToken.consumed_at.is_(None),
        AccountToken.revoked_at.is_(None),
    )
    if purpose:
        statement = statement.where(AccountToken.purpose == purpose)
    db.execute(statement.values(revoked_at=now()))


def issue_email_action(engine, email: str, purpose: str):
    """Runs after the generic HTTP response, with its own DB session.

    A user lock serializes issuance with password changes and token consumption.
    Account-wide cooldown also applies when requests originate from different IPs.
    """
    try:
        with Session(engine, expire_on_commit=False) as db:
            user = db.scalar(
                select(User).where(EmailKey(User.email) == email.lower()).with_for_update()
            )
            if not user or not user.is_active:
                return
            if purpose == "verify_email" and user.email_verified_at is not None:
                return
            recent = db.scalar(
                select(AccountToken.id)
                .where(
                    AccountToken.user_id == user.id,
                    AccountToken.purpose == purpose,
                    AccountToken.created_at > now() - timedelta(seconds=60),
                )
                .limit(1)
            )
            if recent:
                return
            settings = get_settings()
            minutes = (
                settings.verification_minutes
                if purpose == "verify_email"
                else settings.reset_minutes
            )
            invalidate_tokens(db, user.id, purpose)
            raw = secrets.token_urlsafe(48)
            token = AccountToken(
                user_id=user.id,
                email=user.email,
                purpose=purpose,
                token_hash=digest(raw),
                expires_at=now() + timedelta(minutes=minutes),
            )
            db.add(token)
            db.commit()
            try:
                mail.deliver(mail.action_message(user.email, purpose, raw, minutes))
            except Exception:
                # SMTP failures must not leak account existence, tokens, credentials or email.
                db.execute(
                    update(AccountToken).where(AccountToken.id == token.id).values(revoked_at=now())
                )
                db.add(
                    AuditLog(
                        actor_id=user.id,
                        action="auth.email_delivery_failed",
                        target_id=token.id,
                        details={"purpose": purpose},
                    )
                )
                db.commit()
                logger.warning("Account email delivery failed; check SMTP configuration")
                return
            db.add(
                AuditLog(
                    actor_id=user.id,
                    action="auth.email_requested",
                    target_id=token.id,
                    details={"purpose": purpose},
                )
            )
            db.commit()
    except Exception:
        # Background failures cannot change the public response or expose account information.
        logger.error("Account email task failed; retry the request later")


def token_is_valid(token, user):
    return (
        user.is_active
        and token.email == user.email
        and token.consumed_at is None
        and token.revoked_at is None
        and utc(token.expires_at) > now()
    )
