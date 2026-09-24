from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from time import monotonic
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Course,
    CourseLevel,
    Organization,
)
from tests.test_auth_api import HEADERS, login, seed_user

BASE = "/api/v1/courses"
SETTINGS = "/api/v1/course-settings"
CATALOG = "/api/v1/course-catalog"


@pytest.fixture
def catalog_fixture(api):
    client, engine, (org, other), app = api
    seed_user(engine, org)
    headers = login(client, "manager@example.com")
    language = client.post(
        SETTINGS + "/languages", headers=headers, json={"code": "en", "name": "English"}
    ).json()
    framework = client.post(
        SETTINGS + "/frameworks",
        headers=headers,
        json={"code": "LOCAL", "name": "Local scale", "language_id": language["id"]},
    ).json()
    levels = [
        client.post(
            SETTINGS + "/levels",
            headers=headers,
            json={
                "code": f"L{rank}",
                "name": f"Level {rank}",
                "rank": rank,
                "framework_id": framework["id"],
            },
        ).json()
        for rank in (1, 2)
    ]
    content = {
        "name": "Introductory course",
        "language_id": language["id"],
        "framework_id": framework["id"],
        "entry_level_id": levels[0]["id"],
        "exit_level_id": levels[1]["id"],
        "objectives": "A learning goal",
    }
    return client, engine, org, other, app, headers, content, levels


def create(fixture, code="COURSE-01", **changes):
    return fixture[0].post(BASE, headers=fixture[5], json={**fixture[6], "code": code, **changes})


def state(client, headers, row, status):
    return client.post(
        BASE + f"/{row['id']}/state",
        headers=headers,
        json={"version": row["version"], "status": status, "reason": "Course workflow test"},
    )


def test_publish_catalog_archive_rename_and_permissions(catalog_fixture):
    client, engine, org, _, _, manager, content, levels = catalog_fixture
    row = create(catalog_fixture).json()
    seed_user(engine, org, role="student", email="learner@example.com")
    student = login(client, "learner@example.com")
    assert client.get(CATALOG, headers=student).json()["total"] == 0
    assert client.get(CATALOG + f"/{row['id']}", headers=student).status_code == 404
    assert client.get(CATALOG + "/options", headers=student).json() == {
        "languages": [],
        "levels": [],
    }
    assert client.get(BASE, headers=student).status_code == 403
    assert client.get(SETTINGS + "/levels", headers=student).status_code == 403
    published = state(client, manager, row, "published")
    assert published.status_code == 200, published.text
    row = published.json()
    visible = client.get(CATALOG + f"/{row['id']}", headers=student)
    assert visible.status_code == 200 and "version" not in visible.json()
    assert visible.headers["Cache-Control"] == "no-store"
    assert client.get(CATALOG, headers=student).json()["total"] == 1
    assert len(client.get(CATALOG + "/options", headers=student).json()["levels"]) == 1
    assert (
        client.patch(
            BASE + f"/{row['id']}", headers=manager, json={**content, "version": row["version"]}
        ).json()["error"]["code"]
        == "COURSE_DRAFT_REQUIRED"
    )
    renamed = client.patch(
        SETTINGS + f"/levels/{levels[1]['id']}",
        headers=manager,
        json={"name": "Custom display", "version": levels[1]["version"]},
    )
    assert (
        renamed.status_code == 200
        and renamed.json()["code"] == "L2"
        and renamed.json()["rank"] == 2
    )
    assert (
        client.get(CATALOG + f"/{row['id']}", headers=student).json()["exit_level"]["name"]
        == "Custom display"
    )
    assert (
        client.request(
            "DELETE",
            SETTINGS + f"/levels/{levels[1]['id']}",
            headers=manager,
            json={
                "code": "L2",
                "version": renamed.json()["version"],
                "reason": "Cannot delete used level",
            },
        ).status_code
        == 409
    )
    archived = state(client, manager, row, "archived").json()
    assert client.get(CATALOG, headers=student).json()["total"] == 0
    assert client.get(CATALOG + f"/{row['id']}", headers=student).status_code == 404
    assert state(client, manager, archived, "published").status_code == 409
    assert state(client, manager, archived, "draft").status_code == 200


