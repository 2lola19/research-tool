from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.screening_domain import (
    AIScreeningErrorCategory,
    AIScreeningMode,
    ScreeningEvaluationCaseResult,
    ScreeningEvaluationDataset,
    ScreeningEvaluationPolicy,
    ScreeningEvaluationResult,
    ScreeningReferenceDecision,
    ScreeningReferenceStandard,
)
from backend.app.ai.screening_persistence import SqlAlchemyAIScreeningRepository
from backend.app.ai.screening_service import AIScreeningService, AIScreeningSuggestionView
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.protocols.persistence import SqlAlchemyProtocolRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.screening.persistence import SqlAlchemyScreeningRepository

router = APIRouter(prefix="/ai/screening", tags=["ai-screening"])


class PolicyRequest(BaseModel):
    mode: AIScreeningMode
    maximum_batch_size: int = Field(default=20, ge=1, le=100)


class PolicyResponse(BaseModel):
    id: UUID
    review_id: UUID
    version: int
    mode: AIScreeningMode
    maximum_batch_size: int
    created_by_user_id: UUID
    created_at: str


class SuggestionBatchRequest(BaseModel):
    assignment_ids: list[UUID] = Field(min_length=1, max_length=100)
    protocol_version_id: UUID | None = None
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    per_run_token_ceiling: int | None = Field(default=4096, ge=1, le=1_000_000)


class SuggestionResponse(BaseModel):
    assignment_id: UUID
    article_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    mode: AIScreeningMode
    is_revealed: bool
    suggestion: str | None
    structured_value: dict[str, Any] | None
    protocol_version_id: UUID
    citation_content_hash: str
    accessed: bool


class EvaluationCaseRequest(BaseModel):
    article_id: UUID
    reference_decision: ScreeningReferenceDecision
    reference_source_type: ScreeningReferenceStandard | None = None
    reference_source_id: UUID | None = None


class DatasetRequest(BaseModel):
    logical_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    protocol_version_id: UUID | None = None
    reference_standard: ScreeningReferenceStandard
    cases: list[EvaluationCaseRequest] = Field(min_length=1, max_length=100_000)


class DatasetResponse(BaseModel):
    id: UUID
    review_id: UUID
    logical_key: str
    version: int
    protocol_version_id: UUID
    name: str
    reference_standard: ScreeningReferenceStandard
    content_hash: str
    created_by_user_id: UUID
    created_at: str

    @classmethod
    def from_domain(cls, item: ScreeningEvaluationDataset) -> DatasetResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            logical_key=item.logical_key,
            version=item.version,
            protocol_version_id=item.protocol_version_id,
            name=item.name,
            reference_standard=item.reference_standard,
            content_hash=item.content_hash,
            created_by_user_id=item.created_by_user_id,
            created_at=item.created_at.isoformat(),
        )


class EvaluateRequest(BaseModel):
    evaluation_policy: ScreeningEvaluationPolicy = ScreeningEvaluationPolicy.CONSERVATIVE
    prompt_version_id: UUID | None = None
    model_version_id: UUID | None = None


class EvaluationResponse(BaseModel):
    id: UUID
    dataset_id: UUID
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
    created_at: str

    @classmethod
    def from_domain(cls, item: ScreeningEvaluationResult) -> EvaluationResponse:
        return cls(
            id=item.id,
            dataset_id=item.dataset_id,
            review_id=item.review_id,
            protocol_version_id=item.protocol_version_id,
            prompt_version_id=item.prompt_version_id,
            model_version_id=item.model_version_id,
            task_definition_version=item.task_definition_version,
            evaluation_policy=item.evaluation_policy,
            metric_version=item.metric_version,
            metrics=item.metrics,
            calibration=item.calibration,
            threshold_simulation=item.threshold_simulation,
            high_risk_disagreements=item.high_risk_disagreements,
            content_hash=item.content_hash,
            created_by_user_id=item.created_by_user_id,
            created_at=item.created_at.isoformat(),
        )


class EvaluationCaseResultResponse(BaseModel):
    id: UUID
    evaluation_result_id: UUID
    case_id: UUID
    review_id: UUID
    proposal_id: UUID
    suggestion: str
    reference_decision: str
    model_reported_confidence: float
    disagreement: str

    @classmethod
    def from_domain(cls, item: ScreeningEvaluationCaseResult) -> EvaluationCaseResultResponse:
        return cls(
            id=item.id,
            evaluation_result_id=item.evaluation_result_id,
            case_id=item.case_id,
            review_id=item.review_id,
            proposal_id=item.proposal_id,
            suggestion=item.suggestion.value,
            reference_decision=item.reference_decision.value,
            model_reported_confidence=item.model_reported_confidence,
            disagreement=item.disagreement.value,
        )


class ErrorClassificationRequest(BaseModel):
    category: AIScreeningErrorCategory
    notes: str | None = Field(default=None, max_length=4000)


def _service(session: DbSessionDependency) -> AIScreeningService:
    identity = SqlAlchemyIdentityRepository(session)
    review_service = ReviewService(SqlAlchemyReviewRepository(session), identity)
    provenance = SqlAlchemyProvenanceRepository(session)
    execution = AIExecutionService(
        SqlAlchemyAIRepository(session),
        review_service,
        provenance,
        {"mock": DeterministicMockAIProvider()},
    )
    return AIScreeningService(
        SqlAlchemyAIScreeningRepository(session),
        SqlAlchemyAIRepository(session),
        SqlAlchemyScreeningRepository(session),
        SqlAlchemyCitationRepository(session),
        SqlAlchemyProtocolRepository(session),
        review_service,
        provenance,
        execution,
    )


