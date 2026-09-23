import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.invitation_mail import send_invitation
from app.core.security import digest, now, password_hasher
from app.models import AuditLog, MembershipInvitation, Organization, User, UserMembership
from tests.test_auth_api import HEADERS, PASSWORD, login, seed_user

BASE = "/api/v1/organization/membership-invitations"
PUBLIC = "/api/v1/membership-invitations"
EMAIL = "invited@example.com"


@pytest.fixture
def managed(api):
    client, engine, (org, other), app = api
    seed_user(engine, org)
    headers = login(client, "manager@example.com")
    return client, engine, org, other, app, headers


def create(client, headers, **overrides):
    return client.post(
        BASE,
        headers=headers,
        json={
            "email": EMAIL,
            "display_name": "Invited Teacher",
            "role": "teacher",
            "reason": "Teacher onboarding",
            **overrides,
        },
    )


def raw(messages, index=-1):
    return re.search(r"#token=([\w-]+)", messages[index].get_content()).group(1)


def accept_new(client, token, **overrides):
    return client.post(
        PUBLIC + "/accept-new",
        json={
            "token": token,
            "password": PASSWORD,
            "display_name": "Accepted name",
            **overrides,
        },
    )


def age(engine, item_id):
    with Session(engine) as db:
        db.get(MembershipInvitation, UUID(item_id)).last_requested_at = now() - timedelta(minutes=2)
        db.commit()


def existing_user(engine, email=EMAIL):
    with Session(engine) as db:
        user = User(
            email=email,
            display_name="Keep existing name",
            password_hash=password_hasher.hash(PASSWORD),
        )
        db.add(user)
        db.commit()
        return user.id


@pytest.mark.parametrize("existing", [False, True])
def test_two_centers_cannot_activate_two_memberships_postgresql(managed, mail_outbox, existing):
    client, engine, _, other, app, headers = managed
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL cross-center concurrency")
    if existing:
        existing_user(engine)
    create(client, headers)
    first = raw(mail_outbox)
    seed_user(engine, other, email="othermanager@example.com")
    other_headers = login(client, "othermanager@example.com")
    assert create(client, other_headers).status_code == 201
    second = raw(mail_outbox)
    actor = login(client, EMAIL) if existing else HEADERS

    def once(token):
        with TestClient(app, headers=HEADERS) as concurrent:
            if existing:
                return concurrent.post(
                    PUBLIC + "/accept", headers=actor, json={"token": token}
                ).status_code
            return accept_new(concurrent, token).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(once, [first, second])) == [200 if existing else 201, 409]
    with Session(engine) as db:
        users = db.scalars(select(User).where(User.email == EMAIL)).all()
        assert len(users) == 1
        memberships = db.scalars(
            select(UserMembership).where(
                UserMembership.user_id == users[0].id,
            )
        ).all()
        assert len(memberships) == 1 and memberships[0].is_active
        assert (
            db.scalar(
                select(func.count())
                .select_from(MembershipInvitation)
                .where(
                    MembershipInvitation.status == "accepted",
                )
            )
            == 1
        )


def test_invitation_pagination_is_scoped(managed):
    client, engine, org, other, _, headers = managed
    with Session(engine) as db:
        manager_id = db.scalar(select(User.id))
        for i in range(23):
            db.add(
                MembershipInvitation(
                    organization_id=UUID(other if i == 22 else org),
                    created_by=manager_id,
                    email=f"page{i}@example.com",
                    display_name=f"Page {i}",
                    role="teacher",
                    reason="Pagination test",
                    token_hash=digest(str(i)),
                    expires_at=now() + timedelta(days=7),
                    last_requested_at=now(),
                )
            )
        db.commit()
    first = client.get(BASE, headers=headers).json()
    second = client.get(BASE + "?offset=20", headers=headers).json()
    assert first["total"] == second["total"] == 22
    assert len(first["items"]) == 20 and len(second["items"]) == 2
    assert not {row["id"] for row in first["items"]} & {row["id"] for row in second["items"]}


