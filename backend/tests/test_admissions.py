from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alembic import command
from app.models import (
    AdmissionRequest,
    DiscountCode,
    Enrollment,
    Invoice,
    LearningClass,
    Payment,
    StudentIdentity,
    StudentProficiency,
    StudentProfile,
)
from tests.conftest import migration_config
from tests.test_auth_api import HEADERS, login, seed_user
from tests.test_classrooms import foundation  # noqa: F401
from tests.test_courses import catalog_fixture  # noqa: F401
from tests.test_schedules import confirm, schedule  # noqa: F401

BASE = "/api/v1/admissions"


def test_attendance_payload_limit_matches_class_capacity():
    from pydantic import ValidationError

    from app.api.admission_schemas import AttendanceInput

    record = {"student_id": str(uuid4()), "status": "present"}
    # Actual uniqueness/roster validation remains in the transaction handler.
    data = {"request_key": str(uuid4()), "version": 0, "finalized": False}
    assert len(AttendanceInput(**data, records=[record] * 501).records) == 501
    with pytest.raises(ValidationError):
        AttendanceInput(**data, records=[record] * 10001)


def payload(**values):
    return {"request_key": str(uuid4()), **values}


def add_student(s, email="admission-student@example.com"):
    f = s["f"]
    uid, _ = seed_user(f[1], f[2], role="student", email=email)
    with Session(f[1]) as db:
        identity = StudentIdentity(user_id=UUID(uid), code="ST-" + uuid4().hex[:10])
        db.add(identity)
        db.flush()
        student = StudentProfile(
            organization_id=UUID(f[2]),
            identity_id=identity.id,
            full_name="Admission student",
            date_of_birth=date(2000, 1, 1),
            phone="0900000000",
        )
        db.add(student)
        db.flush()
        course = f[6]
        if course.get("entry_level_id"):
            db.add(
                StudentProficiency(
                    organization_id=UUID(f[2]),
                    student_profile_id=student.id,
                    language_id=UUID(course["language_id"]),
                    framework_id=UUID(course["framework_id"]),
                    verified_level_id=UUID(course["entry_level_id"]),
                    verified_at=datetime(2026, 9, 1, tzinfo=UTC),
                    verified_by=UUID(uid),
                )
            )
        db.commit()
        sid = str(student.id)
    return sid, login(f[0], email)


@pytest.fixture
def admissions(schedule, monkeypatch):  # noqa: F811
    s = schedule
    for module in [
        "app.services.admissions",
        "app.api.routes.admissions",
        "app.api.routes.attendance",
        "app.api.routes.session_operations",
    ]:
        monkeypatch.setattr(module + ".now", lambda: datetime(2026, 9, 27, tzinfo=UTC))
    response, _ = confirm(s)
    assert response.status_code == 200, response.text
    s["session"] = response.json()["sessions"][0]
    f = s["f"]
    assert (
        f[0]
        .put(
            BASE + "/fees/" + f[6]["id"],
            headers=f[5],
            json=payload(
                version=0,
                amount=1000,
                installments=[{"days": 0, "percent": 50}, {"days": 30, "percent": 50}],
            ),
        )
        .status_code
        == 200
    )
    assert (
        f[0]
        .put(
            BASE + "/openings/" + s["class_id"], headers=f[5], json=payload(version=0, enabled=True)
        )
        .status_code
        == 200
    )
    s["student"], s["learner"] = add_student(s)
    return s


def submit(s, **values):
    f = s["f"]
    response = f[0].post(
        BASE + "/requests",
        headers=f[5],
        json=payload(
            student_id=s["student"],
            course_id=f[6]["id"],
            availability=[{"weekday": 0, "starts_at": "17:00", "ends_at": "22:00"}],
            **values,
        ),
    )
    assert response.status_code == 200, response.text
    return response.json()


