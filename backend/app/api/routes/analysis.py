from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, Query, Response, status
from pydantic import BaseModel, Field

from backend.app.analysis.domain import (
    AdjustmentPolicy,
    ConfidenceIntervalMethod,
    DependencyPolicy,
    EffectTransformation,
    EstimateSelectionPolicy,
    HeterogeneityEstimator,
    MissingVariancePolicy,
    StatisticalModel,
    ZeroEventPolicy,
)
from backend.app.analysis.engine import NativeDeterministicSynthesisEngine
from backend.app.analysis.persistence import SqlAlchemyAnalysisRepository
from backend.app.analysis.service import AnalysisService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.outcomes.domain import AnalysisPopulation, EffectMeasure
from backend.app.outcomes.persistence import SqlAlchemyOutcomeRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/analysis", tags=["analysis"])


class SpecificationRequest(BaseModel):
    review_id: UUID
    key: str = Field(min_length=1, max_length=120)


class SpecificationDefinition(BaseModel):
    outcome_version_id: UUID
    timepoint_window_id: UUID | None
    synthesis_population: str = Field(min_length=1, max_length=500)
    intervention: str = Field(min_length=1, max_length=1000)
    comparator: str = Field(min_length=1, max_length=1000)
    eligible_study_designs: list[str]
    effect_measure: EffectMeasure
    model: StatisticalModel
    heterogeneity_estimator: HeterogeneityEstimator
    confidence_level: Decimal = Field(gt=0, lt=1)
    transformation: EffectTransformation
    ci_method: ConfidenceIntervalMethod
    zero_event_policy: ZeroEventPolicy
    missing_variance_policy: MissingVariancePolicy
    adjustment_policy: AdjustmentPolicy
    analysis_population: AnalysisPopulation
    selection_policy: EstimateSelectionPolicy
    multi_arm_policy: DependencyPolicy
    cluster_policy: DependencyPolicy
    crossover_policy: DependencyPolicy
    minimum_studies: int = Field(ge=1)
    prediction_interval: bool
    standardized_effect_definition: str | None = None


class SpecificationVersionRequest(BaseModel):
    review_id: UUID
    specification_id: UUID
    definition: SpecificationDefinition


class SpecificationWithVersionRequest(BaseModel):
    review_id: UUID
    key: str = Field(min_length=1, max_length=120)
    definition: SpecificationDefinition


class AnalysisSetRequest(BaseModel):
    review_id: UUID
    specification_version_id: UUID
    candidate_set_id: UUID
    selected_estimate_ids: list[UUID] = Field(min_length=1)


class ExecuteRequest(BaseModel):
    review_id: UUID
    analysis_set_id: UUID


class ReviewRequest(BaseModel):
    review_id: UUID


def _service(session: DbSessionDependency) -> AnalysisService:
    return AnalysisService(
        SqlAlchemyAnalysisRepository(session),
        SqlAlchemyOutcomeRepository(session),
        NativeDeterministicSynthesisEngine(),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post("/specifications", status_code=status.HTTP_201_CREATED)
async def create_specification(
    payload: SpecificationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> dict[str, Any]:
    item = await _service(session).create_specification(actor, **payload.model_dump())
    await session.commit()
    return _specification(item)


@router.post("/specification-versions", status_code=status.HTTP_201_CREATED)
async def create_specification_version(
    payload: SpecificationVersionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> dict[str, Any]:
    values = payload.model_dump()
    values["definition"] = payload.definition.model_dump(mode="json")
    item = await _service(session).create_specification_version(actor, **values)
    await session.commit()
    return _version(item)


@router.post("/specifications-with-version", status_code=status.HTTP_201_CREATED)
async def create_specification_with_version(
    payload: SpecificationWithVersionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> dict[str, Any]:
    service = _service(session)
    specification = await service.create_specification(
        actor, review_id=payload.review_id, key=payload.key
    )
    version = await service.create_specification_version(
        actor,
        review_id=payload.review_id,
        specification_id=specification.id,
        definition=payload.definition.model_dump(mode="json"),
    )
    await session.commit()
    return {"specification": _specification(specification), "version": _version(version)}


@router.post("/sets", status_code=status.HTTP_201_CREATED)
async def create_analysis_set(
    payload: AnalysisSetRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> dict[str, Any]:
    item = await _service(session).create_analysis_set(actor, **payload.model_dump())
    await session.commit()
    return _analysis_set(item)


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def execute_analysis(
    payload: ExecuteRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> dict[str, Any]:
    item = await _service(session).execute(actor, **payload.model_dump())
    await session.commit()
    return _run(item, stale=False)


@router.post("/runs/{run_id}/forest-plot", status_code=status.HTTP_201_CREATED)
async def generate_forest_plot(
    payload: ReviewRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    run_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).generate_forest_plot(
        actor, review_id=payload.review_id, run_id=run_id
    )
    await session.commit()
    return _artifact(item)


@router.get("/reviews/{review_id}")
async def analysis_workspace(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    specifications, sets, runs, artifacts = await _service(session).list_workspace(
        actor, review_id=review_id
    )
    return {
        "specifications": [
            {**_specification(item), "versions": [_version(version) for version in versions]}
            for item, versions in specifications
        ],
        "analysis_sets": [_analysis_set(item) for item in sets],
        "runs": [_run(item, stale=stale) for item, stale in runs],
        "artifacts": [_artifact(item) for item in artifacts],
    }


@router.get("/artifacts/{artifact_id}/download")
async def download_analysis_artifact(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    artifact_id: Annotated[UUID, Path()],
    review_id: Annotated[UUID, Query()],
) -> Response:
    item = await _service(session).get_artifact(actor, review_id=review_id, artifact_id=artifact_id)
    return Response(
        content=item.content,
        media_type=item.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{item.filename}"',
            "X-Content-SHA256": item.sha256,
        },
    )


def _specification(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "review_id": str(item.review_id),
        "key": item.key,
        "created_by_user_id": str(item.created_by_user_id),
        "created_at": item.created_at.isoformat(),
    }


def _version(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "specification_id": str(item.specification_id),
        "version": item.version,
        "definition": item.definition,
        "content_hash": item.content_hash,
        "created_by_user_id": str(item.created_by_user_id),
        "created_at": item.created_at.isoformat(),
    }


def _analysis_set(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "specification_version_id": str(item.specification_version_id),
        "candidate_set_id": str(item.candidate_set_id),
        "included_estimate_ids": [str(value) for value in item.included_estimate_ids],
        "excluded_estimates": list(item.excluded_estimates),
        "input_hash": item.input_hash,
        "created_by_user_id": str(item.created_by_user_id),
        "created_at": item.created_at.isoformat(),
    }


def _run(item: Any, *, stale: bool) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "specification_version_id": str(item.specification_version_id),
        "analysis_set_id": str(item.analysis_set_id),
        "status": item.status.value,
        "algorithm_name": item.algorithm_name,
        "algorithm_version": item.algorithm_version,
        "provider": item.provider,
        "provider_version": item.provider_version,
        "input_hash": item.input_hash,
        "result_hash": item.result_hash,
        "result": item.result,
        "diagnostics": list(item.diagnostics),
        "failure_reason": item.failure_reason,
        "stale": stale,
        "created_by_user_id": str(item.created_by_user_id),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat(),
    }


def _artifact(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "run_id": str(item.run_id),
        "artifact_type": item.artifact_type,
        "renderer_version": item.renderer_version,
        "media_type": item.media_type,
        "filename": item.filename,
        "sha256": item.sha256,
        "byte_size": item.byte_size,
        "created_at": item.created_at.isoformat(),
    }
