"""Grading calculations and roster rules shared by all result views."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select

from app.core.security import utc
from app.models import AttendanceSheet, ClassSession, Enrollment, EnrollmentPeriod, StudentScore


def roster(db, class_id, at):
    return list(
        db.scalars(
            select(Enrollment)
            .where(
                Enrollment.class_id == class_id,
                select(EnrollmentPeriod.id)
                .where(
                    EnrollmentPeriod.enrollment_id == Enrollment.id,
                    EnrollmentPeriod.organization_id == Enrollment.organization_id,
                    EnrollmentPeriod.starts_at <= at,
                    or_(EnrollmentPeriod.ends_at.is_(None), EnrollmentPeriod.ends_at > at),
                )
                .correlate(Enrollment)
                .exists(),
            )
            .order_by(Enrollment.id)
        )
    )


def calculations(db, items, enrollments):
    """Return only eligible items; missing marks never become zero."""
    ids = [e.id for e in enrollments]
    scores = (
        {
            (s.item_id, s.enrollment_id): s
            for s in db.scalars(select(StudentScore).where(StudentScore.enrollment_id.in_(ids)))
        }
        if ids
        else {}
    )
    eligible = {
        item.id: {e.id for e in roster(db, item.class_id, item.assessed_at)}
        for item in items
        if item.assessed_at
    }
    result = {}
    for enrollment in enrollments:
        marks = []
        weight = 0
        earned = Decimal(0)
        skills = {}
        missing = False
        for item in items:
            if enrollment.id not in eligible.get(item.id, set()):
                continue
            weight += item.weight
            score = scores.get((item.id, enrollment.id))
            marks.append(
                {
                    "item_id": item.id,
                    "name": item.name,
                    "skill": item.skill,
                    "max_score": item.max_score,
                    "score": score.score if score else None,
                    "comment": score.comment if score else "",
                }
            )
            if score is None:
                missing = True
                continue
            contribution = score.score / item.max_score * Decimal(item.weight)
            earned += contribution
            if item.skill != "general":
                total, part = skills.get(item.skill, (0, Decimal(0)))
                skills[item.skill] = (total + item.weight, part + contribution)

        def quantize(n):
            return n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        result[enrollment.id] = {
            "coverage_percent": quantize(Decimal(weight) / 100) if weight else Decimal(0),
            "final_score": quantize(earned / weight * 100) if weight and not missing else None,
            "skills": {key: quantize(part / total * 100) for key, (total, part) in skills.items()},
            "marks": marks,
        }
    return result


def attendance_summaries(db, enrollments):
    """Reference-only finalized attendance, fetched in two queries per page."""
    if not enrollments:
        return {}
    by_class = {}
    for enrollment in enrollments:
        by_class.setdefault(enrollment.class_id, []).append(enrollment)
    periods = {}
    for period in db.scalars(
        select(EnrollmentPeriod).where(
            EnrollmentPeriod.enrollment_id.in_([row.id for row in enrollments])
        )
    ):
        periods.setdefault(period.enrollment_id, []).append(period)
    counts = {
        row.id: {key: 0 for key in ("present", "late", "absent", "excused")} for row in enrollments
    }
    sheets = db.execute(
        select(ClassSession, AttendanceSheet)
        .join(AttendanceSheet, AttendanceSheet.session_id == ClassSession.id)
        .where(
            ClassSession.class_id.in_(by_class),
            ClassSession.status == "scheduled",
            AttendanceSheet.finalized.is_(True),
        )
    )
    for session, sheet in sheets:
        marks = {record["student_id"]: record["status"] for record in sheet.records}
        at = utc(session.starts_at)
        for row in by_class[session.class_id]:
            eligible = any(
                utc(period.starts_at) <= at and (period.ends_at is None or utc(period.ends_at) > at)
                for period in periods.get(row.id, [])
            )
            if eligible and marks.get(str(row.student_id)) in counts[row.id]:
                counts[row.id][marks[str(row.student_id)]] += 1
    result = {}
    for row in enrollments:
        values = counts[row.id]
        denominator = values["present"] + values["late"] + values["absent"]
        result[row.id] = {
            "counts": values,
            "attendance_percent": round(100 * (values["present"] + values["late"]) / denominator, 1)
            if denominator
            else None,
        }
    return result
