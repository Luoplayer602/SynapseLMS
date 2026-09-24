from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, GuardianContact, StudentIdentity, StudentProfile, UserMembership
from tests.test_auth_api import HEADERS, login, seed_user

BASE = "/api/v1/students"
PERSONAL = {
    "full_name": "Student profile",
    "phone": "0901234567",
    "guardians": [
        {
            "full_name": "Guardian",
            "relationship": "Parent",
            "phone": "0901234568",
            "is_primary": True,
        }
    ],
}


@pytest.fixture
def roster(api):
    client, engine, (org, other), app = api
    seed_user(engine, org, role="staff", email="staff@example.com")
    user, member = seed_user(engine, org, role="student", email="learner@example.com")
    return client, engine, org, other, app, login(client, "staff@example.com"), user, member


def create(roster, **extra):
    client, _, _, _, _, headers, user, _ = roster
    return client.post(BASE, headers=headers, json={**PERSONAL, "user_id": user, **extra})


def test_student_lifecycle_and_self_redaction(roster):
    client, engine, _, _, _, staff, user, _ = roster
    response = create(roster, internal_notes="Private counseling note")
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["code"].startswith("SL-") and row["missing_fields"] == []
    assert create(roster).status_code == 409
    assert client.get(BASE + "/candidates", headers=staff).json()["total"] == 0
    student = login(client, "learner@example.com")
    mine = client.get(BASE + "/me", headers=student)
    assert mine.status_code == 200 and mine.headers["cache-control"] == "no-store"
    assert "internal_notes" not in mine.json() and "Private counseling note" not in mine.text
    assert client.get(BASE, headers=student).status_code == 403
    assert client.get(BASE + f"/{row['id']}", headers=student).status_code == 403
    assert (
        client.patch(
            BASE + "/me",
            headers=student,
            json={
                **PERSONAL,
                "version": row["version"],
                "internal_notes": "overwrite",
            },
        ).status_code
        == 422
    )
    updated = client.patch(
        BASE + "/me",
        headers=student,
        json={
            **PERSONAL,
            "version": row["version"],
            "full_name": "Updated student",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] > row["version"]
    assert (
        client.patch(
            BASE + "/me",
            headers=student,
            json={
                **PERSONAL,
                "version": row["version"],
            },
        ).status_code
        == 409
    )
    private = client.get(BASE + f"/{row['id']}", headers=staff).json()
    assert private["internal_notes"] == "Private counseling note"
    archive = client.post(
        BASE + f"/{row['id']}/archive",
        headers=staff,
        json={
            "version": private["version"],
            "archived": True,
            "reason": "Archive on request",
        },
    )
    assert archive.status_code == 200
    assert client.get(BASE, headers=staff).json()["total"] == 0
    assert client.get(BASE + "?status=archived", headers=staff).json()["total"] == 1
    assert client.get(BASE + "/me", headers=student).json()["archived"]
    assert (
        client.patch(
            BASE + "/me",
            headers=student,
            json={
                **PERSONAL,
                "version": archive.json()["version"],
            },
        ).json()["error"]["code"]
        == "STUDENT_ARCHIVED"
    )
    restored = client.post(
        BASE + f"/{row['id']}/archive",
        headers=staff,
        json={
            "version": archive.json()["version"],
            "archived": False,
            "reason": "Restore on request",
        },
    )
    assert restored.status_code == 200 and restored.json()["code"] == row["code"]
    with Session(engine) as db:
        assert db.scalar(
            select(UserMembership).where(UserMembership.user_id == UUID(user))
        ).is_active
        logs = db.scalars(select(AuditLog).where(AuditLog.action.like("student.%"))).all()
        assert len(logs) == 4
        assert all("Private counseling note" not in str(log.details) for log in logs)


def test_student_can_create_own_draft_without_side_effect_from_get(roster):
    client, engine, _, _, _, _, _, _ = roster
    student = login(client, "learner@example.com")
    assert client.get(BASE + "/me", headers=student).status_code == 404
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(StudentProfile)) == 0
    result = client.post(BASE + "/me", headers=student, json={"full_name": "Draft"})
    assert result.status_code == 201 and result.json()["missing_fields"] == ["phone"]
    assert "internal_notes" not in result.json()
    assert (
        client.post(BASE + "/me", headers=student, json={"full_name": "Duplicate"}).status_code
        == 409
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"date_of_birth": "2999-01-01"},
        {"phone": "-----"},
        {"full_name": "  "},
        {"organization_id": "11111111-1111-1111-1111-111111111111"},
        {"guardians": PERSONAL["guardians"] * 2},
        {"guardians": [{**PERSONAL["guardians"][0], "email": "invalid"}]},
    ],
)
def test_invalid_profile_never_partially_creates(roster, extra):
    response = create(roster, **extra)
    assert response.status_code == 422, response.text
    with Session(roster[1]) as db:
        assert db.scalar(select(func.count()).select_from(StudentProfile)) == 0


def test_tenant_isolation_permissions_and_candidates(roster):
    client, engine, org, other, _, staff, _, _ = roster
    seed_user(engine, org, role="teacher", email="teacher@example.com")
    teacher = login(client, "teacher@example.com")
    assert client.get(BASE, headers=teacher).status_code == 403
    assert client.get(BASE + "/candidates", headers=teacher).status_code == 403
    assert client.get(BASE + "/me", headers=teacher).status_code == 403
    seed_user(engine, other, email="other@example.com")
    other_headers = login(client, "other@example.com")
    candidate = client.get(BASE + "/candidates", headers=staff).json()
    assert candidate["total"] == 1 and candidate["items"][0]["email"] == "learner@example.com"
    assert client.get(BASE + "/candidates", headers=other_headers).json()["total"] == 0
    assert (
        client.post(
            BASE,
            headers=other_headers,
            json={
                **PERSONAL,
                "user_id": roster[6],
            },
        ).status_code
        == 404
    )
    row = create(roster).json()
    for method, path, body in [
        ("get", f"/{row['id']}", None),
        ("patch", f"/{row['id']}", {**PERSONAL, "version": row["version"]}),
        (
            "post",
            f"/{row['id']}/archive",
            {"version": row["version"], "archived": True, "reason": "test"},
        ),
    ]:
        response = client.request(method, BASE + path, headers=other_headers, json=body)
        assert response.status_code == 404
    assert client.get(BASE, headers=other_headers).json()["total"] == 0


