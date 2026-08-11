from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class StudyArticleRole(StrEnum):
    PRIMARY = "PRIMARY"
    PROTOCOL = "PROTOCOL"
    FOLLOW_UP = "FOLLOW_UP"
    SUBGROUP = "SUBGROUP"
    SECONDARY_ANALYSIS = "SECONDARY_ANALYSIS"
    CONFERENCE_ABSTRACT = "CONFERENCE_ABSTRACT"
    CORRECTION = "CORRECTION"
    SUPPLEMENT = "SUPPLEMENT"
    OTHER = "OTHER"


class StudyLinkMethod(StrEnum):
    MANUAL = "MANUAL"
    EXACT_REGISTRY_MATCH = "EXACT_REGISTRY_MATCH"
    METADATA_MATCH = "METADATA_MATCH"
    AI_SUGGESTED = "AI_SUGGESTED"
    IMPORTED = "IMPORTED"


@dataclass(frozen=True, slots=True)
class Study:
    id: UUID
    organization_id: UUID
    review_id: UUID
    study_key: str
    label: str | None
    study_design: str | None
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StudyArticleLink:
    id: UUID
    study_id: UUID
    article_id: UUID
    organization_id: UUID
    review_id: UUID
    role: StudyArticleRole
    method: StudyLinkMethod
    reason: str | None
    confidence: float | None
    source_evidence: dict[str, Any] | None
    linked_by_user_id: UUID
    created_at: datetime
    unlinked_at: datetime | None
    unlinked_by_user_id: UUID | None

    @property
    def active(self) -> bool:
        return self.unlinked_at is None
