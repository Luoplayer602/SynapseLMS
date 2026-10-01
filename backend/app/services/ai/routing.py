"""Task routing, tenant opt-in and conservative provider failover."""

import hashlib
import json
from datetime import timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import now
from app.models import AIActivePrompt, AIPrompt, AIProvider, AIRoute, AIRun, AITenantSetting
from app.services.ai import prompts, providers


def digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def invoke(db, tenant, task: str, locale: str, payload: dict, validator):
    setting = db.scalar(
        select(AITenantSetting).where(
            AITenantSetting.organization_id == tenant.organization.id,
            AITenantSetting.task == task,
            AITenantSetting.enabled.is_(True),
        )
    )
    if not setting:
        return None
    active = db.scalar(
        select(AIActivePrompt).where(
            AIActivePrompt.task == task,
            AIActivePrompt.locale == locale,
        )
    )
    prompt = db.get(AIPrompt, active.prompt_id) if active else None
    if not prompt or prompt.status != "published":
        return None
    today = now().date()
    count = db.scalar(
        select(func.count(AIRun.id)).where(
            AIRun.organization_id == tenant.organization.id,
            AIRun.task == task,
            AIRun.created_at >= today,
        )
    )
    if count >= setting.max_daily_calls:
        return None
    routes = db.execute(
        select(AIRoute, AIProvider)
        .join(AIProvider)
        .where(
            AIRoute.task == task,
            AIProvider.enabled.is_(True),
        )
        .order_by(AIRoute.priority)
    ).all()
    for _, provider in routes:
        if task not in provider.allowed_tasks:
            continue
        db.scalar(select(AIProvider.id).where(AIProvider.id == provider.id).with_for_update())
        used = db.scalar(
            select(func.count(AIRun.id)).where(
                AIRun.provider_id == provider.id,
                AIRun.created_at >= today,
            )
        )
        recent_failures = db.scalar(
            select(func.count(AIRun.id)).where(
                AIRun.provider_id == provider.id,
                AIRun.status == "failed",
                AIRun.created_at >= now() - timedelta(minutes=5),
            )
        )
        if used >= provider.max_daily_calls or recent_failures >= 3:
            continue
        run = AIRun(
            organization_id=tenant.organization.id,
            actor_id=tenant.actor.user.id,
            task=task,
            provider_id=provider.id,
            prompt_id=prompt.id,
            input_digest=digest(payload),
            status="reserved",
            source_refs=payload.get("source_refs", []),
        )
        db.add(run)
        db.flush()
        run_id = run.id
        db.commit()  # Release tenant/provider locks before waiting on an external endpoint.
        try:
            output = providers.complete(
                provider,
                prompts.render(prompt.body, task, locale),
                payload,
                get_settings().ai_key_file,
            )
            output_tokens = output.pop("_provider_tokens", 0)
            value = validator(output)
            record = db.get(AIRun, run_id)
            record.status = "ok"
            record.output_tokens = output_tokens
            db.commit()
            return value, run_id
        except (APIError, ValueError, TypeError, KeyError):
            db.get(AIRun, run_id).status = "failed"
            db.commit()
            continue
    return None
