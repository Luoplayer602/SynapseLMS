"""Opt-in real SMTP check against local Mailpit, using a unique synthetic recipient.

Run from backend: uv run python -m tests.mailpit_smoke
No user accounts, real recipients, production mail or database are accessed.
"""

import json
import os
import secrets
from urllib.parse import urlencode
from urllib.request import urlopen
from uuid import uuid4

# Override delivery settings before importing the app; only use local Mailpit.
os.environ["SYNAPSE_ENV"] = "test"
os.environ["SYNAPSE_MAIL_BACKEND"] = "smtp"
os.environ["SYNAPSE_SMTP_HOST"] = "mailpit" if os.path.exists("/.dockerenv") else "127.0.0.1"
os.environ["SYNAPSE_SMTP_PORT"] = "1025"
os.environ["SYNAPSE_SMTP_SECURITY"] = "none"
os.environ["SYNAPSE_SMTP_USERNAME"] = ""
os.environ["SYNAPSE_SMTP_PASSWORD"] = ""

from app.core.mail import action_message, deliver  # noqa: E402


def main():
    recipient = f"synapse-smoke-{uuid4().hex}@example.com"
    secret = secrets.token_urlsafe(48)
    deliver(action_message(recipient, "reset_password", secret, 30))
    base = f"http://{os.environ['SYNAPSE_SMTP_HOST']}:8025/api/v1"
    query = urlencode({"query": f"to:{recipient}"})
    with urlopen(f"{base}/search?{query}", timeout=10) as response:
        result = json.load(response)
    assert result["total"] == 1, "Synthetic SMTP message missing"
    identifier = result["messages"][0]["ID"]
    with urlopen(f"{base}/message/{identifier}", timeout=10) as response:
        stored = json.load(response)
    assert f"#token={secret}" in stored["Text"], "Email link damaged in SMTP transport"
    print("Mailpit SMTP delivery and recovery link integrity: passed (synthetic message only)")


if __name__ == "__main__":
    main()
