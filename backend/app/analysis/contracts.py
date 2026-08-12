from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.analysis.domain import (
    AnalysisArtifact,
    AnalysisSet,
    AnalysisSpecification,
    AnalysisSpecificationVersion,
    MetaAnalysisRun,
    SensitivityResult,
    StudyEffectInput,
    SynthesisResult,
)
from backend.app.outcomes.domain import EffectEstimate, OutcomeMapping, SynthesisCandidateSet


class StatisticalSynthesisEngine(Protocol):
    name: str
    version: str
    provider: str
    provider_version: str

    def synthesize(
        self, definition: dict[str, Any], studies: tuple[StudyEffectInput, ...]
    ) -> SynthesisResult: ...

    def leave_one_out(
        self, definition: dict[str, Any], studies: tuple[StudyEffectInput, ...]
    ) -> tuple[SensitivityResult, ...]: ...


class AnalysisRepository(Protocol):
    async def create_specification(self, **values: Any) -> AnalysisSpecification: ...
    async def get_specification(
        self, organization_id: UUID, review_id: UUID, specification_id: UUID
    ) -> AnalysisSpecification | None: ...
    async def list_specifications(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AnalysisSpecification]: ...
    async def create_specification_version(self, **values: Any) -> AnalysisSpecificationVersion: ...
    async def get_specification_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> AnalysisSpecificationVersion | None: ...
    async def list_specification_versions(
        self, organization_id: UUID, review_id: UUID, specification_id: UUID | None = None
    ) -> list[AnalysisSpecificationVersion]: ...
    async def get_candidate_set(
        self, organization_id: UUID, review_id: UUID, candidate_set_id: UUID
    ) -> SynthesisCandidateSet | None: ...
    async def get_effect_estimate(
        self, organization_id: UUID, review_id: UUID, estimate_id: UUID
    ) -> EffectEstimate | None: ...
    async def get_mapping(
        self, organization_id: UUID, review_id: UUID, mapping_id: UUID
    ) -> OutcomeMapping | None: ...
    async def mapping_is_superseded(
        self, organization_id: UUID, review_id: UUID, mapping_id: UUID
    ) -> bool: ...
    async def study_label(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> str | None: ...
    async def study_design(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> str | None: ...
    async def create_analysis_set(self, **values: Any) -> AnalysisSet: ...
    async def get_analysis_set(
        self, organization_id: UUID, review_id: UUID, analysis_set_id: UUID
    ) -> AnalysisSet | None: ...
    async def list_analysis_sets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AnalysisSet]: ...
    async def create_run(self, **values: Any) -> MetaAnalysisRun: ...
    async def mark_run_running(self, run_id: UUID) -> MetaAnalysisRun: ...
    async def complete_run(
        self,
        run_id: UUID,
        *,
        result_hash: str,
        result: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        weights: list[dict[str, Any]],
        sensitivities: list[dict[str, Any]],
    ) -> MetaAnalysisRun: ...
    async def fail_run(
        self, run_id: UUID, *, failure_reason: str, diagnostics: list[dict[str, Any]]
    ) -> MetaAnalysisRun: ...
    async def get_run(
        self, organization_id: UUID, review_id: UUID, run_id: UUID
    ) -> MetaAnalysisRun | None: ...
    async def list_runs(self, organization_id: UUID, review_id: UUID) -> list[MetaAnalysisRun]: ...
    async def create_artifact(self, **values: Any) -> AnalysisArtifact: ...
    async def get_artifact(
        self, organization_id: UUID, review_id: UUID, artifact_id: UUID
    ) -> AnalysisArtifact | None: ...
    async def list_artifacts(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AnalysisArtifact]: ...
