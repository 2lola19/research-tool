from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path

from backend.app.ai.queries import list_attempts, usage_summary
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService

router = APIRouter(prefix="/ai", tags=["ai"])


async def _authorize(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: UUID
) -> None:
    await ReviewService(
        SqlAlchemyReviewRepository(session), SqlAlchemyIdentityRepository(session)
    ).get(actor, review_id)


@router.get("/reviews/{review_id}/runs/{run_id}/attempts")
async def attempts(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    run_id: Annotated[UUID, Path()],
) -> list[dict[str, Any]]:
    await _authorize(actor, session, review_id)
    return await list_attempts(session, actor.organization_id, review_id, run_id)


@router.get("/reviews/{review_id}/usage")
async def usage(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    await _authorize(actor, session, review_id)
    return await usage_summary(session, actor.organization_id, review_id)