def test_new_invitation_creates_no_user_until_accepted(managed, mail_outbox):
    client, engine, org, _, _, headers = managed
    response = create(client, headers, email=" INVITED@example.com ")
    assert response.status_code == 201, response.text
    token = raw(mail_outbox)
    assert token not in response.text and "token_hash" not in response.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(UserMembership)) == 1
        item = db.scalar(select(MembershipInvitation))
        assert item.email == EMAIL and item.token_hash == digest(token)
        assert item.delivery_status == "sent" and item.sent_at is not None
    preview = client.post(PUBLIC + "/preview", json={"token": token})
    assert preview.status_code == 200 and preview.json()["existing_account"] is False
    assert preview.headers["cache-control"] == "no-store"
    assert preview.json()["role"] == "teacher"
    assert accept_new(client, token).status_code == 201
    assert accept_new(client, token).status_code == 400
    assert client.post(PUBLIC + "/preview", json={"token": token}).status_code == 400
    user_headers = login(client, EMAIL)
    profile = client.get("/api/v1/auth/me", headers=user_headers).json()
    assert profile["membership"]["organization_id"] == org
    assert profile["membership"]["role"] == "teacher"
    assert profile["email_verified_at"] and profile["display_name"] == "Accepted name"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 2
        item = db.scalar(select(MembershipInvitation))
        assert item.status == "accepted" and item.accepted_at and item.accepted_by
        actions = db.scalars(select(AuditLog.action)).all()
        assert {
            "membership_invitation.create",
            "membership_invitation.email_sent",
            "membership_invitation.accept",
        } <= set(actions)
        assert token not in str(db.scalars(select(AuditLog.details)).all())
    listing = client.get(BASE, headers=headers).json()
    assert listing["total"] == 1 and listing["items"][0]["status"] == "accepted"
    assert token not in str(listing)


def test_duplicate_and_existing_membership_are_rejected(managed, mail_outbox):
    client, engine, org, _, _, headers = managed
    first = create(client, headers)
    assert first.status_code == 201
    assert create(client, headers, email=EMAIL.upper()).status_code == 409
    assert len(mail_outbox) == 1
    seed_user(engine, org, role="teacher", email="already@example.com")
    result = create(client, headers, email="already@example.com")
    assert (
        result.status_code == 409 and result.json()["error"]["code"] == "INVITATION_MEMBER_EXISTS"
    )


def test_resend_rotation_cooldown_revocation_and_filters(managed, mail_outbox):
    client, engine, _, _, _, headers = managed
    item_id = create(client, headers).json()["id"]
    old = raw(mail_outbox)
    path = f"{BASE}/{item_id}"
    assert (
        client.post(
            path + "/resend", headers=headers, json={"reason": "Resend request"}
        ).status_code
        == 429
    )
    age(engine, item_id)
    assert (
        client.post(
            path + "/resend", headers=headers, json={"reason": "Resend request"}
        ).status_code
        == 200
    )
    latest = raw(mail_outbox)
    assert old != latest
    assert accept_new(client, old).status_code == 400
    assert client.post(PUBLIC + "/preview", json={"token": latest}).status_code == 200
    assert (
        client.post(
            path + "/revoke", headers=headers, json={"reason": "Changed staffing"}
        ).status_code
        == 204
    )
    assert accept_new(client, latest).status_code == 400
    assert (
        client.post(path + "/resend", headers=headers, json={"reason": "Try again"}).status_code
        == 409
    )
    assert client.get(BASE + "?status=pending", headers=headers).json()["total"] == 0
    assert client.get(BASE + "?status=revoked", headers=headers).json()["total"] == 1
    with Session(engine) as db:
        assert {"membership_invitation.resend", "membership_invitation.revoke"} <= set(
            db.scalars(select(AuditLog.action))
        )


