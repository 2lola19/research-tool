from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.domain import AIProposalState, AITaskType
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.core.errors import ConflictError
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService

router = APIRouter(prefix="/ai", tags=["ai"])
_GOVERNED_SCREENING_TASKS = {
    AITaskType.SCREENING_SUGGESTION,
    AITaskType.FULL_TEXT_SCREENING_SUGGESTION,
    AITaskType.EXTRACTION_SUGGESTION,
    AITaskType.ROB_SUGGESTION,
    AITaskType.OUTCOME_MAPPING_SUGGESTION,
    AITaskType.CERTAINTY_SUGGESTION,
    AITaskType.REVIEW_COPILOT,
}


class CreateRunRequest(BaseModel):
    review_id: UUID
    task_type: AITaskType
    input_data: dict[str, Any]
    model_version_id: UUID | None = None
    prompt_version_id: UUID | None = None
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    per_run_token_ceiling: int | None = Field(default=4096, ge=1, le=1_000_000)


class DecisionRequest(BaseModel):
    review_id: UUID
    decision: AIProposalState
    reason: str | None = Field(default=None, max_length=2000)


def _service(session: DbSessionDependency) -> AIExecutionService:
    reviews = ReviewService(
        SqlAlchemyReviewRepository(session), SqlAlchemyIdentityRepository(session)
    )
    return AIExecutionService(
        SqlAlchemyAIRepository(session),
        reviews,
        SqlAlchemyProvenanceRepository(session),
        {"mock": DeterministicMockAIProvider()},
    )


@router.get("/registry")
async def registry(actor: ActorContextDependency, session: DbSessionDependency) -> dict[str, Any]:
    result = await _service(session).registry(actor)
    await session.commit()
    return {
        "providers": result["providers"],
        "models": [asdict(item) for item in result["models"]],
        "prompts": [asdict(item) for item in result["prompts"]],
        "tasks": [asdict(item) for item in result["tasks"]],
    }


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: CreateRunRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    if payload.task_type in _GOVERNED_SCREENING_TASKS:
        raise ConflictError("consequential AI runs must use their governed domain endpoints")
    run, proposal = await _service(session).create_and_execute(actor, **payload.model_dump())
    await session.commit()
    return {"run": asdict(run), "proposal": asdict(proposal) if proposal else None}


@router.get("/reviews/{review_id}/runs")
async def list_runs(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> list[dict[str, Any]]:
    return [asdict(item) for item in await _service(session).list_runs(actor, review_id)]


@router.get("/reviews/{review_id}/usage")
async def usage_summary_route(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return await _service(session).usage(actor, review_id)


@router.get("/reviews/{review_id}/proposals/{proposal_id}")
async def get_proposal(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    proposal_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return asdict(await _service(session).proposal(actor, review_id, proposal_id))


@router.post("/proposals/{proposal_id}/decision")
async def decide_proposal(
    payload: DecisionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    proposal_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).decide(
        actor, payload.review_id, proposal_id, payload.decision, payload.reason
    )
    await session.commit()
    return asdict(item)
