from __future__ import annotations

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _create_noop_job(
    tenant_api: TenantApi,
    *,
    suffix: str = "durable",
    max_attempts: int = 2,
) -> tuple[dict[str, str], str]:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    run = tenant_api.client.post(
        "/api/v1/workflow/runs",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "workflow_name": "durable-fixture",
            "workflow_version": "1",
            "idempotency_key": f"{suffix}-run",
        },
    )
    assert run.status_code == 201, run.text
    job = tenant_api.client.post(
        f"/api/v1/workflow/runs/{run.json()['id']}/jobs",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "task_name": "workflow.noop",
            "task_version": "1",
            "payload_schema": "workflow.noop",
            "payload_version": 1,
            "max_attempts": max_attempts,
            "idempotency_key": f"{suffix}-job",
            "payload": {},
        },
    )
    assert job.status_code == 201, job.text
    return headers, job.json()["id"]


def test_worker_claim_lease_heartbeat_and_completion_are_durable(
    tenant_api: TenantApi,
) -> None:
    headers, job_id = _create_noop_job(tenant_api)
    prefix = "/api/v1/workflow/execution"
    registered = tenant_api.client.post(
        f"{prefix}/workers/worker-a/register",
        headers=headers,
        json={"capacity": 1},
    )
    assert registered.status_code == 201, registered.text

    claimed = tenant_api.client.post(
        f"{prefix}/workers/worker-a/claim",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "lease_seconds": 60,
        },
    )
    assert claimed.status_code == 200, claimed.text
    claim = claimed.json()
    assert claim["job_id"] == job_id
    assert claim["payload"] == {}
    assert claim["attempt"]["state"] == "CLAIMED"
    heartbeat = tenant_api.client.post(
        f"{prefix}/attempts/{claim['attempt']['id']}/heartbeat",
        headers=headers,
        json={
            "worker_id": "worker-a",
            "lease_token": claim["lease_token"],
            "lease_seconds": 60,
        },
    )
    assert heartbeat.status_code == 200, heartbeat.text
    assert heartbeat.json()["state"] == "RUNNING"

    completed = tenant_api.client.post(
        f"{prefix}/attempts/{claim['attempt']['id']}/complete",
        headers=headers,
        json={
            "worker_id": "worker-a",
            "lease_token": claim["lease_token"],
            "result_snapshot": {"status": "completed"},
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["state"] == "COMPLETED"

    attempts = tenant_api.client.get(
        f"{prefix}/reviews/{tenant_api.ids.private_review}/attempts",
        headers=headers,
    )
    assert attempts.status_code == 200
    assert attempts.json()[0]["state"] == "COMPLETED"
    assert "lease_token" not in attempts.json()[0]

    events = tenant_api.client.get(
        f"/api/v1/workflow/jobs/{job_id}/events",
        headers=headers,
    )
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()] == [
        "SUBMITTED",
        "ATTEMPT_CLAIMED",
        "ATTEMPT_HEARTBEAT",
        "ATTEMPT_COMPLETED",
    ]


def test_worker_claim_is_review_and_tenant_scoped(tenant_api: TenantApi) -> None:
    _create_noop_job(tenant_api)
    foreign_headers = tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b)
    response = tenant_api.client.post(
        "/api/v1/workflow/execution/workers/worker-b/claim",
        headers=foreign_headers,
        json={"review_id": str(tenant_api.ids.private_review)},
    )
    assert response.status_code == 404


def test_worker_failure_requeues_and_controller_can_requeue_terminal_attempt(
    tenant_api: TenantApi,
) -> None:
    headers, job_id = _create_noop_job(tenant_api, suffix="retry", max_attempts=3)
    prefix = "/api/v1/workflow/execution"
    registered = tenant_api.client.post(
        f"{prefix}/workers/worker-retry/register",
        headers=headers,
        json={"capacity": 1},
    )
    assert registered.status_code == 201, registered.text

    first = tenant_api.client.post(
        f"{prefix}/workers/worker-retry/claim",
        headers=headers,
        json={"review_id": str(tenant_api.ids.private_review)},
    )
    assert first.status_code == 200, first.text
    first_claim = first.json()
    failed = tenant_api.client.post(
        f"{prefix}/attempts/{first_claim['attempt']['id']}/fail",
        headers=headers,
        json={
            "worker_id": "worker-retry",
            "lease_token": first_claim["lease_token"],
            "failure_code": "FIXTURE_FAILURE",
            "failure_message": "fixture handler failed",
            "requeue": True,
        },
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["state"] == "QUEUED"

    second = tenant_api.client.post(
        f"{prefix}/workers/worker-retry/claim",
        headers=headers,
        json={"review_id": str(tenant_api.ids.private_review)},
    )
    assert second.status_code == 200, second.text
    second_claim = second.json()
    terminal = tenant_api.client.post(
        f"{prefix}/attempts/{second_claim['attempt']['id']}/fail",
        headers=headers,
        json={
            "worker_id": "worker-retry",
            "lease_token": second_claim["lease_token"],
            "failure_code": "FIXTURE_FAILURE",
            "failure_message": "fixture handler failed again",
            "requeue": False,
        },
    )
    assert terminal.status_code == 200, terminal.text
    assert terminal.json()["state"] == "FAILED"

    requeued = tenant_api.client.post(
        f"{prefix}/jobs/{job_id}/requeue",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "reason": "controller approved a bounded retry",
        },
    )
    assert requeued.status_code == 200, requeued.text
    assert requeued.json()["state"] == "QUEUED"


