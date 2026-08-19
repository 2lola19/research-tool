from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.outcome_domain import (
    AIOutcomeErrorCategory,
    AIOutcomeReferenceStandard,
    AIOutcomeReviewAction,
)
from backend.app.ai.outcome_persistence import SqlAlchemyAIOutcomeRepository
from backend.app.ai.outcome_service import AIOutcomeProposalView, AIOutcomeService
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.outcomes.persistence import SqlAlchemyOutcomeRepository
from backend.app.outcomes.service import OutcomeService
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.studies.persistence import SqlAlchemyStudyRepository

router = APIRouter(prefix="/ai/outcomes", tags=["ai-outcomes"])


class OutcomeSourceRequest(BaseModel):
    document_id: UUID
    document_role: str = Field(default="PRIMARY_FULL_TEXT", min_length=1, max_length=50)


class OutcomeReadinessRequest(BaseModel):
    extraction_value_id: UUID
    outcome_version_id: UUID
    documents: list[OutcomeSourceRequest] = Field(min_length=1, max_length=8)


class OutcomeBatchItemRequest(OutcomeReadinessRequest):
    pass


class OutcomeBatchRequest(BaseModel):
    items: list[OutcomeBatchItemRequest] = Field(min_length=1, max_length=100)
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    per_run_token_ceiling: int | None = Field(default=16_384, ge=1, le=1_000_000)


class OutcomePolicyRequest(BaseModel):
    maximum_batch_size: int = Field(default=20, ge=1, le=100)


class OutcomeReviewRequest(BaseModel):
    action: AIOutcomeReviewAction
    canonical_action: str | None = Field(default=None, max_length=40)
    human_payload: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=4_000)


class OutcomeDatasetRequest(BaseModel):
    logical_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    reference_standard: AIOutcomeReferenceStandard
    cases: list[dict[str, Any]] = Field(min_length=1, max_length=100_000)


class OutcomeErrorRequest(BaseModel):
    case_key: str = Field(min_length=1, max_length=160)
    category: AIOutcomeErrorCategory
    note: str | None = Field(default=None, max_length=4_000)


def _service(session: DbSessionDependency) -> AIOutcomeService:
    identity = SqlAlchemyIdentityRepository(session)
    review_repository = SqlAlchemyReviewRepository(session)
    reviews = ReviewService(review_repository, identity)
    provenance_repository = SqlAlchemyProvenanceRepository(session)
    provenance = ProvenanceService(provenance_repository, review_repository, identity)
    outcome_repository = SqlAlchemyOutcomeRepository(session)
    studies = SqlAlchemyStudyRepository(session)
    outcome_service = OutcomeService(
        outcome_repository,
        studies,
        review_repository,
        identity,
        provenance_repository,
    )
    ai_repository = SqlAlchemyAIRepository(session)
    execution = AIExecutionService(
        ai_repository,
        reviews,
        provenance_repository,
        {"mock": DeterministicMockAIProvider()},
    )
    return AIOutcomeService(
        SqlAlchemyAIOutcomeRepository(session),
        ai_repository,
        outcome_repository,
        SqlAlchemyDocumentRepository(session),
        studies,
        reviews,
        provenance,
        execution,
        outcome_service,
    )