def test_draft_missing_fields_and_stale_update(catalog_fixture):
    client, _, _, _, _, headers, content, _ = catalog_fixture
    row = client.post(BASE, headers=headers, json={"code": "DRAFT", "name": "Draft"}).json()
    assert set(row["missing_fields"]) == {"language_id", "exit_level_id", "objectives"}
    assert state(client, headers, row, "published").status_code == 422
    current = client.get(BASE + f"/{row['id']}", headers=headers).json()
    assert current["status"] == "draft" and current["version"] == row["version"]
    changed = client.patch(
        BASE + f"/{row['id']}", headers=headers, json={**content, "version": row["version"]}
    )
    assert changed.status_code == 200 and changed.json()["missing_fields"] == []
    assert (
        client.patch(
            BASE + f"/{row['id']}", headers=headers, json={**content, "version": row["version"]}
        ).status_code
        == 409
    )
    assert state(client, headers, row, "published").status_code == 409


@pytest.mark.parametrize("role", ["staff", "teacher", "student"])
def test_role_restrictions(catalog_fixture, role):
    client, engine, org, _, _, manager, content, _ = catalog_fixture
    seed_user(engine, org, role=role, email=f"{role}@example.com")
    actor = login(client, f"{role}@example.com")
    row = create(catalog_fixture).json()
    response = client.patch(
        BASE + f"/{row['id']}", headers=actor, json={**content, "version": row["version"]}
    )
    assert response.status_code == (200 if role == "staff" else 403)
    assert state(client, actor, row, "published").status_code == 403
    assert (
        client.post(
            SETTINGS + "/languages", headers=actor, json={"code": "NEW", "name": "New"}
        ).status_code
        == 403
    )
    assert client.get(SETTINGS + "/levels", headers=actor).status_code == (
        200 if role == "staff" else 403
    )
    row = client.get(BASE + f"/{row['id']}", headers=manager).json()
    row = state(client, manager, row, "published").json()
    if role == "staff":
        assert (
            client.patch(
                BASE + f"/{row['id']}", headers=actor, json={**content, "version": row["version"]}
            ).status_code
            == 409
        )


def test_tenant_and_level_boundaries(catalog_fixture):
    client, engine, _, other, _, headers, content, levels = catalog_fixture
    seed_user(engine, other, email="other@example.com")
    other_headers = login(client, "other@example.com")
    row = create(catalog_fixture).json()
    assert client.get(BASE, headers=other_headers).json()["total"] == 0
    assert client.get(BASE + f"/{row['id']}", headers=other_headers).status_code == 404
    assert (
        client.patch(
            BASE + f"/{row['id']}",
            headers=other_headers,
            json={**content, "version": row["version"]},
        ).status_code
        == 404
    )
    assert (
        client.post(BASE, headers=other_headers, json={**content, "code": "SAME"}).status_code
        == 404
    )
    assert (
        client.post(
            BASE, headers=other_headers, json={"code": row["code"], "name": "Other draft"}
        ).status_code
        == 201
    )
    assert create(catalog_fixture, code=row["code"].lower()).status_code == 409
    assert (
        create(
            catalog_fixture,
            code="REVERSE",
            entry_level_id=levels[1]["id"],
            exit_level_id=levels[0]["id"],
        ).json()["error"]["code"]
        == "COURSE_LEVEL_ORDER"
    )
    language = client.post(
        SETTINGS + "/languages", headers=headers, json={"code": "XX", "name": "Other language"}
    ).json()
    assert (
        create(catalog_fixture, code="MISMATCH", language_id=language["id"]).json()["error"]["code"]
        == "COURSE_LEVEL_MISMATCH"
    )
    framework = client.post(
        SETTINGS + "/frameworks",
        headers=headers,
        json={"code": "OTHER", "name": "Other framework", "language_id": content["language_id"]},
    ).json()
    assert (
        create(catalog_fixture, code="WRONG-SET", framework_id=framework["id"]).status_code == 422
    )
    assert create(catalog_fixture, code="WRONG-NULL", framework_id=None).status_code == 422


def test_root_requires_support_and_locked_tenant_denied(catalog_fixture):
    client, engine, org, _, _, _, _, _ = catalog_fixture
    seed_user(engine, org, email="root@example.com", root=True)
    root = login(client, "root@example.com")
    assert client.get(BASE, headers=root).status_code == 403
    support = client.post(
        "/api/v1/admin/support-sessions",
        headers=root,
        json={"organization_id": org, "reason": "Course support"},
    ).json()
    root["X-Support-Session"] = support["id"]
    assert client.get(BASE, headers=root).status_code == 200
    assert (
        client.delete(f"/api/v1/admin/support-sessions/{support['id']}", headers=root).status_code
        == 204
    )
    assert client.get(BASE, headers=root).status_code == 403
    with Session(engine) as db:
        db.get(Organization, UUID(org)).is_active = False
        db.commit()
    assert client.get(BASE, headers=catalog_fixture[5]).status_code == 403


