from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field, field_validator

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.protocols.persistence import SqlAlchemyProtocolRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.search.domain import SearchStrategyVersion, SearchTranslation
from backend.app.search.persistence import SqlAlchemySearchRepository
from backend.app.search.service import SearchStrategyService

router = APIRouter(prefix="/search-strategies", tags=["search strategies"])


class SearchTerm(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    field: Literal["all", "title_abstract", "mesh"] = "all"

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class SearchConcept(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    terms: list[SearchTerm] = Field(min_length=1, max_length=500)


class SearchStrategyContent(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    concepts: list[SearchConcept] = Field(min_length=1, max_length=50)


class SearchStrategyRequest(BaseModel):
    review_id: UUID
    protocol_version_id: UUID
    content: SearchStrategyContent


class TranslationRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=80)


class SearchStrategyResponse(BaseModel):
    id: UUID
    review_id: UUID
    protocol_version_id: UUID
    version: int
    content: SearchStrategyContent
    content_hash: str

    @classmethod
    def from_domain(cls, strategy: SearchStrategyVersion) -> SearchStrategyResponse:
        return cls(
            id=strategy.id,
            review_id=strategy.review_id,
            protocol_version_id=strategy.protocol_version_id,
            version=strategy.version,
            content=SearchStrategyContent.model_validate(strategy.content),
            content_hash=strategy.content_hash,
        )


class TranslationResponse(BaseModel):
    id: UUID
    search_strategy_version_id: UUID
    provider: str
    translator_version: str
    query: str

    @classmethod
    def from_domain(cls, translation: SearchTranslation) -> TranslationResponse:
        return cls(
            id=translation.id,
            search_strategy_version_id=translation.search_strategy_version_id,
            provider=translation.provider,
            translator_version=translation.translator_version,
            query=translation.query,
        )


def _service(session: DbSessionDependency) -> SearchStrategyService:
    return SearchStrategyService(
        SqlAlchemySearchRepository(session),
        SqlAlchemyProtocolRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post(
    "/versions",
    response_model=SearchStrategyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_search_strategy_version(
    payload: SearchStrategyRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> SearchStrategyResponse:
    strategy = await _service(session).create_version(
        actor,
        review_id=payload.review_id,
        protocol_version_id=payload.protocol_version_id,
        content=payload.content.model_dump(mode="json"),
    )
    await session.commit()
    return SearchStrategyResponse.from_domain(strategy)


@router.get("/reviews/{review_id}/versions", response_model=list[SearchStrategyResponse])
async def list_search_strategy_versions(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[SearchStrategyResponse]:
    strategies = await _service(session).list_versions(actor, review_id)
    return [SearchStrategyResponse.from_domain(item) for item in strategies]


@router.post(
    "/versions/{strategy_version_id}/translations",
    response_model=TranslationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def translate_search_strategy(
    payload: TranslationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    strategy_version_id: Annotated[UUID, Path()],
) -> TranslationResponse:
    translation = await _service(session).translate(
        actor,
        strategy_version_id=strategy_version_id,
        provider=payload.provider,
    )
    await session.commit()
    return TranslationResponse.from_domain(translation)
