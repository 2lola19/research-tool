from __future__ import annotations

from typing import Any

from tests.integration.test_tenant_isolation import tenant_api as tenant_api


def _headers(tenant_api: Any, user_id: object) -> dict[str, str]:
    return tenant_api.headers(user_id, tenant_api.ids.organization_a)


def _install_instrument(tenant_api: Any) -> dict[str, Any]:
    response = tenant_api.client.post(
        "/api/v1/risk-of-bias/demonstration-instrument",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={"review_id": str(tenant_api.ids.assigned_review)},
    )
    assert response.status_code == 201, response.text
    version = response.json()["version"]
    decision = tenant_api.client.post(
        f"/api/v1/risk-of-bias/instrument-versions/{version['id']}/decision",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "decision": "APPROVED",
            "reason": "Approved for framework validation only.",
        },
    )
    assert decision.status_code == 200, decision.text
    return decision.json()


def _create_study(
    tenant_api: Any, *, design: str = "RANDOMIZED_CONTROLLED_TRIAL", suffix: str = "primary"
) -> dict[str, Any]:
    response = tenant_api.client.post(
        "/api/v1/studies",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_key": f"ROB-{design}-{suffix}",
            "label": "Risk of Bias test Study",
            "study_design": design,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_assessment(
    tenant_api: Any, user_id: object, study_id: str, version_id: str
) -> dict[str, Any]:
    response = tenant_api.client.post(
        "/api/v1/risk-of-bias/assessments",
        headers=_headers(tenant_api, user_id),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_id": study_id,
            "instrument_version_id": version_id,
            "round_number": 1,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _complete_assessment(
    tenant_api: Any, user_id: object, assessment_id: str, *, high: bool
) -> dict[str, Any]:
    headers = _headers(tenant_api, user_id)
    review_id = str(tenant_api.ids.assigned_review)
    answers = {
        "RANDOM_SEQUENCE": "NO" if high else "YES",
        "ALLOCATION_CONCEALED": "YES",
        "OUTCOME_DATA_COMPLETE": "YES",
    }
    for key, answer in answers.items():
        response = tenant_api.client.put(
            f"/api/v1/risk-of-bias/assessments/{assessment_id}/answers/{key}",
            headers=headers,
            json={"review_id": review_id, "answer": answer, "rationale": f"Rationale {key}"},
        )
        assert response.status_code == 200, response.text
    for key, judgment in (
        ("RANDOMIZATION", "HIGH" if high else "LOW"),
        ("MISSING_OUTCOME_DATA", "LOW"),
    ):
        response = tenant_api.client.put(
            f"/api/v1/risk-of-bias/assessments/{assessment_id}/domains/{key}",
            headers=headers,
            json={
                "review_id": review_id,
                "final_judgment": judgment,
                "rationale": f"Domain rationale {key}",
            },
        )
        assert response.status_code == 200, response.text
    overall = "HIGH" if high else "LOW"
    saved = tenant_api.client.put(
        f"/api/v1/risk-of-bias/assessments/{assessment_id}/overall",
        headers=headers,
        json={
            "review_id": review_id,
            "final_judgment": overall,
            "rationale": "Overall structured synthesis.",
        },
    )
    assert saved.status_code == 200, saved.text
    submitted = tenant_api.client.post(
        f"/api/v1/risk-of-bias/assessments/{assessment_id}/submit",
        headers=headers,
        json={"review_id": review_id},
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


def test_instrument_versioning_design_compatibility_and_role_boundaries(tenant_api: Any) -> None:
    version = _install_instrument(tenant_api)
    duplicate_decision = tenant_api.client.post(
        f"/api/v1/risk-of-bias/instrument-versions/{version['id']}/decision",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={"review_id": str(tenant_api.ids.assigned_review), "decision": "REJECTED"},
    )
    viewer_install = tenant_api.client.post(
        "/api/v1/risk-of-bias/demonstration-instrument",
        headers=_headers(tenant_api, tenant_api.ids.viewer_a),
        json={"review_id": str(tenant_api.ids.assigned_review)},
    )
    incompatible = _create_study(tenant_api, design="DIAGNOSTIC_ACCURACY")
    rejected = tenant_api.client.post(
        "/api/v1/risk-of-bias/assessments",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_id": incompatible["id"],
            "instrument_version_id": version["id"],
            "round_number": 1,
        },
    )
    assert duplicate_decision.status_code == 409
    assert viewer_install.status_code == 403
    assert rejected.status_code == 409


def test_independent_blinded_assessments_conflict_and_adjudication(tenant_api: Any) -> None:
    version = _install_instrument(tenant_api)
    study = _create_study(tenant_api)
    lead = _create_assessment(tenant_api, tenant_api.ids.lead_a, study["id"], version["id"])
    reviewer = _create_assessment(tenant_api, tenant_api.ids.reviewer_a, study["id"], version["id"])

    hidden = tenant_api.client.get(
        f"/api/v1/risk-of-bias/assessments/{lead['id']}?review_id={tenant_api.ids.assigned_review}",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
    )
    reviewer_list = tenant_api.client.get(
        f"/api/v1/risk-of-bias/reviews/{tenant_api.ids.assigned_review}/assessments",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
    )
    assert hidden.status_code == 404
    assert [item["id"] for item in reviewer_list.json()] == [reviewer["id"]]
    viewer_before_reveal = tenant_api.client.get(
        f"/api/v1/risk-of-bias/reviews/{tenant_api.ids.assigned_review}/assessments",
        headers=_headers(tenant_api, tenant_api.ids.viewer_a),
    )
    assert viewer_before_reveal.json() == []

    lead = _complete_assessment(tenant_api, tenant_api.ids.lead_a, lead["id"], high=False)
    reviewer = _complete_assessment(
        tenant_api, tenant_api.ids.reviewer_a, reviewer["id"], high=True
    )
    immutable = tenant_api.client.put(
        f"/api/v1/risk-of-bias/assessments/{reviewer['id']}/answers/RANDOM_SEQUENCE",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={"review_id": str(tenant_api.ids.assigned_review), "answer": "YES"},
    )
    assert immutable.status_code == 409

    compared = tenant_api.client.post(
        "/api/v1/risk-of-bias/comparisons",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "assessment_a_id": lead["id"],
            "assessment_b_id": reviewer["id"],
        },
    )
    assert compared.status_code == 201, compared.text
    assert compared.json()["status"] == "CONFLICT"
    assert {(item["scope"], item["key"]) for item in compared.json()["differences"]} == {
        ("answer", "RANDOM_SEQUENCE"),
        ("domain", "RANDOMIZATION"),
        ("overall", "overall"),
    }
    viewer_after_reveal = tenant_api.client.get(
        f"/api/v1/risk-of-bias/reviews/{tenant_api.ids.assigned_review}/assessments",
        headers=_headers(tenant_api, tenant_api.ids.viewer_a),
    )
    assert {item["id"] for item in viewer_after_reveal.json()} == {lead["id"], reviewer["id"]}
    adjudicated = tenant_api.client.post(
        f"/api/v1/risk-of-bias/comparisons/{compared.json()['id']}/adjudicate",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "resolution_assessment_id": reviewer["id"],
            "rationale": "Senior reviewer accepted the documented high-risk assessment.",
        },
    )
    unauthorized = tenant_api.client.post(
        f"/api/v1/risk-of-bias/comparisons/{compared.json()['id']}/adjudicate",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "resolution_assessment_id": lead["id"],
            "rationale": "Not authorized.",
        },
    )
    assert adjudicated.status_code == 200, adjudicated.text
    assert adjudicated.json()["status"] == "ADJUDICATED"
    assert unauthorized.status_code == 403

    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/audit",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
    )
    actions = {event["action"] for event in audit.json()}
    assert {"ROB_ASSESSMENT_SUBMITTED", "ROB_CONFLICT_CREATED", "ROB_ADJUDICATED"} <= actions


