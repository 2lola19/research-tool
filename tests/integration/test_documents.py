from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_tenant_isolation import (
    TenantApi,
    _approved_protocol,
    _import_screening_fixture,
)

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _upload_document(
    tenant_api: TenantApi,
    article_id: object,
    content: bytes = b"%PDF-FIXTURE\nMethods text for screening.",
) -> dict[str, object]:
    response = tenant_api.client.post(
        f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/articles/{article_id}/upload",
        headers={
            **tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
            "Content-Type": "application/pdf",
            "X-Original-Filename": "fixture.pdf",
        },
        content=content,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_document_upload_process_retrieve_and_screening_preserve_structure(
    tenant_api: TenantApi,
) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    document = _upload_document(tenant_api, article["id"])
    document_id = document["id"]
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    assert document["status"] == "MALWARE_SCAN_PENDING"

    processed = tenant_api.client.post(
        f"/api/v1/documents/{document_id}/process", headers=lead_headers
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "PROCESSED"
    scans = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/malware-scans", headers=lead_headers
    )
    assert scans.status_code == 200, scans.text
    assert len(scans.json()) == 1
    assert scans.json()[0]["outcome"] == "CLEAN"
    assert scans.json()[0]["provider_type"] == "fixture"
    assert scans.json()[0]["content_sha256"] == document["sha256"]
    assert scans.json()[0]["content_size"] == document["file_size"]
    runs = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/processing-runs", headers=lead_headers
    )
    assert runs.status_code == 200, runs.text
    assert runs.json()[0]["chunk_manifest_hash"]
    assert runs.json()[0]["block_count"] == 1

    content = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/content", headers=lead_headers
    )
    assert content.status_code == 200
    assert content.content.startswith(b"%PDF-FIXTURE")

    reconciliation = tenant_api.client.get(
        f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/storage-reconciliation",
        headers=lead_headers,
    )
    assert reconciliation.status_code == 200, reconciliation.text
    assert reconciliation.json()["status"] == "RECONCILIATION_ONLY"
    assert reconciliation.json()["missing_document_ids"] == []
    assert reconciliation.json()["orphan_object_count"] == 0

    foreign_reconciliation = tenant_api.client.get(
        f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/storage-reconciliation",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign_reconciliation.status_code == 404

    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=tenant_api.ids.assigned_review,
        suffix="full-text",
    )
    screening = tenant_api.client.post(
        f"/api/v1/documents/{document_id}/full-text-screening",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "protocol_version_id": protocol_id,
            "judgments": [
                {
                    "criterion_key": "population",
                    "decision": "PASS",
                    "evidence_text": "Participants were eligible.",
                },
                {
                    "criterion_key": "outcome",
                    "decision": "FAIL",
                    "reason": "No eligible outcome was reported.",
                },
            ],
        },
    )
    assert screening.status_code == 200, screening.text
    assert screening.json()["final_decision"] == "EXCLUDE"
    assert screening.json()["primary_reason"] == "No eligible outcome was reported."


