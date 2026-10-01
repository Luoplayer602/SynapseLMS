"""Tenant-scoped library, curriculum and learner material delivery."""

import json
from datetime import UTC
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.dependencies import DB, Tenant, audit, auth_guard
from app.api.material_schemas import (
    AssignmentCreate,
    CurriculumBind,
    CurriculumCreate,
    Decision,
    LinkVersion,
    MaterialCreate,
    QuotaInput,
    UnitInput,
    UnitMaterialInput,
    VersionChange,
)
from app.api.routes.courses import Limit, Offset, authorize
from app.core.errors import APIError
from app.core.security import digest, now
from app.models import (
    ClassCurriculum,
    ClassSession,
    ClassTeacher,
    Course,
    CourseCurriculum,
    Curriculum,
    CurriculumMaterial,
    CurriculumUnit,
    CurriculumVersion,
    Enrollment,
    LearningClass,
    Material,
    MaterialAssignment,
    MaterialQuota,
    MaterialReview,
    MaterialVersion,
    Organization,
    SessionTeacher,
    StudentIdentity,
    TeacherProfile,
)
from app.services import admissions as admissions_svc
from app.services import materials as svc

router = APIRouter(prefix="/materials", dependencies=[Depends(auth_guard)])


def role(db, tenant, request, response):
    return authorize(db, tenant, request, response, "business_read")


def staff(db, tenant, request, response):
    current = role(db, tenant, request, response)
    if current not in {"organization_manager", "staff"}:
        raise APIError(403, "FORBIDDEN")
    return current


def scoped(db, model, tenant, row_id):
    row = db.scalar(
        select(model).where(model.id == row_id, model.organization_id == tenant.organization.id)
    )
    if not row:
        raise APIError(404, "BUSINESS_NOT_FOUND")
    return row


def teacher_access(db, tenant, class_id, session_id=None):
    profile = db.scalar(
        select(TeacherProfile).where(
            TeacherProfile.organization_id == tenant.organization.id,
            TeacherProfile.user_id == tenant.actor.user.id,
            TeacherProfile.archived_at.is_(None),
        )
    )
    if not profile:
        raise APIError(403, "FORBIDDEN")
    assigned = db.scalar(
        select(ClassTeacher.id).where(
            ClassTeacher.organization_id == tenant.organization.id,
            ClassTeacher.class_id == class_id,
            ClassTeacher.teacher_profile_id == profile.id,
        )
    )
    if not assigned and session_id:
        assigned = db.scalar(
            select(SessionTeacher.id).where(
                SessionTeacher.organization_id == tenant.organization.id,
                SessionTeacher.class_id == class_id,
                SessionTeacher.session_id == session_id,
                SessionTeacher.teacher_profile_id == profile.id,
            )
        )
    if not assigned:
        raise APIError(404, "BUSINESS_NOT_FOUND")


def material_view(row, version=None):
    result = {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "source": row.source,
        "language": row.language,
        "audience": row.audience,
        "scope": row.scope,
        "class_id": row.class_id,
        "session_id": row.session_id,
        "status": row.status,
        "version": row.version,
        "created_at": row.created_at,
    }
    if version:
        result["latest"] = version_view(version)
    return result


def version_view(row):
    return {
        "id": row.id,
        "material_id": row.material_id,
        "revision": row.revision,
        "kind": row.kind,
        "file_status": row.file_status,
        "filename": row.filename,
        "mime": row.mime,
        "size_bytes": row.size_bytes,
        "source_url": row.source_url,
        "published_at": row.published_at,
    }


def assignment_view(db, row):
    version = db.get(MaterialVersion, row.material_version_id)
    material = db.get(Material, version.material_id)
    return {
        "id": row.id,
        "class_id": row.class_id,
        "session_id": row.session_id,
        "publish_at": row.publish_at,
        "withdrawn_at": row.withdrawn_at,
        "material": {**material_view(material), **version.metadata_snapshot},
        "version": version_view(version),
    }


def latest(db, material_id):
    return db.scalar(
        select(MaterialVersion)
        .where(MaterialVersion.material_id == material_id)
        .order_by(MaterialVersion.revision.desc())
    )


def changeable(db, tenant, request, response, material):
    current = role(db, tenant, request, response)
    if current in {"organization_manager", "staff"}:
        return current
    if current == "teacher" and material.creator_id == tenant.actor.user.id:
        if material.class_id:
            teacher_access(db, tenant, material.class_id, material.session_id)
        return current
    raise APIError(403, "FORBIDDEN")


