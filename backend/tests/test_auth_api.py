from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import bootstrap_root, seed_centers
from app.core.config import Settings, get_settings
from app.core.security import digest, now, password_hasher
from app.models import (
    AuditLog,
    AuthSession,
    Organization,
    OrganizationInvite,
    RefreshToken,
    User,
    UserMembership,
)

PASSWORD = "test-password-2026!"
HEADERS = {"X-Synapse-Client": "web", "Origin": "http://localhost:5173"}


def register(client, org, email="student@example.com", **extra):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Student",
            "organization_id": org,
            **extra,
        },
    )


def login(client, email="student@example.com", password=PASSWORD):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {**HEADERS, "Authorization": "Bearer " + response.json()["access_token"]}


def seed_user(engine, org, role="organization_manager", email="manager@example.com", root=False):
    with Session(engine) as db:
        user = User(email=email, password_hash=password_hasher.hash(PASSWORD), is_root_admin=root)
        db.add(user)
        db.flush()
        membership_id = None
        if not root:
            member = UserMembership(user_id=user.id, organization_id=UUID(org), role=role)
            db.add(member)
            db.flush()
            membership_id = str(member.id)
        user_id = str(user.id)
        db.commit()
    return user_id, membership_id


def test_register_login_me_refresh_logout(api):
    client, engine, (org, _), _app = api
    assert register(client, org, "STUDENT@example.com").status_code == 201
    assert register(client, org).status_code == 409
    headers = login(client)
    old = client.cookies.get("synapse_refresh")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["membership"]["role"] == "student"
    assert "password_hash" not in me.text
    assert client.get("/api/v1/members", headers=headers).status_code == 403
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.cookies.get("synapse_refresh") != old
    with Session(engine) as db:
        assert db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == digest(old))
        ).consumed_at
        assert db.scalar(select(User)).password_hash.startswith("$argon2id$")
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_registration_restrictions_and_validation_does_not_echo_secrets(api):
    client, engine, (org, private), _app = api
    assert len(client.get("/api/v1/organizations/public").json()) == 1
    assert register(client, private).status_code == 400
    assert register(client, str(uuid4())).status_code == 400
    for extra in (
        {"role": "organization_manager"},
        {"is_root_admin": True},
        {"password": "secret"},
    ):
        result = register(client, org, **extra)
        assert result.status_code == 422
        assert '"input"' not in result.text
        assert PASSWORD not in result.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_invite_usage_and_duplicate_registration_rollback(api):
    client, engine, (org, private), _app = api
    assert register(client, org).status_code == 201
    raw = "test-invite-code-long-enough-2026"
    with Session(engine) as db:
        db.add(
            OrganizationInvite(
                organization_id=UUID(private),
                token_hash=digest(raw),
                expires_at=now() + timedelta(days=1),
                max_uses=1,
            )
        )
        db.commit()
    payload = {
        "email": "student@example.com",
        "password": PASSWORD,
        "display_name": "Invited",
        "invite_code": raw,
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    payload["email"] = "invited@example.com"
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    payload["email"] = "another@example.com"
    assert client.post("/api/v1/auth/register", json=payload).status_code == 400
    with Session(engine) as db:
        assert db.scalar(select(OrganizationInvite)).uses == 1


@pytest.mark.parametrize("expired,revoked", [(True, False), (False, True)])
def test_invite_expired_or_revoked(api, expired, revoked):
    client, engine, (_, private), _app = api
    raw = "test-invite-code-long-enough-2026"
    with Session(engine) as db:
        db.add(
            OrganizationInvite(
                organization_id=UUID(private),
                token_hash=digest(raw),
                expires_at=now() + timedelta(days=-1 if expired else 1),
                revoked_at=now() if revoked else None,
                max_uses=1,
            )
        )
        db.commit()
    result = client.post(
        "/api/v1/auth/register",
        json={
            "email": "invited@example.com",
            "password": PASSWORD,
            "display_name": "Invite",
            "invite_code": raw,
        },
    )
    assert result.status_code == 400


def test_origin_validation_login_errors_and_rate_limit(api):
    client, _, _, _ = api
    payload = {"email": "unknown@example.com", "password": PASSWORD}
    assert (
        client.post(
            "/api/v1/auth/login", json=payload, headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    for _ in range(10):
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
    assert client.post("/api/v1/auth/login", json=payload).status_code == 429
    assert client.get("/api/v1/auth/me").status_code == 401


def test_replay_revokes_entire_session(api):
    client, engine, (org, _), app = api
    register(client, org)
    headers = login(client)
    raw = client.cookies.get("synapse_refresh")
    assert client.post("/api/v1/auth/refresh").status_code == 200
    with TestClient(app, headers=HEADERS) as second:
        second.cookies.set("synapse_refresh", raw)
        assert second.post("/api/v1/auth/refresh").status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401
    with Session(engine) as db:
        assert db.scalar(select(AuthSession)).revoked_at is not None
        assert db.scalar(select(AuditLog).where(AuditLog.action == "auth.refresh_replay"))


def test_manager_isolation_and_revocation_on_member_change(api):
    client, engine, (org, other), _app = api
    seed_user(engine, org)
    _, foreign = seed_user(engine, other, "student", "foreign@example.com")
    register(client, org)
    student_headers = login(client)
    member_id = client.get("/api/v1/auth/me", headers=student_headers).json()["membership"]["id"]
    manager_headers = login(client, "manager@example.com")
    rows = client.get("/api/v1/members", headers=manager_headers).json()
    assert len(rows) == 2 and all(row["email"] != "foreign@example.com" for row in rows)
    change = {"role": "teacher", "is_active": True, "reason": "Test permission change"}
    assert (
        client.patch(f"/api/v1/members/{foreign}", json=change, headers=manager_headers).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/members/{member_id}",
            json={**change, "role": "organization_manager"},
            headers=manager_headers,
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/members/{member_id}", json=change, headers=manager_headers
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=student_headers).status_code == 401
    assert client.get("/api/v1/admin/organizations", headers=manager_headers).status_code == 403


@pytest.mark.parametrize("role", ["staff", "teacher", "student"])
def test_non_managers_cannot_manage_members(api, role):
    client, engine, (org, _), _app = api
    seed_user(engine, org, role)
    headers = login(client, "manager@example.com")
    assert client.get("/api/v1/organization", headers=headers).status_code == 200
    assert client.get("/api/v1/members", headers=headers).status_code == 403


def test_root_requires_bound_support_session_and_audits_access(api):
    client, engine, (org, _), _app = api
    seed_user(engine, None, email="root@example.com", root=True)
    root = login(client, "root@example.com")
    assert client.get("/api/v1/members", headers=root).status_code == 403
    support = client.post(
        "/api/v1/admin/support-sessions",
        headers=root,
        json={"organization_id": org, "reason": "Initial configuration"},
    )
    assert support.status_code == 201
    support_id = support.json()["id"]
    access = {**root, "X-Support-Session": support_id}
    assert client.get("/api/v1/members", headers=access).status_code == 200
    other_login = login(client, "root@example.com")
    assert (
        client.get(
            "/api/v1/members", headers={**other_login, "X-Support-Session": support_id}
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/admin/support-sessions/{support_id}", headers=root).status_code
        == 204
    )
    assert client.get("/api/v1/members", headers=access).status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "support.access"))


def test_password_change_revokes_sessions(api):
    client, _, (org, _), _app = api
    register(client, org)
    headers = login(client)
    result = client.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"current_password": PASSWORD, "password": "new-password-2026!"},
    )
    assert result.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    login(client, password="new-password-2026!")


