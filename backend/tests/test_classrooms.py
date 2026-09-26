from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, AuthRateBucket, Branch, LearningClass, Room
from tests.test_auth_api import HEADERS, login, seed_user
from tests.test_courses import catalog_fixture  # noqa: F401

FAC = "/api/v1/facilities"
BASE = "/api/v1/classes"


@pytest.fixture
def foundation(catalog_fixture):  # noqa: F811
    client, engine, org, other, app, manager, content, levels = catalog_fixture
    course = client.post(
        "/api/v1/courses", headers=manager, json={**content, "code": "CLASS-COURSE"}
    ).json()
    published = client.post(
        "/api/v1/courses/" + course["id"] + "/state",
        headers=manager,
        json={"version": 1, "status": "published", "reason": "Publish fixture"},
    )
    assert published.status_code == 200, published.text
    branch = client.post(
        FAC + "/branches",
        headers=manager,
        json={"code": "MAIN", "name": "Main branch", "address": "PRIVATE-ADDRESS"},
    ).json()
    room = client.post(
        FAC + "/rooms",
        headers=manager,
        json={
            "branch_id": branch["id"],
            "code": "R01",
            "name": "Room",
            "capacity": 20,
            "notes": "PRIVATE-NOTES",
        },
    ).json()
    payload = {
        "course_id": course["id"],
        "branch_id": branch["id"],
        "room_id": room["id"],
        "code": "CLASS-01",
        "name": "Draft class",
        "capacity": 15,
        "starts_on": "2026-10-01",
        "ends_on": "2026-12-01",
        "format": "offline",
    }
    return (
        client,
        engine,
        org,
        other,
        app,
        manager,
        published.json(),
        branch,
        room,
        payload,
        content,
        levels,
    )


def create(f, **changes):
    return f[0].post(BASE, headers=f[5], json={**f[9], **changes})


def state(f, path, version=1, **values):
    return f[0].post(
        path + "/state", headers=f[5], json={"version": version, "reason": "Test change", **values}
    )


def test_class_snapshot_crud_codes_and_reference_guards(foundation):
    f = foundation
    client, engine, _, _, _, manager, course, branch, room, payload, content, levels = f
    created = create(f)
    assert created.status_code == 201, created.text
    row = created.json()
    path = BASE + "/" + row["id"]
    snapshot = row["course_snapshot"]
    assert row["status"] == "draft" and snapshot["name"] == content["name"]
    assert snapshot["exit_level"]["name"] == "Level 2"
    assert (
        client.get(BASE + "?q=CLASS-01&branch_id=" + branch["id"], headers=manager).json()["total"]
        == 1
    )
    assert create(f).status_code == 409
    changed = client.patch(
        path,
        headers=manager,
        json={
            key: value
            for key, value in {**payload, "version": 1, "name": "Changed class"}.items()
            if key not in ("code", "course_id")
        },
    )
    assert changed.status_code == 200 and changed.json()["course_snapshot"] == snapshot
    assert (
        client.patch(
            path + "/code",
            headers=manager,
            json={"version": 2, "code": "CLS-FIX", "reason": "Fix code"},
        ).status_code
        == 200
    )
    assert state(f, path, version=3, status="archived").status_code == 200
    course_path = "/api/v1/courses/" + course["id"]
    assert state(f, course_path, version=2, status="draft").status_code == 200
    assert (
        client.patch(
            course_path,
            headers=manager,
            json={
                **content,
                "name": "Course changed",
                "entry_level_id": None,
                "exit_level_id": levels[0]["id"],
                "version": 3,
            },
        ).status_code
        == 200
    )
    current = client.get(path, headers=manager).json()
    assert current["course_snapshot"] == snapshot and current["course_status"] == "draft"
    for target in (course_path, "/api/v1/course-settings/levels/" + levels[1]["id"]):
        response = client.patch(
            target + "/code",
            headers=manager,
            json={
                "version": 4 if target == course_path else 1,
                "code": "FIXED",
                "reason": "Used snapshot",
            },
        )
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "CATALOG_CLASS_IN_USE"
        )
    with Session(engine) as db:
        logs = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.action.like("branch.%") | AuditLog.action.like("room.%")
                )
            )
        )
        assert all("PRIVATE" not in str(log.details) for log in logs)
        with pytest.raises(IntegrityError), db.begin_nested():
            db.delete(db.get(Branch, UUID(branch["id"])))
            db.flush()
    assert (
        state(f, path, version=4, status="draft").status_code == 200
    )  # Existing class may remain draft.
    assert create(f, code="NO-PUBLISH").status_code == 409


