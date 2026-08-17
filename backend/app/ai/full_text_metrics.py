from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.app.ai.screening_domain import (
    AIScreeningSuggestion,
    ScreeningEvaluationPolicy,
    ScreeningReferenceDecision,
)
from backend.app.ai.screening_metrics import ScreeningPrediction, evaluate_screening_predictions

FULL_TEXT_METRIC_VERSION = "ai-full-text-screening-metrics-1"


@dataclass(frozen=True, slots=True)
class FullTextPrediction:
    case_id: UUID
    article_id: UUID
    document_id: UUID
    proposal_id: UUID
    reference: ScreeningReferenceDecision
    suggestion: AIScreeningSuggestion
    confidence: float
    reference_criterion_id: str | None
    proposed_criterion_ids: tuple[str, ...]
    evidence_issue_codes: tuple[str, ...] = ()
    evidence_sections: tuple[str, ...] = ()


def evaluate_full_text_predictions(
    predictions: list[FullTextPrediction], policy: ScreeningEvaluationPolicy
) -> dict[str, Any]:
    base = evaluate_screening_predictions(
        [
            ScreeningPrediction(
                case_id=item.case_id,
                article_id=item.article_id,
                proposal_id=item.proposal_id,
                reference=item.reference,
                suggestion=item.suggestion,
                confidence=item.confidence,
            )
            for item in predictions
        ],
        policy,
    )
    ai_excludes = [item for item in predictions if item.suggestion is AIScreeningSuggestion.EXCLUDE]
    correct_decision = [
        item for item in ai_excludes if item.reference is ScreeningReferenceDecision.EXCLUDE
    ]
    correct_criterion = [
        item
        for item in correct_decision
        if item.reference_criterion_id is not None
        and item.reference_criterion_id in item.proposed_criterion_ids
    ]
    wrong_criterion = [
        item
        for item in correct_decision
        if item.reference_criterion_id is not None
        and item.reference_criterion_id not in item.proposed_criterion_ids
    ]
    issue_counts: dict[str, int] = {}
    section_counts: dict[str, int] = {}
    for item in predictions:
        for issue in item.evidence_issue_codes:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        for section in item.evidence_sections or ("unknown",):
            normalized = section.strip().casefold() or "unknown"
            section_counts[normalized] = section_counts.get(normalized, 0) + 1
    fully_valid = sum(not item.evidence_issue_codes for item in predictions)
    total = len(predictions)
    base.update(
        {
            "metric_version": FULL_TEXT_METRIC_VERSION,
            "stage": "FULL_TEXT",
            "criterion_level": {
                "ai_exclude_cases": len(ai_excludes),
                "correct_exclusion_and_criterion": len(correct_criterion),
                "correct_exclusion_wrong_criterion": len(wrong_criterion),
                "wrong_exclusion": sum(
                    item.reference is ScreeningReferenceDecision.RETAIN for item in ai_excludes
                ),
                "criterion_hallucination": sum(
                    "UNKNOWN_CRITERION" in item.evidence_issue_codes for item in ai_excludes
                ),
                "criterion_unsupported_by_evidence": sum(
                    bool(
                        {
                            "MISSING_EVIDENCE",
                            "EXCLUDE_MISSING_EVIDENCE",
                            "INVALID_CHUNK_REFERENCE",
                            "QUOTE_MISMATCH",
                            "WRONG_DOCUMENT",
                            "WRONG_DOCUMENT_VERSION",
                            "REFERENCE_LIST_ONLY",
                        }
                        & set(item.evidence_issue_codes)
                    )
                    for item in ai_excludes
                ),
                "criterion_accuracy": (
                    len(correct_criterion) / len(correct_decision) if correct_decision else None
                ),
            },
            "evidence_grounding": {
                "fully_valid_proposals": fully_valid,
                "evidence_validation_rate": fully_valid / total if total else None,
                "issue_counts": issue_counts,
            },
            "section_analysis": section_counts,
        }
    )
    base["zero_false_negative_label"] = "ZERO OBSERVED FALSE NEGATIVES ON THIS EVALUATION DATASET"
    return base