def approve(s, row):
    f = s["f"]
    body = payload(version=row["version"], action="approve")
    response = f[0].post(BASE + "/requests/" + row["id"] + "/decision", headers=f[5], json=body)
    assert response.status_code == 200, response.text
    return response.json(), body


def test_end_to_end_finance_placement_receipt_notifications(admissions):
    s, f = admissions, admissions["f"]
    row = submit(s)
    result, decision = approve(s, row)
    assert result["status"] == "placed"
    assert (
        f[0].post(BASE + "/requests/" + row["id"] + "/decision", headers=f[5], json=decision).json()
        == result
    )
    invoice = f[0].get(BASE + "/invoices", headers=s["learner"]).json()["items"][0]
    assert invoice["total"] == invoice["remaining"] == 1000
    assert [i["amount"] for i in invoice["installments"]] == [500, 500]
    path = BASE + "/invoices/" + invoice["id"]
    body = payload(amount=600, method="cash", reference="paper 123")
    paid = f[0].post(path + "/payments", headers=f[5], json=body)
    assert paid.status_code == 200, paid.text
    assert paid.json()["invoice"]["remaining"] == 400
    assert f[0].post(path + "/payments", headers=f[5], json=body).json() == paid.json()
    assert (
        f[0]
        .post(path + "/payments", headers=f[5], json=payload(amount=401, method="cash"))
        .status_code
        == 409
    )
    assert (
        f[0]
        .post(path + "/payments", headers=s["learner"], json=payload(amount=1, method="cash"))
        .status_code
        == 403
    )
    detail = f[0].get(path, headers=s["learner"]).json()
    assert len(detail["payments"]) == 1
    reverse = payload(reason="Wrong receipt entered")
    revpath = BASE + "/payments/" + paid.json()["payment_id"] + "/reverse"
    assert f[0].post(revpath, headers=f[5], json=reverse).json()["remaining"] == 1000
    assert f[0].post(revpath, headers=f[5], json=reverse).status_code == 200
    assert f[0].get(BASE + "/my-sessions", headers=s["learner"]).json()["total"] == 1
    inbox = f[0].get("/api/v1/notifications", headers=s["learner"]).json()
    assert inbox["unread"] == 3
    assert (
        f[0]
        .post("/api/v1/notifications/" + inbox["items"][0]["id"] + "/read", headers=f[5])
        .status_code
        == 404
    )
    assert (
        f[0]
        .post("/api/v1/notifications/" + inbox["items"][0]["id"] + "/read", headers=s["learner"])
        .status_code
        == 200
    )
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(Enrollment)) == 1
        assert db.scalar(select(func.count()).select_from(Payment)) == 1


def test_missing_availability_manual_queue_rejection_and_privacy(admissions):
    s, f = admissions, admissions["f"]
    req = (
        f[0]
        .post(BASE + "/requests", headers=s["learner"], json=payload(course_id=f[6]["id"]))
        .json()
    )
    result, _ = approve(s, req)
    assert result["status"] == "waiting"
    path = BASE + "/requests/" + result["id"]
    choices = f[0].get(path + "/candidates", headers=f[5]).json()["items"]
    assert "ADMISSION_AVAILABILITY_REVIEW" in choices[0]["warnings"]
    assert (
        f[0]
        .post(
            path + "/placement",
            headers=f[5],
            json=payload(version=2, class_id=s["class_id"], reason="Confirmed available by phone"),
        )
        .json()["status"]
        == "placed"
    )
    _, outsider = add_student(s, "other-student@example.com")
    assert f[0].get(BASE + "/requests", headers=outsider).json()["total"] == 0
    iid = f[0].get(BASE + "/invoices", headers=f[5]).json()["items"][0]["id"]
    assert f[0].get(BASE + "/invoices/" + iid, headers=outsider).status_code == 404
    assert f[0].get(BASE + "/invoices", headers=s["personal"]).status_code == 403


