from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.errors import APIError
from app.services.ai import recommendations


def test_ai_cannot_add_unfiltered_class(monkeypatch):
    ids = [uuid4(), uuid4()]
    rows = [
        {"id": ids[0], "name": "A", "code": "A", "seats_left": 2, "warnings": []},
        {
            "id": ids[1],
            "name": "B",
            "code": "B",
            "seats_left": 3,
            "warnings": ["ADMISSION_LEVEL_REVIEW"],
        },
    ]
    monkeypatch.setattr(recommendations.admissions, "candidates", lambda *_: rows)

    def rogue(_db, _tenant, _task, _locale, _payload, validator):
        validator({"ranked_ids": [str(ids[0]), str(uuid4())]})

    monkeypatch.setattr(recommendations, "invoke", rogue)
    tenant = SimpleNamespace(organization=SimpleNamespace(id=uuid4()))
    request = SimpleNamespace(
        status="waiting", cancelled_at=None, course_id=uuid4(), format="any", availability=[]
    )
    with pytest.raises(APIError):
        recommendations.recommend(None, tenant, request, "vi")
