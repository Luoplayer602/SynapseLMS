"""Root AI settings and tenant task opt-in."""

from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.ai_schemas import (
    PromptInput,
    PromptPublish,
    ProviderInput,
    RouteInput,
    TenantTaskInput,
)
from app.api.dependencies import DB, Root, Tenant, audit, auth_guard
from app.api.routes.courses import authorize
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import now
from app.models import (
    AdmissionRequest,
    AIActivePrompt,
    AIPrompt,
    AIProvider,
    AIRoute,
    AIRun,
    AITenantSetting,
)
from app.services.ai import progress
from app.services.ai.prompts import render, validate_template
from app.services.ai.providers import LOCAL_KINDS, complete, encrypt_credential, validate_base_url
from app.services.ai.recommendations import recommend

router = APIRouter(prefix="/ai", dependencies=[Depends(auth_guard)])


@router.get("/recommendations/requests/{request_id}")
def class_recommendations(
    request_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    locale: Literal["vi", "en"] = "vi",
):
    authorize(db, tenant, request, response)
    row = db.scalar(
        select(AdmissionRequest).where(
            AdmissionRequest.id == request_id,
            AdmissionRequest.organization_id == tenant.organization.id,
        )
    )
    if not row:
        raise APIError(404, "BUSINESS_NOT_FOUND")
    return recommend(db, tenant, row, locale)


@router.get("/progress/mine")
def my_progress(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    locale: Literal["vi", "en"] = "vi",
):
    if authorize(db, tenant, request, response, "business_read") != "student":
        raise APIError(403, "FORBIDDEN")
    return progress.student(db, tenant, locale)


@router.get("/progress/classes/{class_id}")
def class_progress(
    class_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    locale: Literal["vi", "en"] = "vi",
):
    from app.api.routes.results import class_access

    if authorize(db, tenant, request, response, "business_read") != "teacher":
        raise APIError(403, "FORBIDDEN")
    class_access(db, tenant, request, response, class_id)
    return progress.teacher_class(db, tenant, class_id, locale)


def provider_view(row):
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "kind": row.kind,
        "base_url": row.base_url,
        "model_id": row.model_id,
        "has_key": bool(row.credential_ciphertext),
        "enabled": row.enabled,
        "allowed_tasks": row.allowed_tasks,
        "timeout_seconds": row.timeout_seconds,
        "max_output_tokens": row.max_output_tokens,
        "max_daily_calls": row.max_daily_calls,
        "version": row.version,
    }


def root_provider(db, provider_id):
    row = db.get(AIProvider, provider_id)
    if not row:
        raise APIError(404, "AI_PROVIDER_NOT_FOUND")
    return row


@router.get("/providers")
def providers(db: DB, root: Root):
    return {
        "items": [
            provider_view(row) for row in db.scalars(select(AIProvider).order_by(AIProvider.name))
        ]
    }


@router.post("/providers")
def create_provider(body: ProviderInput, db: DB, root: Root):
    base = validate_base_url(body.kind, body.base_url)
    if body.enabled and body.kind not in LOCAL_KINDS and not body.api_key:
        raise APIError(422, "AI_KEY_REQUIRED")
    cipher = encrypt_credential(body.api_key, get_settings().ai_key_file) if body.api_key else None
    row = AIProvider(
        code=body.code,
        name=body.name,
        kind=body.kind,
        base_url=base,
        model_id=body.model_id,
        credential_ciphertext=cipher,
        credential_key_version=1 if cipher else None,
        enabled=body.enabled,
        allowed_tasks=list(set(body.allowed_tasks)),
        timeout_seconds=body.timeout_seconds,
        max_output_tokens=body.max_output_tokens,
        max_daily_calls=body.max_daily_calls,
    )
    db.add(row)
    audit(db, root, "ai.provider.create", target_id=row.id, code=row.code)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "AI_PROVIDER_CONFLICT") from error
    return provider_view(row)


@router.put("/providers/{provider_id}")
def update_provider(provider_id: UUID, body: ProviderInput, db: DB, root: Root):
    row = root_provider(db, provider_id)
    if body.version != row.version:
        raise APIError(409, "AI_PROVIDER_STALE")
    if body.code != row.code or body.kind != row.kind:
        raise APIError(409, "AI_PROVIDER_IDENTITY_FIXED")
    row.name = body.name
    row.base_url = validate_base_url(body.kind, body.base_url)
    row.model_id = body.model_id
    row.allowed_tasks = list(set(body.allowed_tasks))
    row.timeout_seconds = body.timeout_seconds
    row.max_output_tokens = body.max_output_tokens
    row.max_daily_calls = body.max_daily_calls
    if body.api_key:
        row.credential_ciphertext = encrypt_credential(body.api_key, get_settings().ai_key_file)
        row.credential_key_version = 1
    if body.enabled and row.kind not in LOCAL_KINDS and not row.credential_ciphertext:
        raise APIError(422, "AI_KEY_REQUIRED")
    row.enabled = body.enabled
    audit(db, root, "ai.provider.update", target_id=row.id, code=row.code)
    db.commit()
    return provider_view(row)


@router.post("/providers/{provider_id}/test")
def test_provider(provider_id: UUID, db: DB, root: Root):
    row = root_provider(db, provider_id)
    audit(db, root, "ai.provider.test", target_id=row.id)
    db.commit()
    result = complete(
        row, "Return JSON object with ok=true.", {"sample": "ping"}, get_settings().ai_key_file
    )
    return {"ok": result.get("ok") is True, "structured_output": isinstance(result, dict)}


@router.get("/routes")
def routes(db: DB, root: Root):
    return {
        "items": [
            {"task": r.task, "provider_id": r.provider_id, "priority": r.priority}
            for r in db.scalars(select(AIRoute).order_by(AIRoute.task, AIRoute.priority))
        ]
    }


