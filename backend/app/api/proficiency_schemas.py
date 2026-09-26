from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.api.schemas import Input, Reason


class ProficiencyCreate(Input):
    framework_id: UUID


class Versioned(Input):
    version: int = Field(ge=1)


class Declaration(Versioned):
    self_level_id: UUID | None


class Goals(Versioned):
    goal_text: Annotated[str, Field(max_length=5000)] = ""
    goal_level_id: UUID | None = None
    target_date: date | None = None


class Verification(Versioned):
    action: Literal["verify", "revoke"]
    level_id: UUID | None = None
    source: Annotated[str, Field(max_length=500)] = ""
    evidence: Annotated[str, Field(max_length=5000)] = ""
    reason: Reason
