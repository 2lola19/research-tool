from __future__ import annotations

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_ai_proposal_requires_human_decision_and_preserves_tenant_boundaries(
    tenant_api: TenantApi,
) -> None:
    review_id = str(tenant_api.ids.assigned_review)
    owner = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    viewer = tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a)
    foreign = tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b)
    before = tenant_api.client.get(
        f"/api/v1/search-strategies/reviews/{review_id}/versions", headers=owner
    ).json()
    registry = tenant_api.client.get("/api/v1/ai/registry", headers=owner)
    assert registry.status_code == 200, registry.text
    denied = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=viewer,
        json={
            "review_id": review_id,
            "task_type": "SEARCH_QUERY_SUGGESTION",
            "input_data": {"query": "aspirin", "objective": "find randomized trials"},
        },
    )
    assert denied.status_code == 403
    generated = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=owner,
        json={
            "review_id": review_id,
            "task_type": "SEARCH_QUERY_SUGGESTION",
            "input_data": {"query": "aspirin", "objective": "find randomized trials"},
        },
    )
    assert generated.status_code == 201, generated.text
    result = generated.json()
    assert result["run"]["state"] == "SUCCEEDED"
    assert result["proposal"]["state"] == "PENDING_REVIEW"
    usage = tenant_api.client.get(f"/api/v1/ai/reviews/{review_id}/usage", headers=owner)
    assert usage.status_code == 200, usage.text
    assert usage.json()["summary"]["attempts"] >= 1
    assert usage.json()["policy"]["allow_unknown_cost"] is False
    after_generation = tenant_api.client.get(
        f"/api/v1/search-strategies/reviews/{review_id}/versions", headers=owner
    ).json()
    assert after_generation == before
    proposal_id = result["proposal"]["id"]
    accepted = tenant_api.client.post(
        f"/api/v1/ai/proposals/{proposal_id}/decision",
        headers=owner,
        json={"review_id": review_id, "decision": "ACCEPTED", "reason": "Useful draft"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "ACCEPTED"
    assert (
        tenant_api.client.get(
            f"/api/v1/search-strategies/reviews/{review_id}/versions", headers=owner
        ).json()
        == before
    )
    repeated = tenant_api.client.post(
        f"/api/v1/ai/proposals/{proposal_id}/decision",
        headers=owner,
        json={"review_id": review_id, "decision": "REJECTED", "reason": "changed mind"},
    )
    assert repeated.status_code == 409
    foreign_view = tenant_api.client.get(
        f"/api/v1/ai/reviews/{review_id}/proposals/{proposal_id}", headers=foreign
    )
    assert foreign_view.status_code == 404
