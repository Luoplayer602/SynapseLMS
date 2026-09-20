from uuid import uuid4

from app.core.tenant import TenantContext


def test_tenant_context_is_immutable() -> None:
    context = TenantContext(organization_id=uuid4(), actor_id=uuid4())

    assert context.support_session_id is None

