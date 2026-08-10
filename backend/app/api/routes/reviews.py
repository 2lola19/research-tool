from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.reviews.domain import ReviewProject
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class ReviewUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class ReviewAssignmentRequest(BaseModel):
    user_id: UUID


class ReviewResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    owner_user_id: UUID
    created_by_user_id: UUID

    @classmethod
    def from_domain(cls, review: ReviewProject) -> ReviewResponse:
        return cls(
            id=review.id,
            organization_id=review.organization_id,
            title=review.title,
            owner_user_id=review.owner_user_id,
            created_by_user_id=review.created_by_user_id,
        )


def _service(session: DbSessionDependency) -> ReviewService:
    return ReviewService(
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
    )


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: ReviewCreateRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> ReviewResponse:
    review = await _service(session).create(actor, payload.title)
    await session.commit()
    return ReviewResponse.from_domain(review)


@router.get("", response_model=list[ReviewResponse])
async def list_reviews(
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> list[ReviewResponse]:
    reviews = await _service(session).list(actor)
    return [ReviewResponse.from_domain(review) for review in reviews]


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> ReviewResponse:
    review = await _service(session).get(actor, review_id)
    return ReviewResponse.from_domain(review)


@router.patch("/{review_id}", response_model=ReviewResponse)
async def update_review(
    payload: ReviewUpdateRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> ReviewResponse:
    review = await _service(session).update_title(actor, review_id, payload.title)
    await session.commit()
    return ReviewResponse.from_domain(review)


@router.post("/{review_id}/memberships", status_code=status.HTTP_204_NO_CONTENT)
async def assign_review_member(
    payload: ReviewAssignmentRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> None:
    await _service(session).assign_user(actor, review_id, payload.user_id)
    await session.commit()
