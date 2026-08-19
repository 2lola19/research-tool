from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.ai.domain import content_hash
from backend.app.prisma.domain import PrismaReadiness, PrismaSummary
from backend.app.reviews.domain import ReviewProject
from backend.app.workflow.domain import WorkflowJob, WorkflowRun

COPILOT_CONTEXT_VERSION = "review-copilot-context-1"
COPILOT_VALIDATOR_VERSION = "review-copilot-validator-1"


class AICopilotTaskKey(StrEnum):
    PROJECT_STATUS = "PROJECT_STATUS"
    WORKFLOW_BLOCKERS = "WORKFLOW_BLOCKERS"
    PROVENANCE_NAVIGATION = "PROVENANCE_NAVIGATION"


class AICopilotQueryStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"
    INVALID_OUTPUT = "INVALID_OUTPUT"


@dataclass(frozen=True, slots=True)
class AICopilotPolicy:
    id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    maximum_query_characters: int
    maximum_context_items: int
    created_by_user_id: UUID


@dataclass(frozen=True, slots=True)
class AICopilotQuery:
    id: UUID
    organization_id: UUID
    review_id: UUID
    task_key: AICopilotTaskKey
    query_text: str
    context_snapshot: dict[str, Any]
    context_hash: str
    citations: tuple[dict[str, Any], ...]
    ai_run_id: UUID | None
    proposal_id: UUID | None
    answer_snapshot: dict[str, Any] | None
    validation_results: dict[str, Any]
    status: AICopilotQueryStatus
    failure_reason: str | None
    created_by_user_id: UUID
    created_at: datetime
    stale: bool = False
    stale_reasons: tuple[str, ...] = ()


