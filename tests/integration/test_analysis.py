from __future__ import annotations

import json
from typing import Any

from tests.integration.test_extraction_verification import _run_with_value
from tests.integration.test_tenant_isolation import TenantApi, _import_screening_fixture

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _headers(tenant_api: TenantApi, user: Any) -> dict[str, str]:
    return tenant_api.headers(user, tenant_api.ids.organization_a)


def _verified_studies(tenant_api: TenantApi) -> list[tuple[str, str]]:
    headers = _headers(tenant_api, tenant_api.ids.lead_a)
    review_id = str(tenant_api.ids.assigned_review)
    articles = [*_import_screening_fixture(tenant_api), *_import_screening_fixture(tenant_api)]
    schema = tenant_api.client.post(
        "/api/v1/extraction/schemas",
        headers=headers,
        json={"review_id": review_id, "name": "Analysis source fields"},
    )
    assert schema.status_code == 201, schema.text
    version = tenant_api.client.post(
        "/api/v1/extraction/schema-versions",
        headers=headers,
        json={
            "review_id": review_id,
            "schema_id": schema.json()["id"],
            "fields": [
                {"key": "n", "label": "N", "field_type": "INTEGER", "required": True},
                {
                    "key": "design",
                    "label": "Design",
                    "field_type": "ENUM",
                    "allowed_options": ["RCT"],
                },
            ],
        },
    )
    assert version.status_code == 201, version.text
    result: list[tuple[str, str]] = []
    for index, article in enumerate(articles[:3], start=1):
        study = tenant_api.client.post(
            "/api/v1/studies",
            headers=headers,
            json={
                "review_id": review_id,
                "study_key": f"META-{index}",
                "label": f"Synthetic Study {index}",
                "study_design": "RANDOMIZED_CONTROLLED_TRIAL",
            },
        )
        assert study.status_code == 201, study.text
        linked = tenant_api.client.post(
            f"/api/v1/studies/{study.json()['id']}/articles",
            headers=headers,
            json={
                "review_id": review_id,
                "article_id": article["id"],
                "role": "PRIMARY",
            },
        )
        assert linked.status_code == 201, linked.text
        run_a = _run_with_value(
            tenant_api, study.json()["id"], version.json()["id"], article["id"], index * 10
        )
        run_b = _run_with_value(
            tenant_api, study.json()["id"], version.json()["id"], article["id"], index * 10
        )
        compared = tenant_api.client.post(
            "/api/v1/extraction/verifications/compare",
            headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
            json={"review_id": review_id, "run_a_id": run_a, "run_b_id": run_b},
        )
        assert compared.status_code == 200, compared.text
        run = tenant_api.client.get(
            f"/api/v1/extraction/runs/{run_a}?review_id={review_id}",
            headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        )
        value = next(item for item in run.json()["values"] if item["field_key"] == "n")
        result.append((study.json()["id"], value["id"]))
    return result


