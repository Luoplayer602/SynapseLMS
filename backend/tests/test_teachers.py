from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    CourseLevel,
    TeacherCredential,
    TeacherHistory,
    TeacherHistoryLevel,
    TeacherProfile,
    TeachingCapability,
    TeachingCapabilityLevel,
    UserMembership,
)
from tests.test_auth_api import HEADERS, login, seed_user
from tests.test_courses import catalog_fixture  # noqa: F401

BASE = "/api/v1/teachers"


@pytest.fixture
def teachers(catalog_fixture):  # noqa: F811
    client, engine, org, other, app, manager, content, levels = catalog_fixture
    user, membership = seed_user(engine, org, role="teacher", email="teacher-profile@example.com")
    personal = login(client, "teacher-profile@example.com")
    created = client.post(
        BASE,
        headers=manager,
        json={"user_id": user, "full_name": "Teacher", "internal_notes": "PRIVATE-PROFILE"},
    )
    assert created.status_code == 201, created.text
    return (
        client,
        engine,
        org,
        other,
        app,
        manager,
        personal,
        created.json(),
        content,
        levels,
        membership,
    )


def capability(f, levels=None):
    result = f[0].post(
        f"{BASE}/{f[7]['id']}/capabilities",
        headers=f[5],
        json={
            "language_id": f[8]["language_id"],
            "level_ids": levels if levels is not None else [f[9][1]["id"]],
            "reason": "PRIVATE-REASON",
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_profile_permissions_versions_candidates_and_archive(teachers):
    f = teachers
    client, _, _, _, _, manager, personal, profile, _, _, _ = f
    path = BASE + "/" + profile["id"]
    assert "PRIVATE" not in client.get(BASE + "/me", headers=personal).text
    assert client.get(BASE, headers=personal).status_code == 403
    assert client.get(BASE + "/candidates", headers=personal).status_code == 403
    assert client.get(path, headers=personal).status_code == 403
    assert client.get(BASE + "/candidates", headers=manager).json()["total"] == 0
    assert client.get(BASE + "?q=Teacher", headers=manager).json()["total"] == 1
    assert (
        client.post(
            BASE, headers=manager, json={"user_id": profile["user_id"], "full_name": "Duplicate"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            BASE, headers=personal, json={"user_id": profile["user_id"], "full_name": "Self"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            BASE + "/me", headers=personal, json={"version": 1, "full_name": "Forged"}
        ).status_code
        == 422
    )
    updated = client.patch(
        BASE + "/me",
        headers=personal,
        json={"version": 1, "phone": "0123", "introduction": "I teach"},
    )
    assert updated.status_code == 200 and updated.json()["version"] == 2
    assert (
        client.patch(path, headers=manager, json={"version": 1, "full_name": "Old"}).status_code
        == 409
    )
    archived = client.post(
        path + "/archive",
        headers=manager,
        json={"version": 2, "archived": True, "reason": "Archive test"},
    ).json()
    assert archived["archived"]
    assert client.get(BASE + "?status=archived", headers=manager).json()["total"] == 1
    assert client.patch(BASE + "/me", headers=personal, json={"version": 3}).status_code == 409
    assert (
        client.post(
            path + "/credentials", headers=manager, json={"name": "No", "reason": "Blocked"}
        ).status_code
        == 409
    )
    assert client.get(BASE + "/me", headers=personal).status_code == 200
    assert client.get("/api/v1/auth/me", headers=personal).status_code == 200
    assert (
        client.post(
            path + "/archive",
            headers=manager,
            json={"version": 3, "archived": False, "reason": "Restore"},
        ).json()["archived"]
        is False
    )


def test_capabilities_credentials_privacy_history_and_catalog_guard(teachers):
    f = teachers
    client, engine, _, _, _, manager, personal, profile, content, levels, _ = f
    path = f"{BASE}/{profile['id']}"
    cap = capability(f)
    assert [x["id"] for x in cap["levels"]] == [levels[1]["id"]]  # No inference of lower levels.
    credential = client.post(
        path + "/credentials",
        headers=manager,
        json={
            "name": "Certificate",
            "issuer": "Issuer",
            "issued_on": "2020-01-01",
            "expires_on": "2021-01-01",
            "internal_notes": "PRIVATE-CERTIFICATE",
            "reason": "PRIVATE-REASON",
        },
    ).json()
    assert credential["expired"] and not credential["revoked_at"]
    assert "PRIVATE" not in client.get(BASE + "/me/credentials", headers=personal).text
    changed = client.patch(
        path + "/capabilities/" + cap["id"],
        headers=manager,
        json={"version": 1, "level_ids": [], "reason": "Clear current"},
    ).json()
    assert changed["levels"] == []
    for kind, row in (
        ("languages", {"id": content["language_id"], "code": "EN"}),
        ("frameworks", {"id": content["framework_id"], "code": "LOCAL"}),
        ("levels", levels[1]),
    ):
        for method, suffix in (("DELETE", ""), ("PATCH", "/code")):
            response = client.request(
                method,
                f"/api/v1/course-settings/{kind}/{row['id']}{suffix}",
                headers=manager,
                json={"version": 1, "code": row["code"], "reason": "Reference guard"},
            )
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "CATALOG_TEACHER_IN_USE"
    assert (
        client.patch(
            "/api/v1/course-settings/levels/" + levels[1]["id"],
            headers=manager,
            json={"version": 1, "name": "Renamed"},
        ).status_code
        == 200
    )
    for kind, row in (("capabilities", changed), ("credentials", credential)):
        state = client.post(
            f"{path}/{kind}/{row['id']}/state",
            headers=manager,
            json={"version": row["version"], "revoked": True, "reason": "PRIVATE-REVOKE"},
        )
        assert state.status_code == 200 and state.json()["revoked_at"]
    public = client.get(BASE + "/me/history?limit=2", headers=personal).json()
    assert public["total"] == 5 and len(public["items"]) == 2
    history = client.get(BASE + "/me/history", headers=personal)
    assert "PRIVATE" not in history.text and "internal" not in history.text
    assert "Level 2" in history.text and "Renamed" not in history.text
    assert "PRIVATE" in client.get(path + "/history", headers=manager).text
    assert client.get(BASE + "/options/levels", headers=personal).json()["total"] == 2
    assert client.get("/api/v1/course-settings/levels", headers=personal).status_code == 403
    assert client.get("/api/v1/students", headers=personal).status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(TeacherHistory)) == 5
        logs = list(db.scalars(select(AuditLog).where(AuditLog.action.like("teacher.%"))))
        assert all("PRIVATE" not in str(log.details) for log in logs)
        with pytest.raises(IntegrityError), db.begin_nested():
            db.delete(db.get(CourseLevel, UUID(levels[1]["id"])))
            db.flush()


def test_validation_tenant_membership_and_record_scope(teachers):
    f = teachers
    client, engine, org, other, _, manager, personal, profile, content, levels, member = f
    cap = capability(f)
    path = f"{BASE}/{profile['id']}"
    assert (
        client.post(
            path + "/capabilities",
            headers=manager,
            json={"language_id": content["language_id"], "reason": "Duplicate"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            path + "/capabilities/" + cap["id"],
            headers=manager,
            json={"version": 1, "level_ids": [levels[0]["id"]] * 2, "reason": "Duplicate"},
        ).status_code
        == 422
    )
    for payload in ({"issued_on": "2025-01-01", "expires_on": "2020-01-01"}, {"reason": ""}):
        assert (
            client.post(
                path + "/credentials",
                headers=manager,
                json={"name": "Bad", "reason": "Test", **payload},
            ).status_code
            == 422
        )
    other_teacher, _ = seed_user(engine, org, role="teacher", email="another-teacher@example.com")
    second = client.post(
        BASE, headers=manager, json={"user_id": other_teacher, "full_name": "Other"}
    ).json()
    assert (
        client.patch(
            f"{BASE}/{second['id']}/capabilities/{cap['id']}",
            headers=manager,
            json={"version": 1, "reason": "Wrong profile"},
        ).status_code
        == 404
    )
    seed_user(engine, other, email="outsider-teacher@example.com")
    outsider = login(client, "outsider-teacher@example.com")
    assert client.get(path, headers=outsider).status_code == 404
    assert client.get(BASE + "/options/levels", headers=outsider).json()["total"] == 0
    student_id, _ = seed_user(engine, org, role="student", email="not-teacher@example.com")
    student = login(client, "not-teacher@example.com")
    assert (
        client.post(
            BASE, headers=manager, json={"user_id": student_id, "full_name": "No"}
        ).status_code
        == 404
    )
    assert client.get(BASE + "/me", headers=student).status_code == 403
    assert (
        client.post(
            path + "/credentials", headers=personal, json={"name": "Forged", "reason": "Forged"}
        ).status_code
        == 403
    )
    with Session(engine) as db:
        db.get(UserMembership, UUID(member)).is_active = False
        db.commit()
    assert client.get(BASE + "/me", headers=personal).status_code == 403
    assert client.get(path, headers=manager).status_code == 200


@pytest.mark.parametrize("operation", ["create", "update", "delete", "code", "support"])
def test_postgres_teacher_concurrency(teachers, operation):
    f = teachers
    client, engine, org, _, app, manager, _, profile, content, levels, _ = f
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL teacher concurrency")
    path = f"{BASE}/{profile['id']}"
    if operation == "create":
        user, _ = seed_user(engine, org, role="teacher", email="race-teacher@example.com")
    if operation == "support":
        seed_user(engine, org, email="root-teachers@example.com", root=True)
        root = login(client, "root-teachers@example.com")
        support = client.post(
            "/api/v1/admin/support-sessions",
            headers=root,
            json={"organization_id": org, "reason": "Teacher reads"},
        ).json()
        root["X-Support-Session"] = support["id"]

    def run(index):
        with TestClient(app, headers=HEADERS, raise_server_exceptions=False) as worker:
            if operation == "create":
                return worker.post(
                    BASE, headers=manager, json={"user_id": user, "full_name": "Race"}
                ).status_code
            if operation == "update":
                return worker.patch(
                    path, headers=manager, json={"version": 1, "full_name": "Changed"}
                ).status_code
            if operation == "support":
                return (
                    worker.get(path + "/history", headers=root)
                    if index == 1
                    else worker.delete(
                        "/api/v1/admin/support-sessions/" + support["id"], headers=root
                    )
                ).status_code
            if index == 1:
                return worker.request(
                    "DELETE" if operation == "delete" else "PATCH",
                    "/api/v1/course-settings/levels/"
                    + levels[0]["id"]
                    + ("" if operation == "delete" else "/code"),
                    headers=manager,
                    json={
                        "version": 1,
                        "code": levels[0]["code"] if operation == "delete" else "FIXED",
                        "reason": "Race",
                    },
                ).status_code
            return worker.post(
                path + "/capabilities",
                headers=manager,
                json={
                    "language_id": content["language_id"],
                    "level_ids": [levels[0]["id"]],
                    "reason": "Race",
                },
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(run, [1, 2]))
    if operation == "create":
        assert sorted(result) == [201, 409]
    elif operation == "update":
        assert sorted(result) == [200, 409]
    elif operation == "delete":
        assert result in ([204, 422], [409, 201])
    elif operation == "code":
        assert result in ([200, 201], [409, 201])
    else:
        assert result in ([200, 204], [403, 204])
        assert client.get(path, headers=root).status_code == 403


def test_database_composite_constraints(teachers):
    f = teachers
    cap = capability(f)
    with Session(f[1]) as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.get(TeacherProfile, UUID(f[7]["id"])).organization_id = UUID(f[3])
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            ref = db.scalar(
                select(TeachingCapabilityLevel).where(
                    TeachingCapabilityLevel.capability_id == UUID(cap["id"])
                )
            )
            ref.organization_id = UUID(f[3])
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            ref = db.scalar(select(TeacherHistoryLevel))
            ref.organization_id = UUID(f[3])
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                TeacherCredential(
                    teacher_profile_id=UUID(f[7]["id"]),
                    organization_id=UUID(f[3]),
                    name="Wrong tenant",
                )
            )
            db.flush()
        assert db.scalar(select(func.count()).select_from(TeachingCapability)) == 1


def test_language_levels_record_versions_restore_and_history_order(teachers):
    f = teachers
    client, engine, _, _, _, manager, personal, profile, _, levels, _ = f
    path = f"{BASE}/{profile['id']}"
    lang = client.post(
        "/api/v1/course-settings/languages",
        headers=manager,
        json={"code": "OTHER", "name": "Other language"},
    ).json()
    wrong = client.post(
        path + "/capabilities",
        headers=manager,
        json={
            "language_id": lang["id"],
            "level_ids": [levels[0]["id"]],
            "reason": "Wrong language",
        },
    )
    assert wrong.status_code == 422
    assert client.get(path + "/capabilities", headers=manager).json()["total"] == 0
    cap = capability(f, [])
    state_path = path + "/capabilities/" + cap["id"] + "/state"
    assert (
        client.post(
            state_path, headers=manager, json={"version": 1, "revoked": True, "reason": "Revoke"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            path + "/capabilities/" + cap["id"],
            headers=manager,
            json={"version": 2, "reason": "Revoked edit"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            state_path, headers=manager, json={"version": 1, "revoked": False, "reason": "Stale"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            state_path, headers=manager, json={"version": 2, "revoked": False, "reason": "Restore"}
        ).status_code
        == 200
    )
    history = client.get(BASE + "/me/history", headers=personal).json()
    assert [entry["version"] for entry in history["items"]] == [3, 2, 1]
    pages = [
        client.get(BASE + f"/me/history?limit=2&offset={n}", headers=personal).json()["items"]
        for n in (0, 2)
    ]
    assert len({entry["id"] for entries in pages for entry in entries}) == 3
    with Session(engine) as db:
        event = db.scalar(
            select(TeacherHistory).where(TeacherHistory.capability_id == UUID(cap["id"]))
        )
        with pytest.raises(IntegrityError), db.begin_nested():
            event.language_id = UUID(lang["id"])
            db.flush()


@pytest.mark.parametrize("role", ["staff", "root", "teacher", "student"])
def test_teacher_module_actor_roles(teachers, role):
    f = teachers
    client, engine, org, _, _, _, _, profile, _, _, _ = f
    seed_user(
        engine,
        org,
        role="staff" if role == "root" else role,
        email="teacher-role@example.com",
        root=role == "root",
    )
    actor = login(client, "teacher-role@example.com")
    if role == "root":
        assert client.get(BASE, headers=actor).status_code == 403
        support = client.post(
            "/api/v1/admin/support-sessions",
            headers=actor,
            json={"organization_id": org, "reason": "Teacher role test"},
        ).json()
        actor["X-Support-Session"] = support["id"]
    response = client.post(
        f"{BASE}/{profile['id']}/credentials",
        headers=actor,
        json={"name": "Certificate", "reason": "Record certificate"},
    )
    assert response.status_code == (201 if role in ("staff", "root") else 403)
    if role == "teacher":
        assert client.get(BASE + "/me", headers=actor).status_code == 404
        assert client.get(f"{BASE}/{profile['id']}/history", headers=actor).status_code == 403
