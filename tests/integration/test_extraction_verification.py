from __future__ import annotations

from tests.integration.test_manual_extraction import _schema_and_study
from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _run_with_value(
    tenant_api: TenantApi, study_id: str, version_id: str, article_id: str, value: int
) -> str:
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
                    "value": value,
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
    return run.json()["id"]


def test_verification_matches_normalized_values_and_preserves_conflicts(
    tenant_api: TenantApi,
) -> None:
    study_id, version_id, article_id = _schema_and_study(tenant_api)
    run_a = _run_with_value(tenant_api, study_id, version_id, article_id, 10)
    run_b = _run_with_value(tenant_api, study_id, version_id, article_id, 10)
    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    matched = tenant_api.client.post(
        "/api/v1/extraction/verifications/compare",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "run_a_id": run_a,
            "run_b_id": run_b,
        },
    )
    assert matched.status_code == 200, matched.text
    assert all(item["status"] == "MATCHED" for item in matched.json())

    run_c = _run_with_value(tenant_api, study_id, version_id, article_id, 11)
    conflict = tenant_api.client.post(
        "/api/v1/extraction/verifications/compare",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "run_a_id": run_a,
            "run_b_id": run_c,
        },
    )
    assert conflict.status_code == 200, conflict.text
    n_conflict = next(item for item in conflict.json() if item["field_key"] == "n")
    assert n_conflict["status"] == "NEEDS_ADJUDICATION"
    resolved = tenant_api.client.post(
        f"/api/v1/extraction/conflicts/{n_conflict['conflict_id']}/resolve",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "resolution": "ACCEPT_A",
            "reason": "Primary extraction has source agreement.",
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"


def test_verification_tenant_and_adjudication_permissions(
    tenant_api: TenantApi,
) -> None:
    study_id, version_id, article_id = _schema_and_study(tenant_api)
    run_a = _run_with_value(tenant_api, study_id, version_id, article_id, 1)
    run_b = _run_with_value(tenant_api, study_id, version_id, article_id, 2)
    foreign = tenant_api.client.post(
        "/api/v1/extraction/verifications/compare",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        json={
            "review_id": str(tenant_api.ids.organization_b_review),
            "run_a_id": run_a,
            "run_b_id": run_b,
        },
    )
    assert foreign.status_code == 404
