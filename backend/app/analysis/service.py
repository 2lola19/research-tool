from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from backend.app.analysis.contracts import AnalysisRepository, StatisticalSynthesisEngine
from backend.app.analysis.domain import (
    ALGORITHM_VERSION,
    FOREST_RENDERER_VERSION,
    AdjustmentPolicy,
    AnalysisArtifact,
    AnalysisSet,
    AnalysisSpecification,
    AnalysisSpecificationVersion,
    DiagnosticCode,
    DiagnosticLevel,
    EffectTransformation,
    MetaAnalysisRun,
    RunStatus,
    SensitivityResult,
    StudyEffectInput,
    ZeroEventPolicy,
    canonical_hash,
    normalize_specification,
    synthesis_result_payload,
    transform_effect,
)
from backend.app.analysis.renderers import forest_plot_model, render_forest_svg
from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.outcomes.contracts import OutcomeRepository
from backend.app.outcomes.domain import (
    AdjustmentStatus,
    EffectEstimate,
    EffectMeasure,
    ReadinessStatus,
    VarianceScale,
    ZeroEventPattern,
)
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService


class AnalysisService:
    def __init__(
        self,
        repository: AnalysisRepository,
        outcome_repository: OutcomeRepository,
        engine: StatisticalSynthesisEngine,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._outcomes = outcome_repository
        self._engine = engine
        self._reviews = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_specification(
        self, actor: ActorContext, *, review_id: UUID, key: str
    ) -> AnalysisSpecification:
        AuthorizationService.require(actor, Permission.MANAGE_ANALYSIS)
        await self._reviews.get(actor, review_id)
        normalized = self._key(key)
        if any(
            item.key == normalized
            for item in await self._repository.list_specifications(actor.organization_id, review_id)
        ):
            raise ConflictError("analysis specification key already exists")
        item = await self._repository.create_specification(
            organization_id=actor.organization_id,
            review_id=review_id,
            key=normalized,
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "analysis_specification",
            item.id,
            "ANALYSIS_SPECIFICATION_CREATED",
            {"key": item.key},
            source_type=None,
            source_id=None,
            method="versioned_analysis_specification",
        )
        return item

    async def create_specification_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        specification_id: UUID,
        definition: dict[str, Any],
    ) -> AnalysisSpecificationVersion:
        AuthorizationService.require(actor, Permission.MANAGE_ANALYSIS)
        await self._reviews.get(actor, review_id)
        await self._specification(actor, review_id, specification_id)
        try:
            normalized = normalize_specification(definition)
        except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
            raise ConflictError(str(exc)) from exc
        outcome_version_id = UUID(normalized["outcome_version_id"])
        if (
            await self._outcomes.get_outcome_version(
                actor.organization_id, review_id, outcome_version_id
            )
            is None
        ):
            raise ResourceNotFoundError("outcome version was not found")
        timepoint_id = (
            UUID(normalized["timepoint_window_id"]) if normalized["timepoint_window_id"] else None
        )
        if timepoint_id is not None and (
            await self._outcomes.get_timepoint_window(
                actor.organization_id, review_id, timepoint_id
            )
            is None
        ):
            raise ResourceNotFoundError("timepoint window was not found")
        item = await self._repository.create_specification_version(
            specification_id=specification_id,
            organization_id=actor.organization_id,
            review_id=review_id,
            definition=normalized,
            content_hash=canonical_hash(normalized),
            outcome_version_id=outcome_version_id,
            timepoint_window_id=timepoint_id,
            effect_measure=normalized["effect_measure"],
            model=normalized["model"],
            heterogeneity_estimator=normalized["heterogeneity_estimator"],
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "analysis_specification_version",
            item.id,
            "ANALYSIS_SPECIFICATION_VERSIONED",
            {
                "specification_id": str(specification_id),
                "version": item.version,
                "content_hash": item.content_hash,
                "definition": item.definition,
            },
            source_type="outcome_definition_version",
            source_id=outcome_version_id,
            method="analysis-specification-1",
        )
        return item

    async def list_specifications(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[tuple[AnalysisSpecification, list[AnalysisSpecificationVersion]]]:
        await self._reviews.get(actor, review_id)
        specifications = await self._repository.list_specifications(
            actor.organization_id, review_id
        )
        return [
            (
                item,
                await self._repository.list_specification_versions(
                    actor.organization_id, review_id, item.id
                ),
            )
            for item in specifications
        ]

    async def create_analysis_set(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        specification_version_id: UUID,
        candidate_set_id: UUID,
        selected_estimate_ids: list[UUID],
    ) -> AnalysisSet:
        AuthorizationService.require(actor, Permission.RUN_ANALYSIS)
        await self._reviews.get(actor, review_id)
        version = await self._version(actor, review_id, specification_version_id)
        candidate = await self._candidate(actor, review_id, candidate_set_id)
        readiness = [
            item
            for item in await self._outcomes.list_readiness_snapshots(
                actor.organization_id, review_id
            )
            if item.candidate_set_id == candidate.id
        ]
        if not readiness or readiness[-1].status != ReadinessStatus.READY:
            raise ConflictError(DiagnosticCode.CANDIDATE_NOT_ANALYSIS_READY.value)
        if not selected_estimate_ids or len(selected_estimate_ids) != len(
            set(selected_estimate_ids)
        ):
            raise ConflictError("analysis set requires unique explicitly selected estimates")
        if not set(selected_estimate_ids) <= set(candidate.estimate_ids):
            raise ResourceNotFoundError("selected effect estimate was not found in candidate set")
        if candidate.outcome_version_id != UUID(version.definition["outcome_version_id"]):
            raise ConflictError(DiagnosticCode.OUTCOME_VERSION_MISMATCH.value)
        if candidate.effect_measure.value != version.definition["effect_measure"]:
            raise ConflictError(DiagnosticCode.EFFECT_MEASURE_MISMATCH.value)
        if candidate.timepoint_window_id != self._uuid_or_none(
            version.definition["timepoint_window_id"]
        ):
            raise ConflictError(DiagnosticCode.TIMEPOINT_MISMATCH.value)
        if candidate.population_label != version.definition["synthesis_population"]:
            raise ConflictError(DiagnosticCode.ANALYSIS_POPULATION_MISMATCH.value)
        estimates = [
            await self._estimate(actor, review_id, estimate_id)
            for estimate_id in selected_estimate_ids
        ]
        included, excluded, blockers = await self._validate_estimates(
            actor, review_id, version, estimates
        )
        if blockers:
            raise ConflictError(
                "analysis set is not ready: "
                + ", ".join(sorted({item["code"] for item in blockers}))
            )
        if len(included) < int(version.definition["minimum_studies"]):
            raise ConflictError("analysis set has fewer Studies than its explicit minimum")
        payload = self._input_payload(version, included)
        item = await self._repository.create_analysis_set(
            organization_id=actor.organization_id,
            review_id=review_id,
            specification_version_id=version.id,
            candidate_set_id=candidate.id,
            included_estimate_ids=[str(value.id) for value in included],
            excluded_estimates=excluded,
            input_hash=canonical_hash(payload),
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "analysis_set",
            item.id,
            "ANALYSIS_SET_CREATED",
            {
                "specification_version_id": str(version.id),
                "candidate_set_id": str(candidate.id),
                "included_estimate_ids": [str(value) for value in item.included_estimate_ids],
                "excluded_estimates": list(item.excluded_estimates),
                "input_hash": item.input_hash,
            },
            source_type="synthesis_candidate_set",
            source_id=candidate.id,
            method="analysis-set-1",
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        return item

    async def execute(
        self, actor: ActorContext, *, review_id: UUID, analysis_set_id: UUID
    ) -> MetaAnalysisRun:
        AuthorizationService.require(actor, Permission.RUN_ANALYSIS)
        await self._reviews.get(actor, review_id)
        analysis_set = await self._analysis_set(actor, review_id, analysis_set_id)
        version = await self._version(actor, review_id, analysis_set.specification_version_id)
        estimates = [
            await self._estimate(actor, review_id, item)
            for item in analysis_set.included_estimate_ids
        ]
        included, _, blockers = await self._validate_estimates(actor, review_id, version, estimates)
        current_hash = canonical_hash(self._input_payload(version, included))
        if current_hash != analysis_set.input_hash:
            blockers.append(self._blocking(DiagnosticCode.STALE_ANALYSIS_SET))
        if blockers:
            raise ConflictError(
                "analysis execution blocked: "
                + ", ".join(sorted({item["code"] for item in blockers}))
            )
        study_inputs: list[StudyEffectInput] = []
        for estimate in included:
            study_inputs.append(await self._study_input(actor, review_id, version, estimate))
        studies = tuple(study_inputs)
        run = await self._repository.create_run(
            organization_id=actor.organization_id,
            review_id=review_id,
            specification_version_id=version.id,
            analysis_set_id=analysis_set.id,
            status=RunStatus.PLANNED.value,
            algorithm_name=self._engine.name,
            algorithm_version=self._engine.version,
            provider=self._engine.provider,
            provider_version=self._engine.provider_version,
            input_hash=current_hash,
            result_hash=None,
            result=None,
            diagnostics=[],
            failure_reason=None,
            created_by_user_id=actor.user_id,
            started_at=None,
            completed_at=None,
        )
        run = await self._repository.mark_run_running(run.id)
        await self._audit(
            actor,
            review_id,
            "meta_analysis_run",
            run.id,
            "META_ANALYSIS_STARTED",
            {"analysis_set_id": str(analysis_set.id), "input_hash": current_hash},
        )
        try:
            result = self._engine.synthesize(version.definition, studies)
            sensitivities = self._engine.leave_one_out(version.definition, studies)
        except (ValueError, ArithmeticError, InvalidOperation) as exc:
            diagnostic = {
                "code": DiagnosticCode.ESTIMATOR_NONCONVERGENCE.value,
                "level": DiagnosticLevel.BLOCKING.value,
                "message": str(exc),
            }
            run = await self._repository.fail_run(
                run.id, failure_reason=str(exc), diagnostics=[diagnostic]
            )
            await self._audit(
                actor,
                review_id,
                "meta_analysis_run",
                run.id,
                "META_ANALYSIS_FAILED",
                {"failure_reason": str(exc), "diagnostics": [diagnostic]},
            )
            return run
        result_payload = synthesis_result_payload(result)
        sensitivity_payloads = [self._sensitivity_payload(item) for item in sensitivities]
        result_payload["sensitivity"] = [
            {
                "omitted_study_id": str(item.omitted_study_id),
                "omitted_estimate_id": str(item.omitted_estimate_id),
                "presentation_estimate": str(item.result.presentation_estimate),
                "presentation_ci_lower": str(item.result.presentation_ci_lower),
                "presentation_ci_upper": str(item.result.presentation_ci_upper),
                "heterogeneity": synthesis_result_payload(item.result)["heterogeneity"],
            }
            for item in sensitivities
        ]
        run = await self._repository.complete_run(
            run.id,
            result_hash=canonical_hash(result_payload),
            result=result_payload,
            diagnostics=list(result.diagnostics),
            weights=[
                {
                    "study_id": item.study_id,
                    "estimate_id": item.estimate_id,
                    "analysis_estimate": item.analysis_estimate,
                    "presentation_estimate": item.presentation_estimate,
                    "ci_lower": item.ci_lower,
                    "ci_upper": item.ci_upper,
                    "raw_weight": item.raw_weight,
                    "normalized_weight_percent": item.normalized_weight_percent,
                }
                for item in result.weights
            ],
            sensitivities=sensitivity_payloads,
        )
        await self._write(
            actor,
            review_id,
            "meta_analysis_run",
            run.id,
            "META_ANALYSIS_COMPLETED",
            {
                "analysis_set_id": str(analysis_set.id),
                "input_hash": run.input_hash,
                "result_hash": run.result_hash,
                "result": run.result,
            },
            source_type="analysis_set",
            source_id=analysis_set.id,
            method=self._engine.name,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        if sensitivities:
            await self._audit(
                actor,
                review_id,
                "meta_analysis_run",
                run.id,
                "SENSITIVITY_ANALYSIS_COMPLETED",
                {"leave_one_out_count": len(sensitivities)},
            )
        return run

    async def generate_forest_plot(
        self, actor: ActorContext, *, review_id: UUID, run_id: UUID
    ) -> AnalysisArtifact:
        AuthorizationService.require(actor, Permission.RUN_ANALYSIS)
        await self._reviews.get(actor, review_id)
        run = await self._run(actor, review_id, run_id)
        if run.status != RunStatus.COMPLETED or run.result is None:
            raise ConflictError("forest plot requires a completed meta-analysis run")
        version = await self._version(actor, review_id, run.specification_version_id)
        labels = {
            item["study_id"]: (
                await self._repository.study_label(
                    actor.organization_id, review_id, UUID(item["study_id"])
                )
                or item["study_id"]
            )
            for item in run.result["weights"]
        }
        model = forest_plot_model(
            effect_measure=version.definition["effect_measure"],
            result=run.result,
            study_labels=labels,
        )
        content = render_forest_svg(model)
        artifact = await self._repository.create_artifact(
            organization_id=actor.organization_id,
            review_id=review_id,
            run_id=run.id,
            artifact_type="FOREST_PLOT_SVG",
            renderer_version=FOREST_RENDERER_VERSION,
            media_type="image/svg+xml",
            filename=f"forest-plot-{run.id}.svg",
            content=content,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            created_by_user_id=actor.user_id,
        )
        await self._write(
            actor,
            review_id,
            "analysis_artifact",
            artifact.id,
            "ANALYSIS_ARTIFACT_GENERATED",
            {
                "run_id": str(run.id),
                "input_hash": run.input_hash,
                "renderer_version": artifact.renderer_version,
                "sha256": artifact.sha256,
            },
            source_type="meta_analysis_run",
            source_id=run.id,
            method=FOREST_RENDERER_VERSION,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        return artifact

    async def list_workspace(
        self, actor: ActorContext, *, review_id: UUID
    ) -> tuple[
        list[tuple[AnalysisSpecification, list[AnalysisSpecificationVersion]]],
        list[AnalysisSet],
        list[tuple[MetaAnalysisRun, bool]],
        list[AnalysisArtifact],
    ]:
        await self._reviews.get(actor, review_id)
        specifications = await self.list_specifications(actor, review_id=review_id)
        sets = await self._repository.list_analysis_sets(actor.organization_id, review_id)
        runs = await self._repository.list_runs(actor.organization_id, review_id)
        return (
            specifications,
            sets,
            [(run, await self._is_stale(actor, review_id, run)) for run in runs],
            await self._repository.list_artifacts(actor.organization_id, review_id),
        )

    async def get_artifact(
        self, actor: ActorContext, *, review_id: UUID, artifact_id: UUID
    ) -> AnalysisArtifact:
        await self._reviews.get(actor, review_id)
        artifact = await self._repository.get_artifact(
            actor.organization_id, review_id, artifact_id
        )
        if artifact is None:
            raise ResourceNotFoundError("analysis artifact was not found")
        if hashlib.sha256(artifact.content).hexdigest() != artifact.sha256:
            raise ConflictError("analysis artifact checksum verification failed")
        return artifact

    async def _validate_estimates(
        self,
        actor: ActorContext,
        review_id: UUID,
        version: AnalysisSpecificationVersion,
        estimates: list[EffectEstimate],
    ) -> tuple[list[EffectEstimate], list[dict[str, Any]], list[dict[str, Any]]]:
        included: list[EffectEstimate] = []
        excluded: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        studies: set[UUID] = set()
        units: set[UUID | None] = set()
        scales: set[UUID | None] = set()
        definition = version.definition
        for estimate in sorted(estimates, key=lambda item: (str(item.study_id), str(item.id))):
            details = {"study_id": str(estimate.study_id), "estimate_id": str(estimate.id)}
            if estimate.study_id in studies:
                blockers.append(
                    self._blocking(DiagnosticCode.MULTIPLE_ELIGIBLE_ESTIMATES_PER_STUDY, **details)
                )
            studies.add(estimate.study_id)
            units.add(estimate.unit_id)
            scales.add(estimate.measurement_scale_id)
            eligible_designs = set(definition["eligible_study_designs"])
            study_design = await self._repository.study_design(
                actor.organization_id, review_id, estimate.study_id
            )
            if eligible_designs and study_design not in eligible_designs:
                blockers.append(self._blocking(DiagnosticCode.STUDY_DESIGN_INCOMPATIBLE, **details))
            if estimate.outcome_version_id != UUID(definition["outcome_version_id"]):
                blockers.append(self._blocking(DiagnosticCode.OUTCOME_VERSION_MISMATCH, **details))
            if estimate.effect_measure.value != definition["effect_measure"]:
                blockers.append(self._blocking(DiagnosticCode.EFFECT_MEASURE_MISMATCH, **details))
            if estimate.timepoint_window_id != self._uuid_or_none(
                definition["timepoint_window_id"]
            ):
                blockers.append(self._blocking(DiagnosticCode.TIMEPOINT_MISMATCH, **details))
            if estimate.analysis_population.value != definition["analysis_population"]:
                blockers.append(
                    self._blocking(DiagnosticCode.ANALYSIS_POPULATION_MISMATCH, **details)
                )
            if not self._adjustment_allowed(estimate.adjustment, definition["adjustment_policy"]):
                blockers.append(self._blocking(DiagnosticCode.ADJUSTMENT_MISMATCH, **details))
            mappings = [
                await self._repository.get_mapping(actor.organization_id, review_id, mapping_id)
                for mapping_id in estimate.source_mapping_ids
            ]
            if not mappings or any(
                mapping is None or not mapping.extraction_verified for mapping in mappings
            ):
                blockers.append(self._blocking(DiagnosticCode.UNVERIFIED_EXTRACTION, **details))
            superseded = False
            for mapping in mappings:
                if mapping is not None and await self._repository.mapping_is_superseded(
                    actor.organization_id, review_id, mapping.id
                ):
                    superseded = True
                    break
            if superseded:
                blockers.append(self._blocking(DiagnosticCode.SUPERSEDED_ESTIMATE, **details))
            if estimate.zero_event_pattern == ZeroEventPattern.DOUBLE_ZERO and (
                definition["zero_event_policy"] == ZeroEventPolicy.EXCLUDE_DOUBLE_ZERO.value
            ):
                excluded.append({**details, "reason": DiagnosticCode.DOUBLE_ZERO_STUDY.value})
                continue
            if estimate.zero_event_pattern != ZeroEventPattern.NONE:
                blockers.append(
                    self._blocking(DiagnosticCode.ZERO_EVENT_POLICY_REQUIRED, **details)
                )
            if estimate.variance is None or Decimal(estimate.variance) <= 0:
                blockers.append(self._blocking(DiagnosticCode.MISSING_VARIANCE, **details))
            if estimate.estimate is None:
                blockers.append(
                    self._blocking(DiagnosticCode.ZERO_EVENT_POLICY_REQUIRED, **details)
                )
            expected_scale = (
                VarianceScale.LOG
                if definition["transformation"] == EffectTransformation.LOG.value
                else VarianceScale.NATURAL
            )
            if estimate.variance_scale != expected_scale:
                blockers.append(self._blocking(DiagnosticCode.EFFECT_MEASURE_MISMATCH, **details))
            if estimate.effect_measure in (EffectMeasure.MD, EffectMeasure.MEAN) and (
                estimate.unit_id is None
            ):
                blockers.append(self._blocking(DiagnosticCode.UNIT_NOT_HARMONIZED, **details))
            if estimate.effect_measure == EffectMeasure.SMD:
                if estimate.measurement_scale_id is None:
                    blockers.append(
                        self._blocking(DiagnosticCode.SCALE_DIRECTION_UNKNOWN, **details)
                    )
                else:
                    scale = await self._outcomes.get_scale(
                        actor.organization_id, review_id, estimate.measurement_scale_id
                    )
                    if scale is None or scale.directionality.value == "UNKNOWN":
                        blockers.append(
                            self._blocking(DiagnosticCode.SCALE_DIRECTION_UNKNOWN, **details)
                        )
            self._dependency_blockers(estimate, blockers, details)
            included.append(estimate)
        if len({item for item in units if item is not None}) > 1:
            blockers.append(self._blocking(DiagnosticCode.UNIT_MISMATCH))
        if len({item for item in scales if item is not None}) > 1:
            blockers.append(self._blocking(DiagnosticCode.SCALE_MISMATCH))
        return included, excluded, blockers

    @staticmethod
    def _dependency_blockers(
        estimate: EffectEstimate,
        blockers: list[dict[str, Any]],
        details: dict[str, str],
    ) -> None:
        if estimate.components.get("multi_arm_dependency") == "1":
            blockers.append(
                AnalysisService._blocking(DiagnosticCode.MULTI_ARM_DEPENDENCY, **details)
            )
        if estimate.components.get("cluster_randomized") == "1" and (
            estimate.components.get("cluster_adjusted") != "1"
        ):
            blockers.append(
                AnalysisService._blocking(DiagnosticCode.CLUSTER_ADJUSTMENT_REQUIRED, **details)
            )
        if estimate.components.get("crossover") == "1" and (
            estimate.components.get("crossover_variance_compatible") != "1"
        ):
            blockers.append(
                AnalysisService._blocking(DiagnosticCode.CROSSOVER_VARIANCE_REQUIRED, **details)
            )

    async def _study_input(
        self,
        actor: ActorContext,
        review_id: UUID,
        version: AnalysisSpecificationVersion,
        estimate: EffectEstimate,
    ) -> StudyEffectInput:
        if estimate.estimate is None or estimate.variance is None:
            raise ConflictError("selected estimate is missing its effect or variance")
        transformation = EffectTransformation(version.definition["transformation"])
        expected_scale = (
            VarianceScale.LOG
            if transformation == EffectTransformation.LOG
            else VarianceScale.NATURAL
        )
        if estimate.variance_scale != expected_scale:
            raise ConflictError("effect variance scale does not match analysis transformation")
        presentation = Decimal(estimate.estimate)
        sample_size = self._sample_size(estimate)
        return StudyEffectInput(
            study_id=estimate.study_id,
            estimate_id=estimate.id,
            label=(
                await self._repository.study_label(
                    actor.organization_id, review_id, estimate.study_id
                )
                or str(estimate.study_id)
            ),
            presentation_estimate=presentation,
            analysis_estimate=transform_effect(presentation, transformation),
            variance=Decimal(estimate.variance),
            sample_size=sample_size,
        )

    @staticmethod
    def _sample_size(estimate: EffectEstimate) -> int | None:
        values = [
            estimate.components.get("sample_intervention"),
            estimate.components.get("sample_comparator"),
        ]
        if any(value is None for value in values):
            return None
        return sum(int(Decimal(value)) for value in values if value is not None)

    @staticmethod
    def _input_payload(
        version: AnalysisSpecificationVersion, estimates: list[EffectEstimate]
    ) -> dict[str, Any]:
        return {
            "specification_version_id": str(version.id),
            "specification_content_hash": version.content_hash,
            "definition": version.definition,
            "estimates": [
                {
                    "id": str(item.id),
                    "study_id": str(item.study_id),
                    "outcome_version_id": str(item.outcome_version_id),
                    "effect_measure": item.effect_measure.value,
                    "estimate": item.estimate,
                    "variance": item.variance,
                    "variance_scale": item.variance_scale.value,
                    "adjustment": item.adjustment.value,
                    "analysis_population": item.analysis_population.value,
                    "timepoint_window_id": (
                        str(item.timepoint_window_id) if item.timepoint_window_id else None
                    ),
                    "source_mapping_ids": [str(value) for value in item.source_mapping_ids],
                    "zero_event_pattern": item.zero_event_pattern.value,
                    "components": item.components,
                }
                for item in sorted(
                    estimates, key=lambda value: (str(value.study_id), str(value.id))
                )
            ],
            "algorithm_version": ALGORITHM_VERSION,
        }

    @staticmethod
    def _sensitivity_payload(item: SensitivityResult) -> dict[str, Any]:
        result = synthesis_result_payload(item.result)
        return {
            "omitted_study_id": item.omitted_study_id,
            "omitted_estimate_id": item.omitted_estimate_id,
            "result": result,
            "result_hash": canonical_hash(result),
        }

    async def _is_stale(self, actor: ActorContext, review_id: UUID, run: MetaAnalysisRun) -> bool:
        version = await self._version(actor, review_id, run.specification_version_id)
        versions = await self._repository.list_specification_versions(
            actor.organization_id, review_id, version.specification_id
        )
        if any(item.version > version.version for item in versions):
            return True
        analysis_set = await self._analysis_set(actor, review_id, run.analysis_set_id)
        estimates = [
            await self._estimate(actor, review_id, item)
            for item in analysis_set.included_estimate_ids
        ]
        if canonical_hash(self._input_payload(version, estimates)) != run.input_hash:
            return True
        for estimate in estimates:
            for mapping_id in estimate.source_mapping_ids:
                if await self._repository.mapping_is_superseded(
                    actor.organization_id, review_id, mapping_id
                ):
                    return True
        return False

    async def _specification(
        self, actor: ActorContext, review_id: UUID, specification_id: UUID
    ) -> AnalysisSpecification:
        item = await self._repository.get_specification(
            actor.organization_id, review_id, specification_id
        )
        if item is None:
            raise ResourceNotFoundError("analysis specification was not found")
        return item

    async def _version(
        self, actor: ActorContext, review_id: UUID, version_id: UUID
    ) -> AnalysisSpecificationVersion:
        item = await self._repository.get_specification_version(
            actor.organization_id, review_id, version_id
        )
        if item is None:
            raise ResourceNotFoundError("analysis specification version was not found")
        return item

    async def _candidate(self, actor: ActorContext, review_id: UUID, candidate_id: UUID) -> Any:
        item = await self._repository.get_candidate_set(
            actor.organization_id, review_id, candidate_id
        )
        if item is None:
            raise ResourceNotFoundError("synthesis candidate set was not found")
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

    async def _analysis_set(
        self, actor: ActorContext, review_id: UUID, analysis_set_id: UUID
    ) -> AnalysisSet:
        item = await self._repository.get_analysis_set(
            actor.organization_id, review_id, analysis_set_id
        )
        if item is None:
            raise ResourceNotFoundError("analysis set was not found")
        return item

    async def _run(self, actor: ActorContext, review_id: UUID, run_id: UUID) -> MetaAnalysisRun:
        item = await self._repository.get_run(actor.organization_id, review_id, run_id)
        if item is None:
            raise ResourceNotFoundError("meta-analysis run was not found")
        return item

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
    def _adjustment_allowed(adjustment: AdjustmentStatus, policy: str) -> bool:
        if policy == AdjustmentPolicy.EITHER_EXPLICIT_SELECTION.value:
            return True
        if policy == AdjustmentPolicy.ADJUSTED_ONLY.value:
            return adjustment == AdjustmentStatus.ADJUSTED
        return adjustment == AdjustmentStatus.UNADJUSTED

    @staticmethod
    def _blocking(code: DiagnosticCode, **details: str) -> dict[str, Any]:
        return {"code": code.value, "level": DiagnosticLevel.BLOCKING.value, **details}

    @staticmethod
    def _key(value: str) -> str:
        result = value.strip().upper()
        if (
            not result
            or len(result) > 120
            or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in result)
        ):
            raise ConflictError("analysis specification key is invalid")
        return result

    @staticmethod
    def _uuid_or_none(value: str | None) -> UUID | None:
        return UUID(value) if value else None
