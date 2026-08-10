from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
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
from backend.app.deduplication.domain import (
    CandidateMatch,
    DedupDecisionKind,
    DeduplicationDecision,
    DeduplicationRun,
    DuplicateCandidate,
    MatchReason,
)


class DeduplicationRunRecord(Base):
    __tablename__ = "deduplication_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "algorithm_version",
            "input_hash",
            name="uq_deduplication_runs_input",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_deduplication_runs_id_tenant"
        ),
        CheckConstraint("article_count >= 0", name="ck_deduplication_runs_article_count"),
        CheckConstraint("candidate_count >= 0", name="ck_deduplication_runs_candidate_count"),
        CheckConstraint("length(input_hash) = 64", name="ck_deduplication_runs_hash_length"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_deduplication_runs_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_deduplication_runs_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    algorithm_version: Mapped[str] = mapped_column(String(50))
    input_hash: Mapped[str] = mapped_column(String(64))
    article_count: Mapped[int] = mapped_column(Integer)
    candidate_count: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DuplicateCandidateRecord(Base):
    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        UniqueConstraint(
            "deduplication_run_id",
            "left_article_id",
            "right_article_id",
            name="uq_duplicate_candidates_run_pair",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_duplicate_candidates_id_tenant"
        ),
        CheckConstraint(
            "left_article_id <> right_article_id", name="ck_duplicate_candidates_distinct"
        ),
        CheckConstraint("score >= 0 AND score <= 1", name="ck_duplicate_candidates_score"),
        CheckConstraint(
            "reason IN ('DOI_EXACT', 'PMID_EXACT', 'TITLE_YEAR_EXACT', 'TITLE_FUZZY')",
            name="ck_duplicate_candidates_reason",
        ),
        ForeignKeyConstraint(
            ["deduplication_run_id", "organization_id", "review_id"],
            [
                "deduplication_runs.id",
                "deduplication_runs.organization_id",
                "deduplication_runs.review_id",
            ],
            name="fk_duplicate_candidates_run_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["left_article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_duplicate_candidates_left_article_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["right_article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_duplicate_candidates_right_article_tenant_review",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    deduplication_run_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    left_article_id: Mapped[UUID] = mapped_column()
    right_article_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str] = mapped_column(String(30))
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeduplicationDecisionRecord(Base):
    __tablename__ = "deduplication_decisions"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_deduplication_decisions_candidate"),
        CheckConstraint(
            "decision IN ('CONFIRMED_DUPLICATE', 'REJECTED')",
            name="ck_deduplication_decisions_decision",
        ),
        CheckConstraint(
            "(decision = 'CONFIRMED_DUPLICATE' AND retained_article_id IS NOT NULL) OR "
            "(decision = 'REJECTED' AND retained_article_id IS NULL)",
            name="ck_deduplication_decisions_retained_article",
        ),
        ForeignKeyConstraint(
            ["candidate_id", "organization_id", "review_id"],
            [
                "duplicate_candidates.id",
                "duplicate_candidates.organization_id",
                "duplicate_candidates.review_id",
            ],
            name="fk_deduplication_decisions_candidate_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_deduplication_decisions_actor_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["retained_article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_deduplication_decisions_retained_article",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    decision: Mapped[str] = mapped_column(String(30))
    retained_article_id: Mapped[UUID | None] = mapped_column()
    decided_by_user_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("deduplication history is append-only")


for _record_type in (
    DeduplicationRunRecord,
    DuplicateCandidateRecord,
    DeduplicationDecisionRecord,
):
    event.listen(_record_type, "before_update", _reject_mutation)
    event.listen(_record_type, "before_delete", _reject_mutation)


def _run_to_domain(row: DeduplicationRunRecord) -> DeduplicationRun:
    return DeduplicationRun(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        algorithm_version=row.algorithm_version,
        input_hash=row.input_hash,
        article_count=row.article_count,
        candidate_count=row.candidate_count,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _candidate_to_domain(row: DuplicateCandidateRecord) -> DuplicateCandidate:
    return DuplicateCandidate(
        id=row.id,
        deduplication_run_id=row.deduplication_run_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        left_article_id=row.left_article_id,
        right_article_id=row.right_article_id,
        reason=MatchReason(row.reason),
        score=row.score,
        created_at=row.created_at or datetime.now(UTC),
    )


def _decision_to_domain(row: DeduplicationDecisionRecord) -> DeduplicationDecision:
    return DeduplicationDecision(
        id=row.id,
        candidate_id=row.candidate_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        decision=DedupDecisionKind(row.decision),
        retained_article_id=row.retained_article_id,
        decided_by_user_id=row.decided_by_user_id,
        reason=row.reason,
        decided_at=row.decided_at or datetime.now(UTC),
    )


class SqlAlchemyDeduplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_run_by_input(
        self,
        organization_id: UUID,
        review_id: UUID,
        algorithm_version: str,
        input_hash: str,
    ) -> DeduplicationRun | None:
        query = select(DeduplicationRunRecord).where(
            DeduplicationRunRecord.organization_id == organization_id,
            DeduplicationRunRecord.review_id == review_id,
            DeduplicationRunRecord.algorithm_version == algorithm_version,
            DeduplicationRunRecord.input_hash == input_hash,
        )
        row = (await self._session.execute(query)).scalar_one_or_none()
        return _run_to_domain(row) if row is not None else None

    async def create_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        algorithm_version: str,
        input_hash: str,
        article_count: int,
        matches: list[CandidateMatch],
        created_by_user_id: UUID,
    ) -> tuple[DeduplicationRun, list[DuplicateCandidate]]:
        run = DeduplicationRunRecord(
            organization_id=organization_id,
            review_id=review_id,
            algorithm_version=algorithm_version,
            input_hash=input_hash,
            article_count=article_count,
            candidate_count=len(matches),
            created_by_user_id=created_by_user_id,
        )
        self._session.add(run)
        await self._session.flush()
        candidates = []
        for match in matches:
            row = DuplicateCandidateRecord(
                deduplication_run_id=run.id,
                organization_id=organization_id,
                review_id=review_id,
                left_article_id=match.left_article_id,
                right_article_id=match.right_article_id,
                reason=match.reason.value,
                score=match.score,
            )
            self._session.add(row)
            await self._session.flush()
            candidates.append(_candidate_to_domain(row))
        await self._session.refresh(run)
        return _run_to_domain(run), candidates

    async def list_candidates(
        self, organization_id: UUID, review_id: UUID
    ) -> list[tuple[DuplicateCandidate, DeduplicationDecision | None]]:
        query = (
            select(DuplicateCandidateRecord, DeduplicationDecisionRecord)
            .outerjoin(
                DeduplicationDecisionRecord,
                DeduplicationDecisionRecord.candidate_id == DuplicateCandidateRecord.id,
            )
            .where(
                DuplicateCandidateRecord.organization_id == organization_id,
                DuplicateCandidateRecord.review_id == review_id,
            )
            .order_by(DuplicateCandidateRecord.created_at, DuplicateCandidateRecord.id)
        )
        return [
            (
                _candidate_to_domain(candidate),
                _decision_to_domain(decision) if decision is not None else None,
            )
            for candidate, decision in (await self._session.execute(query)).all()
        ]

    async def get_candidate(
        self, organization_id: UUID, candidate_id: UUID
    ) -> DuplicateCandidate | None:
        query = select(DuplicateCandidateRecord).where(
            DuplicateCandidateRecord.organization_id == organization_id,
            DuplicateCandidateRecord.id == candidate_id,
        )
        row = (await self._session.execute(query)).scalar_one_or_none()
        return _candidate_to_domain(row) if row is not None else None

    async def get_decision(
        self, organization_id: UUID, candidate_id: UUID
    ) -> DeduplicationDecision | None:
        query = select(DeduplicationDecisionRecord).where(
            DeduplicationDecisionRecord.organization_id == organization_id,
            DeduplicationDecisionRecord.candidate_id == candidate_id,
        )
        row = (await self._session.execute(query)).scalar_one_or_none()
        return _decision_to_domain(row) if row is not None else None

    async def append_decision(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        candidate_id: UUID,
        decision: DedupDecisionKind,
        retained_article_id: UUID | None,
        decided_by_user_id: UUID,
        reason: str | None,
    ) -> DeduplicationDecision:
        row = DeduplicationDecisionRecord(
            organization_id=organization_id,
            review_id=review_id,
            candidate_id=candidate_id,
            decision=decision.value,
            retained_article_id=retained_article_id,
            decided_by_user_id=decided_by_user_id,
            reason=reason.strip() if reason else None,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _decision_to_domain(row)

    async def is_confirmed_duplicate(
        self, organization_id: UUID, review_id: UUID, article_id: UUID
    ) -> bool:
        query = (
            select(DeduplicationDecisionRecord.id)
            .join(
                DuplicateCandidateRecord,
                DuplicateCandidateRecord.id == DeduplicationDecisionRecord.candidate_id,
            )
            .where(
                DeduplicationDecisionRecord.organization_id == organization_id,
                DeduplicationDecisionRecord.review_id == review_id,
                DeduplicationDecisionRecord.decision == DedupDecisionKind.CONFIRMED_DUPLICATE.value,
                DeduplicationDecisionRecord.retained_article_id != article_id,
                (
                    (DuplicateCandidateRecord.left_article_id == article_id)
                    | (DuplicateCandidateRecord.right_article_id == article_id)
                ),
            )
            .limit(1)
        )
        return (await self._session.execute(query)).scalar_one_or_none() is not None