@pytest.mark.parametrize("state", ["user_disabled", "session_expired", "token_expired"])
def test_refresh_rejects_inactive_or_expired_credentials(api, state):
    client, engine, (org, _), _app = api
    register(client, org)
    headers = login(client)
    with Session(engine) as db:
        if state == "user_disabled":
            db.scalar(select(User)).is_active = False
        else:
            row = db.scalar(select(AuthSession if state == "session_expired" else RefreshToken))
            row.created_at = now() - timedelta(days=2)
            row.expires_at = now() - timedelta(days=1)
        db.commit()
    assert client.post("/api/v1/auth/refresh").status_code == 401
    if state != "token_expired":
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_cookie_endpoints_require_non_simple_header(api):
    client, _, _, app = api
    with TestClient(app) as without_header:
        assert without_header.post("/api/v1/auth/logout").status_code == 403
    response = client.options("/api/v1/auth/login", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-synapse-client",
    })
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_disabled_tenant_allows_personal_profile_only(api):
    client, engine, (org, _), _app = api
    register(client, org)
    headers = login(client)
    with Session(engine) as db:
        db.get(Organization, UUID(org)).is_active = False
        db.commit()
    assert client.get("/api/v1/organization", headers=headers).status_code == 403
    assert (
        client.get("/api/v1/auth/me", headers=headers).json()["membership"]["tenant_available"]
        is False
    )


@pytest.mark.parametrize("override", [{"aud": "wrong"}, {"iss": "wrong"}, {"exp": 1}])
def test_invalid_jwt_claims(api, override):
    client, _, (org, _), _app = api
    register(client, org)
    headers = login(client)
    token = headers["Authorization"].split()[1]
    claims = jwt.decode(token, options={"verify_signature": False})
    claims.update(override)
    changed = jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + changed}).status_code
        == 401
    )


@pytest.mark.parametrize("operation", ["refresh", "register"])
def test_concurrent_auth_postgresql(api, operation):
    client, engine, (org, _), app = api
    if engine.dialect.name != "postgresql":
        pytest.skip("Row-lock concurrency requires PostgreSQL")
    raw = None
    if operation == "refresh":
        register(client, org)
        login(client)
        raw = client.cookies.get("synapse_refresh")

    def once():
        with TestClient(app, headers=HEADERS) as concurrent:
            if raw:
                concurrent.cookies.set("synapse_refresh", raw)
                return concurrent.post("/api/v1/auth/refresh").status_code
            return register(concurrent, org).status_code

    with ThreadPoolExecutor(2) as executor:
        results = sorted(executor.map(lambda _: once(), range(2)))
    assert results == ([200, 401] if raw else [201, 409])
    with Session(engine) as db:
        if raw:
            assert db.scalar(select(AuthSession)).revoked_at is not None
            assert db.scalar(select(func.count()).select_from(RefreshToken)) == 2
        else:
            assert db.scalar(select(func.count()).select_from(User)) == 1
            assert db.scalar(select(func.count()).select_from(UserMembership)) == 1


def test_bootstrap_and_seed_idempotence(migrated_engine):
    with Session(migrated_engine) as db:
        bootstrap_root(db, "root@example.com", PASSWORD, "Root")
        with pytest.raises(ValueError):
            bootstrap_root(db, "ROOT@example.com", PASSWORD, "Root")
        seed_centers(db)
        seed_centers(db)
        assert db.scalar(select(func.count()).select_from(Organization)) == 2
        assert db.scalar(select(func.count()).select_from(UserMembership)) == 0


def test_production_config_rejects_missing_or_weak_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production", jwt_secret=None)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production", jwt_secret="a" * 64, cookie_secure=True)
