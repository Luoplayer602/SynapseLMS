from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantContext:
    organization_id: UUID
    actor_id: UUID
    support_session_id: UUID | None = None


class TenantContextMissingError(RuntimeError):
    """Raised when a tenant-scoped operation has no authenticated tenant context."""

