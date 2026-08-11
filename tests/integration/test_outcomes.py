from __future__ import annotations

from typing import Any
from uuid import UUID

from tests.integration.test_extraction_verification import _run_with_value
from tests.integration.test_manual_extraction import _schema_and_study
from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _headers(tenant_api: TenantApi, user_id: UUID) -> dict[str, str]:
    return tenant_api.headers(user_id, tenant_api.ids.organization_a)


def _verified_value(tenant_api: TenantApi) -> tuple[str, str]:
    study_id, schema_version_id, article_id = _schema_and_study(tenant_api)
    run_a = _run_with_value(tenant_api, study_id, schema_version_id, article_id, 10)
    run_b = _run_with_value(tenant_api, study_id, schema_version_id, article_id, 10)
    compared = tenant_api.client.post(
        "/api/v1/extraction/verifications/compare",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "run_a_id": run_a,
            "run_b_id": run_b,
        },
    )
    assert compared.status_code == 200, compared.text
    run = tenant_api.client.get(
        f"/api/v1/extraction/runs/{run_a}?review_id={tenant_api.ids.assigned_review}",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
    )
    assert run.status_code == 200, run.text
    value = next(item for item in run.json()["values"] if item["field_key"] == "n")
    return study_id, value["id"]


def _foundation(tenant_api: TenantApi) -> dict[str, Any]:
    headers = _headers(tenant_api, tenant_api.ids.lead_a)
    review_id = str(tenant_api.ids.assigned_review)
    window = tenant_api.client.post(
        "/api/v1/outcomes/timepoint-windows",
        headers=headers,
        json={
            "review_id": review_id,
            "key": "FOUR_WEEKS",
            "label": "4 weeks +/- 7 days",
            "anchor": "INTERVENTION_START",
            "minimum_days": "21",
            "maximum_days": "35",
            "rule_version": "protocol-window-1",
        },
    )
    assert window.status_code == 201, window.text
    created = tenant_api.client.post(
        "/api/v1/outcomes/definitions-with-version",
        headers=headers,
        json={
            "review_id": review_id,
            "key": "ALL_CAUSE_MORTALITY",
            "definition": {
                "name": "All-cause mortality",
                "description": "Death from any cause within the configured window.",
                "outcome_type": "DICHOTOMOUS",
                "directionality": "HIGHER_WORSE",
                "role": "PRIMARY",
                "compatible_effect_measures": ["RR", "OR", "RD"],
                "expected_timepoint_window_ids": [window.json()["id"]],
            },
        },
    )
    assert created.status_code == 201, created.text
    return {
        "outcome": created.json()["outcome"],
        "version": created.json()["version"],
        "window": window.json(),
    }


