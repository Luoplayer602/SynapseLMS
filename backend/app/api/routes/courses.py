from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.api.course_schemas import (
    CatalogCodeAction,
    CourseChange,
    CourseCreate,
    CourseState,
    FrameworkCreate,
    LevelCreate,
    NamedCode,
    Rename,
)
from app.api.dependencies import DB, Tenant, audit, auth_guard, lock_actor
from app.core.errors import APIError
from app.core.security import now, utc
from app.models import (
    AuditLog,
    Course,
    CourseLanguage,
    CourseLevel,
    LevelFramework,
    Organization,
    SupportSession,
    UserMembership,
)

router = APIRouter(dependencies=[Depends(auth_guard)])
Kind = Literal["languages", "frameworks", "levels"]
MODELS = {"languages": CourseLanguage, "frameworks": LevelFramework, "levels": CourseLevel}
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Search = Annotated[str, Query(max_length=100)]


def authorize(db, tenant, request, response, mode="edit"):
    response.headers["Cache-Control"] = "no-store"
    org = db.scalar(
        select(Organization)
        .where(Organization.id == tenant.organization.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = lock_actor(db, tenant.actor)
    if not org or not org.is_active:
        raise APIError(403, "TENANT_UNAVAILABLE")
    role = tenant.role
    if user.is_root_admin:
        support = db.scalar(
            select(SupportSession)
            .where(
                SupportSession.id == UUID(request.headers["x-support-session"]),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            not support
            or support.revoked_at
            or utc(support.expires_at) <= now()
            or support.organization_id != org.id
            or support.user_id != user.id
            or support.auth_session_id != tenant.actor.session.id
        ):
            raise APIError(403, "SUPPORT_SESSION_REQUIRED")
    else:
        member = db.scalar(
            select(UserMembership)
            .where(
                UserMembership.user_id == user.id,
                UserMembership.organization_id == org.id,
                UserMembership.is_active.is_(True),
                UserMembership.ended_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        if not member:
            raise APIError(403, "TENANT_UNAVAILABLE")
        role = member.role
    allowed = (
        {"student"}
        if mode == "catalog"
        else {"organization_manager"}
        if mode == "manage"
        else {"organization_manager", "staff"}
    )
    if role not in allowed or (mode == "catalog" and user.is_root_admin):
        raise APIError(403, "FORBIDDEN")


def commit(db):
    try:
        db.commit()
    except (IntegrityError, StaleDataError) as error:
        db.rollback()
        raise APIError(409, "COURSE_CONFLICT") from error


def scoped(db, model, tenant, item_id):
    item = db.scalar(
        select(model).where(model.id == item_id, model.organization_id == tenant.organization.id)
    )
    if not item:
        raise APIError(404, "COURSE_NOT_FOUND")
    return item


def version(item, expected):
    if item.version != expected:
        raise APIError(409, "COURSE_CONFLICT")


def metadata_view(item):
    return {
        field: getattr(item, field)
        for field in ("id", "code", "name", "version", "language_id", "framework_id", "rank")
        if hasattr(item, field)
    }


@router.get("/course-settings/{kind}")
def settings_list(
    kind: Kind,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 100,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response)
    model = MODELS[kind]
    query = select(model).where(model.organization_id == tenant.organization.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    ordering = (model.rank, model.id) if kind == "levels" else (model.code, model.id)
    return {
        "items": [
            metadata_view(x)
            for x in db.scalars(query.order_by(*ordering).limit(limit).offset(offset))
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def add_metadata(db, tenant, model, fields):
    item = model(organization_id=tenant.organization.id, **fields)
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "COURSE_CONFLICT") from error
    audit(
        db,
        tenant.actor,
        "course_settings.create",
        tenant.organization.id,
        item.id,
        kind=model.__tablename__,
    )
    commit(db)
    return metadata_view(item)


@router.post("/course-settings/languages", status_code=201)
def language_create(data: NamedCode, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    return add_metadata(db, tenant, CourseLanguage, data.model_dump())


@router.post("/course-settings/frameworks", status_code=201)
def framework_create(
    data: FrameworkCreate, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response, "manage")
    scoped(db, CourseLanguage, tenant, data.language_id)
    return add_metadata(db, tenant, LevelFramework, data.model_dump())


@router.post("/course-settings/levels", status_code=201)
def level_create(data: LevelCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    framework = scoped(db, LevelFramework, tenant, data.framework_id)
    return add_metadata(
        db, tenant, CourseLevel, {**data.model_dump(), "language_id": framework.language_id}
    )


@router.patch("/course-settings/{kind}/{item_id}")
def rename(
    kind: Kind,
    item_id: UUID,
    data: Rename,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, MODELS[kind], tenant, item_id)
    version(item, data.version)
    item.name = data.name
    item.version += 1
    audit(db, tenant.actor, "course_settings.rename", tenant.organization.id, item.id, kind=kind)
    commit(db)
    return metadata_view(item)


def require_unused(db, item):
    """No cascade. Student proficiency/history are protected; extend for classes/enrollments.

    Database FKs remain the final guard against deleting any referenced record.
    Previously published courses keep their identity even after returning to draft.
    """
    from app.models import LearningClass

    column = (
        LearningClass.course_id
        if isinstance(item, Course)
        else LearningClass.language_id
        if isinstance(item, CourseLanguage)
        else LearningClass.framework_id
        if isinstance(item, LevelFramework)
        else None
    )
    reference = (
        column == item.id
        if column is not None
        else or_(LearningClass.entry_level_id == item.id, LearningClass.exit_level_id == item.id)
    )
    if db.scalar(select(LearningClass.id).where(reference).limit(1)):
        raise APIError(409, "CATALOG_CLASS_IN_USE")
    if not isinstance(item, Course):
        from app.models import (
            TeacherHistory,
            TeacherHistoryLevel,
            TeachingCapability,
            TeachingCapabilityLevel,
        )

        references = (
            [(model, model.language_id) for model in (TeachingCapability, TeacherHistory)]
            if isinstance(item, CourseLanguage)
            else [
                (model, model.framework_id if isinstance(item, LevelFramework) else model.level_id)
                for model in (TeachingCapabilityLevel, TeacherHistoryLevel)
            ]
        )
        for model, column in references:
            if db.scalar(select(model.id).where(column == item.id).limit(1)):
                raise APIError(409, "CATALOG_TEACHER_IN_USE")
        from app.models import ProficiencyHistory, StudentProficiency

        for model in (StudentProficiency, ProficiencyHistory):
            condition = (
                model.language_id == item.id
                if isinstance(item, CourseLanguage)
                else model.framework_id == item.id
                if isinstance(item, LevelFramework)
                else or_(
                    model.self_level_id == item.id,
                    model.verified_level_id == item.id,
                    model.goal_level_id == item.id,
                )
            )
            if db.scalar(select(model.id).where(condition).limit(1)):
                raise APIError(409, "CATALOG_PROFICIENCY_IN_USE")
    if isinstance(item, Course):
        if item.status != "draft":
            raise APIError(409, "COURSE_DRAFT_REQUIRED")
        history = db.scalars(
            select(AuditLog).where(
                AuditLog.organization_id == item.organization_id,
                AuditLog.target_id == item.id,
                AuditLog.action == "course.state",
            )
        )
        if any(entry.details.get("status") == "published" for entry in history):
            raise APIError(409, "COURSE_PREVIOUSLY_PUBLISHED")
        return
    if isinstance(item, CourseLanguage):
        child = select(LevelFramework.id).where(LevelFramework.language_id == item.id)
        used = select(Course.id).where(Course.language_id == item.id)
    elif isinstance(item, LevelFramework):
        child = select(CourseLevel.id).where(CourseLevel.framework_id == item.id)
        used = select(Course.id).where(Course.framework_id == item.id)
    else:
        child = None
        used = select(Course.id).where(
            or_(
                Course.entry_level_id == item.id,
                Course.exit_level_id == item.id,
            )
        )
    if child is not None and db.scalar(child.limit(1)):
        raise APIError(409, "CATALOG_HAS_CHILDREN")
    if db.scalar(used.limit(1)):
        raise APIError(409, "CATALOG_IN_USE")


def correct_or_delete(db, tenant, item, data, kind, deleting=False):
    version(item, data.version)
    require_unused(db, item)
    previous_code = item.code
    if deleting:
        if data.code != item.code:
            raise APIError(422, "CATALOG_CONFIRMATION_MISMATCH")
        db.delete(item)
    else:
        item.code = data.code
        item.version += 1
    audit(
        db,
        tenant.actor,
        "catalog.delete" if deleting else "catalog.code_change",
        tenant.organization.id,
        item.id,
        kind=kind,
        reason=data.reason,
        previous_code=previous_code,
        code=data.code,
    )
    commit(db)


@router.patch("/course-settings/{kind}/{item_id}/code")
def setting_code(
    kind: Kind,
    item_id: UUID,
    data: CatalogCodeAction,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, MODELS[kind], tenant, item_id)
    correct_or_delete(db, tenant, item, data, kind)
    return metadata_view(item)


@router.delete("/course-settings/{kind}/{item_id}", status_code=204)
def delete_setting(
    kind: Kind,
    item_id: UUID,
    data: CatalogCodeAction,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, MODELS[kind], tenant, item_id)
    correct_or_delete(db, tenant, item, data, kind, deleting=True)


@router.patch("/courses/{course_id}/code")
def course_code(
    course_id: UUID,
    data: CatalogCodeAction,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, Course, tenant, course_id)
    correct_or_delete(db, tenant, item, data, "courses")
    return course_view(db, item)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(
    course_id: UUID,
    data: CatalogCodeAction,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, Course, tenant, course_id)
    correct_or_delete(db, tenant, item, data, "courses", deleting=True)


def validate_levels(db, tenant, data):
    if data.language_id:
        scoped(db, CourseLanguage, tenant, data.language_id)
    if data.framework_id:
        framework = scoped(db, LevelFramework, tenant, data.framework_id)
        if framework.language_id != data.language_id:
            raise APIError(422, "COURSE_LEVEL_MISMATCH")
    levels = []
    for item_id in (data.entry_level_id, data.exit_level_id):
        level = scoped(db, CourseLevel, tenant, item_id) if item_id else None
        if level and (
            level.framework_id != data.framework_id or level.language_id != data.language_id
        ):
            raise APIError(422, "COURSE_LEVEL_MISMATCH")
        levels.append(level)
    if all(levels) and levels[0].rank > levels[1].rank:
        raise APIError(422, "COURSE_LEVEL_ORDER")


def missing(item):
    return [
        name for name in ("language_id", "exit_level_id", "objectives") if not getattr(item, name)
    ]


def course_view(db, item, catalog=False):
    result = {
        name: getattr(item, name)
        for name in (
            "id",
            "code",
            "name",
            "description",
            "objectives",
            "entry_requirements",
            "completion_requirements",
            "language_id",
            "framework_id",
            "entry_level_id",
            "exit_level_id",
        )
    }
    for name, model in (
        ("language", CourseLanguage),
        ("framework", LevelFramework),
        ("entry_level", CourseLevel),
        ("exit_level", CourseLevel),
    ):
        reference = (
            db.get(model, getattr(item, name + "_id")) if getattr(item, name + "_id") else None
        )
        result[name] = {"code": reference.code, "name": reference.name} if reference else None
    if not catalog:
        result.update(status=item.status, version=item.version, missing_fields=missing(item))
    return result


def listing(db, tenant, catalog, q, status, language_id, exit_level_id, limit, offset):
    conditions = [Course.organization_id == tenant.organization.id]
    if catalog or status != "all":
        conditions.append(Course.status == ("published" if catalog else status))
    if q.strip():
        conditions.append(
            or_(
                Course.code.icontains(q.strip(), autoescape=True),
                Course.name.icontains(q.strip(), autoescape=True),
            )
        )
    if language_id:
        conditions.append(Course.language_id == language_id)
    if exit_level_id:
        conditions.append(Course.exit_level_id == exit_level_id)
    query = select(Course).where(*conditions)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            course_view(db, x, catalog)
            for x in db.scalars(
                query.order_by(Course.created_at.desc(), Course.id).limit(limit).offset(offset)
            )
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/courses")
def list_courses(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    q: Search = "",
    status: Literal["all", "draft", "published", "archived"] = "all",
    language_id: UUID | None = None,
    exit_level_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response)
    return listing(db, tenant, False, q, status, language_id, exit_level_id, limit, offset)


@router.post("/courses", status_code=201)
def create(data: CourseCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response)
    validate_levels(db, tenant, data)
    item = Course(organization_id=tenant.organization.id, **data.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "COURSE_CONFLICT") from error
    audit(db, tenant.actor, "course.create", tenant.organization.id, item.id)
    commit(db)
    return course_view(db, item)


@router.get("/courses/{course_id}")
def detail(course_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response)
    return course_view(db, scoped(db, Course, tenant, course_id))


@router.patch("/courses/{course_id}")
def change(
    course_id: UUID,
    data: CourseChange,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    authorize(db, tenant, request, response)
    item = scoped(db, Course, tenant, course_id)
    version(item, data.version)
    if item.status != "draft":
        raise APIError(409, "COURSE_DRAFT_REQUIRED")
    validate_levels(db, tenant, data)
    for name, value in data.model_dump(exclude={"version"}).items():
        setattr(item, name, value)
    item.version += 1
    audit(
        db,
        tenant.actor,
        "course.update",
        tenant.organization.id,
        item.id,
        fields=list(data.model_fields_set - {"version"}),
    )
    commit(db)
    return course_view(db, item)


@router.post("/courses/{course_id}/state")
def state(
    course_id: UUID, data: CourseState, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response, "manage")
    item = scoped(db, Course, tenant, course_id)
    version(item, data.version)
    allowed = {
        "draft": {"published", "archived"},
        "published": {"draft", "archived"},
        "archived": {"draft"},
    }
    if data.status not in allowed[item.status]:
        raise APIError(409, "COURSE_STATE_INVALID")
    if data.status == "published" and missing(item):
        raise APIError(422, "COURSE_INCOMPLETE")
    previous = item.status
    item.status = data.status
    item.version += 1
    audit(
        db,
        tenant.actor,
        "course.state",
        tenant.organization.id,
        item.id,
        previous=previous,
        status=data.status,
        reason=data.reason,
    )
    commit(db)
    return course_view(db, item)


@router.get("/course-catalog/options")
def catalog_options(db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "catalog")
    conditions = (Course.organization_id == tenant.organization.id, Course.status == "published")
    result = {}
    for name, model, field in (
        ("languages", CourseLanguage, Course.language_id),
        ("levels", CourseLevel, Course.exit_level_id),
    ):
        result[name] = [
            {"id": x.id, "name": x.name, "code": x.code}
            for x in db.scalars(
                select(model)
                .where(model.id.in_(select(field).where(*conditions)))
                .order_by(model.code, model.id)
            )
        ]
    return result


@router.get("/course-catalog")
def catalog(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    q: Search = "",
    language_id: UUID | None = None,
    exit_level_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response, "catalog")
    return listing(db, tenant, True, q, "published", language_id, exit_level_id, limit, offset)


@router.get("/course-catalog/{course_id}")
def catalog_detail(course_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "catalog")
    item = scoped(db, Course, tenant, course_id)
    if item.status != "published":
        raise APIError(404, "COURSE_NOT_FOUND")
    return course_view(db, item, catalog=True)
