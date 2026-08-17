from __future__ import annotations

from tests.integration.test_tenant_isolation import (
    TenantApi,
    _approved_protocol,
    _create_screening_round,
    _import_screening_fixture,
)

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _upload_and_process(tenant_api: TenantApi, article_id: object, marker: str) -> str:
    headers = {
        **tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        "Content-Type": "application/pdf",
        "X-Original-Filename": f"{marker}.pdf",
    }
    upload = tenant_api.client.post(
        f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/articles/{article_id}/upload",
        headers=headers,
        content=(
            "%PDF-FIXTURE\nMethods\nAdults with hypertension received exercise therapy. "
            f"Document representation {marker}."
        ).encode(),
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    processed = tenant_api.client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "PROCESSED"
    return str(document_id)


def test_blinded_full_text_ai_is_document_grounded_human_only_and_evaluable(
    tenant_api: TenantApi,
) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    review_id = tenant_api.ids.assigned_review
    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=review_id,
        suffix="ai-full-text",
    )
    round_record = _create_screening_round(tenant_api, name="AI full text", stage="FULL_TEXT")
    assignment = tenant_api.client.post(
        f"/api/v1/screening/rounds/{round_record['id']}/assignments",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={
            "article_id": article["id"],
            "reviewer_user_id": str(tenant_api.ids.reviewer_a),
        },
    )
    assert assignment.status_code == 201, assignment.text
    assignment_id = assignment.json()["id"]
    document_id = _upload_and_process(tenant_api, article["id"], "v1")
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)

    policy = tenant_api.client.post(
        f"/api/v1/ai/screening/reviews/{review_id}/policy",
        headers=lead_headers,
        json={"mode": "BLINDED_AI", "maximum_batch_size": 20},
    )
    assert policy.status_code == 201, policy.text
    readiness = tenant_api.client.get(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/assignments/{assignment_id}/readiness",
        headers=reviewer_headers,
        params={"document_id": document_id},
    )
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["state"] == "READY"
    prisma_before = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{review_id}/summary", headers=reviewer_headers
    )
    assert prisma_before.status_code == 200, prisma_before.text

    generated = tenant_api.client.post(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/suggestions",
        headers=reviewer_headers,
        json={
            "protocol_version_id": protocol_id,
            "items": [{"assignment_id": assignment_id, "document_id": document_id}],
        },
    )
    assert generated.status_code == 201, generated.text
    proposal = generated.json()[0]
    assert proposal["status"] == "SUCCEEDED"
    assert proposal["is_revealed"] is False
    assert proposal["structured_value"] is None
    assert proposal["document_version_id"] == document_id
    assert proposal["processing_run_id"]
    assert proposal["selected_chunk_ids"]

    # Generic AI routes cannot bypass governed screening creation or disclosure.
    generic_create = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=lead_headers,
        json={
            "review_id": str(review_id),
            "task_type": "FULL_TEXT_SCREENING_SUGGESTION",
            "input_data": {"document_id": document_id},
        },
    )
    assert generic_create.status_code == 409
    generic_direct = tenant_api.client.get(
        f"/api/v1/ai/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert generic_direct.status_code == 404
    generic_runs = tenant_api.client.get(
        f"/api/v1/ai/reviews/{review_id}/runs", headers=reviewer_headers
    )
    assert generic_runs.status_code == 200, generic_runs.text
    assert all(
        item["task_type"] != "FULL_TEXT_SCREENING_SUGGESTION" for item in generic_runs.json()
    )

    # Proposal generation does not create canonical screening state.
    queue = tenant_api.client.get(
        f"/api/v1/screening/rounds/{round_record['id']}/queue", headers=reviewer_headers
    )
    assert queue.status_code == 200, queue.text
    assert queue.json()[0]["own_decision"] is None
    prisma_after = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{review_id}/summary", headers=reviewer_headers
    )
    assert prisma_after.status_code == 200, prisma_after.text
    assert prisma_after.json()["counts"] == prisma_before.json()["counts"]

    direct = tenant_api.client.get(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert direct.status_code == 200, direct.text
    assert direct.json()["suggestion"] is None
    assert direct.json()["structured_value"] is None

    changed_policy = tenant_api.client.post(
        f"/api/v1/ai/screening/reviews/{review_id}/policy",
        headers=lead_headers,
        json={"mode": "ASSISTED", "maximum_batch_size": 20},
    )
    assert changed_policy.status_code == 201, changed_policy.text
    still_blinded = tenant_api.client.get(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert still_blinded.status_code == 200, still_blinded.text
    assert still_blinded.json()["mode"] == "BLINDED_AI"
    assert still_blinded.json()["structured_value"] is None

    foreign = tenant_api.client.get(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign.status_code == 404

    human = tenant_api.client.post(
        f"/api/v1/screening/assignments/{assignment_id}/decision",
        headers=reviewer_headers,
        json={"decision": "INCLUDE"},
    )
    assert human.status_code == 200, human.text
    revealed = tenant_api.client.get(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["suggestion"] == "MAYBE"
    assert revealed.json()["structured_value"]["missing_information"] == ["STUDY_DESIGN_UNCLEAR"]

    dataset = tenant_api.client.post(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/evaluation-datasets",
        headers=lead_headers,
        json={
            "logical_key": "full-text-fixture",
            "name": "Full-text fixture",
            "protocol_version_id": protocol_id,
            "reference_standard": "CURATED_DATASET",
            "cases": [
                {
                    "document_id": document_id,
                    "reference_decision": "RETAIN",
                    "reference_source_type": "CURATED_DATASET",
                }
            ],
        },
    )
    assert dataset.status_code == 201, dataset.text
    evaluation = tenant_api.client.post(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/evaluation-datasets/{dataset.json()['id']}/evaluate",
        headers=lead_headers,
        json={"evaluation_policy": "CONSERVATIVE"},
    )
    assert evaluation.status_code == 201, evaluation.text
    metrics = evaluation.json()["metrics"]
    assert metrics["stage"] == "FULL_TEXT"
    assert metrics["positive_class"] == "RETAIN"
    assert metrics["confusion_matrix"]["fn"] == 0
    assert metrics["evidence_grounding"]["evidence_validation_rate"] == 1.0
    case_results_url = (
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/evaluations/"
        f"{evaluation.json()['id']}/case-results"
    )
    case_results = tenant_api.client.get(case_results_url, headers=lead_headers)
    assert case_results.status_code == 200, case_results.text
    case_result_id = case_results.json()[0]["id"]
    classified = tenant_api.client.post(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/evaluation-case-results/"
        f"{case_result_id}/error-classifications",
        headers=lead_headers,
        json={"category": "PARSER_OMISSION", "notes": "Curated test classification"},
    )
    assert classified.status_code == 201, classified.text
    classified_results = tenant_api.client.get(case_results_url, headers=lead_headers)
    assert classified_results.status_code == 200, classified_results.text
    assert classified_results.json()[0]["error_classifications"][0]["category"] == (
        "PARSER_OMISSION"
    )

    # A replacement acquired document version makes the prior proposal stale and inspectable.
    replacement_document_id = _upload_and_process(tenant_api, article["id"], "v2")
    assert replacement_document_id != document_id
    document_stale = tenant_api.client.get(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert document_stale.status_code == 200, document_stale.text
    assert document_stale.json()["stale"] is True
    assert "DOCUMENT_VERSION_CHANGED" in document_stale.json()["stale_reasons"]

    # A later approved protocol does not rewrite the old proposal; it makes it stale.
    _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=review_id,
        suffix="ai-full-text-v2",
    )
    stale = tenant_api.client.get(
        f"/api/v1/ai/screening/full-text/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert stale.status_code == 200, stale.text
    assert stale.json()["stale"] is True
    assert "PROTOCOL_VERSION_CHANGED" in stale.json()["stale_reasons"]

    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{review_id}/audit", headers=reviewer_headers
    )
    actions = {item["action"] for item in audit.json()}
    assert "AI_FULL_TEXT_PROPOSAL_CREATED" in actions
    assert "AI_FULL_TEXT_DECISION_LINKED" in actions
