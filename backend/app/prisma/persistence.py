from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    event,
    false,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.citations.persistence import ArticleRecord, CitationSourceRecordRow
from backend.app.db.base import Base
from backend.app.deduplication.persistence import (
    DeduplicationDecisionRecord,
    DuplicateCandidateRecord,
)
from backend.app.documents.persistence import (
    DocumentRecord,
    FullTextCriterionJudgmentRecord,
    FullTextScreeningRecord,
)
from backend.app.prisma.domain import PrismaBlocker, PrismaReadiness, PrismaSnapshot, PrismaSummary
from backend.app.screening.persistence import (
    ScreeningAdjudicationRecord,
    ScreeningAssignmentRecord,
    ScreeningOutcomeRecord,
    ScreeningProgressionRecord,
    ScreeningRoundRecord,
)
from backend.app.studies.persistence import StudyArticleLinkRecord


class PrismaSnapshotRecord(Base):
    __tablename__ = "prisma_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_prisma_snapshots_id_tenant"
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_prisma_snapshots_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_prisma_snapshots_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    created_by_user_id: Mapped[UUID] = mapped_column()
    algorithm_version: Mapped[str] = mapped_column(String(80))
    counts: Mapped[dict[str, Any]] = mapped_column(JSON)
    readiness: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_references: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_snapshot_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("PRISMA snapshots are immutable")


event.listen(PrismaSnapshotRecord, "before_update", _reject_snapshot_mutation)
event.listen(PrismaSnapshotRecord, "before_delete", _reject_snapshot_mutation)


def _snapshot(row: PrismaSnapshotRecord) -> PrismaSnapshot:
    return PrismaSnapshot(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        created_by_user_id=row.created_by_user_id,
        algorithm_version=row.algorithm_version,
        counts=row.counts,
        readiness=row.readiness,
        source_references=row.source_references,
        created_at=row.created_at or datetime.now(UTC),
    )


