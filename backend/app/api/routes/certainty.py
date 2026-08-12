from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.analysis.engine import NativeDeterministicSynthesisEngine
from backend.app.analysis.persistence import SqlAlchemyAnalysisRepository
from backend.app.analysis.service import AnalysisService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.certainty.domain import CertaintyLevel, EvidenceBodyType
from backend.app.certainty.fixtures import GRADE_COMPATIBLE_FOUNDATION
from backend.app.certainty.persistence import SqlAlchemyCertaintyRepository
from backend.app.certainty.service import CertaintyService
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.outcomes.persistence import SqlAlchemyOutcomeRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.risk_of_bias.persistence import SqlAlchemyRiskOfBiasRepository

router = APIRouter(prefix="/certainty", tags=["certainty"])


class FrameworkRequest(BaseModel):
    review_id: UUID
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)


class FrameworkVersionRequest(BaseModel):
    review_id: UUID
    framework_id: UUID
    definition: dict[str, Any]


class ReviewRequest(BaseModel):
    review_id: UUID


class ThresholdRequest(BaseModel):
    review_id: UUID
    outcome_version_id: UUID
    definition: dict[str, Any]


class AssessmentRequest(BaseModel):
    review_id: UUID
    outcome_version_id: UUID
    timepoint_window_id: UUID | None = None
    analysis_specification_version_id: UUID | None = None
    meta_analysis_run_id: UUID | None = None
    framework_version_id: UUID
    threshold_version_id: UUID | None = None
    round_number: int = Field(default=1, ge=1)
    evidence_body_type: EvidenceBodyType
    evidence_body: dict[str, Any]
    starting_certainty: CertaintyLevel
    starting_rationale: str = Field(min_length=1, max_length=20_000)
    supersedes_assessment_id: UUID | None = None


class DomainRequest(BaseModel):
    review_id: UUID
    judgment: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=20_000)
    evidence_location_id: UUID | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class FinalRequest(BaseModel):
    review_id: UUID
    final_certainty: CertaintyLevel
    final_rationale: str = Field(min_length=1, max_length=20_000)
    override_reason: str | None = Field(default=None, max_length=20_000)


class CompareRequest(BaseModel):
    review_id: UUID
    assessment_a_id: UUID
    assessment_b_id: UUID


class AdjudicateRequest(BaseModel):
    review_id: UUID
    resolution_assessment_id: UUID
    rationale: str = Field(min_length=1, max_length=20_000)
    evidence_location_id: UUID | None = None


def _service(session: DbSessionDependency) -> CertaintyService:
    analyses = SqlAlchemyAnalysisRepository(session)
    outcomes = SqlAlchemyOutcomeRepository(session)
    reviews = SqlAlchemyReviewRepository(session)
    identity = SqlAlchemyIdentityRepository(session)
    provenance = SqlAlchemyProvenanceRepository(session)
    analysis_service = AnalysisService(
        analyses,
        outcomes,
        NativeDeterministicSynthesisEngine(),
        reviews,
        identity,
        provenance,
    )
    return CertaintyService(
        SqlAlchemyCertaintyRepository(session),
        outcomes,
        analyses,
        analysis_service,
        SqlAlchemyRiskOfBiasRepository(session),
        reviews,
        identity,
        provenance,
    )


