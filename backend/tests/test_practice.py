from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PracticeAttempt, PracticeDay, PracticeQuestion, StudentProfile, User
from app.services import practice as practice_service
from tests.test_admissions import admissions, approve, submit  # noqa: F401
from tests.test_classrooms import foundation  # noqa: F401
from tests.test_courses import catalog_fixture  # noqa: F401
from tests.test_schedules import schedule  # noqa: F401

BASE = "/api/v1/practice"


def test_closed_answer_submission_is_idempotent_and_theme_locked(admissions, monkeypatch):  # noqa: F811
    s, f = admissions, admissions["f"]
    request = submit(s)
    placed, _ = approve(s, request)
    assert placed["status"] == "placed"
    monkeypatch.setattr("app.services.practice.now", lambda: datetime(2026, 9, 27, 13, tzinfo=UTC))
    body = {
        "course_id": f[6]["id"],
        "stem": "Choose the correct word in this sample.",
        "options": ["one", "two", "three"],
        "correct_index": 1,
        "explanation": "Two is correct.",
    }
    created = f[0].post(BASE + "/questions", headers=f[5], json=body)
    assert created.status_code == 200, created.text
    qid = created.json()["id"]
    assert f[0].post(BASE + f"/questions/{qid}/publish", headers=f[5]).status_code == 200
    visible = f[0].get(BASE + "/mine", headers=s["learner"])
    assert visible.status_code == 200, visible.text
    assert any(x["id"] == qid for x in visible.json()["items"])
    assert "correct_index" not in visible.text
    attempt = {"request_key": str(uuid4()), "answer_index": 0}
    first = f[0].post(BASE + f"/questions/{qid}/submit", headers=s["learner"], json=attempt)
    assert first.status_code == 200, first.text
    assert first.json()["correct"] is False
    again = f[0].post(BASE + f"/questions/{qid}/submit", headers=s["learner"], json=attempt)
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert (
        f[0]
        .post(
            BASE + f"/questions/{qid}/submit",
            headers=s["learner"],
            json={"request_key": str(uuid4()), "answer_index": 1},
        )
        .status_code
        == 409
    )
    rewards = f[0].get(BASE + "/rewards/mine", headers=s["learner"])
    assert rewards.status_code == 200 and rewards.json()["current_streak"] == 1
    assert (
        f[0]
        .put(BASE + "/rewards/theme", headers=s["learner"], json={"theme": "neo-pop"})
        .status_code
        == 403
    )


def test_parallel_submit_only_creates_one_attempt(admissions, monkeypatch):  # noqa: F811
    s, f = admissions, admissions["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("row lock concurrency is verified on PostgreSQL")
    approve(s, submit(s))
    monkeypatch.setattr("app.services.practice.now", lambda: datetime(2026, 9, 27, 13, tzinfo=UTC))
    created = f[0].post(BASE + "/questions", headers=f[5], json={
        "course_id": f[6]["id"], "stem": "Choose the correct sample word today.",
        "options": ["one", "two"], "correct_index": 1,
    })
    assert created.status_code == 200, created.text
    qid = created.json()["id"]
    assert f[0].post(BASE + f"/questions/{qid}/publish", headers=f[5]).status_code == 200
    barrier = Barrier(2)

    def worker():
        barrier.wait(timeout=10)
        return f[0].post(BASE + f"/questions/{qid}/submit", headers=s["learner"],
                         json={"request_key": str(uuid4()), "answer_index": 1}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda _: worker(), range(2)))
    assert sorted(codes) == [200, 409]
    with Session(f[1]) as db:
        assert db.scalar(select(func.count()).select_from(PracticeAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(PracticeDay)) == 1


def test_streak_milestones_and_permanent_grants(admissions, monkeypatch):  # noqa: F811
    s, f = admissions, admissions["f"]
    approve(s, submit(s))
    start = datetime(2026, 9, 27, 13, tzinfo=UTC)
    for offset in range(14):
        instant = start + timedelta(days=offset)
        monkeypatch.setattr("app.services.practice.now", lambda instant=instant: instant)
        with Session(f[1], expire_on_commit=False) as db:
            profile = db.get(StudentProfile, UUID(s["student"]))
            creator = db.scalar(select(User.id).limit(1))
            question = PracticeQuestion(organization_id=UUID(f[2]), course_id=UUID(f[6]["id"]),
                                        creator_id=creator, locale="vi", status="published",
                                        stem=f"Select the correct word for day {offset}.",
                                        options=["one", "two"], correct_index=1,
                                        explanation="Two is correct.", source_refs=[])
            db.add(question)
            db.flush()
            tenant = SimpleNamespace(organization=SimpleNamespace(id=UUID(f[2])))
            completed = practice_service.submit(db, tenant, profile, question, uuid4(), 0)
            assert completed["correct"] is False
        if offset + 1 in {3, 7, 14}:
            rewards = f[0].get(BASE + "/rewards/mine", headers=s["learner"]).json()
            assert rewards["current_streak"] == offset + 1
    rewards = f[0].get(BASE + "/rewards/mine", headers=s["learner"]).json()
    assert set(rewards["unlocked"]) == {"synapse-soft", "neo-pop", "clay-garden", "liquid-glass"}
    assert f[0].put(BASE + "/rewards/theme", headers=s["learner"],
                    json={"theme": "liquid-glass"}).status_code == 200
    monkeypatch.setattr("app.services.practice.now", lambda: start + timedelta(days=16))
    after = f[0].get(BASE + "/rewards/mine", headers=s["learner"]).json()
    assert after["current_streak"] == 0
    assert after["selected"] == "liquid-glass"
    assert after["best_streak"] == 14
