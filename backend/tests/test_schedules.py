from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, time
from threading import Barrier
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.schedules import local_instant
from app.core.errors import APIError
from app.models import (
    AuthRateBucket,
    ClassSession,
    ClassTeacher,
    SessionTeacher,
    TeacherProfile,
    TeachingCapability,
    TeachingCapabilityLevel,
    UserMembership,
)
from tests.test_auth_api import HEADERS, login, seed_user
from tests.test_classrooms import foundation  # noqa: F401
from tests.test_courses import catalog_fixture  # noqa: F401


@pytest.fixture
def schedule(foundation, monkeypatch):  # noqa: F811
    # Reservation guards are tested against a fixed clock, independent of CI's date.
    for module in ("classrooms", "teachers", "schedules"):
        monkeypatch.setattr(
            f"app.api.routes.{module}.now", lambda: datetime(2026, 9, 26, tzinfo=UTC)
        )
    f = foundation
    user_id, member_id = seed_user(f[1], f[2], role="teacher", email="schedule-teacher@example.com")
    with Session(f[1]) as db:
        teacher = TeacherProfile(
            organization_id=UUID(f[2]),
            user_id=UUID(user_id),
            full_name="Scheduler teacher",
            internal_notes="PRIVATE",
        )
        db.add(teacher)
        db.flush()
        cap = TeachingCapability(
            organization_id=teacher.organization_id,
            teacher_profile_id=teacher.id,
            language_id=UUID(f[10]["language_id"]),
        )
        db.add(cap)
        db.flush()
        db.add(
            TeachingCapabilityLevel(
                capability_id=cap.id,
                organization_id=teacher.organization_id,
                language_id=cap.language_id,
                framework_id=UUID(f[10]["framework_id"]),
                level_id=UUID(f[11][1]["id"]),
            )
        )
        db.commit()
        teacher_id = str(teacher.id)
    row = f[0].post("/api/v1/classes", headers=f[5], json=f[9]).json()
    path = "/api/v1/classes/" + row["id"]
    assignment = f[0].put(
        path + "/teachers", headers=f[5], json={"version": 1, "teacher_ids": [teacher_id]}
    )
    assert assignment.status_code == 200, assignment.text
    draft = {
        "version": 2,
        "starts_on": "2026-10-05",
        "ends_on": "2026-10-05",
        "slots": [
            {
                "weekday": 0,
                "starts_at": "18:00",
                "ends_at": "19:30",
                "room_id": f[8]["id"],
                "teacher_ids": [teacher_id],
            }
        ],
    }
    saved = f[0].put(path + "/schedule", headers=f[5], json=draft)
    assert saved.status_code == 200, saved.text
    return {
        "f": f,
        "path": path,
        "class_id": row["id"],
        "teacher": teacher_id,
        "draft": draft,
        "member": member_id,
        "personal": login(f[0], "schedule-teacher@example.com"),
    }


def reset_rate(s):
    with Session(s["f"][1]) as db:
        db.execute(delete(AuthRateBucket))
        db.commit()


def preview(s, path=None):
    response = s["f"][0].get((path or s["path"]) + "/schedule/preview", headers=s["f"][5])
    assert response.status_code == 200, response.text
    return response.json()


def confirm(s, path=None, prepared=None, **changes):
    data = prepared or preview(s, path)
    payload = {
        "version": data["version"],
        "preview_digest": data["preview_digest"],
        "confirmation_key": str(uuid4()),
        **changes,
    }
    return s["f"][0].post(
        (path or s["path"]) + "/schedule/confirm", headers=s["f"][5], json=payload
    ), payload


def another(s, code="ANOTHER", slots=None, branch_id=None, room_id=None):
    f = s["f"]
    row = (
        f[0]
        .post(
            "/api/v1/classes",
            headers=f[5],
            json={
                **f[9],
                "code": code,
                **({"branch_id": branch_id, "room_id": room_id} if branch_id else {}),
            },
        )
        .json()
    )
    path = "/api/v1/classes/" + row["id"]
    assert (
        f[0]
        .put(path + "/teachers", headers=f[5], json={"version": 1, "teacher_ids": [s["teacher"]]})
        .status_code
        == 200
    )
    assert (
        f[0]
        .put(
            path + "/schedule",
            headers=f[5],
            json={**s["draft"], "slots": slots or s["draft"]["slots"]},
        )
        .status_code
        == 200
    )
    return path


