from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.citations.domain import (
    Article,
    CitationFormat,
    CitationImportBatch,
    CitationSourceRecord,
    ParsedCitation,
)


class CitationRepository(Protocol):
    async def get_batch_by_hash(
        self,
        organization_id: UUID,
        review_id: UUID,
        source_format: CitationFormat,
        content_hash: str,
    ) -> CitationImportBatch | None: ...

    async def create_import(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        source_format: CitationFormat,
        source_name: str,
        source_content: str,
        content_hash: str,
        records: list[ParsedCitation],
        imported_by_user_id: UUID,
    ) -> tuple[CitationImportBatch, list[tuple[Article, CitationSourceRecord]]]: ...

    async def get_batch(
        self, organization_id: UUID, batch_id: UUID
    ) -> CitationImportBatch | None: ...

    async def list_batches(
        self, organization_id: UUID, review_id: UUID
    ) -> list[CitationImportBatch]: ...

    async def list_articles(self, organization_id: UUID, review_id: UUID) -> list[Article]: ...

    async def get_article(
        self, organization_id: UUID, review_id: UUID, article_id: UUID
    ) -> Article | None: ...