def copilot_task_registry() -> list[dict[str, Any]]:
    return [
        {
            "task_key": AICopilotTaskKey.PROJECT_STATUS.value,
            "label": "Project status",
            "description": (
                "Explain deterministic review progress and readiness from cited records."
            ),
            "read_only": True,
        },
        {
            "task_key": AICopilotTaskKey.WORKFLOW_BLOCKERS.value,
            "label": "Workflow blockers",
            "description": "Locate paused, failed, awaiting-human, or incomplete workflow work.",
            "read_only": True,
        },
        {
            "task_key": AICopilotTaskKey.PROVENANCE_NAVIGATION.value,
            "label": "Provenance navigation",
            "description": "Point to the canonical records supporting a project-status answer.",
            "read_only": True,
        },
    ]


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def build_copilot_context(
    review: ReviewProject,
    summary: PrismaSummary,
    readiness: PrismaReadiness,
    source_references: dict[str, Any],
    workflow_runs: Sequence[WorkflowRun],
    workflow_jobs: Sequence[WorkflowJob],
    *,
    maximum_context_items: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Build a bounded, deterministic, read-only context snapshot.

    Workflow payloads are deliberately excluded. The model receives only allowlisted
    identifiers and state metadata; it has no retrieval or mutation authority.
    """
    limit = max(1, min(maximum_context_items, 200))
    ordered_runs = sorted(workflow_runs, key=lambda item: (item.created_at, item.id))[:limit]
    ordered_jobs = sorted(workflow_jobs, key=lambda item: (item.created_at, item.id))[:limit]

    run_context: list[dict[str, Any]] = [
        {
            "run_id": str(item.id),
            "workflow_name": item.workflow_name,
            "workflow_version": item.workflow_version,
            "state": item.state.value,
            "created_at": _timestamp(item.created_at),
            "updated_at": _timestamp(item.updated_at),
        }
        for item in ordered_runs
    ]
    job_context: list[dict[str, Any]] = [
        {
            "job_id": str(item.id),
            "workflow_run_id": str(item.workflow_run_id),
            "task_name": item.task_name,
            "task_version": item.task_version,
            "state": item.state.value,
            "paused_from_state": item.paused_from_state.value
            if item.paused_from_state is not None
            else None,
            "attempt": item.attempt,
            "created_at": _timestamp(item.created_at),
            "updated_at": _timestamp(item.updated_at),
        }
        for item in ordered_jobs
    ]

    workflow_blockers: list[dict[str, Any]] = [
        {
            "kind": "workflow_run",
            "record_id": item["run_id"],
            "state": item["state"],
            "reason": "workflow run requires attention",
        }
        for item in run_context
        if item["state"] in {"PAUSED", "FAILED"}
    ]
    workflow_blockers.extend(
        {
            "kind": "workflow_job",
            "record_id": item["job_id"],
            "state": item["state"],
            "reason": "workflow job requires attention",
        }
        for item in job_context
        if item["state"] in {"PAUSED", "FAILED", "AWAITING_HUMAN"}
    )

    context = {
        "context_version": COPILOT_CONTEXT_VERSION,
        "review": {
            "review_id": str(review.id),
            "title": review.title[:300],
            "project_slug": review.project_slug,
            "description": review.description[:1_000] if review.description else None,
            "archived": review.archived_at is not None,
            "updated_at": _timestamp(review.updated_at),
        },
        "prisma": {
            "summary": summary.as_dict(),
            "readiness": readiness.as_dict(),
        },
        "workflow": {"runs": run_context, "jobs": job_context},
        "derived_blockers": {
            "prisma": [item.as_dict() for item in readiness.blockers],
            "workflow": workflow_blockers[:limit],
        },
        "source_reference_counts": {
            key: len(value) if isinstance(value, list) else 1
            for key, value in sorted(source_references.items())
        },
    }

    citations: list[dict[str, Any]] = [
        {
            "citation_id": "review-project",
            "source_type": "REVIEW_PROJECT",
            "source_id": str(review.id),
            "label": "Review project metadata",
            "locator": {"review_id": str(review.id)},
        },
        {
            "citation_id": "prisma-summary",
            "source_type": "PRISMA_SUMMARY",
            "source_id": str(review.id),
            "label": "Deterministic PRISMA summary and readiness",
            "locator": {"algorithm_version": "prisma-2020-deterministic-2"},
        },
    ]
    citations.extend(
        {
            "citation_id": f"workflow-run:{item['run_id']}",
            "source_type": "WORKFLOW_RUN",
            "source_id": item["run_id"],
            "label": item["workflow_name"],
            "locator": {"workflow_version": item["workflow_version"]},
        }
        for item in run_context
    )
    citations.extend(
        {
            "citation_id": f"workflow-job:{item['job_id']}",
            "source_type": "WORKFLOW_JOB",
            "source_id": item["job_id"],
            "label": item["task_name"],
            "locator": {"workflow_run_id": item["workflow_run_id"]},
        }
        for item in job_context
    )
    for key, value in sorted(source_references.items()):
        citations.append(
            {
                "citation_id": f"prisma-source:{key}",
                "source_type": "PRISMA_SOURCE_SET",
                "source_id": str(review.id),
                "label": f"PRISMA source set: {key}",
                "locator": {
                    "reference_key": key,
                    "item_count": len(value) if isinstance(value, list) else 1,
                },
            }
        )
    citations = citations[: max(2, limit)]
    return context, citations, content_hash({"context": context, "citations": citations})


def validate_copilot_output(
    value: dict[str, Any], input_data: dict[str, Any]
) -> list[dict[str, str]]:
    """Validate citation-grounded prose without permitting scientific or workflow writes."""
    errors: list[dict[str, str]] = []
    answer = value.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        errors.append({"code": "EMPTY_ANSWER", "message": "answer must be bounded text"})
    elif len(answer) > 6_000:
        errors.append({"code": "ANSWER_TOO_LARGE", "message": "answer exceeds 6000 characters"})

    available = {
        str(item.get("citation_id"))
        for item in input_data.get("citations", [])
        if isinstance(item, dict) and item.get("citation_id")
    }
    citations = value.get("citations")
    if not isinstance(citations, list):
        errors.append({"code": "INVALID_CITATIONS", "message": "citations must be a list"})
        citations = []
    if len(citations) > 12:
        errors.append({"code": "TOO_MANY_CITATIONS", "message": "at most 12 citations are allowed"})
    cited_ids: set[str] = set()
    for item in citations:
        if not isinstance(item, dict):
            errors.append(
                {"code": "INVALID_CITATION", "message": "each citation must be an object"}
            )
            continue
        citation_id = item.get("citation_id")
        claim = item.get("claim")
        if not isinstance(citation_id, str) or citation_id not in available:
            errors.append(
                {
                    "code": "UNKNOWN_CITATION",
                    "message": "citation is not in the supplied context",
                }
            )
        else:
            cited_ids.add(citation_id)
        if not isinstance(claim, str) or not claim.strip() or len(claim) > 1_000:
            errors.append(
                {"code": "INVALID_CITATION_CLAIM", "message": "citation claim is invalid"}
            )

    abstention = value.get("abstention")
    if abstention is not None and (
        not isinstance(abstention, str) or not abstention.strip() or len(abstention) > 500
    ):
        errors.append({"code": "INVALID_ABSTENTION", "message": "abstention must be bounded text"})
    uncertainty = value.get("uncertainty_reason")
    if uncertainty is not None and (
        not isinstance(uncertainty, str) or not uncertainty.strip() or len(uncertainty) > 1_000
    ):
        errors.append(
            {
                "code": "INVALID_UNCERTAINTY_REASON",
                "message": "uncertainty reason is invalid",
            }
        )
    if abstention is not None and uncertainty is None:
        errors.append(
            {
                "code": "ABSTENTION_REASON_REQUIRED",
                "message": "abstention requires an uncertainty reason",
            }
        )
    if abstention is None and not cited_ids:
        errors.append(
            {
                "code": "CITATIONS_REQUIRED",
                "message": "non-abstaining answers require citations",
            }
        )

    confidence = value.get("model_reported_confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        errors.append(
            {
                "code": "INVALID_CONFIDENCE",
                "message": "confidence must be from 0 through 1",
            }
        )

    forbidden = {
        "canonical_write",
        "workflow_transition",
        "scientific_calculation",
        "final_decision",
        "manuscript_draft",
    }
    for key in sorted(set(value) & forbidden):
        errors.append({"code": "UNSUPPORTED_ACTION", "message": f"AI cannot provide {key}"})
    return errors