@router.get("")
def list_materials(
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
    query = select(Material).where(Material.organization_id == tenant.organization.id)
    if current == "teacher":
        profile = db.scalar(
            select(TeacherProfile).where(
                TeacherProfile.organization_id == tenant.organization.id,
                TeacherProfile.user_id == tenant.actor.user.id,
                TeacherProfile.archived_at.is_(None),
            )
        )
        ids = select(ClassTeacher.class_id).where(
            ClassTeacher.teacher_profile_id == (profile.id if profile else None)
        )
        sessions = select(SessionTeacher.session_id).where(
            SessionTeacher.teacher_profile_id == (profile.id if profile else None)
        )
        query = query.where(
            (Material.scope == "library") & (Material.status == "published")
            | ((Material.scope == "library") & (Material.creator_id == tenant.actor.user.id))
            | (Material.class_id.in_(ids))
            | (Material.session_id.in_(sessions))
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Material.created_at.desc(), Material.id).limit(limit).offset(offset)
    )
    return {"items": [material_view(row, latest(db, row.id)) for row in rows], "total": total}


@router.get("/classes")
def available_classes(db: DB, tenant: Tenant, request: Request, response: Response):
    current = role(db, tenant, request, response)
    if current == "student":
        raise APIError(403, "FORBIDDEN")
    query = select(LearningClass).where(LearningClass.organization_id == tenant.organization.id)
    if current == "teacher":
        profile = db.scalar(
            select(TeacherProfile).where(
                TeacherProfile.organization_id == tenant.organization.id,
                TeacherProfile.user_id == tenant.actor.user.id,
                TeacherProfile.archived_at.is_(None),
            )
        )
        if not profile:
            return {"items": []}
        assigned = select(ClassTeacher.class_id).where(
            ClassTeacher.teacher_profile_id == profile.id
        )
        substitute = select(SessionTeacher.class_id).where(
            SessionTeacher.teacher_profile_id == profile.id
        )
        query = query.where(LearningClass.id.in_(assigned.union(substitute)))
    return {
        "items": [
            {"id": row.id, "name": row.name}
            for row in db.scalars(query.order_by(LearningClass.name))
        ]
    }


@router.get("/classes/{class_id}/sessions")
def available_sessions(
    class_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response
):
    current = role(db, tenant, request, response)
    scoped(db, LearningClass, tenant, class_id)
    query = select(ClassSession).where(
        ClassSession.organization_id == tenant.organization.id,
        ClassSession.class_id == class_id,
        ClassSession.status == "scheduled",
    )
    if current == "teacher":
        profile = db.scalar(
            select(TeacherProfile).where(
                TeacherProfile.organization_id == tenant.organization.id,
                TeacherProfile.user_id == tenant.actor.user.id,
                TeacherProfile.archived_at.is_(None),
            )
        )
        if not profile:
            raise APIError(403, "FORBIDDEN")
        whole = db.scalar(
            select(ClassTeacher.id).where(
                ClassTeacher.class_id == class_id,
                ClassTeacher.teacher_profile_id == profile.id,
            )
        )
        if not whole:
            query = query.where(
                ClassSession.id.in_(
                    select(SessionTeacher.session_id).where(
                        SessionTeacher.teacher_profile_id == profile.id,
                    )
                )
            )
    elif current not in {"organization_manager", "staff"}:
        raise APIError(403, "FORBIDDEN")
    return {
        "items": [
            {"id": row.id, "starts_at": row.starts_at}
            for row in db.scalars(query.order_by(ClassSession.starts_at))
        ]
    }


@router.post("")
def create_material(
    body: MaterialCreate, db: DB, tenant: Tenant, request: Request, response: Response
):
    current = role(db, tenant, request, response)
    if current == "student":
        raise APIError(403, "FORBIDDEN")
    if body.session_id and not body.class_id:
        raise APIError(422, "MATERIAL_SESSION_MISMATCH")
    if body.class_id:
        scoped(db, LearningClass, tenant, body.class_id)
        if body.session_id:
            session = scoped(db, ClassSession, tenant, body.session_id)
            if session.class_id != body.class_id or session.status != "scheduled":
                raise APIError(409, "MATERIAL_SESSION_MISMATCH")
        if current == "teacher":
            teacher_access(db, tenant, body.class_id, body.session_id)
    row = Material(
        organization_id=tenant.organization.id,
        creator_id=tenant.actor.user.id,
        class_id=body.class_id,
        session_id=body.session_id,
        scope="class" if body.class_id else "library",
        **body.model_dump(exclude={"class_id", "session_id"}),
    )
    db.add(row)
    db.flush()
    audit(db, tenant.actor, "material.create", tenant.organization.id, row.id)
    db.commit()
    db.refresh(row)
    return material_view(row)