def test_discount_snapshot_and_approval_rollback(admissions):
    s, f = admissions, admissions["f"]
    discount = payload(
        code="SAVE10",
        kind="percent",
        value=10,
        starts_on="2026-01-01",
        ends_on="2026-12-31",
        max_uses=1,
    )
    assert f[0].post(BASE + "/discounts", headers=f[5], json=discount).status_code == 200
    row = submit(s, discount_code="save10")
    approve(s, row)
    invoice = f[0].get(BASE + "/invoices", headers=f[5]).json()["items"][0]
    assert invoice["discount"] == 100 and invoice["total"] == 900
    assert (
        f[0]
        .put(
            BASE + "/fees/" + f[6]["id"],
            headers=f[5],
            json=payload(version=1, amount=2000, installments=[{"days": 0, "percent": 100}]),
        )
        .status_code
        == 200
    )
    assert f[0].get(BASE + "/invoices/" + invoice["id"], headers=f[5]).json()["total"] == 900
    s["student"], _ = add_student(s, "discount-second@example.com")
    second = submit(s, discount_code="SAVE10")
    response = f[0].post(
        BASE + "/requests/" + second["id"] + "/decision",
        headers=f[5],
        json=payload(version=1, action="approve"),
    )
    assert response.status_code == 409
    with Session(f[1]) as db:
        assert db.get(AdmissionRequest, UUID(second["id"])).status == "submitted"
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(DiscountCode.used)) == 1


def test_attendance_draft_finalize_revision_and_owner(admissions, monkeypatch):
    s, f = admissions, admissions["f"]
    approve(s, submit(s))
    path = "/api/v1/attendance/sessions/" + s["session"]["id"]
    data = payload(
        version=0,
        finalized=False,
        records=[{"student_id": s["student"], "status": "unmarked", "note": ""}],
    )
    assert f[0].put(path, headers=s["personal"], json=data).status_code == 409
    monkeypatch.setattr(
        "app.api.routes.attendance.now", lambda: datetime(2026, 10, 5, 12, tzinfo=UTC)
    )
    assert f[0].put(path, headers=f[5], json=data).status_code == 403
    saved = f[0].put(path, headers=s["personal"], json=data)
    assert saved.status_code == 200, saved.text
    assert (
        f[0].get("/api/v1/attendance/mine", headers=s["learner"]).json()["counts"]["unmarked"] == 1
    )
    final = payload(
        version=1,
        finalized=True,
        records=[{"student_id": s["student"], "status": "late", "note": "Bus delay"}],
    )
    assert f[0].put(path, headers=s["personal"], json=final).status_code == 200
    assert (
        f[0]
        .put(
            path,
            headers=s["personal"],
            json=payload(version=2, finalized=True, records=final["records"]),
        )
        .status_code
        == 422
    )
    assert (
        f[0]
        .put(
            path,
            headers=s["personal"],
            json=payload(version=1, finalized=True, records=final["records"], reason="Correction"),
        )
        .status_code
        == 409
    )
    mine = f[0].get("/api/v1/attendance/mine", headers=s["learner"]).json()
    assert mine["counts"]["late"] == 1 and mine["attendance_percent"] == 100
    assert f[0].get(path + "/history", headers=s["personal"]).json()["total"] == 2


def test_schema_matches_and_empty_migration_roundtrip(migrated_engine):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db.base import Base

    with migrated_engine.begin() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(migration_config(connection), "20260926_0012")
        command.upgrade(migration_config(connection), "head")