def test_document_upload_rejects_bad_files_duplicates_and_unauthorized_access(
    tenant_api: TenantApi,
) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    path = (
        f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/"
        f"articles/{article['id']}/upload"
    )
    viewer_headers = {
        **tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
        "Content-Type": "application/pdf",
        "X-Original-Filename": "fixture.pdf",
    }
    assert (
        tenant_api.client.post(
            path, headers=viewer_headers, content=b"%PDF-FIXTURE\ntext"
        ).status_code
        == 403
    )

    bad_headers = {
        **tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        "Content-Type": "application/pdf",
        "X-Original-Filename": "../escape.pdf",
    }
    assert tenant_api.client.post(path, headers=bad_headers, content=b"not-pdf").status_code == 409

    document = _upload_document(tenant_api, article["id"])
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    warning = tenant_api.client.post(
        f"/api/v1/documents/{document['id']}/warnings",
        headers=lead_headers,
        json={"kind": "RETRACTION", "message": "Fixture warning"},
    )
    assert warning.status_code == 200
    assert warning.json()["kind"] == "RETRACTION"
    warnings = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/warnings", headers=lead_headers
    )
    assert warnings.status_code == 200
    assert warnings.json()[0]["message"] == "Fixture warning"
    duplicate = tenant_api.client.post(
        path,
        headers={
            **tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
            "Content-Type": "application/pdf",
            "X-Original-Filename": "copy.pdf",
        },
        content=b"%PDF-FIXTURE\nMethods text for screening.",
    )
    assert duplicate.status_code == 409

    foreign = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign.status_code == 404
    guessed = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert guessed.status_code == 200
    viewer_process = tenant_api.client.post(
        f"/api/v1/documents/{document['id']}/process",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert viewer_process.status_code == 403
    viewer_content = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/content",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert viewer_content.status_code == 403
    viewer_scans = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/malware-scans",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert viewer_scans.status_code == 403
    foreign_scans = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/malware-scans",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign_scans.status_code == 404


def test_document_processing_failure_can_be_retried_after_storage_repair(
    tenant_api: TenantApi,
) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    document = _upload_document(tenant_api, article["id"])
    document_id = document["id"]
    content = b"%PDF-FIXTURE\nMethods text for screening."
    storage_path = (
        Path(tenant_api.settings.local_storage_path)
        / str(tenant_api.ids.organization_a)
        / str(tenant_api.ids.assigned_review)
        / str(article["id"])
        / f"{document_id.replace('-', '')}.pdf"
    )
    assert storage_path.exists()
    storage_path.write_bytes(b"corrupted")
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)

    failed = tenant_api.client.post(
        f"/api/v1/documents/{document_id}/process", headers=lead_headers
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "PROCESSING_FAILED"
    failed_runs = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/processing-runs", headers=lead_headers
    )
    assert failed_runs.json()[0]["failure_class"] == "STORAGE_INTEGRITY"
    failed_scans = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/malware-scans", headers=lead_headers
    )
    assert failed_scans.status_code == 200
    assert failed_scans.json() == []

    storage_path.write_bytes(content)
    retried = tenant_api.client.post(
        f"/api/v1/documents/{document_id}/process", headers=lead_headers
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "PROCESSED"
    runs = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/processing-runs", headers=lead_headers
    )
    assert len(runs.json()) == 2
    assert runs.json()[-1]["status"] == "SUCCEEDED"
    repaired_scans = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/malware-scans", headers=lead_headers
    )
    assert repaired_scans.json()[0]["content_sha256"] == document["sha256"]


def test_infected_document_is_blocked_before_parser_and_retains_audit_scan(
    tenant_api: TenantApi,
) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    document = _upload_document(tenant_api, article["id"], b"%PDF-FIXTURE\nMALWARE-TEST-INFECTED")
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)

    blocked = tenant_api.client.post(
        f"/api/v1/documents/{document['id']}/process", headers=lead_headers
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["status"] == "MALWARE_INFECTED"

    scans = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/malware-scans", headers=lead_headers
    )
    assert scans.status_code == 200
    assert scans.json()[0]["outcome"] == "INFECTED"
    assert scans.json()[0]["detection_name"] == "Fixture-Test-Signature"
    assert "MALWARE-TEST" not in scans.text

    runs = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/processing-runs", headers=lead_headers
    )
    assert runs.status_code == 200
    assert runs.json() == []
    assert (
        tenant_api.client.get(
            f"/api/v1/documents/{document['id']}/content", headers=lead_headers
        ).status_code
        == 409
    )
    retry = tenant_api.client.post(
        f"/api/v1/documents/{document['id']}/process", headers=lead_headers
    )
    assert retry.status_code == 409


@pytest.mark.parametrize(
    ("marker", "outcome", "error_class"),
    [
        (b"MALWARE-TEST-UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE"),
        (b"MALWARE-TEST-TIMEOUT", "TIMEOUT", "TIMEOUT"),
        (b"MALWARE-TEST-ERROR", "ERROR", "SCANNER_ERROR"),
    ],
)
def test_scanner_failures_fail_closed_and_retry_is_bounded(
    tenant_api: TenantApi,
    marker: bytes,
    outcome: str,
    error_class: str,
) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    document = _upload_document(tenant_api, article["id"], b"%PDF-FIXTURE\n" + marker)
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)

    for _ in range(3):
        failed = tenant_api.client.post(
            f"/api/v1/documents/{document['id']}/process", headers=lead_headers
        )
        assert failed.status_code == 200, failed.text
        assert failed.json()["status"] == "MALWARE_SCAN_FAILED"

    exhausted = tenant_api.client.post(
        f"/api/v1/documents/{document['id']}/process", headers=lead_headers
    )
    assert exhausted.status_code == 409
    scans = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/malware-scans", headers=lead_headers
    )
    assert [item["outcome"] for item in scans.json()] == [outcome] * 3
    assert [item["error_class"] for item in scans.json()] == [error_class] * 3
    assert (
        tenant_api.client.get(
            f"/api/v1/documents/{document['id']}/content", headers=lead_headers
        ).status_code
        == 409
    )
    runs = tenant_api.client.get(
        f"/api/v1/documents/{document['id']}/processing-runs", headers=lead_headers
    )
    assert runs.json() == []
