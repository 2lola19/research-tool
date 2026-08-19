from __future__ import annotations

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_ai_certainty_routes_preserve_review_and_role_boundaries(tenant_api: TenantApi) -> None:
    review_id = str(tenant_api.ids.assigned_review)
    viewer = tenant_api.client.get(
        f"/api/v1/ai/certainty/reviews/{review_id}/proposals",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    foreign = tenant_api.client.get(
        f"/api/v1/ai/certainty/reviews/{review_id}/proposals",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert viewer.status_code == 403
    assert foreign.status_code == 404


def test_certainty_assistance_uses_the_dedicated_governed_surface(
    tenant_api: TenantApi,
) -> None:
    response = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "task_type": "CERTAINTY_SUGGESTION",
            "input_data": {"assessment_id": "not-used"},
        },
    )
    assert response.status_code == 409


def test_ai_certainty_requires_a_policy_before_generation(tenant_api: TenantApi) -> None:
    review_id = str(tenant_api.ids.assigned_review)
    response = tenant_api.client.post(
        f"/api/v1/ai/certainty/reviews/{review_id}/proposals",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "items": [
                {
                    "assessment_id": "00000000-0000-0000-0000-000000000000",
                    "documents": [
                        {
                            "document_id": "00000000-0000-0000-0000-000000000000",
                            "document_role": "PRIMARY_FULL_TEXT",
                        }
                    ],
                }
            ]
        },
    )
    assert response.status_code == 409
    assert "not configured" in response.text