def test_permanent_failure_dead_letters_and_manual_recovery_is_idempotent(
    tenant_api: TenantApi,
) -> None:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    run = tenant_api.client.post(
        "/api/v1/workflow/runs",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "workflow_name": "recovery-fixture",
            "workflow_version": "1",
            "idempotency_key": "dead-letter-run",
        },
    )
    assert run.status_code == 201, run.text
    job = tenant_api.client.post(
        f"/api/v1/workflow/runs/{run.json()['id']}/jobs",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "task_name": "workflow.noop",
            "task_version": "1",
            "payload_schema": "workflow.noop",
            "payload_version": 1,
            "max_attempts": 1,
            "retry_policy": {
                "max_attempts": 1,
                "backoff_seconds": 0,
                "max_backoff_seconds": 0,
                "timeout_seconds": 30,
                "retryable_failure_classes": ["TRANSIENT"],
            },
            "step_key": "dead-letter-step",
            "step_order": 0,
            "idempotency_key": "dead-letter-job",
            "payload": {},
        },
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]
    prefix = "/api/v1/workflow/execution"
    registered = tenant_api.client.post(
        f"{prefix}/workers/worker-dead-letter/register",
        headers=headers,
        json={"capacity": 1},
    )
    assert registered.status_code == 201, registered.text
    claimed = tenant_api.client.post(
        f"{prefix}/workers/worker-dead-letter/claim",
        headers=headers,
        json={"review_id": str(tenant_api.ids.private_review)},
    )
    assert claimed.status_code == 200, claimed.text
    claim = claimed.json()
    failed = tenant_api.client.post(
        f"{prefix}/attempts/{claim['attempt']['id']}/fail",
        headers=headers,
        json={
            "worker_id": "worker-dead-letter",
            "lease_token": claim["lease_token"],
            "failure_code": "SCIENTIFIC_INPUT_INVALID",
            "failure_message": "fixture permanent failure",
            "failure_class": "PERMANENT",
        },
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["state"] == "DEAD_LETTERED"

    checkpoints = tenant_api.client.get(
        f"{prefix}/reviews/{tenant_api.ids.private_review}/steps",
        headers=headers,
    )
    assert checkpoints.status_code == 200, checkpoints.text
    assert checkpoints.json()[0]["state"] == "DEAD_LETTERED"

    recovery_payload = {
        "review_id": str(tenant_api.ids.private_review),
        "reason": "controller reviewed the permanent failure",
        "idempotency_key": "manual-recovery-1",
        "additional_attempts": 1,
    }
    recovered = tenant_api.client.post(
        f"{prefix}/jobs/{job_id}/requeue",
        headers=headers,
        json=recovery_payload,
    )
    replayed = tenant_api.client.post(
        f"{prefix}/jobs/{job_id}/requeue",
        headers=headers,
        json=recovery_payload,
    )
    assert recovered.status_code == replayed.status_code == 200
    assert recovered.json() == replayed.json() == {"job_id": job_id, "state": "QUEUED"}

    second = tenant_api.client.post(
        f"{prefix}/workers/worker-dead-letter/claim",
        headers=headers,
        json={"review_id": str(tenant_api.ids.private_review)},
    )
    assert second.status_code == 200, second.text
    completed = tenant_api.client.post(
        f"{prefix}/attempts/{second.json()['attempt']['id']}/complete",
        headers=headers,
        json={
            "worker_id": "worker-dead-letter",
            "lease_token": second.json()["lease_token"],
            "result_snapshot": {"status": "recovered"},
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["state"] == "COMPLETED"


def test_resume_is_idempotent_reconciliation_is_scoped_and_reports_drift(
    tenant_api: TenantApi,
) -> None:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    _, job_id = _create_noop_job(tenant_api, suffix="resume")
    transitioned = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/transitions",
        headers=headers,
        json={"target_state": "RUNNING", "reason": "start before pause"},
    )
    assert transitioned.status_code == 200, transitioned.text
    paused = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/transitions",
        headers=headers,
        json={"target_state": "PAUSED", "reason": "operator pause"},
    )
    assert paused.status_code == 200, paused.text

    resume_payload = {
        "review_id": str(tenant_api.ids.private_review),
        "idempotency_key": "resume-operation-1",
        "reason": "operator resumed after inspection",
    }
    resumed = tenant_api.client.post(
        f"/api/v1/workflow/execution/jobs/{job_id}/resume",
        headers=headers,
        json=resume_payload,
    )
    replayed = tenant_api.client.post(
        f"/api/v1/workflow/execution/jobs/{job_id}/resume",
        headers=headers,
        json=resume_payload,
    )
    assert resumed.status_code == replayed.status_code == 200
    assert resumed.json() == replayed.json() == {"job_id": job_id, "state": "RUNNING"}

    reconciliation = tenant_api.client.get(
        f"/api/v1/workflow/execution/reviews/{tenant_api.ids.private_review}/reconciliation",
        headers=headers,
    )
    assert reconciliation.status_code == 200, reconciliation.text
    assert reconciliation.json()["healthy"] is False
    assert reconciliation.json()["issues"][0]["code"] == "RUNNING_WITHOUT_ACTIVE_ATTEMPT"

    foreign = tenant_api.client.get(
        f"/api/v1/workflow/execution/reviews/{tenant_api.ids.private_review}/reconciliation",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign.status_code == 404
