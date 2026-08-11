from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.outcomes.domain import (
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
)
from backend.app.outcomes.persistence import SqlAlchemyOutcomeRepository
from backend.app.outcomes.service import OutcomeService
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.studies.persistence import SqlAlchemyStudyRepository

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


class OutcomeRequest(BaseModel):
    review_id: UUID
    key: str = Field(min_length=1, max_length=120)


class OutcomeVersionRequest(BaseModel):
    review_id: UUID
    outcome_id: UUID
    definition: dict[str, Any]
    protocol_version_id: UUID | None = None


class OutcomeWithVersionRequest(BaseModel):
    review_id: UUID
    key: str = Field(min_length=1, max_length=120)
    definition: dict[str, Any]
    protocol_version_id: UUID | None = None


class OutcomeVersionResponse(BaseModel):
    id: UUID
    outcome_id: UUID
    version: int
    definition: dict[str, Any]
    content_hash: str
    protocol_version_id: UUID | None

    @classmethod
    def from_domain(cls, item: OutcomeDefinitionVersion) -> OutcomeVersionResponse:
        return cls(
            id=item.id,
            outcome_id=item.outcome_id,
            version=item.version,
            definition=item.definition,
            content_hash=item.content_hash,
            protocol_version_id=item.protocol_version_id,
        )


class OutcomeResponse(BaseModel):
    id: UUID
    review_id: UUID
    key: str
    versions: list[OutcomeVersionResponse] = []

    @classmethod
    def from_domain(
        cls, item: OutcomeDefinition, versions: list[OutcomeDefinitionVersion] | None = None
    ) -> OutcomeResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            key=item.key,
            versions=[OutcomeVersionResponse.from_domain(version) for version in versions or []],
        )


class OutcomeWithVersionResponse(BaseModel):
    outcome: OutcomeResponse
    version: OutcomeVersionResponse


class TimepointWindowRequest(BaseModel):
    review_id: UUID
    key: str
    label: str
    anchor: TimeAnchor
    minimum_days: Decimal | None = None
    maximum_days: Decimal | None = None
    rule_version: str = "1"


class UnitRequest(BaseModel):
    review_id: UUID
    key: str
    label: str
    dimension: str
    context_key: str = "GENERAL"
    base_unit_key: str
    multiplier_to_base: Decimal = Decimal("1")
    offset_to_base: Decimal = Decimal("0")
    precision: int = Field(default=6, ge=0, le=18)
    rule_version: str = "1"


class ScaleRequest(BaseModel):
    review_id: UUID
    key: str
    name: str
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    directionality: Directionality


class ConfigurationResponse(BaseModel):
    timepoint_windows: list[dict[str, Any]]
    units: list[dict[str, Any]]
    measurement_scales: list[dict[str, Any]]


class MappingRequest(BaseModel):
    review_id: UUID
    study_id: UUID
    extraction_value_id: UUID
    outcome_version_id: UUID
    method: MappingMethod = MappingMethod.MANUAL
    rationale: str = Field(min_length=1, max_length=20_000)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    reported_unit_id: UUID | None = None
    normalized_unit_id: UUID | None = None
    reported_time_value: Decimal | None = None
    reported_time_unit: TimeUnit | None = None
    reported_time_anchor: TimeAnchor | None = None
    timepoint_window_id: UUID | None = None
    measurement_scale_id: UUID | None = None
    direction_transformation: DirectionTransformation = DirectionTransformation.NONE
    transformation_reason: str | None = Field(default=None, max_length=20_000)
    supersedes_mapping_id: UUID | None = None


class MappingResponse(BaseModel):
    id: UUID
    review_id: UUID
    study_id: UUID
    extraction_value_id: UUID
    outcome_version_id: UUID
    method: MappingMethod
    rationale: str
    confidence: str | None
    reported_value: str | None
    reported_unit: str | None
    reported_unit_id: UUID | None
    normalized_value: str | None
    normalized_unit_id: UUID | None
    conversion_rule_version: str | None
    reported_time_value: str | None
    reported_time_unit: TimeUnit | None
    reported_time_anchor: TimeAnchor | None
    normalized_time_days: str | None
    timepoint_window_id: UUID | None
    timepoint_rule_version: str | None
    measurement_scale_id: UUID | None
    direction_transformation: DirectionTransformation
    transformation_reason: str | None
    extraction_verified: bool
    supersedes_mapping_id: UUID | None

    @classmethod
    def from_domain(cls, item: OutcomeMapping) -> MappingResponse:
        return cls(**{name: getattr(item, name) for name in cls.model_fields})


