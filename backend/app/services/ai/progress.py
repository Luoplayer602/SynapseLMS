"""Source-backed progress facts; AI may select facts, never invent grades."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.routes import results
from app.core.security import now
from app.models import (
    AIActivePrompt,
    AIProgressCache,
    AIPrompt,
    AIProvider,
    AIRoute,
    AITenantSetting,
    ClassGradebook,
    Enrollment,
    LearningClass,
    PracticeAttempt,
)
from app.services import admissions
from app.services import results as calculations
from app.services.ai.routing import digest, invoke


def _fact(key, label, value, href):
    return {"id": key, "label": label, "value": value, "href": href}


def _summary(db, tenant, locale, facts, scope):
    if not facts:
        return {"mode": "rule", "facts": [], "highlights": [], "next_step": "keep_going"}
    allowed = {f["id"] for f in facts}
    payload = {"scope": scope, "facts": facts, "source_refs": sorted(allowed)}
    setting = db.scalar(
        select(AITenantSetting).where(
            AITenantSetting.organization_id == tenant.organization.id,
            AITenantSetting.task == "progress_summary",
            AITenantSetting.enabled.is_(True),
        )
    )
    active = (
        db.scalar(
            select(AIActivePrompt).where(
                AIActivePrompt.task == "progress_summary",
                AIActivePrompt.locale == locale,
            )
        )
        if setting
        else None
    )
    prompt = db.get(AIPrompt, active.prompt_id) if active else None
    route_state = (
        db.execute(
            select(AIRoute, AIProvider)
            .join(AIProvider)
            .where(
                AIRoute.task == "progress_summary",
            )
            .order_by(AIRoute.priority)
        ).all()
        if prompt
        else []
    )
    route_key = digest(
        {"routes": [(str(r.provider_id), r.priority, p.version, p.enabled) for r, p in route_state]}
    )
    source_key = digest(payload)
    cache_key = dict(
        organization_id=tenant.organization.id,
        viewer_id=tenant.actor.user.id,
        scope=scope,
        locale=locale,
        source_digest=source_key,
        prompt_id=prompt.id if prompt else None,
        route_digest=route_key,
    )
    if prompt and prompt.status == "published" and route_state:
        cache = db.scalar(
            select(AIProgressCache).where(
                *(getattr(AIProgressCache, key) == value for key, value in cache_key.items())
            )
        )
        if cache and set(cache.highlight_ids) <= allowed:
            return {
                "mode": "ai",
                "facts": facts,
                "highlights": [f for f in facts if f["id"] in cache.highlight_ids],
                "next_step": cache.next_step,
                "run_id": cache.ai_run_id,
            }

    def check(output):
        ids = output.get("highlight_ids")
        step = output.get("next_step")
        if (
            not isinstance(ids, list)
            or not ids
            or len(ids) > 3
            or any(x not in allowed for x in ids)
        ):
            raise ValueError("invalid fact selection")
        if step not in {"practice_more", "review_results", "keep_going"}:
            raise ValueError("invalid action")
        return ids, step

    selected = invoke(db, tenant, "progress_summary", locale, payload, check)
    if selected is None:
        return {
            "mode": "rule",
            "facts": facts,
            "highlights": facts[:3],
            "next_step": "review_results",
            "run_id": None,
        }
    (ids, step), run_id = selected
    if prompt:
        db.add(AIProgressCache(**cache_key, highlight_ids=ids, next_step=step, ai_run_id=run_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # Another tab may have stored the same validated selection.
    return {
        "mode": "ai",
        "facts": facts,
        "highlights": [f for f in facts if f["id"] in ids],
        "next_step": step,
        "run_id": run_id,
    }


def student(db, tenant, locale):
    profile = admissions.own_student(db, tenant)
    rows = db.execute(
        select(Enrollment, ClassGradebook, LearningClass)
        .join(ClassGradebook, ClassGradebook.class_id == Enrollment.class_id)
        .join(LearningClass, LearningClass.id == Enrollment.class_id)
        .where(
            Enrollment.organization_id == tenant.organization.id,
            Enrollment.student_id == profile.id,
            ClassGradebook.publish_at.is_not(None),
            ClassGradebook.publish_at <= now(),
        )
        .order_by(ClassGradebook.publish_at.desc())
        .limit(100)
    ).all()
    attendance = calculations.attendance_summaries(db, [r[0] for r in rows])
    facts = []
    for enrollment, book, classroom in rows:
        values = calculations.calculations(db, results.grade_items(db, book.id), [enrollment])[
            enrollment.id
        ]
        if values["final_score"] is not None:
            facts.append(
                _fact(
                    f"score:{book.id}", classroom.name, f"{values['final_score']}%", "/my-results"
                )
            )
        rate = attendance[enrollment.id]["attendance_percent"]
        if rate is not None:
            facts.append(_fact(f"attendance:{book.id}", classroom.name, f"{rate}%", "/my-results"))
    attempts = db.scalar(
        select(func.count(PracticeAttempt.id)).where(
            PracticeAttempt.organization_id == tenant.organization.id,
            PracticeAttempt.student_id == profile.id,
        )
    )
    if attempts:
        facts.append(
            _fact("practice:recent", "Bài luyện đã hoàn thành", str(attempts), "/practice")
        )
    return _summary(db, tenant, locale, facts, "student")


def teacher_class(db, tenant, class_id, locale):
    book = db.scalar(
        select(ClassGradebook).where(
            ClassGradebook.organization_id == tenant.organization.id,
            ClassGradebook.class_id == class_id,
            ClassGradebook.publish_at.is_not(None),
            ClassGradebook.publish_at <= now(),
        )
    )
    if not book:
        return _summary(db, tenant, locale, [], "class")
    enrolled = list(
        db.scalars(
            select(Enrollment).where(
                Enrollment.organization_id == tenant.organization.id,
                Enrollment.class_id == class_id,
            )
        )
    )
    if not enrolled:
        return _summary(db, tenant, locale, [], "class")
    scores = calculations.calculations(db, results.grade_items(db, book.id), enrolled)
    attendance = calculations.attendance_summaries(db, enrolled)
    published = [float(x["final_score"]) for x in scores.values() if x["final_score"] is not None]
    rates = [
        x["attendance_percent"] for x in attendance.values() if x["attendance_percent"] is not None
    ]
    facts = [
        _fact(
            f"class:published:{book.id}",
            "Học viên có điểm tổng kết",
            str(len(published)),
            f"/gradebook?class={class_id}",
        )
    ]
    if published:
        facts.append(
            _fact(
                f"class:average:{book.id}",
                "Điểm trung bình đã công bố",
                f"{sum(published) / len(published):.1f}%",
                f"/gradebook?class={class_id}",
            )
        )
    if rates:
        facts.append(
            _fact(
                f"class:attendance:{book.id}",
                "Chuyên cần trung bình",
                f"{sum(rates) / len(rates):.1f}%",
                "/attendance",
            )
        )
    return _summary(db, tenant, locale, facts, f"class:{class_id}")
