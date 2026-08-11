from __future__ import annotations

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _fields() -> list[dict[str, object]]:
    return [
        {"key": "sample_size", "label": "Sample size", "field_type": "INTEGER", "required": True},
        {
            "key": "design",
            "label": "Design",
            "field_type": "CATEGORICAL",
            "allowed_options": ["RCT", "COHORT"],
        },
    ]


def test_schema_versions_are_deterministic_and_prior_versions_remain_readable(
    tenant_api: TenantApi,
) -> None:
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    schema = tenant_api.client.post(
        "/api/v1/extraction/schemas",
        headers=headers,
        json={"review_id": str(tenant_api.ids.assigned_review), "name": "Core extraction"},
    )
    assert schema.status_code == 201, schema.text
    payload = {
        "review_id": str(tenant_api.ids.assigned_review),
        "schema_id": schema.json()["id"],
        "fields": _fields(),
    }
    first = tenant_api.client.post(
        "/api/v1/extraction/schema-versions", headers=headers, json=payload
    )
    second = tenant_api.client.post(
        "/api/v1/extraction/schema-versions", headers=headers, json=payload
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert first.json()["content_hash"] == second.json()["content_hash"]


def test_schema_rejects_duplicate_keys_invalid_options_and_foreign_access(
    tenant_api: TenantApi,
) -> None:
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    schema = tenant_api.client.post(
        "/api/v1/extraction/schemas",
        headers=headers,
        json={"review_id": str(tenant_api.ids.assigned_review), "name": "Invalid cases"},
    )
    assert schema.status_code == 201
    duplicate = tenant_api.client.post(
        "/api/v1/extraction/schema-versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "schema_id": schema.json()["id"],
            "fields": [
                {"key": "x", "label": "X", "field_type": "TEXT"},
                {"key": "x", "label": "X2", "field_type": "TEXT"},
            ],
        },
    )
    assert duplicate.status_code == 409
    options = tenant_api.client.post(
        "/api/v1/extraction/schema-versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "schema_id": schema.json()["id"],
            "fields": [
                {"key": "kind", "label": "Kind", "field_type": "ENUM", "allowed_options": []}
            ],
        },
    )
    assert options.status_code == 409
    foreign = tenant_api.client.get(
        f"/api/v1/extraction/schemas/{schema.json()['id']}/versions",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        params={"review_id": str(tenant_api.ids.organization_b_review)},
    )
    assert foreign.status_code == 404