def test_facility_archive_capacity_restore_and_code_rules(foundation):
    f = foundation
    client, _, _, _, _, manager, _, branch, room, _, _, _ = f
    row = create(f).json()
    branch_path, room_path = FAC + "/branches/" + branch["id"], FAC + "/rooms/" + room["id"]
    assert state(f, branch_path, archived=True).status_code == 409
    assert state(f, room_path, archived=True).status_code == 409
    assert (
        client.patch(
            room_path, headers=manager, json={"version": 1, "name": "Too small", "capacity": 10}
        ).status_code
        == 409
    )
    for path in (branch_path, room_path):
        assert (
            client.patch(
                path + "/code",
                headers=manager,
                json={"version": 1, "code": "FIX", "reason": "Used"},
            ).status_code
            == 409
        )
    assert state(f, BASE + "/" + row["id"], status="archived").status_code == 200
    assert (
        client.patch(
            room_path, headers=manager, json={"version": 1, "name": "Smaller", "capacity": 10}
        ).status_code
        == 200
    )
    assert state(f, BASE + "/" + row["id"], version=2, status="draft").status_code == 409
    assert state(f, room_path, version=2, archived=True).status_code == 200
    assert state(f, branch_path, archived=True).status_code == 200
    # A new logical test window; production rate limits remain unchanged.
    with Session(f[1]) as db:
        db.execute(delete(AuthRateBucket))
        db.commit()
    assert state(f, room_path, version=3, archived=False).status_code == 409
    assert state(f, BASE + "/" + row["id"], version=2, status="draft").status_code == 409
    assert state(f, branch_path, version=2, archived=False).status_code == 200
    assert state(f, room_path, version=3, archived=False).status_code == 200
    assert (
        client.patch(
            room_path, headers=manager, json={"version": 4, "name": "Larger", "capacity": 20}
        ).status_code
        == 200
    )
    assert state(f, BASE + "/" + row["id"], version=2, status="draft").status_code == 200
    assert client.get(FAC + "/rooms?status=active", headers=manager).json()["total"] == 1


@pytest.mark.parametrize(
    "change",
    [
        {"capacity": 21},
        {"capacity": 0},
        {"ends_on": "2020-01-01"},
        {"format": "online"},
        {"status": "published"},
    ],
)
def test_invalid_class_payloads(foundation, change):
    assert create(foundation, **change).status_code in (409, 422)
    assert foundation[0].get(BASE, headers=foundation[5]).json()["total"] == 0


def test_online_hybrid_scopes_and_database_constraints(foundation):
    f = foundation
    client, engine, _, other, _, manager, _, branch, room, _, _, _ = f
    assert (
        client.post(
            FAC + "/branches",
            headers=manager,
            json={"code": "BAD", "name": "Bad", "timezone": "Not/A_Timezone"},
        ).status_code
        == 422
    )
    branch2 = client.post(
        FAC + "/branches", headers=manager, json={"code": "OTHER", "name": "Other"}
    ).json()
    assert create(f, branch_id=branch2["id"]).status_code == 422
    online = create(f, format="online", room_id=None).json()
    assert online["room_id"] is None and online["format"] == "online"
    assert create(f, format="hybrid", room_id=None, code="HYBRID").status_code == 201
    assert (
        client.patch(
            FAC + "/branches/" + branch2["id"] + "/code",
            headers=manager,
            json={"version": 1, "code": "RENAMED", "reason": "Unused"},
        ).status_code
        == 200
    )
    seed_user(engine, other, email="other-class@example.com")
    outsider = login(client, "other-class@example.com")
    assert client.get(BASE + "/" + online["id"], headers=outsider).status_code == 404
    assert client.get(BASE, headers=outsider).json()["total"] == 0
    with Session(engine) as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.get(Room, UUID(room["id"])).organization_id = UUID(other)
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            item = db.get(LearningClass, UUID(online["id"]))
            item.format = "offline"
            item.branch_id = UUID(branch2["id"])
            item.room_id = UUID(room["id"])
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.get(LearningClass, UUID(online["id"])).organization_id = UUID(other)
            db.flush()
        assert db.scalar(select(func.count()).select_from(LearningClass)) == 2