def test_risk_of_bias_direct_ids_are_tenant_and_review_scoped(tenant_api: Any) -> None:
    version = _install_instrument(tenant_api)
    study = _create_study(tenant_api)
    assessment = _create_assessment(
        tenant_api, tenant_api.ids.reviewer_a, study["id"], version["id"]
    )
    foreign = tenant_api.client.get(
        f"/api/v1/risk-of-bias/assessments/{assessment['id']}?review_id={tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    wrong_review = tenant_api.client.get(
        f"/api/v1/risk-of-bias/assessments/{assessment['id']}?review_id={tenant_api.ids.private_review}",
        headers=_headers(tenant_api, tenant_api.ids.owner_a),
    )
    assert foreign.status_code == wrong_review.status_code == 404


def test_assessment_evidence_can_span_articles_in_one_study_family(tenant_api: Any) -> None:
    version = _install_instrument(tenant_api)
    study = _create_study(tenant_api)
    headers = _headers(tenant_api, tenant_api.ids.lead_a)
    imported = tenant_api.client.post(
        "/api/v1/citations/imports",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_format": "CSV",
            "source_name": "rob-evidence.csv",
            "content": (
                "title,year,doi\n"
                "Trial protocol,2025,10.18/protocol\n"
                "Trial results,2026,10.18/results\n"
            ),
        },
    )
    assert imported.status_code == 201, imported.text
    articles = tenant_api.client.get(
        f"/api/v1/citations/reviews/{tenant_api.ids.assigned_review}/articles",
        headers=headers,
    ).json()
    selected = {item["doi"]: item for item in articles}
    evidence_ids: list[str] = []
    for doi, role in (("10.18/protocol", "PROTOCOL"), ("10.18/results", "PRIMARY")):
        article = selected[doi]
        linked = tenant_api.client.post(
            f"/api/v1/studies/{study['id']}/articles",
            headers=headers,
            json={
                "review_id": str(tenant_api.ids.assigned_review),
                "article_id": article["id"],
                "role": role,
                "method": "MANUAL",
            },
        )
        assert linked.status_code == 201, linked.text
        document = tenant_api.client.post(
            f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/articles/{article['id']}/retrieval-record",
            headers=headers,
            json={
                "status": "EXTERNAL_LINK_ONLY",
                "retrieval_method": "EXTERNAL_LINK",
                "source_name": "Publisher record",
                "source_url": f"https://example.test/{doi}",
            },
        )
        assert document.status_code == 201, document.text
        evidence = tenant_api.client.post(
            f"/api/v1/documents/{document.json()['id']}/evidence-locations",
            headers=headers,
            json={
                "page_number": 2 if role == "PROTOCOL" else 8,
                "section": "Methods" if role == "PROTOCOL" else "Results",
                "source_text": f"Structured {role.lower()} evidence",
            },
        )
        assert evidence.status_code == 200, evidence.text
        evidence_ids.append(evidence.json()["id"])

    assessment = _create_assessment(tenant_api, tenant_api.ids.lead_a, study["id"], version["id"])
    for question, evidence_id in (
        ("RANDOM_SEQUENCE", evidence_ids[0]),
        ("OUTCOME_DATA_COMPLETE", evidence_ids[1]),
    ):
        saved = tenant_api.client.put(
            f"/api/v1/risk-of-bias/assessments/{assessment['id']}/answers/{question}",
            headers=headers,
            json={
                "review_id": str(tenant_api.ids.assigned_review),
                "answer": "YES",
                "rationale": "Evidence from the linked Study Family document.",
                "evidence_location_id": evidence_id,
            },
        )
        assert saved.status_code == 200, saved.text
    current = tenant_api.client.get(
        f"/api/v1/risk-of-bias/assessments/{assessment['id']}?review_id={tenant_api.ids.assigned_review}",
        headers=headers,
    ).json()
    assert {item["evidence_location_id"] for item in current["answers"]} == set(evidence_ids)

    unrelated_study = _create_study(tenant_api, suffix="unrelated")
    unrelated_assessment = _create_assessment(
        tenant_api, tenant_api.ids.lead_a, unrelated_study["id"], version["id"]
    )
    rejected = tenant_api.client.put(
        f"/api/v1/risk-of-bias/assessments/{unrelated_assessment['id']}/answers/RANDOM_SEQUENCE",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "answer": "YES",
            "evidence_location_id": evidence_ids[0],
        },
    )
    assert rejected.status_code == 409
