from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import (
    ActorContextDependency,
    DbSessionDependency,
    SettingsDependency,
    build_authentication_provider,
)
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.identity.security import ScryptPasswordHasher
from backend.app.identity.service import AuthenticationService, MembershipService
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(tags=["identity"])


class TokenRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class ActorResponse(BaseModel):
    user_id: UUID
    organization_id: UUID
    membership_id: UUID
    role: str


@router.post("/auth/token", response_model=TokenResponse)
async def create_access_token(
    payload: TokenRequest,
    session: DbSessionDependency,
    settings: SettingsDependency,
) -> TokenResponse:
    repository = SqlAlchemyIdentityRepository(session)
    provider = build_authentication_provider(settings)
    service = AuthenticationService(repository, ScryptPasswordHasher(), provider)
    token = await service.login(payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.get("/auth/me", response_model=ActorResponse)
async def get_authenticated_actor(actor: ActorContextDependency) -> ActorResponse:
    return ActorResponse(
        user_id=actor.user_id,
        organization_id=actor.organization_id,
        membership_id=actor.membership_id,
        role=actor.role.value,
    )


@router.delete(
    "/organizations/current/memberships/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_organization_membership(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    user_id: Annotated[UUID, Path()],
) -> None:
    repository = SqlAlchemyIdentityRepository(session)
    await MembershipService(repository, SqlAlchemyReviewRepository(session)).remove_membership(
        actor,
        user_id,
    )
    await session.commit()