def _harmonized_fixture(tenant_api: TenantApi) -> dict[str, Any]:
    studies = _verified_studies(tenant_api)
    lead = _headers(tenant_api, tenant_api.ids.lead_a)
    statistician = _headers(tenant_api, tenant_api.ids.statistician_a)
    reviewer = _headers(tenant_api, tenant_api.ids.reviewer_a)
    review_id = str(tenant_api.ids.assigned_review)
    window = tenant_api.client.post(
        "/api/v1/outcomes/timepoint-windows",
        headers=lead,
        json={
            "review_id": review_id,
            "key": "DAY_28",
            "label": "Day 28",
            "anchor": "INTERVENTION_START",
            "minimum_days": "28",
            "maximum_days": "28",
            "rule_version": "meta-fixture-1",
        },
    )
    unit = tenant_api.client.post(
        "/api/v1/outcomes/units",
        headers=lead,
        json={
            "review_id": review_id,
            "key": "POINT",
            "label": "points",
            "dimension": "SCORE",
            "context_key": "SYNTHETIC",
            "base_unit_key": "POINT",
            "multiplier_to_base": "1",
            "offset_to_base": "0",
            "precision": 6,
            "rule_version": "1",
        },
    )
    assert window.status_code == unit.status_code == 201
    outcome = tenant_api.client.post(
        "/api/v1/outcomes/definitions-with-version",
        headers=lead,
        json={
            "review_id": review_id,
            "key": "SYNTHETIC_SCORE",
            "definition": {
                "name": "Synthetic score",
                "outcome_type": "CONTINUOUS",
                "directionality": "HIGHER_BETTER",
                "role": "PRIMARY",
                "compatible_effect_measures": ["MD"],
                "allowed_unit_ids": [unit.json()["id"]],
                "expected_timepoint_window_ids": [window.json()["id"]],
            },
        },
    )
    assert outcome.status_code == 201, outcome.text
    mappings: list[dict[str, Any]] = []
    estimates: list[dict[str, Any]] = []
    for (study_id, value_id), estimate, variance in zip(
        studies, ("0.2", "0.5", "1.2"), ("0.04", "0.09", "0.16"), strict=True
    ):
        mapping = tenant_api.client.post(
            "/api/v1/outcomes/mappings",
            headers=reviewer,
            json={
                "review_id": review_id,
                "study_id": study_id,
                "extraction_value_id": value_id,
                "outcome_version_id": outcome.json()["version"]["id"],
                "method": "MANUAL",
                "rationale": "Synthetic verified value mapped for golden analysis fixture.",
                "reported_unit_id": unit.json()["id"],
                "normalized_unit_id": unit.json()["id"],
                "reported_time_value": "28",
                "reported_time_unit": "DAY",
                "reported_time_anchor": "INTERVENTION_START",
                "timepoint_window_id": window.json()["id"],
            },
        )
        assert mapping.status_code == 201, mapping.text
        mappings.append(mapping.json())
        effect = tenant_api.client.post(
            "/api/v1/outcomes/effect-estimates",
            headers=statistician,
            json={
                "review_id": review_id,
                "study_id": study_id,
                "outcome_version_id": outcome.json()["version"]["id"],
                "effect_measure": "MD",
                "origin": "REPORTED",
                "estimate": estimate,
                "variance": variance,
                "standard_error": str(float(variance) ** 0.5),
                "variance_scale": "NATURAL",
                "confidence_level": "0.95",
                "adjustment": "UNADJUSTED",
                "analysis_population": "INTENTION_TO_TREAT",
                "timepoint_window_id": window.json()["id"],
                "unit_id": unit.json()["id"],
                "source_mapping_ids": [mapping.json()["id"]],
            },
        )
        assert effect.status_code == 201, effect.text
        estimates.append(effect.json())
    candidate = tenant_api.client.post(
        "/api/v1/outcomes/candidate-sets",
        headers=statistician,
        json={
            "review_id": review_id,
            "outcome_version_id": outcome.json()["version"]["id"],
            "effect_measure": "MD",
            "timepoint_window_id": window.json()["id"],
            "population_label": "Adults",
            "estimate_ids": [item["id"] for item in estimates],
        },
    )
    assert candidate.status_code == 201, candidate.text
    ready = tenant_api.client.post(
        f"/api/v1/outcomes/candidate-sets/{candidate.json()['id']}/evaluate",
        headers=statistician,
        json={"review_id": review_id},
    )
    assert ready.status_code == 201, ready.text
    assert ready.json()["status"] == "READY"
    return {
        "outcome": outcome.json(),
        "window": window.json(),
        "unit": unit.json(),
        "mappings": mappings,
        "estimates": estimates,
        "candidate": candidate.json(),
    }


def _spec_definition(fixture: dict[str, Any], *, model: str = "RANDOM_EFFECTS") -> dict[str, Any]:
    return {
        "outcome_version_id": fixture["outcome"]["version"]["id"],
        "timepoint_window_id": fixture["window"]["id"],
        "synthesis_population": "Adults",
        "intervention": "Intervention A",
        "comparator": "Placebo",
        "eligible_study_designs": ["RANDOMIZED_CONTROLLED_TRIAL"],
        "effect_measure": "MD",
        "model": model,
        "heterogeneity_estimator": "DERSIMONIAN_LAIRD" if model == "RANDOM_EFFECTS" else "NONE",
        "confidence_level": "0.95",
        "transformation": "IDENTITY",
        "ci_method": "NORMAL",
        "zero_event_policy": "BLOCK",
        "missing_variance_policy": "BLOCK",
        "adjustment_policy": "UNADJUSTED_ONLY",
        "analysis_population": "INTENTION_TO_TREAT",
        "selection_policy": "EXPLICIT_ESTIMATE_IDS",
        "multi_arm_policy": "BLOCK",
        "cluster_policy": "BLOCK",
        "crossover_policy": "BLOCK",
        "minimum_studies": 2,
        "prediction_interval": True,
        "standardized_effect_definition": None,
    }