def test_preview_confirmation_idempotency_and_guards(schedule):
    s, f = schedule, schedule["f"]
    p = preview(s)
    assert f[0].get(s["path"] + "/schedule/preview?version=1", headers=f[5]).status_code == 409
    assert p["can_confirm"] and len(p["sessions"]) == 1
    assert p["sessions"][0]["starts_at"] == "2026-10-05T11:00:00+00:00"
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(ClassSession)) == 0
    response, payload = confirm(s, prepared=p)
    assert response.status_code == 200, response.text
    assert len(response.json()["sessions"]) == 1
    assert f[0].post(s["path"] + "/schedule/confirm", headers=f[5], json=payload).status_code == 200
    assert confirm(s, prepared=p)[0].status_code == 409
    assert (
        f[0]
        .put(s["path"] + "/schedule", headers=f[5], json={**s["draft"], "version": 4})
        .status_code
        == 409
    )
    assert (
        f[0]
        .put(s["path"] + "/teachers", headers=f[5], json={"version": 4, "teacher_ids": []})
        .status_code
        == 409
    )
    changed = {k: v for k, v in f[9].items() if k not in ("code", "course_id")}
    assert (
        f[0]
        .patch(s["path"], headers=f[5], json={**changed, "version": 4, "capacity": 14})
        .status_code
        == 409
    )
    assert (
        f[0]
        .patch(s["path"], headers=f[5], json={**changed, "version": 4, "name": "Renamed"})
        .status_code
        == 200
    )
    assert (
        f[0]
        .patch(
            s["path"] + "/code",
            headers=f[5],
            json={"version": 5, "code": "FIX", "reason": "Correction"},
        )
        .status_code
        == 409
    )
    assert (
        f[0]
        .post(
            s["path"] + "/state",
            headers=f[5],
            json={"version": 5, "status": "archived", "reason": "Archive"},
        )
        .status_code
        == 409
    )
    assert (
        f[0]
        .patch(
            "/api/v1/facilities/branches/" + f[7]["id"],
            headers=f[5],
            json={"version": 1, "name": "Branch", "timezone": "UTC"},
        )
        .status_code
        == 409
    )
    assert (
        f[0]
        .post(
            "/api/v1/teachers/" + s["teacher"] + "/archive",
            headers=f[5],
            json={"version": 1, "archived": True, "reason": "Archive"},
        )
        .status_code
        == 409
    )
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(ClassSession)) == 1
        assert db.scalar(select(func.count()).select_from(SessionTeacher)) == 1
        with pytest.raises(IntegrityError), db.begin_nested():
            db.get(ClassTeacher, db.scalar(select(ClassTeacher.id))).organization_id = UUID(f[3])
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.get(ClassSession, db.scalar(select(ClassSession.id))).organization_id = UUID(f[3])
            db.flush()


def test_room_teacher_conflicts_and_atomic_batch(schedule):
    s = schedule
    assert confirm(s)[0].status_code == 200
    other = another(
        s,
        slots=[
            s["draft"]["slots"][0],
            {**s["draft"]["slots"][0], "starts_at": "20:00", "ends_at": "21:00"},
        ],
    )
    p = preview(s, other)
    assert not p["can_confirm"] and {x["type"] for x in p["conflicts"]} == {"room", "teacher"}
    assert s["f"][8]["id"] in p["room_checks"][0]["unavailable_room_ids"]
    assert confirm(s, other, p)[0].status_code == 409
    with Session(s["f"][1]) as db:
        assert db.scalar(select(func.count()).select_from(ClassSession)) == 1
    adjacent = another(
        s,
        code="ADJACENT",
        slots=[{**s["draft"]["slots"][0], "starts_at": "19:30", "ends_at": "21:00"}],
    )
    assert preview(s, adjacent)["can_confirm"]
    assert confirm(s, adjacent)[0].status_code == 200


