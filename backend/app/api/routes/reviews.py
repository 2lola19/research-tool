from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.reviews.domain import ReviewParticipant, ReviewProject
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    project_slug: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)


class ReviewUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    project_slug: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)


class ReviewAssignmentRequest(BaseModel):
    user_id: UUID


class ReviewOwnershipRequest(BaseModel):
    user_id: UUID


class ReviewResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    project_slug: str
    description: str | None
    owner_user_id: UUID
    created_by_user_id: UUID
    archived: bool
    archived_by_user_id: UUID | None

    @classmethod
    def from_domain(cls, review: ReviewProject) -> ReviewResponse:
        return cls(
            id=review.id,
            organization_id=review.organization_id,
            title=review.title,
            project_slug=review.project_slug,
            description=review.description,
            owner_user_id=review.owner_user_id,
            created_by_user_id=review.created_by_user_id,
            archived=review.archived_at is not None,
            archived_by_user_id=review.archived_by_user_id,
        )


class ReviewParticipantResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    organization_role: str

    @classmethod
    def from_domain(cls, participant: ReviewParticipant) -> ReviewParticipantResponse:
        return cls(
            user_id=participant.user_id,
            email=participant.email,
            display_name=participant.display_name,
            organization_role=participant.organization_role,
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
    review = await _service(session).create(
        actor,
        payload.title,
        payload.project_slug,
        payload.description,
    )
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
    review = await _service(session).update_metadata(
        actor,
        review_id,
        payload.title,
        payload.project_slug,
        payload.description,
    )
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


@router.get("/{review_id}/memberships", response_model=list[ReviewParticipantResponse])
async def list_review_members(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[ReviewParticipantResponse]:
    participants = await _service(session).list_participants(actor, review_id)
    return [ReviewParticipantResponse.from_domain(item) for item in participants]


@router.delete(
    "/{review_id}/memberships/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_review_member(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    user_id: Annotated[UUID, Path()],
) -> None:
    await _service(session).remove_user(actor, review_id, user_id)
    await session.commit()


@router.post("/{review_id}/ownership", response_model=ReviewResponse)
async def transfer_review_ownership(
    payload: ReviewOwnershipRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> ReviewResponse:
    review = await _service(session).transfer_ownership(actor, review_id, payload.user_id)
    await session.commit()
    return ReviewResponse.from_domain(review)


@router.post("/{review_id}/archive", response_model=ReviewResponse)
async def archive_review(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> ReviewResponse:
    review = await _service(session).set_archived(actor, review_id, archived=True)
    await session.commit()
    return ReviewResponse.from_domain(review)


@router.delete("/{review_id}/archive", response_model=ReviewResponse)
async def restore_review(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> ReviewResponse:
    review = await _service(session).set_archived(actor, review_id, archived=False)
    await session.commit()
    return ReviewResponse.from_domain(review)
