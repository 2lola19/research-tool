from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from backend.app.analysis.contracts import AnalysisRepository
from backend.app.analysis.domain import MetaAnalysisRun, RunStatus
from backend.app.analysis.service import AnalysisService
from backend.app.certainty.contracts import CertaintyRepository
from backend.app.certainty.domain import (
    EVIDENCE_SNAPSHOT_VERSION,
    SOF_MODEL_VERSION,
    CertaintyAssessment,
    CertaintyAssessmentStatus,
    CertaintyComparison,
    CertaintyComparisonStatus,
    CertaintyFramework,
    CertaintyFrameworkVersion,
    CertaintyLevel,
    DecisionThresholdVersion,
    EvidenceBodyType,
    SummaryOfFindingsSnapshot,
    assessment_snapshot,
    calculate_candidate_certainty,
    canonical_hash,
    compare_assessments,
    normalize_framework_definition,
    normalize_threshold_definition,
)
from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.outcomes.contracts import OutcomeRepository
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.risk_of_bias.contracts import RiskOfBiasRepository
from backend.app.risk_of_bias.domain import AssessmentStatus


class CertaintyService:
    def __init__(
        self,
        repository: CertaintyRepository,
        outcomes: OutcomeRepository,
        analyses: AnalysisRepository,
        analysis_service: AnalysisService,
        risk_of_bias: RiskOfBiasRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._outcomes = outcomes
        self._analyses = analyses
        self._analysis_service = analysis_service
        self._risk_of_bias = risk_of_bias
        self._reviews = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_framework(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        key: str,
        name: str,
        description: str | None,
    ) -> CertaintyFramework:
        AuthorizationService.require(actor, Permission.MANAGE_CERTAINTY_FRAMEWORK)
        await self._reviews.get(actor, review_id)
        normalized_key = self._key(key)
        if any(
            item.key == normalized_key
            for item in await self._repository.list_frameworks(actor.organization_id, review_id)
        ):
            raise ConflictError("certainty framework key already exists")
        item = await self._repository.create_framework(
            organization_id=actor.organization_id,
            review_id=review_id,
            key=normalized_key,
            name=self._required(name, "framework name"),
            description=self._optional(description),
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            "certainty_framework",
            item.id,
            "CERTAINTY_FRAMEWORK_CREATED",
            None,
            {"key": item.key},
        )
        return item

    async def create_framework_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        framework_id: UUID,
        definition: dict[str, Any],
    ) -> CertaintyFrameworkVersion:
        AuthorizationService.require(actor, Permission.MANAGE_CERTAINTY_FRAMEWORK)
        await self._reviews.get(actor, review_id)
        await self._framework(actor, review_id, framework_id)
        try:
            normalized = normalize_framework_definition(definition)
        except (ValueError, TypeError) as exc:
            raise ConflictError(str(exc)) from exc
        item = await self._repository.create_framework_version(
            framework_id=framework_id,
            organization_id=actor.organization_id,
            review_id=review_id,
            definition=normalized,
            content_hash=canonical_hash(normalized),
            created_by_user_id=actor.user_id,
        )
        await self._scientific_write(
            actor,
            item.review_id,
            "certainty_framework_version",
            item.id,
            "CERTAINTY_FRAMEWORK_VERSIONED",
            None,
            {"version": item.version, "content_hash": item.content_hash},
            "certainty_framework",
            item.framework_id,
        )
        return item

    async def list_frameworks(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[tuple[CertaintyFramework, list[CertaintyFrameworkVersion]]]:
        await self._reviews.get(actor, review_id)
        items = await self._repository.list_frameworks(actor.organization_id, review_id)
        return [
            (
                item,
                await self._repository.list_framework_versions(
                    actor.organization_id, review_id, item.id
                ),
            )
            for item in items
        ]

    async def create_threshold_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        outcome_version_id: UUID,
        definition: dict[str, Any],
    ) -> DecisionThresholdVersion:
        AuthorizationService.require(actor, Permission.MANAGE_CERTAINTY_FRAMEWORK)
        await self._reviews.get(actor, review_id)
        await self._outcome(actor, review_id, outcome_version_id)
        try:
            normalized = normalize_threshold_definition(definition)
        except (ValueError, TypeError) as exc:
            raise ConflictError(str(exc)) from exc
        item = await self._repository.create_threshold_version(
            organization_id=actor.organization_id,
            review_id=review_id,
            outcome_version_id=outcome_version_id,
            definition=normalized,
            content_hash=canonical_hash(normalized),
            created_by_user_id=actor.user_id,
        )
        await self._scientific_write(
            actor,
            review_id,
            "certainty_threshold_version",
            item.id,
            "CERTAINTY_THRESHOLD_VERSIONED",
            None,
            {
                "outcome_version_id": str(outcome_version_id),
                "version": item.version,
                "content_hash": item.content_hash,
            },
            "outcome_definition_version",
            outcome_version_id,
        )
        return item

    async def create_assessment(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        outcome_version_id: UUID,
        timepoint_window_id: UUID | None,
        analysis_specification_version_id: UUID | None,
        meta_analysis_run_id: UUID | None,
        framework_version_id: UUID,
        threshold_version_id: UUID | None,
        round_number: int,
        evidence_body_type: EvidenceBodyType,
        evidence_body: dict[str, Any],
        starting_certainty: CertaintyLevel,
        starting_rationale: str,
        supersedes_assessment_id: UUID | None,
    ) -> CertaintyAssessment:
        AuthorizationService.require(actor, Permission.ASSESS_CERTAINTY)
        await self._reviews.get(actor, review_id)
        await self._outcome(actor, review_id, outcome_version_id)
        framework = await self._framework_version(actor, review_id, framework_version_id)
        expected = CertaintyLevel(framework.definition["starting_rules"][evidence_body_type.value])
        rationale = self._required(starting_rationale, "starting-certainty rationale")
        if starting_certainty != expected and len(rationale) < 20:
            raise ConflictError(
                "overriding the framework starting rule requires a substantive rationale"
            )
        if (
            timepoint_window_id is not None
            and await self._outcomes.get_timepoint_window(
                actor.organization_id, review_id, timepoint_window_id
            )
            is None
        ):
            raise ResourceNotFoundError("certainty timepoint window was not found")
        threshold = None
        if threshold_version_id is not None:
            threshold = await self._threshold(actor, review_id, threshold_version_id)
            if threshold.outcome_version_id != outcome_version_id:
                raise ConflictError("decision threshold belongs to another outcome version")
        run = await self._optional_run(actor, review_id, meta_analysis_run_id)
        if run is not None:
            spec = await self._analyses.get_specification_version(
                actor.organization_id, review_id, run.specification_version_id
            )
            if spec is None:
                raise ResourceNotFoundError("analysis specification version was not found")
            if analysis_specification_version_id != spec.id:
                raise ConflictError(
                    "certainty target must pin the run's analysis specification version"
                )
            if UUID(spec.definition["outcome_version_id"]) != outcome_version_id:
                raise ConflictError("certainty outcome does not match the analysis specification")
            if self._uuid_or_none(spec.definition["timepoint_window_id"]) != timepoint_window_id:
                raise ConflictError("certainty timepoint does not match the analysis specification")
            if await self._analysis_service.is_run_stale(actor, review_id=review_id, run_id=run.id):
                raise ConflictError(
                    "stale meta-analysis runs cannot be used for a current assessment"
                )
        elif analysis_specification_version_id is not None:
            raise ConflictError("an analysis specification requires its immutable run")
        await self._validate_narrative_studies(actor, review_id, evidence_body, run)
        revision = 1
        if supersedes_assessment_id is not None:
            previous = await self._raw_assessment(actor, review_id, supersedes_assessment_id)
            all_items = await self._repository.list_assessments(actor.organization_id, review_id)
            if (
                previous.status != CertaintyAssessmentStatus.SUBMITTED
                or previous.assessor_user_id != actor.user_id
            ):
                raise ConflictError("only the assessor's submitted assessment can be corrected")
            if any(item.supersedes_assessment_id == previous.id for item in all_items):
                raise ConflictError("certainty assessment already has a correction")
            target = (
                previous.outcome_version_id,
                previous.timepoint_window_id,
                previous.analysis_specification_version_id,
                previous.meta_analysis_run_id,
                previous.framework_version_id,
                previous.threshold_version_id,
                previous.round_number,
                previous.evidence_body_type,
            )
            if target != (
                outcome_version_id,
                timepoint_window_id,
                analysis_specification_version_id,
                meta_analysis_run_id,
                framework_version_id,
                threshold_version_id,
                round_number,
                evidence_body_type,
            ):
                raise ConflictError(
                    "correction must preserve its outcome, timepoint, analysis run, "
                    "framework, threshold version, round, and evidence-body type"
                )
            revision = previous.revision + 1
        item = await self._repository.create_assessment(
            organization_id=actor.organization_id,
            review_id=review_id,
            outcome_version_id=outcome_version_id,
            timepoint_window_id=timepoint_window_id,
            analysis_specification_version_id=analysis_specification_version_id,
            meta_analysis_run_id=meta_analysis_run_id,
            framework_version_id=framework_version_id,
            threshold_version_id=threshold_version_id,
            assessor_user_id=actor.user_id,
            round_number=round_number,
            revision=revision,
            supersedes_assessment_id=supersedes_assessment_id,
            evidence_body_type=evidence_body_type.value,
            evidence_body=evidence_body,
            starting_certainty=starting_certainty.value,
            starting_rationale=rationale,
            status=CertaintyAssessmentStatus.IN_PROGRESS.value,
            candidate_certainty=None,
            final_certainty=None,
            final_rationale=None,
            override_reason=None,
            evidence_snapshot=None,
            evidence_hash=None,
        )
        action = (
            "CERTAINTY_ASSESSMENT_CORRECTED"
            if supersedes_assessment_id
            else "CERTAINTY_ASSESSMENT_CREATED"
        )
        await self._scientific_write(
            actor,
            review_id,
            "certainty_assessment",
            item.id,
            action,
            None,
            assessment_snapshot(item),
            "meta_analysis_run" if run else "outcome_definition_version",
            run.id if run else outcome_version_id,
        )
        return item

    async def save_domain(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        domain_key: str,
        judgment: str,
        rationale: str,
        evidence_location_id: UUID | None,
        evidence: dict[str, Any],
    ) -> CertaintyAssessment:
        assessment, framework = await self._editable(actor, review_id, assessment_id)
        domain = self._domain(framework.definition, domain_key)
        choice = next(
            (item for item in domain["choices"] if item["value"] == self._key(judgment)), None
        )
        if choice is None:
            raise ConflictError("certainty judgment is not allowed by the pinned framework version")
        await self._validate_evidence_location(actor, review_id, evidence_location_id)
        updated = await self._repository.save_domain(
            assessment=assessment,
            domain_key=domain["key"],
            direction=domain["direction"],
            magnitude=choice["magnitude"],
            judgment=choice["value"],
            rationale=self._required(rationale, "domain rationale"),
            evidence_location_id=evidence_location_id,
            evidence=evidence,
        )
        await self._scientific_write(
            actor,
            review_id,
            "certainty_domain_judgment",
            next(item.id for item in updated.domain_judgments if item.domain_key == domain["key"]),
            "CERTAINTY_DOMAIN_JUDGMENT_RECORDED",
            assessment_snapshot(assessment),
            assessment_snapshot(updated),
            "document_evidence_location" if evidence_location_id else "certainty_assessment",
            evidence_location_id or assessment.id,
        )
        return updated

    async def save_final(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        final_certainty: CertaintyLevel,
        final_rationale: str,
        override_reason: str | None,
    ) -> CertaintyAssessment:
        assessment, framework = await self._editable(actor, review_id, assessment_id)
        required = {item["key"] for item in framework.definition["domains"]}
        if required != {item.domain_key for item in assessment.domain_judgments}:
            raise ConflictError("every certainty domain requires an explicit judgment")
        candidate = calculate_candidate_certainty(
            assessment.starting_certainty, assessment.domain_judgments
        )
        override = self._optional(override_reason)
        if final_certainty != candidate and override is None:
            raise ConflictError("overriding candidate certainty requires a reason")
        updated = await self._repository.save_final(
            assessment=assessment,
            candidate_certainty=candidate.value,
            final_certainty=final_certainty.value,
            final_rationale=self._required(final_rationale, "final-certainty rationale"),
            override_reason=override,
        )
        await self._scientific_write(
            actor,
            review_id,
            "certainty_assessment",
            assessment.id,
            "CERTAINTY_FINAL_JUDGMENT_RECORDED",
            assessment_snapshot(assessment),
            assessment_snapshot(updated),
            "certainty_framework_version",
            framework.id,
        )
        return updated

    async def submit(
        self, actor: ActorContext, *, review_id: UUID, assessment_id: UUID
    ) -> CertaintyAssessment:
        assessment, framework = await self._editable(actor, review_id, assessment_id)
        required = {item["key"] for item in framework.definition["domains"]}
        if (
            required != {item.domain_key for item in assessment.domain_judgments}
            or assessment.final_certainty is None
        ):
            raise ConflictError("all domains and final certainty are required before submission")
        current_candidate = calculate_candidate_certainty(
            assessment.starting_certainty, assessment.domain_judgments
        )
        if current_candidate != assessment.candidate_certainty:
            raise ConflictError(
                "domain judgments changed; resave final certainty before submission"
            )
        evidence = await self._evidence_profile(actor, assessment)
        if evidence["staleness"]["analysis_stale"]:
            raise ConflictError("stale analysis evidence cannot support a current submission")
        submitted = await self._repository.submit(
            assessment=assessment,
            evidence_snapshot=evidence,
            evidence_hash=canonical_hash(evidence),
        )
        await self._scientific_write(
            actor,
            review_id,
            "certainty_assessment",
            submitted.id,
            "CERTAINTY_ASSESSMENT_SUBMITTED",
            assessment_snapshot(assessment),
            assessment_snapshot(submitted),
            "meta_analysis_run" if submitted.meta_analysis_run_id else "outcome_definition_version",
            submitted.meta_analysis_run_id or submitted.outcome_version_id,
            VerificationState.HUMAN_VERIFIED,
        )
        return submitted

    async def list_assessments(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[tuple[CertaintyAssessment, bool]]:
        await self._reviews.get(actor, review_id)
        comparisons = await self._repository.list_comparisons(actor.organization_id, review_id)
        revealed = {
            assessment_id
            for comparison in comparisons
            for assessment_id in (comparison.assessment_a_id, comparison.assessment_b_id)
        }
        all_items = await self._repository.list_assessments(actor.organization_id, review_id)
        if actor.has_permission(Permission.ADJUDICATE_CERTAINTY) or actor.has_permission(
            Permission.ASSESS_CERTAINTY
        ):
            items = [
                item
                for item in all_items
                if item.assessor_user_id == actor.user_id or item.id in revealed
            ]
        else:
            items = [item for item in all_items if item.id in revealed]
        return [(item, await self._is_stale(actor, item)) for item in items]

    async def evidence_profile(
        self, actor: ActorContext, *, review_id: UUID, assessment_id: UUID
    ) -> dict[str, Any]:
        await self._reviews.get(actor, review_id)
        assessment = await self._assessment(actor, review_id, assessment_id, own=False)
        return await self._evidence_profile(actor, assessment)

    async def compare(
        self, actor: ActorContext, *, review_id: UUID, assessment_a_id: UUID, assessment_b_id: UUID
    ) -> CertaintyComparison:
        AuthorizationService.require(actor, Permission.ADJUDICATE_CERTAINTY)
        await self._reviews.get(actor, review_id)
        if assessment_a_id == assessment_b_id:
            raise ConflictError("comparison requires two different assessments")
        first = await self._raw_assessment(actor, review_id, assessment_a_id)
        second = await self._raw_assessment(actor, review_id, assessment_b_id)
        all_items = await self._repository.list_assessments(actor.organization_id, review_id)
        superseded = {
            item.supersedes_assessment_id for item in all_items if item.supersedes_assessment_id
        }
        if first.id in superseded or second.id in superseded:
            raise ConflictError("only current certainty revisions can be compared")
        if (
            first.status != CertaintyAssessmentStatus.SUBMITTED
            or second.status != CertaintyAssessmentStatus.SUBMITTED
        ):
            raise ConflictError("only submitted certainty assessments can be compared")
        if first.assessor_user_id == second.assessor_user_id:
            raise ConflictError("comparison requires independent assessors")
        target_a = (
            first.outcome_version_id,
            first.timepoint_window_id,
            first.framework_version_id,
            first.round_number,
            first.meta_analysis_run_id,
            first.threshold_version_id,
            first.evidence_body_type,
        )
        target_b = (
            second.outcome_version_id,
            second.timepoint_window_id,
            second.framework_version_id,
            second.round_number,
            second.meta_analysis_run_id,
            second.threshold_version_id,
            second.evidence_body_type,
        )
        if target_a != target_b:
            raise ConflictError(
                "certainty assessments must share the same evidence target, framework, and round"
            )
        first, second = sorted((first, second), key=lambda item: str(item.id))
        existing = await self._repository.get_comparison_for_pair(
            actor.organization_id, review_id, first.id, second.id
        )
        if existing:
            return existing
        differences = compare_assessments(first, second)
        item = await self._repository.create_comparison(
            organization_id=actor.organization_id,
            review_id=review_id,
            outcome_version_id=first.outcome_version_id,
            framework_version_id=first.framework_version_id,
            round_number=first.round_number,
            assessment_a_id=first.id,
            assessment_b_id=second.id,
            status=(
                CertaintyComparisonStatus.CONFLICT
                if differences
                else CertaintyComparisonStatus.AGREEMENT
            ).value,
            differences=list(differences),
            compared_by_user_id=actor.user_id,
            adjudicated_snapshot=None,
            adjudicated_by_user_id=None,
            adjudication_reason=None,
            adjudication_evidence_location_id=None,
            adjudicated_at=None,
        )
        await self._scientific_write(
            actor,
            review_id,
            "certainty_comparison",
            item.id,
            "CERTAINTY_CONFLICT_CREATED" if differences else "CERTAINTY_AGREEMENT_RECORDED",
            None,
            {"differences": list(differences)},
            "certainty_assessment",
            first.id,
        )
        return item

    async def adjudicate(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        comparison_id: UUID,
        resolution_assessment_id: UUID,
        rationale: str,
        evidence_location_id: UUID | None,
    ) -> CertaintyComparison:
        AuthorizationService.require(actor, Permission.ADJUDICATE_CERTAINTY)
        await self._reviews.get(actor, review_id)
        comparison = await self._repository.get_comparison(
            actor.organization_id, review_id, comparison_id
        )
        if comparison is None:
            raise ResourceNotFoundError("certainty comparison was not found")
        if comparison.status != CertaintyComparisonStatus.CONFLICT:
            raise ConflictError("only unresolved certainty conflicts can be adjudicated")
        if resolution_assessment_id not in (comparison.assessment_a_id, comparison.assessment_b_id):
            raise ConflictError("adjudication must preserve one original submitted assessment")
        await self._validate_evidence_location(actor, review_id, evidence_location_id)
        selected = await self._raw_assessment(actor, review_id, resolution_assessment_id)
        item = await self._repository.adjudicate(
            comparison=comparison,
            adjudicated_snapshot=assessment_snapshot(selected),
            adjudicated_by_user_id=actor.user_id,
            adjudication_reason=self._required(rationale, "adjudication rationale"),
            adjudication_evidence_location_id=evidence_location_id,
        )
        await self._scientific_write(
            actor,
            review_id,
            "certainty_comparison",
            item.id,
            "CERTAINTY_ADJUDICATED",
            {"differences": list(comparison.differences)},
            {"final_snapshot": item.adjudicated_snapshot},
            "certainty_assessment",
            selected.id,
            VerificationState.HUMAN_VERIFIED,
        )
        return item

    async def list_comparisons(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[CertaintyComparison]:
        await self._reviews.get(actor, review_id)
        return await self._repository.list_comparisons(actor.organization_id, review_id)

    async def create_sof_snapshot(
        self, actor: ActorContext, *, review_id: UUID, assessment_id: UUID
    ) -> SummaryOfFindingsSnapshot:
        AuthorizationService.require(actor, Permission.ASSESS_CERTAINTY)
        await self._reviews.get(actor, review_id)
        assessment = await self._assessment(actor, review_id, assessment_id, own=False)
        if assessment.status != CertaintyAssessmentStatus.SUBMITTED:
            raise ConflictError("Summary of Findings requires a submitted certainty assessment")
        if await self._is_stale(actor, assessment):
            raise ConflictError(
                "stale certainty evidence cannot create a current Summary of Findings"
            )
        profile = await self._evidence_profile(actor, assessment)
        row = self._sof_row(assessment, profile)
        item = await self._repository.create_sof_snapshot(
            organization_id=actor.organization_id,
            review_id=review_id,
            assessment_id=assessment.id,
            model_version=SOF_MODEL_VERSION,
            row=row,
            content_hash=canonical_hash(row),
            created_by_user_id=actor.user_id,
        )
        await self._scientific_write(
            actor,
            review_id,
            "summary_of_findings_snapshot",
            item.id,
            "SOF_SNAPSHOT_GENERATED",
            None,
            {"content_hash": item.content_hash, "row": row},
            "certainty_assessment",
            assessment.id,
            VerificationState.HUMAN_VERIFIED,
        )
        return item

    async def list_blind_comparison_candidates(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[dict[str, Any]]:
        await self._reviews.get(actor, review_id)
        if not actor.has_permission(Permission.ADJUDICATE_CERTAINTY):
            return []
        items = await self._repository.list_assessments(actor.organization_id, review_id)
        superseded = {
            item.supersedes_assessment_id for item in items if item.supersedes_assessment_id
        }
        return [
            {
                "id": str(item.id),
                "outcome_version_id": str(item.outcome_version_id),
                "timepoint_window_id": (
                    str(item.timepoint_window_id) if item.timepoint_window_id else None
                ),
                "framework_version_id": str(item.framework_version_id),
                "round_number": item.round_number,
                "assessor_user_id": str(item.assessor_user_id),
            }
            for item in items
            if item.status == CertaintyAssessmentStatus.SUBMITTED and item.id not in superseded
        ]

    async def list_workspace(self, actor: ActorContext, *, review_id: UUID) -> tuple[Any, ...]:
        frameworks = await self.list_frameworks(actor, review_id=review_id)
        assessments = await self.list_assessments(actor, review_id=review_id)
        return (
            frameworks,
            await self._repository.list_threshold_versions(actor.organization_id, review_id),
            assessments,
            await self.list_comparisons(actor, review_id=review_id),
            await self._repository.list_sof_snapshots(actor.organization_id, review_id),
        )

    async def _evidence_profile(
        self, actor: ActorContext, assessment: CertaintyAssessment
    ) -> dict[str, Any]:
        framework = await self._framework_version(
            actor, assessment.review_id, assessment.framework_version_id
        )
        outcome = await self._outcome(actor, assessment.review_id, assessment.outcome_version_id)
        threshold = (
            await self._threshold(actor, assessment.review_id, assessment.threshold_version_id)
            if assessment.threshold_version_id
            else None
        )
        run = await self._optional_run(actor, assessment.review_id, assessment.meta_analysis_run_id)
        analysis_stale = (
            await self._analysis_service.is_run_stale(
                actor, review_id=assessment.review_id, run_id=run.id
            )
            if run
            else False
        )
        study_ids: list[UUID] = []
        analysis_set = None
        if run:
            analysis_set = await self._analyses.get_analysis_set(
                actor.organization_id, assessment.review_id, run.analysis_set_id
            )
            assert analysis_set is not None
            for estimate_id in analysis_set.included_estimate_ids:
                estimate = await self._analyses.get_effect_estimate(
                    actor.organization_id, assessment.review_id, estimate_id
                )
                if estimate and estimate.study_id not in study_ids:
                    study_ids.append(estimate.study_id)
        else:
            study_ids = [UUID(item) for item in assessment.evidence_body.get("study_ids", [])]
        rob_items = await self._risk_of_bias.list_assessments(
            actor.organization_id, assessment.review_id
        )
        superseded = {
            item.supersedes_assessment_id for item in rob_items if item.supersedes_assessment_id
        }
        current_rob = [
            item
            for item in rob_items
            if item.study_id in study_ids
            and item.status == AssessmentStatus.SUBMITTED
            and item.id not in superseded
        ]
        rob_comparisons = await self._risk_of_bias.list_comparisons(
            actor.organization_id, assessment.review_id
        )
        relevant_rob_comparisons = [item for item in rob_comparisons if item.study_id in study_ids]
        unresolved = [item for item in relevant_rob_comparisons if item.status.value == "CONFLICT"]
        rob_history = [
            {
                "id": str(item.id),
                "study_id": str(item.study_id),
                "status": item.status.value,
                "assessment_a_id": str(item.assessment_a_id),
                "assessment_b_id": str(item.assessment_b_id),
                "differences": list(item.differences),
                "adjudicated_snapshot": item.adjudicated_snapshot,
            }
            for item in sorted(
                relevant_rob_comparisons,
                key=lambda value: (str(value.study_id), str(value.id)),
            )
        ]
        rob_summary = [
            {
                "id": str(item.id),
                "study_id": str(item.study_id),
                "revision": item.revision,
                "overall_judgment": item.overall_final_judgment,
                "instrument_version_id": str(item.instrument_version_id),
            }
            for item in sorted(current_rob, key=lambda value: (str(value.study_id), str(value.id)))
        ]
        weights = []
        if run and run.result:
            weights = list(run.result.get("weights", []))
        return {
            "snapshot_version": EVIDENCE_SNAPSHOT_VERSION,
            "framework_version": {"id": str(framework.id), "content_hash": framework.content_hash},
            "outcome": {
                "id": str(outcome.id),
                "definition": outcome.definition,
                "content_hash": outcome.content_hash,
            },
            "timepoint_window_id": str(assessment.timepoint_window_id)
            if assessment.timepoint_window_id
            else None,
            "threshold": (
                {
                    "id": str(threshold.id),
                    "content_hash": threshold.content_hash,
                    "definition": threshold.definition,
                }
                if threshold
                else None
            ),
            "analysis": (
                {
                    "run_id": str(run.id),
                    "specification_version_id": str(run.specification_version_id),
                    "analysis_set_id": str(run.analysis_set_id),
                    "input_hash": run.input_hash,
                    "result_hash": run.result_hash,
                    "result": run.result,
                    "diagnostics": list(run.diagnostics),
                    "weights": weights,
                }
                if run
                else None
            ),
            "evidence_body": assessment.evidence_body,
            "study_ids": [str(item) for item in sorted(study_ids, key=str)],
            "risk_of_bias": {
                "assessments": rob_summary,
                "comparisons": rob_history,
                "unresolved_count": len(unresolved),
            },
            "publication_bias": {
                "formal_inference": "NOT_IMPLEMENTED",
                "available_evidence": assessment.evidence_body.get("publication_bias_evidence", {}),
            },
            "absolute_effect": {
                "status": "UNAVAILABLE",
                "reason": "BASELINE_RISK_CALCULATION_NOT_IMPLEMENTED",
            },
            "staleness": {"analysis_stale": analysis_stale},
        }

    def _sof_row(self, assessment: CertaintyAssessment, profile: dict[str, Any]) -> dict[str, Any]:
        analysis = profile["analysis"]
        result = analysis["result"] if analysis else None
        return {
            "outcome_version_id": str(assessment.outcome_version_id),
            "outcome": profile["outcome"]["definition"]["name"],
            "timepoint_window_id": profile["timepoint_window_id"],
            "study_count": len(profile["study_ids"]),
            "participants": result.get("total_participants") if result else None,
            "effect_measure": result.get("effect_measure") if result else None,
            "relative_or_continuous_effect": (
                {
                    "estimate": result.get("presentation_estimate"),
                    "ci_lower": result.get("presentation_ci_lower"),
                    "ci_upper": result.get("presentation_ci_upper"),
                }
                if result
                else None
            ),
            "absolute_effect": profile["absolute_effect"],
            "domains": {item.domain_key: item.judgment for item in assessment.domain_judgments},
            "final_certainty": assessment.final_certainty.value
            if assessment.final_certainty
            else None,
            "key_rationale": assessment.final_rationale,
            "evidence_hash": assessment.evidence_hash,
            "evidence_stale": profile["staleness"]["analysis_stale"]
            or (
                assessment.evidence_hash is not None
                and assessment.evidence_hash != canonical_hash(profile)
            ),
        }

    async def _is_stale(self, actor: ActorContext, assessment: CertaintyAssessment) -> bool:
        if (
            assessment.status != CertaintyAssessmentStatus.SUBMITTED
            or assessment.evidence_hash is None
        ):
            return False
        return (
            canonical_hash(await self._evidence_profile(actor, assessment))
            != assessment.evidence_hash
        )

    async def _editable(
        self, actor: ActorContext, review_id: UUID, assessment_id: UUID
    ) -> tuple[CertaintyAssessment, CertaintyFrameworkVersion]:
        AuthorizationService.require(actor, Permission.ASSESS_CERTAINTY)
        await self._reviews.get(actor, review_id)
        assessment = await self._assessment(actor, review_id, assessment_id, own=True)
        if assessment.status != CertaintyAssessmentStatus.IN_PROGRESS:
            raise ConflictError(
                "submitted certainty assessments are immutable; create a correction"
            )
        return assessment, await self._framework_version(
            actor, review_id, assessment.framework_version_id
        )

    async def _assessment(
        self, actor: ActorContext, review_id: UUID, assessment_id: UUID, *, own: bool
    ) -> CertaintyAssessment:
        item = await self._raw_assessment(actor, review_id, assessment_id)
        if item.assessor_user_id == actor.user_id:
            return item
        if own:
            raise ResourceNotFoundError("certainty assessment was not found")
        comparisons = await self._repository.list_comparisons(actor.organization_id, review_id)
        revealed = {
            assessment_id
            for comparison in comparisons
            for assessment_id in (comparison.assessment_a_id, comparison.assessment_b_id)
        }
        if item.id not in revealed:
            raise ResourceNotFoundError("certainty assessment was not found")
        return item

    async def _raw_assessment(
        self, actor: ActorContext, review_id: UUID, assessment_id: UUID
    ) -> CertaintyAssessment:
        item = await self._repository.get_assessment(
            actor.organization_id, review_id, assessment_id
        )
        if item is None:
            raise ResourceNotFoundError("certainty assessment was not found")
        return item

    async def _framework(
        self, actor: ActorContext, review_id: UUID, framework_id: UUID
    ) -> CertaintyFramework:
        item = await self._repository.get_framework(actor.organization_id, review_id, framework_id)
        if item is None:
            raise ResourceNotFoundError("certainty framework was not found")
        return item

    async def _framework_version(
        self, actor: ActorContext, review_id: UUID, version_id: UUID
    ) -> CertaintyFrameworkVersion:
        item = await self._repository.get_framework_version(
            actor.organization_id, review_id, version_id
        )
        if item is None:
            raise ResourceNotFoundError("certainty framework version was not found")
        return item

    async def _threshold(
        self, actor: ActorContext, review_id: UUID, version_id: UUID
    ) -> DecisionThresholdVersion:
        item = await self._repository.get_threshold_version(
            actor.organization_id, review_id, version_id
        )
        if item is None:
            raise ResourceNotFoundError("certainty threshold version was not found")
        return item

    async def _outcome(self, actor: ActorContext, review_id: UUID, outcome_id: UUID) -> Any:
        item = await self._outcomes.get_outcome_version(
            actor.organization_id, review_id, outcome_id
        )
        if item is None:
            raise ResourceNotFoundError("certainty outcome version was not found")
        return item

    async def _optional_run(
        self, actor: ActorContext, review_id: UUID, run_id: UUID | None
    ) -> MetaAnalysisRun | None:
        if run_id is None:
            return None
        run = await self._analyses.get_run(actor.organization_id, review_id, run_id)
        if run is None:
            raise ResourceNotFoundError("meta-analysis run was not found")
        if run.status != RunStatus.COMPLETED:
            raise ConflictError("certainty assessment requires a completed meta-analysis run")
        return run

    async def _validate_narrative_studies(
        self,
        actor: ActorContext,
        review_id: UUID,
        evidence_body: dict[str, Any],
        run: MetaAnalysisRun | None,
    ) -> None:
        ids = evidence_body.get("study_ids", [])
        if run is None and (not isinstance(ids, list) or not ids):
            raise ConflictError("narrative certainty assessment requires structured Study IDs")
        if isinstance(ids, list):
            for raw in ids:
                try:
                    study_id = UUID(str(raw))
                except ValueError as exc:
                    raise ConflictError("narrative evidence contains an invalid Study ID") from exc
                if (
                    await self._analyses.study_label(actor.organization_id, review_id, study_id)
                    is None
                ):
                    raise ResourceNotFoundError("narrative evidence Study was not found")

    async def _validate_evidence_location(
        self, actor: ActorContext, review_id: UUID, location_id: UUID | None
    ) -> None:
        if location_id is not None and not await self._repository.evidence_location_exists(
            actor.organization_id, review_id, location_id
        ):
            raise ResourceNotFoundError("certainty evidence location was not found")

    async def _scientific_write(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        source_type: str,
        source_id: UUID,
        verification_state: VerificationState = VerificationState.UNVERIFIED,
    ) -> None:
        await self._provenance.record_provenance(
            actor,
            review_id=review_id,
            subject_type=entity_type,
            subject_id=entity_id,
            source_type=source_type,
            source_id=source_id,
            source_locator={},
            method_name="structured_human_certainty",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=verification_state,
        )
        await self._audit(actor, review_id, entity_type, entity_id, action, before, after)

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any],
    ) -> None:
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_snapshot=before,
            after_snapshot=after,
            reason=None,
        )

    @staticmethod
    def _domain(definition: dict[str, Any], key: str) -> dict[str, Any]:
        normalized = CertaintyService._key(key)
        for item in definition["domains"]:
            if item["key"] == normalized:
                return cast(dict[str, Any], item)
        raise ConflictError("certainty domain is not defined by the pinned framework version")

    @staticmethod
    def _uuid_or_none(value: Any) -> UUID | None:
        return UUID(str(value)) if value else None

    @staticmethod
    def _key(value: str) -> str:
        key = value.strip().upper()
        if (
            not key
            or len(key) > 120
            or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in key)
        ):
            raise ConflictError("scientific key is invalid")
        return key

    @staticmethod
    def _required(value: str, label: str) -> str:
        result = value.strip()
        if not result:
            raise ConflictError(f"{label} is required")
        return result

    @staticmethod
    def _optional(value: str | None) -> str | None:
        result = (value or "").strip()
        return result or None