def test_teacher_conflict_across_branches_and_room_session_guards(schedule):
    s, f = schedule, schedule["f"]
    assert confirm(s)[0].status_code == 200
    branch = (
        f[0]
        .post("/api/v1/facilities/branches", headers=f[5], json={"name": "Other", "code": "OTHER"})
        .json()
    )
    room = (
        f[0]
        .post(
            "/api/v1/facilities/rooms",
            headers=f[5],
            json={"name": "Other room", "code": "OTHER", "branch_id": branch["id"], "capacity": 20},
        )
        .json()
    )
    other = another(
        s,
        branch_id=branch["id"],
        room_id=room["id"],
        slots=[{**s["draft"]["slots"][0], "room_id": room["id"]}],
    )
    p = preview(s, other)
    assert {x["type"] for x in p["conflicts"]} == {"teacher"}
    # A session room is protected even if it differs from the default class room.
    other_room = (
        f[0]
        .post(
            "/api/v1/facilities/rooms",
            headers=f[5],
            json={
                "name": "Session room",
                "code": "SESSION",
                "branch_id": f[7]["id"],
                "capacity": 20,
            },
        )
        .json()
    )
    another_path = another(
        s,
        code="NONDEFAULT",
        slots=[
            {
                **s["draft"]["slots"][0],
                "room_id": other_room["id"],
                "starts_at": "20:00",
                "ends_at": "21:00",
            }
        ],
    )
    assert confirm(s, another_path)[0].status_code == 200
    room_path = "/api/v1/facilities/rooms/" + other_room["id"]
    assert (
        f[0]
        .patch(room_path, headers=f[5], json={"version": 1, "name": "Small", "capacity": 10})
        .status_code
        == 409
    )
    assert (
        f[0]
        .post(
            room_path + "/state",
            headers=f[5],
            json={"version": 1, "archived": True, "reason": "Archive"},
        )
        .status_code
        == 409
    )
    assert (
        f[0]
        .patch(
            room_path + "/code",
            headers=f[5],
            json={"version": 1, "code": "FIX", "reason": "Correction"},
        )
        .status_code
        == 409
    )


@pytest.mark.parametrize(
    "change",
    ["empty_teacher", "empty_room", "self_overlap", "unavailable_teacher", "stale_preview"],
)
def test_incomplete_conflicting_or_stale_preview_cannot_confirm(schedule, change):
    s, f = schedule, schedule["f"]
    p = preview(s)
    if change == "stale_preview":
        assert (
            f[0]
            .patch(
                "/api/v1/facilities/rooms/" + f[8]["id"],
                headers=f[5],
                json={"version": 1, "name": "Renamed", "capacity": 20},
            )
            .status_code
            == 200
        )
        assert confirm(s, prepared=p)[0].json()["error"]["code"] == "SCHEDULE_PREVIEW_STALE"
        assert confirm(s)[0].status_code == 200
        return
    if change == "unavailable_teacher":
        with Session(f[1]) as db:
            db.get(UserMembership, UUID(s["member"])).is_active = False
            db.commit()
    else:
        slots = [dict(s["draft"]["slots"][0])]
        if change == "empty_teacher":
            slots[0]["teacher_ids"] = []
        elif change == "empty_room":
            slots[0]["room_id"] = None
        else:
            slots.append(dict(slots[0]))
        assert (
            f[0]
            .put(
                s["path"] + "/schedule",
                headers=f[5],
                json={**s["draft"], "version": 3, "slots": slots},
            )
            .status_code
            == 200
        )
    p = preview(s)
    assert not p["can_confirm"]
    assert confirm(s, prepared=p)[0].status_code == 409
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(ClassSession)) == 0


