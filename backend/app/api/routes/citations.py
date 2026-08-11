from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.citations.domain import Article, CitationFormat, CitationImportBatch
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.citations.service import CitationImportService
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/citations", tags=["citations"])


class CitationImportRequest(BaseModel):
    review_id: UUID
    source_format: CitationFormat
    source_name: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=10_000_000)


class CitationImportResponse(BaseModel):
    id: UUID
    review_id: UUID
    source_format: CitationFormat
    source_name: str
    content_hash: str
    record_count: int

    @classmethod
    def from_domain(cls, batch: CitationImportBatch) -> CitationImportResponse:
        return cls(
            id=batch.id,
            review_id=batch.review_id,
            source_format=batch.source_format,
            source_name=batch.source_name,
            content_hash=batch.content_hash,
            record_count=batch.record_count,
        )


class ArticleResponse(BaseModel):
    id: UUID
    review_id: UUID
    title: str
    abstract: str | None
    publication_year: int | None
    doi: str | None
    pmid: str | None
    authors: list[str]
    journal: str | None

    @classmethod
    def from_domain(cls, article: Article) -> ArticleResponse:
        return cls(
            id=article.id,
            review_id=article.review_id,
            title=article.title,
            abstract=article.abstract,
            publication_year=article.publication_year,
            doi=article.doi,
            pmid=article.pmid,
            authors=article.authors,
            journal=article.journal,
        )


def _service(session: DbSessionDependency) -> CitationImportService:
    return CitationImportService(
        SqlAlchemyCitationRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post(
    "/imports",
    response_model=CitationImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_citations(
    payload: CitationImportRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> CitationImportResponse:
    batch = await _service(session).import_citations(
        actor,
        review_id=payload.review_id,
        source_format=payload.source_format,
        source_name=payload.source_name,
        content=payload.content,
    )
    await session.commit()
    return CitationImportResponse.from_domain(batch)


@router.get("/reviews/{review_id}/articles", response_model=list[ArticleResponse])
async def list_articles(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[ArticleResponse]:
    articles = await _service(session).list_articles(actor, review_id)
    return [ArticleResponse.from_domain(article) for article in articles]


@router.get("/reviews/{review_id}/imports", response_model=list[CitationImportResponse])
async def list_citation_imports(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[CitationImportResponse]:
    batches = await _service(session).list_imports(actor, review_id)
    return [CitationImportResponse.from_domain(batch) for batch in batches]
