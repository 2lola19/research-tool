from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.studies.domain import Study, StudyArticleLink, StudyArticleRole, StudyLinkMethod


class StudyRepository(Protocol):
    async def create_study(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        study_key: str,
        label: str | None,
        created_by_user_id: UUID,
    ) -> Study: ...
    async def get_study(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> Study | None: ...
    async def list_studies(self, organization_id: UUID, review_id: UUID) -> list[Study]: ...
    async def get_article_link(
        self, organization_id: UUID, review_id: UUID, link_id: UUID
    ) -> StudyArticleLink | None: ...
    async def list_links(
        self, organization_id: UUID, review_id: UUID, study_id: UUID, *, active_only: bool = False
    ) -> list[StudyArticleLink]: ...
    async def active_link_exists(
        self,
        organization_id: UUID,
        review_id: UUID,
        study_id: UUID,
        article_id: UUID,
        role: StudyArticleRole,
    ) -> bool: ...
    async def article_linked(
        self, organization_id: UUID, review_id: UUID, study_id: UUID, article_id: UUID
    ) -> bool: ...
    async def link_article(
        self,
        *,
        study: Study,
        article_id: UUID,
        role: StudyArticleRole,
        method: StudyLinkMethod,
        reason: str | None,
        confidence: float | None,
        source_evidence: dict[str, object] | None,
        linked_by_user_id: UUID,
    ) -> StudyArticleLink: ...
    async def unlink_article(
        self, *, organization_id: UUID, review_id: UUID, link_id: UUID, unlinked_by_user_id: UUID
    ) -> StudyArticleLink | None: ...