def test_synthetic_review_runs_golden_random_effects_and_forest_plot(
    tenant_api: TenantApi,
) -> None:
    fixture = _harmonized_fixture(tenant_api)
    review_id = str(tenant_api.ids.assigned_review)
    statistician = _headers(tenant_api, tenant_api.ids.statistician_a)
    created = tenant_api.client.post(
        "/api/v1/analysis/specifications-with-version",
        headers=statistician,
        json={"review_id": review_id, "key": "PRIMARY_MD", "definition": _spec_definition(fixture)},
    )
    assert created.status_code == 201, created.text
    analysis_set = tenant_api.client.post(
        "/api/v1/analysis/sets",
        headers=statistician,
        json={
            "review_id": review_id,
            "specification_version_id": created.json()["version"]["id"],
            "candidate_set_id": fixture["candidate"]["id"],
            "selected_estimate_ids": [item["id"] for item in fixture["estimates"]],
        },
    )
    assert analysis_set.status_code == 201, analysis_set.text
    run = tenant_api.client.post(
        "/api/v1/analysis/runs",
        headers=statistician,
        json={"review_id": review_id, "analysis_set_id": analysis_set.json()["id"]},
    )
    assert run.status_code == 201, run.text
    assert run.json()["status"] == "COMPLETED"
    assert abs(float(run.json()["result"]["presentation_estimate"]) - 0.5466480261) < 1e-9
    assert abs(float(run.json()["result"]["heterogeneity"]["tau_squared"]) - 0.1296551724) < 1e-9
    assert len(run.json()["result"]["weights"]) == 3
    assert len(run.json()["result"]["sensitivity"]) == 3
    forest = tenant_api.client.post(
        f"/api/v1/analysis/runs/{run.json()['id']}/forest-plot",
        headers=statistician,
        json={"review_id": review_id},
    )
    assert forest.status_code == 201, forest.text
    downloaded = tenant_api.client.get(
        f"/api/v1/analysis/artifacts/{forest.json()['id']}/download",
        headers=statistician,
        params={"review_id": review_id},
    )
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b'<?xml version="1.0"')
    assert b"Synthetic Study 1" in downloaded.content
    assert downloaded.headers["x-content-sha256"] == forest.json()["sha256"]
    exported = tenant_api.client.post(
        f"/api/v1/exports/reviews/{review_id}",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        json={"format": "JSON"},
    )
    assert exported.status_code == 201, exported.text
    export_download = tenant_api.client.get(
        f"/api/v1/exports/{exported.json()['id']}/download",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
        params={"review_id": review_id},
    )
    package = json.loads(export_download.content)
    assert package["schema_version"] == "review-export-5"
    assert package["analysis"]["meta_analysis_runs"][0]["id"] == run.json()["id"]
    assert len(package["analysis"]["study_weights"]) == 3

    foreign_artifact = tenant_api.client.get(
        f"/api/v1/analysis/artifacts/{forest.json()['id']}/download",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        params={"review_id": str(tenant_api.ids.organization_b_review)},
    )
    assert foreign_artifact.status_code == 404
    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{review_id}/audit",
        headers=_headers(tenant_api, tenant_api.ids.lead_a),
    )
    actions = {item["action"] for item in audit.json()}
    assert {
        "ANALYSIS_SPECIFICATION_VERSIONED",
        "ANALYSIS_SET_CREATED",
        "META_ANALYSIS_STARTED",
        "META_ANALYSIS_COMPLETED",
        "SENSITIVITY_ANALYSIS_COMPLETED",
        "ANALYSIS_ARTIFACT_GENERATED",
    } <= actions

    second = tenant_api.client.post(
        "/api/v1/analysis/specification-versions",
        headers=statistician,
        json={
            "review_id": review_id,
            "specification_id": created.json()["specification"]["id"],
            "definition": {**_spec_definition(fixture), "confidence_level": "0.90"},
        },
    )
    assert second.status_code == 201, second.text
    workspace = tenant_api.client.get(
        f"/api/v1/analysis/reviews/{review_id}",
        headers=_headers(tenant_api, tenant_api.ids.viewer_a),
    )
    assert workspace.status_code == 200
    assert [item["version"] for item in workspace.json()["specifications"][0]["versions"]] == [1, 2]
    assert workspace.json()["runs"][0]["stale"] is True


