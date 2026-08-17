from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.full_text_domain import (
    FullTextDocumentRole,
    FullTextErrorCategory,
    FullTextReferenceStandard,
)
from backend.app.ai.full_text_persistence import SqlAlchemyAIFullTextRepository
from backend.app.ai.full_text_service import (
    AIFullTextScreeningService,
    AIFullTextSuggestionView,
)
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.screening_domain import ScreeningEvaluationPolicy, ScreeningReferenceDecision
from backend.app.ai.screening_persistence import SqlAlchemyAIScreeningRepository
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.deduplication.persistence import SqlAlchemyDeduplicationRepository
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.protocols.persistence import SqlAlchemyProtocolRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.screening.persistence import SqlAlchemyScreeningRepository
from backend.app.screening.service import ScreeningService

router = APIRouter(prefix="/ai/screening/full-text", tags=["ai-full-text-screening"])


class FullTextBatchItemRequest(BaseModel):
    assignment_id: UUID
    document_id: UUID
    document_role: FullTextDocumentRole = FullTextDocumentRole.PRIMARY_FULL_TEXT


class FullTextBatchRequest(BaseModel):
    items: list[FullTextBatchItemRequest] = Field(min_length=1, max_length=100)
    protocol_version_id: UUID | None = None
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    per_run_token_ceiling: int | None = Field(default=16_384, ge=1, le=1_000_000)


class FullTextSuggestionResponse(BaseModel):
    assignment_id: UUID
    article_id: UUID
    document_id: UUID
    document_version_id: UUID
    processing_run_id: UUID
    proposal_id: UUID | None
    ai_run_id: UUID | None
    mode: str
    readiness: str
    status: str
    failure_reason: str | None
    is_revealed: bool
    suggestion: str | None
    structured_value: dict[str, Any] | None
    protocol_version_id: UUID
    stale: bool
    stale_reasons: list[str]
    selected_chunk_ids: list[str]
    selection_method: str

    @classmethod
    def from_domain(cls, item: AIFullTextSuggestionView) -> FullTextSuggestionResponse:
        return cls(
            assignment_id=item.assignment_id,
            article_id=item.article_id,
            document_id=item.document_id,
            document_version_id=item.document_version_id,
            processing_run_id=item.processing_run_id,
            proposal_id=item.proposal_id,
            ai_run_id=item.ai_run_id,
            mode=item.mode.value,
            readiness=item.readiness.value,
            status=item.status,
            failure_reason=item.failure_reason,
            is_revealed=item.is_revealed,
            suggestion=item.suggestion.value if item.suggestion else None,
            structured_value=item.structured_value,
            protocol_version_id=item.protocol_version_id,
            stale=item.stale,
            stale_reasons=list(item.stale_reasons),
            selected_chunk_ids=list(item.selected_chunk_ids),
            selection_method=item.selection_method,
        )


class AcceptRequest(BaseModel):
    exclusion_reason: str | None = Field(default=None, max_length=4000)


class FullTextEvaluationCaseRequest(BaseModel):
    document_id: UUID
    reference_decision: ScreeningReferenceDecision
    reference_exclusion_criterion_id: str | None = Field(default=None, max_length=200)
    reference_source_type: FullTextReferenceStandard | None = None
    reference_source_id: UUID | None = None


class FullTextDatasetRequest(BaseModel):
    logical_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    protocol_version_id: UUID | None = None
    reference_standard: FullTextReferenceStandard
    cases: list[FullTextEvaluationCaseRequest] = Field(min_length=1, max_length=100_000)


class EvaluateRequest(BaseModel):
    evaluation_policy: ScreeningEvaluationPolicy = ScreeningEvaluationPolicy.CONSERVATIVE
    prompt_version_id: UUID | None = None
    model_version_id: UUID | None = None


class ErrorRequest(BaseModel):
    category: FullTextErrorCategory
    notes: str | None = Field(default=None, max_length=4000)


