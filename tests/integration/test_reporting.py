from __future__ import annotations

import io
import json
import zipfile

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_structured_report_package_round_trip_staleness_and_tenant_boundaries(
    tenant_api: TenantApi,
) -> None:
    review_id = str(tenant_api.ids.assigned_review)
    lead = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    viewer = tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a)
    foreign = tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b)

    denied = tenant_api.client.post(
        "/api/v1/reporting/specifications",
        headers=viewer,
        json={
            "review_id": review_id,
            "logical_key": "PACKAGE",
            "report_type": "REPRODUCIBILITY_PACKAGE",
            "definition": {"formats": ["ZIP"], "allow_draft": True},
        },
    )
    assert denied.status_code == 403
    specification = tenant_api.client.post(
        "/api/v1/reporting/specifications",
        headers=lead,
        json={
            "review_id": review_id,
            "logical_key": "PACKAGE",
            "report_type": "REPRODUCIBILITY_PACKAGE",
            "definition": {"formats": ["ZIP"], "allow_draft": True},
        },
    )
    assert specification.status_code == 201, specification.text
    generated = tenant_api.client.post(
        f"/api/v1/reporting/specifications/{specification.json()['id']}/generate",
        headers=lead,
        json={"review_id": review_id},
    )
    assert generated.status_code == 201, generated.text
    artifact = generated.json()["artifacts"][0]
    assert artifact["format"] == "ZIP"
    downloaded = tenant_api.client.get(
        f"/api/v1/reporting/artifacts/{artifact['id']}/download",
        headers=lead,
        params={"review_id": review_id},
    )
    assert downloaded.status_code == 200
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["review_id"] == review_id
        assert "documents" not in " ".join(archive.namelist())
        assert "manifest-checksums.json" in archive.namelist()
    current = tenant_api.client.get(
        f"/api/v1/reporting/reviews/{review_id}/snapshots", headers=lead
    )
    assert current.json()[0]["currency"] == "CURRENT"
    unrelated_export = tenant_api.client.post(
        f"/api/v1/exports/reviews/{review_id}", headers=lead, json={"format": "JSON"}
    )
    assert unrelated_export.status_code == 201
    still_current = tenant_api.client.get(
        f"/api/v1/reporting/reviews/{review_id}/snapshots", headers=lead
    )
    assert still_current.json()[0]["currency"] == "CURRENT"

    foreign_list = tenant_api.client.get(
        f"/api/v1/reporting/reviews/{review_id}/snapshots", headers=foreign
    )
    foreign_download = tenant_api.client.get(
        f"/api/v1/reporting/artifacts/{artifact['id']}/download",
        headers=foreign,
        params={"review_id": str(tenant_api.ids.organization_b_review)},
    )
    assert foreign_list.status_code == foreign_download.status_code == 404
