from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.extraction_domain import (
    AIExtractionErrorCategory,
    AIExtractionFieldReviewAction,
    AIExtractionReferenceStandard,
)
from backend.app.ai.extraction_persistence import SqlAlchemyAIExtractionRepository
from backend.app.ai.extraction_service import (
    AIExtractionProposalView,
    AIExtractionService,
)
from backend.app.ai.full_text_domain import FullTextDocumentRole
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.extraction.manual_persistence import SqlAlchemyManualExtractionRepository
from backend.app.extraction.manual_service import ManualExtractionService
from backend.app.extraction.schema_persistence import SqlAlchemyExtractionSchemaRepository
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.studies.persistence import SqlAlchemyStudyRepository

router = APIRouter(prefix="/ai/extraction", tags=["ai-extraction"])


class ExtractionPolicyRequest(BaseModel):
    mode: AIScreeningMode
    maximum_batch_size: int = Field(default=20, ge=1, le=100)


class ExtractionSourceRequest(BaseModel):
    document_id: UUID
    document_role: FullTextDocumentRole = FullTextDocumentRole.PRIMARY_FULL_TEXT


class ExtractionReadinessRequest(BaseModel):
    assignment_id: UUID
    documents: list[ExtractionSourceRequest] = Field(min_length=1, max_length=8)


class ExtractionBatchItemRequest(BaseModel):
    assignment_id: UUID
    documents: list[ExtractionSourceRequest] = Field(min_length=1, max_length=8)


class ExtractionBatchRequest(BaseModel):
    items: list[ExtractionBatchItemRequest] = Field(min_length=1, max_length=100)
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    per_run_token_ceiling: int | None = Field(default=16_384, ge=1, le=1_000_000)


class FieldReviewRequest(BaseModel):
    action: AIExtractionFieldReviewAction
    human_value: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=4_000)


class EvaluationCaseRequest(BaseModel):
    study_id: UUID
    field_key: str = Field(min_length=1, max_length=200)
    reference_missingness: str = Field(min_length=1, max_length=40)
    reference_value: Any = None
    reference_unit: str | None = Field(default=None, max_length=100)
    reference_source_id: UUID | None = None
    evidence_snapshot: dict[str, Any] | None = None
    absolute_tolerance: float | None = Field(default=None, ge=0)


class EvaluationDatasetRequest(BaseModel):
    schema_version_id: UUID
    logical_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    reference_standard: AIExtractionReferenceStandard
    tolerance_policy_version: str | None = Field(default=None, max_length=80)
    cases: list[EvaluationCaseRequest] = Field(min_length=1, max_length=100_000)


class ErrorClassificationRequest(BaseModel):
    category: AIExtractionErrorCategory
    note: str | None = Field(default=None, max_length=4_000)


def _service(session: DbSessionDependency) -> AIExtractionService:
    identity = SqlAlchemyIdentityRepository(session)
    review_repository = SqlAlchemyReviewRepository(session)
    review_service = ReviewService(review_repository, identity)
    provenance = SqlAlchemyProvenanceRepository(session)
    ai_repository = SqlAlchemyAIRepository(session)
    manual_repository = SqlAlchemyManualExtractionRepository(session)
    schemas = SqlAlchemyExtractionSchemaRepository(session)
    studies = SqlAlchemyStudyRepository(session)
    manual = ManualExtractionService(
        manual_repository,
        schemas,
        studies,
        review_repository,
        identity,
        provenance,
    )
    execution = AIExecutionService(
        ai_repository,
        review_service,
        provenance,
        {"mock": DeterministicMockAIProvider()},
    )
    return AIExtractionService(
        SqlAlchemyAIExtractionRepository(session),
        ai_repository,
        manual_repository,
        schemas,
        studies,
        SqlAlchemyDocumentRepository(session),
        review_service,
        provenance,
        execution,
        manual,
    )


