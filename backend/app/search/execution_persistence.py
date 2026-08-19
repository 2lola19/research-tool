from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.citations.persistence import CitationSourceRecordRow
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.search.execution_domain import (
    IdentificationSource,
    IdentificationSourceClassification,
    SearchExecution,
    SearchExecutionArtifact,
    SearchExecutionCitationLink,
    SearchExecutionEvent,
    SearchExecutionMethod,
    SearchExecutionStatus,
)

SOURCE_CLASSIFICATIONS = tuple(item.value for item in IdentificationSourceClassification)
EXECUTION_METHODS = tuple(item.value for item in SearchExecutionMethod)
EXECUTION_STATUSES = tuple(item.value for item in SearchExecutionStatus)


def _sql_values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class IdentificationSourceRecord(Base):
    __tablename__ = "identification_sources"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "source_key", name="uq_identification_sources_key"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_identification_sources_id_tenant"
        ),
        CheckConstraint(
            f"classification IN ({_sql_values(SOURCE_CLASSIFICATIONS)})",
            name="ck_identification_sources_classification",
        ),
        CheckConstraint("length(trim(source_key)) > 0", name="ck_identification_source_key"),
        CheckConstraint("length(trim(display_name)) > 0", name="ck_identification_source_name"),
        CheckConstraint(
            "length(trim(provider_name)) > 0", name="ck_identification_source_provider"
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_identification_sources_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_identification_sources_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    source_key: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(300))
    classification: Mapped[str] = mapped_column(String(40))
    provider_name: Mapped[str] = mapped_column(String(200))
    platform_name: Mapped[str | None] = mapped_column(String(200))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchExecutionRecord(Base):
    __tablename__ = "search_executions"
    __table_args__ = (
        Index(
            "ix_search_executions_review_date",
            "organization_id",
            "review_id",
            "executed_at",
            "id",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_executions_id_tenant"
        ),
        UniqueConstraint("supersedes_execution_id", name="uq_search_executions_single_correction"),
        CheckConstraint(
            f"method IN ({_sql_values(EXECUTION_METHODS)})", name="ck_search_execution_method"
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_search_executions_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_id", "organization_id", "review_id"],
            [
                "identification_sources.id",
                "identification_sources.organization_id",
                "identification_sources.review_id",
            ],
            name="fk_search_executions_source_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["search_strategy_version_id", "organization_id", "review_id"],
            [
                "search_strategy_versions.id",
                "search_strategy_versions.organization_id",
                "search_strategy_versions.review_id",
            ],
            name="fk_search_executions_strategy_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "search_translation_id",
                "search_strategy_version_id",
                "organization_id",
                "review_id",
            ],
            [
                "search_translations.id",
                "search_translations.search_strategy_version_id",
                "search_translations.organization_id",
                "search_translations.review_id",
            ],
            name="fk_search_executions_translation_strategy",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_executions_superseded_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_executions_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    source_id: Mapped[UUID] = mapped_column()
    search_strategy_version_id: Mapped[UUID | None] = mapped_column()
    search_translation_id: Mapped[UUID | None] = mapped_column()
    supersedes_execution_id: Mapped[UUID | None] = mapped_column()
    method: Mapped[str] = mapped_column(String(30))
    exact_query: Mapped[str | None] = mapped_column(Text)
    filters: Mapped[dict[str, str]] = mapped_column(JSON)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    software_version: Mapped[str | None] = mapped_column(String(120))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchExecutionEventRecord(Base):
    __tablename__ = "search_execution_events"
    __table_args__ = (
        UniqueConstraint(
            "search_execution_id", "sequence", name="uq_search_execution_events_sequence"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_execution_events_id_tenant"
        ),
        CheckConstraint("sequence > 0", name="ck_search_execution_event_sequence"),
        CheckConstraint(
            f"status IN ({_sql_values(EXECUTION_STATUSES)})", name="ck_search_execution_status"
        ),
        CheckConstraint(
            "provider_result_count IS NULL OR provider_result_count >= 0",
            name="ck_search_execution_result_count",
        ),
        CheckConstraint(
            "status != 'COMPLETED' OR provider_result_count IS NOT NULL",
            name="ck_completed_search_execution_result_count",
        ),
        ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_execution_events_execution_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "recorded_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_execution_events_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    search_execution_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    provider_result_count: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by_user_id: Mapped[UUID] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SearchExecutionCitationLinkRecord(Base):
    __tablename__ = "search_execution_citation_links"
    __table_args__ = (
        Index(
            "ix_search_execution_links_citation",
            "organization_id",
            "review_id",
            "citation_source_record_id",
        ),
        UniqueConstraint(
            "search_execution_id",
            "citation_source_record_id",
            name="uq_search_execution_citation_link",
        ),
        ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_execution_links_execution_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["citation_source_record_id", "organization_id", "review_id"],
            [
                "citation_source_records.id",
                "citation_source_records.organization_id",
                "citation_source_records.review_id",
            ],
            name="fk_search_execution_links_citation_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "linked_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_execution_links_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    search_execution_id: Mapped[UUID] = mapped_column()
    citation_source_record_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    linked_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchExecutionArtifactRecord(Base):
    __tablename__ = "search_execution_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "search_execution_id", "sha256", name="uq_search_execution_artifact_checksum"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_execution_artifact_id_tenant"
        ),
        CheckConstraint("byte_size > 0", name="ck_search_execution_artifact_size"),
        CheckConstraint("length(sha256) = 64", name="ck_search_execution_artifact_hash"),
        ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_execution_artifacts_execution_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_execution_artifacts_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    search_execution_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(200))
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("search execution provenance is append-only")


for _record_type in (
    IdentificationSourceRecord,
    SearchExecutionRecord,
    SearchExecutionEventRecord,
    SearchExecutionCitationLinkRecord,
    SearchExecutionArtifactRecord,
):
    event.listen(_record_type, "before_update", _reject_mutation)
    event.listen(_record_type, "before_delete", _reject_mutation)


def _source(row: IdentificationSourceRecord) -> IdentificationSource:
    return IdentificationSource(
        row.id,
        row.organization_id,
        row.review_id,
        row.source_key,
        row.display_name,
        IdentificationSourceClassification(row.classification),
        row.provider_name,
        row.platform_name,
        row.created_by_user_id,
        _as_utc(row.created_at),
    )


def _event(row: SearchExecutionEventRecord) -> SearchExecutionEvent:
    return SearchExecutionEvent(
        row.id,
        row.search_execution_id,
        row.sequence,
        SearchExecutionStatus(row.status),
        row.provider_result_count,
        row.note,
        row.recorded_by_user_id,
        _as_utc(row.occurred_at),
    )


def _link(row: SearchExecutionCitationLinkRecord) -> SearchExecutionCitationLink:
    return SearchExecutionCitationLink(
        row.id,
        row.search_execution_id,
        row.citation_source_record_id,
        row.linked_by_user_id,
        _as_utc(row.created_at),
    )


def _artifact(row: SearchExecutionArtifactRecord) -> SearchExecutionArtifact:
    return SearchExecutionArtifact(
        row.id,
        row.search_execution_id,
        row.original_filename,
        row.media_type,
        row.byte_size,
        row.sha256,
        row.created_by_user_id,
        _as_utc(row.created_at),
    )


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemySearchExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_source(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        source_key: str,
        display_name: str,
        classification: IdentificationSourceClassification,
        provider_name: str,
        platform_name: str | None,
        created_by_user_id: UUID,
    ) -> IdentificationSource:
        row = IdentificationSourceRecord(
            organization_id=organization_id,
            review_id=review_id,
            source_key=source_key,
            display_name=display_name,
            classification=classification.value,
            provider_name=provider_name,
            platform_name=platform_name,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _source(row)

    async def get_source(
        self, organization_id: UUID, review_id: UUID, source_id: UUID
    ) -> IdentificationSource | None:
        row = (
            await self._session.execute(
                select(IdentificationSourceRecord).where(
                    IdentificationSourceRecord.organization_id == organization_id,
                    IdentificationSourceRecord.review_id == review_id,
                    IdentificationSourceRecord.id == source_id,
                )
            )
        ).scalar_one_or_none()
        return _source(row) if row else None

    async def list_sources(
        self, organization_id: UUID, review_id: UUID
    ) -> list[IdentificationSource]:
        rows = await self._session.scalars(
            select(IdentificationSourceRecord)
            .where(
                IdentificationSourceRecord.organization_id == organization_id,
                IdentificationSourceRecord.review_id == review_id,
            )
            .order_by(IdentificationSourceRecord.source_key, IdentificationSourceRecord.id)
        )
        return [_source(row) for row in rows]

    async def create_execution(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        source_id: UUID,
        strategy_version_id: UUID | None,
        translation_id: UUID | None,
        supersedes_execution_id: UUID | None,
        method: SearchExecutionMethod,
        exact_query: str | None,
        filters: dict[str, str],
        executed_at: datetime,
        software_version: str | None,
        initial_status: SearchExecutionStatus,
        provider_result_count: int | None,
        note: str | None,
        created_by_user_id: UUID,
    ) -> SearchExecution:
        row = SearchExecutionRecord(
            organization_id=organization_id,
            review_id=review_id,
            source_id=source_id,
            search_strategy_version_id=strategy_version_id,
            search_translation_id=translation_id,
            supersedes_execution_id=supersedes_execution_id,
            method=method.value,
            exact_query=exact_query,
            filters=filters,
            executed_at=executed_at,
            software_version=software_version,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        event_row = SearchExecutionEventRecord(
            search_execution_id=row.id,
            organization_id=organization_id,
            review_id=review_id,
            sequence=1,
            status=initial_status.value,
            provider_result_count=provider_result_count,
            note=note,
            recorded_by_user_id=created_by_user_id,
        )
        self._session.add(event_row)
        await self._session.flush()
        result = await self.get_execution(organization_id, review_id, row.id)
        assert result is not None
        return result

    async def _load_executions(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID | None = None
    ) -> list[SearchExecution]:
        query = select(SearchExecutionRecord).where(
            SearchExecutionRecord.organization_id == organization_id,
            SearchExecutionRecord.review_id == review_id,
        )
        if execution_id is not None:
            query = query.where(SearchExecutionRecord.id == execution_id)
        execution_rows = list(
            await self._session.scalars(
                query.order_by(SearchExecutionRecord.executed_at, SearchExecutionRecord.id)
            )
        )
        if not execution_rows:
            return []
        execution_ids = [row.id for row in execution_rows]
        sources = {
            row.id: row
            for row in await self._session.scalars(
                select(IdentificationSourceRecord).where(
                    IdentificationSourceRecord.organization_id == organization_id,
                    IdentificationSourceRecord.review_id == review_id,
                )
            )
        }
        event_rows = list(
            await self._session.scalars(
                select(SearchExecutionEventRecord)
                .where(SearchExecutionEventRecord.search_execution_id.in_(execution_ids))
                .order_by(
                    SearchExecutionEventRecord.search_execution_id,
                    SearchExecutionEventRecord.sequence,
                )
            )
        )
        latest_events: dict[UUID, SearchExecutionEventRecord] = {}
        events_by_execution: dict[UUID, list[SearchExecutionEventRecord]] = {}
        for row in event_rows:
            latest_events[row.search_execution_id] = row
            events_by_execution.setdefault(row.search_execution_id, []).append(row)
        link_counts = Counter(
            await self._session.scalars(
                select(SearchExecutionCitationLinkRecord.search_execution_id).where(
                    SearchExecutionCitationLinkRecord.organization_id == organization_id,
                    SearchExecutionCitationLinkRecord.review_id == review_id,
                    SearchExecutionCitationLinkRecord.search_execution_id.in_(execution_ids),
                )
            )
        )
        return [
            SearchExecution(
                id=row.id,
                organization_id=row.organization_id,
                review_id=row.review_id,
                source=_source(sources[row.source_id]),
                search_strategy_version_id=row.search_strategy_version_id,
                search_translation_id=row.search_translation_id,
                supersedes_execution_id=row.supersedes_execution_id,
                method=SearchExecutionMethod(row.method),
                exact_query=row.exact_query,
                filters=row.filters,
                executed_at=_as_utc(row.executed_at),
                software_version=row.software_version,
                created_by_user_id=row.created_by_user_id,
                created_at=_as_utc(row.created_at),
                events=tuple(_event(item) for item in events_by_execution[row.id]),
                current_event=_event(latest_events[row.id]),
                imported_record_count=link_counts[row.id],
            )
            for row in execution_rows
        ]

    async def get_execution(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID
    ) -> SearchExecution | None:
        rows = await self._load_executions(organization_id, review_id, execution_id)
        return rows[0] if rows else None

    async def list_executions(
        self, organization_id: UUID, review_id: UUID
    ) -> list[SearchExecution]:
        return await self._load_executions(organization_id, review_id)

    async def get_correction_for(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID
    ) -> SearchExecution | None:
        corrected_id = await self._session.scalar(
            select(SearchExecutionRecord.id).where(
                SearchExecutionRecord.organization_id == organization_id,
                SearchExecutionRecord.review_id == review_id,
                SearchExecutionRecord.supersedes_execution_id == execution_id,
            )
        )
        return (
            await self.get_execution(organization_id, review_id, corrected_id)
            if corrected_id
            else None
        )

    async def append_event(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        execution_id: UUID,
        status: SearchExecutionStatus,
        provider_result_count: int | None,
        note: str | None,
        recorded_by_user_id: UUID,
    ) -> SearchExecution:
        async def read_next_sequence() -> int:
            value = await self._session.scalar(
                select(func.coalesce(func.max(SearchExecutionEventRecord.sequence), 0)).where(
                    SearchExecutionEventRecord.search_execution_id == execution_id
                )
            )
            return int(value or 0) + 1

        await insert_next_unique_integer(
            self._session,
            read_next_sequence,
            lambda sequence: SearchExecutionEventRecord(
                search_execution_id=execution_id,
                organization_id=organization_id,
                review_id=review_id,
                sequence=sequence,
                status=status.value,
                provider_result_count=provider_result_count,
                note=note,
                recorded_by_user_id=recorded_by_user_id,
            ),
        )
        result = await self.get_execution(organization_id, review_id, execution_id)
        assert result is not None
        return result

    async def link_import_batch(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        execution_id: UUID,
        import_batch_id: UUID,
        linked_by_user_id: UUID,
    ) -> list[SearchExecutionCitationLink]:
        source_ids = list(
            await self._session.scalars(
                select(CitationSourceRecordRow.id)
                .where(
                    CitationSourceRecordRow.organization_id == organization_id,
                    CitationSourceRecordRow.review_id == review_id,
                    CitationSourceRecordRow.import_batch_id == import_batch_id,
                )
                .order_by(CitationSourceRecordRow.ordinal, CitationSourceRecordRow.id)
            )
        )
        existing = set(
            await self._session.scalars(
                select(SearchExecutionCitationLinkRecord.citation_source_record_id).where(
                    SearchExecutionCitationLinkRecord.search_execution_id == execution_id,
                    SearchExecutionCitationLinkRecord.citation_source_record_id.in_(source_ids),
                )
            )
        )
        rows = [
            SearchExecutionCitationLinkRecord(
                search_execution_id=execution_id,
                citation_source_record_id=source_id,
                organization_id=organization_id,
                review_id=review_id,
                linked_by_user_id=linked_by_user_id,
            )
            for source_id in source_ids
            if source_id not in existing
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return [_link(row) for row in rows]

    async def get_artifact_by_checksum(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID, sha256: str
    ) -> SearchExecutionArtifact | None:
        row = (
            await self._session.execute(
                select(SearchExecutionArtifactRecord).where(
                    SearchExecutionArtifactRecord.organization_id == organization_id,
                    SearchExecutionArtifactRecord.review_id == review_id,
                    SearchExecutionArtifactRecord.search_execution_id == execution_id,
                    SearchExecutionArtifactRecord.sha256 == sha256,
                )
            )
        ).scalar_one_or_none()
        return _artifact(row) if row else None

    async def create_artifact(
        self,
        *,
        artifact_id: UUID,
        organization_id: UUID,
        review_id: UUID,
        execution_id: UUID,
        storage_key: str,
        original_filename: str,
        media_type: str,
        byte_size: int,
        sha256: str,
        created_by_user_id: UUID,
    ) -> SearchExecutionArtifact:
        row = SearchExecutionArtifactRecord(
            id=artifact_id,
            search_execution_id=execution_id,
            organization_id=organization_id,
            review_id=review_id,
            storage_key=storage_key,
            original_filename=original_filename,
            media_type=media_type,
            byte_size=byte_size,
            sha256=sha256,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _artifact(row)

    async def get_artifact(
        self, organization_id: UUID, review_id: UUID, artifact_id: UUID
    ) -> tuple[SearchExecutionArtifact, str] | None:
        row = (
            await self._session.execute(
                select(SearchExecutionArtifactRecord).where(
                    SearchExecutionArtifactRecord.organization_id == organization_id,
                    SearchExecutionArtifactRecord.review_id == review_id,
                    SearchExecutionArtifactRecord.id == artifact_id,
                )
            )
        ).scalar_one_or_none()
        return (_artifact(row), row.storage_key) if row else None

    async def list_artifacts(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID
    ) -> list[SearchExecutionArtifact]:
        rows = await self._session.scalars(
            select(SearchExecutionArtifactRecord)
            .where(
                SearchExecutionArtifactRecord.organization_id == organization_id,
                SearchExecutionArtifactRecord.review_id == review_id,
                SearchExecutionArtifactRecord.search_execution_id == execution_id,
            )
            .order_by(SearchExecutionArtifactRecord.created_at, SearchExecutionArtifactRecord.id)
        )
        return [_artifact(row) for row in rows]
