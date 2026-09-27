from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alembic import command
from app.models import ClassSession, ClassTeacher, SessionHistory, SessionTeacher, TeacherProfile
from tests.conftest import migration_config
from tests.test_auth_api import HEADERS, login, seed_user
from tests.test_classrooms import foundation  # noqa: F401
from tests.test_courses import catalog_fixture  # noqa: F401
from tests.test_schedules import another, confirm, preview, schedule  # noqa: F401


@pytest.fixture
def operation(schedule, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        "app.api.routes.session_operations.now", lambda: datetime(2026, 9, 26, tzinfo=UTC)
    )
    response, _ = confirm(schedule)
    assert response.status_code == 200, response.text
    row = response.json()["sessions"][0]
    return schedule, row, "/api/v1/class-sessions/" + row["id"]


def body(row, action="reschedule", **changes):
    return {
        "version": row["version"],
        "action": action,
        "reason": "PRIVATE operational reason",
        "request_key": str(uuid4()),
        **(
            {
                "day": "2026-10-05",
                "starts_at": "19:30",
                "ends_at": "21:00",
                "room_id": row["room_id"],
            }
            if action == "reschedule"
            else {}
        ),
        **changes,
    }


def send(o, payload, suffix="operations", headers=None):
    s, _, path = o
    return s["f"][0].post(path + "/" + suffix, headers=headers or s["f"][5], json=payload)


def test_reschedule_preview_atomic_idempotency_history_and_calendar(operation):
    s, row, path = operation
    f = s["f"]
    request = body(row)
    check = send(operation, request, "preview")
    assert check.status_code == 200 and check.json()["after"]["can_apply"]
    assert f[0].get(path, headers=f[5]).json()["session"]["starts_at"] == row["starts_at"]
    applied = send(operation, request)
    assert applied.status_code == 200, applied.text
    changed = applied.json()["session"]
    assert changed["id"] == row["id"] and changed["version"] == 2
    assert changed["starts_at"].startswith("2026-10-05T12:30")
    assert send(operation, request).json()["replayed"]
    assert (
        send(operation, {**request, "reason": "Different reason"}).json()["error"]["code"]
        == "SESSION_REQUEST_REUSED"
    )
    assert send(operation, body(row)).status_code == 409
    history = f[0].get(path + "/history", headers=f[5]).json()
    assert history["total"] == 1
    assert history["items"][0]["before"]["starts_at"] == row["starts_at"]
    assert history["items"][0]["after"]["starts_at"] == changed["starts_at"]
    # Original weekly template stays unchanged.
    assert (
        f[0].get(s["path"] + "/planning", headers=f[5]).json()["plan"]["slots"][0]["starts_at"]
        == "18:00:00"
    )
    q = "/api/v1/class-sessions?starts_on=2026-10-05&ends_on=2026-10-11"
    assert f[0].get(q + "&teacher_id=" + s["teacher"], headers=f[5]).json()["total"] == 1
    assert f[0].get(q + "&room_id=" + row["room_id"], headers=f[5]).json()["total"] == 1
    assert f[0].get(q + "&offset=1", headers=f[5]).json()["items"] == []
    assert f[0].get(q + "&room_id=" + str(uuid4()), headers=f[5]).status_code == 404
    assert (
        f[0]
        .get("/api/v1/class-sessions?starts_on=2026-01-01&ends_on=2026-10-11", headers=f[5])
        .status_code
        == 422
    )
    # Old slot is now free; initial weekly confirmation uses same conflict engine.
    other = another(s)
    assert confirm(s, other)[0].status_code == 200
    fail = send(operation, body(changed, starts_at="18:00", ends_at="19:30"))
    assert fail.status_code == 409
    assert f[0].get(path, headers=f[5]).json()["session"]["version"] == 2


def test_cancel_release_restore_and_guard_semantics(operation):
    s, row, path = operation
    f = s["f"]
    cancelled = send(operation, body(row, "cancel"))
    assert cancelled.status_code == 200, cancelled.text
    row2 = cancelled.json()["session"]
    assert row2["status"] == "cancelled"
    assert f[0].get("/api/v1/teaching-sessions", headers=s["personal"]).json()["total"] == 0
    other = another(s)
    assert confirm(s, other)[0].status_code == 200
    restore = body(row2, "restore")
    p = send(operation, restore, "preview").json()
    assert not p["after"]["can_apply"] and p["after"]["conflicts"]
    assert send(operation, restore).status_code == 409
    assert f[0].get(path, headers=f[5]).json()["session"]["status"] == "cancelled"
    with Session(f[1]) as db:
        other_row = db.scalar(select(ClassSession).where(ClassSession.id != UUID(row["id"])))
        other_id = str(other_row.id)
    other_o = (s, {}, "/api/v1/class-sessions/" + other_id)
    assert send(other_o, body({"version": 1}, "cancel")).status_code == 200
    assert send(operation, restore).status_code == 200
    assert f[0].get("/api/v1/teaching-sessions", headers=s["personal"]).json()["total"] == 1
    assert send(operation, body({"version": 3}, "restore")).status_code == 409
    # Cancel again; class archive is allowed, but restore into archived class is not.
    assert send(operation, body({"version": 3}, "cancel")).status_code == 200
    current = f[0].get(s["path"], headers=f[5]).json()
    assert (
        f[0]
        .post(
            s["path"] + "/state",
            headers=f[5],
            json={
                "version": current["version"],
                "status": "archived",
                "reason": "Archive cancelled class",
            },
        )
        .status_code
        == 200
    )
    assert send(operation, body({"version": 4}, "restore")).status_code == 409


