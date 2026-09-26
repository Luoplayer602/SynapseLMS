from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, CourseLevel, ProficiencyHistory, StudentProficiency, StudentProfile
from tests.test_auth_api import HEADERS, login, seed_user
from tests.test_courses import catalog_fixture  # noqa: F401

BASE = "/api/v1/student-proficiencies"
OPTIONS = "/api/v1/student-proficiency-options"


@pytest.fixture
def proficiency(catalog_fixture):  # noqa: F811
    client, engine, org, other, app, manager, content, levels = catalog_fixture
    user, _ = seed_user(engine, org, role="student", email="proficiency@example.com")
    profile = client.post(
        "/api/v1/students", headers=manager, json={"user_id": user, "full_name": "Learner"}
    ).json()
    personal = login(client, "proficiency@example.com")
    created = client.post(
        BASE + "/me", headers=personal, json={"framework_id": content["framework_id"]}
    )
    assert created.status_code == 201, created.text
    return client, engine, org, other, app, manager, personal, profile, created.json(), levels


def mutation(f, action, payload, personal=True, row=None):
    client, _, _, _, _, manager, student, profile, initial, _ = f
    row = row or initial
    return client.request(
        "POST" if action == "verification" else "PATCH",
        f"{BASE}/{'me' if personal else profile['id']}/{row['id']}/{action}",
        headers=student if personal else manager,
        json={"version": row["version"], **payload},
    )


def verified(f, row=None):
    return mutation(
        f,
        "verification",
        {
            "action": "verify",
            "level_id": f[9][1]["id"],
            "source": "PRIVATE-SOURCE",
            "evidence": "PRIVATE-EVIDENCE",
            "reason": "PRIVATE-REASON",
        },
        personal=False,
        row=row,
    )


def test_declaration_verification_goals_history_and_redaction(proficiency):
    f = proficiency
    client, engine, _, _, _, manager, student, profile, row, levels = f
    assert row["self_level_id"] is None and row["self_declared_at"] is None
    row = mutation(f, "declaration", {"self_level_id": None}).json()
    assert row["self_declared_at"] and row["self_level_id"] is None
    row = verified(f, row).json()
    stamp = row["verified_at"]
    row = mutation(f, "declaration", {"self_level_id": levels[0]["id"]}, row=row).json()
    assert row["verified_level_id"] == levels[1]["id"] and row["verified_at"] == stamp
    row = mutation(
        f,
        "goals",
        {
            "goal_level_id": levels[0]["id"],
            "goal_text": "Review basics",
            "target_date": "2027-01-01",
        },
        row=row,
    ).json()
    assert row["goal_text"] == "Review basics"
    for suffix in ("", f"/{row['id']}", f"/{row['id']}/history"):
        response = client.get(BASE + "/me" + suffix, headers=student)
        assert response.status_code == 200 and "PRIVATE" not in response.text
        assert "evidence" not in response.text and "internal" not in response.text
    history = client.get(f"{BASE}/{profile['id']}/{row['id']}/history", headers=manager).json()
    assert (
        history["total"] == 5 and history["items"][0]["internal"]["evidence"] == "PRIVATE-EVIDENCE"
    )
    # Rename display without rewriting historical snapshots.
    client.patch(
        "/api/v1/course-settings/levels/" + levels[1]["id"],
        headers=manager,
        json={"name": "Renamed", "version": 1},
    )
    assert (
        client.get(f"{BASE}/me/{row['id']}", headers=student).json()["verified_level"]["name"]
        == "Renamed"
    )
    assert (
        client.get(f"{BASE}/me/{row['id']}/history", headers=student).json()["items"][0][
            "verified_level"
        ]["name"]
        == "Level 2"
    )
    row = mutation(
        f, "verification", {"action": "revoke", "reason": "PRIVATE-REVOKE"}, personal=False, row=row
    ).json()
    assert row["verified_level_id"] is None and row["self_level_id"] == levels[0]["id"]
    assert "PRIVATE" not in client.get(f"{BASE}/me/{row['id']}/history", headers=student).text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ProficiencyHistory)) == 6
        audits = list(db.scalars(select(AuditLog).where(AuditLog.action.like("proficiency.%"))))
        assert len(audits) == 6 and all("PRIVATE" not in str(a.details) for a in audits)


