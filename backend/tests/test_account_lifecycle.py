import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import mail
from app.core.config import Settings
from app.core.mail import deliver as smtp_deliver
from app.core.security import digest, now
from app.models import AccountToken, AuditLog, AuthSession, User
from tests.test_auth_api import HEADERS, PASSWORD, login, register, seed_user


def raw_token(mail_outbox, index=-1):
    return re.search(r"#token=([\w-]+)", mail_outbox[index].get_content()).group(1)


def age_tokens(engine):
    with Session(engine) as db:
        for token in db.scalars(select(AccountToken)):
            token.created_at = now() - timedelta(minutes=2)
        db.commit()


def test_registration_email_verifies_once_without_login(api, mail_outbox):
    client, engine, (org, _), _ = api
    response = register(client, org)
    assert response.status_code == 201
    assert len(mail_outbox) == 1
    raw = raw_token(mail_outbox)
    assert raw not in response.text
    assert "/account/verify-email#token=" in mail_outbox[0].get_content()
    with Session(engine) as db:
        token = db.scalar(select(AccountToken))
        assert token.token_hash == digest(raw) and token.email == "student@example.com"
        assert db.scalar(select(User)).email_verified_at is None
    response = client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    assert client.post("/api/v1/auth/verify-email", json={"token": raw}).status_code == 400
    headers = login(client)
    assert client.get("/api/v1/auth/me", headers=headers).json()["email_verified_at"]
    client.post("/api/v1/auth/request-verification", json={"email": "student@example.com"})
    assert len(mail_outbox) == 1
    with Session(engine) as db:
        assert "auth.email_verified" in db.scalars(select(AuditLog.action)).all()
        assert raw not in str(db.scalars(select(AuditLog.details)).all())


@pytest.mark.parametrize("purpose", ["verify-email", "reset-password"])
@pytest.mark.parametrize(
    "invalid", ["expired", "revoked", "inactive", "email_changed", "wrong_purpose"]
)
def test_invalid_links_never_change_account(api, mail_outbox, purpose, invalid):
    client, engine, (org, _), _ = api
    register(client, org)
    if purpose == "reset-password":
        client.post("/api/v1/auth/forgot-password", json={"email": "student@example.com"})
    raw = raw_token(mail_outbox)
    with Session(engine) as db:
        token = db.scalar(select(AccountToken).where(AccountToken.token_hash == digest(raw)))
        user = db.scalar(select(User))
        old_hash = user.password_hash
        if invalid == "expired":
            token.created_at = now() - timedelta(hours=2)
            token.expires_at = now() - timedelta(hours=1)
        elif invalid == "revoked":
            token.revoked_at = now()
        elif invalid == "inactive":
            user.is_active = False
        elif invalid == "email_changed":
            user.email = "changed@example.com"
        else:
            token.purpose = "reset_password" if purpose == "verify-email" else "verify_email"
        db.commit()
    body = {
        "token": raw,
        **({"password": "changed-password-2026!"} if purpose == "reset-password" else {}),
    }
    response = client.post("/api/v1/auth/" + purpose, json=body)
    assert (
        response.status_code == 400 and response.json()["error"]["code"] == "INVALID_ACCOUNT_LINK"
    )
    with Session(engine) as db:
        user = db.scalar(select(User))
        assert user.password_hash == old_hash and user.email_verified_at is None


def test_reset_revokes_all_sessions_and_links(api, mail_outbox):
    client, engine, (org, _), _ = api
    register(client, org)
    verify_raw = raw_token(mail_outbox)
    first = login(client)
    old_cookie = client.cookies.get("synapse_refresh")
    second = login(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "STUDENT@example.com"})
    raw = raw_token(mail_outbox)
    body = {"token": raw, "password": "recovered-password-2026!"}
    assert client.post("/api/v1/auth/reset-password", json=body).status_code == 204
    assert client.cookies.get("synapse_refresh") is None
    assert client.get("/api/v1/auth/me", headers=first).status_code == 401
    assert client.get("/api/v1/auth/me", headers=second).status_code == 401
    client.cookies.set("synapse_refresh", old_cookie)
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.post("/api/v1/auth/reset-password", json=body).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": verify_raw}).status_code == 400
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "student@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    login(client, password=body["password"])
    with Session(engine) as db:
        assert db.scalar(select(User)).password_changed_at is not None
        assert "auth.password_reset" in db.scalars(select(AuditLog.action)).all()


