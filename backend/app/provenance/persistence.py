from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
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

from backend.app.db.base import Base
from backend.app.provenance.domain import (
    AIRun,
    AIRunStatus,
    AuditEvent,
    PromptVersion,
    ProvenanceActorKind,
    ScientificProvenance,
    VerificationState,
)


class PromptVersionRecord(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "prompt_key", "version", name="uq_prompt_versions_key_version"
        ),
        UniqueConstraint("id", "organization_id", name="uq_prompt_versions_id_org"),
        CheckConstraint("version > 0", name="ck_prompt_versions_positive_version"),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_prompt_versions_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    prompt_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    template: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIRunRecord(Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_runs_id_tenant"),
        CheckConstraint("status IN ('SUCCEEDED', 'FAILED')", name="ck_ai_runs_status"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_runs_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["prompt_versions.id", "prompt_versions.organization_id"],
            name="fk_ai_runs_prompt_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_runs_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    prompt_version_id: Mapped[UUID] = mapped_column()
    provider: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(160))
    model_version: Mapped[str] = mapped_column(String(100))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    output_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))
    usage: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScientificProvenanceRecord(Base):
    __tablename__ = "scientific_provenance"
    __table_args__ = (
        CheckConstraint("actor_kind IN ('HUMAN', 'AI', 'SYSTEM')", name="ck_provenance_actor_kind"),
        CheckConstraint(
            "verification_state IN ('UNVERIFIED', 'HUMAN_VERIFIED', 'REJECTED')",
            name="ck_provenance_verification_state",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_provenance_confidence",
        ),
        CheckConstraint(
            "(actor_kind = 'HUMAN' AND actor_user_id IS NOT NULL AND ai_run_id IS NULL) "
            "OR (actor_kind = 'AI' AND actor_user_id IS NULL AND ai_run_id IS NOT NULL) "
            "OR (actor_kind = 'SYSTEM' AND actor_user_id IS NULL AND ai_run_id IS NULL)",
            name="ck_provenance_actor_reference",
        ),
        CheckConstraint(
            "(source_type IS NULL AND source_id IS NULL) OR "
            "(source_type IS NOT NULL AND source_id IS NOT NULL)",
            name="ck_provenance_source_pair",
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_provenance_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_provenance_actor_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            ["ai_runs.id", "ai_runs.organization_id", "ai_runs.review_id"],
            name="fk_provenance_ai_run_tenant_review",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    subject_type: Mapped[str] = mapped_column(String(120))
    subject_id: Mapped[UUID] = mapped_column()
    source_type: Mapped[str | None] = mapped_column(String(120))
    source_id: Mapped[UUID | None] = mapped_column()
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSON)
    method_name: Mapped[str] = mapped_column(String(160))
    method_version: Mapped[str] = mapped_column(String(100))
    actor_kind: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[UUID | None] = mapped_column()
    ai_run_id: Mapped[UUID | None] = mapped_column()
    confidence: Mapped[float | None] = mapped_column(Float)
    verification_state: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEventRecord(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_audit_events_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID | None] = mapped_column()
    entity_type: Mapped[str] = mapped_column(String(120))
    entity_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(120))
    actor_user_id: Mapped[UUID] = mapped_column()
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("provenance ledger records are append-only")


for _record_type in (
    PromptVersionRecord,
    AIRunRecord,
    ScientificProvenanceRecord,
    AuditEventRecord,
):
    event.listen(_record_type, "before_update", _reject_mutation)
    event.listen(_record_type, "before_delete", _reject_mutation)


def _prompt_to_domain(record: PromptVersionRecord) -> PromptVersion:
    return PromptVersion(
        id=record.id,
        organization_id=record.organization_id,
        prompt_key=record.prompt_key,
        version=record.version,
        template=record.template,
        output_schema=record.output_schema,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or datetime.now(UTC),
    )


def _ai_run_to_domain(record: AIRunRecord) -> AIRun:
    return AIRun(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        prompt_version_id=record.prompt_version_id,
        provider=record.provider,
        model_name=record.model_name,
        model_version=record.model_version,
        parameters=record.parameters,
        input_snapshot=record.input_snapshot,
        output_snapshot=record.output_snapshot,
        status=AIRunStatus(record.status),
        usage=record.usage,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or datetime.now(UTC),
    )


def _provenance_to_domain(record: ScientificProvenanceRecord) -> ScientificProvenance:
    return ScientificProvenance(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        subject_type=record.subject_type,
        subject_id=record.subject_id,
        source_type=record.source_type,
        source_id=record.source_id,
        source_locator=record.source_locator,
        method_name=record.method_name,
        method_version=record.method_version,
        actor_kind=ProvenanceActorKind(record.actor_kind),
        actor_user_id=record.actor_user_id,
        ai_run_id=record.ai_run_id,
        confidence=record.confidence,
        verification_state=VerificationState(record.verification_state),
        created_at=record.created_at or datetime.now(UTC),
    )


