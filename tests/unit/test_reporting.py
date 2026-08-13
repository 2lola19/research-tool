from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from backend.app.reporting.domain import calculate_absolute_effect, content_hash
from backend.app.reporting.renderers import (
    render_reproducibility_package,
    validate_reproducibility_package,
)


def _payload() -> dict[str, object]:
    return {
        "review": {"id": "review-1", "title": "Synthetic review"},
        "source_references": {
            "prisma_snapshot_id": "prisma-1",
            "meta_analysis_run_ids": ["run-1"],
            "certainty_assessment_ids": ["certainty-1"],
        },
        "sections": {
            "protocol": [{"id": "protocol-1", "version": 1}],
            "search": [{"id": "search-1", "exact_query": "trial"}],
            "citations": [{"id": "article-1"}],
            "screening": {"included": ["article-1"]},
            "prisma": {"counts": {"studies_included_review": 2}},
            "studies": [{"id": "study-1"}, {"id": "study-2"}],
            "extraction": {"verified_values": 4},
            "risk_of_bias": {"assessments": [{"study_id": "study-1"}]},
            "outcomes": {"definitions": [{"id": "outcome-1"}]},
            "analysis": {"runs": [{"id": "run-1", "pooled_effect": "0.750000"}]},
            "certainty": {
                "assessments": [{"id": "certainty-1", "final_certainty": "MODERATE"}],
                "summary_of_findings": [{"outcome_id": "outcome-1", "certainty": "MODERATE"}],
            },
            "provenance": [{"subject_id": "run-1"}],
        },
    }


def test_explicit_baseline_risk_absolute_effects_are_deterministic() -> None:
    rr = calculate_absolute_effect(
        relative_measure="RR", relative_effect="0.75", baseline_risk="0.20"
    )
    odds = calculate_absolute_effect(
        relative_measure="OR", relative_effect="0.5", baseline_risk="0.20"
    )
    assert rr == {
        "baseline_risk": "0.20",
        "treated_risk": "0.1500",
        "risk_difference": "-0.0500",
        "formula_version": "absolute-effect-1",
    }
    assert odds["treated_risk"] == "0.1111111111111111111111111111"
    with pytest.raises(ValueError, match="probability"):
        calculate_absolute_effect(relative_measure="RR", relative_effect="1", baseline_risk="2")
    with pytest.raises(ValueError, match="only for RR and OR"):
        calculate_absolute_effect(relative_measure="HR", relative_effect="1", baseline_risk="0.2")


def test_package_round_trip_checksums_identities_and_determinism() -> None:
    first = render_reproducibility_package(_payload())
    second = render_reproducibility_package(_payload())
    assert first.content == second.content
    assert first.manifest["package_hash"] == second.manifest["package_hash"]
    assert validate_reproducibility_package(first.content) == {"valid": True, "errors": []}
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert "manifest.json" in names
        assert all(".." not in name and not name.startswith("/") for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        for name, expected in manifest["checksums"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
        analysis = json.loads(archive.read("analysis/analysis.json"))
        certainty = json.loads(archive.read("certainty/certainty.json"))
        studies = json.loads(archive.read("studies/studies.json"))
    assert analysis["runs"][0]["id"] == "run-1"
    assert certainty["summary_of_findings"][0]["certainty"] == "MODERATE"
    assert {item["id"] for item in studies} == {"study-1", "study-2"}
    assert content_hash(_payload()) == content_hash(_payload())


def test_package_validator_rejects_tampering() -> None:
    rendered = render_reproducibility_package(_payload())
    source = zipfile.ZipFile(io.BytesIO(rendered.content))
    buffer = io.BytesIO()
    with source, zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "analysis/analysis.json":
                content = b"{}\n"
            target.writestr(info, content)
    result = validate_reproducibility_package(buffer.getvalue())
    assert result["valid"] is False
    assert "checksum mismatch: analysis/analysis.json" in result["errors"]
