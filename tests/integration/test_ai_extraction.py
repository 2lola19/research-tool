from __future__ import annotations

from tests.integration.test_ai_full_text_screening import _upload_and_process
from tests.integration.test_manual_extraction import _schema_and_study
from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_governed_ai_extraction_is_human_only_blinded_scoped_and_evaluable(
    tenant_api: TenantApi,
) -> None:
    review_id = tenant_api.ids.assigned_review
    study_id, schema_version_id, article_id = _schema_and_study(tenant_api)
    document_id = _upload_and_process(tenant_api, article_id, "ai-extraction-v1")
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    run = tenant_api.client.post(
        "/api/v1/extraction/runs",
        headers=reviewer_headers,
        json={
            "review_id": str(review_id),
            "study_id": study_id,
            "schema_version_id": schema_version_id,
        },
    )
    assert run.status_code == 201, run.text
    assignment_id = run.json()["id"]
    policy = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/policies",
        headers=lead_headers,
        json={"mode": "ASSISTED", "maximum_batch_size": 10},
    )
    assert policy.status_code == 201, policy.text
    readiness = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/readiness",
        headers=reviewer_headers,
        json={
            "assignment_id": assignment_id,
            "documents": [{"document_id": document_id}],
        },
    )
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["state"] == "READY"

    before = tenant_api.client.get(
        f"/api/v1/extraction/runs/{assignment_id}",
        headers=reviewer_headers,
        params={"review_id": str(review_id)},
    )
    assert before.status_code == 200
    assert before.json()["values"] == []
    generated = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals",
        headers=reviewer_headers,
        json={
            "items": [
                {
                    "assignment_id": assignment_id,
                    "documents": [{"document_id": document_id}],
                }
            ]
        },
    )
    assert generated.status_code == 201, generated.text
    proposal = generated.json()[0]
    assert proposal["status"] == "SUCCEEDED"
    assert proposal["is_revealed"] is True
    assert proposal["validation_results"]["aggregate_valid"] is True
    assert proposal["source_manifest"][0]["document_id"] == document_id
    assert proposal["selected_chunk_ids"]
    assert proposal["selection_method"] == "field-aware-structured-bounded-v1"

    # AI generation cannot create or complete canonical extraction values.
    unchanged = tenant_api.client.get(
        f"/api/v1/extraction/runs/{assignment_id}",
        headers=reviewer_headers,
        params={"review_id": str(review_id)},
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["status"] == "NOT_STARTED"
    assert unchanged.json()["values"] == []
    not_a_second_extractor = tenant_api.client.post(
        "/api/v1/extraction/verifications/compare",
        headers=reviewer_headers,
        json={
            "review_id": str(review_id),
            "run_a_id": assignment_id,
            "run_b_id": proposal["proposal_id"],
        },
    )
    assert not_a_second_extractor.status_code == 404

    # Generic AI creation, listing, and direct proposal reads cannot bypass governance.
    generic_create = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=lead_headers,
        json={
            "review_id": str(review_id),
            "task_type": "EXTRACTION_SUGGESTION",
            "input_data": {"assignment_id": assignment_id},
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
    assert generic_runs.status_code == 200
    assert all(item["task_type"] != "EXTRACTION_SUGGESTION" for item in generic_runs.json())

    # Human edit calls the existing manual extraction service and preserves the AI output.
    edited = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals/"
        f"{proposal['proposal_id']}/fields/n/review",
        headers=reviewer_headers,
        json={
            "action": "EDITED",
            "human_value": {
                "value": 146,
                "missingness": "VALUE_REPORTED",
                "unit": None,
                "source_article_id": article_id,
                "evidence_location_id": None,
                "evidence_text": "Human verified source value",
            },
            "reason": "The human extractor verified the report.",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["human_actor_id"] == str(tenant_api.ids.reviewer_a)
    canonical = tenant_api.client.get(
        f"/api/v1/extraction/runs/{assignment_id}",
        headers=reviewer_headers,
        params={"review_id": str(review_id)},
    )
    assert canonical.status_code == 200
    assert canonical.json()["values"][0]["value"] == 146
    original = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert original.status_code == 200
    assert original.json()["structured_value"]["fields"][0]["status"] == "ABSTAIN"

    # A second assignment proves server-side BLINDED_AI withholding and post-submission reveal.
    blinded_run = tenant_api.client.post(
        "/api/v1/extraction/runs",
        headers=reviewer_headers,
        json={
            "review_id": str(review_id),
            "study_id": study_id,
            "schema_version_id": schema_version_id,
        },
    )
    assert blinded_run.status_code == 201, blinded_run.text
    blinded_assignment = blinded_run.json()["id"]
    changed_policy = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/policies",
        headers=lead_headers,
        json={"mode": "BLINDED_AI", "maximum_batch_size": 10},
    )
    assert changed_policy.status_code == 201, changed_policy.text
    blinded_generated = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals",
        headers=reviewer_headers,
        json={
            "items": [
                {
                    "assignment_id": blinded_assignment,
                    "documents": [{"document_id": document_id}],
                }
            ]
        },
    )
    assert blinded_generated.status_code == 201, blinded_generated.text
    blinded = blinded_generated.json()[0]
    assert blinded["is_revealed"] is False
    assert blinded["structured_value"] is None
    assert blinded["validation_results"] is None
    direct_blinded = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals/{blinded['proposal_id']}",
        headers=reviewer_headers,
    )
    assert direct_blinded.status_code == 200
    assert direct_blinded.json()["structured_value"] is None

    human_submission = tenant_api.client.put(
        f"/api/v1/extraction/runs/{blinded_assignment}/values",
        headers=reviewer_headers,
        json={
            "review_id": str(review_id),
            "status": "COMPLETED",
            "values": [
                {
                    "field_key": "n",
                    "value": 146,
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
    assert human_submission.status_code == 200, human_submission.text
    revealed = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals/{blinded['proposal_id']}",
        headers=reviewer_headers,
    )
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["is_revealed"] is True
    assert revealed.json()["structured_value"]["fields"]

    # Foreign tenants receive non-enumerable direct-ID behavior.
    foreign = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals/{blinded['proposal_id']}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign.status_code == 404

    dataset = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/evaluation-datasets",
        headers=lead_headers,
        json={
            "schema_version_id": schema_version_id,
            "logical_key": "extraction-fixture",
            "name": "Extraction fixture",
            "reference_standard": "CURATED_GOLD",
            "cases": [
                {
                    "study_id": study_id,
                    "field_key": "n",
                    "reference_missingness": "VALUE_REPORTED",
                    "reference_value": 146,
                },
                {
                    "study_id": study_id,
                    "field_key": "design",
                    "reference_missingness": "NOT_REPORTED",
                    "reference_value": None,
                },
            ],
        },
    )
    assert dataset.status_code == 201, dataset.text
    evaluation = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/evaluation-datasets/"
        f"{dataset.json()['id']}/evaluate",
        headers=lead_headers,
    )
    assert evaluation.status_code == 201, evaluation.text
    assert evaluation.json()["metrics"]["abstention_count"] == 2
    assert evaluation.json()["metrics"]["threshold_label"] == ("HYPOTHETICAL EVALUATION ONLY")
    datasets = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/evaluation-datasets", headers=lead_headers
    )
    evaluations = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/evaluations", headers=lead_headers
    )
    assert datasets.status_code == evaluations.status_code == 200
    assert datasets.json()[0]["id"] == dataset.json()["id"]
    assert evaluations.json()[0]["id"] == evaluation.json()["id"]
    case_results = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/evaluations/"
        f"{evaluation.json()['id']}/case-results",
        headers=lead_headers,
    )
    assert case_results.status_code == 200, case_results.text
    assert len(case_results.json()) == 2
    classified = tenant_api.client.post(
        f"/api/v1/ai/extraction/reviews/{review_id}/evaluation-case-results/"
        f"{case_results.json()[0]['id']}/classifications",
        headers=lead_headers,
        json={"category": "OTHER", "note": "Curated review"},
    )
    assert classified.status_code == 200, classified.text
    assert classified.json()["category"] == "OTHER"

    # A successor schema makes the prior immutable proposal stale without rerunning it.
    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{review_id}/audit", headers=reviewer_headers
    )
    schema_id = next(
        item["entity_id"]
        for item in audit.json()
        if item["entity_type"] == "extraction_schema" and item["action"] == "created"
    )
    successor = tenant_api.client.post(
        "/api/v1/extraction/schema-versions",
        headers=lead_headers,
        json={
            "review_id": str(review_id),
            "schema_id": schema_id,
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
    assert successor.status_code == 201, successor.text
    stale = tenant_api.client.get(
        f"/api/v1/ai/extraction/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert stale.status_code == 200, stale.text
    assert stale.json()["stale"] is True
    assert "ACTIVE_SCHEMA_VERSION_CHANGED" in stale.json()["stale_reasons"]

    actions = {item["action"] for item in audit.json()}
    assert "AI_EXTRACTION_PROPOSAL_CREATED" in actions
    assert "AI_EXTRACTION_FIELD_REVIEWED" in actions
