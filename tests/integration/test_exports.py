from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from tests.integration.test_search_executions import _record_completed_execution
from tests.integration.test_tenant_isolation import TenantApi, _import_screening_fixture

pytest_plugins = ("tests.integration.test_tenant_isolation",)


@pytest.mark.parametrize(
    ("export_format", "signature"),
    [("CSV", b"\xef\xbb\xbf"), ("XLSX", b"PK"), ("JSON", b"{"), ("RIS", b"TY  -")],
)
def test_export_artifacts_have_manifests_checksums_and_downloads(
    tenant_api: TenantApi,
    export_format: str,
    signature: bytes,
) -> None:
    _import_screening_fixture(tenant_api)
    _record_completed_execution(tenant_api)
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        f"/api/v1/exports/reviews/{tenant_api.ids.assigned_review}",
        headers=headers,
        json={"format": export_format},
    )
    assert created.status_code == 201, created.text
    artifact = created.json()
    assert artifact["format"] == export_format
    assert artifact["manifest"]["prisma_ready_for_final"] is False
    assert artifact["manifest"]["row_counts"]["articles"] == 2
    assert artifact["schema_version"] == "review-export-2"
    download = tenant_api.client.get(
        f"/api/v1/exports/{artifact['id']}/download",
        headers=headers,
        params={"review_id": str(tenant_api.ids.assigned_review)},
    )
    assert download.status_code == 200, download.text
    assert download.content.startswith(signature)
    assert hashlib.sha256(download.content).hexdigest() == artifact["sha256"]
    assert download.headers["x-content-sha256"] == artifact["sha256"]
    if export_format == "XLSX":
        with zipfile.ZipFile(io.BytesIO(download.content)) as workbook:
            assert workbook.testzip() is None
            assert b"Search Executions" in workbook.read("xl/workbook.xml")
    if export_format == "JSON":
        payload = json.loads(download.content)
        assert payload["prisma"]["readiness"]["ready_for_final"] is False
        assert payload["search_executions"][0]["source_name"] == "Fixture Database"


def test_new_export_does_not_mutate_prior_artifact(
    tenant_api: TenantApi,
) -> None:
    _import_screening_fixture(tenant_api)
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    first = tenant_api.client.post(
        f"/api/v1/exports/reviews/{tenant_api.ids.assigned_review}",
        headers=headers,
        json={"format": "JSON"},
    )
    assert first.status_code == 201, first.text
    first_artifact = first.json()
    second = tenant_api.client.post(
        f"/api/v1/exports/reviews/{tenant_api.ids.assigned_review}",
        headers=headers,
        json={"format": "JSON"},
    )
    assert second.status_code == 201, second.text
    second_artifact = second.json()
    assert second_artifact["id"] != first_artifact["id"]
    first_download = tenant_api.client.get(
        f"/api/v1/exports/{first_artifact['id']}/download",
        headers=headers,
        params={"review_id": str(tenant_api.ids.assigned_review)},
    )
    second_download = tenant_api.client.get(
        f"/api/v1/exports/{second_artifact['id']}/download",
        headers=headers,
        params={"review_id": str(tenant_api.ids.assigned_review)},
    )
    assert hashlib.sha256(first_download.content).hexdigest() == first_artifact["sha256"]
    assert hashlib.sha256(second_download.content).hexdigest() == second_artifact["sha256"]


def test_export_authorization_and_tenant_non_enumeration(tenant_api: TenantApi) -> None:
    _import_screening_fixture(tenant_api)
    viewer = tenant_api.client.post(
        f"/api/v1/exports/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
        json={"format": "CSV"},
    )
    assert viewer.status_code == 403
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        f"/api/v1/exports/reviews/{tenant_api.ids.assigned_review}",
        headers=lead_headers,
        json={"format": "RIS"},
    )
    artifact_id = created.json()["id"]
    foreign = tenant_api.client.get(
        f"/api/v1/exports/{artifact_id}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        params={"review_id": str(tenant_api.ids.organization_b_review)},
    )
    assert foreign.status_code == 404
    listed = tenant_api.client.get(
        f"/api/v1/exports/reviews/{tenant_api.ids.assigned_review}", headers=lead_headers
    )
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == artifact_id
