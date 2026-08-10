from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ProvenanceActorKind(StrEnum):
    HUMAN = "HUMAN"
    AI = "AI"
    SYSTEM = "SYSTEM"


class VerificationState(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    REJECTED = "REJECTED"


class AIRunStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class PromptVersion:
    id: UUID
    organization_id: UUID
    prompt_key: str
    version: int
    template: str
    output_schema: dict[str, Any]
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AIRun:
    id: UUID
    organization_id: UUID
    review_id: UUID
    prompt_version_id: UUID
    provider: str
    model_name: str
    model_version: str
    parameters: dict[str, Any]
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any] | None
    status: AIRunStatus
    usage: dict[str, Any]
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ScientificProvenance:
    id: UUID
    organization_id: UUID
    review_id: UUID
    subject_type: str
    subject_id: UUID
    source_type: str | None
    source_id: UUID | None
    source_locator: dict[str, Any]
    method_name: str
    method_version: str
    actor_kind: ProvenanceActorKind
    actor_user_id: UUID | None
    ai_run_id: UUID | None
    confidence: float | None
    verification_state: VerificationState
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    organization_id: UUID
    review_id: UUID | None
    entity_type: str
    entity_id: UUID
    action: str
    actor_user_id: UUID
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None
    reason: str | None
    occurred_at: datetime
