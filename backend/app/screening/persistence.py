from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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

from backend.app.core.errors import ResourceNotFoundError
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.screening.domain import (
    ScreeningAdjudication,
    ScreeningAssignment,
    ScreeningDecision,
    ScreeningDecisionKind,
    ScreeningOutcome,
    ScreeningOutcomeKind,
    ScreeningProgression,
    ScreeningRound,
    ScreeningRoundState,
    ScreeningStage,
)


class ScreeningRoundRecord(Base):
    __tablename__ = "screening_rounds"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "sequence", name="uq_screening_rounds_sequence"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_screening_rounds_id_tenant"
        ),
        CheckConstraint(
            "stage IN ('TITLE_ABSTRACT', 'FULL_TEXT')", name="ck_screening_rounds_stage"
        ),
        CheckConstraint("state IN ('OPEN', 'CLOSED')", name="ck_screening_rounds_state"),
        CheckConstraint(
            "required_decisions BETWEEN 1 AND 10", name="ck_screening_rounds_required_decisions"
        ),
        CheckConstraint(
            "(state = 'OPEN' AND closed_at IS NULL AND closed_by_user_id IS NULL) OR "
            "(state = 'CLOSED' AND closed_at IS NOT NULL AND closed_by_user_id IS NOT NULL)",
            name="ck_screening_rounds_close_metadata",
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_screening_rounds_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_rounds_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "closed_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_rounds_closer_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String(300))
    stage: Mapped[str] = mapped_column(String(30))
    sequence: Mapped[int] = mapped_column(Integer)
    required_decisions: Mapped[int] = mapped_column(Integer)
    blinded: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    state: Mapped[str] = mapped_column(String(20))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[UUID | None] = mapped_column()


class ScreeningAssignmentRecord(Base):
    __tablename__ = "screening_assignments"
    __table_args__ = (
        UniqueConstraint(
            "round_id", "article_id", "reviewer_user_id", name="uq_screening_assignments_target"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_screening_assignments_id_tenant"
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "review_id",
            "round_id",
            "article_id",
            "reviewer_user_id",
            name="uq_screening_assignments_decision_boundary",
        ),
        ForeignKeyConstraint(
            ["round_id", "organization_id", "review_id"],
            [
                "screening_rounds.id",
                "screening_rounds.organization_id",
                "screening_rounds.review_id",
            ],
            name="fk_screening_assignments_round_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_screening_assignments_article_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_assignments_reviewer_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_assignments_assigner_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    round_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    reviewer_user_id: Mapped[UUID] = mapped_column()
    assigned_by_user_id: Mapped[UUID] = mapped_column()
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScreeningDecisionRecord(Base):
    __tablename__ = "screening_decisions"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_screening_decisions_assignment"),
        CheckConstraint(
            "decision IN ('INCLUDE', 'EXCLUDE')", name="ck_screening_decisions_decision"
        ),
        CheckConstraint(
            "(decision = 'INCLUDE' AND exclusion_reason IS NULL) OR "
            "(decision = 'EXCLUDE' AND exclusion_reason IS NOT NULL)",
            name="ck_screening_decisions_exclusion_reason",
        ),
        ForeignKeyConstraint(
            [
                "assignment_id",
                "organization_id",
                "review_id",
                "round_id",
                "article_id",
                "reviewer_user_id",
            ],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
                "screening_assignments.round_id",
                "screening_assignments.article_id",
                "screening_assignments.reviewer_user_id",
            ],
            name="fk_screening_decisions_assignment_tenant_review",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    round_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    reviewer_user_id: Mapped[UUID] = mapped_column()
    decision: Mapped[str] = mapped_column(String(20))
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScreeningOutcomeRecord(Base):
    __tablename__ = "screening_outcomes"
    __table_args__ = (
        UniqueConstraint("round_id", "article_id", name="uq_screening_outcomes_round_article"),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_screening_outcomes_id_tenant"
        ),
        CheckConstraint(
            "outcome IN ('INCLUDE', 'EXCLUDE', 'CONFLICT')", name="ck_screening_outcomes_outcome"
        ),
        ForeignKeyConstraint(
            ["round_id", "organization_id", "review_id"],
            [
                "screening_rounds.id",
                "screening_rounds.organization_id",
                "screening_rounds.review_id",
            ],
            name="fk_screening_outcomes_round_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_screening_outcomes_article_tenant_review",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    round_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    outcome: Mapped[str] = mapped_column(String(20))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScreeningAdjudicationRecord(Base):
    __tablename__ = "screening_adjudications"
    __table_args__ = (
        UniqueConstraint("outcome_id", name="uq_screening_adjudications_outcome"),
        CheckConstraint(
            "decision IN ('INCLUDE', 'EXCLUDE')", name="ck_screening_adjudications_decision"
        ),
        ForeignKeyConstraint(
            ["outcome_id", "organization_id", "review_id"],
            [
                "screening_outcomes.id",
                "screening_outcomes.organization_id",
                "screening_outcomes.review_id",
            ],
            name="fk_screening_adjudications_outcome_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_adjudications_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    outcome_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    decision: Mapped[str] = mapped_column(String(20))
    decided_by_user_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScreeningProgressionRecord(Base):
    __tablename__ = "screening_progressions"
    __table_args__ = (
        UniqueConstraint(
            "source_round_id",
            "target_round_id",
            "article_id",
            name="uq_screening_progressions_path",
        ),
        ForeignKeyConstraint(
            ["source_round_id", "organization_id", "review_id"],
            [
                "screening_rounds.id",
                "screening_rounds.organization_id",
                "screening_rounds.review_id",
            ],
            name="fk_screening_progressions_source_round",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_round_id", "organization_id", "review_id"],
            [
                "screening_rounds.id",
                "screening_rounds.organization_id",
                "screening_rounds.review_id",
            ],
            name="fk_screening_progressions_target_round",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_screening_progressions_article",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_progressions_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    source_round_id: Mapped[UUID] = mapped_column()
    target_round_id: Mapped[UUID] = mapped_column()
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("screening scientific history is append-only")


for _record_type in (
    ScreeningAssignmentRecord,
    ScreeningDecisionRecord,
    ScreeningOutcomeRecord,
    ScreeningAdjudicationRecord,
    ScreeningProgressionRecord,
):
    event.listen(_record_type, "before_update", _reject_mutation)
    event.listen(_record_type, "before_delete", _reject_mutation)


def _round(row: ScreeningRoundRecord) -> ScreeningRound:
    return ScreeningRound(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        name=row.name,
        stage=ScreeningStage(row.stage),
        sequence=row.sequence,
        required_decisions=row.required_decisions,
        blinded=row.blinded,
        state=ScreeningRoundState(row.state),
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
        closed_at=row.closed_at,
        closed_by_user_id=row.closed_by_user_id,
    )


def _assignment(row: ScreeningAssignmentRecord) -> ScreeningAssignment:
    return ScreeningAssignment(
        id=row.id,
        round_id=row.round_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        article_id=row.article_id,
        reviewer_user_id=row.reviewer_user_id,
        assigned_by_user_id=row.assigned_by_user_id,
        assigned_at=row.assigned_at or datetime.now(UTC),
    )


def _decision(row: ScreeningDecisionRecord) -> ScreeningDecision:
    return ScreeningDecision(
        id=row.id,
        assignment_id=row.assignment_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        round_id=row.round_id,
        article_id=row.article_id,
        reviewer_user_id=row.reviewer_user_id,
        decision=ScreeningDecisionKind(row.decision),
        exclusion_reason=row.exclusion_reason,
        decided_at=row.decided_at or datetime.now(UTC),
    )


def _outcome(row: ScreeningOutcomeRecord) -> ScreeningOutcome:
    return ScreeningOutcome(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        round_id=row.round_id,
        article_id=row.article_id,
        outcome=ScreeningOutcomeKind(row.outcome),
        computed_at=row.computed_at or datetime.now(UTC),
    )


def _adjudication(row: ScreeningAdjudicationRecord) -> ScreeningAdjudication:
    return ScreeningAdjudication(
        id=row.id,
        outcome_id=row.outcome_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        decision=ScreeningDecisionKind(row.decision),
        decided_by_user_id=row.decided_by_user_id,
        reason=row.reason,
        decided_at=row.decided_at or datetime.now(UTC),
    )


def _progression(row: ScreeningProgressionRecord) -> ScreeningProgression:
    return ScreeningProgression(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        article_id=row.article_id,
        source_round_id=row.source_round_id,
        target_round_id=row.target_round_id,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


class SqlAlchemyScreeningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_round(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        name: str,
        stage: ScreeningStage,
        required_decisions: int,
        blinded: bool,
        created_by_user_id: UUID,
    ) -> ScreeningRound:
        async def read_next_sequence() -> int:
            query = select(func.coalesce(func.max(ScreeningRoundRecord.sequence), 0)).where(
                ScreeningRoundRecord.organization_id == organization_id,
                ScreeningRoundRecord.review_id == review_id,
            )
            return int((await self._session.execute(query)).scalar_one()) + 1

        row = await insert_next_unique_integer(
            self._session,
            read_next_sequence,
            lambda sequence: ScreeningRoundRecord(
                organization_id=organization_id,
                review_id=review_id,
                name=name,
                stage=stage.value,
                sequence=sequence,
                required_decisions=required_decisions,
                blinded=blinded,
                state=ScreeningRoundState.OPEN.value,
                created_by_user_id=created_by_user_id,
            ),
        )
        await self._session.refresh(row)
        return _round(row)

    async def get_round(self, organization_id: UUID, round_id: UUID) -> ScreeningRound | None:
        row = (
            await self._session.execute(
                select(ScreeningRoundRecord).where(
                    ScreeningRoundRecord.organization_id == organization_id,
                    ScreeningRoundRecord.id == round_id,
                )
            )
        ).scalar_one_or_none()
        return _round(row) if row is not None else None

    async def close_round(
        self, organization_id: UUID, round_id: UUID, closed_by_user_id: UUID
    ) -> ScreeningRound:
        row = (
            await self._session.execute(
                select(ScreeningRoundRecord)
                .where(
                    ScreeningRoundRecord.organization_id == organization_id,
                    ScreeningRoundRecord.id == round_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise ResourceNotFoundError("screening round was not found")
        row.state = ScreeningRoundState.CLOSED.value
        row.closed_at = datetime.now(UTC)
        row.closed_by_user_id = closed_by_user_id
        await self._session.flush()
        await self._session.refresh(row)
        return _round(row)

    async def get_assignment_for(
        self, organization_id: UUID, round_id: UUID, article_id: UUID, reviewer_id: UUID
    ) -> ScreeningAssignment | None:
        row = (
            await self._session.execute(
                select(ScreeningAssignmentRecord).where(
                    ScreeningAssignmentRecord.organization_id == organization_id,
                    ScreeningAssignmentRecord.round_id == round_id,
                    ScreeningAssignmentRecord.article_id == article_id,
                    ScreeningAssignmentRecord.reviewer_user_id == reviewer_id,
                )
            )
        ).scalar_one_or_none()
        return _assignment(row) if row is not None else None

    async def create_assignment(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        round_id: UUID,
        article_id: UUID,
        reviewer_user_id: UUID,
        assigned_by_user_id: UUID,
    ) -> ScreeningAssignment:
        row = ScreeningAssignmentRecord(
            organization_id=organization_id,
            review_id=review_id,
            round_id=round_id,
            article_id=article_id,
            reviewer_user_id=reviewer_user_id,
            assigned_by_user_id=assigned_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _assignment(row)

    async def count_article_assignments(
        self, organization_id: UUID, round_id: UUID, article_id: UUID
    ) -> int:
        query = (
            select(func.count())
            .select_from(ScreeningAssignmentRecord)
            .where(
                ScreeningAssignmentRecord.organization_id == organization_id,
                ScreeningAssignmentRecord.round_id == round_id,
                ScreeningAssignmentRecord.article_id == article_id,
            )
        )
        return int((await self._session.execute(query)).scalar_one())

    async def list_reviewer_assignments(
        self, organization_id: UUID, round_id: UUID, reviewer_user_id: UUID
    ) -> list[ScreeningAssignment]:
        query = (
            select(ScreeningAssignmentRecord)
            .where(
                ScreeningAssignmentRecord.organization_id == organization_id,
                ScreeningAssignmentRecord.round_id == round_id,
                ScreeningAssignmentRecord.reviewer_user_id == reviewer_user_id,
            )
            .order_by(ScreeningAssignmentRecord.assigned_at, ScreeningAssignmentRecord.id)
        )
        return [_assignment(row) for row in await self._session.scalars(query)]

    async def get_assignment(
        self, organization_id: UUID, assignment_id: UUID
    ) -> ScreeningAssignment | None:
        row = (
            await self._session.execute(
                select(ScreeningAssignmentRecord).where(
                    ScreeningAssignmentRecord.organization_id == organization_id,
                    ScreeningAssignmentRecord.id == assignment_id,
                )
            )
        ).scalar_one_or_none()
        return _assignment(row) if row is not None else None

    async def get_decision_for_assignment(
        self, organization_id: UUID, assignment_id: UUID
    ) -> ScreeningDecision | None:
        row = (
            await self._session.execute(
                select(ScreeningDecisionRecord).where(
                    ScreeningDecisionRecord.organization_id == organization_id,
                    ScreeningDecisionRecord.assignment_id == assignment_id,
                )
            )
        ).scalar_one_or_none()
        return _decision(row) if row is not None else None

    async def append_decision(
        self,
        *,
        assignment: ScreeningAssignment,
        decision: ScreeningDecisionKind,
        exclusion_reason: str | None,
    ) -> ScreeningDecision:
        row = ScreeningDecisionRecord(
            assignment_id=assignment.id,
            organization_id=assignment.organization_id,
            review_id=assignment.review_id,
            round_id=assignment.round_id,
            article_id=assignment.article_id,
            reviewer_user_id=assignment.reviewer_user_id,
            decision=decision.value,
            exclusion_reason=exclusion_reason,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _decision(row)

    async def list_article_decisions(
        self, organization_id: UUID, round_id: UUID, article_id: UUID
    ) -> list[ScreeningDecision]:
        query = (
            select(ScreeningDecisionRecord)
            .where(
                ScreeningDecisionRecord.organization_id == organization_id,
                ScreeningDecisionRecord.round_id == round_id,
                ScreeningDecisionRecord.article_id == article_id,
            )
            .order_by(ScreeningDecisionRecord.decided_at, ScreeningDecisionRecord.id)
        )
        return [_decision(row) for row in await self._session.scalars(query)]

    async def get_outcome(
        self, organization_id: UUID, round_id: UUID, article_id: UUID
    ) -> ScreeningOutcome | None:
        row = (
            await self._session.execute(
                select(ScreeningOutcomeRecord).where(
                    ScreeningOutcomeRecord.organization_id == organization_id,
                    ScreeningOutcomeRecord.round_id == round_id,
                    ScreeningOutcomeRecord.article_id == article_id,
                )
            )
        ).scalar_one_or_none()
        return _outcome(row) if row is not None else None

    async def get_outcome_by_id(
        self, organization_id: UUID, outcome_id: UUID
    ) -> ScreeningOutcome | None:
        row = (
            await self._session.execute(
                select(ScreeningOutcomeRecord).where(
                    ScreeningOutcomeRecord.organization_id == organization_id,
                    ScreeningOutcomeRecord.id == outcome_id,
                )
            )
        ).scalar_one_or_none()
        return _outcome(row) if row is not None else None

    async def append_outcome(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        round_id: UUID,
        article_id: UUID,
        outcome: ScreeningOutcomeKind,
    ) -> ScreeningOutcome:
        row = ScreeningOutcomeRecord(
            organization_id=organization_id,
            review_id=review_id,
            round_id=round_id,
            article_id=article_id,
            outcome=outcome.value,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _outcome(row)

    async def list_outcomes(self, organization_id: UUID, round_id: UUID) -> list[ScreeningOutcome]:
        query = (
            select(ScreeningOutcomeRecord)
            .where(
                ScreeningOutcomeRecord.organization_id == organization_id,
                ScreeningOutcomeRecord.round_id == round_id,
            )
            .order_by(ScreeningOutcomeRecord.computed_at, ScreeningOutcomeRecord.id)
        )
        return [_outcome(row) for row in await self._session.scalars(query)]

    async def get_adjudication(
        self, organization_id: UUID, outcome_id: UUID
    ) -> ScreeningAdjudication | None:
        row = (
            await self._session.execute(
                select(ScreeningAdjudicationRecord).where(
                    ScreeningAdjudicationRecord.organization_id == organization_id,
                    ScreeningAdjudicationRecord.outcome_id == outcome_id,
                )
            )
        ).scalar_one_or_none()
        return _adjudication(row) if row is not None else None

    async def append_adjudication(
        self,
        *,
        outcome: ScreeningOutcome,
        decision: ScreeningDecisionKind,
        decided_by_user_id: UUID,
        reason: str | None,
    ) -> ScreeningAdjudication:
        row = ScreeningAdjudicationRecord(
            outcome_id=outcome.id,
            organization_id=outcome.organization_id,
            review_id=outcome.review_id,
            decision=decision.value,
            decided_by_user_id=decided_by_user_id,
            reason=reason,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _adjudication(row)

    async def round_is_complete(self, organization_id: UUID, round_id: UUID) -> bool:
        assignment_count = int(
            (
                await self._session.execute(
                    select(func.count(func.distinct(ScreeningAssignmentRecord.article_id))).where(
                        ScreeningAssignmentRecord.organization_id == organization_id,
                        ScreeningAssignmentRecord.round_id == round_id,
                    )
                )
            ).scalar_one()
        )
        outcome_count = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ScreeningOutcomeRecord)
                    .where(
                        ScreeningOutcomeRecord.organization_id == organization_id,
                        ScreeningOutcomeRecord.round_id == round_id,
                    )
                )
            ).scalar_one()
        )
        unresolved = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ScreeningOutcomeRecord)
                    .outerjoin(
                        ScreeningAdjudicationRecord,
                        ScreeningAdjudicationRecord.outcome_id == ScreeningOutcomeRecord.id,
                    )
                    .where(
                        ScreeningOutcomeRecord.organization_id == organization_id,
                        ScreeningOutcomeRecord.round_id == round_id,
                        ScreeningOutcomeRecord.outcome == ScreeningOutcomeKind.CONFLICT.value,
                        ScreeningAdjudicationRecord.id.is_(None),
                    )
                )
            ).scalar_one()
        )
        return assignment_count > 0 and outcome_count == assignment_count and unresolved == 0

    async def create_progression(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        article_id: UUID,
        source_round_id: UUID,
        target_round_id: UUID,
        created_by_user_id: UUID,
    ) -> ScreeningProgression:
        row = ScreeningProgressionRecord(
            organization_id=organization_id,
            review_id=review_id,
            article_id=article_id,
            source_round_id=source_round_id,
            target_round_id=target_round_id,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _progression(row)

    async def get_progression(
        self,
        organization_id: UUID,
        source_round_id: UUID,
        target_round_id: UUID,
        article_id: UUID,
    ) -> ScreeningProgression | None:
        row = (
            await self._session.execute(
                select(ScreeningProgressionRecord).where(
                    ScreeningProgressionRecord.organization_id == organization_id,
                    ScreeningProgressionRecord.source_round_id == source_round_id,
                    ScreeningProgressionRecord.target_round_id == target_round_id,
                    ScreeningProgressionRecord.article_id == article_id,
                )
            )
        ).scalar_one_or_none()
        return _progression(row) if row is not None else None
