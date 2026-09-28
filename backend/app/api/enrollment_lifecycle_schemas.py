from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.api.admission_schemas import Change, Input


class LifecyclePreview(Change):
    action: Literal["suspend", "cancel", "resume"]
    session_id: UUID | None = None
    reason: str = Field(min_length=3, max_length=500)


class LifecycleInput(LifecyclePreview):
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class PolicyInput(Change):
    kind: Literal["fixed", "percent"]
    value: int = Field(ge=0, le=1_000_000_000, strict=True)

    @model_validator(mode="after")
    def percent(self):
        if self.kind == "percent" and self.value > 100:
            raise ValueError("percentage exceeds 100")
        return self


class RefundPreview(Input):
    request_id: UUID


class RefundCreate(RefundPreview):
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class RefundDecision(Change):
    action: Literal["approve", "reject", "cancel"]
    amount: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    reason: str = Field(default="", max_length=500)


class DisbursementInput(Change):
    method: Literal["cash", "transfer"]
    reference: str = Field(default="", max_length=200)
