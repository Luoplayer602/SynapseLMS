from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from alembic import command
from app.models import (
    AttendanceSheet,
    BusinessOperation,
    ClassSession,
    Enrollment,
    EnrollmentPeriod,
    StudentScore,
)
from tests.conftest import migration_config
from tests.test_admissions import admissions, approve, payload, submit  # noqa: F401
from tests.test_auth_api import HEADERS, login, seed_user
from tests.test_classrooms import foundation  # noqa: F401
from tests.test_courses import catalog_fixture  # noqa: F401
from tests.test_schedules import schedule  # noqa: F401

BASE = "/api/v1/results"


def components():
    return [
        {
            "code": "listen",
            "name": "Listening",
            "skill": "listening",
            "max_score": "20.00",
            "weight": 4000,
        },
        {
            "code": "speak",
            "name": "Speaking",
            "skill": "speaking",
            "max_score": "10.00",
            "weight": 6000,
        },
    ]


def create_scheme(s, parts=None):
    f = s["f"]
    response = f[0].post(
        BASE + "/schemes",
        headers=f[5],
        json=payload(course_id=f[6]["id"], name="Core skills", components=parts or components()),
    )
    assert response.status_code == 201, response.text
    return response.json()


def gradebook_setup(s):
    f = s["f"]
    request = submit(s)
    approve(s, request)
    scheme = create_scheme(s)
    published = f[0].post(
        BASE + f"/schemes/{scheme['id']}/publish",
        headers=f[5],
        json=payload(version=scheme["version"]),
    )
    assert published.status_code == 200, published.text
    teacher = login(f[0], "schedule-teacher@example.com")
    created = f[0].post(
        BASE + f"/classes/{s['class_id']}/gradebook", headers=teacher, json=payload(version=0)
    )
    assert created.status_code == 201, created.text
    return created.json(), teacher


