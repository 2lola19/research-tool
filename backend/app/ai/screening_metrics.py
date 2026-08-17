from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.app.ai.screening_domain import (
    AIScreeningDisagreement,
    AIScreeningSuggestion,
    ScreeningEvaluationPolicy,
    ScreeningReferenceDecision,
    classify_disagreement,
)

METRIC_VERSION = "ai-screening-metrics-1-wilson95"
DEFAULT_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


@dataclass(frozen=True, slots=True)
class ScreeningPrediction:
    case_id: UUID
    article_id: UUID
    proposal_id: UUID
    reference: ScreeningReferenceDecision
    suggestion: AIScreeningSuggestion
    confidence: float


def evaluate_screening_predictions(
    predictions: Iterable[ScreeningPrediction],
    policy: ScreeningEvaluationPolicy,
    *,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    items = list(predictions)
    tp = tn = fp = fn = 0
    evaluated = 0
    abstentions = sum(item.suggestion is AIScreeningSuggestion.ABSTAIN for item in items)
    maybes = sum(item.suggestion is AIScreeningSuggestion.MAYBE for item in items)
    for item in items:
        predicted = _binary_prediction(item.suggestion, policy)
        if predicted is None:
            continue
        evaluated += 1
        if item.reference is ScreeningReferenceDecision.RETAIN and predicted:
            tp += 1
        elif item.reference is ScreeningReferenceDecision.EXCLUDE and not predicted:
            tn += 1
        elif item.reference is ScreeningReferenceDecision.EXCLUDE and predicted:
            fp += 1
        else:
            fn += 1
    sensitivity = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    precision = _ratio(tp, tp + fp)
    npv = _ratio(tn, tn + fn)
    total = len(items)
    high_risk = [
        {
            "case_id": str(item.case_id),
            "article_id": str(item.article_id),
            "proposal_id": str(item.proposal_id),
            "confidence": item.confidence,
            "classification": AIScreeningDisagreement.AI_EXCLUDE_HUMAN_INCLUDE.value,
        }
        for item in items
        if item.suggestion is AIScreeningSuggestion.EXCLUDE
        and item.reference is ScreeningReferenceDecision.RETAIN
    ]
    simulations = [_simulate_threshold(items, threshold) for threshold in thresholds]
    zero_fn = [row["threshold"] for row in simulations if row["false_negatives"] == 0]
    return {
        "metric_version": METRIC_VERSION,
        "policy": policy.value,
        "positive_class": "RETAIN",
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "sensitivity": sensitivity,
        "sensitivity_wilson_95": _wilson_interval(tp, tp + fn),
        "false_negative_rate": _ratio(fn, tp + fn),
        "specificity": specificity,
        "false_positive_rate": _ratio(fp, tn + fp),
        "precision": precision,
        "negative_predictive_value": npv,
        "accuracy": _ratio(tp + tn, evaluated),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        "abstention_rate": _ratio(abstentions, total),
        "maybe_rate": _ratio(maybes, total),
        "coverage": _ratio(evaluated, total),
        "total_cases": total,
        "evaluated_cases": evaluated,
        "calibration": _calibration(items),
        "threshold_simulation": simulations,
        "zero_observed_false_negative_threshold": max(zero_fn) if zero_fn else None,
        "zero_false_negative_label": "observed on this evaluation dataset",
        "high_risk_disagreements": high_risk,
    }


def _binary_prediction(
    suggestion: AIScreeningSuggestion, policy: ScreeningEvaluationPolicy
) -> bool | None:
    if policy is ScreeningEvaluationPolicy.CONSERVATIVE:
        return suggestion is not AIScreeningSuggestion.EXCLUDE
    if policy is ScreeningEvaluationPolicy.STRICT_MODEL_DECISION:
        return suggestion is AIScreeningSuggestion.INCLUDE
    if suggestion in {AIScreeningSuggestion.MAYBE, AIScreeningSuggestion.ABSTAIN}:
        return None
    return suggestion is AIScreeningSuggestion.INCLUDE


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _wilson_interval(successes: int, total: int) -> dict[str, float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return {"lower": max(0.0, centre - margin), "upper": min(1.0, centre + margin)}


def _calibration(items: list[ScreeningPrediction]) -> list[dict[str, Any]]:
    boundaries = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))
    result = []
    for lower, upper in boundaries:
        members = [
            item
            for item in items
            if lower <= item.confidence <= upper and (upper == 1.0 or item.confidence < upper)
        ]
        comparable = [
            item
            for item in members
            if item.suggestion in {AIScreeningSuggestion.INCLUDE, AIScreeningSuggestion.EXCLUDE}
        ]
        agreements = sum(
            classify_disagreement(item.suggestion, item.reference)
            in {
                AIScreeningDisagreement.AGREE_INCLUDE,
                AIScreeningDisagreement.AGREE_EXCLUDE,
            }
            for item in comparable
        )
        false_negatives = sum(
            item.suggestion is AIScreeningSuggestion.EXCLUDE
            and item.reference is ScreeningReferenceDecision.RETAIN
            for item in members
        )
        abstentions = sum(
            item.suggestion in {AIScreeningSuggestion.MAYBE, AIScreeningSuggestion.ABSTAIN}
            for item in members
        )
        result.append(
            {
                "lower": lower,
                "upper": upper,
                "count": len(members),
                "comparable_count": len(comparable),
                "agreement_count": agreements,
                "empirical_accuracy": _ratio(agreements, len(comparable)),
                "false_negatives": false_negatives,
                "abstentions": abstentions,
            }
        )
    return result


def _simulate_threshold(
    items: list[ScreeningPrediction], threshold: float
) -> dict[str, int | float]:
    excluded = [
        item
        for item in items
        if item.suggestion is AIScreeningSuggestion.EXCLUDE and item.confidence >= threshold
    ]
    false_negatives = sum(item.reference is ScreeningReferenceDecision.RETAIN for item in excluded)
    total = len(items)
    return {
        "threshold": threshold,
        "citations_ai_would_exclude": len(excluded),
        "citations_retained_for_human_review": total - len(excluded),
        "false_negatives": false_negatives,
        "workload_reduction": len(excluded) / total if total else 0.0,
        "human_review_proportion": (total - len(excluded)) / total if total else 0.0,
        "simulation_only": 1,
    }