def test_root_requires_live_support(roster):
    client, engine, org, _, _, _, _, _ = roster
    row = create(roster).json()
    seed_user(engine, org, email="root-student@example.com", root=True)
    root = login(client, "root-student@example.com")
    assert client.get(BASE, headers=root).status_code == 403
    support = client.post(
        "/api/v1/admin/support-sessions",
        headers=root,
        json={
            "organization_id": org,
            "reason": "Profile support test",
        },
    ).json()
    root["X-Support-Session"] = support["id"]
    assert client.get(BASE + f"/{row['id']}", headers=root).status_code == 200
    assert client.get(BASE + "/me", headers=root).status_code == 403
    assert (
        client.delete(f"/api/v1/admin/support-sessions/{support['id']}", headers=root).status_code
        == 204
    )
    assert client.get(BASE, headers=root).status_code == 403


def test_profile_search_pagination_and_literal_wildcards(roster):
    client, engine, org, _, _, staff, user, _ = roster
    # Distinct fixture users avoid weakening global identity uniqueness.
    from app.models import User

    with Session(engine) as db:
        for index in range(23):
            account = User(email=f"page{index}@example.com", password_hash="unused-test-hash")
            db.add(account)
            db.flush()
            identity = StudentIdentity(user_id=account.id, code=f"SL-PAGE{index:08d}")
            db.add(identity)
            db.flush()
            db.add(
                StudentProfile(
                    organization_id=UUID(org),
                    identity_id=identity.id,
                    full_name=f"Page {index}",
                    internal_notes="private",
                )
            )
        db.commit()
    first = client.get(BASE, headers=staff).json()
    second = client.get(BASE + "?offset=20", headers=staff).json()
    assert first["total"] == 23 and len(first["items"]) == 20 and len(second["items"]) == 3
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    assert "internal_notes" not in str(first) and "guardians" not in str(first)
    assert client.get(BASE + "?q=SL-PAGE00000003", headers=staff).json()["total"] == 1
    assert client.get(BASE + "?q=%25", headers=staff).json()["total"] == 0


def test_identity_and_primary_guardian_constraints(roster):
    row = create(roster).json()
    with Session(roster[1]) as db:
        original = db.scalar(select(StudentIdentity))
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(StudentIdentity(user_id=original.user_id, code="SL-DUPLICATE"))
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                GuardianContact(
                    student_profile_id=UUID(row["id"]),
                    full_name="Second",
                    relationship="Parent",
                    phone="0901234567",
                    is_primary=True,
                )
            )
            db.flush()


def test_identity_code_reused_after_membership_moves_without_copying_private_profile(roster):
    client, engine, org, other, _, staff, user, member = roster
    old = create(roster, internal_notes="Source only").json()
    from app.core.security import now

    with Session(engine) as db:
        membership = db.get(UserMembership, UUID(member))
        membership.is_active = False
        membership.ended_at = now()
        db.flush()
        db.add(UserMembership(user_id=UUID(user), organization_id=UUID(other), role="student"))
        db.commit()
    seed_user(engine, other, role="staff", email="destination@example.com")
    target = login(client, "destination@example.com")
    result = client.post(
        BASE, headers=target, json={"user_id": user, "full_name": "Destination profile"}
    )
    assert result.status_code == 201, result.text
    assert result.json()["code"] == old["code"]
    assert result.json()["guardians"] == [] and result.json()["internal_notes"] == ""
    assert client.get(BASE + f"/{old['id']}", headers=target).status_code == 404
    assert client.get(BASE + f"/{result.json()['id']}", headers=staff).status_code == 404


def test_suspended_student_cannot_create_or_edit_profile(roster):
    client, engine, _, _, _, staff, _, member = roster
    headers = login(client, "learner@example.com")
    with Session(engine) as db:
        db.get(UserMembership, UUID(member)).is_active = False
        db.commit()
    assert client.get(BASE + "/me", headers=headers).status_code == 403
    assert client.post(BASE + "/me", headers=headers, json=PERSONAL).status_code == 403
    assert create(roster).status_code == 404
    assert client.get(BASE + "/candidates", headers=staff).json()["total"] == 0


@pytest.mark.parametrize("operation", ["create", "update"])
def test_concurrent_profile_writes_postgresql(roster, operation):
    _, engine, _, _, app, headers, user, _ = roster
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL profile concurrency")
    row = create(roster).json() if operation == "update" else None

    def once(index):
        with TestClient(app, headers=HEADERS) as client:
            if row:
                return client.patch(
                    BASE + f"/{row['id']}",
                    headers=headers,
                    json={
                        **PERSONAL,
                        "version": row["version"],
                        "full_name": f"Edit {index}",
                    },
                ).status_code
            return client.post(
                BASE, headers=headers, json={**PERSONAL, "user_id": user}
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(once, [1, 2])) == [200 if row else 201, 409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(StudentProfile)) == 1
        assert db.scalar(select(func.count()).select_from(GuardianContact)) == 1