def test_concurrent_last_seat_and_receipt(admissions):
    s, f = admissions, admissions["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("row locks require PostgreSQL")
    one = submit(s)
    s["student"], _ = add_student(s, "seat-second@example.com")
    two = submit(s)
    with Session(f[1]) as db:
        db.get(LearningClass, UUID(s["class_id"])).capacity = 1
        db.commit()
    barrier = Barrier(2)

    def decide(row):
        with TestClient(f[4], headers=HEADERS) as client:
            barrier.wait()
            return client.post(
                BASE + "/requests/" + row["id"] + "/decision",
                headers=f[5],
                json=payload(version=1, action="approve"),
            )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(decide, [one, two]))
    assert sorted(r.json()["status"] for r in results) == ["placed", "waiting"]
    invoice = f[0].get(BASE + "/invoices", headers=f[5]).json()["items"][0]
    barrier = Barrier(2)

    def collect(_):
        with TestClient(f[4], headers=HEADERS) as client:
            barrier.wait()
            return client.post(
                BASE + "/invoices/" + invoice["id"] + "/payments",
                headers=f[5],
                json=payload(amount=1000, method="cash"),
            )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(collect, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]


@pytest.mark.parametrize(
    "case",
    [
        "missing_profile",
        "duplicate",
        "wrong_tenant",
        "wrong_student",
        "no_reason",
        "key_reused",
        "stale",
        "archived_teacher",
    ],
)
def test_rejected_requests_leave_financial_state_unchanged(admissions, case):
    s, f = admissions, admissions["f"]
    client = f[0]
    row = submit(s)
    if case == "missing_profile":
        with Session(f[1]) as db:
            db.get(StudentProfile, UUID(s["student"])).phone = None
            db.commit()
        response = client.post(
            BASE + "/requests/" + row["id"] + "/decision",
            headers=f[5],
            json=payload(version=1, action="approve"),
        )
        assert response.status_code == 422
    elif case == "duplicate":
        response = client.post(
            BASE + "/requests", headers=s["learner"], json=payload(course_id=f[6]["id"])
        )
        assert response.status_code == 409
    elif case == "wrong_tenant":
        seed_user(f[1], f[3], email="foreign-admission@example.com")
        response = client.post(
            BASE + "/requests/" + row["id"] + "/decision",
            headers=login(client, "foreign-admission@example.com"),
            json=payload(version=1, action="approve"),
        )
        assert response.status_code == 404
    elif case == "wrong_student":
        sid, _ = add_student(s, "another-owner@example.com")
        response = client.post(
            BASE + "/requests",
            headers=s["learner"],
            json=payload(course_id=f[6]["id"], student_id=sid),
        )
        assert response.status_code == 403
    elif case == "no_reason":
        response = client.post(
            BASE + "/requests/" + row["id"] + "/decision",
            headers=f[5],
            json=payload(version=1, action="reject", reason=""),
        )
        assert response.status_code == 422
    elif case == "key_reused":
        data = payload(version=1, action="reject", reason="Not eligible yet")
        path = BASE + "/requests/" + row["id"] + "/decision"
        assert client.post(path, headers=f[5], json=data).status_code == 200
        assert (
            client.post(path, headers=f[5], json={**data, "action": "approve"}).status_code == 409
        )
    elif case == "stale":
        assert (
            client.post(
                BASE + "/requests/" + row["id"] + "/decision",
                headers=f[5],
                json=payload(version=2, action="approve"),
            ).status_code
            == 409
        )
    else:
        from app.models import TeacherProfile

        with Session(f[1]) as db:
            db.get(TeacherProfile, UUID(s["teacher"])).archived_at = datetime(
                2026, 9, 27, tzinfo=UTC
            )
            db.commit()
        result, _ = approve(s, row)
        assert result["status"] == "waiting"
        return
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
        assert db.scalar(select(func.count()).select_from(Enrollment)) == 0


