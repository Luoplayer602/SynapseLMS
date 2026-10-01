"""Closed-answer practice, idempotent submissions and permanent theme grants."""

from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from app.core.errors import APIError
from app.core.security import now
from app.models import (
    AITenantSetting,
    Course,
    Enrollment,
    EnrollmentPeriod,
    LearningClass,
    PracticeAttempt,
    PracticeDay,
    PracticeQuestion,
    StudentProfile,
    ThemeGrant,
    ThemeSelection,
)
from app.services.ai.routing import invoke

MILESTONES = {3: "neo-pop", 7: "clay-garden", 14: "liquid-glass"}


def valid_question(stem, options, correct_index):
    if not isinstance(stem, str) or not 10 <= len(stem.strip()) <= 1000:
        raise APIError(422, "PRACTICE_QUESTION_INVALID")
    if not isinstance(options, list) or not 2 <= len(options) <= 4:
        raise APIError(422, "PRACTICE_QUESTION_INVALID")
    if any(not isinstance(x, str) or not 1 <= len(x.strip()) <= 200 for x in options):
        raise APIError(422, "PRACTICE_QUESTION_INVALID")
    if len({x.casefold().strip() for x in options}) != len(options):
        raise APIError(422, "PRACTICE_QUESTION_INVALID")
    if type(correct_index) is not int or not 0 <= correct_index < len(options):
        raise APIError(422, "PRACTICE_QUESTION_INVALID")


def question_view(row, *, reveal=False):
    result = {
        "id": row.id,
        "course_id": row.course_id,
        "locale": row.locale,
        "stem": row.stem,
        "options": row.options,
        "status": row.status,
    }
    if reveal:
        result.update(correct_index=row.correct_index, explanation=row.explanation)
    return result


def tenant_timezone(db, org_id):
    setting = db.scalar(
        select(AITenantSetting).where(
            AITenantSetting.organization_id == org_id,
            AITenantSetting.task == "practice_generation",
        )
    )
    return setting.timezone if setting else "Asia/Ho_Chi_Minh"


def accessible_courses(db, tenant, student_id):
    current = now()
    return set(
        db.scalars(
            select(LearningClass.course_id)
            .join(Enrollment, Enrollment.class_id == LearningClass.id)
            .where(
                Enrollment.organization_id == tenant.organization.id,
                Enrollment.student_id == student_id,
                select(EnrollmentPeriod.id)
                .where(
                    EnrollmentPeriod.enrollment_id == Enrollment.id,
                    EnrollmentPeriod.organization_id == tenant.organization.id,
                    EnrollmentPeriod.starts_at <= current,
                    or_(EnrollmentPeriod.ends_at.is_(None), EnrollmentPeriod.ends_at > current),
                )
                .correlate(Enrollment)
                .exists(),
            )
        )
    )


def generate(db, tenant, course_id: UUID, locale: str):
    course = db.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.organization_id == tenant.organization.id,
            Course.status == "published",
        )
    )
    if not course:
        raise APIError(404, "COURSE_NOT_FOUND")
    payload = {
        "course": course.name,
        "objectives": course.objectives[:2000],
        "locale": locale,
        "source_refs": [str(course.id)],
    }

    def check(output):
        stem, options, index = (
            output.get("stem"),
            output.get("options"),
            output.get("correct_index"),
        )
        valid_question(stem, options, index)
        explanation = output.get("explanation", "")
        if not isinstance(explanation, str) or len(explanation) > 1000:
            raise APIError(422, "PRACTICE_QUESTION_INVALID")
        return stem.strip(), [x.strip() for x in options], index, explanation

    result = invoke(db, tenant, "practice_generation", locale, payload, check)
    if result is None:
        raise APIError(503, "PRACTICE_GENERATION_UNAVAILABLE")
    (stem, options, index, explanation), run_id = result
    row = PracticeQuestion(
        organization_id=tenant.organization.id,
        course_id=course.id,
        creator_id=tenant.actor.user.id,
        ai_run_id=run_id,
        status="draft",
        locale=locale,
        stem=stem,
        options=options,
        correct_index=index,
        explanation=explanation,
        source_refs=[str(course.id)],
    )
    db.add(row)
    db.commit()
    return question_view(row, reveal=True)