def _proposal(item: AIOutcomeProposalView) -> dict[str, Any]:
    return {
        "extraction_value_id": item.extraction_value_id,
        "study_id": item.study_id,
        "outcome_version_id": item.outcome_version_id,
        "proposal_id": item.proposal_id,
        "ai_run_id": item.ai_run_id,
        "readiness": item.readiness.value,
        "status": item.status,
        "failure_reason": item.failure_reason,
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
async def create_policy(
    payload: OutcomePolicyRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).create_policy(
        actor, review_id=review_id, maximum_batch_size=payload.maximum_batch_size
    )
    await session.commit()
    return {
        "id": item.id,
        "review_id": item.review_id,
        "version": item.version,
        "maximum_batch_size": item.maximum_batch_size,
    }


@router.post("/reviews/{review_id}/readiness")
async def readiness(
    payload: OutcomeReadinessRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).readiness(
        actor,
        review_id=review_id,
        extraction_value_id=payload.extraction_value_id,
        outcome_version_id=payload.outcome_version_id,
        documents=[entry.model_dump() for entry in payload.documents],
    )
    return {
        "extraction_value_id": item.extraction_value_id,
        "study_id": item.study_id,
        "outcome_version_id": item.outcome_version_id,
        "state": item.state.value,
        "reason": item.reason,
    }


@router.post("/reviews/{review_id}/proposals", status_code=status.HTTP_201_CREATED)
async def create_proposals(
    payload: OutcomeBatchRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    items = await _service(session).create_suggestions(
        actor,
        review_id=review_id,
        requests=[
            {
                "extraction_value_id": entry.extraction_value_id,
                "outcome_version_id": entry.outcome_version_id,
                "documents": [document.model_dump() for document in entry.documents],
            }
            for entry in payload.items
        ],
        model_version_id=payload.model_version_id,
        prompt_version_id=payload.prompt_version_id,
        maximum_attempts=payload.maximum_attempts,
        timeout_seconds=payload.timeout_seconds,
        per_run_token_ceiling=payload.per_run_token_ceiling,
    )
    await session.commit()
    return [_proposal(item) for item in items]


@router.get("/reviews/{review_id}/proposals")
async def list_proposals(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        _proposal(item)
        for item in await _service(session).list_proposals(actor, review_id=review_id)
    ]


@router.get("/reviews/{review_id}/proposals/{proposal_id}")
async def get_proposal(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    proposal_id: Annotated[UUID, Path()],
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return _proposal(
        await _service(session).get_proposal(actor, review_id=review_id, proposal_id=proposal_id)
    )


@router.post("/reviews/{review_id}/proposals/{proposal_id}/review")
async def review_proposal(
    payload: OutcomeReviewRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    proposal_id: Annotated[UUID, Path()],
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    result = await _service(session).review_proposal(
        actor,
        review_id=review_id,
        proposal_id=proposal_id,
        action=payload.action,
        canonical_action=payload.canonical_action,
        human_payload=payload.human_payload,
        reason=payload.reason,
    )
    await session.commit()
    return result


@router.post("/reviews/{review_id}/evaluation-datasets", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    payload: OutcomeDatasetRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).create_dataset(
        actor, review_id=review_id, **payload.model_dump()
    )
    await session.commit()
    return {
        "id": item.id,
        "review_id": item.review_id,
        "logical_key": item.logical_key,
        "version": item.version,
        "name": item.name,
        "reference_standard": item.reference_standard,
        "content_hash": item.content_hash,
    }


@router.get("/reviews/{review_id}/evaluation-datasets")
async def list_datasets(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "review_id": item.review_id,
            "logical_key": item.logical_key,
            "version": item.version,
            "name": item.name,
            "reference_standard": item.reference_standard,
            "content_hash": item.content_hash,
        }
        for item in await _service(session).list_datasets(actor, review_id=review_id)
    ]


@router.post("/reviews/{review_id}/evaluation-datasets/{dataset_id}/evaluate")
async def evaluate_dataset(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    dataset_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).evaluate_dataset(
        actor, review_id=review_id, dataset_id=dataset_id
    )
    await session.commit()
    return _evaluation(item)


@router.get("/reviews/{review_id}/evaluations")
async def list_evaluations(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        _evaluation(item)
        for item in await _service(session).list_evaluations(actor, review_id=review_id)
    ]


@router.post("/reviews/{review_id}/evaluations/{evaluation_result_id}/errors")
async def classify_error(
    payload: OutcomeErrorRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    evaluation_result_id: Annotated[UUID, Path()],
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).classify_error(
        actor,
        review_id=review_id,
        evaluation_result_id=evaluation_result_id,
        **payload.model_dump(),
    )
    await session.commit()
    return {
        "id": item.id,
        "evaluation_result_id": item.evaluation_result_id,
        "case_key": item.case_key,
        "category": item.category,
        "note": item.note,
    }


def _evaluation(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "review_id": item.review_id,
        "dataset_id": item.dataset_id,
        "metrics": item.metrics,
        "dimensions": item.dimensions,
        "case_results": item.case_results,
        "result_hash": item.result_hash,
    }