def _mapping(
    tenant_api: TenantApi, foundation: dict[str, Any], study_id: str, value_id: str
) -> dict[str, Any]:
    response = tenant_api.client.post(
        "/api/v1/outcomes/mappings",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_id": study_id,
            "extraction_value_id": value_id,
            "outcome_version_id": foundation["version"]["id"],
            "method": "MANUAL",
            "rationale": "Verified event count maps to protocol-defined mortality.",
            "reported_time_value": "4",
            "reported_time_unit": "WEEK",
            "reported_time_anchor": "INTERVENTION_START",
            "timepoint_window_id": foundation["window"]["id"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _estimate(
    tenant_api: TenantApi, foundation: dict[str, Any], mapping: dict[str, Any]
) -> dict[str, Any]:
    response = tenant_api.client.post(
        "/api/v1/outcomes/effect-estimates",
        headers=_headers(tenant_api, tenant_api.ids.statistician_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_id": mapping["study_id"],
            "outcome_version_id": foundation["version"]["id"],
            "effect_measure": "RR",
            "origin": "DERIVED",
            "adjustment": "UNADJUSTED",
            "analysis_population": "INTENTION_TO_TREAT",
            "timepoint_window_id": foundation["window"]["id"],
            "components": {
                "events_intervention": "10",
                "sample_intervention": "100",
                "events_comparator": "20",
                "sample_comparator": "100",
            },
            "source_mapping_ids": [mapping["id"]],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_versioned_mapping_effect_derivation_and_ready_candidate(tenant_api: TenantApi) -> None:
    study_id, value_id = _verified_value(tenant_api)
    foundation = _foundation(tenant_api)
    mapping = _mapping(tenant_api, foundation, study_id, value_id)
    assert mapping["reported_value"].startswith("10")
    assert mapping["normalized_time_days"].startswith("28")
    assert mapping["extraction_verified"] is True
    estimate = _estimate(tenant_api, foundation, mapping)
    assert estimate["estimate"].startswith("0.5")
    assert estimate["variance_scale"] == "LOG"
    assert estimate["calculation_version"] == "effect-foundation-1"
    candidate = tenant_api.client.post(
        "/api/v1/outcomes/candidate-sets",
        headers=_headers(tenant_api, tenant_api.ids.statistician_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "outcome_version_id": foundation["version"]["id"],
            "effect_measure": "RR",
            "timepoint_window_id": foundation["window"]["id"],
            "population_label": "Adults",
            "estimate_ids": [estimate["id"]],
        },
    )
    assert candidate.status_code == 201, candidate.text
    readiness = tenant_api.client.post(
        f"/api/v1/outcomes/candidate-sets/{candidate.json()['id']}/evaluate",
        headers=_headers(tenant_api, tenant_api.ids.statistician_a),
        json={"review_id": str(tenant_api.ids.assigned_review)},
    )
    assert readiness.status_code == 201, readiness.text
    assert readiness.json()["status"] == "READY"
    assert readiness.json()["blockers"] == []
    cross_review = tenant_api.client.post(
        "/api/v1/outcomes/candidate-sets",
        headers=_headers(tenant_api, tenant_api.ids.owner_a),
        json={
            "review_id": str(tenant_api.ids.private_review),
            "outcome_version_id": foundation["version"]["id"],
            "effect_measure": "RR",
            "estimate_ids": [estimate["id"]],
        },
    )
    assert cross_review.status_code == 404
    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/audit",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
    )
    assert {"OUTCOME_MAPPED", "EFFECT_ESTIMATE_DERIVED", "ANALYSIS_READINESS_EVALUATED"} <= {
        item["action"] for item in audit.json()
    }


def test_duplicate_study_estimates_and_zero_events_are_explicit_blockers(
    tenant_api: TenantApi,
) -> None:
    study_id, value_id = _verified_value(tenant_api)
    foundation = _foundation(tenant_api)
    mapping = _mapping(tenant_api, foundation, study_id, value_id)
    first = _estimate(tenant_api, foundation, mapping)
    second = _estimate(tenant_api, foundation, mapping)
    candidate = tenant_api.client.post(
        "/api/v1/outcomes/candidate-sets",
        headers=_headers(tenant_api, tenant_api.ids.statistician_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "outcome_version_id": foundation["version"]["id"],
            "effect_measure": "RR",
            "timepoint_window_id": foundation["window"]["id"],
            "estimate_ids": [first["id"], second["id"]],
        },
    )
    readiness = tenant_api.client.post(
        f"/api/v1/outcomes/candidate-sets/{candidate.json()['id']}/evaluate",
        headers=_headers(tenant_api, tenant_api.ids.statistician_a),
        json={"review_id": str(tenant_api.ids.assigned_review)},
    )
    assert readiness.status_code == 201, readiness.text
    assert "DUPLICATE_STUDY_ESTIMATE" in {item["code"] for item in readiness.json()["blockers"]}

    zero_payload = {
        "review_id": str(tenant_api.ids.assigned_review),
        "study_id": study_id,
        "outcome_version_id": foundation["version"]["id"],
        "effect_measure": "RR",
        "origin": "DERIVED",
        "timepoint_window_id": foundation["window"]["id"],
        "components": {
            "events_intervention": "0",
            "sample_intervention": "50",
            "events_comparator": "0",
            "sample_comparator": "50",
        },
        "source_mapping_ids": [mapping["id"]],
    }
    zero = tenant_api.client.post(
        "/api/v1/outcomes/effect-estimates",
        headers=_headers(tenant_api, tenant_api.ids.statistician_a),
        json=zero_payload,
    )
    assert zero.status_code == 201, zero.text
    assert zero.json()["estimate"] is None
    assert zero.json()["zero_event_pattern"] == "DOUBLE_ZERO"


def test_outcomes_are_versioned_and_tenant_role_scoped(tenant_api: TenantApi) -> None:
    foundation = _foundation(tenant_api)
    second = tenant_api.client.post(
        "/api/v1/outcomes/versions",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "outcome_id": foundation["outcome"]["id"],
            "definition": {
                "name": "All-cause mortality",
                "description": "Revised prospective definition",
                "outcome_type": "DICHOTOMOUS",
                "directionality": "HIGHER_WORSE",
                "role": "PRIMARY",
                "compatible_effect_measures": ["RR"],
                "expected_timepoint_window_ids": [foundation["window"]["id"]],
            },
        },
    )
    assert second.status_code == 201, second.text
    listed = tenant_api.client.get(
        f"/api/v1/outcomes/reviews/{tenant_api.ids.assigned_review}",
        headers=_headers(tenant_api, tenant_api.ids.viewer_a),
    )
    assert [item["version"] for item in listed.json()[0]["versions"]] == [1, 2]
    viewer_write = tenant_api.client.post(
        "/api/v1/outcomes/definitions",
        headers=_headers(tenant_api, tenant_api.ids.viewer_a),
        json={"review_id": str(tenant_api.ids.assigned_review), "key": "FORBIDDEN"},
    )
    foreign = tenant_api.client.get(
        f"/api/v1/outcomes/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert viewer_write.status_code == 403
    assert foreign.status_code == 404