def test_qualification_override_personal_privacy_and_role_isolation(schedule):
    s, f = schedule, schedule["f"]
    with Session(f[1]) as db:
        db.execute(delete(TeachingCapabilityLevel))
        db.commit()
    assert not preview(s)["can_confirm"]
    payload = {"version": 3, "teacher_ids": [s["teacher"]]}
    assert f[0].put(s["path"] + "/teachers", headers=f[5], json=payload).status_code == 422
    payload["override_reason"] = "PRIVATE override reviewed"
    assert f[0].put(s["path"] + "/teachers", headers=f[5], json=payload).status_code == 200
    assert confirm(s)[0].status_code == 200
    personal = f[0].get("/api/v1/teaching-sessions", headers=s["personal"])
    assert personal.status_code == 200 and personal.json()["total"] == 1
    assert "PRIVATE" not in personal.text and "override_reason" not in personal.text
    assert f[0].get(s["path"] + "/planning", headers=s["personal"]).status_code == 403
    assert f[0].get("/api/v1/teaching-sessions", headers=f[5]).status_code == 403
    seed_user(f[1], f[2], role="teacher", email="unassigned@example.com")
    unassigned = login(f[0], "unassigned@example.com")
    assert f[0].get("/api/v1/teaching-sessions", headers=unassigned).json()["total"] == 0
    seed_user(f[1], f[3], email="other-scheduler@example.com")
    other = login(f[0], "other-scheduler@example.com")
    assert f[0].get(s["path"] + "/planning", headers=other).status_code == 404
    with Session(f[1]) as db:
        db.get(UserMembership, UUID(s["member"])).is_active = False
        db.commit()
    assert f[0].get("/api/v1/teaching-sessions", headers=s["personal"]).status_code == 403


