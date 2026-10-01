"""Tenant-scoped course schemes, class gradebooks and published personal results."""

from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.api.dependencies import DB, Tenant, auth_guard
from app.api.result_schemas import (
    ItemTiming,
    LockChange,
    Publication,
    SchemeChange,
    SchemeCreate,
    ScoreSave,
    VersionInput,
)
from app.api.routes.courses import Limit, Offset, authorize
from app.core.errors import APIError
from app.core.security import now, utc
from app.models import (
    ClassGradebook,
    ClassGradeItem,
    ClassSession,
    ClassTeacher,
    Course,
    CourseGradingComponent,
    CourseGradingScheme,
    Enrollment,
    LearningClass,
    StudentProfile,
    StudentScore,
    TeacherProfile,
)
from app.services import admissions as business
from app.services import results as svc

router = APIRouter(prefix="/results", dependencies=[Depends(auth_guard)])


def role(db, tenant, request, response):
    return authorize(db, tenant, request, response, "business_read")


def manager(db, tenant, request, response):
    if role(db, tenant, request, response) != "organization_manager":
        raise APIError(403, "FORBIDDEN")


def teacher(db, tenant):
    row = db.scalar(
        select(TeacherProfile).where(
            TeacherProfile.organization_id == tenant.organization.id,
            TeacherProfile.user_id == tenant.actor.user.id,
            TeacherProfile.archived_at.is_(None),
        )
    )
    if not row:
        raise APIError(403, "FORBIDDEN")
    return row


def class_access(db, tenant, request, response, class_id, *, edit=False, manage=False):
    current = role(db, tenant, request, response)
    row = business.scoped(db, LearningClass, tenant, class_id)
    if manage and current != "organization_manager":
        raise APIError(403, "FORBIDDEN")
    if edit and current != "teacher":
        raise APIError(403, "FORBIDDEN")
    if current == "teacher":
        profile = teacher(db, tenant)
        assigned = db.scalar(
            select(ClassTeacher.id).where(
                ClassTeacher.class_id == row.id,
                ClassTeacher.organization_id == tenant.organization.id,
                ClassTeacher.teacher_profile_id == profile.id,
            )
        )
        if not assigned:
            raise APIError(404, "BUSINESS_NOT_FOUND")
    elif current == "student":
        raise APIError(403, "FORBIDDEN")
    return row


def scheme_components(db, scheme_id):
    return list(
        db.scalars(
            select(CourseGradingComponent)
            .where(CourseGradingComponent.scheme_id == scheme_id)
            .order_by(CourseGradingComponent.position)
        )
    )


def scheme_view(db, scheme):
    return {
        "id": scheme.id,
        "course_id": scheme.course_id,
        "name": scheme.name,
        "revision": scheme.revision,
        "status": scheme.status,
        "version": scheme.version,
        "components": [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "skill": c.skill,
                "max_score": c.max_score,
                "weight": c.weight,
                "position": c.position,
            }
            for c in scheme_components(db, scheme.id)
        ],
    }


def scheme(db, tenant, scheme_id):
    return business.scoped(db, CourseGradingScheme, tenant, scheme_id)


def write_scheme(db, tenant, request, response, body, item=None):
    manager(db, tenant, request, response)
    course = business.scoped(db, Course, tenant, body.course_id)
    if course.status == "archived":
        raise APIError(409, "RESULT_COURSE_UNAVAILABLE")
    if item:
        if item.course_id != course.id:
            raise APIError(409, "RESULT_SCHEME_IMMUTABLE")
    action = "results.scheme.change" if item else "results.scheme.create"
    fingerprint, old = business.replay(db, tenant, action, item.id if item else course.id, body)
    if old is not None:
        return old
    if item:
        business.expected(item, body.version)
        if item.status != "draft":
            raise APIError(409, "RESULT_SCHEME_IMMUTABLE")
    if item is None:
        revision = (
            db.scalar(
                select(func.max(CourseGradingScheme.revision)).where(
                    CourseGradingScheme.organization_id == tenant.organization.id,
                    CourseGradingScheme.course_id == course.id,
                )
            )
            or 0
        )
        item = CourseGradingScheme(
            organization_id=tenant.organization.id,
            course_id=course.id,
            revision=revision + 1,
            name=body.name,
        )
        db.add(item)
        db.flush()
        before = {}
    else:
        before = scheme_view(db, item)
        item.name = body.name
        for component in scheme_components(db, item.id):
            db.delete(component)
        db.flush()
        item.version += 1
    for position, component in enumerate(body.components):
        db.add(
            CourseGradingComponent(
                organization_id=tenant.organization.id,
                scheme_id=item.id,
                position=position,
                **component.model_dump(),
            )
        )
    db.flush()
    return business.finish(
        db, tenant, action, item.id, body, fingerprint, scheme_view(db, item), before
    )


