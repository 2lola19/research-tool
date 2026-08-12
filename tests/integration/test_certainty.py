from __future__ import annotations

from typing import Any

from tests.integration.test_analysis import _harmonized_fixture, _headers, _spec_definition
from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _setup(tenant_api: TenantApi) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fixture = _harmonized_fixture(tenant_api)
    review_id = str(tenant_api.ids.assigned_review)
    headers = _headers(tenant_api, tenant_api.ids.statistician_a)
    specification = tenant_api.client.post(
        "/api/v1/analysis/specifications-with-version",
        headers=headers,
        json={
            "review_id": review_id,
            "key": "CERTAINTY_MD",
            "definition": _spec_definition(fixture),
        },
    )
    analysis_set = tenant_api.client.post(
        "/api/v1/analysis/sets",
        headers=headers,
        json={
            "review_id": review_id,
            "specification_version_id": specification.json()["version"]["id"],
            "candidate_set_id": fixture["candidate"]["id"],
            "selected_estimate_ids": [item["id"] for item in fixture["estimates"]],
        },
    )
    run = tenant_api.client.post(
        "/api/v1/analysis/runs",
        headers=headers,
        json={"review_id": review_id, "analysis_set_id": analysis_set.json()["id"]},
    )
    framework = tenant_api.client.post(
        "/api/v1/certainty/foundation-framework",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={"review_id": review_id},
    )
    assert specification.status_code == analysis_set.status_code == run.status_code == 201
    assert framework.status_code == 201, framework.text
    return (
        fixture,
        {"specification": specification.json(), "run": run.json()},
        framework.json()["version"],
    )