def test_database_foreign_keys_prevent_cross_tenant_and_delete(catalog_fixture):
    _, engine, org, other, _, _, content, levels = catalog_fixture
    row = create(catalog_fixture).json()
    with Session(engine) as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                Course(
                    organization_id=UUID(other),
                    code="RAW",
                    name="Invalid raw",
                    language_id=UUID(content["language_id"]),
                )
            )
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.delete(db.get(CourseLevel, UUID(levels[1]["id"])))
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.get(Course, UUID(row["id"])).framework_id = None
            db.flush()
        assert db.get(Course, UUID(row["id"])).organization_id == UUID(org)


def test_search_filters_pagination_and_hidden_metadata(catalog_fixture):
    client, engine, org, _, _, manager, content, _ = catalog_fixture
    with Session(engine) as db:
        for index in range(24):
            db.add(
                Course(
                    organization_id=UUID(org),
                    code=f"PAGE-{index}",
                    name=f"Page {index}",
                    status="draft" if index == 0 else "published",
                    **{
                        k: UUID(v) if k.endswith("_id") else v
                        for k, v in content.items()
                        if k != "name"
                    },
                )
            )
        db.commit()
    seed_user(engine, org, role="student", email="reader@example.com")
    student = login(client, "reader@example.com")
    first = client.get(CATALOG, headers=student).json()
    second = client.get(CATALOG + "?offset=20", headers=student).json()
    assert first["total"] == 23 and len(first["items"]) == 20 and len(second["items"]) == 3
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    assert client.get(CATALOG + "?q=%25", headers=student).json()["total"] == 0
    assert client.get(BASE + "?status=draft", headers=manager).json()["total"] == 1
    assert (
        client.get(CATALOG + f"?exit_level_id={content['entry_level_id']}", headers=student).json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get(CATALOG + f"?language_id={content['language_id']}", headers=student).json()[
            "total"
        ]
        == 23
    )


def test_forbidden_fields_and_stable_metadata(catalog_fixture):
    client, _, _, _, _, headers, _, levels = catalog_fixture
    assert create(catalog_fixture, status="published").status_code == 422
    assert create(catalog_fixture, organization_id=catalog_fixture[3]).status_code == 422
    assert (
        client.patch(
            SETTINGS + f"/levels/{levels[0]['id']}",
            headers=headers,
            json={"name": "Changed", "rank": 99, "version": 1},
        ).status_code
        == 422
    )
    assert (
        client.post(
            SETTINGS + "/levels",
            headers=headers,
            json={
                "code": "DUP",
                "name": "Duplicate rank",
                "rank": 1,
                "framework_id": levels[0]["framework_id"],
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize("operation", ["create", "update", "publish"])
def test_concurrent_course_operations_postgresql(catalog_fixture, operation):
    _, engine, _, _, app, headers, content, _ = catalog_fixture
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL course concurrency")
    row = create(catalog_fixture).json() if operation != "create" else None

    def once(_):
        with TestClient(app, headers=HEADERS) as client:
            if operation == "create":
                return client.post(
                    BASE, headers=headers, json={**content, "code": "RACE"}
                ).status_code
            if operation == "publish":
                return state(client, headers, row, "published").status_code
            return client.patch(
                BASE + f"/{row['id']}",
                headers=headers,
                json={**content, "version": row["version"], "name": "Changed"},
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(once, [1, 2])) == [201 if operation == "create" else 200, 409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Course)) == 1


def test_root_parallel_catalog_audit_lock_order(catalog_fixture, monkeypatch):
    """Force a second support audit to contend with a handler holding the org lock."""
    client, engine, org, _, app, _, _, _ = catalog_fixture
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL foreign-key lock regression")
    from app.api.routes import courses

    seed_user(engine, org, email="root@example.com", root=True)
    root = login(client, "root@example.com")
    support = client.post(
        "/api/v1/admin/support-sessions",
        headers=root,
        json={"organization_id": org, "reason": "Lock regression"},
    ).json()
    root["X-Support-Session"] = support["id"]
    holding_org, first = Event(), Lock()
    original = courses.lock_actor

    def coordinated(db, actor):
        if first.acquire(blocking=False):
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            holding_org.set()
            deadline = monotonic() + 8
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                while monotonic() < deadline:
                    blocked = observer.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE :pid = ANY(pg_blocking_pids(pid))"
                        ),
                        {"pid": pid},
                    )
                    if blocked:
                        break
                    Event().wait(0.02)
                else:
                    raise AssertionError("Second request never contended on organization")
        return original(db, actor)

    monkeypatch.setattr(courses, "lock_actor", coordinated)

    def get(path):
        with TestClient(app, headers=HEADERS, raise_server_exceptions=False) as worker:
            return worker.get(path, headers=root).status_code

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(get, BASE)
        assert holding_org.wait(8)
        b = pool.submit(get, SETTINGS + "/levels")
        assert [a.result(timeout=15), b.result(timeout=15)] == [200, 200]
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "support.access", AuditLog.target_id == UUID(support["id"])
                )
            )
            == 2
        )


