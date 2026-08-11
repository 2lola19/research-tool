from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.risk_of_bias.domain import (
    AssessmentStatus,
    ComparisonStatus,
    InstrumentDecision,
    RiskOfBiasAssessment,
    RiskOfBiasComparison,
    RiskOfBiasInstrument,
    RiskOfBiasInstrumentVersion,
)
from backend.app.risk_of_bias.fixtures import DEMONSTRATION_RCT_INSTRUMENT
from backend.app.risk_of_bias.persistence import SqlAlchemyRiskOfBiasRepository
from backend.app.risk_of_bias.service import RiskOfBiasService
from backend.app.studies.persistence import SqlAlchemyStudyRepository

router = APIRouter(prefix="/risk-of-bias", tags=["risk-of-bias"])


class InstrumentRequest(BaseModel):
    review_id: UUID
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)


class VersionRequest(BaseModel):
    review_id: UUID
    instrument_id: UUID
    definition: dict[str, Any]


class DecisionRequest(BaseModel):
    review_id: UUID
    decision: InstrumentDecision
    reason: str | None = Field(default=None, max_length=10_000)


class DemonstrationRequest(BaseModel):
    review_id: UUID


class VersionResponse(BaseModel):
    id: UUID
    instrument_id: UUID
    version: int
    definition: dict[str, Any]
    content_hash: str
    decision: InstrumentDecision | None

    @classmethod
    def from_domain(cls, item: RiskOfBiasInstrumentVersion) -> VersionResponse:
        return cls(
            id=item.id,
            instrument_id=item.instrument_id,
            version=item.version,
            definition=item.definition,
            content_hash=item.content_hash,
            decision=item.decision,
        )


class InstrumentResponse(BaseModel):
    id: UUID
    review_id: UUID
    key: str
    name: str
    description: str | None
    versions: list[VersionResponse] = []

    @classmethod
    def from_domain(
        cls, item: RiskOfBiasInstrument, versions: list[RiskOfBiasInstrumentVersion] | None = None
    ) -> InstrumentResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            key=item.key,
            name=item.name,
            description=item.description,
            versions=[VersionResponse.from_domain(version) for version in versions or []],
        )


class DemonstrationResponse(BaseModel):
    instrument: InstrumentResponse
    version: VersionResponse


class AssessmentCreateRequest(BaseModel):
    review_id: UUID
    study_id: UUID
    instrument_version_id: UUID
    round_number: int = Field(default=1, ge=1)
    supersedes_assessment_id: UUID | None = None


class AnswerRequest(BaseModel):
    review_id: UUID
    answer: str = Field(min_length=1, max_length=120)
    rationale: str | None = Field(default=None, max_length=20_000)
    evidence_location_id: UUID | None = None


class DomainJudgmentRequest(BaseModel):
    review_id: UUID
    final_judgment: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=20_000)
    override_reason: str | None = Field(default=None, max_length=20_000)
    evidence_location_id: UUID | None = None


class OverallJudgmentRequest(DomainJudgmentRequest):
    pass