def _service(session: DbSessionDependency) -> AIFullTextScreeningService:
    identity = SqlAlchemyIdentityRepository(session)
    review_repository = SqlAlchemyReviewRepository(session)
    review_service = ReviewService(review_repository, identity)
    provenance = SqlAlchemyProvenanceRepository(session)
    ai_repository = SqlAlchemyAIRepository(session)
    screening_repository = SqlAlchemyScreeningRepository(session)
    citation_repository = SqlAlchemyCitationRepository(session)
    canonical = ScreeningService(
        screening_repository,
        citation_repository,
        SqlAlchemyDeduplicationRepository(session),
        review_repository,
        identity,
        provenance,
    )
    return AIFullTextScreeningService(
        SqlAlchemyAIFullTextRepository(session),
        ai_repository,
        SqlAlchemyAIScreeningRepository(session),
        screening_repository,
        SqlAlchemyDocumentRepository(session),
        citation_repository,
        SqlAlchemyProtocolRepository(session),
        review_service,
        provenance,
        AIExecutionService(
            ai_repository,
            review_service,
            provenance,
            {"mock": DeterministicMockAIProvider()},
        ),
        canonical,
    )


def _dataset_response(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "review_id": item.review_id,
        "logical_key": item.logical_key,
        "version": item.version,
        "protocol_version_id": item.protocol_version_id,
        "name": item.name,
        "reference_standard": item.reference_standard.value,
        "content_hash": item.content_hash,
        "created_by_user_id": item.created_by_user_id,
        "created_at": item.created_at.isoformat(),
        "stage": "FULL_TEXT",
    }


def _result_response(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "dataset_id": item.dataset_id,
        "review_id": item.review_id,
        "protocol_version_id": item.protocol_version_id,
        "prompt_version_id": item.prompt_version_id,
        "model_version_id": item.model_version_id,
        "task_definition_version": item.task_definition_version,
        "evaluation_policy": item.evaluation_policy,
        "metric_version": item.metric_version,
        "metrics": item.metrics,
        "content_hash": item.content_hash,
        "created_by_user_id": item.created_by_user_id,
        "created_at": item.created_at.isoformat(),
        "stage": "FULL_TEXT",
    }


@router.get("/reviews/{review_id}/assignments/{assignment_id}/readiness")
async def get_full_text_ai_readiness(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    assignment_id: Annotated[UUID, Path()],
    document_id: UUID | None = None,
) -> dict[str, Any]:
    item = await _service(session).readiness(
        actor,
        review_id=review_id,
        assignment_id=assignment_id,
        document_id=document_id,
    )
    return {
        "assignment_id": item.assignment_id,
        "document_id": item.document_id,
        "state": item.state.value,
        "reason": item.reason,
    }


