from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.extraction.domain import (
    ExtractionSchema,
    ExtractionSchemaVersion,
)


class ExtractionSchemaRecord(Base):
    __tablename__ = "extraction_schemas"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_extraction_schemas_id_tenant"
        ),
        UniqueConstraint(
            "organization_id", "review_id", "name", name="uq_extraction_schemas_review_name"
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_extraction_schemas_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_extraction_schemas_creator_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtractionSchemaVersionRecord(Base):
    __tablename__ = "extraction_schema_versions"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_extraction_schema_versions_id_tenant"
        ),
        UniqueConstraint("schema_id", "version", name="uq_extraction_schema_versions_number"),
        ForeignKeyConstraint(
            ["schema_id", "organization_id", "review_id"],
            [
                "extraction_schemas.id",
                "extraction_schemas.organization_id",
                "extraction_schemas.review_id",
            ],
            name="fk_extraction_schema_versions_schema_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_extraction_schema_versions_creator_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    schema_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _schema(record: ExtractionSchemaRecord) -> ExtractionSchema:
    return ExtractionSchema(
        record.id,
        record.organization_id,
        record.review_id,
        record.name,
        record.description,
        record.created_by_user_id,
        record.created_at or datetime.now(UTC),
    )


def _version(record: ExtractionSchemaVersionRecord) -> ExtractionSchemaVersion:
    return ExtractionSchemaVersion(
        record.id,
        record.schema_id,
        record.organization_id,
        record.review_id,
        record.version,
        record.content_hash,
        record.fields,
        record.created_by_user_id,
        record.created_at or datetime.now(UTC),
    )


class SqlAlchemyExtractionSchemaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_schema(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        name: str,
        description: str | None,
        created_by_user_id: UUID,
    ) -> ExtractionSchema:
        record = ExtractionSchemaRecord(
            organization_id=organization_id,
            review_id=review_id,
            name=name,
            description=description,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _schema(record)

    async def get_schema(
        self, organization_id: UUID, review_id: UUID, schema_id: UUID
    ) -> ExtractionSchema | None:
        record = (
            await self._session.execute(
                select(ExtractionSchemaRecord).where(
                    ExtractionSchemaRecord.organization_id == organization_id,
                    ExtractionSchemaRecord.review_id == review_id,
                    ExtractionSchemaRecord.id == schema_id,
                )
            )
        ).scalar_one_or_none()
        return _schema(record) if record else None

    async def create_version(
        self,
        *,
        schema: ExtractionSchema,
        fields: list[dict[str, Any]],
        content_hash: str,
        created_by_user_id: UUID,
    ) -> ExtractionSchemaVersion:
        latest = (
            await self._session.execute(
                select(ExtractionSchemaVersionRecord.version)
                .where(ExtractionSchemaVersionRecord.schema_id == schema.id)
                .order_by(ExtractionSchemaVersionRecord.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        record = ExtractionSchemaVersionRecord(
            schema_id=schema.id,
            organization_id=schema.organization_id,
            review_id=schema.review_id,
            version=(latest or 0) + 1,
            content_hash=content_hash,
            fields=fields,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _version(record)

    async def list_versions(
        self, organization_id: UUID, review_id: UUID, schema_id: UUID
    ) -> list[ExtractionSchemaVersion]:
        records = (
            await self._session.execute(
                select(ExtractionSchemaVersionRecord)
                .where(
                    ExtractionSchemaVersionRecord.organization_id == organization_id,
                    ExtractionSchemaVersionRecord.review_id == review_id,
                    ExtractionSchemaVersionRecord.schema_id == schema_id,
                )
                .order_by(ExtractionSchemaVersionRecord.version)
            )
        ).scalars()
        return [_version(record) for record in records]

    async def get_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> ExtractionSchemaVersion | None:
        record = (
            await self._session.execute(
                select(ExtractionSchemaVersionRecord).where(
                    ExtractionSchemaVersionRecord.organization_id == organization_id,
                    ExtractionSchemaVersionRecord.review_id == review_id,
                    ExtractionSchemaVersionRecord.id == version_id,
                )
            )
        ).scalar_one_or_none()
        return _version(record) if record else None