@pytest.mark.parametrize("blocked", ["expired", "center_inactive", "revoked"])
def test_unavailable_links_never_create_accounts(managed, mail_outbox, blocked):
    client, engine, org, _, _, headers = managed
    create(client, headers)
    token = raw(mail_outbox)
    with Session(engine) as db:
        item = db.scalar(select(MembershipInvitation))
        if blocked == "expired":
            item.created_at = now() - timedelta(days=2)
            item.expires_at = now() - timedelta(days=1)
        elif blocked == "revoked":
            item.status = "revoked"
        else:
            db.get(Organization, UUID(org)).is_active = False
        db.commit()
    assert client.post(PUBLIC + "/preview", json={"token": token}).status_code == 400
    assert accept_new(client, token).status_code == 400
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_expired_invite_can_be_renewed_and_new_pending_blocks_older_resend(managed, mail_outbox):
    client, engine, _, _, _, headers = managed
    item_id = create(client, headers).json()["id"]
    with Session(engine) as db:
        item = db.get(MembershipInvitation, UUID(item_id))
        item.created_at = now() - timedelta(days=2)
        item.expires_at = now() - timedelta(days=1)
        item.last_requested_at = now() - timedelta(days=1)
        db.commit()
    assert client.get(BASE + "?status=expired", headers=headers).json()["total"] == 1
    replacement = create(client, headers)
    assert replacement.status_code == 201
    assert (
        client.post(
            f"{BASE}/{item_id}/resend", headers=headers, json={"reason": "Try older invite"}
        ).status_code
        == 409
    )
    assert client.get(BASE + "?status=pending", headers=headers).json()["total"] == 1


def test_existing_account_must_login_and_keeps_its_password_and_name(managed, mail_outbox):
    client, engine, _, _, _, headers = managed
    user_id = existing_user(engine)
    create(client, headers)
    token = raw(mail_outbox)
    assert client.post(PUBLIC + "/preview", json={"token": token}).json()["existing_account"]
    result = accept_new(client, token, password="attempted-password-reset!")
    assert (
        result.status_code == 409 and result.json()["error"]["code"] == "INVITATION_LOGIN_REQUIRED"
    )
    assert client.post(PUBLIC + "/accept", json={"token": token}).status_code == 401
    wrong = client.post(PUBLIC + "/accept", headers=headers, json={"token": token})
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "INVITATION_EMAIL_MISMATCH"
    user_headers = login(client, EMAIL)
    assert (
        client.post(PUBLIC + "/accept", headers=user_headers, json={"token": token}).status_code
        == 200
    )
    login(client, EMAIL)
    with Session(engine) as db:
        user = db.get(User, user_id)
        assert user.display_name == "Keep existing name" and user.email_verified_at
        assert db.scalar(select(func.count()).select_from(User)) == 2


@pytest.mark.parametrize("same_center,suspended", [(False, False), (False, True), (True, True)])
def test_existing_membership_cannot_be_bypassed(managed, mail_outbox, same_center, suspended):
    client, engine, org, other, _, headers = managed
    create(client, headers)
    token = raw(mail_outbox)
    _, member_id = seed_user(engine, org if same_center else other, role="student", email=EMAIL)
    with Session(engine) as db:
        member = db.get(UserMembership, UUID(member_id))
        member.is_active = not suspended
        db.commit()
    user_headers = login(client, EMAIL)
    result = client.post(PUBLIC + "/accept", headers=user_headers, json={"token": token})
    assert result.status_code == 409
    assert result.json()["error"]["code"] == (
        "INVITATION_MEMBER_EXISTS" if same_center else "INVITATION_TRANSFER_REQUIRED"
    )
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(UserMembership)) == 2
        assert db.scalar(select(MembershipInvitation)).status == "pending"


@pytest.mark.parametrize("role", ["teacher", "student", "staff"])
def test_non_managers_cannot_manage_invitations(api, role):
    client, engine, (org, _), _ = api
    seed_user(engine, org, role=role)
    headers = login(client, "manager@example.com")
    assert client.get(BASE, headers=headers).status_code == 403
    assert create(client, headers).status_code == 403