def test_password_change_invalidates_outstanding_recovery(api, mail_outbox):
    client, _, (org, _), _ = api
    register(client, org)
    headers = login(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "student@example.com"})
    raw = raw_token(mail_outbox)
    assert (
        client.post(
            "/api/v1/auth/password",
            headers=headers,
            json={"current_password": PASSWORD, "password": "new-password-2026!"},
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": raw, "password": PASSWORD}
        ).status_code
        == 400
    )


@pytest.mark.parametrize("endpoint", ["forgot-password", "request-verification"])
def test_generic_response_cooldown_resend_and_delivery_failure(
    api, mail_outbox, monkeypatch, caplog, endpoint
):
    client, engine, (org, _), _ = api
    register(client, org)
    age_tokens(engine)
    path = "/api/v1/auth/" + endpoint
    body = {"email": "student@example.com"}
    first = client.post(path, json=body)
    count = len(mail_outbox)
    old_raw = raw_token(mail_outbox)
    assert first.status_code == 202 and "token" not in first.text
    assert client.post(path, json=body).json() == first.json()
    assert len(mail_outbox) == count
    assert client.post(path, json={"email": "missing@example.com"}).json() == first.json()
    age_tokens(engine)
    assert client.post(path, json=body).json() == first.json()
    assert len(mail_outbox) == count + 1
    with Session(engine) as db:
        assert db.scalar(
            select(AccountToken).where(AccountToken.token_hash == digest(old_raw))
        ).revoked_at
    age_tokens(engine)

    def fail(_message):
        raise OSError("secret-smtp-password student@example.com")

    monkeypatch.setattr(mail, "deliver", fail)
    assert client.post(path, json=body).json() == first.json()
    assert "secret-smtp-password" not in caplog.text
    assert "student@example.com" not in caplog.text
    with Session(engine) as db:
        assert "auth.email_delivery_failed" in db.scalars(select(AuditLog.action)).all()
        latest = db.scalar(select(AccountToken).order_by(AccountToken.created_at.desc()))
        assert latest.revoked_at is not None


def test_inactive_account_receives_no_recovery_mail(api, mail_outbox):
    client, engine, (org, _), _ = api
    register(client, org)
    with Session(engine) as db:
        db.scalar(select(User)).is_active = False
        db.commit()
    assert (
        client.post(
            "/api/v1/auth/forgot-password", json={"email": "student@example.com"}
        ).status_code
        == 202
    )
    assert len(mail_outbox) == 1


def test_session_ownership_individual_others_and_all_revocation(api):
    client, engine, (org, other_org), _ = api
    register(client, org)
    first = login(client)
    first_id = client.get("/api/v1/auth/sessions", headers=first).json()[0]["id"]
    second = login(client)
    second_cookie = client.cookies.get("synapse_refresh")
    seed_user(engine, other_org, email="another@example.com", root=True)
    outsider = login(client, email="another@example.com")
    assert client.delete("/api/v1/auth/sessions/" + first_id, headers=outsider).status_code == 404
    rows = client.get("/api/v1/auth/sessions", headers=first).json()
    assert len(rows) == 2 and sum(row["is_current"] for row in rows) == 1
    assert all("token" not in str(row) for row in rows)
    second_id = next(row["id"] for row in rows if not row["is_current"])
    assert client.delete("/api/v1/auth/sessions/" + second_id, headers=first).status_code == 204
    assert client.get("/api/v1/auth/me", headers=second).status_code == 401
    client.cookies.clear()
    client.cookies.set("synapse_refresh", second_cookie)
    assert client.post("/api/v1/auth/refresh").status_code == 401
    third = login(client)
    assert (
        client.post(
            "/api/v1/auth/sessions/revoke", headers=first, json={"scope": "others"}
        ).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me", headers=third).status_code == 401
    assert client.get("/api/v1/auth/me", headers=first).status_code == 200
    assert client.get("/api/v1/auth/me", headers=outsider).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/sessions/revoke", headers=first, json={"scope": "all"}
        ).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me", headers=first).status_code == 401
    with Session(engine) as db:
        actions = db.scalars(select(AuditLog.action)).all()
        assert "auth.session_revoked" in actions and "auth.sessions_revoked" in actions


