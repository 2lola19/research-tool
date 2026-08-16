from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class AIScreeningMode(StrEnum):
    OFF = "OFF"
    BLINDED_AI = "BLINDED_AI"
    ASSISTED = "ASSISTED"


class AIScreeningSuggestion(StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    MAYBE = "MAYBE"
    ABSTAIN = "ABSTAIN"


class AIScreeningAccessType(StrEnum):
    ASSISTED_VIEW = "ASSISTED_VIEW"
    POST_DECISION_REVEAL = "POST_DECISION_REVEAL"


class AIScreeningInteraction(StrEnum):
    UNSEEN = "UNSEEN"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    OVERRIDDEN = "OVERRIDDEN"
    DISAGREED = "DISAGREED"


class AIScreeningDisagreement(StrEnum):
    AGREE_INCLUDE = "AGREE_INCLUDE"
    AGREE_EXCLUDE = "AGREE_EXCLUDE"
    AI_INCLUDE_HUMAN_EXCLUDE = "AI_INCLUDE_HUMAN_EXCLUDE"
    AI_EXCLUDE_HUMAN_INCLUDE = "AI_EXCLUDE_HUMAN_INCLUDE"
    AI_MAYBE_HUMAN_INCLUDE = "AI_MAYBE_HUMAN_INCLUDE"
    AI_MAYBE_HUMAN_EXCLUDE = "AI_MAYBE_HUMAN_EXCLUDE"
    AI_ABSTAIN = "AI_ABSTAIN"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class ScreeningReferenceDecision(StrEnum):
    RETAIN = "RETAIN"
    EXCLUDE = "EXCLUDE"


class ScreeningReferenceStandard(StrEnum):
    ADJUDICATED_TITLE_ABSTRACT = "ADJUDICATED_TITLE_ABSTRACT"
    CONSENSUS_DECISION = "CONSENSUS_DECISION"
    FINAL_FULL_TEXT_INCLUSION = "FINAL_FULL_TEXT_INCLUSION"
    CURATED_DATASET = "CURATED_DATASET"


class ScreeningEvaluationPolicy(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"
    STRICT_MODEL_DECISION = "STRICT_MODEL_DECISION"
    COVERAGE_ONLY = "COVERAGE_ONLY"


class AIScreeningErrorCategory(StrEnum):
    POPULATION_MISUNDERSTANDING = "POPULATION_MISUNDERSTANDING"
    INTERVENTION_MISUNDERSTANDING = "INTERVENTION_MISUNDERSTANDING"
    COMPARATOR_MISUNDERSTANDING = "COMPARATOR_MISUNDERSTANDING"
    OUTCOME_MISUNDERSTANDING = "OUTCOME_MISUNDERSTANDING"
    DESIGN_MISUNDERSTANDING = "DESIGN_MISUNDERSTANDING"
    LANGUAGE_OR_PUBLICATION_TYPE = "LANGUAGE_OR_PUBLICATION_TYPE"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    CRITERION_AMBIGUITY = "CRITERION_AMBIGUITY"
    HALLUCINATED_CRITERION = "HALLUCINATED_CRITERION"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class AIScreeningPolicyVersion:
    id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    mode: AIScreeningMode
    maximum_batch_size: int
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AIScreeningProposalLink:
    id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    article_id: UUID
    assignment_id: UUID
    protocol_version_id: UUID
    protocol_content_hash: str
    eligibility_criteria_hash: str
    exclusion_criteria_hash: str
    citation_content_hash: str
    task_definition_version: int
    assistance_mode: AIScreeningMode
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AIScreeningAccess:
    id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    assignment_id: UUID
    reviewer_user_id: UUID
    access_type: AIScreeningAccessType
    screening_decision_id: UUID | None
    accessed_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningEvaluationDataset:
    id: UUID
    organization_id: UUID
    review_id: UUID
    logical_key: str
    version: int
    protocol_version_id: UUID
    name: str
    reference_standard: ScreeningReferenceStandard
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningEvaluationCase:
    id: UUID
    dataset_id: UUID
    organization_id: UUID
    review_id: UUID
    article_id: UUID
    ordinal: int
    reference_decision: ScreeningReferenceDecision
    reference_source_type: ScreeningReferenceStandard
    reference_source_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningEvaluationResult:
    id: UUID
    dataset_id: UUID
    organization_id: UUID
    review_id: UUID
    protocol_version_id: UUID
    prompt_version_id: UUID
    model_version_id: UUID
    task_definition_version: int
    evaluation_policy: ScreeningEvaluationPolicy
    metric_version: str
    metrics: dict[str, Any]
    calibration: list[dict[str, Any]]
    threshold_simulation: list[dict[str, Any]]
    high_risk_disagreements: list[dict[str, Any]]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningEvaluationCaseResult:
    id: UUID
    evaluation_result_id: UUID
    case_id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    suggestion: AIScreeningSuggestion
    reference_decision: ScreeningReferenceDecision
    model_reported_confidence: float
    disagreement: AIScreeningDisagreement


def classify_disagreement(
    ai: AIScreeningSuggestion, human: ScreeningReferenceDecision
) -> AIScreeningDisagreement:
    if ai is AIScreeningSuggestion.ABSTAIN:
        return AIScreeningDisagreement.AI_ABSTAIN
    if ai is AIScreeningSuggestion.MAYBE:
        return (
            AIScreeningDisagreement.AI_MAYBE_HUMAN_INCLUDE
            if human is ScreeningReferenceDecision.RETAIN
            else AIScreeningDisagreement.AI_MAYBE_HUMAN_EXCLUDE
        )
    if ai is AIScreeningSuggestion.INCLUDE:
        return (
            AIScreeningDisagreement.AGREE_INCLUDE
            if human is ScreeningReferenceDecision.RETAIN
            else AIScreeningDisagreement.AI_INCLUDE_HUMAN_EXCLUDE
        )
    if ai is AIScreeningSuggestion.EXCLUDE:
        return (
            AIScreeningDisagreement.AI_EXCLUDE_HUMAN_INCLUDE
            if human is ScreeningReferenceDecision.RETAIN
            else AIScreeningDisagreement.AGREE_EXCLUDE
        )
    return AIScreeningDisagreement.NOT_COMPARABLE