class AssessmentResponse(BaseModel):
    id: UUID
    review_id: UUID
    study_id: UUID
    instrument_version_id: UUID
    assessor_user_id: UUID
    round_number: int
    revision: int
    supersedes_assessment_id: UUID | None
    status: AssessmentStatus
    overall_suggested_judgment: str | None
    overall_final_judgment: str | None
    overall_rationale: str | None
    answers: list[dict[str, Any]]
    domain_judgments: list[dict[str, Any]]

    @classmethod
    def from_domain(cls, item: RiskOfBiasAssessment) -> AssessmentResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            study_id=item.study_id,
            instrument_version_id=item.instrument_version_id,
            assessor_user_id=item.assessor_user_id,
            round_number=item.round_number,
            revision=item.revision,
            supersedes_assessment_id=item.supersedes_assessment_id,
            status=item.status,
            overall_suggested_judgment=item.overall_suggested_judgment,
            overall_final_judgment=item.overall_final_judgment,
            overall_rationale=item.overall_rationale,
            answers=[
                {
                    "id": str(answer.id),
                    "question_key": answer.question_key,
                    "answer": answer.answer,
                    "rationale": answer.rationale,
                    "evidence_location_id": (
                        str(answer.evidence_location_id) if answer.evidence_location_id else None
                    ),
                }
                for answer in item.answers
            ],
            domain_judgments=[
                {
                    "id": str(domain.id),
                    "domain_key": domain.domain_key,
                    "suggested_judgment": domain.suggested_judgment,
                    "final_judgment": domain.final_judgment,
                    "rationale": domain.rationale,
                    "override_reason": domain.override_reason,
                    "evidence_location_id": (
                        str(domain.evidence_location_id) if domain.evidence_location_id else None
                    ),
                }
                for domain in item.domain_judgments
            ],
        )


class CompareRequest(BaseModel):
    review_id: UUID
    assessment_a_id: UUID
    assessment_b_id: UUID


class AdjudicationRequest(BaseModel):
    review_id: UUID
    resolution_assessment_id: UUID
    rationale: str = Field(min_length=1, max_length=20_000)
    evidence_location_id: UUID | None = None


class ComparisonResponse(BaseModel):
    id: UUID
    review_id: UUID
    study_id: UUID
    instrument_version_id: UUID
    round_number: int
    assessment_a_id: UUID
    assessment_b_id: UUID
    status: ComparisonStatus
    differences: list[dict[str, Any]]
    adjudicated_snapshot: dict[str, Any] | None
    adjudicated_by_user_id: UUID | None
    adjudication_reason: str | None

    @classmethod
    def from_domain(cls, item: RiskOfBiasComparison) -> ComparisonResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            study_id=item.study_id,
            instrument_version_id=item.instrument_version_id,
            round_number=item.round_number,
            assessment_a_id=item.assessment_a_id,
            assessment_b_id=item.assessment_b_id,
            status=item.status,
            differences=list(item.differences),
            adjudicated_snapshot=item.adjudicated_snapshot,
            adjudicated_by_user_id=item.adjudicated_by_user_id,
            adjudication_reason=item.adjudication_reason,
        )