def _proposal_response(item: AIExtractionProposalView) -> dict[str, Any]:
    return {
        "assignment_id": item.assignment_id,
        "study_id": item.study_id,
        "schema_version_id": item.schema_version_id,
        "proposal_id": item.proposal_id,
        "ai_run_id": item.ai_run_id,
        "mode": item.mode.value,
        "readiness": item.readiness.value,
        "status": item.status,
        "failure_reason": item.failure_reason,
        "is_revealed": item.is_revealed,
        "structured_value": item.structured_value,
        "validation_results": item.validation_results,
        "stale": item.stale,
        "stale_reasons": list(item.stale_reasons),
        "source_manifest": list(item.source_manifest),
        "selected_chunk_ids": list(item.selected_chunk_ids),
        "omitted_chunk_count": item.omitted_chunk_count,
        "selection_method": item.selection_method,
    }


@router.post("/reviews/{review_id}/policies", status_code=status.HTTP_201_CREATED)
async def create_extraction_policy(
    payload: ExtractionPolicyRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    policy = await _service(session).create_policy(
        actor,
        review_id=review_id,
        mode=payload.mode,
        maximum_batch_size=payload.maximum_batch_size,
    )
    await session.commit()
    return {
        "id": policy.id,
        "review_id": policy.review_id,
        "version": policy.version,
        "mode": policy.mode.value,
        "maximum_batch_size": policy.maximum_batch_size,
    }


@router.post("/reviews/{review_id}/readiness")
async def extraction_readiness(
    payload: ExtractionReadinessRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).readiness(
        actor,
        review_id=review_id,
        assignment_id=payload.assignment_id,
        documents=[source.model_dump(mode="json") for source in payload.documents],
    )
    return {
        "assignment_id": item.assignment_id,
        "schema_version_id": item.schema_version_id,
        "state": item.state.value,
        "reason": item.reason,
        "unsupported_field_ids": list(item.unsupported_field_ids),
    }


@router.post("/reviews/{review_id}/proposals", status_code=status.HTTP_201_CREATED)
async def create_extraction_proposals(
    payload: ExtractionBatchRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    items = await _service(session).create_suggestions(
        actor,
        review_id=review_id,
        requests=[item.model_dump(mode="json") for item in payload.items],
        model_version_id=payload.model_version_id,
        prompt_version_id=payload.prompt_version_id,
        maximum_attempts=payload.maximum_attempts,
        timeout_seconds=payload.timeout_seconds,
        per_run_token_ceiling=payload.per_run_token_ceiling,
    )
    await session.commit()
    return [_proposal_response(item) for item in items]


@router.get("/reviews/{review_id}/proposals")
async def list_extraction_proposals(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        _proposal_response(item)
        for item in await _service(session).list_suggestions(actor, review_id=review_id)
    ]


@router.get("/reviews/{review_id}/assignments/{assignment_id}")
async def get_assignment_extraction_proposal(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    assignment_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return _proposal_response(
        await _service(session).get_suggestion(
            actor, review_id=review_id, assignment_id=assignment_id
        )
    )


@router.get("/reviews/{review_id}/proposals/{proposal_id}")
async def get_extraction_proposal(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    proposal_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return _proposal_response(
        await _service(session).get_suggestion(actor, review_id=review_id, proposal_id=proposal_id)
    )


@router.post("/reviews/{review_id}/proposals/{proposal_id}/fields/{field_id}/review")
async def review_extraction_field(
    payload: FieldReviewRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    proposal_id: Annotated[UUID, Path()],
    field_id: Annotated[str, Path(min_length=1, max_length=200)],
) -> dict[str, Any]:
    result = await _service(session).review_field(
        actor,
        review_id=review_id,
        proposal_id=proposal_id,
        field_id=field_id,
        action=payload.action,
        human_value=payload.human_value,
        reason=payload.reason,
    )
    await session.commit()
    return result


@router.post("/reviews/{review_id}/evaluation-datasets", status_code=status.HTTP_201_CREATED)
async def create_extraction_evaluation_dataset(
    payload: EvaluationDatasetRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    dataset = await _service(session).create_dataset(
        actor,
        review_id=review_id,
        schema_version_id=payload.schema_version_id,
        logical_key=payload.logical_key,
        name=payload.name,
        reference_standard=payload.reference_standard,
        tolerance_policy_version=payload.tolerance_policy_version,
        cases=[case.model_dump(mode="json") for case in payload.cases],
    )
    await session.commit()
    return {
        "id": dataset.id,
        "schema_version_id": dataset.schema_version_id,
        "logical_key": dataset.logical_key,
        "version": dataset.version,
        "reference_standard": dataset.reference_standard.value,
        "content_hash": dataset.content_hash,
    }


@router.get("/reviews/{review_id}/evaluation-datasets")
async def list_extraction_evaluation_datasets(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "schema_version_id": item.schema_version_id,
            "logical_key": item.logical_key,
            "version": item.version,
            "name": item.name,
            "reference_standard": item.reference_standard.value,
            "content_hash": item.content_hash,
        }
        for item in await _service(session).list_datasets(actor, review_id=review_id)
    ]


@router.post(
    "/reviews/{review_id}/evaluation-datasets/{dataset_id}/evaluate",
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_extraction_dataset(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    dataset_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    result = await _service(session).evaluate_dataset(
        actor, review_id=review_id, dataset_id=dataset_id
    )
    await session.commit()
    return {
        "id": result.id,
        "dataset_id": result.dataset_id,
        "metrics": result.metrics,
        "dimensions": result.dimensions,
        "result_hash": result.result_hash,
    }


@router.get("/reviews/{review_id}/evaluations")
async def list_extraction_evaluations(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "dataset_id": item.dataset_id,
            "metrics": item.metrics,
            "dimensions": item.dimensions,
            "result_hash": item.result_hash,
        }
        for item in await _service(session).list_evaluations(actor, review_id=review_id)
    ]


@router.get("/reviews/{review_id}/evaluations/{evaluation_id}/high-risk")
async def extraction_high_risk_queue(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    evaluation_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    items = await _service(session).high_risk_queue(
        actor, review_id=review_id, evaluation_result_id=evaluation_id
    )
    return [
        {
            "id": item.id,
            "case_id": item.case_id,
            "proposal_id": item.proposal_id,
            "classification": item.classification,
            "ai_value": item.ai_value,
            "reference_value": item.reference_value,
            "evidence_valid": item.evidence_valid,
            "error_categories": item.error_categories,
            "source_location": item.source_location,
        }
        for item in items
    ]


@router.get("/reviews/{review_id}/evaluations/{evaluation_id}/case-results")
async def extraction_evaluation_case_results(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    evaluation_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    items = await _service(session).list_case_results(
        actor, review_id=review_id, evaluation_result_id=evaluation_id
    )
    return [
        {
            "id": item.id,
            "case_id": item.case_id,
            "proposal_id": item.proposal_id,
            "classification": item.classification,
            "ai_status": item.ai_status,
            "ai_value": item.ai_value,
            "reference_value": item.reference_value,
            "absolute_error": item.absolute_error,
            "relative_error": item.relative_error,
            "evidence_valid": item.evidence_valid,
            "error_categories": item.error_categories,
            "confidence": item.confidence,
            "source_location": item.source_location,
        }
        for item in items
    ]


@router.post("/reviews/{review_id}/evaluation-case-results/{case_result_id}/classifications")
async def classify_extraction_error(
    payload: ErrorClassificationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    case_result_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).classify_error(
        actor,
        review_id=review_id,
        case_result_id=case_result_id,
        category=payload.category,
        note=payload.note,
    )
    await session.commit()
    return {
        "id": item.id,
        "case_result_id": item.case_result_id,
        "category": item.category,
        "note": item.note,
        "classified_by_user_id": item.classified_by_user_id,
    }