@router.post(
    "/reviews/{review_id}/suggestions",
    response_model=list[FullTextSuggestionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_full_text_ai_suggestions(
    payload: FullTextBatchRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[FullTextSuggestionResponse]:
    items = await _service(session).create_suggestions(
        actor,
        review_id=review_id,
        requests=[item.model_dump(mode="json") for item in payload.items],
        protocol_version_id=payload.protocol_version_id,
        model_version_id=payload.model_version_id,
        prompt_version_id=payload.prompt_version_id,
        maximum_attempts=payload.maximum_attempts,
        timeout_seconds=payload.timeout_seconds,
        per_run_token_ceiling=payload.per_run_token_ceiling,
    )
    await session.commit()
    return [FullTextSuggestionResponse.from_domain(item) for item in items]


@router.get(
    "/reviews/{review_id}/assignments/{assignment_id}/suggestion",
    response_model=FullTextSuggestionResponse,
)
async def get_full_text_ai_suggestion(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    assignment_id: Annotated[UUID, Path()],
) -> FullTextSuggestionResponse:
    item = await _service(session).get_suggestion(
        actor, review_id=review_id, assignment_id=assignment_id
    )
    await session.commit()
    return FullTextSuggestionResponse.from_domain(item)


@router.get(
    "/reviews/{review_id}/proposals/{proposal_id}",
    response_model=FullTextSuggestionResponse,
)
async def get_full_text_ai_proposal_by_id(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    proposal_id: Annotated[UUID, Path()],
) -> FullTextSuggestionResponse:
    item = await _service(session).get_suggestion(
        actor, review_id=review_id, proposal_id=proposal_id
    )
    await session.commit()
    return FullTextSuggestionResponse.from_domain(item)


@router.post("/reviews/{review_id}/proposals/{proposal_id}/accept")
async def accept_full_text_ai_suggestion(
    payload: AcceptRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    proposal_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    decision = await _service(session).accept_suggestion(
        actor,
        review_id=review_id,
        proposal_id=proposal_id,
        exclusion_reason=payload.exclusion_reason,
    )
    await session.commit()
    return {
        "screening_decision_id": decision.id,
        "assignment_id": decision.assignment_id,
        "decision": decision.decision.value,
        "human_reviewer_user_id": decision.reviewer_user_id,
        "ai_proposal_id": proposal_id,
    }


@router.post("/reviews/{review_id}/evaluation-datasets", status_code=status.HTTP_201_CREATED)
async def create_full_text_evaluation_dataset(
    payload: FullTextDatasetRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
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
    return _dataset_response(item)


@router.get("/reviews/{review_id}/evaluation-datasets")
async def list_full_text_evaluation_datasets(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        _dataset_response(item) for item in await _service(session).list_datasets(actor, review_id)
    ]


@router.post(
    "/reviews/{review_id}/evaluation-datasets/{dataset_id}/evaluate",
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_full_text_dataset(
    payload: EvaluateRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    dataset_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).evaluate_dataset(
        actor,
        review_id=review_id,
        dataset_id=dataset_id,
        evaluation_policy=payload.evaluation_policy,
        prompt_version_id=payload.prompt_version_id,
        model_version_id=payload.model_version_id,
    )
    await session.commit()
    return _result_response(item)


@router.get("/reviews/{review_id}/evaluations")
async def list_full_text_evaluations(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        _result_response(item) for item in await _service(session).list_results(actor, review_id)
    ]


@router.get("/reviews/{review_id}/evaluations/{evaluation_id}/case-results")
async def list_full_text_case_results(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    evaluation_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    items = await _service(session).list_case_results(
        actor, review_id=review_id, result_id=evaluation_id
    )
    errors = await _service(session).list_case_error_classifications(
        actor, review_id=review_id, result_id=evaluation_id
    )
    errors_by_case: dict[UUID, list[dict[str, Any]]] = {}
    for error in errors:
        errors_by_case.setdefault(error.case_result_id, []).append(
            {
                "category": error.category,
                "notes": error.notes,
                "classified_by_user_id": error.classified_by_user_id,
                "created_at": error.created_at.isoformat(),
            }
        )
    return [
        {
            "id": item.id,
            "evaluation_result_id": item.evaluation_result_id,
            "case_id": item.case_id,
            "proposal_id": item.proposal_id,
            "suggestion": item.suggestion,
            "reference_decision": item.reference_decision,
            "model_reported_confidence": item.model_reported_confidence,
            "proposed_criterion_ids": item.proposed_criterion_ids,
            "reference_criterion_id": item.reference_criterion_id,
            "criterion_correct": item.criterion_correct,
            "evidence_valid": item.evidence_valid,
            "evidence_issue_codes": item.evidence_issue_codes,
            "evidence_sections": item.evidence_sections,
            "disagreement": item.disagreement,
            "error_classifications": errors_by_case.get(item.id, []),
        }
        for item in items
    ]


@router.post(
    "/reviews/{review_id}/evaluation-case-results/{case_result_id}/error-classifications",
    status_code=status.HTTP_201_CREATED,
)
async def classify_full_text_error(
    payload: ErrorRequest,
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