class EstimateRequest(BaseModel):
    review_id: UUID
    study_id: UUID
    outcome_version_id: UUID
    effect_measure: EffectMeasure
    origin: EstimateOrigin
    estimate: Decimal | None = None
    standard_error: Decimal | None = None
    variance: Decimal | None = None
    variance_scale: VarianceScale | None = None
    ci_lower: Decimal | None = None
    ci_upper: Decimal | None = None
    confidence_level: Decimal | None = Field(default=None, gt=0, le=1)
    adjustment: AdjustmentStatus = AdjustmentStatus.UNADJUSTED
    analysis_population: AnalysisPopulation = AnalysisPopulation.UNCLEAR
    covariates: str | None = Field(default=None, max_length=20_000)
    model_description: str | None = Field(default=None, max_length=20_000)
    timepoint_window_id: UUID | None = None
    unit_id: UUID | None = None
    measurement_scale_id: UUID | None = None
    components: dict[str, Decimal] = {}
    source_mapping_ids: list[UUID]
    source_evidence_location_id: UUID | None = None


class EstimateResponse(BaseModel):
    id: UUID
    review_id: UUID
    study_id: UUID
    outcome_version_id: UUID
    effect_measure: EffectMeasure
    origin: EstimateOrigin
    estimate: str | None
    standard_error: str | None
    variance: str | None
    variance_scale: VarianceScale
    ci_lower: str | None
    ci_upper: str | None
    confidence_level: str | None
    adjustment: AdjustmentStatus
    analysis_population: AnalysisPopulation
    covariates: str | None
    model_description: str | None
    timepoint_window_id: UUID | None
    unit_id: UUID | None
    measurement_scale_id: UUID | None
    components: dict[str, str]
    source_mapping_ids: list[UUID]
    source_evidence_location_id: UUID | None
    calculation_version: str | None
    zero_event_pattern: str

    @classmethod
    def from_domain(cls, item: EffectEstimate) -> EstimateResponse:
        values = {name: getattr(item, name) for name in cls.model_fields}
        values["source_mapping_ids"] = list(item.source_mapping_ids)
        values["zero_event_pattern"] = item.zero_event_pattern.value
        return cls(**values)


class CandidateRequest(BaseModel):
    review_id: UUID
    outcome_version_id: UUID
    effect_measure: EffectMeasure
    timepoint_window_id: UUID | None = None
    population_label: str | None = Field(default=None, max_length=300)
    estimate_ids: list[UUID] = Field(min_length=1)


class CandidateResponse(BaseModel):
    id: UUID
    review_id: UUID
    outcome_version_id: UUID
    effect_measure: EffectMeasure
    timepoint_window_id: UUID | None
    population_label: str | None
    estimate_ids: list[UUID]

    @classmethod
    def from_domain(cls, item: SynthesisCandidateSet) -> CandidateResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            outcome_version_id=item.outcome_version_id,
            effect_measure=item.effect_measure,
            timepoint_window_id=item.timepoint_window_id,
            population_label=item.population_label,
            estimate_ids=list(item.estimate_ids),
        )


class ReadinessRequest(BaseModel):
    review_id: UUID


class ReadinessResponse(BaseModel):
    id: UUID
    review_id: UUID
    candidate_set_id: UUID
    algorithm_version: str
    status: str
    blockers: list[dict[str, Any]]

    @classmethod
    def from_domain(cls, item: AnalysisReadinessSnapshot) -> ReadinessResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            candidate_set_id=item.candidate_set_id,
            algorithm_version=item.algorithm_version,
            status=item.status.value,
            blockers=list(item.blockers),
        )


class CandidateListResponse(BaseModel):
    candidate_sets: list[CandidateResponse]
    readiness_snapshots: list[ReadinessResponse]