def test_root_support_scope_and_manager_privilege_guard(managed, mail_outbox):
    client, engine, org, other, _, manager = managed
    assert create(client, manager, role="organization_manager").status_code == 403
    seed_user(engine, org, email="root@example.com", root=True)
    root = login(client, "root@example.com")
    assert create(client, root, role="organization_manager").status_code == 403
    support = client.post(
        "/api/v1/admin/support-sessions",
        headers=root,
        json={"organization_id": org, "reason": "Manager onboarding"},
    ).json()["id"]
    scoped = {**root, "X-Support-Session": support}
    response = create(client, scoped, role="organization_manager")
    assert response.status_code == 201
    item_id = response.json()["id"]
    assert (
        client.post(
            f"{BASE}/{item_id}/revoke", headers=manager, json={"reason": "Unauthorized revoke"}
        ).status_code
        == 403
    )
    assert client.get(BASE, headers=manager).json()["items"][0]["can_manage"] is False
    seed_user(engine, other, email="othermanager@example.com")
    outsider = login(client, "othermanager@example.com")
    assert client.get(BASE, headers=outsider).json()["total"] == 0
    assert (
        client.post(
            f"{BASE}/{item_id}/resend", headers=outsider, json={"reason": "Wrong center"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{BASE}/{item_id}/revoke", headers=outsider, json={"reason": "Wrong center"}
        ).status_code
        == 404
    )
    assert accept_new(client, raw(mail_outbox)).status_code == 201


def test_delivery_failure_is_visible_without_leaking_secrets(
    managed, mail_outbox, monkeypatch, caplog
):
    client, engine, _, _, _, headers = managed

    def fail(message):
        mail_outbox.append(message)
        raise OSError("smtp-secret " + EMAIL)

    monkeypatch.setattr("app.core.mail.deliver", fail)
    response = create(client, headers)
    assert response.status_code == 201
    listing = client.get(BASE, headers=headers).json()["items"][0]
    assert listing["delivery_status"] == "failed"
    assert accept_new(client, raw(mail_outbox)).status_code == 400
    assert "smtp-secret" not in caplog.text and EMAIL not in caplog.text
    with Session(engine) as db:
        assert "membership_invitation.email_failed" in db.scalars(select(AuditLog.action)).all()


def test_stale_background_send_does_not_deliver_or_overwrite_new_generation(
    managed, mail_outbox, monkeypatch
):
    client, engine, _, _, _, headers = managed
    tasks = []
    monkeypatch.setattr(
        "app.api.routes.membership_invitations.send_invitation", lambda *args: tasks.append(args)
    )
    item_id = create(client, headers).json()["id"]
    age(engine, item_id)
    assert (
        client.post(
            f"{BASE}/{item_id}/resend", headers=headers, json={"reason": "New generation"}
        ).status_code
        == 200
    )
    send_invitation(*tasks[0])
    assert not mail_outbox
    send_invitation(*tasks[1])
    assert len(mail_outbox) == 1
    assert accept_new(client, raw(mail_outbox)).status_code == 201


def test_client_cannot_change_invitation_scope_or_role(managed, mail_outbox):
    client, _, _, other, _, headers = managed
    assert create(client, headers, organization_id=other).status_code == 422
    create(client, headers)
    token = raw(mail_outbox)
    assert accept_new(client, token, role="organization_manager").status_code == 422
    assert accept_new(client, token, email="attacker@example.com").status_code == 422
    assert accept_new(client, token).status_code == 201


@pytest.mark.parametrize("operation", ["create", "accept", "resend"])
def test_concurrent_invitation_operations_postgresql(managed, mail_outbox, operation):
    client, engine, _, _, app, headers = managed
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency")
    token = item_id = None
    if operation != "create":
        item_id = create(client, headers).json()["id"]
        token = raw(mail_outbox)
        age(engine, item_id)

    def once(_):
        with TestClient(app, headers=HEADERS) as concurrent:
            if operation == "create":
                return create(concurrent, headers).status_code
            if operation == "accept":
                return accept_new(concurrent, token).status_code
            return concurrent.post(
                f"{BASE}/{item_id}/resend", headers=headers, json={"reason": "Concurrent resend"}
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        results = sorted(pool.map(once, range(2)))
    assert results == {"create": [201, 409], "accept": [201, 400], "resend": [200, 429]}[operation]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(MembershipInvitation)) == 1
        assert db.scalar(select(func.count()).select_from(UserMembership)) == (
            2 if operation == "accept" else 1
        )
