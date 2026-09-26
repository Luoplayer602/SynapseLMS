from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import DB, Tenant, audit, auth_guard
from app.api.proficiency_schemas import Declaration, Goals, ProficiencyCreate, Verification
from app.api.routes import students
from app.api.routes.courses import MODELS, Kind, Limit, Offset
from app.core.errors import APIError
from app.core.security import now, utc
from app.models import (
    CourseLanguage,
    CourseLevel,
    LevelFramework,
    ProficiencyHistory,
    StudentProficiency,
    User,
)

router = APIRouter(dependencies=[Depends(auth_guard)])


def profile_access(db, tenant, request, response, profile_ref, writing=False):
    personal = profile_ref == "me"
    students.access(db, tenant, request, response, personal=personal)
    if personal:
        profile = students.personal_id(db, tenant)
    else:
        try:
            profile_id = UUID(profile_ref)
        except ValueError as error:
            raise APIError(404, "STUDENT_NOT_FOUND") from error
        profile = students.scoped(db, tenant, profile_id)
    if writing and profile.archived_at:
        raise APIError(409, "STUDENT_ARCHIVED")
    return profile, personal


def item_for(db, profile, item_id):
    item = db.scalar(
        select(StudentProficiency).where(
            StudentProficiency.id == item_id,
            StudentProficiency.student_profile_id == profile.id,
            StudentProficiency.organization_id == profile.organization_id,
        )
    )
    if not item:
        raise APIError(404, "PROFICIENCY_NOT_FOUND")
    return item


def level_for(db, item, level_id):
    if level_id is not None and not db.scalar(
        select(CourseLevel.id).where(
            CourseLevel.id == level_id,
            CourseLevel.organization_id == item.organization_id,
            CourseLevel.framework_id == item.framework_id,
            CourseLevel.language_id == item.language_id,
        )
    ):
        raise APIError(422, "PROFICIENCY_LEVEL_MISMATCH")


def label(db, model, item_id):
    item = db.get(model, item_id) if item_id else None
    return {"id": item.id, "code": item.code, "name": item.name} if item else None


def view(db, item, personal=False):
    result = {
        field: getattr(item, field)
        for field in (
            "id",
            "version",
            "language_id",
            "framework_id",
            "self_level_id",
            "self_declared_at",
            "verified_level_id",
            "verified_at",
            "goal_level_id",
            "goal_text",
            "target_date",
            "goals_updated_at",
        )
    }
    for field in ("self_declared_at", "verified_at", "goals_updated_at"):
        if result[field]:
            result[field] = utc(result[field])
    result.update(
        language=label(db, CourseLanguage, item.language_id),
        framework=label(db, LevelFramework, item.framework_id),
        self_level=label(db, CourseLevel, item.self_level_id),
        verified_level=label(db, CourseLevel, item.verified_level_id),
        goal_level=label(db, CourseLevel, item.goal_level_id),
    )
    author = db.get(User, item.verified_by) if item.verified_by else None
    result["verified_by_name"] = author.display_name if author else None
    if not personal:
        result.update(verification_source=item.verification_source, evidence=item.evidence)
    return result


def record(db, tenant, item, action, reason=""):
    try:
        db.flush()
        snapshot = jsonable_encoder(view(db, item, personal=True))
        snapshot.update(
            action=action,
            actor_name=tenant.actor.user.display_name,
            actor_role="root" if tenant.actor.user.is_root_admin else tenant.role,
            occurred_at=now().isoformat(),
        )
        db.add(
            ProficiencyHistory(
                organization_id=item.organization_id,
                proficiency_id=item.id,
                language_id=item.language_id,
                framework_id=item.framework_id,
                self_level_id=item.self_level_id,
                verified_level_id=item.verified_level_id,
                goal_level_id=item.goal_level_id,
                actor_id=tenant.actor.user.id,
                version=item.version,
                public_snapshot=snapshot,
                internal_snapshot={
                    "source": item.verification_source,
                    "evidence": item.evidence,
                    "reason": reason,
                },
            )
        )
        audit(
            db,
            tenant.actor,
            "proficiency." + action,
            item.organization_id,
            item.id,
            version=item.version,
        )
        db.commit()
    except (IntegrityError, StaleDataError) as error:
        db.rollback()
        raise APIError(409, "PROFICIENCY_CONFLICT") from error


