from __future__ import annotations

from tests.integration.test_studies import _import_screening_fixture
from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _schema_and_study(tenant_api: TenantApi) -> tuple[str, str, str]:
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    articles = _import_screening_fixture(tenant_api)
    study = tenant_api.client.post(
        "/api/v1/studies",
        headers=headers,
        json={"review_id": str(tenant_api.ids.assigned_review), "study_key": "EXT-001"},
    )
    assert study.status_code == 201, study.text
    linked = tenant_api.client.post(
        f"/api/v1/studies/{study.json()['id']}/articles",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "article_id": articles[0]["id"],
            "role": "PRIMARY",
        },
    )
    assert linked.status_code == 201, linked.text
    schema = tenant_api.client.post(
        "/api/v1/extraction/schemas",
        headers=headers,
        json={"review_id": str(tenant_api.ids.assigned_review), "name": "Manual fields"},
    )
    assert schema.status_code == 201, schema.text
    version = tenant_api.client.post(
        "/api/v1/extraction/schema-versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "schema_id": schema.json()["id"],
            "fields": [
                {"key": "n", "label": "N", "field_type": "INTEGER", "required": True},
                {
                    "key": "design",
                    "label": "Design",
                    "field_type": "ENUM",
                    "allowed_options": ["RCT", "COHORT"],
                },
            ],
        },
    )
    assert version.status_code == 201, version.text
    return study.json()["id"], version.json()["id"], articles[0]["id"]


def test_manual_extraction_validates_types_missingness_and_retains_provenance(
    tenant_api: TenantApi,
) -> None:
    study_id, version_id, article_id = _schema_and_study(tenant_api)
    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    run = tenant_api.client.post(
        "/api/v1/extraction/runs",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_id": study_id,
            "schema_version_id": version_id,
        },
    )
    assert run.status_code == 201, run.text
    saved = tenant_api.client.put(
        f"/api/v1/extraction/runs/{run.json()['id']}/values",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "status": "COMPLETED",
            "values": [
                {
                    "field_key": "n",
                    "value": 42,
                    "missingness": "VALUE_REPORTED",
                    "source_article_id": article_id,
                },
                {
                    "field_key": "design",
                    "missingness": "NOT_REPORTED",
                    "source_article_id": article_id,
                },
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "COMPLETED"
    assert {item["field_key"] for item in saved.json()["values"]} == {"n", "design"}
    invalid = tenant_api.client.put(
        f"/api/v1/extraction/runs/{run.json()['id']}/values",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "values": [
                {
                    "field_key": "n",
                    "value": "not-an-integer",
                    "missingness": "VALUE_REPORTED",
                    "source_article_id": article_id,
                }
            ],
        },
    )
    assert invalid.status_code == 409


def test_manual_extraction_isolated_and_viewer_cannot_mutate(
    tenant_api: TenantApi,
) -> None:
    study_id, version_id, _ = _schema_and_study(tenant_api)
    viewer = tenant_api.client.post(
        "/api/v1/extraction/runs",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_id": study_id,
            "schema_version_id": version_id,
        },
    )
    assert viewer.status_code == 403
    foreign = tenant_api.client.post(
        "/api/v1/extraction/runs",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        json={
            "review_id": str(tenant_api.ids.organization_b_review),
            "study_id": study_id,
            "schema_version_id": version_id,
        },
    )
    assert foreign.status_code == 404