@router.get("/schemes")
def schemes(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    course_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    current = role(db, tenant, request, response)
    if current not in {"organization_manager", "staff"}:
        raise APIError(403, "FORBIDDEN")
    query = select(CourseGradingScheme).where(
        CourseGradingScheme.organization_id == tenant.organization.id
    )
    if course_id:
        query = query.where(CourseGradingScheme.course_id == course_id)
    query = query.order_by(CourseGradingScheme.created_at.desc(), CourseGradingScheme.id)
    return {
        "items": [scheme_view(db, x) for x in db.scalars(query.limit(limit).offset(offset))],
        "total": db.scalar(select(func.count()).select_from(query.order_by(None).subquery())),
    }


@router.post("/schemes", status_code=201)
def create_scheme(body: SchemeCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    return write_scheme(db, tenant, request, response, body)


@router.get("/schemes/{scheme_id}")
def scheme_detail(scheme_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    current = role(db, tenant, request, response)
    if current not in {"organization_manager", "staff"}:
        raise APIError(403, "FORBIDDEN")
    return scheme_view(db, scheme(db, tenant, scheme_id))


@router.patch("/schemes/{scheme_id}")
def change_scheme(
    scheme_id: UUID,
    body: SchemeChange,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    return write_scheme(db, tenant, request, response, body, scheme(db, tenant, scheme_id))


def scheme_state(db, tenant, request, response, scheme_id, body, state):
    manager(db, tenant, request, response)
    item = scheme(db, tenant, scheme_id)
    action = "results.scheme." + state
    fingerprint, old = business.replay(db, tenant, action, item.id, body)
    if old is not None:
        return old
    business.expected(item, body.version)
    before = scheme_view(db, item)
    if state == "publish":
        if item.status != "draft" or sum(c.weight for c in scheme_components(db, item.id)) != 10000:
            raise APIError(409, "RESULT_SCHEME_WEIGHT")
        if db.scalar(
            select(CourseGradingScheme.id).where(
                CourseGradingScheme.course_id == item.course_id,
                CourseGradingScheme.status == "published",
                CourseGradingScheme.id != item.id,
            )
        ):
            raise APIError(409, "RESULT_SCHEME_ACTIVE")
        item.status = "published"
    elif state == "retire":
        if item.status != "published":
            raise APIError(409, "RESULT_SCHEME_IMMUTABLE")
        item.status = "retired"
    item.version += 1
    db.flush()
    return business.finish(
        db, tenant, action, item.id, body, fingerprint, scheme_view(db, item), before
    )


@router.post("/schemes/{scheme_id}/publish")
def publish_scheme(
    scheme_id: UUID,
    body: VersionInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    return scheme_state(db, tenant, request, response, scheme_id, body, "publish")


@router.post("/schemes/{scheme_id}/retire")
def retire_scheme(
    scheme_id: UUID,
    body: VersionInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    return scheme_state(db, tenant, request, response, scheme_id, body, "retire")


@router.post("/schemes/{scheme_id}/clone", status_code=201)
def clone_scheme(
    scheme_id: UUID,
    body: VersionInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    manager(db, tenant, request, response)
    item = scheme(db, tenant, scheme_id)
    components = scheme_components(db, item.id)
    fingerprint, old = business.replay(db, tenant, "results.scheme.clone", item.id, body)
    if old is not None:
        return old
    business.expected(item, body.version)
    revision = (
        db.scalar(
            select(func.max(CourseGradingScheme.revision)).where(
                CourseGradingScheme.course_id == item.course_id,
                CourseGradingScheme.organization_id == tenant.organization.id,
            )
        )
        or 0
    )
    clone = CourseGradingScheme(
        organization_id=tenant.organization.id,
        course_id=item.course_id,
        revision=revision + 1,
        name=item.name,
    )
    db.add(clone)
    db.flush()
    for c in components:
        db.add(
            CourseGradingComponent(
                organization_id=tenant.organization.id,
                scheme_id=clone.id,
                code=c.code,
                name=c.name,
                skill=c.skill,
                max_score=c.max_score,
                weight=c.weight,
                position=c.position,
            )
        )
    db.flush()
    return business.finish(
        db, tenant, "results.scheme.clone", item.id, body, fingerprint, scheme_view(db, clone)
    )


def gradebook(db, tenant, class_id):
    row = db.scalar(
        select(ClassGradebook).where(
            ClassGradebook.class_id == class_id,
            ClassGradebook.organization_id == tenant.organization.id,
        )
    )
    if not row:
        raise APIError(404, "BUSINESS_NOT_FOUND")
    return row


def grade_items(db, gradebook_id):
    return list(
        db.scalars(
            select(ClassGradeItem)
            .where(ClassGradeItem.gradebook_id == gradebook_id)
            .order_by(ClassGradeItem.position)
        )
    )


def gradebook_view(db, row):
    items = grade_items(db, row.id)
    enrollments = list(
        db.scalars(
            select(Enrollment).where(Enrollment.class_id == row.class_id).order_by(Enrollment.id)
        )
    )
    names = (
        {
            s.id: s.full_name
            for s in db.scalars(
                select(StudentProfile).where(
                    StudentProfile.id.in_([e.student_id for e in enrollments])
                )
            )
        }
        if enrollments
        else {}
    )
    values = svc.calculations(db, items, enrollments)
    attendance = svc.attendance_summaries(db, enrollments)
    return {
        "id": row.id,
        "class_id": row.class_id,
        "course_id": row.course_id,
        "scheme_snapshot": row.scheme_snapshot,
        "version": row.version,
        "publish_at": row.publish_at,
        "locked_at": row.locked_at,
        "items": [
            {
                "id": i.id,
                "code": i.code,
                "name": i.name,
                "skill": i.skill,
                "max_score": i.max_score,
                "weight": i.weight,
                "assessed_at": i.assessed_at,
                "session_id": i.session_id,
            }
            for i in items
        ],
        "students": [
            {
                "enrollment_id": e.id,
                "student_name": names.get(e.student_id, ""),
                **values[e.id],
                "attendance": attendance[e.id],
            }
            for e in enrollments
        ],
    }


@router.get("/classes")
def result_classes(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    current = role(db, tenant, request, response)
    if current == "student":
        raise APIError(403, "FORBIDDEN")
    query = select(LearningClass).where(LearningClass.organization_id == tenant.organization.id)
    if current == "teacher":
        profile = teacher(db, tenant)
        query = query.join(ClassTeacher, ClassTeacher.class_id == LearningClass.id).where(
            ClassTeacher.teacher_profile_id == profile.id
        )
    query = query.order_by(LearningClass.name, LearningClass.id)
    rows = list(db.scalars(query.limit(limit).offset(offset)))
    return {
        "items": [
            {
                "id": x.id,
                "name": x.name,
                "course_id": x.course_id,
                "gradebook_id": db.scalar(
                    select(ClassGradebook.id).where(ClassGradebook.class_id == x.id)
                ),
            }
            for x in rows
        ],
        "total": db.scalar(select(func.count()).select_from(query.order_by(None).subquery())),
    }


@router.post("/classes/{class_id}/gradebook", status_code=201)
def create_gradebook(
    class_id: UUID, body: VersionInput, db: DB, tenant: Tenant, request: Request, response: Response
):
    classroom = class_access(db, tenant, request, response, class_id, edit=True)
    fingerprint, old = business.replay(db, tenant, "results.gradebook.create", class_id, body)
    if old is not None:
        return old
    if db.scalar(select(ClassGradebook.id).where(ClassGradebook.class_id == class_id)):
        raise APIError(409, "RESULT_GRADEBOOK_EXISTS")
    scheme_row = db.scalar(
        select(CourseGradingScheme).where(
            CourseGradingScheme.organization_id == tenant.organization.id,
            CourseGradingScheme.course_id == classroom.course_id,
            CourseGradingScheme.status == "published",
        )
    )
    if not scheme_row:
        raise APIError(409, "RESULT_SCHEME_REQUIRED")
    snapshot = scheme_view(db, scheme_row)
    row = ClassGradebook(
        organization_id=tenant.organization.id,
        class_id=class_id,
        course_id=classroom.course_id,
        scheme_id=scheme_row.id,
        scheme_snapshot=jsonable_encoder(snapshot),
    )
    db.add(row)
    db.flush()
    for component in scheme_components(db, scheme_row.id):
        db.add(
            ClassGradeItem(
                organization_id=tenant.organization.id,
                class_id=class_id,
                gradebook_id=row.id,
                code=component.code,
                name=component.name,
                skill=component.skill,
                max_score=component.max_score,
                weight=component.weight,
                position=component.position,
            )
        )
    db.flush()
    return business.finish(
        db, tenant, "results.gradebook.create", class_id, body, fingerprint, gradebook_view(db, row)
    )


@router.get("/classes/{class_id}")
def gradebook_detail(class_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    class_access(db, tenant, request, response, class_id)
    return gradebook_view(db, gradebook(db, tenant, class_id))


def item_for(db, row, item_id):
    item = db.scalar(
        select(ClassGradeItem).where(
            ClassGradeItem.id == item_id, ClassGradeItem.gradebook_id == row.id
        )
    )
    if not item:
        raise APIError(404, "BUSINESS_NOT_FOUND")
    return item


@router.post("/classes/{class_id}/items/{item_id}/timing")
def item_timing(
    class_id: UUID,
    item_id: UUID,
    body: ItemTiming,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    class_access(db, tenant, request, response, class_id, edit=True)
    row = gradebook(db, tenant, class_id)
    item = item_for(db, row, item_id)
    fingerprint, old = business.replay(db, tenant, "results.item.timing", item_id, body)
    if old is not None:
        return old
    business.expected(row, body.version)
    if row.locked_at or (row.publish_at and utc(row.publish_at) <= now()):
        raise APIError(409, "RESULT_LOCKED")
    if db.scalar(select(StudentScore.id).where(StudentScore.item_id == item.id)):
        raise APIError(409, "RESULT_TIMING_LOCKED")
    if body.session_id:
        session = business.scoped(db, ClassSession, tenant, body.session_id)
        if session.class_id != class_id or session.status != "scheduled":
            raise APIError(409, "RESULT_SESSION_MISMATCH")
    before = gradebook_view(db, row)
    item.assessed_at = body.assessed_at.astimezone(UTC)
    item.session_id = body.session_id
    row.version += 1
    db.flush()
    return business.finish(
        db,
        tenant,
        "results.item.timing",
        item_id,
        body,
        fingerprint,
        gradebook_view(db, row),
        before,
    )


@router.put("/classes/{class_id}/items/{item_id}")
def save_scores(
    class_id: UUID,
    item_id: UUID,
    body: ScoreSave,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    class_access(db, tenant, request, response, class_id, edit=True)
    row = gradebook(db, tenant, class_id)
    item = item_for(db, row, item_id)
    fingerprint, old = business.replay(db, tenant, "results.scores.save", item_id, body)
    if old is not None:
        return old
    business.expected(row, body.version)
    if row.locked_at or item.assessed_at is None:
        raise APIError(409, "RESULT_LOCKED")
    if row.publish_at and utc(row.publish_at) <= now() and len(body.reason) < 3:
        raise APIError(422, "BUSINESS_REASON_REQUIRED")
    roster = svc.roster(db, class_id, item.assessed_at)
    ids = [x.enrollment_id for x in body.scores]
    if len(ids) != len(set(ids)) or set(ids) != {e.id for e in roster}:
        raise APIError(409, "RESULT_ROSTER_CHANGED")
    before = gradebook_view(db, row)
    prior = {
        s.enrollment_id: s
        for s in db.scalars(select(StudentScore).where(StudentScore.item_id == item.id))
    }
    for record in body.scores:
        if record.score is not None and record.score > item.max_score:
            raise APIError(422, "RESULT_SCORE_RANGE")
        existing = prior.get(record.enrollment_id)
        if record.score is None:
            if existing:
                db.delete(existing)
        elif existing:
            existing.score = record.score
            existing.comment = record.comment
            existing.actor_id = tenant.actor.user.id
        else:
            db.add(
                StudentScore(
                    organization_id=tenant.organization.id,
                    class_id=class_id,
                    gradebook_id=row.id,
                    item_id=item.id,
                    enrollment_id=record.enrollment_id,
                    score=record.score,
                    comment=record.comment,
                    actor_id=tenant.actor.user.id,
                )
            )
    row.version += 1
    db.flush()
    result = gradebook_view(db, row)
    if row.publish_at and utc(row.publish_at) <= now():
        result["reason"] = body.reason
    return business.finish(
        db,
        tenant,
        "results.scores.save",
        item_id,
        body,
        fingerprint,
        result,
        before,
    )


@router.post("/classes/{class_id}/publication")
def publication(
    class_id: UUID, body: Publication, db: DB, tenant: Tenant, request: Request, response: Response
):
    class_access(db, tenant, request, response, class_id, edit=True)
    row = gradebook(db, tenant, class_id)
    fingerprint, old = business.replay(db, tenant, "results.publication", class_id, body)
    if old is not None:
        return old
    business.expected(row, body.version)
    if row.locked_at or (row.publish_at and utc(row.publish_at) <= now()):
        raise APIError(409, "RESULT_PUBLICATION_FINAL")
    before = gradebook_view(db, row)
    row.publish_at = body.publish_at.astimezone(UTC)
    row.version += 1
    db.flush()
    return business.finish(
        db,
        tenant,
        "results.publication",
        class_id,
        body,
        fingerprint,
        gradebook_view(db, row),
        before,
    )


def lock_change(class_id, body, db, tenant, request, response, locking):
    class_access(db, tenant, request, response, class_id, manage=True)
    row = gradebook(db, tenant, class_id)
    action = "results.lock" if locking else "results.unlock"
    fingerprint, old = business.replay(db, tenant, action, class_id, body)
    if old is not None:
        return old
    business.expected(row, body.version)
    if locking and (row.locked_at or not row.publish_at or utc(row.publish_at) > now()):
        raise APIError(409, "RESULT_LOCK_STATE")
    if not locking and not row.locked_at:
        raise APIError(409, "RESULT_LOCK_STATE")
    before = gradebook_view(db, row)
    row.locked_at = now() if locking else None
    row.locked_by = tenant.actor.user.id if locking else None
    row.version += 1
    db.flush()
    result = gradebook_view(db, row)
    result["reason"] = body.reason
    return business.finish(db, tenant, action, class_id, body, fingerprint, result, before)


@router.post("/classes/{class_id}/lock")
def lock(
    class_id: UUID, body: LockChange, db: DB, tenant: Tenant, request: Request, response: Response
):
    return lock_change(class_id, body, db, tenant, request, response, True)


@router.post("/classes/{class_id}/unlock")
def unlock(
    class_id: UUID, body: LockChange, db: DB, tenant: Tenant, request: Request, response: Response
):
    return lock_change(class_id, body, db, tenant, request, response, False)


@router.get("/mine")
def mine(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    if role(db, tenant, request, response) != "student":
        raise APIError(403, "FORBIDDEN")
    profile = business.own_student(db, tenant)
    query = (
        select(Enrollment, ClassGradebook, LearningClass)
        .join(ClassGradebook, ClassGradebook.class_id == Enrollment.class_id)
        .join(LearningClass, LearningClass.id == Enrollment.class_id)
        .where(
            Enrollment.organization_id == tenant.organization.id,
            Enrollment.student_id == profile.id,
            ClassGradebook.publish_at.is_not(None),
            ClassGradebook.publish_at <= now(),
        )
        .order_by(ClassGradebook.publish_at.desc(), ClassGradebook.id)
    )
    rows = db.execute(query.limit(limit).offset(offset)).all()
    attendance = svc.attendance_summaries(db, [row[0] for row in rows])
    result = []
    for enrollment, book, classroom in rows:
        values = svc.calculations(db, grade_items(db, book.id), [enrollment])[enrollment.id]
        result.append(
            {
                "class_id": classroom.id,
                "class_name": classroom.name,
                "publish_at": book.publish_at,
                **values,
                "attendance": attendance[enrollment.id],
            }
        )
    return {
        "items": result,
        "total": db.scalar(select(func.count()).select_from(query.order_by(None).subquery())),
    }