def test_validation_ownership_version_and_archived(proficiency):
    f = proficiency
    client, engine, org, other, _, manager, student, profile, row, _ = f
    assert (
        client.post(
            BASE + "/me", headers=student, json={"framework_id": row["framework_id"]}
        ).status_code
        == 409
    )
    assert client.get(f"{BASE}/{profile['id']}", headers=student).status_code == 403
    assert mutation(f, "verification", {"action": "verify", "reason": "forged"}).status_code == 403
    assert mutation(f, "declaration", {"self_level_id": None}, personal=False).status_code == 403
    assert (
        mutation(
            f, "verification", {"action": "verify", "reason": "missing evidence"}, personal=False
        ).status_code
        == 422
    )
    assert (
        mutation(
            f, "declaration", {"self_level_id": None, "verified_by": profile["user_id"]}
        ).status_code
        == 422
    )
    current = mutation(f, "goals", {"goal_text": "New goal"}).json()
    assert mutation(f, "goals", {"goal_text": "Stale"}).status_code == 409
    seed_user(engine, other, email="outsider@example.com")
    outsider = login(client, "outsider@example.com")
    assert client.get(f"{BASE}/{profile['id']}", headers=outsider).status_code == 404
    assert client.get(OPTIONS + "/levels", headers=outsider).json()["total"] == 0
    with Session(engine) as db:
        student_profile = db.get(StudentProfile, UUID(profile["id"]))
        from app.core.security import now

        student_profile.archived_at = now()
        db.commit()
    assert mutation(f, "goals", {"goal_text": "No"}, row=current).status_code == 409
    assert verified(f, current).status_code == 409
    assert client.get(BASE + "/me", headers=student).status_code == 200


def test_references_current_goal_and_history_prevent_catalog_deletion(proficiency):
    f = proficiency
    client, engine, _, _, _, manager, student, _, row, levels = f
    row = mutation(f, "goals", {"goal_level_id": levels[0]["id"]}).json()
    row = mutation(f, "goals", {"goal_level_id": None}, row=row).json()
    for kind, item in (
        ("levels", levels[0]),
        ("frameworks", {"id": row["framework_id"], "code": "LOCAL", "version": 1}),
        ("languages", {"id": row["language_id"], "code": "EN", "version": 1}),
    ):
        for method, suffix in (("DELETE", ""), ("PATCH", "/code")):
            response = client.request(
                method,
                f"/api/v1/course-settings/{kind}/{item['id']}{suffix}",
                headers=manager,
                json={"version": item["version"], "code": item["code"], "reason": "Guard history"},
            )
            assert response.json()["error"]["code"] == "CATALOG_PROFICIENCY_IN_USE"
    with Session(engine) as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.delete(db.get(CourseLevel, UUID(levels[0]["id"])))
            db.flush()
    assert client.get(OPTIONS + "/levels", headers=student).json()["total"] == 2


@pytest.mark.parametrize("role", ["staff", "teacher", "root"])
def test_staff_teacher_root_permissions(proficiency, role):
    f = proficiency
    client, engine, org, _, _, _, _, profile, row, levels = f
    seed_user(
        engine,
        org,
        role="staff" if role == "root" else role,
        root=role == "root",
        email="role@example.com",
    )
    actor = login(client, "role@example.com")
    if role == "root":
        assert client.get(f"{BASE}/{profile['id']}", headers=actor).status_code == 403
        support = client.post(
            "/api/v1/admin/support-sessions",
            headers=actor,
            json={"organization_id": org, "reason": "Proficiency support"},
        ).json()
        actor["X-Support-Session"] = support["id"]
    response = client.post(
        f"{BASE}/{profile['id']}/{row['id']}/verification",
        headers=actor,
        json={
            "version": row["version"],
            "action": "verify",
            "level_id": levels[0]["id"],
            "source": "Test",
            "evidence": "Checked manually",
            "reason": "Record baseline",
        },
    )
    assert response.status_code == (403 if role == "teacher" else 200)
    if role == "root":
        client.delete("/api/v1/admin/support-sessions/" + support["id"], headers=actor)
        assert client.get(f"{BASE}/{profile['id']}", headers=actor).status_code == 403


@pytest.mark.parametrize("operation", ["create", "update", "delete_level", "correct_code"])
def test_proficiency_postgresql_concurrency(proficiency, operation):
    f = proficiency
    _, engine, _, _, app, manager, student, _, row, levels = f
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL proficiency/reference races")
    framework_id = row["framework_id"]
    if operation == "create":
        framework_id = (
            f[0]
            .post(
                "/api/v1/course-settings/frameworks",
                headers=manager,
                json={"code": "RACE", "name": "Race", "language_id": row["language_id"]},
            )
            .json()["id"]
        )

    def run(index):
        with TestClient(app, headers=HEADERS) as worker:
            if operation == "create":
                return worker.post(
                    BASE + "/me", headers=student, json={"framework_id": framework_id}
                ).status_code
            if index == 1 and operation in ("delete_level", "correct_code"):
                return worker.request(
                    "DELETE" if operation == "delete_level" else "PATCH",
                    "/api/v1/course-settings/levels/"
                    + levels[0]["id"]
                    + ("/code" if operation == "correct_code" else ""),
                    headers=manager,
                    json={
                        "version": 1,
                        "code": levels[0]["code"] if operation == "delete_level" else "FIXED",
                        "reason": "Race",
                    },
                ).status_code
            return worker.patch(
                f"{BASE}/me/{row['id']}/goals",
                headers=student,
                json={
                    "version": row["version"],
                    "goal_level_id": levels[0]["id"],
                    "goal_text": "Goal",
                },
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(run, [1, 2]))
    if operation == "create":
        assert sorted(result) == [201, 409]
        with Session(engine) as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(StudentProficiency)
                    .where(StudentProficiency.framework_id == UUID(framework_id))
                )
                == 1
            )
    elif operation == "delete_level":
        assert result in ([204, 422], [409, 200])
    elif operation == "correct_code":
        assert result in ([200, 200], [409, 200])
    else:
        assert sorted(result) == [200, 409]