def test_revoke_current_session_clears_cookie_and_ignores_expired_sessions(api):
    client, engine, (org, _), _ = api
    register(client, org)
    login(client)
    with Session(engine) as db:
        old = db.scalar(select(AuthSession))
        old.created_at = now() - timedelta(days=2)
        old.expires_at = now() - timedelta(days=1)
        db.commit()
    headers = login(client)
    response = client.get("/api/v1/auth/sessions", headers=headers)
    assert response.headers["cache-control"] == "no-store"
    rows = response.json()
    assert len(rows) == 1 and rows[0]["is_current"]
    assert (
        client.delete("/api/v1/auth/sessions/" + rows[0]["id"], headers=headers).status_code == 204
    )
    assert client.cookies.get("synapse_refresh") is None
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_origin_rate_limit_and_no_secret_validation_echo(api):
    client, _, _, _ = api
    path = "/api/v1/auth/forgot-password"
    body = {"email": "missing@example.com"}
    assert (
        client.post(path, headers={"Origin": "https://evil.example"}, json=body).status_code == 403
    )
    assert [client.post(path, json=body).status_code for _ in range(6)] == [202] * 5 + [429]
    response = client.post(
        "/api/v1/auth/reset-password", json={"token": "short-secret", "password": "secret"}
    )
    assert response.status_code == 422
    assert "short-secret" not in response.text and '"secret"' not in response.text
    assert client.get("/api/v1/auth/sessions").status_code == 401


@pytest.mark.parametrize("purpose", ["verify-email", "reset-password"])
def test_concurrent_token_consumption_postgresql(api, mail_outbox, purpose):
    client, engine, (org, _), app = api
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency")
    register(client, org)
    if purpose == "reset-password":
        client.post("/api/v1/auth/forgot-password", json={"email": "student@example.com"})
    body = {
        "token": raw_token(mail_outbox),
        **({"password": PASSWORD} if purpose == "reset-password" else {}),
    }

    def once(_):
        with TestClient(app, headers=HEADERS) as parallel:
            return parallel.post("/api/v1/auth/" + purpose, json=body).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(once, range(2))) == [204, 400]


def test_concurrent_resend_postgresql(api, mail_outbox):
    client, engine, (org, _), app = api
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency")
    register(client, org)

    def once(_):
        with TestClient(app, headers=HEADERS) as parallel:
            return parallel.post(
                "/api/v1/auth/forgot-password", json={"email": "student@example.com"}
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(once, range(2))) == [202, 202]
    assert len(mail_outbox) == 2  # one verification, one reset


@pytest.mark.parametrize("security", ["none", "starttls", "ssl"])
def test_smtp_transport(monkeypatch, security):
    settings = Settings(
        _env_file=None,
        mail_backend="smtp",
        smtp_security=security,
        smtp_username="smtp-user",
        smtp_password="smtp-secret",
    )
    monkeypatch.setattr(mail, "get_settings", lambda: settings)
    smtp = MagicMock()
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL" if security == "ssl" else "SMTP", smtp)
    message = mail.action_message("student@example.com", "verify_email", "x" * 64, 30)
    smtp_deliver(message)
    connection = smtp.return_value.__enter__.return_value
    assert connection.starttls.call_count == (1 if security == "starttls" else 0)
    connection.login.assert_called_once_with("smtp-user", "smtp-secret")
    connection.send_message.assert_called_once_with(message)


def test_production_mail_config_requires_tls():
    with pytest.raises(ValidationError, match="SMTP with TLS"):
        Settings(
            _env_file=None,
            env="production",
            debug=False,
            jwt_secret="abcdef0123456789XYZ" * 4,
            cookie_secure=True,
            cors_origins=["https://lms.example.com"],
            frontend_url="https://lms.example.com",
            mail_backend="smtp",
            smtp_security="none",
        )
