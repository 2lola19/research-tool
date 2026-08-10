from __future__ import annotations

from tests.integration.test_tenant_isolation import (
    TenantApi,
    _approved_protocol,
    _import_screening_fixture,
)

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _upload_document(tenant_api: TenantApi, article_id: object) -> dict[str, object]:
    response = tenant_api.client.post(
        f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/articles/{article_id}/upload",
        headers={
            **tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
            "Content-Type": "application/pdf",
            "X-Original-Filename": "fixture.pdf",
        },
        content=b"%PDF-FIXTURE\nMethods text for screening.",
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

    processed = tenant_api.client.post(
        f"/api/v1/documents/{document_id}/process", headers=lead_headers
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "PROCESSED"

    content = tenant_api.client.get(
        f"/api/v1/documents/{document_id}/content", headers=lead_headers
    )
    assert content.status_code == 200
    assert content.content.startswith(b"%PDF-FIXTURE")

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
