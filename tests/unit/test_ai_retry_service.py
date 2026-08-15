from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.app.ai.domain import (
    AIOutputProposal,
    AIProposalState,
    AIProviderErrorKind,
    AIRun,
    AIRunState,
    AITaskType,
    ModelVersion,
    PromptTemplateVersion,
)
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.service import AIExecutionService
from backend.app.identity.domain import ActorContext, OrganizationRole


class FakeRepository:
    def __init__(self, actor: ActorContext) -> None:
        now = datetime.now(UTC)
        self.model = ModelVersion(
            id=uuid4(),
            organization_id=actor.organization_id,
            provider_key="mock",
            model_identifier="mock-v1",
            display_name="Mock",
            configuration_version=1,
            capabilities=("structured_generation",),
            structured_output_supported=True,
            context_window=4096,
            pricing={},
            active=True,
            deprecated=False,
            content_hash="m" * 64,
            created_at=now,
        )
        self.prompt = PromptTemplateVersion(
            id=uuid4(),
            organization_id=actor.organization_id,
            prompt_key="search",
            version=1,
            purpose="test",
            task_type=AITaskType.SEARCH_QUERY_SUGGESTION,
            system_instructions="Return structured output.",
            user_template="Objective: {objective}; Query: {query}",
            output_schema={},
            validation_requirements={},
            status="ACTIVE",
            content_hash="p" * 64,
            created_by_user_id=actor.user_id,
            created_at=now,
        )
        self.run: AIRun | None = None
        self.attempts: list[dict[str, Any]] = []

    async def list_models(self, organization_id: UUID) -> list[ModelVersion]:
        return [self.model]

    async def list_prompts(self, organization_id: UUID) -> list[PromptTemplateVersion]:
        return [self.prompt]

    async def find_identical_run(self, *args: Any) -> None:
        return None

    async def create_run(self, **values: Any) -> AIRun:
        self.run = AIRun(
            id=uuid4(),
            organization_id=values["organization_id"],
            review_id=values["review_id"],
            task_type=AITaskType(values["task_type"]),
            task_definition_key=values["task_definition_key"],
            task_definition_version=values["task_definition_version"],
            prompt_version_id=values["prompt_version_id"],
            model_version_id=values["model_version_id"],
            input_snapshot=values["input_snapshot"],
            input_hash=values["input_hash"],
            rendered_prompt_hash=values["rendered_prompt_hash"],
            state=AIRunState(values["state"]),
            identical_prior_run_id=None,
            created_by_user_id=values["created_by_user_id"],
            created_at=datetime.now(UTC),
            completed_at=None,
        )
        return self.run

    async def update_run(
        self, run_id: UUID, organization_id: UUID, review_id: UUID, **values: Any
    ) -> AIRun:
        assert self.run is not None
        converted = {**values}
        if "state" in converted:
            converted["state"] = AIRunState(converted["state"])
        converted.pop("failure_reason", None)
        self.run = replace(self.run, **converted)
        return self.run

    async def append_attempt(self, **values: Any) -> None:
        self.attempts.append(values)

    async def append_validation(self, **values: Any) -> None:
        return None

    async def create_proposal(self, **values: Any) -> AIOutputProposal:
        return AIOutputProposal(
            id=uuid4(),
            organization_id=values["organization_id"],
            review_id=values["review_id"],
            ai_run_id=values["ai_run_id"],
            task_type=AITaskType(values["task_type"]),
            target_type=values["target_type"],
            target_id=values["target_id"],
            structured_value=values["structured_value"],
            evidence_references=tuple(values["evidence_references"]),
            model_reported_confidence=values["model_reported_confidence"],
            response_hash=values["response_hash"],
            state=AIProposalState.PENDING_REVIEW,
            created_at=datetime.now(UTC),
        )


class FakeReviews:
    async def get(self, actor: ActorContext, review_id: UUID) -> object:
        return object()


class FakeProvenance:
    async def append_audit_event(self, **values: Any) -> None:
        return None


def _actor() -> ActorContext:
    return ActorContext(
        user_id=uuid4(), organization_id=uuid4(), membership_id=uuid4(), role=OrganizationRole.OWNER
    )


def _valid_output() -> dict[str, Any]:
    return {
        "query": "q",
        "rationale": "r",
        "evidence_references": [],
        "model_reported_confidence": None,
        "abstention": "NEEDS_HUMAN_REVIEW",
    }


@pytest.mark.asyncio
async def test_transient_retry_preserves_attempt_history_and_then_succeeds() -> None:
    actor = _actor()
    repository = FakeRepository(actor)
    service = AIExecutionService(
        repository,
        FakeReviews(),
        FakeProvenance(),
        {"mock": DeterministicMockAIProvider([AIProviderErrorKind.TIMEOUT, _valid_output()])},
    )  # type: ignore[arg-type]
    run, proposal = await service.create_and_execute(
        actor,
        review_id=uuid4(),
        task_type=AITaskType.SEARCH_QUERY_SUGGESTION,
        input_data={"query": "q", "objective": "o"},
        maximum_attempts=2,
    )
    assert run.state is AIRunState.SUCCEEDED and proposal is not None
    assert [item["state"] for item in repository.attempts] == ["TIMED_OUT", "SUCCEEDED"]


@pytest.mark.asyncio
async def test_permanent_failure_is_not_retried_and_timeout_exhaustion_is_distinct() -> None:
    actor = _actor()
    permanent = FakeRepository(actor)
    run, proposal = await AIExecutionService(
        permanent,
        FakeReviews(),
        FakeProvenance(),
        {"mock": DeterministicMockAIProvider([AIProviderErrorKind.PERMANENT])},
    ).create_and_execute(
        actor,
        review_id=uuid4(),
        task_type=AITaskType.SEARCH_QUERY_SUGGESTION,
        input_data={"query": "q", "objective": "o"},
        maximum_attempts=3,
    )  # type: ignore[arg-type]
    assert run.state is AIRunState.FAILED and proposal is None and len(permanent.attempts) == 1
    exhausted = FakeRepository(actor)
    run, _ = await AIExecutionService(
        exhausted,
        FakeReviews(),
        FakeProvenance(),
        {
            "mock": DeterministicMockAIProvider(
                [AIProviderErrorKind.TIMEOUT, AIProviderErrorKind.TIMEOUT]
            )
        },
    ).create_and_execute(
        actor,
        review_id=uuid4(),
        task_type=AITaskType.SEARCH_QUERY_SUGGESTION,
        input_data={"query": "q", "objective": "o"},
        maximum_attempts=2,
    )  # type: ignore[arg-type]
    assert run.state is AIRunState.TIMED_OUT and len(exhausted.attempts) == 2