def _service(session: DbSessionDependency) -> RiskOfBiasService:
    return RiskOfBiasService(
        SqlAlchemyRiskOfBiasRepository(session),
        SqlAlchemyStudyRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post("/instruments", response_model=InstrumentResponse, status_code=status.HTTP_201_CREATED)
async def create_instrument(
    payload: InstrumentRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> InstrumentResponse:
    item = await _service(session).create_instrument(actor, **payload.model_dump())
    await session.commit()
    return InstrumentResponse.from_domain(item)


@router.post(
    "/instrument-versions", response_model=VersionResponse, status_code=status.HTTP_201_CREATED
)
async def create_version(
    payload: VersionRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> VersionResponse:
    item = await _service(session).create_version(actor, **payload.model_dump())
    await session.commit()
    return VersionResponse.from_domain(item)


@router.post("/instrument-versions/{version_id}/decision", response_model=VersionResponse)
async def decide_version(
    payload: DecisionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    version_id: Annotated[UUID, Path()],
) -> VersionResponse:
    item = await _service(session).decide_version(
        actor, version_id=version_id, **payload.model_dump()
    )
    await session.commit()
    return VersionResponse.from_domain(item)


@router.post(
    "/demonstration-instrument",
    response_model=DemonstrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def install_demonstration_instrument(
    payload: DemonstrationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> DemonstrationResponse:
    service = _service(session)
    instrument = await service.create_instrument(
        actor,
        review_id=payload.review_id,
        key="DEMO_RCT",
        name="Demonstration RCT Risk of Bias Instrument",
        description="Framework-validation instrument; not a complete implementation of RoB 2.",
    )
    version = await service.create_version(
        actor,
        review_id=payload.review_id,
        instrument_id=instrument.id,
        definition=DEMONSTRATION_RCT_INSTRUMENT,
    )
    await session.commit()
    return DemonstrationResponse(
        instrument=InstrumentResponse.from_domain(instrument, [version]),
        version=VersionResponse.from_domain(version),
    )


@router.get("/reviews/{review_id}/instruments", response_model=list[InstrumentResponse])
async def list_instruments(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[InstrumentResponse]:
    items = await _service(session).list_instruments(actor, review_id=review_id)
    return [InstrumentResponse.from_domain(item, versions) for item, versions in items]


@router.post("/assessments", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    payload: AssessmentCreateRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> AssessmentResponse:
    item = await _service(session).create_assessment(actor, **payload.model_dump())
    await session.commit()
    return AssessmentResponse.from_domain(item)


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> AssessmentResponse:
    item = await _service(session).get_assessment(
        actor, review_id=review_id, assessment_id=assessment_id
    )
    return AssessmentResponse.from_domain(item)


@router.get("/reviews/{review_id}/assessments", response_model=list[AssessmentResponse])
async def list_assessments(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[AssessmentResponse]:
    items = await _service(session).list_assessments(actor, review_id=review_id)
    return [AssessmentResponse.from_domain(item) for item in items]


@router.put(
    "/assessments/{assessment_id}/answers/{question_key}", response_model=AssessmentResponse
)
async def save_answer(
    payload: AnswerRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
    question_key: Annotated[str, Path()],
) -> AssessmentResponse:
    item = await _service(session).save_answer(
        actor, assessment_id=assessment_id, question_key=question_key, **payload.model_dump()
    )
    await session.commit()
    return AssessmentResponse.from_domain(item)


@router.put("/assessments/{assessment_id}/domains/{domain_key}", response_model=AssessmentResponse)
async def save_domain(
    payload: DomainJudgmentRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
    domain_key: Annotated[str, Path()],
) -> AssessmentResponse:
    item = await _service(session).save_domain_judgment(
        actor, assessment_id=assessment_id, domain_key=domain_key, **payload.model_dump()
    )
    await session.commit()
    return AssessmentResponse.from_domain(item)


@router.put("/assessments/{assessment_id}/overall", response_model=AssessmentResponse)
async def save_overall(
    payload: OverallJudgmentRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
) -> AssessmentResponse:
    item = await _service(session).save_overall(
        actor, assessment_id=assessment_id, **payload.model_dump()
    )
    await session.commit()
    return AssessmentResponse.from_domain(item)


@router.post("/assessments/{assessment_id}/submit", response_model=AssessmentResponse)
async def submit_assessment(
    payload: DemonstrationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
) -> AssessmentResponse:
    item = await _service(session).submit(
        actor, review_id=payload.review_id, assessment_id=assessment_id
    )
    await session.commit()
    return AssessmentResponse.from_domain(item)


@router.post("/comparisons", response_model=ComparisonResponse, status_code=status.HTTP_201_CREATED)
async def compare_assessments(
    payload: CompareRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> ComparisonResponse:
    item = await _service(session).compare(actor, **payload.model_dump())
    await session.commit()
    return ComparisonResponse.from_domain(item)


@router.get("/reviews/{review_id}/comparisons", response_model=list[ComparisonResponse])
async def list_comparisons(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[ComparisonResponse]:
    items = await _service(session).list_comparisons(actor, review_id=review_id)
    return [ComparisonResponse.from_domain(item) for item in items]


@router.post("/comparisons/{comparison_id}/adjudicate", response_model=ComparisonResponse)
async def adjudicate(
    payload: AdjudicationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    comparison_id: Annotated[UUID, Path()],
) -> ComparisonResponse:
    item = await _service(session).adjudicate(
        actor, comparison_id=comparison_id, **payload.model_dump()
    )
    await session.commit()
    return ComparisonResponse.from_domain(item)