@router.get("/quota")
def get_quota(db: DB, tenant: Tenant, request: Request, response: Response):
    staff(db, tenant, request, response)
    return {
        "quota_bytes": svc.quota(db, tenant.organization.id),
        "used_bytes": svc.used(db, tenant.organization.id),
    }


@router.put("/quota")
def set_quota(body: QuotaInput, db: DB, tenant: Tenant, request: Request, response: Response):
    if role(db, tenant, request, response) != "organization_manager":
        raise APIError(403, "FORBIDDEN")
    db.scalar(
        select(Organization.id)
        .where(Organization.id == tenant.organization.id)
        .with_for_update()
    )
    if body.quota_bytes < svc.used(db, tenant.organization.id):
        raise APIError(409, "MATERIAL_QUOTA")
    row = db.scalar(
        select(MaterialQuota).where(MaterialQuota.organization_id == tenant.organization.id)
    )
    if not row:
        row = MaterialQuota(organization_id=tenant.organization.id, quota_bytes=body.quota_bytes)
        db.add(row)
    else:
        row.quota_bytes = body.quota_bytes
    db.commit()
    return {"quota_bytes": row.quota_bytes, "used_bytes": svc.used(db, tenant.organization.id)}


@router.patch("/{material_id}")
def edit_material(
    material_id: UUID,
    body: VersionChange,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    row = scoped(db, Material, tenant, material_id)
    changeable(db, tenant, request, response, row)
    if row.version != body.version or row.status != "draft":
        raise APIError(409, "MATERIAL_STALE")
    for name, value in body.model_dump(exclude={"version"}, exclude_none=True).items():
        setattr(row, name, value)
    db.commit()
    return material_view(row, latest(db, row.id))


@router.post("/{material_id}/versions/link")
def add_link(
    material_id: UUID,
    body: LinkVersion,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    row = scoped(db, Material, tenant, material_id)
    changeable(db, tenant, request, response, row)
    if row.status == "withdrawn":
        raise APIError(409, "MATERIAL_WITHDRAWN")
    db.scalar(
        select(Material)
        .where(Material.id == row.id, Material.organization_id == tenant.organization.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row.status == "withdrawn":
        raise APIError(409, "MATERIAL_WITHDRAWN")
    old = db.scalar(
        select(MaterialVersion).where(
            MaterialVersion.organization_id == tenant.organization.id,
            MaterialVersion.request_key == body.request_key,
        )
    )
    if old:
        if old.material_id != row.id or old.source_url != str(body.url):
            raise APIError(409, "MATERIAL_REQUEST_REUSED")
        return version_view(old)
    prior = latest(db, row.id)
    version = MaterialVersion(
        organization_id=tenant.organization.id,
        material_id=row.id,
        revision=prior.revision + 1 if prior else 1,
        request_key=body.request_key,
        kind="link",
        file_status="ready",
        source_url=str(body.url),
        metadata_snapshot={
            "title": row.title,
            "description": row.description,
            "source": row.source,
            "language": row.language,
            "audience": row.audience,
        },
        size_bytes=0,
    )
    db.add(version)
    db.flush()
    audit(db, tenant.actor, "material.version.link", tenant.organization.id, version.id)
    db.commit()
    db.refresh(version)
    return version_view(version)


@router.post("/{material_id}/versions/file")
def add_file(
    material_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    upload: Annotated[UploadFile, File()],
    request_key: Annotated[UUID, Form()],
):
    row = scoped(db, Material, tenant, material_id)
    changeable(db, tenant, request, response, row)
    if row.status == "withdrawn":
        raise APIError(409, "MATERIAL_WITHDRAWN")
    return version_view(svc.save_upload(db, tenant, row, upload, request_key, audit))


@router.post("/versions/{version_id}/retry-scan")
def retry_scan(version_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    version = scoped(db, MaterialVersion, tenant, version_id)
    material = scoped(db, Material, tenant, version.material_id)
    changeable(db, tenant, request, response, material)
    if version.file_status != "pending_check" or not version.object_key:
        raise APIError(409, "MATERIAL_SCAN_STATE")
    path = svc.safe_path(version.object_key)
    version.file_status = svc.scan(path)
    if version.file_status == "rejected":
        path.unlink(missing_ok=True)
        version.object_key = None
    audit(db, tenant.actor, "material.version.retry_scan", tenant.organization.id, version.id)
    db.commit()
    return version_view(version)


@router.post("/versions/{version_id}/submit")
def submit(version_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    version = scoped(db, MaterialVersion, tenant, version_id)
    material = scoped(db, Material, tenant, version.material_id)
    if (
        role(db, tenant, request, response) != "teacher"
        or material.creator_id != tenant.actor.user.id
    ):
        raise APIError(403, "FORBIDDEN")
    if material.class_id:
        teacher_access(db, tenant, material.class_id, material.session_id)
    if version.file_status != "ready":
        raise APIError(409, "MATERIAL_NOT_READY")
    pending = db.scalar(
        select(MaterialReview.id).where(
            MaterialReview.material_version_id == version.id, MaterialReview.status == "pending"
        )
    )
    if pending:
        raise APIError(409, "MATERIAL_REVIEW_PENDING")
    review = MaterialReview(
        organization_id=tenant.organization.id,
        material_version_id=version.id,
        requester_id=tenant.actor.user.id,
    )
    db.add(review)
    db.flush()
    audit(db, tenant.actor, "material.review.submit", tenant.organization.id, review.id)
    db.commit()
    return {"id": review.id, "status": review.status}


@router.get("/reviews")
def reviews(db: DB, tenant: Tenant, request: Request, response: Response):
    staff(db, tenant, request, response)
    rows = db.scalars(
        select(MaterialReview)
        .where(MaterialReview.organization_id == tenant.organization.id)
        .order_by(MaterialReview.created_at.desc())
        .limit(100)
    )
    return {
        "items": [
            {
                "id": r.id,
                "material_version_id": r.material_version_id,
                "status": r.status,
                "reason": r.reason,
            }
            for r in rows
        ]
    }


@router.post("/reviews/{review_id}/decision")
def decide(
    review_id: UUID,
    approve: bool,
    body: Decision,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = scoped(db, MaterialReview, tenant, review_id)
    if row.status != "pending" or (not approve and len(body.reason.strip()) < 3):
        raise APIError(409, "MATERIAL_REVIEW_STATE")
    version = scoped(db, MaterialVersion, tenant, row.material_version_id)
    material = scoped(db, Material, tenant, version.material_id)
    row.status = "approved" if approve else "rejected"
    row.reviewer_id = tenant.actor.user.id
    row.reason = body.reason.strip()
    if approve:
        if version.file_status != "ready":
            raise APIError(409, "MATERIAL_NOT_READY")
        material.scope = "library"
        material.class_id = None
        material.session_id = None
        material.status = "published"
        version.published_at = now()
    audit(
        db,
        tenant.actor,
        "material.review.approve" if approve else "material.review.reject",
        tenant.organization.id,
        row.id,
        reason=row.reason,
    )
    db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/versions/{version_id}/publish")
def publish(version_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    version = scoped(db, MaterialVersion, tenant, version_id)
    material = scoped(db, Material, tenant, version.material_id)
    current = changeable(db, tenant, request, response, material)
    if version.file_status != "ready" or material.status == "withdrawn":
        raise APIError(409, "MATERIAL_NOT_READY")
    if current == "teacher" and material.scope != "class":
        raise APIError(403, "FORBIDDEN")
    version.published_at = version.published_at or now()
    material.status = "published"
    audit(db, tenant.actor, "material.publish", tenant.organization.id, version.id)
    db.commit()
    return material_view(material, version)


@router.post("/{material_id}/archive")
def archive(material_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    material = scoped(db, Material, tenant, material_id)
    changeable(db, tenant, request, response, material)
    if material.status != "published":
        raise APIError(409, "MATERIAL_STATE")
    material.status = "archived"
    audit(db, tenant.actor, "material.archive", tenant.organization.id, material.id)
    db.commit()
    return material_view(material)


@router.post("/{material_id}/withdraw")
def withdraw(
    material_id: UUID, body: Decision, db: DB, tenant: Tenant, request: Request, response: Response
):
    material = scoped(db, Material, tenant, material_id)
    changeable(db, tenant, request, response, material)
    if len(body.reason.strip()) < 3:
        raise APIError(422, "BUSINESS_REASON_REQUIRED")
    material.status = "withdrawn"
    material.withdrawn_reason = body.reason.strip()
    audit(
        db,
        tenant.actor,
        "material.withdraw",
        tenant.organization.id,
        material.id,
        reason=material.withdrawn_reason,
    )
    db.commit()
    return material_view(material)


@router.post("/assignments")
def assign(body: AssignmentCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    current = role(db, tenant, request, response)
    if current == "student":
        raise APIError(403, "FORBIDDEN")
    fingerprint = digest(json.dumps(body.model_dump(mode="json"), sort_keys=True))
    old = db.scalar(
        select(MaterialAssignment).where(
            MaterialAssignment.organization_id == tenant.organization.id,
            MaterialAssignment.request_key == body.request_key,
        )
    )
    if old:
        if old.fingerprint != fingerprint:
            raise APIError(409, "MATERIAL_REQUEST_REUSED")
        return assignment_view(db, old)
    classroom = scoped(db, LearningClass, tenant, body.class_id)
    version = scoped(db, MaterialVersion, tenant, body.material_version_id)
    material = scoped(db, Material, tenant, version.material_id)
    if (
        material.status != "published"
        or not version.published_at
        or version.file_status != "ready"
        or (material.class_id and material.class_id != classroom.id)
        or (material.session_id and material.session_id != body.session_id)
    ):
        raise APIError(409, "MATERIAL_NOT_READY")
    if body.session_id:
        session = scoped(db, ClassSession, tenant, body.session_id)
        if session.class_id != classroom.id or session.status != "scheduled":
            raise APIError(409, "MATERIAL_SESSION_MISMATCH")
    if current == "teacher":
        teacher_access(db, tenant, classroom.id, body.session_id)
    row = MaterialAssignment(
        organization_id=tenant.organization.id,
        material_version_id=version.id,
        class_id=classroom.id,
        session_id=body.session_id,
        publish_at=body.publish_at.astimezone(UTC) if body.publish_at else now(),
        request_key=body.request_key,
        fingerprint=fingerprint,
        actor_id=tenant.actor.user.id,
    )
    db.add(row)
    db.flush()
    audit(db, tenant.actor, "material.assign", tenant.organization.id, row.id)
    db.commit()
    db.refresh(row)
    return assignment_view(db, row)


@router.get("/assignments")
def assignments(db: DB, tenant: Tenant, request: Request, response: Response, class_id: UUID):
    current = role(db, tenant, request, response)
    scoped(db, LearningClass, tenant, class_id)
    if current == "student":
        raise APIError(403, "FORBIDDEN")
    query = select(MaterialAssignment).where(
        MaterialAssignment.organization_id == tenant.organization.id,
        MaterialAssignment.class_id == class_id,
    )
    if current == "teacher":
        try:
            teacher_access(db, tenant, class_id)
        except APIError:
            profile = db.scalar(
                select(TeacherProfile).where(
                    TeacherProfile.organization_id == tenant.organization.id,
                    TeacherProfile.user_id == tenant.actor.user.id,
                    TeacherProfile.archived_at.is_(None),
                )
            )
            if not profile:
                raise APIError(403, "FORBIDDEN") from None
            allowed = select(SessionTeacher.session_id).where(
                SessionTeacher.organization_id == tenant.organization.id,
                SessionTeacher.class_id == class_id,
                SessionTeacher.teacher_profile_id == profile.id,
            )
            query = query.where(MaterialAssignment.session_id.in_(allowed))
    rows = db.scalars(query.order_by(MaterialAssignment.publish_at.desc()))
    return {"items": [assignment_view(db, row) for row in rows]}


@router.post("/assignments/{assignment_id}/withdraw")
def withdraw_assignment(
    assignment_id: UUID,
    body: Decision,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    row = scoped(db, MaterialAssignment, tenant, assignment_id)
    current = role(db, tenant, request, response)
    if current == "teacher":
        teacher_access(db, tenant, row.class_id, row.session_id)
    elif current not in {"organization_manager", "staff"}:
        raise APIError(403, "FORBIDDEN")
    if len(body.reason.strip()) < 3:
        raise APIError(422, "BUSINESS_REASON_REQUIRED")
    row.withdrawn_at = now()
    row.reason = body.reason.strip()
    audit(
        db,
        tenant.actor,
        "material.assignment.withdraw",
        tenant.organization.id,
        row.id,
        reason=row.reason,
    )
    db.commit()
    return assignment_view(db, row)


def learner_rows(db, tenant):
    profile = admissions_svc.own_student(db, tenant)
    rows = db.execute(
        select(MaterialAssignment, Enrollment)
        .join(Enrollment, Enrollment.class_id == MaterialAssignment.class_id)
        .where(
            MaterialAssignment.organization_id == tenant.organization.id,
            Enrollment.organization_id == tenant.organization.id,
            Enrollment.student_id == profile.id,
            MaterialAssignment.publish_at <= now(),
            MaterialAssignment.withdrawn_at.is_(None),
        )
    ).all()
    for assignment, enrollment in rows:
        version = db.get(MaterialVersion, assignment.material_version_id)
        material = db.get(Material, version.material_id)
        if material.status == "withdrawn" or material.audience != "students":
            continue
        if svc.own_grant(db, tenant.organization.id, enrollment, assignment):
            identity = db.get(StudentIdentity, profile.identity_id)
            svc.notify_grant(db, tenant.organization.id, identity.user_id, assignment)
            yield assignment


@router.get("/mine")
def mine(db: DB, tenant: Tenant, request: Request, response: Response):
    if role(db, tenant, request, response) != "student":
        raise APIError(403, "FORBIDDEN")
    items = [assignment_view(db, row) for row in learner_rows(db, tenant)]
    db.commit()
    return {"items": items, "total": len(items)}


def content_access(db, tenant, request, response, version):
    current = role(db, tenant, request, response)
    material = scoped(db, Material, tenant, version.material_id)
    if version.file_status != "ready" or material.status == "withdrawn":
        raise APIError(404, "BUSINESS_NOT_FOUND")
    if current in {"organization_manager", "staff"}:
        return
    if current == "teacher":
        if material.creator_id == tenant.actor.user.id:
            if material.class_id:
                teacher_access(db, tenant, material.class_id, material.session_id)
            return
        if material.scope == "library" and material.status in {"published", "archived"}:
            return
        if material.class_id:
            try:
                teacher_access(db, tenant, material.class_id, material.session_id)
                return
            except APIError:
                pass
        for assignment in db.scalars(
            select(MaterialAssignment).where(
                MaterialAssignment.material_version_id == version.id,
                MaterialAssignment.organization_id == tenant.organization.id,
                MaterialAssignment.session_id.is_not(None),
                MaterialAssignment.withdrawn_at.is_(None),
            )
        ):
            try:
                teacher_access(db, tenant, assignment.class_id, assignment.session_id)
                return
            except APIError:
                continue
    if current == "student" and material.audience == "students":
        if any(row.material_version_id == version.id for row in learner_rows(db, tenant)):
            db.commit()
            return
    raise APIError(404, "BUSINESS_NOT_FOUND")


@router.get("/versions/{version_id}/content")
def content(version_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    version = scoped(db, MaterialVersion, tenant, version_id)
    content_access(db, tenant, request, response, version)
    if not version.object_key:
        return {"url": version.source_url}
    path = svc.safe_path(version.object_key)
    size = version.size_bytes
    start, end = 0, size - 1
    status = 200
    if range_value := request.headers.get("range"):
        if not range_value.startswith("bytes=") or "," in range_value:
            raise APIError(416, "MATERIAL_RANGE")
        try:
            left, right = range_value[6:].split("-", 1)
            if not left:
                length = int(right)
                start = max(0, size - length)
            else:
                start = int(left)
                end = int(right) if right else size - 1
            if start < 0 or start >= size or end < start or end >= size:
                raise ValueError
        except ValueError as error:
            raise APIError(416, "MATERIAL_RANGE") from error
        status = 206

    def stream():
        with path.open("rb") as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Content-Disposition": f'inline; filename="{version.filename.replace(chr(34), "")}"',
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(stream(), status_code=status, media_type=version.mime, headers=headers)


@router.get("/curricula")
def curricula(db: DB, tenant: Tenant, request: Request, response: Response):
    staff(db, tenant, request, response)
    rows = db.scalars(
        select(Curriculum)
        .where(Curriculum.organization_id == tenant.organization.id)
        .order_by(Curriculum.title)
    )
    return {
        "items": [
            {"id": r.id, "title": r.title, "author": r.author, "status": r.status} for r in rows
        ]
    }


@router.post("/curricula")
def create_curriculum(
    body: CurriculumCreate, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    row = Curriculum(organization_id=tenant.organization.id, **body.model_dump())
    db.add(row)
    db.flush()
    version = CurriculumVersion(
        organization_id=tenant.organization.id, curriculum_id=row.id, revision=1
    )
    db.add(version)
    db.commit()
    return {"id": row.id, "version_id": version.id, "revision": 1}


@router.post("/curricula/{curriculum_id}/clone")
def clone_curriculum(
    curriculum_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    row = scoped(db, Curriculum, tenant, curriculum_id)
    prior = db.scalar(
        select(CurriculumVersion)
        .where(CurriculumVersion.curriculum_id == row.id)
        .order_by(CurriculumVersion.revision.desc())
    )
    version = CurriculumVersion(
        organization_id=tenant.organization.id, curriculum_id=row.id, revision=prior.revision + 1
    )
    db.add(version)
    db.flush()
    parent_map = {}
    for unit in db.scalars(
        select(CurriculumUnit)
        .where(CurriculumUnit.curriculum_version_id == prior.id)
        .order_by(CurriculumUnit.position)
    ):
        copy = CurriculumUnit(
            organization_id=tenant.organization.id,
            curriculum_version_id=version.id,
            title=unit.title,
            position=unit.position,
            parent_id=parent_map.get(unit.parent_id),
        )
        db.add(copy)
        db.flush()
        parent_map[unit.id] = copy.id
        for item in db.scalars(
            select(CurriculumMaterial).where(CurriculumMaterial.unit_id == unit.id)
        ):
            db.add(
                CurriculumMaterial(
                    organization_id=tenant.organization.id,
                    unit_id=copy.id,
                    material_version_id=item.material_version_id,
                    page_hint=item.page_hint,
                    required=item.required,
                )
            )
    db.commit()
    return {"id": version.id, "revision": version.revision}


@router.get("/curricula/{curriculum_id}")
def curriculum_detail(
    curriculum_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    row = scoped(db, Curriculum, tenant, curriculum_id)
    versions = db.scalars(
        select(CurriculumVersion)
        .where(CurriculumVersion.curriculum_id == row.id)
        .order_by(CurriculumVersion.revision.desc())
    )
    result = []
    for version in versions:
        units = db.scalars(
            select(CurriculumUnit)
            .where(CurriculumUnit.curriculum_version_id == version.id)
            .order_by(CurriculumUnit.position)
        )
        result.append(
            {
                "id": version.id,
                "revision": version.revision,
                "status": version.status,
                "units": [
                    {
                        "id": unit.id,
                        "title": unit.title,
                        "position": unit.position,
                        "materials": [
                            {
                                "material_version_id": item.material_version_id,
                                "page_hint": item.page_hint,
                                "required": item.required,
                            }
                            for item in db.scalars(
                                select(CurriculumMaterial).where(
                                    CurriculumMaterial.unit_id == unit.id
                                )
                            )
                        ],
                    }
                    for unit in units
                ],
            }
        )
    return {"id": row.id, "title": row.title, "versions": result}


@router.post("/curriculum-versions/{version_id}/units")
def add_unit(
    version_id: UUID, body: UnitInput, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    version = scoped(db, CurriculumVersion, tenant, version_id)
    if version.status != "draft":
        raise APIError(409, "MATERIAL_VERSION_LOCKED")
    if body.parent_id:
        parent = scoped(db, CurriculumUnit, tenant, body.parent_id)
        if parent.curriculum_version_id != version.id:
            raise APIError(409, "MATERIAL_UNIT_MISMATCH")
    row = CurriculumUnit(
        organization_id=tenant.organization.id,
        curriculum_version_id=version.id,
        **body.model_dump(),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "title": row.title, "position": row.position}


@router.post("/curriculum-units/{unit_id}/materials")
def add_unit_material(
    unit_id: UUID,
    body: UnitMaterialInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    unit = scoped(db, CurriculumUnit, tenant, unit_id)
    release = scoped(db, CurriculumVersion, tenant, unit.curriculum_version_id)
    version = scoped(db, MaterialVersion, tenant, body.material_version_id)
    material = scoped(db, Material, tenant, version.material_id)
    if release.status != "draft" or material.status != "published" or not version.published_at:
        raise APIError(409, "MATERIAL_NOT_READY")
    row = CurriculumMaterial(
        organization_id=tenant.organization.id, unit_id=unit.id, **body.model_dump()
    )
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.post("/curriculum-versions/{version_id}/publish")
def publish_curriculum(
    version_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    version = scoped(db, CurriculumVersion, tenant, version_id)
    if version.status != "draft" or not db.scalar(
        select(CurriculumUnit.id).where(CurriculumUnit.curriculum_version_id == version.id)
    ):
        raise APIError(409, "MATERIAL_VERSION_LOCKED")
    version.status = "published"
    version.published_at = now()
    audit(db, tenant.actor, "curriculum.publish", tenant.organization.id, version.id)
    db.commit()
    return {"id": version.id, "status": version.status}


@router.post("/courses/{course_id}/curricula")
def bind_course(
    course_id: UUID,
    body: CurriculumBind,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    scoped(db, Course, tenant, course_id)
    version = scoped(db, CurriculumVersion, tenant, body.curriculum_version_id)
    if version.status != "published":
        raise APIError(409, "MATERIAL_NOT_READY")
    old = db.scalar(
        select(CourseCurriculum).where(
            CourseCurriculum.organization_id == tenant.organization.id,
            CourseCurriculum.course_id == course_id,
            CourseCurriculum.curriculum_version_id == version.id,
        )
    )
    if old:
        return {"id": old.id}
    if body.primary:
        for current in db.scalars(
            select(CourseCurriculum).where(
                CourseCurriculum.organization_id == tenant.organization.id,
                CourseCurriculum.course_id == course_id,
                CourseCurriculum.primary.is_(True),
            )
        ):
            current.primary = False
    row = CourseCurriculum(
        organization_id=tenant.organization.id,
        course_id=course_id,
        curriculum_version_id=version.id,
        primary=body.primary,
    )
    db.add(row)
    db.flush()
    audit(db, tenant.actor, "curriculum.bind.course", tenant.organization.id, row.id)
    db.commit()
    return {"id": row.id}


@router.post("/classes/{class_id}/curricula")
def bind_class(
    class_id: UUID,
    body: CurriculumBind,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    classroom = scoped(db, LearningClass, tenant, class_id)
    version = scoped(db, CurriculumVersion, tenant, body.curriculum_version_id)
    if version.status != "published" or not db.scalar(
        select(CourseCurriculum.id).where(
            CourseCurriculum.course_id == classroom.course_id,
            CourseCurriculum.curriculum_version_id == version.id,
        )
    ):
        raise APIError(409, "MATERIAL_CURRICULUM_MISMATCH")
    old = db.scalar(
        select(ClassCurriculum).where(
            ClassCurriculum.organization_id == tenant.organization.id,
            ClassCurriculum.class_id == class_id,
            ClassCurriculum.curriculum_version_id == version.id,
        )
    )
    if old:
        return {"id": old.id}
    if body.primary:
        previous = list(
            db.scalars(
                select(ClassCurriculum).where(
                    ClassCurriculum.organization_id == tenant.organization.id,
                    ClassCurriculum.class_id == class_id,
                    ClassCurriculum.primary.is_(True),
                )
            )
        )
        if previous and len(body.reason.strip()) < 3:
            raise APIError(422, "BUSINESS_REASON_REQUIRED")
        for current in previous:
            current.primary = False
    row = ClassCurriculum(
        organization_id=tenant.organization.id,
        class_id=class_id,
        curriculum_version_id=version.id,
        primary=body.primary,
        reason=body.reason,
    )
    db.add(row)
    db.flush()
    audit(
        db, tenant.actor, "curriculum.bind.class", tenant.organization.id, row.id, reason=row.reason
    )
    db.commit()
    return {"id": row.id}


@router.get("/classes/{class_id}/curricula")
def class_curricula(class_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    current = role(db, tenant, request, response)
    scoped(db, LearningClass, tenant, class_id)
    if current == "teacher":
        teacher_access(db, tenant, class_id)
    elif current == "student":
        raise APIError(403, "FORBIDDEN")
    rows = db.scalars(
        select(ClassCurriculum).where(
            ClassCurriculum.organization_id == tenant.organization.id,
            ClassCurriculum.class_id == class_id,
        )
    )
    return {
        "items": [
            {
                "id": row.id,
                "curriculum_version_id": row.curriculum_version_id,
                "primary": row.primary,
                "reason": row.reason,
            }
            for row in rows
        ]
    }
