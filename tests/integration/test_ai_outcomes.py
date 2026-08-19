from __future__ import annotations

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_outcome_assistance_uses_dedicated_governed_surface(tenant_api: TenantApi) -> None:
    review_id = tenant_api.ids.assigned_review
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)

    generic = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=lead_headers,
        json={
            "review_id": str(review_id),
            "task_type": "OUTCOME_MAPPING_SUGGESTION",
            "input_data": {"extraction_value_id": "not-used"},
        },
    )
    assert generic.status_code == 409

    proposals = tenant_api.client.get(
        f"/api/v1/ai/outcomes/reviews/{review_id}/proposals",
        headers=lead_headers,
    )
    assert proposals.status_code == 200, proposals.text
    assert proposals.json() == []

    viewer = tenant_api.client.get(
        f"/api/v1/ai/outcomes/reviews/{review_id}/proposals",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert viewer.status_code == 403

    foreign = tenant_api.client.get(
        f"/api/v1/ai/outcomes/reviews/{review_id}/proposals",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign.status_code == 404