@pytest.mark.parametrize("role", ["staff", "teacher", "student", "root"])
def test_roles_and_support(foundation, role):
    f = foundation
    client, engine, org, _, _, _, _, _, _, payload, _, _ = f
    seed_user(
        engine,
        org,
        role="staff" if role == "root" else role,
        root=role == "root",
        email="class-role@example.com",
    )
    actor = login(client, "class-role@example.com")
    if role == "root":
        assert client.get(BASE, headers=actor).status_code == 403
        support = client.post(
            "/api/v1/admin/support-sessions",
            headers=actor,
            json={"organization_id": org, "reason": "Class test"},
        ).json()
        actor["X-Support-Session"] = support["id"]
    allowed = role in ("staff", "root")
    assert client.get(FAC + "/branches", headers=actor).status_code == (200 if allowed else 403)
    assert client.post(
        FAC + "/branches", headers=actor, json={"code": "ROLE", "name": "Role"}
    ).status_code == (201 if role == "root" else 403)
    assert client.post(BASE, headers=actor, json=payload).status_code == (201 if allowed else 403)
    if role == "root":
        client.delete("/api/v1/admin/support-sessions/" + support["id"], headers=actor)
        assert client.get(BASE, headers=actor).status_code == 403


@pytest.mark.parametrize(
    "operation",
    [
        "duplicate",
        "version",
        "capacity",
        "archive_room",
        "archive_branch",
        "course_state",
        "support",
    ],
)
def test_postgres_foundation_concurrency(foundation, operation):
    f = foundation
    client, engine, org, _, app, manager, course, branch, room, payload, _, _ = f
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL facility/class races")
    if operation == "version":
        row = create(f).json()
    if operation == "archive_branch":
        branch = client.post(
            FAC + "/branches", headers=manager, json={"code": "RACE", "name": "Race"}
        ).json()
        payload = {**payload, "branch_id": branch["id"], "room_id": None, "format": "online"}
    if operation == "support":
        seed_user(engine, org, root=True, email="class-root@example.com")
        root = login(client, "class-root@example.com")
        support = client.post(
            "/api/v1/admin/support-sessions",
            headers=root,
            json={"organization_id": org, "reason": "Concurrent reads"},
        ).json()
        root["X-Support-Session"] = support["id"]

    def run(index):
        with TestClient(app, headers=HEADERS, raise_server_exceptions=False) as worker:
            if operation == "support":
                return (
                    worker.get(BASE, headers=root)
                    if index == 1
                    else worker.delete(
                        "/api/v1/admin/support-sessions/" + support["id"], headers=root
                    )
                ).status_code
            if operation == "version":
                return worker.patch(
                    BASE + "/" + row["id"],
                    headers=manager,
                    json={
                        k: v
                        for k, v in {**payload, "version": 1}.items()
                        if k not in ("code", "course_id")
                    },
                ).status_code
            if index == 1 or operation == "duplicate":
                return worker.post(BASE, headers=manager, json=payload).status_code
            if operation == "capacity":
                return worker.patch(
                    FAC + "/rooms/" + room["id"],
                    headers=manager,
                    json={"version": 1, "name": "Smaller", "capacity": 10},
                ).status_code
            path = (
                FAC + "/rooms/" + room["id"]
                if operation == "archive_room"
                else FAC + "/branches/" + branch["id"]
                if operation == "archive_branch"
                else "/api/v1/courses/" + course["id"]
            )
            return worker.post(
                path + "/state",
                headers=manager,
                json={
                    "version": 2 if operation == "course_state" else 1,
                    "reason": "Concurrent archive",
                    **(
                        {"status": "archived"}
                        if operation == "course_state"
                        else {"archived": True}
                    ),
                },
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(run, [1, 2]))
    if operation == "duplicate":
        assert sorted(result) == [201, 409]
    elif operation == "version":
        assert sorted(result) == [200, 409]
    elif operation == "support":
        assert result in ([200, 204], [403, 204])
        assert client.get(BASE, headers=root).status_code == 403
    elif operation == "course_state":
        assert result in ([201, 200], [409, 200])
    else:
        assert result in ([201, 409], [409, 200])
