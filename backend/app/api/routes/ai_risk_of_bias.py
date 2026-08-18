from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.rob_domain import (
    AIRobErrorCategory,
    AIRobReferenceStandard,
    AIRobReviewAction,
)
from backend.app.ai.rob_persistence import SqlAlchemyAIRobRepository
from backend.app.ai.rob_service import AIRiskOfBiasService, AIRobProposalView
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.risk_of_bias.persistence import SqlAlchemyRiskOfBiasRepository
from backend.app.risk_of_bias.service import RiskOfBiasService
from backend.app.studies.persistence import SqlAlchemyStudyRepository

router = APIRouter(prefix="/ai/risk-of-bias", tags=["ai-risk-of-bias"])


class RobPolicyRequest(BaseModel):
    mode: AIScreeningMode
    maximum_batch_size: int = Field(default=20, ge=1, le=100)


class RobSourceRequest(BaseModel):
    document_id: UUID
    document_role: str = Field(default="PRIMARY_FULL_TEXT", min_length=1, max_length=50)


class RobReadinessRequest(BaseModel):
    assessment_id: UUID
    documents: list[RobSourceRequest] = Field(min_length=1, max_length=8)


class RobBatchItemRequest(BaseModel):
    assessment_id: UUID
    documents: list[RobSourceRequest] = Field(min_length=1, max_length=8)


class RobBatchRequest(BaseModel):
    items: list[RobBatchItemRequest] = Field(min_length=1, max_length=100)
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    per_run_token_ceiling: int | None = Field(default=16_384, ge=1, le=1_000_000)


class RobAnswerReviewRequest(BaseModel):
    action: AIRobReviewAction
    human_answer: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=4_000)


class RobEvaluationCaseRequest(BaseModel):
    study_id: UUID
    assessment_id: UUID | None = None
    question_key: str | None = Field(default=None, max_length=120)
    reference_answers: dict[str, str]
    reference_domains: dict[str, str] | None = None
    reference_overall: str | None = Field(default=None, max_length=120)
    evidence_snapshot: dict[str, Any] | None = None


class RobEvaluationDatasetRequest(BaseModel):
    instrument_version_id: UUID
    logical_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    reference_standard: AIRobReferenceStandard
    cases: list[RobEvaluationCaseRequest] = Field(min_length=1, max_length=100_000)


class RobErrorClassificationRequest(BaseModel):
    category: AIRobErrorCategory
    note: str | None = Field(default=None, max_length=4_000)


def _service(session: DbSessionDependency) -> AIRiskOfBiasService:
    identity = SqlAlchemyIdentityRepository(session)
    review_repository = SqlAlchemyReviewRepository(session)
    reviews = ReviewService(review_repository, identity)
    provenance_repository = SqlAlchemyProvenanceRepository(session)
    provenance = ProvenanceService(provenance_repository, review_repository, identity)
    ai_repository = SqlAlchemyAIRepository(session)
    rob_repository = SqlAlchemyRiskOfBiasRepository(session)
    rob_service = RiskOfBiasService(
        rob_repository,
        SqlAlchemyStudyRepository(session),
        review_repository,
        identity,
        provenance_repository,
    )
    execution = AIExecutionService(
        ai_repository,
        reviews,
        provenance_repository,
        {"mock": DeterministicMockAIProvider()},
    )
    return AIRiskOfBiasService(
        SqlAlchemyAIRobRepository(session),
        ai_repository,
        rob_repository,
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyStudyRepository(session),
        reviews,
        provenance,
        execution,
        rob_service,
    )


def _proposal_response(item: AIRobProposalView) -> dict[str, Any]:
    return {
        "assessment_id": item.assessment_id,
        "study_id": item.study_id,
        "instrument_version_id": item.instrument_version_id,
        "proposal_id": item.proposal_id,
        "ai_run_id": item.ai_run_id,
        "mode": item.mode.value,
        "readiness": item.readiness.value,
        "status": item.status,
        "failure_reason": item.failure_reason,
        "is_revealed": item.is_revealed,
        "structured_value": item.structured_value,
        "validation_results": item.validation_results,
        "domain_suggestions": item.domain_suggestions,
        "overall_suggestion": item.overall_suggestion,
        "stale": item.stale,
        "stale_reasons": list(item.stale_reasons),
        "source_manifest": list(item.source_manifest),
        "selected_chunk_ids": list(item.selected_chunk_ids),
        "omitted_chunk_count": item.omitted_chunk_count,
        "selection_method": item.selection_method,
    }


