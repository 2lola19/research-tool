from __future__ import annotations

import pytest

from backend.app.core.errors import StaleWorkflowDefinitionError
from backend.app.workflow.recovery_domain import (
    FailureClass,
    RetryPolicy,
    WorkflowDefinition,
    WorkflowDefinitionRegistry,
    WorkflowStepDefinition,
)


def test_retry_policy_classifies_backoff_and_bounds_attempts() -> None:
    policy = RetryPolicy(
        max_attempts=4,
        backoff_seconds=5,
        max_backoff_seconds=12,
        timeout_seconds=30,
    )

    assert policy.should_retry(FailureClass.TRANSIENT, 1)
    assert policy.should_retry(FailureClass.TIMEOUT, 3)
    assert not policy.should_retry(FailureClass.PERMANENT, 1)
    assert not policy.should_retry(FailureClass.TRANSIENT, 4)
    assert [policy.delay_for_attempt(attempt) for attempt in (1, 2, 3, 4)] == [5, 10, 12, 12]


def test_workflow_definition_hash_is_versioned_and_stale_hash_is_rejected() -> None:
    definition = WorkflowDefinition(
        name="review-workflow",
        version="1",
        steps=(
            WorkflowStepDefinition(
                step_key="search",
                step_order=0,
                task_name="search.fixture",
                task_version="1",
                payload_schema="search.fixture",
                payload_version=1,
            ),
        ),
    )
    registry = WorkflowDefinitionRegistry((definition,))

    assert registry.resolve("review-workflow", "1", definition.definition_hash) == definition
    with pytest.raises(StaleWorkflowDefinitionError, match="stale"):
        registry.resolve("review-workflow", "1", "0" * 64)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition)
