"""Rank only admissions' already eligible class candidates."""

from app.core.errors import APIError
from app.services import admissions
from app.services.ai.routing import invoke


def recommend(db, tenant, request_row, locale: str):
    if request_row.status != "waiting" or request_row.cancelled_at:
        raise APIError(409, "ADMISSION_NOT_WAITING")
    candidates = admissions.candidates(db, tenant, request_row)
    ordered = sorted(candidates, key=lambda x: (len(x["warnings"]), -x["seats_left"], x["code"]))
    if len(ordered) <= 1:
        return {"items": ordered, "mode": "rule", "run_id": None}
    allowed = {str(c["id"]): c for c in ordered}
    payload = {
        "course_id": str(request_row.course_id),
        "format": request_row.format,
        "availability": request_row.availability,
        "candidates": [{**c, "id": str(c["id"])} for c in ordered],
    }

    def check(output):
        ids = output.get("ranked_ids")
        if not isinstance(ids, list) or len(ids) != len(allowed) or set(ids) != set(allowed):
            raise APIError(422, "AI_OUTPUT_INVALID")
        return [allowed[key] for key in ids]

    result = invoke(db, tenant, "class_recommendation", locale, payload, check)
    if result is None:
        return {"items": ordered, "mode": "rule", "run_id": None}
    items, run_id = result
    return {"items": items, "mode": "ai", "run_id": run_id}