def test_parallel_root_proficiency_and_support_revocation(proficiency):
    client, engine, org, _, app, _, _, profile, row, _ = proficiency
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL proficiency/support race")
    seed_user(engine, org, email="root-proficiency@example.com", root=True)
    root = login(client, "root-proficiency@example.com")
    support = client.post(
        "/api/v1/admin/support-sessions",
        headers=root,
        json={"organization_id": org, "reason": "Parallel proficiency reads"},
    ).json()
    root["X-Support-Session"] = support["id"]
    item_path = f"{BASE}/{profile['id']}/{row['id']}"
    paths = [item_path, item_path + "/history", OPTIONS + "/levels", OPTIONS + "/frameworks"]

    def run(path):
        with TestClient(app, headers=HEADERS, raise_server_exceptions=False) as worker:
            if path == "revoke":
                return worker.delete(
                    "/api/v1/admin/support-sessions/" + support["id"], headers=root
                ).status_code
            return worker.get(path, headers=root).status_code

    with ThreadPoolExecutor(5) as pool:
        assert list(pool.map(run, paths)) == [200] * 4
        results = list(pool.map(run, [*paths, "revoke"]))
    assert all(code in (200, 403) for code in results[:4]), results
    assert results[4] == 204
    for path in paths:
        assert client.get(path, headers=root).status_code == 403
    assert (
        client.patch(
            item_path + "/goals", headers=root, json={"version": 1, "goal_text": "Revoked"}
        ).status_code
        == 403
    )
    with Session(engine) as db:
        assert db.get(StudentProficiency, UUID(row["id"])).version == 1


def test_wrong_framework_profile_and_database_constraints(proficiency):
    f = proficiency
    client, engine, org, other, _, manager, student, profile, row, levels = f
    other_framework = client.post(
        "/api/v1/course-settings/frameworks",
        headers=manager,
        json={"code": "DIFFERENT", "name": "Other scale", "language_id": row["language_id"]},
    ).json()
    wrong_level = client.post(
        "/api/v1/course-settings/levels",
        headers=manager,
        json={
            "code": "L9",
            "name": "Not equivalent",
            "rank": 9,
            "framework_id": other_framework["id"],
        },
    ).json()
    assert mutation(f, "declaration", {"self_level_id": wrong_level["id"]}).status_code == 422
    assert mutation(f, "goals", {"goal_level_id": wrong_level["id"]}).status_code == 422
    user, _ = seed_user(engine, org, role="student", email="second@example.com")
    second = client.post(
        "/api/v1/students", headers=manager, json={"user_id": user, "full_name": "Second"}
    ).json()
    their_item = client.post(
        BASE + "/" + second["id"], headers=manager, json={"framework_id": row["framework_id"]}
    ).json()
    assert client.get(f"{BASE}/me/{their_item['id']}/history", headers=student).status_code == 404
    assert (
        client.get(f"{BASE}/{profile['id']}/{their_item['id']}", headers=manager).status_code == 404
    )
    with Session(engine) as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.get(StudentProficiency, UUID(row["id"])).self_level_id = UUID(wrong_level["id"])
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                StudentProficiency(
                    student_profile_id=UUID(profile["id"]),
                    organization_id=UUID(other),
                    language_id=UUID(row["language_id"]),
                    framework_id=UUID(other_framework["id"]),
                )
            )
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            entry = db.scalar(
                select(ProficiencyHistory).where(
                    ProficiencyHistory.proficiency_id == UUID(row["id"])
                )
            )
            entry.goal_level_id = UUID(wrong_level["id"])
            db.flush()


def test_history_pagination_and_no_get_writes(proficiency):
    client, engine, _, _, _, _, student, _, row, _ = proficiency
    with Session(engine) as db:
        entry = db.scalar(
            select(ProficiencyHistory).where(ProficiencyHistory.proficiency_id == UUID(row["id"]))
        )
        for version in range(2, 24):
            db.add(
                ProficiencyHistory(
                    organization_id=entry.organization_id,
                    proficiency_id=entry.proficiency_id,
                    language_id=entry.language_id,
                    framework_id=entry.framework_id,
                    actor_id=entry.actor_id,
                    version=version,
                    public_snapshot={**entry.public_snapshot, "version": version},
                    internal_snapshot={},
                )
            )
        db.commit()
    path = f"{BASE}/me/{row['id']}/history"
    first = client.get(path, headers=student).json()
    second = client.get(path + "?offset=20", headers=student).json()
    assert first["total"] == 23 and len(first["items"]) == 20 and len(second["items"]) == 3
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    for _ in range(2):
        client.get(BASE + "/me", headers=student)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(StudentProficiency)) == 1
        assert db.scalar(select(func.count()).select_from(ProficiencyHistory)) == 23
