import pytest

from backend.app.core.errors import InvalidStateTransitionError
from backend.app.orchestration.contracts import JobState
from backend.app.workflow.domain import validate_job_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobState.QUEUED, JobState.RUNNING),
        (JobState.RUNNING, JobState.AWAITING_HUMAN),
        (JobState.AWAITING_HUMAN, JobState.RUNNING),
        (JobState.FAILED, JobState.QUEUED),
    ],
)
def test_valid_workflow_job_transitions(current: JobState, target: JobState) -> None:
    validate_job_transition(current, target)


@pytest.mark.parametrize("terminal", [JobState.COMPLETED, JobState.CANCELLED])
def test_terminal_workflow_job_states_cannot_transition(terminal: JobState) -> None:
    with pytest.raises(InvalidStateTransitionError):
        validate_job_transition(terminal, JobState.QUEUED)


def test_workflow_job_cannot_skip_from_queued_to_completed() -> None:
    with pytest.raises(InvalidStateTransitionError):
        validate_job_transition(JobState.QUEUED, JobState.COMPLETED)