@router.post("/frameworks", status_code=status.HTTP_201_CREATED)
async def create_framework(
    payload: FrameworkRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_framework(actor, **payload.model_dump())
    await session.commit()
    return _framework(item)


@router.post("/framework-versions", status_code=status.HTTP_201_CREATED)
async def create_framework_version(
    payload: FrameworkVersionRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_framework_version(actor, **payload.model_dump())
    await session.commit()
    return _framework_version(item)


@router.post("/foundation-framework", status_code=status.HTTP_201_CREATED)
async def install_foundation(
    payload: ReviewRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    service = _service(session)
    framework = await service.create_framework(
        actor,
        review_id=payload.review_id,
        key="GRADE_FOUNDATION",
        name="GRADE-compatible Certainty Foundation",
        description="Human-first structured foundation; not complete official GRADE guidance.",
    )
    version = await service.create_framework_version(
        actor,
        review_id=payload.review_id,
        framework_id=framework.id,
        definition=GRADE_COMPATIBLE_FOUNDATION,
    )
    await session.commit()
    return {"framework": _framework(framework), "version": _framework_version(version)}


@router.post("/threshold-versions", status_code=status.HTTP_201_CREATED)
async def create_threshold(
    payload: ThresholdRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_threshold_version(actor, **payload.model_dump())
    await session.commit()
    return _threshold(item)


@router.post("/assessments", status_code=status.HTTP_201_CREATED)
async def create_assessment(
    payload: AssessmentRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_assessment(actor, **payload.model_dump())
    await session.commit()
    return _assessment(item, stale=False)


@router.put("/assessments/{assessment_id}/domains/{domain_key}")
async def save_domain(
    payload: DomainRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
    domain_key: Annotated[str, Path()],
) -> dict[str, Any]:
    item = await _service(session).save_domain(
        actor, assessment_id=assessment_id, domain_key=domain_key, **payload.model_dump()
    )
    await session.commit()
    return _assessment(item, stale=False)


@router.put("/assessments/{assessment_id}/final")
async def save_final(
    payload: FinalRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).save_final(
        actor, assessment_id=assessment_id, **payload.model_dump()
    )
    await session.commit()
    return _assessment(item, stale=False)


@router.post("/assessments/{assessment_id}/submit")
async def submit_assessment(
    payload: ReviewRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).submit(
        actor, review_id=payload.review_id, assessment_id=assessment_id
    )
    await session.commit()
    return _assessment(item, stale=False)


@router.get("/assessments/{assessment_id}/evidence-profile")
async def evidence_profile(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> dict[str, Any]:
    return await _service(session).evidence_profile(
        actor, review_id=review_id, assessment_id=assessment_id
    )


@router.post("/comparisons", status_code=status.HTTP_201_CREATED)
async def compare(
    payload: CompareRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).compare(actor, **payload.model_dump())
    await session.commit()
    return _comparison(item)


@router.post("/comparisons/{comparison_id}/adjudicate")
async def adjudicate(
    payload: AdjudicateRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    comparison_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).adjudicate(
        actor, comparison_id=comparison_id, **payload.model_dump()
    )
    await session.commit()
    return _comparison(item)


@router.post("/assessments/{assessment_id}/sof-snapshot", status_code=status.HTTP_201_CREATED)
async def create_sof(
    payload: ReviewRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assessment_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    item = await _service(session).create_sof_snapshot(
        actor, review_id=payload.review_id, assessment_id=assessment_id
    )
    await session.commit()
    return _sof(item)


@router.get("/reviews/{review_id}")
async def workspace(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> dict[str, Any]:
    service = _service(session)
    frameworks, thresholds, assessments, comparisons, sof = await service.list_workspace(
        actor, review_id=review_id
    )
    blind_candidates = await service.list_blind_comparison_candidates(actor, review_id=review_id)
    return {
        "frameworks": [
            {**_framework(item), "versions": [_framework_version(version) for version in versions]}
            for item, versions in frameworks
        ],
        "threshold_versions": [_threshold(item) for item in thresholds],
        "assessments": [_assessment(item, stale=stale) for item, stale in assessments],
        "comparisons": [_comparison(item) for item in comparisons],
        "comparison_candidates": blind_candidates,
        "summary_of_findings": [_sof(item) for item in sof],
    }


def _framework(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "review_id": str(item.review_id),
        "key": item.key,
        "name": item.name,
        "description": item.description,
    }


def _framework_version(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "framework_id": str(item.framework_id),
        "version": item.version,
        "definition": item.definition,
        "content_hash": item.content_hash,
    }


def _threshold(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "outcome_version_id": str(item.outcome_version_id),
        "version": item.version,
        "definition": item.definition,
        "content_hash": item.content_hash,
    }


def _assessment(item: Any, *, stale: bool) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "review_id": str(item.review_id),
        "outcome_version_id": str(item.outcome_version_id),
        "timepoint_window_id": str(item.timepoint_window_id) if item.timepoint_window_id else None,
        "analysis_specification_version_id": str(item.analysis_specification_version_id)
        if item.analysis_specification_version_id
        else None,
        "meta_analysis_run_id": str(item.meta_analysis_run_id)
        if item.meta_analysis_run_id
        else None,
        "framework_version_id": str(item.framework_version_id),
        "threshold_version_id": str(item.threshold_version_id)
        if item.threshold_version_id
        else None,
        "assessor_user_id": str(item.assessor_user_id),
        "round_number": item.round_number,
        "revision": item.revision,
        "supersedes_assessment_id": str(item.supersedes_assessment_id)
        if item.supersedes_assessment_id
        else None,
        "evidence_body_type": item.evidence_body_type.value,
        "evidence_body": item.evidence_body,
        "starting_certainty": item.starting_certainty.value,
        "starting_rationale": item.starting_rationale,
        "status": item.status.value,
        "candidate_certainty": item.candidate_certainty.value if item.candidate_certainty else None,
        "final_certainty": item.final_certainty.value if item.final_certainty else None,
        "final_rationale": item.final_rationale,
        "override_reason": item.override_reason,
        "evidence_hash": item.evidence_hash,
        "stale": stale,
        "domain_judgments": [
            {
                "id": str(domain.id),
                "domain_key": domain.domain_key,
                "direction": domain.direction.value,
                "magnitude": domain.magnitude,
                "judgment": domain.judgment,
                "rationale": domain.rationale,
                "evidence_location_id": str(domain.evidence_location_id)
                if domain.evidence_location_id
                else None,
                "evidence": domain.evidence,
            }
            for domain in item.domain_judgments
        ],
    }


def _comparison(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "outcome_version_id": str(item.outcome_version_id),
        "framework_version_id": str(item.framework_version_id),
        "round_number": item.round_number,
        "assessment_a_id": str(item.assessment_a_id),
        "assessment_b_id": str(item.assessment_b_id),
        "status": item.status.value,
        "differences": list(item.differences),
        "adjudicated_snapshot": item.adjudicated_snapshot,
        "adjudicated_by_user_id": str(item.adjudicated_by_user_id)
        if item.adjudicated_by_user_id
        else None,
        "adjudication_reason": item.adjudication_reason,
    }


def _sof(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "assessment_id": str(item.assessment_id),
        "model_version": item.model_version,
        "row": item.row,
        "content_hash": item.content_hash,
        "created_at": item.created_at.isoformat(),
    }
