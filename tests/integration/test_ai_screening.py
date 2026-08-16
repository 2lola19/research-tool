from __future__ import annotations

from tests.integration.test_tenant_isolation import (
    TenantApi,
    _approved_protocol,
    _create_screening_round,
    _import_screening_fixture,
)

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_blinded_ai_screening_withholds_until_human_decision_and_links_provenance(
    tenant_api: TenantApi,
) -> None:
    articles = _import_screening_fixture(tenant_api)
    article_id = articles[0]["id"]
    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=tenant_api.ids.assigned_review,
        suffix="ai-screening",
    )
    round_record = _create_screening_round(
        tenant_api, name="AI title abstract", stage="TITLE_ABSTRACT"
    )
    assigned = tenant_api.client.post(
        f"/api/v1/screening/rounds/{round_record['id']}/assignments",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={"article_id": article_id, "reviewer_user_id": str(tenant_api.ids.reviewer_a)},
    )
    assert assigned.status_code == 201, assigned.text
    assignment_id = assigned.json()["id"]

    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    policy = tenant_api.client.post(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/policy",
        headers=lead_headers,
        json={"mode": "BLINDED_AI", "maximum_batch_size": 10},
    )
    assert policy.status_code == 201, policy.text

    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    generated = tenant_api.client.post(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/suggestions",
        headers=reviewer_headers,
        json={"assignment_ids": [assignment_id], "protocol_version_id": protocol_id},
    )
    assert generated.status_code == 201, generated.text
    assert generated.json()[0]["mode"] == "BLINDED_AI"
    assert generated.json()[0]["is_revealed"] is False
    assert generated.json()[0]["suggestion"] is None

    withheld = tenant_api.client.get(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/assignments/{assignment_id}/suggestion",
        headers=reviewer_headers,
    )
    assert withheld.status_code == 200, withheld.text
    assert withheld.json()["structured_value"] is None

    decision = tenant_api.client.post(
        f"/api/v1/screening/assignments/{assignment_id}/decision",
        headers=reviewer_headers,
        json={"decision": "INCLUDE"},
    )
    assert decision.status_code == 200, decision.text

    revealed = tenant_api.client.get(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/assignments/{assignment_id}/suggestion",
        headers=reviewer_headers,
    )
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["is_revealed"] is True
    assert revealed.json()["suggestion"] == "MAYBE"

    dataset = tenant_api.client.post(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/evaluation-datasets",
        headers=lead_headers,
        json={
            "logical_key": "screening-fixture",
            "name": "Screening fixture",
            "protocol_version_id": protocol_id,
            "reference_standard": "ADJUDICATED_TITLE_ABSTRACT",
            "cases": [
                {
                    "article_id": article_id,
                    "reference_decision": "RETAIN",
                    "reference_source_type": "ADJUDICATED_TITLE_ABSTRACT",
                }
            ],
        },
    )
    assert dataset.status_code == 201, dataset.text
    evaluation = tenant_api.client.post(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/evaluation-datasets/{dataset.json()['id']}/evaluate",
        headers=lead_headers,
        json={"evaluation_policy": "CONSERVATIVE"},
    )
    assert evaluation.status_code == 201, evaluation.text
    assert evaluation.json()["metrics"]["total_cases"] == 1
    case_results = tenant_api.client.get(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/evaluations/{evaluation.json()['id']}/case-results",
        headers=lead_headers,
    )
    assert case_results.status_code == 200, case_results.text
    assert case_results.json()[0]["suggestion"] == "MAYBE"
    classified = tenant_api.client.post(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/evaluation-case-results/{case_results.json()[0]['id']}/error-classifications",
        headers=lead_headers,
        json={"category": "MISSING_INFORMATION", "notes": "Fixture intentionally uncertain."},
    )
    assert classified.status_code == 201, classified.text

    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/audit",
        headers=reviewer_headers,
    )
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert "AI_SCREENING_PROPOSAL_CREATED" in actions
    assert "AI_SCREENING_DECISION_LINKED" in actions

    foreign = tenant_api.client.get(
        f"/api/v1/ai/screening/reviews/{tenant_api.ids.assigned_review}/assignments/{assignment_id}/suggestion",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign.status_code == 404
