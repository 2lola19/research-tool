from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

CERTAINTY_ALGORITHM_VERSION = "certainty-adjustment-1"
EVIDENCE_SNAPSHOT_VERSION = "certainty-evidence-1"
SOF_MODEL_VERSION = "sof-model-1"


class CertaintyLevel(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class EvidenceBodyType(StrEnum):
    RANDOMIZED = "RANDOMIZED"
    OBSERVATIONAL = "OBSERVATIONAL"
    MIXED = "MIXED"
    OTHER = "OTHER"


class CertaintyAssessmentStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"


class CertaintyComparisonStatus(StrEnum):
    AGREEMENT = "AGREEMENT"
    CONFLICT = "CONFLICT"
    ADJUDICATED = "ADJUDICATED"


class AdjustmentDirection(StrEnum):
    DOWNGRADE = "DOWNGRADE"
    UPGRADE = "UPGRADE"


LEVEL_ORDER = (
    CertaintyLevel.VERY_LOW,
    CertaintyLevel.LOW,
    CertaintyLevel.MODERATE,
    CertaintyLevel.HIGH,
)


@dataclass(frozen=True, slots=True)
class CertaintyFramework:
    id: UUID
    organization_id: UUID
    review_id: UUID
    key: str
    name: str
    description: str | None
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CertaintyFrameworkVersion:
    id: UUID
    framework_id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    definition: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DecisionThresholdVersion:
    id: UUID
    organization_id: UUID
    review_id: UUID
    outcome_version_id: UUID
    version: int
    definition: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CertaintyDomainJudgment:
    id: UUID
    assessment_id: UUID
    domain_key: str
    direction: AdjustmentDirection
    magnitude: int
    judgment: str
    rationale: str
    evidence_location_id: UUID | None
    evidence: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CertaintyAssessment:
    id: UUID
    organization_id: UUID
    review_id: UUID
    outcome_version_id: UUID
    timepoint_window_id: UUID | None
    analysis_specification_version_id: UUID | None
    meta_analysis_run_id: UUID | None
    framework_version_id: UUID
    threshold_version_id: UUID | None
    assessor_user_id: UUID
    round_number: int
    revision: int
    supersedes_assessment_id: UUID | None
    evidence_body_type: EvidenceBodyType
    evidence_body: dict[str, Any]
    starting_certainty: CertaintyLevel
    starting_rationale: str
    status: CertaintyAssessmentStatus
    candidate_certainty: CertaintyLevel | None
    final_certainty: CertaintyLevel | None
    final_rationale: str | None
    override_reason: str | None
    evidence_snapshot: dict[str, Any] | None
    evidence_hash: str | None
    created_at: datetime
    submitted_at: datetime | None
    domain_judgments: tuple[CertaintyDomainJudgment, ...]


@dataclass(frozen=True, slots=True)
class CertaintyComparison:
    id: UUID
    organization_id: UUID
    review_id: UUID
    outcome_version_id: UUID
    framework_version_id: UUID
    round_number: int
    assessment_a_id: UUID
    assessment_b_id: UUID
    status: CertaintyComparisonStatus
    differences: tuple[dict[str, Any], ...]
    compared_by_user_id: UUID
    compared_at: datetime
    adjudicated_snapshot: dict[str, Any] | None
    adjudicated_by_user_id: UUID | None
    adjudication_reason: str | None
    adjudication_evidence_location_id: UUID | None
    adjudicated_at: datetime | None


@dataclass(frozen=True, slots=True)
class SummaryOfFindingsSnapshot:
    id: UUID
    organization_id: UUID
    review_id: UUID
    assessment_id: UUID
    model_version: str
    row: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


def canonical_hash(value: Any) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def normalize_framework_definition(definition: dict[str, Any]) -> dict[str, Any]:
    raw_domains = definition.get("domains")
    if not isinstance(raw_domains, list) or not raw_domains:
        raise ValueError("certainty framework requires domains")
    domains: list[dict[str, Any]] = []
    keys: set[str] = set()
    for order, raw in enumerate(raw_domains):
        if not isinstance(raw, dict):
            raise ValueError("certainty domains must be objects")
        key = _key(raw.get("key"), "domain key")
        if key in keys:
            raise ValueError("certainty domain keys must be unique")
        keys.add(key)
        direction = AdjustmentDirection(_key(raw.get("direction"), "domain direction"))
        choices = _choices(raw.get("choices"), direction)
        domains.append(
            {
                "key": key,
                "label": _text(raw.get("label"), "domain label"),
                "direction": direction.value,
                "guidance": _optional(raw.get("guidance")),
                "choices": choices,
                "order": order,
            }
        )
    rules = definition.get("starting_rules")
    if not isinstance(rules, dict):
        raise ValueError("certainty framework requires structured starting rules")
    normalized_rules: dict[str, str] = {}
    for body_type in EvidenceBodyType:
        if body_type.value not in rules:
            raise ValueError("starting rules must cover every evidence body type")
        normalized_rules[body_type.value] = CertaintyLevel(str(rules[body_type.value])).value
    return {
        "name": _text(definition.get("name"), "framework name"),
        "version_label": _text(definition.get("version_label"), "framework version label"),
        "guidance": _optional(definition.get("guidance")),
        "starting_rules": normalized_rules,
        "domains": domains,
        "certainty_levels": [item.value for item in reversed(LEVEL_ORDER)],
    }


def normalize_threshold_definition(definition: dict[str, Any]) -> dict[str, Any]:
    unit = _text(definition.get("unit"), "threshold unit")
    values: dict[str, str | None] = {}
    for key in ("minimally_important_difference", "appreciable_benefit", "appreciable_harm"):
        raw = definition.get(key)
        values[key] = str(raw).strip() if raw is not None and str(raw).strip() else None
    if all(value is None for value in values.values()):
        raise ValueError("at least one decision threshold is required")
    return {
        **values,
        "unit": unit,
        "scale": _optional(definition.get("scale")),
        "rationale": _text(definition.get("rationale"), "threshold rationale"),
        "source": _text(definition.get("source"), "threshold source"),
    }


def calculate_candidate_certainty(
    starting: CertaintyLevel, judgments: tuple[CertaintyDomainJudgment, ...]
) -> CertaintyLevel:
    index = LEVEL_ORDER.index(starting)
    delta = sum(
        item.magnitude if item.direction == AdjustmentDirection.UPGRADE else -item.magnitude
        for item in judgments
    )
    return LEVEL_ORDER[max(0, min(len(LEVEL_ORDER) - 1, index + delta))]


def assessment_snapshot(assessment: CertaintyAssessment) -> dict[str, Any]:
    return {
        "starting_certainty": assessment.starting_certainty.value,
        "starting_rationale": assessment.starting_rationale,
        "domains": {
            item.domain_key: {
                "direction": item.direction.value,
                "magnitude": item.magnitude,
                "judgment": item.judgment,
                "rationale": item.rationale,
                "evidence_location_id": (
                    str(item.evidence_location_id) if item.evidence_location_id else None
                ),
                "evidence": item.evidence,
            }
            for item in assessment.domain_judgments
        },
        "candidate_certainty": (
            assessment.candidate_certainty.value if assessment.candidate_certainty else None
        ),
        "final_certainty": (
            assessment.final_certainty.value if assessment.final_certainty else None
        ),
        "final_rationale": assessment.final_rationale,
        "override_reason": assessment.override_reason,
        "evidence_hash": assessment.evidence_hash,
    }


def compare_assessments(
    first: CertaintyAssessment, second: CertaintyAssessment
) -> tuple[dict[str, Any], ...]:
    differences: list[dict[str, Any]] = []
    if first.starting_certainty != second.starting_certainty:
        differences.append(
            {
                "scope": "starting_certainty",
                "key": "starting_certainty",
                "value_a": first.starting_certainty.value,
                "value_b": second.starting_certainty.value,
            }
        )
    first_domains = {
        item.domain_key: (item.direction.value, item.magnitude, item.judgment)
        for item in first.domain_judgments
    }
    second_domains = {
        item.domain_key: (item.direction.value, item.magnitude, item.judgment)
        for item in second.domain_judgments
    }
    for key in sorted(set(first_domains) | set(second_domains)):
        if first_domains.get(key) != second_domains.get(key):
            differences.append(
                {
                    "scope": "domain",
                    "key": key,
                    "value_a": first_domains.get(key),
                    "value_b": second_domains.get(key),
                }
            )
    if first.final_certainty != second.final_certainty:
        differences.append(
            {
                "scope": "final_certainty",
                "key": "final_certainty",
                "value_a": first.final_certainty.value if first.final_certainty else None,
                "value_b": second.final_certainty.value if second.final_certainty else None,
            }
        )
    return tuple(differences)


def _choices(value: Any, direction: AdjustmentDirection) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("certainty domain requires adjustment choices")
    choices: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("adjustment choices must be objects")
        key = _key(raw.get("value"), "adjustment choice")
        magnitude = int(raw.get("magnitude", -1))
        if key in seen or magnitude < 0 or magnitude > 2:
            raise ValueError("adjustment choices and magnitudes must be unique and between 0 and 2")
        seen.add(key)
        choices.append(
            {
                "value": key,
                "label": _text(raw.get("label"), "adjustment label"),
                "magnitude": magnitude,
                "direction": direction.value,
            }
        )
    return choices


def _key(value: Any, label: str) -> str:
    result = str(value or "").strip().upper()
    if (
        not result
        or len(result) > 120
        or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in result)
    ):
        raise ValueError(f"{label} is invalid")
    return result


def _text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _optional(value: Any) -> str | None:
    result = str(value or "").strip()
    return result or None