def test_substitution_outside_default_assignment_and_privacy(operation):
    s, row, path = operation
    f = s["f"]
    uid, _ = seed_user(f[1], f[2], role="teacher", email="substitute@example.com")
    with Session(f[1]) as db:
        teacher = TeacherProfile(
            organization_id=UUID(f[2]), user_id=UUID(uid), full_name="Substitute"
        )
        db.add(teacher)
        db.commit()
        tid = str(teacher.id)
    payload = body(row, "substitute", teacher_ids=[tid])
    assert not send(operation, payload, "preview").json()["after"]["can_apply"]
    assert send(operation, payload).status_code == 409
    payload["override_reason"] = "PRIVATE reviewed exception"
    applied = send(operation, payload)
    assert applied.status_code == 200, applied.text
    assert f[0].get("/api/v1/teaching-sessions", headers=s["personal"]).json()["total"] == 0
    personal = login(f[0], "substitute@example.com")
    own = f[0].get("/api/v1/teaching-sessions", headers=personal)
    assert own.json()["total"] == 1 and "PRIVATE" not in own.text
    assert f[0].get(path + "/history", headers=personal).status_code == 403
    with Session(f[1]) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(ClassTeacher)
                .where(ClassTeacher.teacher_profile_id == UUID(tid))
            )
            == 0
        )
        assert db.scalar(select(SessionTeacher.teacher_profile_id)) == UUID(tid)
    # Default qualification waiver is retained when moving this session.
    assert send(operation, body(applied.json()["session"])).status_code == 200


@pytest.mark.parametrize(
    "case",
    ["past", "outside", "missing_room", "wrong_role", "wrong_tenant", "invalid_action_fields"],
)
def test_session_operation_rejections_leave_reservation_unchanged(operation, monkeypatch, case):
    s, row, path = operation
    f = s["f"]
    payload, headers = body(row), f[5]
    expected = 409
    if case == "past":
        monkeypatch.setattr(
            "app.api.routes.session_operations.now", lambda: datetime(2026, 10, 5, 11, tzinfo=UTC)
        )
    elif case == "outside":
        payload["day"] = "2027-01-01"
        expected = 422
    elif case == "missing_room":
        payload["room_id"] = None
    elif case == "wrong_role":
        headers = s["personal"]
        expected = 403
    elif case == "wrong_tenant":
        seed_user(f[1], f[3], email="other-operations@example.com")
        headers = login(f[0], "other-operations@example.com")
        expected = 404
    else:
        payload["action"] = "cancel"
        expected = 422
    assert send(operation, payload, headers=headers).status_code == expected
    assert f[0].get(path, headers=f[5]).json()["session"]["version"] == 1
    assert f[0].get(path + "/history", headers=f[5]).json()["total"] == 0


def test_migration_roundtrip_preserves_populated_sessions_and_assignments(operation):
    s, row, _ = operation
    engine = s["f"][1]
    with engine.begin() as connection:
        config = migration_config(connection)
        command.downgrade(config, "20260926_0011")
        command.upgrade(config, "head")
        command.check(config)
    with Session(engine) as db:
        session = db.get(ClassSession, UUID(row["id"]))
        assert session.status == "scheduled" and session.version == 1
        assert db.scalar(select(SessionTeacher.teacher_profile_id)) == UUID(s["teacher"])
        assert db.scalar(select(func.count()).select_from(SessionHistory)) == 0


def test_old_room_history_keeps_code_guard_but_releases_occupancy(operation):
    s, row, _ = operation
    f = s["f"]
    room = (
        f[0]
        .post(
            "/api/v1/facilities/rooms",
            headers=f[5],
            json={
                "branch_id": row["branch_id"],
                "code": "HISTORY",
                "name": "History room",
                "capacity": 20,
            },
        )
        .json()
    )
    changed = send(operation, body(row, room_id=room["id"])).json()["session"]
    assert send(operation, body(changed, room_id=row["room_id"])).status_code == 200
    path = "/api/v1/facilities/rooms/" + room["id"]
    assert (
        f[0]
        .patch(
            path + "/code", headers=f[5], json={"version": 1, "code": "NEW", "reason": "Fix typo"}
        )
        .status_code
        == 409
    )
    assert (
        f[0]
        .patch(path, headers=f[5], json={"version": 1, "name": "History room", "capacity": 1})
        .status_code
        == 200
    )
    assert (
        f[0]
        .post(
            path + "/state",
            headers=f[5],
            json={"version": 2, "archived": True, "reason": "Unused now"},
        )
        .status_code
        == 200
    )
    history = f[0].get(operation[2] + "/history", headers=f[5]).json()
    assert [x["after"]["version"] for x in history["items"]] == [3, 2]