def test_analysis_rejects_duplicate_studies_and_foreign_access(tenant_api: TenantApi) -> None:
    fixture = _harmonized_fixture(tenant_api)
    review_id = str(tenant_api.ids.assigned_review)
    statistician = _headers(tenant_api, tenant_api.ids.statistician_a)
    first = fixture["estimates"][0]
    duplicate = tenant_api.client.post(
        "/api/v1/outcomes/effect-estimates",
        headers=statistician,
        json={
            "review_id": review_id,
            "study_id": first["study_id"],
            "outcome_version_id": first["outcome_version_id"],
            "effect_measure": "MD",
            "origin": "REPORTED",
            "estimate": "0.25",
            "variance": "0.05",
            "standard_error": "0.22360679775",
            "variance_scale": "NATURAL",
            "confidence_level": "0.95",
            "adjustment": "UNADJUSTED",
            "analysis_population": "INTENTION_TO_TREAT",
            "timepoint_window_id": fixture["window"]["id"],
            "unit_id": fixture["unit"]["id"],
            "source_mapping_ids": [fixture["mappings"][0]["id"]],
        },
    )
    assert duplicate.status_code == 201, duplicate.text
    candidate = tenant_api.client.post(
        "/api/v1/outcomes/candidate-sets",
        headers=statistician,
        json={
            "review_id": review_id,
            "outcome_version_id": first["outcome_version_id"],
            "effect_measure": "MD",
            "timepoint_window_id": fixture["window"]["id"],
            "estimate_ids": [first["id"], duplicate.json()["id"]],
        },
    )
    readiness = tenant_api.client.post(
        f"/api/v1/outcomes/candidate-sets/{candidate.json()['id']}/evaluate",
        headers=statistician,
        json={"review_id": review_id},
    )
    assert readiness.status_code == 201, readiness.text
    assert readiness.json()["status"] == "NOT_READY"
    assert "DUPLICATE_STUDY_ESTIMATE" in {item["code"] for item in readiness.json()["blockers"]}
    spec = tenant_api.client.post(
        "/api/v1/analysis/specifications-with-version",
        headers=statistician,
        json={
            "review_id": review_id,
            "key": "DUPLICATE_CHECK",
            "definition": {**_spec_definition(fixture, model="FIXED_EFFECT"), "minimum_studies": 1},
        },
    )
    blocked = tenant_api.client.post(
        "/api/v1/analysis/sets",
        headers=statistician,
        json={
            "review_id": review_id,
            "specification_version_id": spec.json()["version"]["id"],
            "candidate_set_id": candidate.json()["id"],
            "selected_estimate_ids": [first["id"], duplicate.json()["id"]],
        },
    )
    assert blocked.status_code == 409
    assert "CANDIDATE_NOT_ANALYSIS_READY" in blocked.text
    reviewer_write = tenant_api.client.post(
        "/api/v1/analysis/specifications",
        headers=_headers(tenant_api, tenant_api.ids.reviewer_a),
        json={"review_id": review_id, "key": "FORBIDDEN"},
    )
    foreign = tenant_api.client.get(
        f"/api/v1/analysis/reviews/{review_id}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    cross_review = tenant_api.client.post(
        "/api/v1/analysis/sets",
        headers=_headers(tenant_api, tenant_api.ids.owner_a),
        json={
            "review_id": str(tenant_api.ids.private_review),
            "specification_version_id": spec.json()["version"]["id"],
            "candidate_set_id": candidate.json()["id"],
            "selected_estimate_ids": [first["id"]],
        },
    )
    assert reviewer_write.status_code == 403
    assert foreign.status_code == 404
    assert cross_review.status_code == 404