@pytest.mark.parametrize(
    "operation", ["room", "teacher", "same_class", "idempotent", "shrink", "teacher_archive"]
)
def test_postgres_atomic_confirmation_races(schedule, operation):
    s, f = schedule, schedule["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("PostgreSQL reservation concurrency")
    path2 = s["path"]
    if operation in ("room", "teacher"):
        path2 = another(s)
    p1, p2 = preview(s), preview(s, path2)
    key = str(uuid4())
    barrier = Barrier(2)

    def run(i):
        with TestClient(f[4], headers=HEADERS, raise_server_exceptions=False) as client:
            barrier.wait(timeout=10)
            if i and operation == "shrink":
                return client.patch(
                    "/api/v1/facilities/rooms/" + f[8]["id"],
                    headers=f[5],
                    json={"version": 1, "name": "Room", "capacity": 14},
                ).status_code
            if i and operation == "teacher_archive":
                return client.post(
                    "/api/v1/teachers/" + s["teacher"] + "/archive",
                    headers=f[5],
                    json={"version": 1, "archived": True, "reason": "Archive teacher"},
                ).status_code
            p = p2 if i else p1
            return client.post(
                (path2 if i else s["path"]) + "/schedule/confirm",
                headers=f[5],
                json={
                    "version": p["version"],
                    "preview_digest": p["preview_digest"],
                    "confirmation_key": key if operation == "idempotent" else str(uuid4()),
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(run, [0, 1]))
    assert results == ([200, 200] if operation == "idempotent" else [200, 409]), results
    with Session(f[1]) as db:
        count = db.scalar(select(func.count()).select_from(ClassSession))
        assert count <= 1
        if operation not in ("teacher_archive",):
            assert count == 1


@pytest.mark.parametrize(
    "day,clock", [(date(2026, 3, 8), time(2, 30)), (date(2026, 11, 1), time(1, 30))]
)
def test_dst_ambiguous_or_nonexistent_wall_times_are_rejected(day, clock):
    with pytest.raises(APIError) as exc:
        local_instant(day, clock, ZoneInfo("America/New_York"))
    assert exc.value.code == "SCHEDULE_DST_TIME"


@pytest.mark.parametrize("role", ["staff", "student", "teacher", "root"])
def test_scheduling_roles_root_support_and_revocation(schedule, role):
    s, f = schedule, schedule["f"]
    seed_user(
        f[1],
        f[2],
        role="staff" if role == "root" else role,
        root=role == "root",
        email="schedule-role@example.com",
    )
    headers = login(f[0], "schedule-role@example.com")
    if role == "root":
        assert f[0].get(s["path"] + "/planning", headers=headers).status_code == 403
        support = (
            f[0]
            .post(
                "/api/v1/admin/support-sessions",
                headers=headers,
                json={"organization_id": f[2], "reason": "Schedule review"},
            )
            .json()
        )
        headers["X-Support-Session"] = support["id"]
    allowed = role in ("staff", "root")
    assert f[0].get(s["path"] + "/planning", headers=headers).status_code == (
        200 if allowed else 403
    )
    assert f[0].put(
        s["path"] + "/schedule", headers=headers, json={**s["draft"], "version": 3}
    ).status_code == (200 if allowed else 403)
    if role == "root":
        assert (
            f[0]
            .delete("/api/v1/admin/support-sessions/" + support["id"], headers=headers)
            .status_code
            == 204
        )
        assert f[0].get(s["path"] + "/schedule/preview", headers=headers).status_code == 403


@pytest.mark.parametrize(
    "change", ["weekday", "timezone", "reverse", "outside", "teacher", "tenant"]
)
def test_invalid_draft_never_changes_version_or_creates_sessions(schedule, change):
    s, f = schedule, schedule["f"]
    slot = dict(s["draft"]["slots"][0])
    data = {**s["draft"], "version": 3, "slots": [slot]}
    if change == "weekday":
        slot["weekday"] = 7
    elif change == "timezone":
        slot["starts_at"] = "18:00:00+07:00"
    elif change == "reverse":
        slot["ends_at"] = "17:00"
    elif change == "outside":
        data["starts_on"] = "2026-09-01"
    elif change == "teacher":
        slot["teacher_ids"] = [str(uuid4())]
    else:
        data["organization_id"] = f[3]
    assert f[0].put(s["path"] + "/schedule", headers=f[5], json=data).status_code == 422
    result = f[0].get(s["path"] + "/planning", headers=f[5]).json()
    assert result["class"]["version"] == 3 and result["sessions"] == []


def test_online_draft_has_no_room_and_retains_branch(schedule):
    s, f = schedule, schedule["f"]
    values = {key: value for key, value in f[9].items() if key not in ("code", "course_id")}
    assert (
        f[0]
        .patch(
            s["path"],
            headers=f[5],
            json={**values, "version": 3, "format": "online", "room_id": None},
        )
        .status_code
        == 200
    )
    assert not preview(s)["can_confirm"]
    slot = {**s["draft"]["slots"][0], "room_id": None}
    assert (
        f[0]
        .put(
            s["path"] + "/schedule",
            headers=f[5],
            json={**s["draft"], "version": 4, "slots": [slot]},
        )
        .status_code
        == 200
    )
    response, _ = confirm(s)
    assert response.status_code == 200
    assert response.json()["sessions"][0]["room_name"] is None
    assert response.json()["sessions"][0]["branch_name"] == f[7]["name"]


@pytest.mark.parametrize("operation", ["member", "account", "support"])
def test_postgres_confirm_races_with_authority_changes(schedule, operation):
    s, f = schedule, schedule["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("PostgreSQL authority/teacher eligibility race")
    seed_user(f[1], f[2], root=True, email="schedule-root@example.com")
    root = login(f[0], "schedule-root@example.com")
    support = (
        f[0]
        .post(
            "/api/v1/admin/support-sessions",
            headers=root,
            json={"organization_id": f[2], "reason": "Race review"},
        )
        .json()
    )
    headers = {**root, "X-Support-Session": support["id"]}
    p = preview(s)
    barrier = Barrier(2)
    with Session(f[1]) as db:
        teacher_user = str(db.get(TeacherProfile, UUID(s["teacher"])).user_id)

    def run(i):
        with TestClient(f[4], headers=HEADERS, raise_server_exceptions=False) as client:
            barrier.wait(timeout=10)
            if not i:
                return client.post(
                    s["path"] + "/schedule/confirm",
                    headers=headers,
                    json={
                        "version": p["version"],
                        "preview_digest": p["preview_digest"],
                        "confirmation_key": str(uuid4()),
                    },
                ).status_code
            if operation == "support":
                return client.delete(
                    "/api/v1/admin/support-sessions/" + support["id"], headers=root
                ).status_code
            if operation == "account":
                return client.patch(
                    "/api/v1/admin/users/" + teacher_user,
                    headers=root,
                    json={"is_active": False, "reason": "Disable teacher"},
                ).status_code
            return client.patch(
                "/api/v1/members/" + s["member"],
                headers=headers,
                json={"role": "teacher", "is_active": False, "reason": "Suspend teacher"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [0, 1]))
    if operation == "support":
        assert results in ([200, 204], [403, 204]), results
        assert f[0].get(s["path"] + "/planning", headers=headers).status_code == 403
    else:
        assert results in ([200, 200], [409, 200]), results
        assert f[0].get("/api/v1/teaching-sessions", headers=s["personal"]).status_code in (
            401,
            403,
        )
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(ClassSession)) == (
            1 if results[0] == 200 else 0
        )
