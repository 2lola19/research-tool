from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

REPORT_SCHEMA_VERSION = "structured-review-report-1"
PACKAGE_SCHEMA_VERSION = "review-reproducibility-package-1"
REPORT_RENDERER_VERSION = "deterministic-report-renderer-1"
ABSOLUTE_EFFECT_FORMULA_VERSION = "absolute-effect-1"


class ReportType(StrEnum):
    INTERNAL_REVIEW_REPORT = "INTERNAL_REVIEW_REPORT"
    STRUCTURED_REVIEW_REPORT = "STRUCTURED_REVIEW_REPORT"
    EVIDENCE_PROFILE = "EVIDENCE_PROFILE"
    SUMMARY_OF_FINDINGS = "SUMMARY_OF_FINDINGS"
    REPRODUCIBILITY_PACKAGE = "REPRODUCIBILITY_PACKAGE"


class ReportFormat(StrEnum):
    JSON = "JSON"
    XLSX = "XLSX"
    HTML = "HTML"
    ZIP = "ZIP"


class ReportStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReportCurrency(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"


class BaselineRiskSource(StrEnum):
    CONTROL_GROUP_MEDIAN = "CONTROL_GROUP_MEDIAN"
    EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"
    PREDEFINED_PROTOCOL_VALUE = "PREDEFINED_PROTOCOL_VALUE"
    OBSERVED_CONTROL_RISK = "OBSERVED_CONTROL_RISK"
    OTHER_EXPLICIT_SOURCE = "OTHER_EXPLICIT_SOURCE"


@dataclass(frozen=True, slots=True)
class ReportingReadiness:
    report_type: ReportType
    ready: bool
    blockers: tuple[dict[str, Any], ...]
    source_preview: dict[str, Any]
    included_components: tuple[str, ...]
    excluded_components: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportSpecification:
    id: UUID
    organization_id: UUID
    review_id: UUID
    logical_key: str
    version: int
    report_type: ReportType
    definition: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    id: UUID
    organization_id: UUID
    review_id: UUID
    specification_id: UUID
    status: ReportStatus
    source_references: dict[str, Any]
    source_hashes: dict[str, Any]
    structured_content: dict[str, Any] | None
    scientific_content_hash: str | None
    renderer_version: str
    created_by_user_id: UUID
    created_at: datetime
    completed_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class ReportArtifact:
    id: UUID
    organization_id: UUID
    review_id: UUID
    report_snapshot_id: UUID
    report_format: ReportFormat
    filename: str
    media_type: str
    sha256: str
    byte_size: int
    manifest: dict[str, Any]
    created_at: datetime
    content: bytes | None = None


@dataclass(frozen=True, slots=True)
class RenderedReport:
    content: bytes
    media_type: str
    extension: str
    manifest: dict[str, Any]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def calculate_absolute_effect(
    *, relative_measure: str, relative_effect: str, baseline_risk: str
) -> dict[str, str]:
    """Transform an explicit baseline risk without altering the relative effect."""
    try:
        effect = Decimal(relative_effect)
        baseline = Decimal(baseline_risk)
    except InvalidOperation as exc:
        raise ValueError("relative effect and baseline risk must be decimal values") from exc
    if baseline < 0 or baseline > 1:
        raise ValueError("baseline risk must be a probability from 0 through 1")
    measure = relative_measure.upper()
    if measure == "RR":
        treated = baseline * effect
    elif measure == "OR":
        denominator = Decimal(1) - baseline + effect * baseline
        if denominator == 0:
            raise ValueError("odds-ratio absolute-effect denominator is zero")
        treated = effect * baseline / denominator
    else:
        raise ValueError("absolute effect is supported only for RR and OR")
    return {
        "baseline_risk": format(baseline, "f"),
        "treated_risk": format(treated, "f"),
        "risk_difference": format(treated - baseline, "f"),
        "formula_version": ABSOLUTE_EFFECT_FORMULA_VERSION,
    }