def action(client, headers, path, item, *, deleting=False, **overrides):
    return client.request(
        "DELETE" if deleting else "PATCH",
        path if deleting else path + "/code",
        headers=headers,
        json={
            "code": item["code"],
            "version": item["version"],
            "reason": "Correct a typo",
            **overrides,
        },
    )


def test_unused_catalog_correction_deletion_and_audit(catalog_fixture):
    client, engine, _, _, _, headers, content, levels = catalog_fixture
    language_path = SETTINGS + "/languages/" + content["language_id"]
    framework_path = SETTINGS + "/frameworks/" + content["framework_id"]
    language = client.get(SETTINGS + "/languages", headers=headers).json()["items"][0]
    framework = client.get(SETTINGS + "/frameworks", headers=headers).json()["items"][0]
    for path, item in [(language_path, language), (framework_path, framework)]:
        for deleting in (False, True):
            result = action(client, headers, path, item, deleting=deleting)
            assert result.json()["error"]["code"] == "CATALOG_HAS_CHILDREN"
    for level in levels:
        path = SETTINGS + "/levels/" + level["id"]
        changed = action(client, headers, path, level, code="fix-" + level["code"])
        assert changed.status_code == 200
        current = changed.json()
        assert current["code"] == "FIX-" + level["code"] and current["rank"] == level["rank"]
        assert action(client, headers, path, level, deleting=True).status_code == 409
        assert (
            action(client, headers, path, current, deleting=True, code="WRONG").status_code == 422
        )
        assert action(client, headers, path, current, deleting=True).status_code == 204
        assert action(client, headers, path, current, deleting=True).status_code == 404
        with Session(engine) as db:
            entries = list(
                db.scalars(select(AuditLog).where(AuditLog.target_id == UUID(level["id"])))
            )
            assert {e.action for e in entries} >= {"catalog.code_change", "catalog.delete"}
            assert (
                next(e for e in entries if e.action == "catalog.delete").details["code"]
                == current["code"]
            )
    changed = action(client, headers, framework_path, framework, code="FIXED").json()
    assert action(client, headers, framework_path, changed, deleting=True).status_code == 204
    changed = action(client, headers, language_path, language, code="FIXED").json()
    assert action(client, headers, language_path, changed, deleting=True).status_code == 204


def test_used_settings_blocked_but_labels_editable(catalog_fixture):
    client, _, _, _, _, headers, _, levels = catalog_fixture
    create(catalog_fixture)
    for deleting in (False, True):
        response = action(
            client, headers, SETTINGS + "/levels/" + levels[0]["id"], levels[0], deleting=deleting
        )
        assert response.json()["error"]["code"] == "CATALOG_IN_USE"
    assert (
        client.patch(
            SETTINGS + "/levels/" + levels[0]["id"],
            headers=headers,
            json={"name": "Typo corrected", "version": 1},
        ).status_code
        == 200
    )


def test_course_code_delete_guards(catalog_fixture):
    client, _, _, _, _, headers, _, _ = catalog_fixture
    row = create(catalog_fixture).json()
    path = BASE + "/" + row["id"]
    changed = action(client, headers, path, row, code="corrected")
    assert changed.status_code == 200 and changed.json()["code"] == "CORRECTED"
    current = changed.json()
    assert action(client, headers, path, row, deleting=True).status_code == 409
    assert action(client, headers, path, current, deleting=True).status_code == 204
    assert client.get(path, headers=headers).status_code == 404
    row = create(catalog_fixture).json()
    path = BASE + "/" + row["id"]
    row = state(client, headers, row, "published").json()
    assert action(client, headers, path, row, deleting=True).status_code == 409
    row = state(client, headers, row, "draft").json()
    for deleting in (False, True):
        assert (
            action(client, headers, path, row, deleting=deleting).json()["error"]["code"]
            == "COURSE_PREVIOUSLY_PUBLISHED"
        )


