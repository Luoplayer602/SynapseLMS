from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.ai import progress
from tests.test_admissions import admissions, approve, submit  # noqa: F401
from tests.test_auth_api import login, seed_user
from tests.test_classrooms import foundation  # noqa: F401
from tests.test_courses import catalog_fixture  # noqa: F401
from tests.test_schedules import schedule  # noqa: F401


def test_summary_rejects_citation_outside_source(monkeypatch):
    fact = {"id": "score:published", "label": "Điểm", "value": "80%", "href": "/my-results"}

    def rogue(_db, _tenant, _task, _locale, _payload, validator):
        return validator({"highlight_ids": ["score:secret"], "next_step": "keep_going"})

    monkeypatch.setattr(progress, "invoke", rogue)
    tenant = SimpleNamespace(
        organization=SimpleNamespace(id=uuid4()),
        actor=SimpleNamespace(user=SimpleNamespace(id=uuid4())),
    )
    db = SimpleNamespace(scalar=lambda *_: None)
    with pytest.raises(ValueError):
        progress._summary(db, tenant, "vi", [fact], "student")


def test_progress_cache_changes_with_published_facts(admissions, monkeypatch):  # noqa: F811
    from app.core.config import get_settings

    s, f = admissions, admissions["f"]
    placed, _ = approve(s, submit(s))
    assert placed["status"] == "placed"
    seed_user(f[1], f[2], root=True, email="progress-root@example.com")
    root = login(f[0], "progress-root@example.com")
    monkeypatch.setattr(get_settings(), "ai_local_hosts", ["192.168.1.10"])
    provider = f[0].post(
        "/api/v1/ai/providers",
        headers=root,
        json={
            "code": "fake-local",
            "name": "Fake local",
            "kind": "ollama",
            "base_url": "http://192.168.1.10:11434",
            "model_id": "fixture",
            "allowed_tasks": ["progress_summary"],
            "enabled": True,
        },
    )
    assert provider.status_code == 200, provider.text
    prompt = (
        f[0]
        .post(
            "/api/v1/ai/prompts",
            headers=root,
            json={
                "task": "progress_summary",
                "locale": "vi",
                "body": "Chọn các nguồn đã được công bố trong {task}, trình bày bằng {locale}.",
            },
        )
        .json()["id"]
    )
    assert f[0].post(f"/api/v1/ai/prompts/{prompt}/test", headers=root).status_code == 200
    assert (
        f[0]
        .post(f"/api/v1/ai/prompts/{prompt}/publish", headers=root, json={"reason": "Ready"})
        .status_code
        == 200
    )
    assert (
        f[0]
        .put(
            "/api/v1/ai/routes",
            headers=root,
            json={
                "task": "progress_summary",
                "provider_ids": [provider.json()["id"]],
            },
        )
        .status_code
        == 200
    )
    assert (
        f[0]
        .put(
            "/api/v1/ai/tenant-tasks",
            headers=f[5],
            json={
                "task": "progress_summary",
                "enabled": True,
            },
        )
        .status_code
        == 200
    )
    call_count = 0

    def fake_complete(_provider, _system, payload, _path):
        nonlocal call_count
        call_count += 1
        return {"highlight_ids": [payload["facts"][0]["id"]], "next_step": "practice_more"}

    monkeypatch.setattr("app.services.ai.providers.complete", fake_complete)
    for i in range(2):
        question = (
            f[0]
            .post(
                "/api/v1/practice/questions",
                headers=f[5],
                json={
                    "course_id": f[6]["id"],
                    "stem": f"Select the correct word for item {i}.",
                    "options": ["one", "two"],
                    "correct_index": 1,
                },
            )
            .json()["id"]
        )
        assert (
            f[0].post(f"/api/v1/practice/questions/{question}/publish", headers=f[5]).status_code
            == 200
        )
        monkeypatch.setattr(
            "app.services.practice.now", lambda: datetime(2026, 9, 27, 13, tzinfo=UTC)
        )
        assert (
            f[0]
            .post(
                f"/api/v1/practice/questions/{question}/submit",
                headers=s["learner"],
                json={"request_key": str(uuid4()), "answer_index": 0},
            )
            .status_code
            == 200
        )
        response = f[0].get("/api/v1/ai/progress/mine", headers=s["learner"])
        assert response.status_code == 200, response.text
        assert response.json()["mode"] == "ai"
        assert response.json()["facts"][0]["value"] == str(i + 1)
        assert f[0].get("/api/v1/ai/progress/mine", headers=s["learner"]).status_code == 200
        assert call_count == i + 1
