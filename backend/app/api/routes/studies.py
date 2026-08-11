from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.studies.domain import Study, StudyArticleLink, StudyArticleRole, StudyLinkMethod
from backend.app.studies.persistence import SqlAlchemyStudyRepository
from backend.app.studies.service import StudyService

router = APIRouter(prefix="/studies", tags=["studies"])


class StudyRequest(BaseModel):
    review_id: UUID
    study_key: str = Field(min_length=1, max_length=100)
    label: str | None = Field(default=None, max_length=500)
    study_design: str | None = Field(default=None, min_length=1, max_length=100)


class ArticleLinkRequest(BaseModel):
    review_id: UUID
    article_id: UUID
    role: StudyArticleRole
    method: StudyLinkMethod = StudyLinkMethod.MANUAL
    reason: str | None = Field(default=None, max_length=4000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_evidence: dict[str, object] | None = None


class StudyResponse(BaseModel):
    id: UUID
    review_id: UUID
    study_key: str
    label: str | None
    study_design: str | None

    @classmethod
    def from_domain(cls, item: Study) -> StudyResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            study_key=item.study_key,
            label=item.label,
            study_design=item.study_design,
        )


class LinkResponse(BaseModel):
    id: UUID
    study_id: UUID
    article_id: UUID
    role: StudyArticleRole
    method: StudyLinkMethod
    reason: str | None
    confidence: float | None
    source_evidence: dict[str, object] | None
    active: bool

    @classmethod
    def from_domain(cls, item: StudyArticleLink) -> LinkResponse:
        return cls(
            id=item.id,
            study_id=item.study_id,
            article_id=item.article_id,
            role=item.role,
            method=item.method,
            reason=item.reason,
            confidence=item.confidence,
            source_evidence=item.source_evidence,
            active=item.active,
        )


def _service(session: DbSessionDependency) -> StudyService:
    return StudyService(
        SqlAlchemyStudyRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
async def create_study(
    payload: StudyRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> StudyResponse:
    study = await _service(session).create(
        actor,
        review_id=payload.review_id,
        study_key=payload.study_key,
        label=payload.label,
        study_design=payload.study_design,
    )
    await session.commit()
    return StudyResponse.from_domain(study)


@router.get("/reviews/{review_id}", response_model=list[StudyResponse])
async def list_studies(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> list[StudyResponse]:
    return [
        StudyResponse.from_domain(item)
        for item in await _service(session).list_studies(actor, review_id=review_id)
    ]


@router.post(
    "/{study_id}/articles", response_model=LinkResponse, status_code=status.HTTP_201_CREATED
)
async def link_article(
    payload: ArticleLinkRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    study_id: Annotated[UUID, Path()],
) -> LinkResponse:
    link = await _service(session).link(
        actor,
        review_id=payload.review_id,
        study_id=study_id,
        article_id=payload.article_id,
        role=payload.role,
        method=payload.method,
        reason=payload.reason,
        confidence=payload.confidence,
        source_evidence=payload.source_evidence,
    )
    await session.commit()
    return LinkResponse.from_domain(link)


@router.get("/{study_id}/articles", response_model=list[LinkResponse])
async def list_links(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    study_id: Annotated[UUID, Path()],
    review_id: UUID,
    active_only: bool = True,
) -> list[LinkResponse]:
    return [
        LinkResponse.from_domain(item)
        for item in await _service(session).links(
            actor, review_id=review_id, study_id=study_id, active_only=active_only
        )
    ]


@router.delete("/links/{link_id}", response_model=LinkResponse)
async def unlink_article(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    link_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> LinkResponse:
    link = await _service(session).unlink(actor, review_id=review_id, link_id=link_id)
    await session.commit()
    return LinkResponse.from_domain(link)