def _policy_response(item: Any) -> PolicyResponse:
    return PolicyResponse(
        id=item.id,
        review_id=item.review_id,
        version=item.version,
        mode=item.mode,
        maximum_batch_size=item.maximum_batch_size,
        created_by_user_id=item.created_by_user_id,
        created_at=item.created_at.isoformat(),
    )


def _suggestion_response(item: AIScreeningSuggestionView) -> SuggestionResponse:
    return SuggestionResponse(
        assignment_id=item.assignment_id,
        article_id=item.article_id,
        proposal_id=item.proposal_id,
        ai_run_id=item.ai_run_id,
        mode=item.mode,
        is_revealed=item.is_revealed,
        suggestion=item.suggestion.value if item.suggestion is not None else None,
        structured_value=item.structured_value,
        protocol_version_id=item.protocol_version_id,
        citation_content_hash=item.citation_content_hash,
        accessed=item.accessed,
    )


@router.get("/reviews/{review_id}/policy", response_model=PolicyResponse | None)
async def get_screening_ai_policy(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> PolicyResponse | None:
    item = await _service(session).get_policy(actor, review_id)
    return _policy_response(item) if item is not None else None


@router.post(
    "/reviews/{review_id}/policy",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_screening_ai_policy(
    payload: PolicyRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> PolicyResponse:
    item = await _service(session).set_policy(
        actor,
        review_id=review_id,
        mode=payload.mode,
        maximum_batch_size=payload.maximum_batch_size,
    )
    await session.commit()
    return _policy_response(item)


@router.post(
    "/reviews/{review_id}/suggestions",
    response_model=list[SuggestionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_screening_ai_suggestions(
    payload: SuggestionBatchRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[SuggestionResponse]:
    items = await _service(session).create_suggestions(
        actor,
        review_id=review_id,
        assignment_ids=payload.assignment_ids,
        protocol_version_id=payload.protocol_version_id,
        model_version_id=payload.model_version_id,
        prompt_version_id=payload.prompt_version_id,
        maximum_attempts=payload.maximum_attempts,
        timeout_seconds=payload.timeout_seconds,
        per_run_token_ceiling=payload.per_run_token_ceiling,
    )
    await session.commit()
    return [_suggestion_response(item) for item in items]


@router.get(
    "/reviews/{review_id}/assignments/{assignment_id}/suggestion",
    response_model=SuggestionResponse,
)
async def get_screening_ai_suggestion(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    assignment_id: Annotated[UUID, Path()],
) -> SuggestionResponse:
    item = await _service(session).get_suggestion(
        actor, review_id=review_id, assignment_id=assignment_id
    )
    await session.commit()
    return _suggestion_response(item)


@router.post(
    "/reviews/{review_id}/evaluation-datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening_evaluation_dataset(
    payload: DatasetRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> DatasetResponse:
    item = await _service(session).create_dataset(
        actor,
        review_id=review_id,
        logical_key=payload.logical_key,
        name=payload.name,
        protocol_version_id=payload.protocol_version_id,
        reference_standard=payload.reference_standard,
        cases=[case.model_dump(mode="json") for case in payload.cases],
    )
    await session.commit()
    return DatasetResponse.from_domain(item)


@router.get(
    "/reviews/{review_id}/evaluation-datasets",
    response_model=list[DatasetResponse],
)
async def list_screening_evaluation_datasets(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[DatasetResponse]:
    items = await _service(session).list_datasets(actor, review_id)
    return [DatasetResponse.from_domain(item) for item in items]


@router.post(
    "/reviews/{review_id}/evaluation-datasets/{dataset_id}/evaluate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_screening_dataset(
    payload: EvaluateRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    dataset_id: Annotated[UUID, Path()],
) -> EvaluationResponse:
    item = await _service(session).evaluate_dataset(
        actor,
        review_id=review_id,
        dataset_id=dataset_id,
        evaluation_policy=payload.evaluation_policy,
        prompt_version_id=payload.prompt_version_id,
        model_version_id=payload.model_version_id,
    )
    await session.commit()
    return EvaluationResponse.from_domain(item)


@router.get("/reviews/{review_id}/evaluations", response_model=list[EvaluationResponse])
async def list_screening_evaluations(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[EvaluationResponse]:
    items = await _service(session).list_results(actor, review_id)
    return [EvaluationResponse.from_domain(item) for item in items]


@router.get(
    "/reviews/{review_id}/evaluations/{evaluation_id}/case-results",
    response_model=list[EvaluationCaseResultResponse],
)
async def list_screening_evaluation_case_results(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    evaluation_id: Annotated[UUID, Path()],
) -> list[EvaluationCaseResultResponse]:
    items = await _service(session).list_case_results(
        actor, review_id=review_id, result_id=evaluation_id
    )
    return [EvaluationCaseResultResponse.from_domain(item) for item in items]


@router.post(
    "/reviews/{review_id}/evaluation-case-results/{case_result_id}/error-classifications",
    status_code=status.HTTP_201_CREATED,
)
async def classify_screening_evaluation_error(
    payload: ErrorClassificationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    case_result_id: Annotated[UUID, Path()],
) -> dict[str, str]:
    await _service(session).classify_error(
        actor,
        review_id=review_id,
        case_result_id=case_result_id,
        category=payload.category,
        notes=payload.notes,
    )
    await session.commit()
    return {"status": "recorded", "category": payload.category.value}
