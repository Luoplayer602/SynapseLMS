"""SMTP adapter. Development uses Mailpit; no tokens or message bodies enter logs."""

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings


def deliver(message: EmailMessage):
    settings = get_settings()
    if settings.mail_backend != "smtp":
        raise RuntimeError("Mail delivery is disabled")
    options = {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "timeout": settings.smtp_timeout,
    }
    if settings.smtp_security == "ssl":
        connection = smtplib.SMTP_SSL(**options, context=ssl.create_default_context())
    else:
        connection = smtplib.SMTP(**options)
    with connection as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


def action_message(email: str, purpose: str, raw: str, minutes: int) -> EmailMessage:
    settings = get_settings()
    action = "verify-email" if purpose == "verify_email" else "reset-password"
    # Fragments are not sent to HTTP servers or included in Referer headers.
    link = f"{str(settings.frontend_url).rstrip('/')}/account/{action}#token={raw}"
    label = (
        "Xác minh email / Verify email"
        if purpose == "verify_email"
        else "Đặt lại mật khẩu / Reset password"
    )
    message = EmailMessage()
    message["Subject"] = f"SynapseLMS — {label}"
    message["From"] = str(settings.mail_from)
    message["To"] = email
    message.set_content(
        f"{label}\n\n{link}\n\n"
        f"Liên kết dùng một lần, hết hạn sau {minutes} phút. "
        "Nếu bạn không yêu cầu, hãy bỏ qua email này.\n"
        f"This single-use link expires in {minutes} minutes. "
        "If you did not request it, ignore this email.\n"
    )
    return message