def _submitted(
    tenant_api: TenantApi,
    fixture: dict[str, Any],
    analysis: dict[str, Any],
    framework: dict[str, Any],
    user: object,
    final: str,
) -> dict[str, Any]:
    review_id = str(tenant_api.ids.assigned_review)
    headers = _headers(tenant_api, user)
    created = tenant_api.client.post(
        "/api/v1/certainty/assessments",
        headers=headers,
        json={
            "review_id": review_id,
            "outcome_version_id": fixture["outcome"]["version"]["id"],
            "timepoint_window_id": fixture["window"]["id"],
            "analysis_specification_version_id": analysis["specification"]["version"]["id"],
            "meta_analysis_run_id": analysis["run"]["id"],
            "framework_version_id": framework["id"],
            "evidence_body_type": "RANDOMIZED",
            "evidence_body": {"study_ids": [item["study_id"] for item in fixture["estimates"]]},
            "starting_certainty": "HIGH",
            "starting_rationale": "Randomized evidence body starts at high certainty.",
        },
    )
    assert created.status_code == 201, created.text
    for domain in framework["definition"]["domains"]:
        choice = domain["choices"][1] if domain["key"] == "RISK_OF_BIAS" else domain["choices"][0]
        saved = tenant_api.client.put(
            f"/api/v1/certainty/assessments/{created.json()['id']}/domains/{domain['key']}",
            headers=headers,
            json={
                "review_id": review_id,
                "judgment": choice["value"],
                "rationale": f"Explicit human rationale for {domain['label']}.",
                "evidence": {"interpretation": "No automatic statistical rule."},
            },
        )
        assert saved.status_code == 200, saved.text
    finalized = tenant_api.client.put(
        f"/api/v1/certainty/assessments/{created.json()['id']}/final",
        headers=headers,
        json={
            "review_id": review_id,
            "final_certainty": final,
            "final_rationale": "Human assessor integrated every explicit judgment.",
            "override_reason": "Explicit assessor override." if final != "MODERATE" else None,
        },
    )
    assert finalized.status_code == 200, finalized.text
    submitted = tenant_api.client.post(
        f"/api/v1/certainty/assessments/{created.json()['id']}/submit",
        headers=headers,
        json={"review_id": review_id},
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


def test_blind_comparison_adjudication_sof_export_and_tenant_boundaries(
    tenant_api: TenantApi,
) -> None:
    fixture, analysis, framework = _setup(tenant_api)
    first = _submitted(
        tenant_api, fixture, analysis, framework, tenant_api.ids.reviewer_a, "MODERATE"
    )
    second = _submitted(
        tenant_api, fixture, analysis, framework, tenant_api.ids.statistician_a, "LOW"
    )
    review_id = str(tenant_api.ids.assigned_review)
    lead_headers = _headers(tenant_api, tenant_api.ids.lead_a)
    hidden = tenant_api.client.get(
        f"/api/v1/certainty/reviews/{review_id}", headers=lead_headers
    ).json()
    assert hidden["assessments"] == []
    assert {item["id"] for item in hidden["comparison_candidates"]} == {first["id"], second["id"]}
    blind_export = tenant_api.client.post(
        f"/api/v1/exports/reviews/{review_id}",
        headers=lead_headers,
        json={"format": "JSON"},
    )
    blind_package = tenant_api.client.get(
        f"/api/v1/exports/{blind_export.json()['id']}/download",
        headers=lead_headers,
        params={"review_id": review_id},
    ).json()
    assert blind_package["certainty"]["assessments"] == []

    retargeted_correction = tenant_api.client.post(
        "/api/v1/certainty/assessments",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={
            "review_id": review_id,
            "outcome_version_id": fixture["outcome"]["version"]["id"],
            "timepoint_window_id": fixture["window"]["id"],
            "analysis_specification_version_id": analysis["specification"]["version"]["id"],
            "meta_analysis_run_id": analysis["run"]["id"],
            "framework_version_id": framework["id"],
            "evidence_body_type": "OBSERVATIONAL",
            "evidence_body": {"study_ids": [item["study_id"] for item in fixture["estimates"]]},
            "starting_certainty": "HIGH",
            "starting_rationale": "Correction attempt must retain its target.",
            "supersedes_assessment_id": first["id"],
        },
    )
    assert retargeted_correction.status_code == 409
    compared = tenant_api.client.post(
        "/api/v1/certainty/comparisons",
        headers=lead_headers,
        json={
            "review_id": review_id,
            "assessment_a_id": first["id"],
            "assessment_b_id": second["id"],
        },
    )
    assert compared.status_code == 201, compared.text
    assert compared.json()["status"] == "CONFLICT"
    adjudicated = tenant_api.client.post(
        f"/api/v1/certainty/comparisons/{compared.json()['id']}/adjudicate",
        headers=lead_headers,
        json={
            "review_id": review_id,
            "resolution_assessment_id": first["id"],
            "rationale": "Human adjudicator selected the moderate assessment.",
        },
    )
    assert adjudicated.status_code == 200
    sof = tenant_api.client.post(
        f"/api/v1/certainty/assessments/{first['id']}/sof-snapshot",
        headers=lead_headers,
        json={"review_id": review_id},
    )
    assert sof.status_code == 201
    assert sof.json()["row"]["absolute_effect"]["status"] == "UNAVAILABLE"
    exported = tenant_api.client.post(
        f"/api/v1/exports/reviews/{review_id}", headers=lead_headers, json={"format": "JSON"}
    )
    package = tenant_api.client.get(
        f"/api/v1/exports/{exported.json()['id']}/download",
        headers=lead_headers,
        params={"review_id": review_id},
    ).json()
    assert package["schema_version"] == "review-export-6"
    assert len(package["certainty"]["assessments"]) == 2
    assert package["certainty"]["comparisons"][0]["status"] == "ADJUDICATED"
    mutation = tenant_api.client.put(
        f"/api/v1/certainty/assessments/{first['id']}/final",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={"review_id": review_id, "final_certainty": "HIGH", "final_rationale": "Forbidden."},
    )
    foreign = tenant_api.client.get(
        f"/api/v1/certainty/reviews/{review_id}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert mutation.status_code == 409
    assert foreign.status_code == 404


def test_wrong_outcome_and_stale_analysis_are_rejected(tenant_api: TenantApi) -> None:
    fixture, analysis, framework = _setup(tenant_api)
    review_id = str(tenant_api.ids.assigned_review)
    changed = tenant_api.client.post(
        "/api/v1/analysis/specification-versions",
        headers=_headers(tenant_api, tenant_api.ids.statistician_a),
        json={
            "review_id": review_id,
            "specification_id": analysis["specification"]["specification"]["id"],
            "definition": {**_spec_definition(fixture), "confidence_level": "0.90"},
        },
    )
    assert changed.status_code == 201
    stale = tenant_api.client.post(
        "/api/v1/certainty/assessments",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={
            "review_id": review_id,
            "outcome_version_id": fixture["outcome"]["version"]["id"],
            "timepoint_window_id": fixture["window"]["id"],
            "analysis_specification_version_id": analysis["specification"]["version"]["id"],
            "meta_analysis_run_id": analysis["run"]["id"],
            "framework_version_id": framework["id"],
            "evidence_body_type": "RANDOMIZED",
            "evidence_body": {},
            "starting_certainty": "HIGH",
            "starting_rationale": "Explicit starting rationale.",
        },
    )
    assert stale.status_code == 409
    assert "stale meta-analysis runs" in stale.text