@pytest.mark.parametrize("role", ["staff", "teacher", "student", "other_manager"])
def test_destructive_catalog_permissions(catalog_fixture, role):
    client, engine, org, other, _, _, _, levels = catalog_fixture
    seed_user(
        engine,
        other if role == "other_manager" else org,
        email="restricted@example.com",
        role="organization_manager" if role == "other_manager" else role,
    )
    headers = login(client, "restricted@example.com")
    row = create(catalog_fixture).json()
    for path, item in [
        (BASE + "/" + row["id"], row),
        (SETTINGS + "/levels/" + levels[0]["id"], levels[0]),
    ]:
        for deleting in (False, True):
            assert action(client, headers, path, item, deleting=deleting).status_code == (
                404 if role == "other_manager" else 403
            )


@pytest.mark.parametrize("operation", ["delete", "code", "attach"])
def test_catalog_mutation_races(catalog_fixture, operation):
    _, engine, _, _, app, headers, content, levels = catalog_fixture
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL delete/correct/attach concurrency")
    level = levels[0]
    path = SETTINGS + "/levels/" + level["id"]

    def run(index):
        with TestClient(app, headers=HEADERS) as client:
            if index == 1:
                return action(client, headers, path, level, deleting=True).status_code
            if operation == "attach":
                return client.post(
                    BASE, headers=headers, json={**content, "code": "RACE"}
                ).status_code
            return action(
                client,
                headers,
                path,
                level,
                deleting=operation == "delete",
                code="FIXED" if operation == "code" else level["code"],
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(run, [1, 2]))
    if operation == "attach":
        assert result in ([204, 404], [409, 201])
    elif operation == "code":
        assert result in ([204, 404], [409, 200])
    else:
        assert sorted(result) == [204, 404]


@pytest.mark.parametrize("revoke", ["support", "tenant", "session"])
def test_parallel_root_catalog_and_revocation(catalog_fixture, revoke):
    client, engine, org, _, app, _, _, _ = catalog_fixture
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL root parallel reads/revocation")
    seed_user(engine, org, email="root@example.com", root=True)
    root = login(client, "root@example.com")
    support = client.post(
        "/api/v1/admin/support-sessions",
        headers=root,
        json={"organization_id": org, "reason": "Parallel reads"},
    ).json()
    root["X-Support-Session"] = support["id"]
    paths = [BASE, *(SETTINGS + "/" + kind for kind in ("languages", "frameworks", "levels"))]

    def run(path):
        with TestClient(app, headers=HEADERS, raise_server_exceptions=False) as worker:
            if path == "revoke":
                if revoke == "support":
                    return worker.delete(
                        "/api/v1/admin/support-sessions/" + support["id"], headers=root
                    ).status_code
                if revoke == "tenant":
                    return worker.patch(
                        "/api/v1/admin/organizations/" + org,
                        headers=root,
                        json={
                            "is_active": False,
                            "is_public": True,
                            "registration_enabled": True,
                            "reason": "Revoke tenant",
                        },
                    ).status_code
                return worker.post(
                    "/api/v1/auth/logout", headers=root, cookies=client.cookies
                ).status_code
            return worker.get(path, headers=root).status_code

    with ThreadPoolExecutor(5) as pool:
        for _ in range(3):
            assert list(pool.map(run, paths)) == [200] * 4
        results = list(pool.map(run, [*paths, "revoke"]))
    assert all(status in (200, 401, 403) for status in results[:4]), results
    assert results[4] in (200, 204), results
    assert client.get(BASE, headers=root).status_code in (401, 403)


def test_correction_validation_and_duplicate_rollback(catalog_fixture):
    client, engine, org, _, _, headers, _, _ = catalog_fixture
    a = client.post(
        SETTINGS + "/languages", headers=headers, json={"code": "AA", "name": "A"}
    ).json()
    b = client.post(
        SETTINGS + "/languages", headers=headers, json={"code": "BB", "name": "B"}
    ).json()
    path = SETTINGS + "/languages/" + a["id"]
    assert action(client, headers, path, a, code=b["code"]).status_code == 409
    assert action(client, headers, path, a, code="!").status_code == 422
    assert action(client, headers, path, a, deleting=True, reason="").status_code == 422
    assert action(client, headers, path, a, version=0).status_code == 422
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.organization_id == UUID(org),
                    AuditLog.target_id == UUID(a["id"]),
                    AuditLog.action.in_(["catalog.delete", "catalog.code_change"]),
                )
            )
            == 0
        )
    assert action(client, headers, path, a, code="CC").status_code == 200