def _service(session: DbSessionDependency) -> OutcomeService:
    return OutcomeService(
        SqlAlchemyOutcomeRepository(session),
        SqlAlchemyStudyRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post("/definitions", response_model=OutcomeResponse, status_code=status.HTTP_201_CREATED)
async def create_outcome(
    payload: OutcomeRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> OutcomeResponse:
    item = await _service(session).create_outcome(actor, **payload.model_dump())
    await session.commit()
    return OutcomeResponse.from_domain(item)


@router.post(
    "/definitions-with-version",
    response_model=OutcomeWithVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_outcome_with_version(
    payload: OutcomeWithVersionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> OutcomeWithVersionResponse:
    service = _service(session)
    outcome = await service.create_outcome(
        actor,
        review_id=payload.review_id,
        key=payload.key,
    )
    version = await service.create_version(
        actor,
        review_id=payload.review_id,
        outcome_id=outcome.id,
        definition=payload.definition,
        protocol_version_id=payload.protocol_version_id,
    )
    await session.commit()
    return OutcomeWithVersionResponse(
        outcome=OutcomeResponse.from_domain(outcome),
        version=OutcomeVersionResponse.from_domain(version),
    )


@router.post(
    "/versions", response_model=OutcomeVersionResponse, status_code=status.HTTP_201_CREATED
)
async def create_version(
    payload: OutcomeVersionRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> OutcomeVersionResponse:
    item = await _service(session).create_version(actor, **payload.model_dump())
    await session.commit()
    return OutcomeVersionResponse.from_domain(item)


@router.get("/reviews/{review_id}", response_model=list[OutcomeResponse])
async def list_outcomes(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> list[OutcomeResponse]:
    return [
        OutcomeResponse.from_domain(item, versions)
        for item, versions in await _service(session).list_outcomes(actor, review_id=review_id)
    ]


@router.post("/timepoint-windows", status_code=status.HTTP_201_CREATED)
async def create_window(
    payload: TimepointWindowRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_timepoint_window(actor, **payload.model_dump())
    await session.commit()
    return _window(item)


@router.post("/units", status_code=status.HTTP_201_CREATED)
async def create_unit(
    payload: UnitRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_unit(actor, **payload.model_dump())
    await session.commit()
    return _unit(item)


@router.post("/measurement-scales", status_code=status.HTTP_201_CREATED)
async def create_scale(
    payload: ScaleRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_scale(actor, **payload.model_dump())
    await session.commit()
    return _scale(item)


@router.get("/reviews/{review_id}/configuration", response_model=ConfigurationResponse)
async def list_configuration(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> ConfigurationResponse:
    windows, units, scales = await _service(session).list_configuration(actor, review_id=review_id)
    return ConfigurationResponse(
        timepoint_windows=[_window(item) for item in windows],
        units=[_unit(item) for item in units],
        measurement_scales=[_scale(item) for item in scales],
    )


@router.post("/mappings", response_model=MappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    payload: MappingRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> MappingResponse:
    item = await _service(session).create_mapping(actor, **payload.model_dump())
    await session.commit()
    return MappingResponse.from_domain(item)


@router.get("/reviews/{review_id}/mappings", response_model=list[MappingResponse])
async def list_mappings(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> list[MappingResponse]:
    return [
        MappingResponse.from_domain(item)
        for item in await _service(session).list_mappings(actor, review_id=review_id)
    ]


@router.post(
    "/effect-estimates", response_model=EstimateResponse, status_code=status.HTTP_201_CREATED
)
async def create_estimate(
    payload: EstimateRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> EstimateResponse:
    item = await _service(session).create_effect_estimate(actor, **payload.model_dump())
    await session.commit()
    return EstimateResponse.from_domain(item)


@router.get("/reviews/{review_id}/effect-estimates", response_model=list[EstimateResponse])
async def list_estimates(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> list[EstimateResponse]:
    return [
        EstimateResponse.from_domain(item)
        for item in await _service(session).list_effect_estimates(actor, review_id=review_id)
    ]


@router.post(
    "/candidate-sets", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED
)
async def create_candidate(
    payload: CandidateRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> CandidateResponse:
    item = await _service(session).create_candidate_set(actor, **payload.model_dump())
    await session.commit()
    return CandidateResponse.from_domain(item)


@router.post(
    "/candidate-sets/{candidate_set_id}/evaluate",
    response_model=ReadinessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate(
    payload: ReadinessRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    candidate_set_id: Annotated[UUID, Path()],
) -> ReadinessResponse:
    item = await _service(session).evaluate_readiness(
        actor, candidate_set_id=candidate_set_id, **payload.model_dump()
    )
    await session.commit()
    return ReadinessResponse.from_domain(item)


@router.get("/reviews/{review_id}/candidate-sets", response_model=CandidateListResponse)
async def list_candidates(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> CandidateListResponse:
    candidates, snapshots = await _service(session).list_candidates(actor, review_id=review_id)
    return CandidateListResponse(
        candidate_sets=[CandidateResponse.from_domain(item) for item in candidates],
        readiness_snapshots=[ReadinessResponse.from_domain(item) for item in snapshots],
    )


def _window(item: TimepointWindow) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "key": item.key,
        "label": item.label,
        "anchor": item.anchor.value,
        "minimum_days": item.minimum_days,
        "maximum_days": item.maximum_days,
        "rule_version": item.rule_version,
    }


def _unit(item: UnitDefinition) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "key": item.key,
        "label": item.label,
        "dimension": item.dimension,
        "context_key": item.context_key,
        "base_unit_key": item.base_unit_key,
        "multiplier_to_base": item.multiplier_to_base,
        "offset_to_base": item.offset_to_base,
        "precision": item.precision,
        "rule_version": item.rule_version,
    }


def _scale(item: MeasurementScale) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "key": item.key,
        "name": item.name,
        "minimum": item.minimum,
        "maximum": item.maximum,
        "directionality": item.directionality.value,
    }