def submit(
    db,
    tenant,
    profile: StudentProfile,
    question: PracticeQuestion,
    request_key: UUID,
    answer_index: int,
):
    db.scalar(select(StudentProfile).where(StudentProfile.id == profile.id).with_for_update())
    old = db.scalar(
        select(PracticeAttempt).where(
            PracticeAttempt.organization_id == tenant.organization.id,
            PracticeAttempt.student_id == profile.id,
            PracticeAttempt.request_key == request_key,
        )
    )
    if old:
        if old.question_id != question.id or old.answer_index != answer_index:
            raise APIError(409, "PRACTICE_REPLAY_CONFLICT")
        return attempt_view(db, old)
    if question.status != "published" or question.course_id not in accessible_courses(
        db, tenant, profile.id
    ):
        raise APIError(404, "PRACTICE_NOT_FOUND")
    if answer_index >= len(question.options):
        raise APIError(422, "PRACTICE_ANSWER_INVALID")
    prior = db.scalar(
        select(PracticeAttempt).where(
            PracticeAttempt.organization_id == tenant.organization.id,
            PracticeAttempt.student_id == profile.id,
            PracticeAttempt.question_id == question.id,
        )
    )
    if prior:
        raise APIError(409, "PRACTICE_ALREADY_COMPLETED")
    timezone = tenant_timezone(db, tenant.organization.id)
    stamp = now()
    day = stamp.astimezone(ZoneInfo(timezone)).date()
    attempt = PracticeAttempt(
        organization_id=tenant.organization.id,
        student_id=profile.id,
        question_id=question.id,
        request_key=request_key,
        answer_index=answer_index,
        correct=answer_index == question.correct_index,
        completed_at=stamp,
        local_day=day,
        timezone=timezone,
    )
    db.add(attempt)
    db.flush()
    existing_day = db.scalar(
        select(PracticeDay).where(
            PracticeDay.organization_id == tenant.organization.id,
            PracticeDay.student_id == profile.id,
            PracticeDay.local_day == day,
        )
    )
    if not existing_day:
        yesterday = db.scalar(
            select(PracticeDay).where(
                PracticeDay.organization_id == tenant.organization.id,
                PracticeDay.student_id == profile.id,
                PracticeDay.local_day == day - timedelta(days=1),
            )
        )
        streak = yesterday.streak + 1 if yesterday else 1
        current_day = PracticeDay(
            organization_id=tenant.organization.id,
            student_id=profile.id,
            local_day=day,
            timezone=timezone,
            attempt_id=attempt.id,
            streak=streak,
        )
        db.add(current_day)
        db.flush()
        if streak in MILESTONES:
            db.add(
                ThemeGrant(
                    organization_id=tenant.organization.id,
                    student_id=profile.id,
                    theme=MILESTONES[streak],
                    earned_day_id=current_day.id,
                )
            )
    db.commit()
    return attempt_view(db, attempt)


def attempt_view(db, row):
    question = db.get(PracticeQuestion, row.question_id)
    return {
        "id": row.id,
        "question_id": row.question_id,
        "answer_index": row.answer_index,
        "correct": row.correct,
        "correct_index": question.correct_index,
        "explanation": question.explanation,
        "completed_at": row.completed_at,
        "local_day": row.local_day,
    }


def rewards(db, tenant, profile):
    latest = db.scalar(
        select(PracticeDay)
        .where(
            PracticeDay.organization_id == tenant.organization.id,
            PracticeDay.student_id == profile.id,
        )
        .order_by(PracticeDay.local_day.desc())
    )
    today = now().astimezone(ZoneInfo(tenant_timezone(db, tenant.organization.id))).date()
    current = latest.streak if latest and latest.local_day >= today - timedelta(days=1) else 0
    best = (
        db.scalar(
            select(PracticeDay.streak)
            .where(
                PracticeDay.organization_id == tenant.organization.id,
                PracticeDay.student_id == profile.id,
            )
            .order_by(PracticeDay.streak.desc())
            .limit(1)
        )
        or 0
    )
    grants = set(
        db.scalars(
            select(ThemeGrant.theme).where(
                ThemeGrant.organization_id == tenant.organization.id,
                ThemeGrant.student_id == profile.id,
            )
        )
    )
    selection = db.scalar(
        select(ThemeSelection).where(
            ThemeSelection.organization_id == tenant.organization.id,
            ThemeSelection.student_id == profile.id,
        )
    )
    return {
        "current_streak": current,
        "best_streak": best,
        "unlocked": ["synapse-soft", *sorted(grants)],
        "selected": selection.theme if selection else "synapse-soft",
    }
