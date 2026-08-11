from __future__ import annotations

import hashlib
import json
from typing import Any, cast
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.risk_of_bias.contracts import RiskOfBiasRepository
from backend.app.risk_of_bias.domain import (
    AssessmentStatus,
    ComparisonStatus,
    InstrumentDecision,
    RiskOfBiasAssessment,
    RiskOfBiasComparison,
    RiskOfBiasInstrument,
    RiskOfBiasInstrumentVersion,
    assessment_snapshot,
    compare_assessment_snapshots,
    normalize_instrument_definition,
    suggest_domain_judgment,
    suggest_overall_judgment,
)
from backend.app.studies.contracts import StudyRepository


class RiskOfBiasService:
    def __init__(
        self,
        repository: RiskOfBiasRepository,
        study_repository: StudyRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._studies = study_repository
        self._reviews = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_instrument(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        key: str,
        name: str,
        description: str | None,
    ) -> RiskOfBiasInstrument:
        AuthorizationService.require(actor, Permission.MANAGE_ROB_INSTRUMENT)
        review = await self._reviews.get(actor, review_id)
        normalized_key = self._key(key)
        existing = await self._repository.list_instruments(actor.organization_id, review.id)
        if any(item.key == normalized_key for item in existing):
            raise ConflictError("Risk of Bias instrument key already exists")
        instrument = await self._repository.create_instrument(
            organization_id=actor.organization_id,
            review_id=review.id,
            key=normalized_key,
            name=self._required(name, "instrument name"),
            description=self._optional(description),
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review.id,
            "rob_instrument",
            instrument.id,
            "ROB_INSTRUMENT_CREATED",
            None,
            {"key": instrument.key, "name": instrument.name},
        )
        return instrument

    async def create_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        instrument_id: UUID,
        definition: dict[str, Any],
    ) -> RiskOfBiasInstrumentVersion:
        AuthorizationService.require(actor, Permission.MANAGE_ROB_INSTRUMENT)
        await self._reviews.get(actor, review_id)
        instrument = await self._instrument(actor, review_id, instrument_id)
        try:
            normalized = normalize_instrument_definition(definition)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
        version = await self._repository.create_version(
            instrument_id=instrument.id,
            organization_id=actor.organization_id,
            review_id=review_id,
            definition=normalized,
            content_hash=hashlib.sha256(encoded).hexdigest(),
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            "rob_instrument_version",
            version.id,
            "ROB_INSTRUMENT_VERSION_CREATED",
            None,
            {"instrument_id": str(instrument.id), "version": version.version},
        )
        return version

    async def decide_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        version_id: UUID,
        decision: InstrumentDecision,
        reason: str | None,
    ) -> RiskOfBiasInstrumentVersion:
        AuthorizationService.require(actor, Permission.MANAGE_ROB_INSTRUMENT)
        await self._reviews.get(actor, review_id)
        version = await self._version(actor, review_id, version_id)
        if version.decision is not None:
            raise ConflictError("instrument version already has an immutable decision")
        decided = await self._repository.decide_version(
            version=version,
            decision=decision,
            decided_by_user_id=actor.user_id,
            reason=self._optional(reason),
        )
        await self._audit(
            actor,
            review_id,
            "rob_instrument_version",
            version.id,
            "ROB_INSTRUMENT_VERSION_DECIDED",
            None,
            {"decision": decision.value},
            reason,
        )
        return decided

    async def list_instruments(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[tuple[RiskOfBiasInstrument, list[RiskOfBiasInstrumentVersion]]]:
        await self._reviews.get(actor, review_id)
        instruments = await self._repository.list_instruments(actor.organization_id, review_id)
        return [
            (
                item,
                await self._repository.list_versions(actor.organization_id, review_id, item.id),
            )
            for item in instruments
        ]

    async def create_assessment(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        study_id: UUID,
        instrument_version_id: UUID,
        round_number: int,
        supersedes_assessment_id: UUID | None = None,
    ) -> RiskOfBiasAssessment:
        AuthorizationService.require(actor, Permission.PERFORM_ROB_ASSESSMENT)
        await self._reviews.get(actor, review_id)
        if round_number < 1:
            raise ConflictError("assessment round must be positive")
        study = await self._studies.get_study(actor.organization_id, review_id, study_id)
        if study is None:
            raise ResourceNotFoundError("study was not found")
        if study.study_design is None:
            raise ConflictError("Study design must be recorded before Risk of Bias assessment")
        version = await self._version(actor, review_id, instrument_version_id)
        if version.decision != InstrumentDecision.APPROVED:
            raise ConflictError("only an approved instrument version can be assessed")
        if study.study_design not in version.definition["applicable_study_designs"]:
            raise ConflictError("instrument version is not compatible with the Study design")

        revision = 1
        if supersedes_assessment_id is not None:
            prior = await self._assessment(actor, review_id, supersedes_assessment_id, own=True)
            if prior.status != AssessmentStatus.SUBMITTED:
                raise ConflictError("only a submitted assessment can be corrected")
            if (
                prior.study_id != study.id
                or prior.instrument_version_id != version.id
                or prior.round_number != round_number
            ):
                raise ConflictError("a correction must retain Study, instrument version, and round")
            revision = prior.revision + 1
        else:
            existing = await self._repository.list_assessments(
                actor.organization_id, review_id, assessor_user_id=actor.user_id
            )
            if any(
                item.study_id == study.id
                and item.instrument_version_id == version.id
                and item.round_number == round_number
                for item in existing
            ):
                raise ConflictError("an assessment already exists; create an explicit correction")

        assessment = await self._repository.create_assessment(
            organization_id=actor.organization_id,
            review_id=review_id,
            study_id=study.id,
            instrument_version_id=version.id,
            assessor_user_id=actor.user_id,
            round_number=round_number,
            revision=revision,
            supersedes_assessment_id=supersedes_assessment_id,
            status=AssessmentStatus.IN_PROGRESS.value,
        )
        await self._audit(
            actor,
            review_id,
            "rob_assessment",
            assessment.id,
            "ROB_ASSESSMENT_CREATED" if revision == 1 else "ROB_ASSESSMENT_CORRECTED",
            None,
            {
                "study_id": str(study.id),
                "instrument_version_id": str(version.id),
                "round": round_number,
                "revision": revision,
                "supersedes_assessment_id": (
                    str(supersedes_assessment_id) if supersedes_assessment_id else None
                ),
            },
        )
        return assessment

    async def get_assessment(
        self, actor: ActorContext, *, review_id: UUID, assessment_id: UUID
    ) -> RiskOfBiasAssessment:
        await self._reviews.get(actor, review_id)
        return await self._assessment(actor, review_id, assessment_id, own=False)

    async def list_assessments(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[RiskOfBiasAssessment]:
        await self._reviews.get(actor, review_id)
        if actor.has_permission(Permission.ADJUDICATE_ROB):
            return await self._repository.list_assessments(actor.organization_id, review_id)
        if actor.has_permission(Permission.PERFORM_ROB_ASSESSMENT):
            return await self._repository.list_assessments(
                actor.organization_id, review_id, assessor_user_id=actor.user_id
            )
        comparisons = await self._repository.list_comparisons(actor.organization_id, review_id)
        revealed_ids = {
            assessment_id
            for item in comparisons
            for assessment_id in (item.assessment_a_id, item.assessment_b_id)
        }
        assessments = await self._repository.list_assessments(actor.organization_id, review_id)
        return [item for item in assessments if item.id in revealed_ids]

    async def save_answer(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        question_key: str,
        answer: str,
        rationale: str | None,
        evidence_location_id: UUID | None,
    ) -> RiskOfBiasAssessment:
        assessment, version = await self._editable(actor, review_id, assessment_id)
        question = self._question(version.definition, question_key)
        normalized_answer = self._key(answer)
        if normalized_answer not in question["allowed_answers"]:
            raise ConflictError("answer is not allowed by the pinned instrument version")
        await self._validate_evidence(actor, assessment, evidence_location_id)
        before = assessment_snapshot(assessment)
        updated = await self._repository.save_answer(
            assessment=assessment,
            question_key=question["key"],
            answer=normalized_answer,
            rationale=self._optional(rationale),
            evidence_location_id=evidence_location_id,
        )
        await self._scientific_write(
            actor,
            updated,
            "rob_answer",
            next(item.id for item in updated.answers if item.question_key == question["key"]),
            "ROB_ANSWER_RECORDED",
            before,
            assessment_snapshot(updated),
            evidence_location_id,
        )
        return updated

    async def save_domain_judgment(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        domain_key: str,
        final_judgment: str,
        rationale: str,
        override_reason: str | None,
        evidence_location_id: UUID | None,
    ) -> RiskOfBiasAssessment:
        assessment, version = await self._editable(actor, review_id, assessment_id)
        domain = self._domain(version.definition, domain_key)
        final = self._key(final_judgment)
        choices = {item["value"] for item in version.definition["domain_judgment_choices"]}
        if final not in choices:
            raise ConflictError("domain judgment is not allowed by the pinned instrument version")
        suggested = suggest_domain_judgment(
            version.definition,
            domain["key"],
            {item.question_key: item.answer for item in assessment.answers},
        )
        if suggested is not None and suggested != final and not self._optional(override_reason):
            raise ConflictError("overriding a deterministic suggestion requires a reason")
        await self._validate_evidence(actor, assessment, evidence_location_id)
        before = assessment_snapshot(assessment)
        updated = await self._repository.save_domain_judgment(
            assessment=assessment,
            domain_key=domain["key"],
            suggested_judgment=suggested,
            final_judgment=final,
            rationale=self._required(rationale, "domain rationale"),
            override_reason=self._optional(override_reason),
            evidence_location_id=evidence_location_id,
        )
        await self._scientific_write(
            actor,
            updated,
            "rob_domain_judgment",
            next(item.id for item in updated.domain_judgments if item.domain_key == domain["key"]),
            "ROB_DOMAIN_JUDGMENT_RECORDED",
            before,
            assessment_snapshot(updated),
            evidence_location_id,
        )
        return updated

    async def save_overall(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        final_judgment: str,
        rationale: str,
        override_reason: str | None,
        evidence_location_id: UUID | None,
    ) -> RiskOfBiasAssessment:
        assessment, version = await self._editable(actor, review_id, assessment_id)
        final = self._key(final_judgment)
        choices = {item["value"] for item in version.definition["overall_judgment_choices"]}
        if final not in choices:
            raise ConflictError("overall judgment is not allowed by the pinned instrument version")
        suggested = suggest_overall_judgment(
            version.definition,
            {item.domain_key: item.final_judgment for item in assessment.domain_judgments},
        )
        if suggested is not None and suggested != final and not self._optional(override_reason):
            raise ConflictError("overriding a deterministic suggestion requires a reason")
        await self._validate_evidence(actor, assessment, evidence_location_id)
        before = assessment_snapshot(assessment)
        updated = await self._repository.save_overall(
            assessment=assessment,
            overall_suggested_judgment=suggested,
            overall_final_judgment=final,
            overall_rationale=self._required(rationale, "overall rationale"),
            overall_override_reason=self._optional(override_reason),
            overall_evidence_location_id=evidence_location_id,
        )
        await self._scientific_write(
            actor,
            updated,
            "rob_assessment",
            updated.id,
            "ROB_OVERALL_JUDGMENT_RECORDED",
            before,
            assessment_snapshot(updated),
            evidence_location_id,
        )
        return updated

    async def submit(
        self, actor: ActorContext, *, review_id: UUID, assessment_id: UUID
    ) -> RiskOfBiasAssessment:
        assessment, version = await self._editable(actor, review_id, assessment_id)
        required_questions = {
            question["key"]
            for domain in version.definition["domains"]
            for question in domain["questions"]
            if question["required"]
        }
        if not required_questions <= {item.question_key for item in assessment.answers}:
            raise ConflictError("all required signalling questions must be answered")
        if {item["key"] for item in version.definition["domains"]} != {
            item.domain_key for item in assessment.domain_judgments
        }:
            raise ConflictError("every domain requires a final judgment")
        answers = {item.question_key: item.answer for item in assessment.answers}
        for domain in assessment.domain_judgments:
            current_suggestion = suggest_domain_judgment(
                version.definition, domain.domain_key, answers
            )
            if current_suggestion != domain.suggested_judgment:
                raise ConflictError(
                    "signalling answers changed; resave affected domain judgments before submission"
                )
        if assessment.overall_final_judgment is None or assessment.overall_rationale is None:
            raise ConflictError("overall judgment and rationale are required")
        current_overall_suggestion = suggest_overall_judgment(
            version.definition,
            {item.domain_key: item.final_judgment for item in assessment.domain_judgments},
        )
        if current_overall_suggestion != assessment.overall_suggested_judgment:
            raise ConflictError(
                "domain judgments changed; resave the overall judgment before submission"
            )
        before = assessment_snapshot(assessment)
        submitted = await self._repository.submit_assessment(assessment)
        await self._scientific_write(
            actor,
            submitted,
            "rob_assessment",
            submitted.id,
            "ROB_ASSESSMENT_SUBMITTED",
            before,
            assessment_snapshot(submitted),
            None,
            VerificationState.HUMAN_VERIFIED,
        )
        return submitted

    async def compare(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_a_id: UUID,
        assessment_b_id: UUID,
    ) -> RiskOfBiasComparison:
        AuthorizationService.require(actor, Permission.ADJUDICATE_ROB)
        await self._reviews.get(actor, review_id)
        if assessment_a_id == assessment_b_id:
            raise ConflictError("comparison requires two different assessments")
        assessment_a = await self._raw_assessment(actor, review_id, assessment_a_id)
        assessment_b = await self._raw_assessment(actor, review_id, assessment_b_id)
        all_assessments = await self._repository.list_assessments(actor.organization_id, review_id)
        superseded_ids = {
            item.supersedes_assessment_id
            for item in all_assessments
            if item.supersedes_assessment_id is not None
        }
        if assessment_a.id in superseded_ids or assessment_b.id in superseded_ids:
            raise ConflictError("only the current assessment revision can be compared")
        if (
            assessment_a.status != AssessmentStatus.SUBMITTED
            or assessment_b.status != AssessmentStatus.SUBMITTED
        ):
            raise ConflictError("only submitted assessments can be compared")
        if assessment_a.assessor_user_id == assessment_b.assessor_user_id:
            raise ConflictError("comparison requires independent assessors")
        if (
            assessment_a.study_id,
            assessment_a.instrument_version_id,
            assessment_a.round_number,
        ) != (
            assessment_b.study_id,
            assessment_b.instrument_version_id,
            assessment_b.round_number,
        ):
            raise ConflictError("assessments must share Study, instrument version, and round")
        first, second = sorted((assessment_a, assessment_b), key=lambda item: str(item.id))
        existing = await self._repository.get_comparison_for_pair(
            actor.organization_id, review_id, first.id, second.id
        )
        if existing is not None:
            return existing
        differences = compare_assessment_snapshots(first, second)
        comparison = await self._repository.create_comparison(
            organization_id=actor.organization_id,
            review_id=review_id,
            study_id=first.study_id,
            instrument_version_id=first.instrument_version_id,
            round_number=first.round_number,
            assessment_a_id=first.id,
            assessment_b_id=second.id,
            status=(ComparisonStatus.CONFLICT if differences else ComparisonStatus.AGREEMENT).value,
            differences=list(differences),
            compared_by_user_id=actor.user_id,
        )
        await self._scientific_write(
            actor,
            first,
            "rob_comparison",
            comparison.id,
            "ROB_CONFLICT_CREATED" if differences else "ROB_AGREEMENT_RECORDED",
            None,
            {"status": comparison.status.value, "differences": list(differences)},
            None,
        )
        return comparison

    async def list_comparisons(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[RiskOfBiasComparison]:
        await self._reviews.get(actor, review_id)
        return await self._repository.list_comparisons(actor.organization_id, review_id)

    async def adjudicate(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        comparison_id: UUID,
        resolution_assessment_id: UUID,
        rationale: str,
        evidence_location_id: UUID | None,
    ) -> RiskOfBiasComparison:
        AuthorizationService.require(actor, Permission.ADJUDICATE_ROB)
        await self._reviews.get(actor, review_id)
        comparison = await self._repository.get_comparison(
            actor.organization_id, review_id, comparison_id
        )
        if comparison is None:
            raise ResourceNotFoundError("Risk of Bias comparison was not found")
        if comparison.status != ComparisonStatus.CONFLICT:
            raise ConflictError("only an unresolved conflict can be adjudicated")
        if resolution_assessment_id not in (
            comparison.assessment_a_id,
            comparison.assessment_b_id,
        ):
            raise ConflictError("resolution must preserve one submitted scientific assessment")
        selected = await self._raw_assessment(actor, review_id, resolution_assessment_id)
        await self._validate_evidence(actor, selected, evidence_location_id)
        resolved = await self._repository.adjudicate(
            comparison=comparison,
            final_snapshot=assessment_snapshot(selected),
            rationale=self._required(rationale, "adjudication rationale"),
            evidence_location_id=evidence_location_id,
            adjudicated_by_user_id=actor.user_id,
        )
        await self._scientific_write(
            actor,
            selected,
            "rob_comparison",
            comparison.id,
            "ROB_ADJUDICATED",
            {"status": comparison.status.value, "differences": list(comparison.differences)},
            {
                "status": resolved.status.value,
                "resolution_assessment_id": str(resolution_assessment_id),
                "final_snapshot": resolved.adjudicated_snapshot,
            },
            evidence_location_id,
            VerificationState.HUMAN_VERIFIED,
        )
        return resolved

    async def _editable(
        self, actor: ActorContext, review_id: UUID, assessment_id: UUID
    ) -> tuple[RiskOfBiasAssessment, RiskOfBiasInstrumentVersion]:
        AuthorizationService.require(actor, Permission.PERFORM_ROB_ASSESSMENT)
        await self._reviews.get(actor, review_id)
        assessment = await self._assessment(actor, review_id, assessment_id, own=True)
        if assessment.status != AssessmentStatus.IN_PROGRESS:
            raise ConflictError("submitted assessments are immutable; create a correction")
        return assessment, await self._version(actor, review_id, assessment.instrument_version_id)

    async def _assessment(
        self, actor: ActorContext, review_id: UUID, assessment_id: UUID, *, own: bool
    ) -> RiskOfBiasAssessment:
        assessment = await self._raw_assessment(actor, review_id, assessment_id)
        can_reveal = actor.has_permission(Permission.ADJUDICATE_ROB)
        if assessment.assessor_user_id != actor.user_id and (own or not can_reveal):
            if own or actor.has_permission(Permission.PERFORM_ROB_ASSESSMENT):
                raise ResourceNotFoundError("Risk of Bias assessment was not found")
            comparisons = await self._repository.list_comparisons(actor.organization_id, review_id)
            if not any(
                assessment.id in (item.assessment_a_id, item.assessment_b_id)
                for item in comparisons
            ):
                raise ResourceNotFoundError("Risk of Bias assessment was not found")
        return assessment

    async def _raw_assessment(
        self, actor: ActorContext, review_id: UUID, assessment_id: UUID
    ) -> RiskOfBiasAssessment:
        assessment = await self._repository.get_assessment(
            actor.organization_id, review_id, assessment_id
        )
        if assessment is None:
            raise ResourceNotFoundError("Risk of Bias assessment was not found")
        return assessment

    async def _instrument(
        self, actor: ActorContext, review_id: UUID, instrument_id: UUID
    ) -> RiskOfBiasInstrument:
        instrument = await self._repository.get_instrument(
            actor.organization_id, review_id, instrument_id
        )
        if instrument is None:
            raise ResourceNotFoundError("Risk of Bias instrument was not found")
        return instrument

    async def _version(
        self, actor: ActorContext, review_id: UUID, version_id: UUID
    ) -> RiskOfBiasInstrumentVersion:
        version = await self._repository.get_version(actor.organization_id, review_id, version_id)
        if version is None:
            raise ResourceNotFoundError("Risk of Bias instrument version was not found")
        return version

    async def _validate_evidence(
        self,
        actor: ActorContext,
        assessment: RiskOfBiasAssessment,
        evidence_location_id: UUID | None,
    ) -> None:
        if evidence_location_id is None:
            return
        article_id = await self._repository.get_evidence_article(
            actor.organization_id, assessment.review_id, evidence_location_id
        )
        if article_id is None:
            raise ResourceNotFoundError("evidence location was not found")
        if not await self._studies.article_linked(
            actor.organization_id, assessment.review_id, assessment.study_id, article_id
        ):
            raise ConflictError("evidence Article is not linked to the assessment Study")

    async def _scientific_write(
        self,
        actor: ActorContext,
        assessment: RiskOfBiasAssessment,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        evidence_location_id: UUID | None,
        verification_state: VerificationState = VerificationState.UNVERIFIED,
    ) -> None:
        await self._provenance.record_provenance(
            actor,
            review_id=assessment.review_id,
            subject_type=entity_type,
            subject_id=entity_id,
            source_type="document_evidence_location" if evidence_location_id else None,
            source_id=evidence_location_id,
            source_locator={
                "study_id": str(assessment.study_id),
                "instrument_version_id": str(assessment.instrument_version_id),
            },
            method_name="structured_human_risk_of_bias",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=verification_state,
        )
        await self._audit(
            actor,
            assessment.review_id,
            entity_type,
            entity_id,
            action,
            before,
            after,
        )

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        reason: str | None = None,
    ) -> None:
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_snapshot=before,
            after_snapshot=after,
            reason=reason,
        )

    @staticmethod
    def _question(definition: dict[str, Any], question_key: str) -> dict[str, Any]:
        key = RiskOfBiasService._key(question_key)
        for domain in definition["domains"]:
            for question in domain["questions"]:
                if question["key"] == key:
                    return cast(dict[str, Any], question)
        raise ConflictError("signalling question is not defined by the pinned instrument version")

    @staticmethod
    def _domain(definition: dict[str, Any], domain_key: str) -> dict[str, Any]:
        key = RiskOfBiasService._key(domain_key)
        for domain in definition["domains"]:
            if domain["key"] == key:
                return cast(dict[str, Any], domain)
        raise ConflictError("domain is not defined by the pinned instrument version")

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