def test_scheme_weights_roles_and_clone(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    scheme = create_scheme(s, [{**components()[0], "weight": 9000}])
    body = payload(version=scheme["version"])
    rejected = f[0].post(BASE + f"/schemes/{scheme['id']}/publish", headers=f[5], json=body)
    assert rejected.status_code == 409
    teacher = login(f[0], "schedule-teacher@example.com")
    assert (
        f[0]
        .post(
            BASE + "/schemes",
            headers=teacher,
            json=payload(course_id=f[6]["id"], name="Bad", components=components()),
        )
        .status_code
        == 403
    )
    update = f[0].patch(
        BASE + f"/schemes/{scheme['id']}",
        headers=f[5],
        json=payload(
            version=scheme["version"], course_id=f[6]["id"], name="Core", components=components()
        ),
    )
    assert update.status_code == 200, update.text
    new = update.json()
    response = f[0].post(
        BASE + f"/schemes/{scheme['id']}/publish",
        headers=f[5],
        json=payload(version=new["version"]),
    )
    assert response.status_code == 200, response.text
    cloned = f[0].post(
        BASE + f"/schemes/{scheme['id']}/clone",
        headers=f[5],
        json=payload(version=response.json()["version"]),
    )
    assert cloned.status_code == 201, cloned.text
    assert cloned.json()["status"] == "draft"
    assert cloned.json()["revision"] == new["revision"] + 1
    assert (
        f[0]
        .post(
            BASE + f"/schemes/{cloned.json()['id']}/publish",
            headers=f[5],
            json=payload(version=cloned.json()["version"]),
        )
        .status_code
        == 409
    )


def test_gradebook_scores_publication_and_student_privacy(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    book, teacher = gradebook_setup(s)
    class_id = s["class_id"]
    with Session(f[1]) as db:
        enrollment = db.scalar(select(Enrollment).where(Enrollment.class_id == UUID(class_id)))
        start = db.scalar(
            select(EnrollmentPeriod.starts_at).where(
                EnrollmentPeriod.enrollment_id == enrollment.id
            )
        )
        start = start.replace(tzinfo=UTC) if start.tzinfo is None else start
    stamp = (start + timedelta(minutes=1)).isoformat()
    for item in book["items"]:
        response = f[0].post(
            BASE + f"/classes/{class_id}/items/{item['id']}/timing",
            headers=teacher,
            json=payload(version=book["version"], assessed_at=stamp),
        )
        assert response.status_code == 200, response.text
        book = response.json()
    assert f[0].get(BASE + "/mine", headers=s["learner"]).json()["items"] == []
    for item, score in zip(book["items"], ["15.50", "9.00"], strict=True):
        body = payload(
            version=book["version"],
            scores=[
                {
                    "enrollment_id": book["students"][0]["enrollment_id"],
                    "score": score,
                    "comment": "Well done",
                }
            ],
        )
        response = f[0].put(
            BASE + f"/classes/{class_id}/items/{item['id']}", headers=teacher, json=body
        )
        assert response.status_code == 200, response.text
        book = response.json()
        assert (
            f[0]
            .put(BASE + f"/classes/{class_id}/items/{item['id']}", headers=teacher, json=body)
            .json()
            == book
        )
    assert book["students"][0]["final_score"] == 85.0
    assert book["students"][0]["coverage_percent"] == 100.0
    assert book["students"][0]["skills"] == {"listening": 77.5, "speaking": 90.0}
    assert f[0].get(BASE + f"/classes/{class_id}", headers=s["learner"]).status_code == 403
    future = datetime.now(UTC) + timedelta(days=1)
    later = f[0].post(
        BASE + f"/classes/{class_id}/publication",
        headers=teacher,
        json=payload(version=book["version"], publish_at=future.isoformat()),
    )
    assert later.status_code == 200, later.text
    assert f[0].get(BASE + "/mine", headers=s["learner"]).json()["items"] == []
    response = f[0].post(
        BASE + f"/classes/{class_id}/publication",
        headers=teacher,
        json=payload(
            version=later.json()["version"],
            publish_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        ),
    )
    assert response.status_code == 200, response.text
    book = response.json()
    mine = f[0].get(BASE + "/mine", headers=s["learner"])
    assert mine.status_code == 200, mine.text
    assert mine.json()["items"][0]["final_score"] == 85.0
    assert "student_name" not in mine.json()["items"][0]
    assert (
        f[0]
        .post(
            BASE + f"/classes/{class_id}/publication",
            headers=teacher,
            json=payload(version=book["version"], publish_at=future.isoformat()),
        )
        .status_code
        == 409
    )
    assert (
        f[0]
        .post(
            BASE + f"/classes/{class_id}/lock",
            headers=teacher,
            json=payload(version=book["version"], reason="Closed"),
        )
        .status_code
        == 403
    )
    locked = f[0].post(
        BASE + f"/classes/{class_id}/lock",
        headers=f[5],
        json=payload(version=book["version"], reason="Final review"),
    )
    assert locked.status_code == 200, locked.text
    assert (
        f[0]
        .put(
            BASE + f"/classes/{class_id}/items/{book['items'][0]['id']}",
            headers=teacher,
            json=payload(version=locked.json()["version"], scores=[]),
        )
        .status_code
        == 409
    )
    unlocked = f[0].post(
        BASE + f"/classes/{class_id}/unlock",
        headers=f[5],
        json=payload(version=locked.json()["version"], reason="Correct mark"),
    )
    assert unlocked.status_code == 200, unlocked.text
    assert (
        f[0]
        .put(
            BASE + f"/classes/{class_id}/items/{book['items'][0]['id']}",
            headers=teacher,
            json=payload(
                version=unlocked.json()["version"],
                scores=[{"enrollment_id": book["students"][0]["enrollment_id"], "score": "16.00"}],
            ),
        )
        .status_code
        == 422
    )


def test_roster_boundary_and_atomic_invalid_score(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    book, teacher = gradebook_setup(s)
    item = book["items"][0]
    with Session(f[1]) as db:
        enrollment = db.scalar(select(Enrollment).where(Enrollment.class_id == UUID(s["class_id"])))
        start = db.scalar(
            select(EnrollmentPeriod.starts_at).where(
                EnrollmentPeriod.enrollment_id == enrollment.id
            )
        )
        start = start.replace(tzinfo=UTC) if start.tzinfo is None else start
    path = BASE + f"/classes/{s['class_id']}/items/{item['id']}"
    early = f[0].post(
        path + "/timing",
        headers=teacher,
        json=payload(
            version=book["version"], assessed_at=(start - timedelta(seconds=1)).isoformat()
        ),
    )
    assert early.status_code == 200, early.text
    denied = f[0].put(
        path,
        headers=teacher,
        json=payload(
            version=early.json()["version"],
            scores=[{"enrollment_id": str(enrollment.id), "score": "10"}],
        ),
    )
    assert denied.status_code == 409
    timed = f[0].post(
        path + "/timing",
        headers=teacher,
        json=payload(
            version=early.json()["version"], assessed_at=(start + timedelta(seconds=1)).isoformat()
        ),
    )
    assert timed.status_code == 200, timed.text
    invalid = f[0].put(
        path,
        headers=teacher,
        json=payload(
            version=timed.json()["version"],
            scores=[{"enrollment_id": str(enrollment.id), "score": "21.00"}],
        ),
    )
    assert invalid.status_code == 422
    with Session(f[1]) as db:
        assert not db.scalar(
            select(StudentScore.id).where(StudentScore.item_id == UUID(item["id"]))
        )
    assert (
        f[0]
        .put(
            path,
            headers=teacher,
            json=payload(
                version=timed.json()["version"],
                scores=[{"enrollment_id": str(enrollment.id), "score": "10"}],
            ),
        )
        .status_code
        == 200
    )
    assert (
        f[0]
        .post(
            path + "/timing",
            headers=teacher,
            json=payload(
                version=timed.json()["version"] + 1,
                assessed_at=(start + timedelta(minutes=2)).isoformat(),
            ),
        )
        .status_code
        == 409
    )


def test_results_denies_other_teacher_and_manager_score(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    book, _ = gradebook_setup(s)
    seed_user(f[1], f[2], role="teacher", email="outside-results@example.com")
    outsider = login(f[0], "outside-results@example.com")
    assert f[0].get(BASE + f"/classes/{s['class_id']}", headers=outsider).status_code in {403, 404}
    assert (
        f[0]
        .post(
            BASE + f"/classes/{s['class_id']}/items/{book['items'][0]['id']}/timing",
            headers=f[5],
            json=payload(version=book["version"], assessed_at=datetime.now(UTC).isoformat()),
        )
        .status_code
        == 403
    )


def test_missing_mark_stale_version_and_published_correction(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    book, teacher = gradebook_setup(s)
    class_id = s["class_id"]
    with Session(f[1]) as db:
        enrollment = db.scalar(select(Enrollment).where(Enrollment.class_id == UUID(class_id)))
        start = db.scalar(
            select(EnrollmentPeriod.starts_at).where(
                EnrollmentPeriod.enrollment_id == enrollment.id
            )
        )
        start = start.replace(tzinfo=UTC) if start.tzinfo is None else start
    for item in book["items"]:
        response = f[0].post(
            BASE + f"/classes/{class_id}/items/{item['id']}/timing",
            headers=teacher,
            json=payload(
                version=book["version"], assessed_at=(start + timedelta(minutes=1)).isoformat()
            ),
        )
        assert response.status_code == 200, response.text
        book = response.json()
    first = book["items"][0]
    path = BASE + f"/classes/{class_id}/items/{first['id']}"
    record = {"enrollment_id": str(enrollment.id), "score": "15.50", "comment": "Good"}
    body = payload(version=book["version"], scores=[record])
    response = f[0].put(path, headers=teacher, json=body)
    assert response.status_code == 200, response.text
    book = response.json()
    assert book["students"][0]["final_score"] is None
    assert book["students"][0]["marks"][0]["name"] == "Listening"
    assert (
        f[0]
        .put(path, headers=teacher, json=payload(version=body["version"], scores=[record]))
        .status_code
        == 409
    )
    assert (
        f[0]
        .put(path, headers=teacher, json={**body, "scores": [{**record, "score": "15.00"}]})
        .status_code
        == 409
    )
    published = f[0].post(
        BASE + f"/classes/{class_id}/publication",
        headers=teacher,
        json=payload(
            version=book["version"],
            publish_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        ),
    )
    assert published.status_code == 200, published.text
    book = published.json()
    corrected = f[0].put(
        path,
        headers=teacher,
        json=payload(
            version=book["version"],
            reason="Transcription error",
            scores=[{**record, "score": "16.25"}],
        ),
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["students"][0]["marks"][0]["score"] == 16.25
    assert (
        f[0].get(BASE + "/mine", headers=s["learner"]).json()["items"][0]["marks"][0]["score"]
        == 16.25
    )
    with Session(f[1]) as db:
        history = list(
            db.scalars(
                select(BusinessOperation)
                .where(
                    BusinessOperation.action == "results.scores.save",
                    BusinessOperation.target_id == UUID(first["id"]),
                )
                .order_by(BusinessOperation.created_at)
            )
        )
        assert history[-1].result["reason"] == "Transcription error"
        assert history[-1].before["students"][0]["marks"][0]["score"] == 15.5
        assert history[-1].result["students"][0]["marks"][0]["score"] == 16.25


def test_gradebook_creation_replay_and_duplicate(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    book, teacher = gradebook_setup(s)
    class_id = s["class_id"]
    assert (
        f[0]
        .post(BASE + f"/classes/{class_id}/gradebook", headers=teacher, json=payload(version=0))
        .status_code
        == 409
    )
    assert (
        f[0].get(BASE + f"/classes/{class_id}", headers=f[5]).json()["scheme_snapshot"]["name"]
        == "Core skills"
    )
    assert book["version"] == 1


def test_migration_refuses_downgrade_with_gradebook(admissions):  # noqa: F811
    s = admissions
    gradebook_setup(s)
    with s["f"][1].begin() as connection:
        with pytest.raises(RuntimeError, match="learning result"):
            command.downgrade(migration_config(connection), "20260928_0014")


def test_finalized_attendance_is_reference_only(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    book, teacher = gradebook_setup(s)
    with Session(f[1]) as db:
        enrollment = db.scalar(select(Enrollment).where(Enrollment.class_id == UUID(s["class_id"])))
        session = db.scalar(
            select(ClassSession).where(ClassSession.class_id == UUID(s["class_id"]))
        )
        db.add(
            AttendanceSheet(
                organization_id=enrollment.organization_id,
                class_id=enrollment.class_id,
                session_id=session.id,
                records=[
                    {"student_id": str(enrollment.student_id), "status": "present", "note": ""}
                ],
                finalized=True,
            )
        )
        db.commit()
    response = f[0].get(BASE + f"/classes/{s['class_id']}", headers=teacher)
    assert response.status_code == 200, response.text
    student = response.json()["students"][0]
    assert student["attendance"]["attendance_percent"] == 100
    assert student["final_score"] is None
    assert student["marks"] == []
    assert book["version"] == response.json()["version"]


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_gradebook_create_is_singleton(admissions, same_key):  # noqa: F811
    s, f = admissions, admissions["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("row locks require PostgreSQL")
    scheme = create_scheme(s)
    assert (
        f[0]
        .post(
            BASE + f"/schemes/{scheme['id']}/publish",
            headers=f[5],
            json=payload(version=scheme["version"]),
        )
        .status_code
        == 200
    )
    teacher = login(f[0], "schedule-teacher@example.com")
    barrier = Barrier(2)
    shared = payload(version=0)

    def create(_):
        with TestClient(f[4], headers=HEADERS) as client:
            barrier.wait()
            return client.post(
                BASE + f"/classes/{s['class_id']}/gradebook",
                headers=teacher,
                json=shared if same_key else payload(version=0),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, range(2)))
    assert sorted(row.status_code for row in responses) == ([201, 201] if same_key else [201, 409])
    assert f[0].get(BASE + f"/classes/{s['class_id']}", headers=teacher).status_code == 200
