from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.outcomes.contracts import OutcomeRepository
from backend.app.outcomes.domain import (
    CALCULATION_VERSION,
    HARMONIZATION_VERSION,
    READINESS_VERSION,
    AdjustmentStatus,
    AnalysisPopulation,
    AnalysisReadinessSnapshot,
    Directionality,
    DirectionTransformation,
    EffectEstimate,
    EffectMeasure,
    EstimateOrigin,
    MappingMethod,
    MeasurementScale,
    OutcomeDefinition,
    OutcomeDefinitionVersion,
    OutcomeMapping,
    SynthesisCandidateSet,
    TimeAnchor,
    TimepointWindow,
    TimeUnit,
    UnitDefinition,
    VarianceScale,
    ZeroEventPattern,
    apply_direction,
    convert_unit,
    derive_effect,
    normalize_outcome_definition,
    normalize_time_to_days,
    readiness_blockers,
    readiness_status,
)
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.studies.contracts import StudyRepository


class OutcomeService:
    def __init__(
        self,
        repository: OutcomeRepository,
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

    async def create_outcome(
        self, actor: ActorContext, *, review_id: UUID, key: str
    ) -> OutcomeDefinition:
        AuthorizationService.require(actor, Permission.MANAGE_OUTCOMES)
        review = await self._reviews.get(actor, review_id)
        normalized = self._key(key)
        if any(
            item.key == normalized
            for item in await self._repository.list_outcomes(actor.organization_id, review.id)
        ):
            raise ConflictError("outcome key already exists")
        item = await self._repository.create_outcome(
            organization_id=actor.organization_id,
            review_id=review.id,
            key=normalized,
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review.id,
            "outcome_definition",
            item.id,
            "OUTCOME_DEFINITION_CREATED",
            {"key": item.key},
            source_type=None,
            source_id=None,
            method="manual_outcome_definition",
        )
        return item

    async def create_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        outcome_id: UUID,
        definition: dict[str, Any],
        protocol_version_id: UUID | None,
    ) -> OutcomeDefinitionVersion:
        AuthorizationService.require(actor, Permission.MANAGE_OUTCOMES)
        await self._reviews.get(actor, review_id)
        await self._outcome(actor, review_id, outcome_id)
        try:
            normalized = normalize_outcome_definition(definition)
        except (ValueError, KeyError) as exc:
            raise ConflictError(str(exc)) from exc
        if protocol_version_id is not None and not await self._repository.protocol_version_exists(
            actor.organization_id, review_id, protocol_version_id
        ):
            raise ResourceNotFoundError("protocol version was not found")
        await self._validate_definition_references(actor, review_id, normalized)
        encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
        item = await self._repository.create_outcome_version(
            outcome_id=outcome_id,
            organization_id=actor.organization_id,
            review_id=review_id,
            definition=normalized,
            content_hash=hashlib.sha256(encoded).hexdigest(),
            protocol_version_id=protocol_version_id,
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "outcome_definition_version",
            item.id,
            "OUTCOME_VERSION_CREATED",
            {
                "outcome_id": str(outcome_id),
                "version": item.version,
                "content_hash": item.content_hash,
            },
            source_type="protocol_version" if protocol_version_id else None,
            source_id=protocol_version_id,
            method="versioned_outcome_definition",
        )
        return item

    async def list_outcomes(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[tuple[OutcomeDefinition, list[OutcomeDefinitionVersion]]]:
        await self._reviews.get(actor, review_id)
        outcomes = await self._repository.list_outcomes(actor.organization_id, review_id)
        return [
            (
                item,
                await self._repository.list_outcome_versions(
                    actor.organization_id, review_id, item.id
                ),
            )
            for item in outcomes
        ]

    async def create_timepoint_window(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        key: str,
        label: str,
        anchor: TimeAnchor,
        minimum_days: Decimal | None,
        maximum_days: Decimal | None,
        rule_version: str,
    ) -> TimepointWindow:
        AuthorizationService.require(actor, Permission.MANAGE_OUTCOMES)
        await self._reviews.get(actor, review_id)
        if minimum_days is not None and minimum_days < 0:
            raise ConflictError("minimum days cannot be negative")
        if maximum_days is not None and maximum_days < 0:
            raise ConflictError("maximum days cannot be negative")
        if minimum_days is not None and maximum_days is not None and minimum_days > maximum_days:
            raise ConflictError("timepoint window minimum cannot exceed maximum")
        item = await self._repository.create_timepoint_window(
            organization_id=actor.organization_id,
            review_id=review_id,
            key=self._key(key),
            label=self._required(label, "timepoint label"),
            anchor=anchor.value,
            minimum_days=minimum_days,
            maximum_days=maximum_days,
            rule_version=self._required(rule_version, "timepoint rule version"),
            created_by_user_id=actor.user_id,
        )
        await self._audit_config(
            actor, review_id, "timepoint_window", item.id, "TIMEPOINT_WINDOW_CREATED"
        )
        return item

    async def create_unit(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        key: str,
        label: str,
        dimension: str,
        context_key: str,
        base_unit_key: str,
        multiplier_to_base: Decimal,
        offset_to_base: Decimal,
        precision: int,
        rule_version: str,
    ) -> UnitDefinition:
        AuthorizationService.require(actor, Permission.MANAGE_OUTCOMES)
        await self._reviews.get(actor, review_id)
        if multiplier_to_base <= 0 or not 0 <= precision <= 18:
            raise ConflictError("unit multiplier and precision are invalid")
        item = await self._repository.create_unit(
            organization_id=actor.organization_id,
            review_id=review_id,
            key=self._key(key),
            label=self._required(label, "unit label"),
            dimension=self._key(dimension),
            context_key=self._key(context_key),
            base_unit_key=self._key(base_unit_key),
            multiplier_to_base=multiplier_to_base,
            offset_to_base=offset_to_base,
            precision=precision,
            rule_version=self._required(rule_version, "unit rule version"),
            created_by_user_id=actor.user_id,
        )
        await self._audit_config(
            actor, review_id, "unit_definition", item.id, "UNIT_DEFINITION_CREATED"
        )
        return item

    async def create_scale(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        key: str,
        name: str,
        minimum: Decimal | None,
        maximum: Decimal | None,
        directionality: Directionality,
    ) -> MeasurementScale:
        AuthorizationService.require(actor, Permission.MANAGE_OUTCOMES)
        await self._reviews.get(actor, review_id)
        if minimum is not None and maximum is not None and minimum >= maximum:
            raise ConflictError("measurement scale minimum must be below maximum")
        item = await self._repository.create_scale(
            organization_id=actor.organization_id,
            review_id=review_id,
            key=self._key(key),
            name=self._required(name, "scale name"),
            minimum=minimum,
            maximum=maximum,
            directionality=directionality.value,
            created_by_user_id=actor.user_id,
        )
        await self._audit_config(
            actor, review_id, "measurement_scale", item.id, "MEASUREMENT_SCALE_CREATED"
        )
        return item

    async def list_configuration(
        self, actor: ActorContext, *, review_id: UUID
    ) -> tuple[list[TimepointWindow], list[UnitDefinition], list[MeasurementScale]]:
        await self._reviews.get(actor, review_id)
        return (
            await self._repository.list_timepoint_windows(actor.organization_id, review_id),
            await self._repository.list_units(actor.organization_id, review_id),
            await self._repository.list_scales(actor.organization_id, review_id),
        )

    async def create_mapping(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        study_id: UUID,
        extraction_value_id: UUID,
        outcome_version_id: UUID,
        method: MappingMethod,
        rationale: str,
        confidence: Decimal | None,
        reported_unit_id: UUID | None,
        normalized_unit_id: UUID | None,
        reported_time_value: Decimal | None,
        reported_time_unit: TimeUnit | None,
        reported_time_anchor: TimeAnchor | None,
        timepoint_window_id: UUID | None,
        measurement_scale_id: UUID | None,
        direction_transformation: DirectionTransformation,
        transformation_reason: str | None,
        supersedes_mapping_id: UUID | None,
    ) -> OutcomeMapping:
        AuthorizationService.require(actor, Permission.HARMONIZE_OUTCOMES)
        await self._reviews.get(actor, review_id)
        study = await self._studies.get_study(actor.organization_id, review_id, study_id)
        if study is None:
            raise ResourceNotFoundError("study was not found")
        version = await self._version(actor, review_id, outcome_version_id)
        context = await self._repository.extraction_value_context(
            actor.organization_id, review_id, extraction_value_id
        )
        if context is None:
            raise ResourceNotFoundError("extraction value was not found")
        if context["study_id"] != study_id:
            raise ConflictError("extraction value does not belong to the mapped Study")
        if confidence is not None and not Decimal("0") <= confidence <= Decimal("1"):
            raise ConflictError("mapping confidence must be between zero and one")
        if len(
            [
                item
                for item in (reported_time_value, reported_time_unit, reported_time_anchor)
                if item is not None
            ]
        ) not in (0, 3):
            raise ConflictError("reported time value, unit, and anchor must be recorded together")
        if direction_transformation == DirectionTransformation.SIGN_REVERSED and not self._optional(
            transformation_reason
        ):
            raise ConflictError("sign reversal requires a scientific reason")
        if supersedes_mapping_id is not None:
            prior = await self._mapping(actor, review_id, supersedes_mapping_id)
            if prior.study_id != study_id or prior.extraction_value_id != extraction_value_id:
                raise ConflictError("mapping correction must preserve Study and extraction source")
        reported_value = self._decimal_or_none(context["reported_value"])
        source_unit = await self._optional_unit(actor, review_id, reported_unit_id)
        target_unit = await self._optional_unit(actor, review_id, normalized_unit_id)
        normalized_value = reported_value
        conversion_version: str | None = None
        if target_unit is not None:
            if source_unit is None or reported_value is None:
                raise ConflictError(
                    "unit conversion requires a numeric value and structured reported unit"
                )
            try:
                normalized_value = convert_unit(reported_value, source_unit, target_unit)
            except ValueError as exc:
                raise ConflictError(str(exc)) from exc
            conversion_version = f"{source_unit.rule_version}->{target_unit.rule_version}"
        if normalized_value is not None:
            normalized_value = apply_direction(normalized_value, direction_transformation)
        window = await self._optional_window(actor, review_id, timepoint_window_id)
        normalized_days: Decimal | None = None
        if reported_time_value is not None and reported_time_unit is not None:
            try:
                normalized_days = normalize_time_to_days(reported_time_value, reported_time_unit)
            except ValueError as exc:
                raise ConflictError(str(exc)) from exc
        if window is not None:
            if normalized_days is None:
                raise ConflictError("timepoint mapping requires an original reported time")
            if window.minimum_days is not None and normalized_days < Decimal(window.minimum_days):
                raise ConflictError("reported timepoint is outside the selected canonical window")
            if window.maximum_days is not None and normalized_days > Decimal(window.maximum_days):
                raise ConflictError("reported timepoint is outside the selected canonical window")
            if window.anchor != reported_time_anchor:
                raise ConflictError("reported timepoint anchor does not match the canonical window")
        scale = await self._optional_scale(actor, review_id, measurement_scale_id)
        self._validate_mapping_against_definition(
            version, target_unit or source_unit, window, scale
        )
        item = await self._repository.create_mapping(
            organization_id=actor.organization_id,
            review_id=review_id,
            study_id=study_id,
            extraction_value_id=extraction_value_id,
            outcome_version_id=outcome_version_id,
            method=method.value,
            rationale=self._required(rationale, "mapping rationale"),
            confidence=confidence,
            reported_value=reported_value,
            reported_unit=context["reported_unit"],
            reported_unit_id=reported_unit_id,
            normalized_value=normalized_value,
            normalized_unit_id=normalized_unit_id,
            conversion_rule_version=conversion_version,
            reported_time_value=reported_time_value,
            reported_time_unit=reported_time_unit.value if reported_time_unit else None,
            reported_time_anchor=reported_time_anchor.value if reported_time_anchor else None,
            normalized_time_days=normalized_days,
            timepoint_window_id=timepoint_window_id,
            timepoint_rule_version=window.rule_version if window else None,
            measurement_scale_id=measurement_scale_id,
            direction_transformation=direction_transformation.value,
            transformation_reason=self._optional(transformation_reason),
            extraction_verified=bool(context["verified"]),
            supersedes_mapping_id=supersedes_mapping_id,
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "outcome_mapping",
            item.id,
            "OUTCOME_MAPPED",
            self._mapping_snapshot(item),
            source_type="extraction_value",
            source_id=extraction_value_id,
            method=method.value,
            verification_state=(
                VerificationState.HUMAN_VERIFIED
                if item.extraction_verified
                else VerificationState.UNVERIFIED
            ),
        )
        if window is not None:
            await self._audit(
                actor,
                review_id,
                "outcome_mapping",
                item.id,
                "TIMEPOINT_HARMONIZED",
                {"normalized_time_days": item.normalized_time_days, "window_id": str(window.id)},
            )
        if conversion_version is not None:
            await self._audit(
                actor,
                review_id,
                "outcome_mapping",
                item.id,
                "UNIT_CONVERTED",
                {
                    "reported_value": item.reported_value,
                    "normalized_value": item.normalized_value,
                    "rule_version": conversion_version,
                },
            )
        return item

    async def list_mappings(self, actor: ActorContext, *, review_id: UUID) -> list[OutcomeMapping]:
        await self._reviews.get(actor, review_id)
        return await self._repository.list_mappings(actor.organization_id, review_id)

    async def create_effect_estimate(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        study_id: UUID,
        outcome_version_id: UUID,
        effect_measure: EffectMeasure,
        origin: EstimateOrigin,
        estimate: Decimal | None,
        standard_error: Decimal | None,
        variance: Decimal | None,
        variance_scale: VarianceScale | None,
        ci_lower: Decimal | None,
        ci_upper: Decimal | None,
        confidence_level: Decimal | None,
        adjustment: AdjustmentStatus,
        analysis_population: AnalysisPopulation,
        covariates: str | None,
        model_description: str | None,
        timepoint_window_id: UUID | None,
        unit_id: UUID | None,
        measurement_scale_id: UUID | None,
        components: dict[str, Decimal],
        source_mapping_ids: list[UUID],
        source_evidence_location_id: UUID | None,
    ) -> EffectEstimate:
        AuthorizationService.require(actor, Permission.HARMONIZE_OUTCOMES)
        await self._reviews.get(actor, review_id)
        if await self._studies.get_study(actor.organization_id, review_id, study_id) is None:
            raise ResourceNotFoundError("study was not found")
        version = await self._version(actor, review_id, outcome_version_id)
        if effect_measure.value not in version.definition["compatible_effect_measures"]:
            raise ConflictError("effect measure is incompatible with the canonical outcome version")
        if not source_mapping_ids or len(source_mapping_ids) != len(set(source_mapping_ids)):
            raise ConflictError("effect estimate requires unique source mappings")
        mappings = [await self._mapping(actor, review_id, item) for item in source_mapping_ids]
        if any(
            item.study_id != study_id or item.outcome_version_id != outcome_version_id
            for item in mappings
        ):
            raise ConflictError("effect sources must share the estimate Study and outcome version")
        window = await self._optional_window(actor, review_id, timepoint_window_id)
        unit = await self._optional_unit(actor, review_id, unit_id)
        scale = await self._optional_scale(actor, review_id, measurement_scale_id)
        self._validate_mapping_against_definition(version, unit, window, scale)
        await self._validate_evidence(actor, review_id, study_id, source_evidence_location_id)
        if adjustment == AdjustmentStatus.ADJUSTED and not self._optional(model_description):
            raise ConflictError("adjusted estimates require a model description")
        if (ci_lower is None) != (ci_upper is None):
            raise ConflictError("both confidence interval bounds must be supplied together")
        if ci_lower is not None and ci_upper is not None and ci_lower > ci_upper:
            raise ConflictError("confidence interval lower bound cannot exceed upper bound")
        if standard_error is not None and standard_error < 0:
            raise ConflictError("standard error cannot be negative")
        if variance is not None and variance < 0:
            raise ConflictError("variance cannot be negative")
        if (
            standard_error is not None
            and variance is not None
            and abs(standard_error**2 - variance) > Decimal("0.000000000001")
        ):
            raise ConflictError("standard error and variance are inconsistent")
        if effect_measure in (EffectMeasure.RR, EffectMeasure.OR, EffectMeasure.HR):
            if estimate is not None and estimate <= 0:
                raise ConflictError("ratio effect estimates must be positive")
            if ci_lower is not None and ci_lower <= 0:
                raise ConflictError("ratio confidence intervals must be positive")
        zero_pattern = ZeroEventPattern.NONE
        calculation_version: str | None = None
        if origin == EstimateOrigin.DERIVED:
            try:
                estimate, standard_error, variance, zero_pattern = derive_effect(
                    effect_measure, components
                )
            except ValueError as exc:
                raise ConflictError(str(exc)) from exc
            calculation_version = CALCULATION_VERSION
            variance_scale = (
                VarianceScale.LOG
                if effect_measure in (EffectMeasure.RR, EffectMeasure.OR)
                else VarianceScale.NATURAL
            )
        elif estimate is None:
            raise ConflictError("reported effect estimate requires an estimate value")
        elif variance_scale is None:
            raise ConflictError("reported estimate requires an explicit variance scale")
        item = await self._repository.create_effect_estimate(
            organization_id=actor.organization_id,
            review_id=review_id,
            study_id=study_id,
            outcome_version_id=outcome_version_id,
            effect_measure=effect_measure.value,
            origin=origin.value,
            estimate=estimate,
            standard_error=standard_error,
            variance=variance,
            variance_scale=variance_scale.value,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=confidence_level,
            adjustment=adjustment.value,
            analysis_population=analysis_population.value,
            covariates=self._optional(covariates),
            model_description=self._optional(model_description),
            timepoint_window_id=timepoint_window_id,
            unit_id=unit_id,
            measurement_scale_id=measurement_scale_id,
            components={key: str(value) for key, value in sorted(components.items())},
            source_mapping_ids=[str(item) for item in sorted(source_mapping_ids, key=str)],
            source_evidence_location_id=source_evidence_location_id,
            calculation_version=calculation_version,
            zero_event_pattern=zero_pattern.value,
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "effect_estimate",
            item.id,
            "EFFECT_ESTIMATE_DERIVED"
            if origin == EstimateOrigin.DERIVED
            else "EFFECT_ESTIMATE_CREATED",
            self._estimate_snapshot(item),
            source_type="document_evidence_location"
            if source_evidence_location_id
            else "outcome_mapping",
            source_id=source_evidence_location_id or source_mapping_ids[0],
            method=calculation_version or "structured_reported_effect",
            verification_state=(
                VerificationState.HUMAN_VERIFIED
                if all(mapping.extraction_verified for mapping in mappings)
                else VerificationState.UNVERIFIED
            ),
        )
        return item

    async def list_effect_estimates(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[EffectEstimate]:
        await self._reviews.get(actor, review_id)
        return await self._repository.list_effect_estimates(actor.organization_id, review_id)

    async def create_candidate_set(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        outcome_version_id: UUID,
        effect_measure: EffectMeasure,
        timepoint_window_id: UUID | None,
        population_label: str | None,
        estimate_ids: list[UUID],
    ) -> SynthesisCandidateSet:
        AuthorizationService.require(actor, Permission.PREPARE_SYNTHESIS)
        await self._reviews.get(actor, review_id)
        await self._version(actor, review_id, outcome_version_id)
        await self._optional_window(actor, review_id, timepoint_window_id)
        if not estimate_ids or len(estimate_ids) != len(set(estimate_ids)):
            raise ConflictError("candidate set requires unique effect estimates")
        for estimate_id in estimate_ids:
            await self._estimate(actor, review_id, estimate_id)
        item = await self._repository.create_candidate_set(
            organization_id=actor.organization_id,
            review_id=review_id,
            outcome_version_id=outcome_version_id,
            effect_measure=effect_measure.value,
            timepoint_window_id=timepoint_window_id,
            population_label=self._optional(population_label),
            estimate_ids=[str(item) for item in sorted(estimate_ids, key=str)],
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            "synthesis_candidate_set",
            item.id,
            "SYNTHESIS_CANDIDATE_SET_CREATED",
            {"estimate_ids": [str(value) for value in item.estimate_ids]},
        )
        return item

    async def evaluate_readiness(
        self, actor: ActorContext, *, review_id: UUID, candidate_set_id: UUID
    ) -> AnalysisReadinessSnapshot:
        AuthorizationService.require(actor, Permission.PREPARE_SYNTHESIS)
        await self._reviews.get(actor, review_id)
        candidate = await self._candidate(actor, review_id, candidate_set_id)
        outcome = await self._version(actor, review_id, candidate.outcome_version_id)
        estimates = [
            await self._estimate(actor, review_id, item) for item in candidate.estimate_ids
        ]
        all_mappings = await self._repository.list_mappings(actor.organization_id, review_id)
        mappings = {item.id: item for item in all_mappings}
        scales = {
            item.id: item
            for item in await self._repository.list_scales(actor.organization_id, review_id)
        }
        blockers = readiness_blockers(candidate, outcome, estimates, mappings, scales)
        item = await self._repository.create_readiness_snapshot(
            organization_id=actor.organization_id,
            review_id=review_id,
            candidate_set_id=candidate.id,
            algorithm_version=READINESS_VERSION,
            status=readiness_status(blockers).value,
            blockers=list(blockers),
            evaluated_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "analysis_readiness_snapshot",
            item.id,
            "ANALYSIS_READINESS_EVALUATED",
            {
                "candidate_set_id": str(candidate.id),
                "status": item.status.value,
                "blockers": list(item.blockers),
            },
            source_type="synthesis_candidate_set",
            source_id=candidate.id,
            method=READINESS_VERSION,
        )
        return item

    async def list_candidates(
        self, actor: ActorContext, *, review_id: UUID
    ) -> tuple[list[SynthesisCandidateSet], list[AnalysisReadinessSnapshot]]:
        await self._reviews.get(actor, review_id)
        return (
            await self._repository.list_candidate_sets(actor.organization_id, review_id),
            await self._repository.list_readiness_snapshots(actor.organization_id, review_id),
        )

    async def _validate_definition_references(
        self, actor: ActorContext, review_id: UUID, definition: dict[str, Any]
    ) -> None:
        for value in definition["allowed_unit_ids"]:
            if (
                await self._repository.get_unit(actor.organization_id, review_id, UUID(value))
                is None
            ):
                raise ResourceNotFoundError("allowed unit was not found")
        for value in definition["allowed_scale_ids"]:
            if (
                await self._repository.get_scale(actor.organization_id, review_id, UUID(value))
                is None
            ):
                raise ResourceNotFoundError("allowed measurement scale was not found")
        for value in definition["expected_timepoint_window_ids"]:
            if (
                await self._repository.get_timepoint_window(
                    actor.organization_id, review_id, UUID(value)
                )
                is None
            ):
                raise ResourceNotFoundError("expected timepoint window was not found")

    @staticmethod
    def _validate_mapping_against_definition(
        version: OutcomeDefinitionVersion,
        unit: UnitDefinition | None,
        window: TimepointWindow | None,
        scale: MeasurementScale | None,
    ) -> None:
        definition = version.definition
        if (
            unit is not None
            and definition["allowed_unit_ids"]
            and str(unit.id) not in definition["allowed_unit_ids"]
        ):
            raise ConflictError("unit is not permitted by the canonical outcome version")
        if (
            window is not None
            and definition["expected_timepoint_window_ids"]
            and str(window.id) not in definition["expected_timepoint_window_ids"]
        ):
            raise ConflictError(
                "timepoint window is not permitted by the canonical outcome version"
            )
        if (
            scale is not None
            and definition["allowed_scale_ids"]
            and str(scale.id) not in definition["allowed_scale_ids"]
        ):
            raise ConflictError(
                "measurement scale is not permitted by the canonical outcome version"
            )

    async def _validate_evidence(
        self,
        actor: ActorContext,
        review_id: UUID,
        study_id: UUID,
        evidence_location_id: UUID | None,
    ) -> None:
        if evidence_location_id is None:
            return
        article_id = await self._repository.evidence_article(
            actor.organization_id, review_id, evidence_location_id
        )
        if article_id is None:
            raise ResourceNotFoundError("evidence location was not found")
        if not await self._studies.article_linked(
            actor.organization_id, review_id, study_id, article_id
        ):
            raise ConflictError("evidence Article is not linked to the estimate Study")

    async def _outcome(
        self, actor: ActorContext, review_id: UUID, outcome_id: UUID
    ) -> OutcomeDefinition:
        item = await self._repository.get_outcome(actor.organization_id, review_id, outcome_id)
        if item is None:
            raise ResourceNotFoundError("outcome was not found")
        return item

    async def _version(
        self, actor: ActorContext, review_id: UUID, version_id: UUID
    ) -> OutcomeDefinitionVersion:
        item = await self._repository.get_outcome_version(
            actor.organization_id, review_id, version_id
        )
        if item is None:
            raise ResourceNotFoundError("outcome version was not found")
        return item

    async def _mapping(
        self, actor: ActorContext, review_id: UUID, mapping_id: UUID
    ) -> OutcomeMapping:
        item = await self._repository.get_mapping(actor.organization_id, review_id, mapping_id)
        if item is None:
            raise ResourceNotFoundError("outcome mapping was not found")
        return item

    async def _estimate(
        self, actor: ActorContext, review_id: UUID, estimate_id: UUID
    ) -> EffectEstimate:
        item = await self._repository.get_effect_estimate(
            actor.organization_id, review_id, estimate_id
        )
        if item is None:
            raise ResourceNotFoundError("effect estimate was not found")
        return item

    async def _candidate(
        self, actor: ActorContext, review_id: UUID, candidate_id: UUID
    ) -> SynthesisCandidateSet:
        item = await self._repository.get_candidate_set(
            actor.organization_id, review_id, candidate_id
        )
        if item is None:
            raise ResourceNotFoundError("synthesis candidate set was not found")
        return item

    async def _optional_unit(
        self, actor: ActorContext, review_id: UUID, unit_id: UUID | None
    ) -> UnitDefinition | None:
        if unit_id is None:
            return None
        item = await self._repository.get_unit(actor.organization_id, review_id, unit_id)
        if item is None:
            raise ResourceNotFoundError("unit definition was not found")
        return item

    async def _optional_window(
        self, actor: ActorContext, review_id: UUID, window_id: UUID | None
    ) -> TimepointWindow | None:
        if window_id is None:
            return None
        item = await self._repository.get_timepoint_window(
            actor.organization_id, review_id, window_id
        )
        if item is None:
            raise ResourceNotFoundError("timepoint window was not found")
        return item

    async def _optional_scale(
        self, actor: ActorContext, review_id: UUID, scale_id: UUID | None
    ) -> MeasurementScale | None:
        if scale_id is None:
            return None
        item = await self._repository.get_scale(actor.organization_id, review_id, scale_id)
        if item is None:
            raise ResourceNotFoundError("measurement scale was not found")
        return item

    async def _audit_config(
        self, actor: ActorContext, review_id: UUID, entity_type: str, entity_id: UUID, action: str
    ) -> None:
        await self._write(
            actor,
            review_id,
            entity_type,
            entity_id,
            action,
            {},
            source_type=None,
            source_id=None,
            method=HARMONIZATION_VERSION,
        )

    async def _write(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        after: dict[str, Any],
        *,
        source_type: str | None,
        source_id: UUID | None,
        method: str,
        verification_state: VerificationState = VerificationState.UNVERIFIED,
    ) -> None:
        await self._provenance.record_provenance(
            actor,
            review_id=review_id,
            subject_type=entity_type,
            subject_id=entity_id,
            source_type=source_type,
            source_id=source_id,
            source_locator=after,
            method_name=method,
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=verification_state,
        )
        await self._audit(actor, review_id, entity_type, entity_id, action, after)

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        after: dict[str, Any],
    ) -> None:
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_snapshot=None,
            after_snapshot=after,
            reason=None,
        )

    @staticmethod
    def _mapping_snapshot(item: OutcomeMapping) -> dict[str, Any]:
        return {
            "study_id": str(item.study_id),
            "outcome_version_id": str(item.outcome_version_id),
            "reported_value": item.reported_value,
            "reported_unit": item.reported_unit,
            "normalized_value": item.normalized_value,
            "normalized_unit_id": str(item.normalized_unit_id) if item.normalized_unit_id else None,
            "normalized_time_days": item.normalized_time_days,
            "timepoint_window_id": str(item.timepoint_window_id)
            if item.timepoint_window_id
            else None,
            "extraction_verified": item.extraction_verified,
        }

    @staticmethod
    def _estimate_snapshot(item: EffectEstimate) -> dict[str, Any]:
        return {
            "study_id": str(item.study_id),
            "outcome_version_id": str(item.outcome_version_id),
            "effect_measure": item.effect_measure.value,
            "origin": item.origin.value,
            "estimate": item.estimate,
            "standard_error": item.standard_error,
            "variance": item.variance,
            "components": item.components,
            "zero_event_pattern": item.zero_event_pattern.value,
            "calculation_version": item.calculation_version,
        }

    @staticmethod
    def _key(value: str) -> str:
        result = value.strip().upper()
        if (
            not result
            or len(result) > 120
            or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in result)
        ):
            raise ConflictError("scientific key is invalid")
        return result

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

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ConflictError("extraction value is not numeric") from exc