class SqlAlchemyPrismaRepository:
    algorithm_version = "prisma-2020-deterministic-1"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summarize(
        self, organization_id: UUID, review_id: UUID
    ) -> tuple[PrismaSummary, PrismaReadiness, dict[str, Any]]:
        source_rows = list(
            await self._session.scalars(
                select(CitationSourceRecordRow)
                .where(
                    CitationSourceRecordRow.organization_id == organization_id,
                    CitationSourceRecordRow.review_id == review_id,
                )
                .order_by(
                    CitationSourceRecordRow.import_batch_id,
                    CitationSourceRecordRow.ordinal,
                    CitationSourceRecordRow.id,
                )
            )
        )
        article_rows = list(
            await self._session.scalars(
                select(ArticleRecord)
                .where(
                    ArticleRecord.organization_id == organization_id,
                    ArticleRecord.review_id == review_id,
                )
                .order_by(ArticleRecord.id)
            )
        )
        source_counts = Counter(row.article_id for row in source_rows)

        candidate_ids = list(
            await self._session.scalars(
                select(DuplicateCandidateRecord.id)
                .where(
                    DuplicateCandidateRecord.organization_id == organization_id,
                    DuplicateCandidateRecord.review_id == review_id,
                )
                .order_by(DuplicateCandidateRecord.id)
            )
        )
        duplicate_decision_ids = list(
            await self._session.scalars(
                select(DeduplicationDecisionRecord.id)
                .where(
                    DeduplicationDecisionRecord.organization_id == organization_id,
                    DeduplicationDecisionRecord.review_id == review_id,
                )
                .order_by(DeduplicationDecisionRecord.id)
            )
        )
        duplicate_rows = (
            await self._session.execute(
                select(
                    DuplicateCandidateRecord.id,
                    DuplicateCandidateRecord.left_article_id,
                    DuplicateCandidateRecord.right_article_id,
                    DeduplicationDecisionRecord.id,
                    DeduplicationDecisionRecord.retained_article_id,
                )
                .join(
                    DeduplicationDecisionRecord,
                    DeduplicationDecisionRecord.candidate_id == DuplicateCandidateRecord.id,
                )
                .where(
                    DuplicateCandidateRecord.organization_id == organization_id,
                    DuplicateCandidateRecord.review_id == review_id,
                    DeduplicationDecisionRecord.decision == "CONFIRMED_DUPLICATE",
                )
                .order_by(DuplicateCandidateRecord.id)
            )
        ).all()
        suppressed_articles: set[UUID] = set()
        for _, left_id, right_id, _, retained_id in duplicate_rows:
            suppressed_articles.update({left_id, right_id} - {retained_id})
        unresolved_duplicates = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(DuplicateCandidateRecord)
                    .outerjoin(
                        DeduplicationDecisionRecord,
                        DeduplicationDecisionRecord.candidate_id == DuplicateCandidateRecord.id,
                    )
                    .where(
                        DuplicateCandidateRecord.organization_id == organization_id,
                        DuplicateCandidateRecord.review_id == review_id,
                        DeduplicationDecisionRecord.id.is_(None),
                    )
                )
            ).scalar_one()
        )

        round_rows = list(
            await self._session.scalars(
                select(ScreeningRoundRecord)
                .where(
                    ScreeningRoundRecord.organization_id == organization_id,
                    ScreeningRoundRecord.review_id == review_id,
                )
                .order_by(ScreeningRoundRecord.sequence, ScreeningRoundRecord.id)
            )
        )
        title_rounds = [row for row in round_rows if row.stage == "TITLE_ABSTRACT"]
        title_round = title_rounds[0] if title_rounds else None
        full_rounds = [row for row in round_rows if row.stage == "FULL_TEXT"]
        full_round_ids = {row.id for row in full_rounds}
        assignments = (
            list(
                await self._session.scalars(
                    select(ScreeningAssignmentRecord).where(
                        ScreeningAssignmentRecord.organization_id == organization_id,
                        ScreeningAssignmentRecord.review_id == review_id,
                    )
                )
            )
            if title_round is not None
            else []
        )
        title_assignments = (
            [row for row in assignments if row.round_id == title_round.id] if title_round else []
        )
        title_article_ids = {row.article_id for row in title_assignments}
        screened_article_ids = title_article_ids - suppressed_articles
        title_outcomes = (
            list(
                await self._session.scalars(
                    select(ScreeningOutcomeRecord)
                    .where(
                        ScreeningOutcomeRecord.organization_id == organization_id,
                        ScreeningOutcomeRecord.review_id == review_id,
                        ScreeningOutcomeRecord.round_id == title_round.id,
                    )
                    .order_by(ScreeningOutcomeRecord.id)
                )
            )
            if title_round is not None
            else []
        )
        title_adjudication_rows = list(
            await self._session.scalars(
                select(ScreeningAdjudicationRecord)
                .where(
                    ScreeningAdjudicationRecord.organization_id == organization_id,
                    ScreeningAdjudicationRecord.review_id == review_id,
                )
                .order_by(ScreeningAdjudicationRecord.id)
            )
        )
        title_adjudications = {row.outcome_id: row.decision for row in title_adjudication_rows}
        title_final: dict[UUID, str] = {}
        unresolved_title_conflicts = 0
        for outcome in title_outcomes:
            if outcome.outcome == "CONFLICT":
                decision = title_adjudications.get(outcome.id)
                if decision is None:
                    unresolved_title_conflicts += 1
                else:
                    title_final[outcome.article_id] = decision
            else:
                title_final[outcome.article_id] = outcome.outcome

        progressions = list(
            await self._session.scalars(
                select(ScreeningProgressionRecord)
                .where(
                    ScreeningProgressionRecord.organization_id == organization_id,
                    ScreeningProgressionRecord.review_id == review_id,
                )
                .order_by(ScreeningProgressionRecord.id)
            )
        )
        sought_article_ids = {
            row.article_id for row in progressions if row.target_round_id in full_round_ids
        }
        documents = list(
            await self._session.scalars(
                select(DocumentRecord)
                .where(
                    DocumentRecord.organization_id == organization_id,
                    DocumentRecord.review_id == review_id,
                )
                .order_by(DocumentRecord.id)
            )
        )
        documents_by_article: dict[UUID, list[DocumentRecord]] = defaultdict(list)
        for document in documents:
            documents_by_article[document.article_id].append(document)
        terminal_retrieval = {
            "RETRIEVED",
            "OPEN_ACCESS",
            "USER_UPLOADED",
            "EXTERNAL_LINK_ONLY",
            "PAYWALLED",
            "NOT_FOUND",
            "INVALID_FILE",
            "PROCESSED",
            "PROCESSING_FAILED",
            "RETRACTION_WARNING",
            "SUPPLEMENT_AVAILABLE",
        }
        retrieved_article_ids = {
            article_id
            for article_id, rows in documents_by_article.items()
            if any(row.storage_key is not None for row in rows)
        }
        pending_retrieval = {
            article_id
            for article_id in sought_article_ids
            if not documents_by_article.get(article_id)
            or any(row.status not in terminal_retrieval for row in documents_by_article[article_id])
        }

        full_text_rows = list(
            await self._session.scalars(
                select(FullTextScreeningRecord)
                .where(
                    FullTextScreeningRecord.organization_id == organization_id,
                    FullTextScreeningRecord.review_id == review_id,
                )
                .order_by(FullTextScreeningRecord.id)
            )
        )
        document_article = {row.id: row.article_id for row in documents}
        assessed_article_ids = {
            document_article[row.document_id]
            for row in full_text_rows
            if row.document_id in document_article
        }
        article_decisions: dict[UUID, set[str]] = defaultdict(set)
        for row in full_text_rows:
            article_id = document_article.get(row.document_id)
            if article_id is not None:
                article_decisions[article_id].add(row.final_decision)
        included_article_ids = {
            article_id
            for article_id, decisions in article_decisions.items()
            if decisions == {"INCLUDE"}
        }
        excluded_article_ids = {
            article_id
            for article_id, decisions in article_decisions.items()
            if decisions == {"EXCLUDE"}
        }
        unresolved_full_text = sum("MAYBE" in decisions for decisions in article_decisions.values())
        conflicting_full_text = sum(
            len(decisions - {"MAYBE"}) > 1 for decisions in article_decisions.values()
        )
        exclusion_rows = list(
            await self._session.scalars(
                select(FullTextCriterionJudgmentRecord)
                .where(
                    FullTextCriterionJudgmentRecord.organization_id == organization_id,
                    FullTextCriterionJudgmentRecord.review_id == review_id,
                    FullTextCriterionJudgmentRecord.decision == "FAIL",
                )
                .order_by(FullTextCriterionJudgmentRecord.id)
            )
        )
        excluded_screening_ids = {
            row.id for row in full_text_rows if row.final_decision == "EXCLUDE"
        }
        reasons = Counter(
            row.criterion_key if row.screening_id in excluded_screening_ids else ""
            for row in exclusion_rows
        )
        reasons.pop("", None)

        link_query = select(StudyArticleLinkRecord).where(
            StudyArticleLinkRecord.organization_id == organization_id,
            StudyArticleLinkRecord.review_id == review_id,
            StudyArticleLinkRecord.unlinked_at.is_(None),
        )
        if included_article_ids:
            link_query = link_query.where(
                StudyArticleLinkRecord.article_id.in_(included_article_ids)
            )
        else:
            link_query = link_query.where(false())
        included_links = list(await self._session.scalars(link_query))
        included_study_ids = {row.study_id for row in included_links}
        missing_study_assignments = included_article_ids - {
            row.article_id for row in included_links
        }

        blockers: list[PrismaBlocker] = [
            PrismaBlocker(
                "SEARCH_EXECUTION_NOT_RECORDED",
                "Search execution records are not yet represented by the current domain.",
            )
        ]
        if unresolved_duplicates:
            blockers.append(
                PrismaBlocker(
                    "DEDUPLICATION_UNRESOLVED",
                    "Duplicate candidates still lack a decision.",
                    unresolved_duplicates,
                )
            )
        if title_round is None:
            blockers.append(
                PrismaBlocker("TITLE_ABSTRACT_ROUND_MISSING", "No title/abstract round exists.")
            )
        else:
            eligible_title_articles = {row.id for row in article_rows} - suppressed_articles
            unassigned_title_articles = eligible_title_articles - screened_article_ids
            if unassigned_title_articles:
                blockers.append(
                    PrismaBlocker(
                        "TITLE_ABSTRACT_RECORDS_UNASSIGNED",
                        "Some non-duplicate records have not been assigned for screening.",
                        len(unassigned_title_articles),
                    )
                )
            missing_title_outcomes = len(screened_article_ids - set(title_final))
            if missing_title_outcomes:
                blockers.append(
                    PrismaBlocker(
                        "TITLE_ABSTRACT_SCREENING_INCOMPLETE",
                        "Some title/abstract assignments have no final outcome.",
                        missing_title_outcomes,
                    )
                )
            if title_round.state != "CLOSED":
                blockers.append(
                    PrismaBlocker(
                        "TITLE_ABSTRACT_ROUND_OPEN",
                        "The title/abstract screening round has not been closed.",
                    )
                )
            if unresolved_title_conflicts:
                blockers.append(
                    PrismaBlocker(
                        "TITLE_ABSTRACT_CONFLICTS_UNRESOLVED",
                        "Title/abstract screening conflicts remain unresolved.",
                        unresolved_title_conflicts,
                    )
                )
        if len(title_rounds) > 1:
            blockers.append(
                PrismaBlocker(
                    "MULTIPLE_TITLE_ABSTRACT_ROUNDS",
                    "Multiple title/abstract rounds require an explicit reporting policy.",
                    len(title_rounds),
                )
            )
        if not full_rounds:
            blockers.append(
                PrismaBlocker("FULL_TEXT_ROUND_MISSING", "No full-text screening round exists.")
            )
        elif len(full_rounds) > 1:
            blockers.append(
                PrismaBlocker(
                    "MULTIPLE_FULL_TEXT_ROUNDS",
                    "Multiple full-text rounds require an explicit reporting policy.",
                    len(full_rounds),
                )
            )
        elif full_rounds[0].state != "CLOSED":
            blockers.append(
                PrismaBlocker(
                    "FULL_TEXT_ROUND_OPEN",
                    "The full-text screening round has not been closed.",
                )
            )
        if pending_retrieval:
            blockers.append(
                PrismaBlocker(
                    "RETRIEVAL_INCOMPLETE",
                    "Some reports sought for retrieval have no settled retrieval state.",
                    len(pending_retrieval),
                )
            )
        if unresolved_full_text:
            blockers.append(
                PrismaBlocker(
                    "FULL_TEXT_ELIGIBILITY_UNRESOLVED",
                    "Full-text eligibility decisions remain MAYBE.",
                    unresolved_full_text,
                )
            )
        if conflicting_full_text:
            blockers.append(
                PrismaBlocker(
                    "FULL_TEXT_REPORT_DECISIONS_CONFLICT",
                    "Reports with multiple Documents have conflicting eligibility decisions.",
                    conflicting_full_text,
                )
            )
        full_text_missing = (sought_article_ids & retrieved_article_ids) - assessed_article_ids
        if full_text_missing:
            blockers.append(
                PrismaBlocker(
                    "FULL_TEXT_SCREENING_INCOMPLETE",
                    "Some retrieved reports have not been assessed for eligibility.",
                    len(full_text_missing),
                )
            )
        if missing_study_assignments:
            blockers.append(
                PrismaBlocker(
                    "INCLUDED_ARTICLE_WITHOUT_STUDY",
                    "Included Articles must be assigned to a Study before finalization.",
                    len(missing_study_assignments),
                )
            )

        summary = PrismaSummary(
            records_identified_databases=len(source_rows),
            records_identified_other_sources=0,
            records_removed_duplicates=sum(
                source_counts.get(article_id, 0) for article_id in suppressed_articles
            ),
            records_removed_other_reasons=0,
            records_screened=sum(
                source_counts.get(article_id, 0) for article_id in screened_article_ids
            ),
            records_excluded_title_abstract=sum(
                source_counts.get(article_id, 0)
                for article_id, decision in title_final.items()
                if decision == "EXCLUDE" and article_id in screened_article_ids
            ),
            reports_sought_for_retrieval=len(sought_article_ids),
            reports_not_retrieved=len(
                sought_article_ids - retrieved_article_ids - pending_retrieval
            ),
            reports_assessed_for_eligibility=len(assessed_article_ids),
            reports_excluded_full_text=len(excluded_article_ids),
            studies_included_review=len(included_study_ids),
            reports_of_included_studies=len(included_article_ids),
            studies_included_meta_analysis=None,
            full_text_exclusion_reasons=dict(sorted(reasons.items())),
        )
        references = {
            "citation_source_ids": [str(row.id) for row in source_rows],
            "article_ids": [str(row.id) for row in article_rows],
            "deduplication_candidate_ids": [str(item) for item in candidate_ids],
            "deduplication_decision_ids": [str(item) for item in duplicate_decision_ids],
            "title_abstract_round_id": str(title_round.id) if title_round else None,
            "title_abstract_outcome_ids": [str(row.id) for row in title_outcomes],
            "title_abstract_adjudication_ids": [str(row.id) for row in title_adjudication_rows],
            "full_text_round_ids": [str(item) for item in sorted(full_round_ids, key=str)],
            "screening_progression_ids": [str(row.id) for row in progressions],
            "document_ids": [str(row.id) for row in documents],
            "full_text_screening_ids": [str(row.id) for row in full_text_rows],
            "full_text_exclusion_judgment_ids": [str(row.id) for row in exclusion_rows],
            "study_article_link_ids": [str(row.id) for row in included_links],
        }
        return summary, PrismaReadiness(not blockers, tuple(blockers)), references

    async def create_snapshot(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        created_by_user_id: UUID,
        algorithm_version: str,
        summary: PrismaSummary,
        readiness: PrismaReadiness,
        source_references: dict[str, Any],
    ) -> PrismaSnapshot:
        row = PrismaSnapshotRecord(
            organization_id=organization_id,
            review_id=review_id,
            created_by_user_id=created_by_user_id,
            algorithm_version=algorithm_version,
            counts=summary.as_dict(),
            readiness=readiness.as_dict(),
            source_references=source_references,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _snapshot(row)

    async def get_snapshot(
        self, organization_id: UUID, review_id: UUID, snapshot_id: UUID
    ) -> PrismaSnapshot | None:
        row = (
            await self._session.execute(
                select(PrismaSnapshotRecord).where(
                    PrismaSnapshotRecord.organization_id == organization_id,
                    PrismaSnapshotRecord.review_id == review_id,
                    PrismaSnapshotRecord.id == snapshot_id,
                )
            )
        ).scalar_one_or_none()
        return _snapshot(row) if row else None

    async def list_snapshots(self, organization_id: UUID, review_id: UUID) -> list[PrismaSnapshot]:
        rows = await self._session.scalars(
            select(PrismaSnapshotRecord)
            .where(
                PrismaSnapshotRecord.organization_id == organization_id,
                PrismaSnapshotRecord.review_id == review_id,
            )
            .order_by(PrismaSnapshotRecord.created_at, PrismaSnapshotRecord.id)
        )
        return [_snapshot(row) for row in rows]
