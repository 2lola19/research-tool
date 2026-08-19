from __future__ import annotations

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_ai_copilot_routes_preserve_review_and_role_boundaries(tenant_api: TenantApi) -> None:
    review_id = str(tenant_api.ids.assigned_review)
    viewer = tenant_api.client.get(
        f"/api/v1/ai/copilot/reviews/{review_id}/queries",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    foreign = tenant_api.client.get(
        f"/api/v1/ai/copilot/reviews/{review_id}/queries",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert viewer.status_code == 403
    assert foreign.status_code == 404


def test_ai_copilot_uses_the_dedicated_governed_surface(tenant_api: TenantApi) -> None:
    response = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "task_type": "REVIEW_COPILOT",
            "input_data": {"query": "status"},
        },
    )
    assert response.status_code == 409


def test_ai_copilot_requires_policy_before_query(tenant_api: TenantApi) -> None:
    review_id = str(tenant_api.ids.assigned_review)
    response = tenant_api.client.post(
        f"/api/v1/ai/copilot/reviews/{review_id}/queries",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={"task_key": "PROJECT_STATUS", "query": "What is the status?"},
    )
    assert response.status_code == 409
    assert "not configured" in response.text


def test_ai_copilot_records_bounded_abstaining_query(tenant_api: TenantApi) -> None:
    review_id = str(tenant_api.ids.assigned_review)
    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    policy = tenant_api.client.post(
        f"/api/v1/ai/copilot/reviews/{review_id}/policies",
        headers=headers,
        json={"maximum_query_characters": 2_000, "maximum_context_items": 20},
    )
    assert policy.status_code == 201

    response = tenant_api.client.post(
        f"/api/v1/ai/copilot/reviews/{review_id}/queries",
        headers=headers,
        json={"task_key": "PROJECT_STATUS", "query": "What is the status?"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "ABSTAINED"
    assert payload["context_hash"]
    assert payload["answer"]["abstention"] == "NEEDS_HUMAN_REVIEW"

    listed = tenant_api.client.get(
        f"/api/v1/ai/copilot/reviews/{review_id}/queries",
        headers=headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["stale"] is False

    changed = tenant_api.client.patch(
        f"/api/v1/reviews/{review_id}",
        headers=headers,
        json={"title": "Assigned review changed", "project_slug": "assigned-review"},
    )
    assert changed.status_code == 200
    stale = tenant_api.client.get(
        f"/api/v1/ai/copilot/reviews/{review_id}/queries",
        headers=headers,
    )
    assert stale.status_code == 200
    assert stale.json()[0]["stale"] is True
    assert stale.json()[0]["stale_reasons"] == ["CURRENT_CANONICAL_CONTEXT_CHANGED"]
