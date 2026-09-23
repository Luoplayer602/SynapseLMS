import logging
import secrets
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import mail
from app.core.config import get_settings
from app.core.security import digest, now, utc
from app.models import AuditLog, MembershipInvitation, Organization

logger = logging.getLogger(__name__)


def invitation_message(invitation, organization_name, raw):
    settings = get_settings()
    link = f"{str(settings.frontend_url).rstrip('/')}/account/accept-invitation#token={raw}"
    message = EmailMessage()
    message["Subject"] = "SynapseLMS — Lời mời tham gia / Membership invitation"
    message["From"] = str(settings.mail_from)
    message["To"] = invitation.email
    message.set_content(
        f"Xin chào / Hello {invitation.display_name},\n\n"
        f"Trung tâm / Center: {organization_name}\n"
        f"Vai trò / Role: {invitation.role}\n"
        f"Hết hạn / Expires (UTC): {utc(invitation.expires_at).isoformat()}\n\n"
        f"{link}\n\n"
        "Mở liên kết để xem và tiếp nhận lời mời. Nếu đã có tài khoản, đăng nhập đúng email. "
        "Không chia sẻ liên kết này.\n"
        "Open the link to review and accept. Existing accounts must sign in with this email. "
        "Do not share this link.\n"
    )
    return message


def send_invitation(engine, invitation_id, raw):
    """Only the current generation may update delivery state; no raw token is persisted."""
    expected_hash = digest(raw)
    try:
        with Session(engine) as db:
            item = db.get(MembershipInvitation, invitation_id)
            if (
                not item
                or item.token_hash != expected_hash
                or item.status != "pending"
                or utc(item.expires_at) <= now()
            ):
                return
            org = db.get(Organization, item.organization_id)
            if not org or not org.is_active:
                return
            org_id = org.id
            message = invitation_message(item, org.name, raw)
        delivered = True
        try:
            mail.deliver(message)
        except Exception:
            delivered = False
            logger.warning("Invitation email delivery failed; check SMTP configuration")
        with Session(engine) as db:
            # Same lock ordering as acceptance/resend. Never hold locks during SMTP I/O.
            db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            item = db.scalar(
                select(MembershipInvitation)
                .where(
                    MembershipInvitation.id == invitation_id,
                )
                .with_for_update()
            )
            if not item or item.token_hash != expected_hash or item.status != "pending":
                return
            item.delivery_status = "sent" if delivered else "failed"
            if delivered:
                item.sent_at = now()
            else:
                item.token_hash = digest(secrets.token_urlsafe(48))
            db.add(
                AuditLog(
                    actor_id=item.created_by,
                    organization_id=org_id,
                    action="membership_invitation.email_sent"
                    if delivered
                    else "membership_invitation.email_failed",
                    target_id=item.id,
                    details={},
                )
            )
            db.commit()
    except Exception:
        logger.error("Invitation email task failed; retry via resend")