@router.post("/reviews/{review_id}/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: RobPolicyRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).create_policy(
        actor,
        review_id=review_id,
        mode=payload.mode,
        maximum_batch_size=payload.maximum_batch_size,
    )
    await session.commit()
    return {
        "id": item.id,
        "review_id": item.review_id,
        "version": item.version,
        "mode": item.mode.value,
        "maximum_batch_size": item.maximum_batch_size,
    }


@router.post("/reviews/{review_id}/readiness")
async def readiness(
    payload: RobReadinessRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).readiness(
        actor,
        review_id=review_id,
        assessment_id=payload.assessment_id,
        documents=[source.model_dump(mode="json") for source in payload.documents],
    )
    return {
        "assessment_id": item.assessment_id,
        "study_id": item.study_id,
        "instrument_version_id": item.instrument_version_id,
        "state": item.state.value,
        "reason": item.reason,
    }


@router.post("/reviews/{review_id}/proposals", status_code=status.HTTP_201_CREATED)
async def create_proposals(
    payload: RobBatchRequest,
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
async def list_proposals(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        _proposal_response(item)
        for item in await _service(session).list_suggestions(actor, review_id=review_id)
    ]


@router.get("/reviews/{review_id}/assessments/{assessment_id}")
async def get_assignment_proposal(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    assessment_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return _proposal_response(
        await _service(session).get_suggestion(
            actor, review_id=review_id, assessment_id=assessment_id
        )
    )


@router.get("/reviews/{review_id}/proposals/{proposal_id}")
async def get_proposal(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    proposal_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return _proposal_response(
        await _service(session).get_suggestion(actor, review_id=review_id, proposal_id=proposal_id)
    )


@router.post("/reviews/{review_id}/proposals/{proposal_id}/answers/{question_key}/review")
async def review_answer(
    payload: RobAnswerReviewRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    proposal_id: Annotated[UUID, Path()],
    question_key: Annotated[str, Path(min_length=1, max_length=120)],
) -> dict[str, Any]:
    item = await _service(session).review_answer(
        actor,
        review_id=review_id,
        proposal_id=proposal_id,
        question_key=question_key,
        action=payload.action,
        human_answer=payload.human_answer,
        reason=payload.reason,
    )
    await session.commit()
    return item


@router.post("/reviews/{review_id}/evaluation-datasets", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    payload: RobEvaluationDatasetRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).create_dataset(
        actor,
        review_id=review_id,
        instrument_version_id=payload.instrument_version_id,
        logical_key=payload.logical_key,
        name=payload.name,
        reference_standard=payload.reference_standard,
        cases=[case.model_dump(mode="json") for case in payload.cases],
    )
    await session.commit()
    return {
        "id": item.id,
        "instrument_version_id": item.instrument_version_id,
        "logical_key": item.logical_key,
        "version": item.version,
        "reference_standard": item.reference_standard.value,
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
            "instrument_version_id": item.instrument_version_id,
            "logical_key": item.logical_key,
            "version": item.version,
            "reference_standard": item.reference_standard.value,
            "content_hash": item.content_hash,
        }
        for item in await _service(session).list_datasets(actor, review_id=review_id)
    ]


@router.post(
    "/reviews/{review_id}/evaluation-datasets/{dataset_id}/evaluate",
    status_code=status.HTTP_201_CREATED,
)
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
    return {
        "id": item.id,
        "dataset_id": item.dataset_id,
        "metrics": item.metrics,
        "dimensions": item.dimensions,
        "result_hash": item.result_hash,
    }


@router.get("/reviews/{review_id}/evaluations")
async def list_evaluations(
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
async def high_risk_queue(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    evaluation_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "case_id": item.case_id,
            "proposal_id": item.proposal_id,
            "classification": item.classification,
            "dangerous_underestimation": item.dangerous_underestimation,
            "details": item.details,
        }
        for item in await _service(session).high_risk_queue(
            actor, review_id=review_id, evaluation_id=evaluation_id
        )
    ]


@router.get("/reviews/{review_id}/evaluations/{evaluation_id}/case-results")
async def case_results(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    evaluation_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "case_id": item.case_id,
            "proposal_id": item.proposal_id,
            "classification": item.classification,
            "signalling_agreement": item.signalling_agreement,
            "domain_agreement": item.domain_agreement,
            "overall_agreement": item.overall_agreement,
            "evidence_grounding_valid": item.evidence_grounding_valid,
            "abstention": item.abstention,
            "dangerous_underestimation": item.dangerous_underestimation,
            "details": item.details,
        }
        for item in await _service(session).list_case_results(
            actor, review_id=review_id, evaluation_id=evaluation_id
        )
    ]


@router.post("/reviews/{review_id}/evaluation-case-results/{case_result_id}/classifications")
async def classify_error(
    payload: RobErrorClassificationRequest,
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