def test_debt_policy_rechecks_approval_and_settings_permission(admissions):
    s, f = admissions, admissions["f"]
    # A second published course makes this a real new request, not a duplicate.
    course = (
        f[0].post("/api/v1/courses", headers=f[5], json={**f[10], "code": "NEXT-COURSE"}).json()
    )
    assert (
        f[0]
        .post(
            "/api/v1/courses/" + course["id"] + "/state",
            headers=f[5],
            json={"version": 1, "status": "published", "reason": "Publish next"},
        )
        .status_code
        == 200
    )
    assert (
        f[0]
        .put(
            BASE + "/fees/" + course["id"],
            headers=f[5],
            json=payload(version=0, amount=1000, installments=[{"days": 30, "percent": 100}]),
        )
        .status_code
        == 200
    )
    approve(s, submit(s))
    second = (
        f[0]
        .post(BASE + "/requests", headers=s["learner"], json=payload(course_id=course["id"]))
        .json()
    )
    assert (
        f[0]
        .put(BASE + "/settings", headers=s["learner"], json=payload(version=0, block_debt=True))
        .status_code
        == 403
    )
    assert (
        f[0]
        .put(BASE + "/settings", headers=f[5], json=payload(version=0, block_debt=True))
        .status_code
        == 200
    )
    response = f[0].post(
        BASE + "/requests/" + second["id"] + "/decision",
        headers=f[5],
        json=payload(version=1, action="approve"),
    )
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "ADMISSION_DEBT_BLOCKED"
    )
    assert f[0].post(BASE + "/settings", headers=f[5], json={}).status_code == 405
    invoice = f[0].get(BASE + "/invoices", headers=f[5]).json()["items"][0]
    assert (
        f[0]
        .post(
            BASE + "/invoices/" + invoice["id"] + "/payments",
            headers=f[5],
            json=payload(amount=1000, method="transfer"),
        )
        .status_code
        == 200
    )
    assert approve(s, second)[0]["status"] == "waiting"


def test_student_archive_and_cancel_notification_are_consistent(admissions):
    s, f = admissions, admissions["f"]
    approve(s, submit(s))
    response = f[0].post(
        "/api/v1/students/" + s["student"] + "/archive",
        headers=f[5],
        json={"version": 1, "archived": True, "reason": "Attempt archive"},
    )
    assert response.status_code == 409
    path = "/api/v1/class-sessions/" + s["session"]["id"] + "/operations"
    body = payload(version=1, action="cancel", reason="Cancel session")
    assert f[0].post(path, headers=f[5], json=body).status_code == 200
    assert f[0].post(path, headers=f[5], json=body).status_code == 200
    assert f[0].get(BASE + "/my-sessions", headers=s["learner"]).json()["total"] == 0
    notices = f[0].get("/api/v1/notifications", headers=s["learner"]).json()["items"]
    assert sum(x["kind"] == "session.cancel" for x in notices) == 1
    assert all("reason" not in x for x in notices)
    cancelled = next(x for x in notices if x["kind"] == "session.cancel")
    assert cancelled["session"]["class_name"] == s["session"]["class_name"]
    assert set(cancelled["session"]) == {
        "class_name",
        "starts_at",
        "ends_at",
        "timezone",
        "room_name",
    }


