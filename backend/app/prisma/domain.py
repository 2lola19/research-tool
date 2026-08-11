from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PrismaSummary:
    records_identified_databases: int
    records_identified_other_sources: int
    records_removed_duplicates: int
    records_removed_other_reasons: int
    records_screened: int
    records_excluded_title_abstract: int
    reports_sought_for_retrieval: int
    reports_not_retrieved: int
    reports_assessed_for_eligibility: int
    reports_excluded_full_text: int
    studies_included_review: int
    reports_of_included_studies: int
    studies_included_meta_analysis: int | None
    full_text_exclusion_reasons: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "records_identified_databases": self.records_identified_databases,
            "records_identified_other_sources": self.records_identified_other_sources,
            "records_removed_duplicates": self.records_removed_duplicates,
            "records_removed_other_reasons": self.records_removed_other_reasons,
            "records_screened": self.records_screened,
            "records_excluded_title_abstract": self.records_excluded_title_abstract,
            "reports_sought_for_retrieval": self.reports_sought_for_retrieval,
            "reports_not_retrieved": self.reports_not_retrieved,
            "reports_assessed_for_eligibility": self.reports_assessed_for_eligibility,
            "reports_excluded_full_text": self.reports_excluded_full_text,
            "studies_included_review": self.studies_included_review,
            "reports_of_included_studies": self.reports_of_included_studies,
            "studies_included_meta_analysis": self.studies_included_meta_analysis,
            "full_text_exclusion_reasons": self.full_text_exclusion_reasons,
        }


@dataclass(frozen=True, slots=True)
class PrismaBlocker:
    code: str
    message: str
    count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "count": self.count}


@dataclass(frozen=True, slots=True)
class PrismaReadiness:
    ready_for_final: bool
    blockers: tuple[PrismaBlocker, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready_for_final": self.ready_for_final,
            "blockers": [item.as_dict() for item in self.blockers],
        }


@dataclass(frozen=True, slots=True)
class PrismaSnapshot:
    id: UUID
    organization_id: UUID
    review_id: UUID
    created_by_user_id: UUID
    algorithm_version: str
    counts: dict[str, Any]
    readiness: dict[str, Any]
    source_references: dict[str, Any]
    created_at: datetime