@router.put("/routes")
def set_routes(body: RouteInput, db: DB, root: Root):
    if len(set(body.provider_ids)) != len(body.provider_ids):
        raise APIError(422, "AI_ROUTE_DUPLICATE")
    rows = [root_provider(db, key) for key in body.provider_ids]
    if any(body.task not in row.allowed_tasks for row in rows):
        raise APIError(422, "AI_TASK_UNSUPPORTED")
    db.execute(delete(AIRoute).where(AIRoute.task == body.task))
    db.flush()
    db.add_all(
        [AIRoute(task=body.task, provider_id=row.id, priority=i + 1) for i, row in enumerate(rows)]
    )
    audit(db, root, "ai.route.update", task=body.task)
    db.commit()
    return {"task": body.task, "provider_ids": body.provider_ids}


@router.get("/prompts")
def prompts(db: DB, root: Root):
    active = {(x.task, x.locale): x.prompt_id for x in db.scalars(select(AIActivePrompt))}
    return {
        "items": [
            {
                "id": p.id,
                "task": p.task,
                "locale": p.locale,
                "revision": p.revision,
                "status": p.status,
                "body": p.body,
                "active": active.get((p.task, p.locale)) == p.id,
            }
            for p in db.scalars(
                select(AIPrompt).order_by(AIPrompt.task, AIPrompt.locale, AIPrompt.revision.desc())
            )
        ]
    }


@router.post("/prompts")
def create_prompt(body: PromptInput, db: DB, root: Root):
    validate_template(body.body)
    last = (
        db.scalar(
            select(func.max(AIPrompt.revision)).where(
                AIPrompt.task == body.task,
                AIPrompt.locale == body.locale,
            )
        )
        or 0
    )
    row = AIPrompt(
        task=body.task,
        locale=body.locale,
        revision=last + 1,
        body=body.body,
        status="draft",
        actor_id=root.user.id,
    )
    db.add(row)
    audit(db, root, "ai.prompt.create", target_id=row.id, task=row.task)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "AI_PROMPT_CONFLICT") from error
    return {"id": row.id, "revision": row.revision, "status": row.status}


@router.post("/prompts/{prompt_id}/test")
def test_prompt(prompt_id: UUID, db: DB, root: Root):
    row = db.get(AIPrompt, prompt_id)
    if not row:
        raise APIError(404, "AI_PROMPT_NOT_FOUND")
    # A syntax/safety smoke test never uses live student data or billable providers.
    rendered = render(row.body, row.task, row.locale)
    row.status = "tested" if row.status == "draft" else row.status
    audit(db, root, "ai.prompt.test", target_id=row.id)
    db.commit()
    return {"valid": True, "rendered_length": len(rendered)}


@router.post("/prompts/{prompt_id}/publish")
def publish_prompt(prompt_id: UUID, body: PromptPublish, db: DB, root: Root):
    row = db.get(AIPrompt, prompt_id)
    if not row:
        raise APIError(404, "AI_PROMPT_NOT_FOUND")
    if row.status not in {"tested", "published", "retired"}:
        raise APIError(409, "AI_PROMPT_NOT_TESTED")
    current = db.scalar(
        select(AIActivePrompt)
        .where(
            AIActivePrompt.task == row.task,
            AIActivePrompt.locale == row.locale,
        )
        .with_for_update()
    )
    if current:
        previous = db.get(AIPrompt, current.prompt_id)
        if previous and previous.id != row.id:
            previous.status = "retired"
        current.prompt_id = row.id
    else:
        db.add(AIActivePrompt(task=row.task, locale=row.locale, prompt_id=row.id))
    row.status = "published"
    row.published_at = now()
    audit(db, root, "ai.prompt.publish", target_id=row.id, reason=body.reason)
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/tenant-tasks")
def tenant_tasks(db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    return {
        "items": [
            {
                "task": x.task,
                "enabled": x.enabled,
                "max_daily_calls": x.max_daily_calls,
                "timezone": x.timezone,
            }
            for x in db.scalars(
                select(AITenantSetting).where(
                    AITenantSetting.organization_id == tenant.organization.id
                )
            )
        ]
    }


@router.put("/tenant-tasks")
def set_tenant_task(
    body: TenantTaskInput, db: DB, tenant: Tenant, request: Request, response: Response
):
    authorize(db, tenant, request, response, "manage")
    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError as error:
        raise APIError(422, "AI_TIMEZONE_INVALID") from error
    row = db.scalar(
        select(AITenantSetting).where(
            AITenantSetting.organization_id == tenant.organization.id,
            AITenantSetting.task == body.task,
        )
    )
    if not row:
        row = AITenantSetting(organization_id=tenant.organization.id, task=body.task)
        db.add(row)
    row.enabled = body.enabled
    row.max_daily_calls = body.max_daily_calls
    row.timezone = body.timezone
    audit(db, tenant.actor, "ai.tenant_task.update", tenant.organization.id, row.id, task=body.task)
    db.commit()
    return {
        "task": row.task,
        "enabled": row.enabled,
        "max_daily_calls": row.max_daily_calls,
        "timezone": row.timezone,
    }


@router.get("/usage")
def usage(db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    rows = db.execute(
        select(AIRun.task, AIRun.status, func.count(AIRun.id), func.sum(AIRun.output_tokens))
        .where(
            AIRun.organization_id == tenant.organization.id,
        )
        .group_by(AIRun.task, AIRun.status)
    ).all()
    return {
        "items": [
            {"task": task, "status": status, "count": count, "output_tokens": tokens or 0}
            for task, status, count, tokens in rows
        ]
    }