def test_cancelled_slot_can_be_reused_by_another_session_of_same_class(schedule, monkeypatch):  # noqa: F811
    s, f = schedule, schedule["f"]
    monkeypatch.setattr(
        "app.api.routes.session_operations.now", lambda: datetime(2026, 9, 26, tzinfo=UTC)
    )
    assert (
        f[0]
        .put(
            s["path"] + "/schedule",
            headers=f[5],
            json={**s["draft"], "version": 3, "ends_on": "2026-10-12"},
        )
        .status_code
        == 200
    )
    response, _ = confirm(s)
    a, b = response.json()["sessions"]
    one = (s, a, "/api/v1/class-sessions/" + a["id"])
    two = (s, b, "/api/v1/class-sessions/" + b["id"])
    assert send(one, body(a, "cancel")).status_code == 200
    assert (
        send(two, body(b, day="2026-10-05", starts_at="18:00", ends_at="19:30")).status_code == 200
    )
    assert send(one, body({"version": 2}, "restore")).status_code == 409


@pytest.mark.parametrize("change", ["account", "member", "support"])
def test_postgres_operation_races_with_revocation(operation, change):
    s, row, path = operation
    f = s["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("PostgreSQL authority race")
    seed_user(f[1], f[2], root=True, email="ops-root@example.com")
    root = login(f[0], "ops-root@example.com")
    support = (
        f[0]
        .post(
            "/api/v1/admin/support-sessions",
            headers=root,
            json={"organization_id": f[2], "reason": "Operations race"},
        )
        .json()
    )
    headers = {**root, "X-Support-Session": support["id"]}
    with Session(f[1]) as db:
        uid = str(db.get(TeacherProfile, UUID(s["teacher"])).user_id)
    barrier = Barrier(2)

    def run(i):
        with TestClient(f[4], headers=HEADERS, raise_server_exceptions=False) as client:
            barrier.wait(timeout=10)
            if not i:
                return client.post(
                    path + "/operations", headers=headers, json=body(row)
                ).status_code
            if change == "support":
                return client.delete(
                    "/api/v1/admin/support-sessions/" + support["id"], headers=root
                ).status_code
            if change == "account":
                return client.patch(
                    "/api/v1/admin/users/" + uid,
                    headers=root,
                    json={"is_active": False, "reason": "Disable"},
                ).status_code
            return client.patch(
                "/api/v1/members/" + s["member"],
                headers=headers,
                json={"role": "teacher", "is_active": False, "reason": "Suspend"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(run, [0, 1]))
    assert codes in (
        ([200, 204], [403, 204]) if change == "support" else ([200, 200], [409, 200])
    ), codes
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(SessionHistory)) == (
            1 if codes[0] == 200 else 0
        )


@pytest.mark.parametrize("race", ["same_session", "initial_confirmation", "idempotent", "restore"])
def test_postgres_session_mutation_races(operation, race):
    s, row, path = operation
    f = s["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("PostgreSQL reservation race")
    second = another(s)
    prepared = preview(s, second)
    a = body(row)
    if race == "restore":
        response = send(operation, body(row, "cancel"))
        a = body(response.json()["session"], "restore")
    if race == "initial_confirmation":
        # Move first away then race moving it back vs confirming another in original slot.
        changed = send(operation, a).json()["session"]
        a = body(changed, starts_at="18:00", ends_at="19:30")
    barrier = Barrier(2)

    def run(i):
        with TestClient(f[4], headers=HEADERS, raise_server_exceptions=False) as client:
            barrier.wait(timeout=10)
            if i and race in ("initial_confirmation", "restore"):
                return client.post(
                    second + "/schedule/confirm",
                    headers=f[5],
                    json={
                        "version": prepared["version"],
                        "preview_digest": prepared["preview_digest"],
                        "confirmation_key": str(uuid4()),
                    },
                ).status_code
            b = (
                a
                if race == "idempotent" or not i
                else {**a, "request_key": str(uuid4()), "starts_at": "20:00", "ends_at": "21:30"}
            )
            return client.post(path + "/operations", headers=f[5], json=b).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(run, [0, 1]))
    assert sorted(codes) == ([200, 200] if race == "idempotent" else [200, 409]), codes
