from __future__ import annotations

from tests.integration.test_ai_full_text_screening import _upload_and_process
from tests.integration.test_risk_of_bias import (
    _complete_assessment,
    _create_assessment,
    _install_instrument,
)
from tests.integration.test_studies import _import_screening_fixture
from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _headers(tenant_api: TenantApi, user_id: object) -> dict[str, str]:
    return tenant_api.headers(user_id, tenant_api.ids.organization_a)


def _create_study_with_article(tenant_api: TenantApi) -> tuple[str, str]:
    headers = _headers(tenant_api, tenant_api.ids.lead_a)
    article = _import_screening_fixture(tenant_api)[0]
    study = tenant_api.client.post(
        "/api/v1/studies",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_key": "AI-ROB-001",
            "label": "AI Risk of Bias fixture Study",
            "study_design": "RANDOMIZED_CONTROLLED_TRIAL",
        },
    )
    assert study.status_code == 201, study.text
    linked = tenant_api.client.post(
        f"/api/v1/studies/{study.json()['id']}/articles",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "article_id": article["id"],
            "role": "PRIMARY",
        },
    )
    assert linked.status_code == 201, linked.text
    return str(study.json()["id"]), str(article["id"])


def test_governed_rob_assistance_is_blinded_human_only_and_evaluable(
    tenant_api: TenantApi,
) -> None:
    review_id = tenant_api.ids.assigned_review
    study_id, article_id = _create_study_with_article(tenant_api)
    document_id = _upload_and_process(tenant_api, article_id, "ai-rob-v1")
    version = _install_instrument(tenant_api)
    assessment = _create_assessment(
        tenant_api,
        tenant_api.ids.reviewer_a,
        study_id,
        version["id"],
    )
    lead_headers = _headers(tenant_api, tenant_api.ids.lead_a)
    reviewer_headers = _headers(tenant_api, tenant_api.ids.reviewer_a)

    policy = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/policies",
        headers=lead_headers,
        json={"mode": "BLINDED_AI", "maximum_batch_size": 10},
    )
    assert policy.status_code == 201, policy.text
    readiness = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/readiness",
        headers=reviewer_headers,
        json={
            "assessment_id": assessment["id"],
            "documents": [{"document_id": document_id}],
        },
    )
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["state"] == "READY"

    generated = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/proposals",
        headers=reviewer_headers,
        json={
            "items": [
                {
                    "assessment_id": assessment["id"],
                    "documents": [{"document_id": document_id}],
                }
            ]
        },
    )
    assert generated.status_code == 201, generated.text
    proposal = generated.json()[0]
    assert proposal["status"] == "SUCCEEDED"
    assert proposal["is_revealed"] is False
    assert proposal["structured_value"] is None
    assert proposal["validation_results"] is None
    assert proposal["domain_suggestions"] is None
    assert proposal["overall_suggestion"] is None
    assert proposal["source_manifest"][0]["document_id"] == document_id
    assert proposal["selected_chunk_ids"]

    # The generic AI surface cannot enumerate or expose governed RoB runs/proposals.
    generic_create = tenant_api.client.post(
        "/api/v1/ai/runs",
        headers=lead_headers,
        json={
            "review_id": str(review_id),
            "task_type": "ROB_SUGGESTION",
            "input_data": {"assessment_id": assessment["id"]},
        },
    )
    generic_direct = tenant_api.client.get(
        f"/api/v1/ai/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    generic_runs = tenant_api.client.get(
        f"/api/v1/ai/reviews/{review_id}/runs", headers=reviewer_headers
    )
    assert generic_create.status_code == 409
    assert generic_direct.status_code == 404
    assert all(item["task_type"] != "ROB_SUGGESTION" for item in generic_runs.json())

    canonical_before = tenant_api.client.get(
        f"/api/v1/risk-of-bias/assessments/{assessment['id']}",
        headers=reviewer_headers,
        params={"review_id": str(review_id)},
    )
    assert canonical_before.status_code == 200
    assert canonical_before.json()["answers"] == []

    blinded_review = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/proposals/"
        f"{proposal['proposal_id']}/answers/RANDOM_SEQUENCE/review",
        headers=reviewer_headers,
        json={"action": "UNRESOLVED", "reason": "The assistant abstained."},
    )
    assert blinded_review.status_code == 409

    # Assisted mode reveals the proposal to the assigned human, while still requiring a
    # disposition and never treating an abstention as a canonical answer.
    assisted_policy = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/policies",
        headers=lead_headers,
        json={"mode": "ASSISTED", "maximum_batch_size": 10},
    )
    assert assisted_policy.status_code == 201, assisted_policy.text
    assisted_generated = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/proposals",
        headers=reviewer_headers,
        json={
            "items": [
                {
                    "assessment_id": assessment["id"],
                    "documents": [{"document_id": document_id}],
                }
            ]
        },
    )
    assert assisted_generated.status_code == 201, assisted_generated.text
    assisted_proposal = assisted_generated.json()[0]
    assert assisted_proposal["is_revealed"] is True
    unresolved = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/proposals/"
        f"{assisted_proposal['proposal_id']}/answers/RANDOM_SEQUENCE/review",
        headers=reviewer_headers,
        json={"action": "UNRESOLVED", "reason": "The assistant abstained."},
    )
    assert unresolved.status_code == 200, unresolved.text
    assert unresolved.json()["canonical_answer_recorded"] is False

    # Only the existing human RoB service can write the canonical assessment.
    submitted = _complete_assessment(
        tenant_api,
        tenant_api.ids.reviewer_a,
        assessment["id"],
        high=False,
    )
    assert submitted["status"] == "SUBMITTED"
    revealed = tenant_api.client.get(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/proposals/{proposal['proposal_id']}",
        headers=reviewer_headers,
    )
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["is_revealed"] is True
    assert revealed.json()["structured_value"]["answers"]
    assert revealed.json()["domain_suggestions"] == {
        "RANDOMIZATION": None,
        "MISSING_OUTCOME_DATA": None,
    }

    dataset = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/evaluation-datasets",
        headers=lead_headers,
        json={
            "instrument_version_id": version["id"],
            "logical_key": "rob-fixture",
            "name": "RoB governed assistant fixture",
            "reference_standard": "ADJUDICATED_ASSESSMENT",
            "cases": [
                {
                    "study_id": study_id,
                    "assessment_id": assessment["id"],
                    "reference_answers": {
                        "RANDOM_SEQUENCE": "YES",
                        "ALLOCATION_CONCEALED": "YES",
                        "OUTCOME_DATA_COMPLETE": "YES",
                    },
                    "reference_domains": {
                        "RANDOMIZATION": "LOW",
                        "MISSING_OUTCOME_DATA": "LOW",
                    },
                    "reference_overall": "LOW",
                }
            ],
        },
    )
    assert dataset.status_code == 201, dataset.text
    evaluation = tenant_api.client.post(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/evaluation-datasets/"
        f"{dataset.json()['id']}/evaluate",
        headers=lead_headers,
    )
    assert evaluation.status_code == 201, evaluation.text
    assert evaluation.json()["metrics"]["abstention_rate"] == 1.0
    assert evaluation.json()["metrics"]["calibration"]["status"] == "DESCRIPTIVE_ONLY"
    case_results = tenant_api.client.get(
        f"/api/v1/ai/risk-of-bias/reviews/{review_id}/evaluations/"
        f"{evaluation.json()['id']}/case-results",
        headers=lead_headers,
    )
    assert case_results.status_code == 200
    assert case_results.json()[0]["classification"] == "AI_ABSTAIN"

    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{review_id}/audit", headers=lead_headers
    )
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert {"AI_ROB_PROPOSAL_CREATED", "AI_ROB_ANSWER_REVIEWED"} <= actions


def test_rob_assistance_direct_ids_are_tenant_and_assessor_scoped(
    tenant_api: TenantApi,
) -> None:
    study_id, _ = _create_study_with_article(tenant_api)
    version = _install_instrument(tenant_api)
    assessment = _create_assessment(
        tenant_api,
        tenant_api.ids.reviewer_a,
        study_id,
        version["id"],
    )
    foreign = tenant_api.client.get(
        f"/api/v1/ai/risk-of-bias/reviews/{tenant_api.ids.assigned_review}/assessments/"
        f"{assessment['id']}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    wrong_assessor = tenant_api.client.get(
        f"/api/v1/ai/risk-of-bias/reviews/{tenant_api.ids.assigned_review}/assessments/"
        f"{assessment['id']}",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
    )
    assert foreign.status_code == 404
    assert wrong_assessor.status_code == 404


def test_rob_route_serialization_does_not_leak_unexpected_fields(tenant_api: TenantApi) -> None:
    # This lightweight route assertion keeps the contract visible without creating scientific data.
    response = tenant_api.client.get(
        f"/api/v1/ai/risk-of-bias/reviews/{tenant_api.ids.assigned_review}/proposals",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert all(isinstance(item, dict) for item in response.json())
