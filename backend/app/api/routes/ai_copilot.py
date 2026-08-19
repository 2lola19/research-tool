from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.copilot_domain import AICopilotQuery, AICopilotTaskKey
from backend.app.ai.copilot_persistence import SqlAlchemyAICopilotRepository
from backend.app.ai.copilot_service import AICopilotService
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.prisma.persistence import SqlAlchemyPrismaRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.workflow.persistence import SqlAlchemyWorkflowRepository

router = APIRouter(prefix="/ai/copilot", tags=["ai-copilot"])


class CopilotPolicyRequest(BaseModel):
    maximum_query_characters: int = Field(default=2_000, ge=100, le=4_000)
    maximum_context_items: int = Field(default=50, ge=2, le=200)


class CopilotQueryRequest(BaseModel):
    task_key: AICopilotTaskKey
    query: str = Field(min_length=1, max_length=4_000)
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    per_run_token_ceiling: int | None = Field(default=8_192, ge=1, le=1_000_000)


def _service(session: DbSessionDependency) -> AICopilotService:
    identity = SqlAlchemyIdentityRepository(session)
    review_repository = SqlAlchemyReviewRepository(session)
    reviews = ReviewService(review_repository, identity)
    provenance_repository = SqlAlchemyProvenanceRepository(session)
    provenance = ProvenanceService(provenance_repository, review_repository, identity)
    execution = AIExecutionService(
        SqlAlchemyAIRepository(session),
        reviews,
        provenance_repository,
        {"mock": DeterministicMockAIProvider()},
    )
    return AICopilotService(
        SqlAlchemyAICopilotRepository(session),
        reviews,
        provenance,
        execution,
        SqlAlchemyPrismaRepository(session),
        SqlAlchemyWorkflowRepository(session),
    )


def _query(item: AICopilotQuery) -> dict[str, Any]:
    return {
        "id": item.id,
        "review_id": item.review_id,
        "task_key": item.task_key,
        "query": item.query_text,
        "context_hash": item.context_hash,
        "citations": list(item.citations),
        "ai_run_id": item.ai_run_id,
        "proposal_id": item.proposal_id,
        "answer": item.answer_snapshot,
        "validation_results": item.validation_results,
        "status": item.status,
        "failure_reason": item.failure_reason,
        "stale": item.stale,
        "stale_reasons": list(item.stale_reasons),
        "created_at": item.created_at,
    }


@router.get("/tasks")
async def tasks(
    actor: ActorContextDependency, session: DbSessionDependency
) -> list[dict[str, Any]]:
    return _service(session).task_registry(actor)


@router.post("/reviews/{review_id}/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: CopilotPolicyRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).create_policy(
        actor,
        review_id=review_id,
        maximum_query_characters=payload.maximum_query_characters,
        maximum_context_items=payload.maximum_context_items,
    )
    await session.commit()
    return {
        "id": item.id,
        "review_id": item.review_id,
        "version": item.version,
        "maximum_query_characters": item.maximum_query_characters,
        "maximum_context_items": item.maximum_context_items,
    }


@router.get("/reviews/{review_id}/policy")
async def get_policy(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).get_policy(actor, review_id)
    return {
        "id": item.id,
        "review_id": item.review_id,
        "version": item.version,
        "maximum_query_characters": item.maximum_query_characters,
        "maximum_context_items": item.maximum_context_items,
    }


@router.post("/reviews/{review_id}/queries", status_code=status.HTTP_201_CREATED)
async def create_query(
    payload: CopilotQueryRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).query(
        actor,
        review_id=review_id,
        task_key=payload.task_key,
        query_text=payload.query,
        maximum_attempts=payload.maximum_attempts,
        timeout_seconds=payload.timeout_seconds,
        per_run_token_ceiling=payload.per_run_token_ceiling,
    )
    await session.commit()
    return _query(item)


@router.get("/reviews/{review_id}/queries")
async def list_queries(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    return [_query(item) for item in await _service(session).list_queries(actor, review_id)]


@router.get("/reviews/{review_id}/queries/{query_id}")
async def get_query(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    query_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    return _query(await _service(session).get_query(actor, review_id, query_id))