def _audit_to_domain(record: AuditEventRecord) -> AuditEvent:
    return AuditEvent(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        action=record.action,
        actor_user_id=record.actor_user_id,
        before_snapshot=record.before_snapshot,
        after_snapshot=record.after_snapshot,
        reason=record.reason,
        occurred_at=record.occurred_at or datetime.now(UTC),
    )


class SqlAlchemyProvenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_prompt_version(
        self,
        *,
        organization_id: UUID,
        prompt_key: str,
        template: str,
        output_schema: dict[str, Any],
        created_by_user_id: UUID,
    ) -> PromptVersion:
        version_query = select(func.coalesce(func.max(PromptVersionRecord.version), 0)).where(
            PromptVersionRecord.organization_id == organization_id,
            PromptVersionRecord.prompt_key == prompt_key,
        )
        version = int((await self._session.execute(version_query)).scalar_one()) + 1
        record = PromptVersionRecord(
            organization_id=organization_id,
            prompt_key=prompt_key.strip(),
            version=version,
            template=template,
            output_schema=output_schema,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _prompt_to_domain(record)

    async def get_prompt_version(
        self, organization_id: UUID, prompt_version_id: UUID
    ) -> PromptVersion | None:
        statement = select(PromptVersionRecord).where(
            PromptVersionRecord.organization_id == organization_id,
            PromptVersionRecord.id == prompt_version_id,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _prompt_to_domain(record) if record is not None else None

    async def append_ai_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        prompt_version_id: UUID,
        provider: str,
        model_name: str,
        model_version: str,
        parameters: dict[str, Any],
        input_snapshot: dict[str, Any],
        output_snapshot: dict[str, Any] | None,
        status: AIRunStatus,
        usage: dict[str, Any],
        created_by_user_id: UUID,
    ) -> AIRun:
        record = AIRunRecord(
            organization_id=organization_id,
            review_id=review_id,
            prompt_version_id=prompt_version_id,
            provider=provider,
            model_name=model_name,
            model_version=model_version,
            parameters=parameters,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            status=status.value,
            usage=usage,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _ai_run_to_domain(record)

    async def get_ai_run(
        self, organization_id: UUID, review_id: UUID, ai_run_id: UUID
    ) -> AIRun | None:
        statement = select(AIRunRecord).where(
            AIRunRecord.organization_id == organization_id,
            AIRunRecord.review_id == review_id,
            AIRunRecord.id == ai_run_id,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _ai_run_to_domain(record) if record is not None else None

    async def append_provenance(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        subject_type: str,
        subject_id: UUID,
        source_type: str | None,
        source_id: UUID | None,
        source_locator: dict[str, Any],
        method_name: str,
        method_version: str,
        actor_kind: ProvenanceActorKind,
        actor_user_id: UUID | None,
        ai_run_id: UUID | None,
        confidence: float | None,
        verification_state: VerificationState,
    ) -> ScientificProvenance:
        record = ScientificProvenanceRecord(
            organization_id=organization_id,
            review_id=review_id,
            subject_type=subject_type,
            subject_id=subject_id,
            source_type=source_type,
            source_id=source_id,
            source_locator=source_locator,
            method_name=method_name,
            method_version=method_version,
            actor_kind=actor_kind.value,
            actor_user_id=actor_user_id,
            ai_run_id=ai_run_id,
            confidence=confidence,
            verification_state=verification_state.value,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _provenance_to_domain(record)

    async def list_provenance(
        self, organization_id: UUID, review_id: UUID
    ) -> list[ScientificProvenance]:
        statement = (
            select(ScientificProvenanceRecord)
            .where(
                ScientificProvenanceRecord.organization_id == organization_id,
                ScientificProvenanceRecord.review_id == review_id,
            )
            .order_by(ScientificProvenanceRecord.created_at, ScientificProvenanceRecord.id)
        )
        return [_provenance_to_domain(row) for row in await self._session.scalars(statement)]

    async def append_audit_event(
        self,
        *,
        organization_id: UUID,
        review_id: UUID | None,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor_user_id: UUID,
        before_snapshot: dict[str, Any] | None,
        after_snapshot: dict[str, Any] | None,
        reason: str | None,
    ) -> AuditEvent:
        record = AuditEventRecord(
            organization_id=organization_id,
            review_id=review_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=actor_user_id,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            reason=reason,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _audit_to_domain(record)

    async def list_audit_events(
        self, organization_id: UUID, review_id: UUID | None
    ) -> list[AuditEvent]:
        statement = select(AuditEventRecord).where(
            AuditEventRecord.organization_id == organization_id,
            AuditEventRecord.review_id == review_id,
        )
        statement = statement.order_by(AuditEventRecord.occurred_at, AuditEventRecord.id)
        return [_audit_to_domain(row) for row in await self._session.scalars(statement)]