@router.get("/student-proficiency-options/{kind}")
def options(
    kind: Kind,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 100,
    offset: Offset = 0,
):
    students.access(db, tenant, request, response, personal=tenant.role == "student")
    model = MODELS[kind]
    query = select(model).where(model.organization_id == tenant.organization.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            {
                field: getattr(item, field)
                for field in ("id", "code", "name", "language_id", "framework_id", "rank")
                if hasattr(item, field)
            }
            for item in db.scalars(query.order_by(model.id).limit(limit).offset(offset))
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/student-proficiencies/{profile_ref}")
def listing(
    profile_ref: str,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    profile, personal = profile_access(db, tenant, request, response, profile_ref)
    query = select(StudentProficiency).where(
        StudentProficiency.student_profile_id == profile.id,
        StudentProficiency.organization_id == profile.organization_id,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            view(db, item, personal)
            for item in db.scalars(
                query.order_by(StudentProficiency.created_at, StudentProficiency.id)
                .limit(limit)
                .offset(offset)
            )
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/student-proficiencies/{profile_ref}", status_code=201)
def create(
    profile_ref: str,
    data: ProficiencyCreate,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    profile, personal = profile_access(db, tenant, request, response, profile_ref, writing=True)
    framework = db.scalar(
        select(LevelFramework).where(
            LevelFramework.id == data.framework_id,
            LevelFramework.organization_id == profile.organization_id,
        )
    )
    if not framework:
        raise APIError(422, "PROFICIENCY_LEVEL_MISMATCH")
    item = StudentProficiency(
        student_profile_id=profile.id,
        organization_id=profile.organization_id,
        language_id=framework.language_id,
        framework_id=framework.id,
    )
    db.add(item)
    record(db, tenant, item, "create")
    return view(db, item, personal)


@router.get("/student-proficiencies/{profile_ref}/{item_id}/history")
def history(
    profile_ref: str,
    item_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    profile, personal = profile_access(db, tenant, request, response, profile_ref)
    item = item_for(db, profile, item_id)
    query = select(ProficiencyHistory).where(
        ProficiencyHistory.proficiency_id == item.id,
        ProficiencyHistory.organization_id == profile.organization_id,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            {
                **entry.public_snapshot,
                "id": entry.id,
                **({} if personal else {"internal": entry.internal_snapshot}),
            }
            for entry in db.scalars(
                query.order_by(ProficiencyHistory.version.desc()).limit(limit).offset(offset)
            )
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/student-proficiencies/{profile_ref}/{item_id}")
def detail(
    profile_ref: str, item_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response
):
    profile, personal = profile_access(db, tenant, request, response, profile_ref)
    return view(db, item_for(db, profile, item_id), personal)


def writable(db, tenant, request, response, profile_ref, item_id, expected):
    profile, personal = profile_access(db, tenant, request, response, profile_ref, writing=True)
    item = item_for(db, profile, item_id)
    if item.version != expected:
        raise APIError(409, "PROFICIENCY_CONFLICT")
    return item, personal


@router.patch("/student-proficiencies/{profile_ref}/{item_id}/declaration")
def declare(
    profile_ref: str,
    item_id: UUID,
    data: Declaration,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    item, personal = writable(db, tenant, request, response, profile_ref, item_id, data.version)
    if not personal:
        raise APIError(403, "FORBIDDEN")
    level_for(db, item, data.self_level_id)
    item.self_level_id, item.self_declared_at = data.self_level_id, now()
    item.version += 1
    record(db, tenant, item, "declare")
    return view(db, item, personal)


@router.patch("/student-proficiencies/{profile_ref}/{item_id}/goals")
def goals(
    profile_ref: str,
    item_id: UUID,
    data: Goals,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    item, personal = writable(db, tenant, request, response, profile_ref, item_id, data.version)
    level_for(db, item, data.goal_level_id)
    item.goal_level_id, item.goal_text, item.target_date = (
        data.goal_level_id,
        data.goal_text,
        data.target_date,
    )
    item.goals_updated_at = now()
    item.version += 1
    record(db, tenant, item, "goals")
    return view(db, item, personal)


@router.post("/student-proficiencies/{profile_ref}/{item_id}/verification")
def verify(
    profile_ref: str,
    item_id: UUID,
    data: Verification,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    item, personal = writable(db, tenant, request, response, profile_ref, item_id, data.version)
    if personal:
        raise APIError(403, "FORBIDDEN")
    if data.action == "verify":
        if not data.level_id or not data.source.strip() or not data.evidence.strip():
            raise APIError(422, "PROFICIENCY_EVIDENCE_REQUIRED")
        level_for(db, item, data.level_id)
        item.verified_level_id, item.verified_at, item.verified_by = (
            data.level_id,
            now(),
            tenant.actor.user.id,
        )
        item.verification_source, item.evidence = data.source, data.evidence
    else:
        if not item.verified_at:
            raise APIError(409, "PROFICIENCY_NOT_VERIFIED")
        item.verified_level_id = item.verified_at = item.verified_by = None
        item.verification_source = item.evidence = ""
    item.version += 1
    record(db, tenant, item, data.action, data.reason)
    return view(db, item, personal)