def test_roster_and_rescheduling_protect_student_reservations(admissions):
    from app.models import ClassSession

    s, f = admissions, admissions["f"]
    first = submit(s)
    approve(s, first)
    roster_path = BASE + "/classes/" + s["class_id"] + "/roster"
    assert f[0].get(roster_path, headers=f[5]).json()["total"] == 1
    assert f[0].get(roster_path, headers=s["learner"]).status_code == 403
    # Independent course/class fixture: the same student has a different reserved time.
    course = (
        f[0].post("/api/v1/courses", headers=f[5], json={**f[10], "code": "OTHER-ENROLLED"}).json()
    )
    assert (
        f[0]
        .post(
            "/api/v1/courses/" + course["id"] + "/state",
            headers=f[5],
            json={"version": 1, "status": "published", "reason": "Fixture publish"},
        )
        .status_code
        == 200
    )
    cls = (
        f[0]
        .post(
            "/api/v1/classes",
            headers=f[5],
            json={**f[9], "course_id": course["id"], "code": "OTHER-STUDENT-CLASS"},
        )
        .json()
    )
    with Session(f[1]) as db:
        req = AdmissionRequest(
            organization_id=UUID(f[2]),
            student_id=UUID(s["student"]),
            course_id=UUID(course["id"]),
            availability=[],
            status="placed",
        )
        db.add(req)
        db.flush()
        db.add(
            Enrollment(
                organization_id=UUID(f[2]),
                request_id=req.id,
                student_id=req.student_id,
                class_id=UUID(cls["id"]),
                effective_at=datetime(2026, 9, 27, tzinfo=UTC),
            )
        )
        db.add(
            ClassSession(
                organization_id=UUID(f[2]),
                class_id=UUID(cls["id"]),
                branch_id=UUID(f[7]["id"]),
                room_id=UUID(f[8]["id"]),
                starts_at=datetime(2026, 10, 5, 13, tzinfo=UTC),
                ends_at=datetime(2026, 10, 5, 14, tzinfo=UTC),
                timezone="Asia/Ho_Chi_Minh",
                capacity=15,
                format="offline",
            )
        )
        db.commit()
    path = "/api/v1/class-sessions/" + s["session"]["id"]
    body = payload(
        version=1,
        action="reschedule",
        reason="Move requested",
        day="2026-10-05",
        starts_at="20:00",
        ends_at="21:00",
        room_id=f[8]["id"],
    )
    preview = f[0].post(path + "/preview", headers=f[5], json=body).json()
    assert "ADMISSION_STUDENT_CONFLICT" in preview["after"]["issues"]
    assert f[0].post(path + "/operations", headers=f[5], json=body).status_code == 409
    assert f[0].get(path, headers=f[5]).json()["session"]["version"] == 1


@pytest.mark.parametrize(
    "case", ["fractional", "negative", "too_large", "duplicate_student", "finalize_unmarked"]
)
def test_invalid_money_and_attendance_payloads(admissions, monkeypatch, case):
    s, f = admissions, admissions["f"]
    approve(s, submit(s))
    if case in ["fractional", "negative", "too_large"]:
        invoice = f[0].get(BASE + "/invoices", headers=f[5]).json()["items"][0]
        amount = {"fractional": 1.5, "negative": -1, "too_large": 1001}[case]
        response = f[0].post(
            BASE + "/invoices/" + invoice["id"] + "/payments",
            headers=f[5],
            json=payload(amount=amount, method="cash"),
        )
        assert response.status_code == (409 if case == "too_large" else 422)
        return
    monkeypatch.setattr(
        "app.api.routes.attendance.now", lambda: datetime(2026, 10, 5, 12, tzinfo=UTC)
    )
    record = {"student_id": s["student"], "status": "unmarked"}
    records = [record, record] if case == "duplicate_student" else [record]
    response = f[0].put(
        "/api/v1/attendance/sessions/" + s["session"]["id"],
        headers=s["personal"],
        json=payload(version=0, finalized=True, records=records),
    )
    assert response.status_code == (409 if case == "duplicate_student" else 422)


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_approval_creates_one_invoice(admissions, same_key):
    s, f = admissions, admissions["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("row locks require PostgreSQL")
    row = submit(s)
    barrier = Barrier(2)
    shared = payload(version=1, action="approve")

    def apply(_):
        with TestClient(f[4], headers=HEADERS) as client:
            barrier.wait()
            return client.post(
                BASE + "/requests/" + row["id"] + "/decision",
                headers=f[5],
                json=shared if same_key else payload(version=1, action="approve"),
            )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(apply, range(2)))
    assert sorted(r.status_code for r in results) == ([200, 200] if same_key else [200, 409])
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(Enrollment)) == 1


def test_populated_financial_migration_refuses_loss(admissions):
    s, f = admissions, admissions["f"]
    approve(s, submit(s))
    with f[1].begin() as connection:
        with pytest.raises(RuntimeError, match="Refusing"):
            command.downgrade(migration_config(connection), "20260926_0012")
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
