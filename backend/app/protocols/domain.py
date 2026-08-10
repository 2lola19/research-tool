from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ProtocolDecisionKind(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def protocol_content_hash(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProtocolVersion:
    id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    content: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProtocolDecision:
    id: UUID
    protocol_version_id: UUID
    organization_id: UUID
    review_id: UUID
    decision: ProtocolDecisionKind
    decided_by_user_id: UUID
    reason: str | None
    decided_at: datetime
