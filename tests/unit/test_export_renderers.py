from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from uuid import UUID

from backend.app.exports.domain import (
    ExportArticle,
    ExportDataset,
    ExportFormat,
    ExportRiskOfBiasAssessment,
    ExportRiskOfBiasComparison,
    ExportSearchExecution,
    ExportStudy,
)
from backend.app.exports.renderers import render_export


def _dataset() -> ExportDataset:
    article_id = UUID("00000000-0000-0000-0000-000000000004")
    return ExportDataset(
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        review_id=UUID("00000000-0000-0000-0000-000000000002"),
        review_title="Deterministic review",
        prisma_snapshot_id=UUID("00000000-0000-0000-0000-000000000003"),
        prisma_algorithm_version="prisma-2020-deterministic-2",
        prisma_counts={
            "records_identified_databases": 1,
            "full_text_exclusion_reasons": {"population": 1},
        },
        prisma_readiness={"ready_for_final": False, "blockers": [{"code": "INCOMPLETE"}]},
        prisma_source_references={"article_ids": [str(article_id)]},
        articles=(
            ExportArticle(
                id=article_id,
                title=" \t=unsafe spreadsheet title",
                abstract="Stable abstract",
                publication_year=2026,
                doi="10.1000/test",
                pmid="123",
                authors=("Researcher, A",),
                journal="Journal",
                source_record_ids=(UUID("00000000-0000-0000-0000-000000000005"),),
                study_keys=("study-1",),
            ),
        ),
        studies=(
            ExportStudy(
                id=UUID("00000000-0000-0000-0000-000000000006"),
                study_key="study-1",
                label="Study one",
                article_ids=(article_id,),
            ),
        ),
        search_executions=(
            ExportSearchExecution(
                id=UUID("00000000-0000-0000-0000-000000000007"),
                source_name="PubMed",
                provider_name="NCBI",
                platform_name="PubMed",
                source_classification="BIBLIOGRAPHIC_DATABASE",
                method="FILE_IMPORT",
                executed_at=datetime(2026, 8, 11, 10, tzinfo=UTC),
                search_strategy_version_id=UUID("00000000-0000-0000-0000-000000000008"),
                search_translation_id=None,
                exact_query="review[Title]",
                filters=(("language", "all"),),
                software_version="fixture/1",
                status="COMPLETED",
                provider_result_count=1,
                imported_record_count=1,
                status_history=((1, "COMPLETED", datetime(2026, 8, 11, 10, tzinfo=UTC), 1, None),),
            ),
        ),
        risk_of_bias_assessments=(
            ExportRiskOfBiasAssessment(
                id=UUID("00000000-0000-0000-0000-000000000009"),
                study_id=UUID("00000000-0000-0000-0000-000000000006"),
                instrument_version_id=UUID("00000000-0000-0000-0000-000000000010"),
                instrument_version=1,
                instrument_content_hash="a" * 64,
                assessor_user_id=UUID("00000000-0000-0000-0000-000000000011"),
                round_number=1,
                revision=1,
                supersedes_assessment_id=None,
                status="SUBMITTED",
                overall_suggested_judgment="LOW",
                overall_final_judgment="LOW",
                overall_rationale="Structured synthesis",
                answers=(("Q1", "YES", "Reported", None),),
                domain_judgments=(("D1", "LOW", "LOW", "Reported", None, None),),
            ),
        ),
        risk_of_bias_comparisons=(
            ExportRiskOfBiasComparison(
                id=UUID("00000000-0000-0000-0000-000000000012"),
                study_id=UUID("00000000-0000-0000-0000-000000000006"),
                instrument_version_id=UUID("00000000-0000-0000-0000-000000000010"),
                round_number=1,
                assessment_a_id=UUID("00000000-0000-0000-0000-000000000009"),
                assessment_b_id=UUID("00000000-0000-0000-0000-000000000013"),
                status="CONFLICT",
                differences=(
                    {"scope": "domain", "key": "D1", "value_a": "LOW", "value_b": "HIGH"},
                ),
                adjudicated_snapshot=None,
                adjudicated_by_user_id=None,
                adjudication_reason=None,
            ),
        ),
        outcome_versions=(
            {
                "id": "00000000-0000-0000-0000-000000000014",
                "outcome_id": "00000000-0000-0000-0000-000000000015",
                "outcome_key": "MORTALITY",
                "version": 1,
                "definition": {
                    "name": "All-cause mortality",
                    "compatible_effect_measures": ["RR"],
                },
                "content_hash": "b" * 64,
                "protocol_version_id": None,
            },
        ),
        outcome_mappings=(
            {
                "id": "00000000-0000-0000-0000-000000000016",
                "study_id": "00000000-0000-0000-0000-000000000006",
                "reported_value": "10",
                "normalized_time_days": "28",
                "extraction_verified": True,
            },
        ),
        effect_estimates=(
            {
                "id": "00000000-0000-0000-0000-000000000017",
                "study_id": "00000000-0000-0000-0000-000000000006",
                "outcome_version_id": "00000000-0000-0000-0000-000000000014",
                "effect_measure": "RR",
                "origin": "DERIVED",
                "estimate": "0.5",
                "variance_scale": "LOG",
                "components": {"events_intervention": "10"},
            },
        ),
        synthesis_candidate_sets=(
            {
                "id": "00000000-0000-0000-0000-000000000018",
                "outcome_version_id": "00000000-0000-0000-0000-000000000014",
                "effect_measure": "RR",
                "estimate_ids": ["00000000-0000-0000-0000-000000000017"],
            },
        ),
        analysis_readiness=(
            {
                "id": "00000000-0000-0000-0000-000000000019",
                "candidate_set_id": "00000000-0000-0000-0000-000000000018",
                "algorithm_version": "analysis-readiness-1",
                "status": "READY",
                "blockers": [],
            },
        ),
        analysis_specification_versions=(
            {
                "id": "00000000-0000-0000-0000-000000000020",
                "specification_id": "00000000-0000-0000-0000-000000000021",
                "version": 1,
                "definition": {"model": "FIXED_EFFECT", "effect_measure": "RR"},
                "content_hash": "c" * 64,
            },
        ),
        analysis_sets=(
            {
                "id": "00000000-0000-0000-0000-000000000022",
                "included_estimate_ids": ["00000000-0000-0000-0000-000000000017"],
                "excluded_estimates": [],
                "input_hash": "d" * 64,
            },
        ),
        meta_analysis_runs=(
            {
                "id": "00000000-0000-0000-0000-000000000023",
                "status": "COMPLETED",
                "algorithm_version": "meta-analysis-1",
                "input_hash": "d" * 64,
                "result_hash": "e" * 64,
                "result": {"presentation_estimate": "0.5"},
            },
        ),
        analysis_study_weights=(
            {
                "run_id": "00000000-0000-0000-0000-000000000023",
                "study_id": "00000000-0000-0000-0000-000000000006",
                "normalized_weight_percent": "100.000000000000",
            },
        ),
        analysis_sensitivities=(),
        analysis_artifacts=(
            {
                "id": "00000000-0000-0000-0000-000000000024",
                "run_id": "00000000-0000-0000-0000-000000000023",
                "artifact_type": "FOREST_PLOT_SVG",
                "sha256": "f" * 64,
            },
        ),
    )


def test_all_export_formats_are_byte_reproducible() -> None:
    dataset = _dataset()
    for export_format in ExportFormat:
        first = render_export(export_format, dataset)
        second = render_export(export_format, dataset)
        assert first.content == second.content
        assert first.content


def test_csv_neutralizes_spreadsheet_formula_prefixes() -> None:
    rendered = render_export(ExportFormat.CSV, _dataset())
    rows = list(csv.reader(io.StringIO(rendered.content.decode("utf-8-sig"))))
    assert rows[1][1] == "' \t=unsafe spreadsheet title"


def test_xlsx_contains_expected_portable_sheets() -> None:
    rendered = render_export(ExportFormat.XLSX, _dataset())
    with zipfile.ZipFile(io.BytesIO(rendered.content)) as workbook:
        assert workbook.testzip() is None
        assert {
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
            "xl/worksheets/sheet3.xml",
            "xl/worksheets/sheet4.xml",
            "xl/worksheets/sheet5.xml",
            "xl/worksheets/sheet6.xml",
            "xl/worksheets/sheet7.xml",
            "xl/worksheets/sheet8.xml",
            "xl/worksheets/sheet9.xml",
            "xl/worksheets/sheet10.xml",
            "xl/worksheets/sheet11.xml",
            "xl/worksheets/sheet12.xml",
            "xl/worksheets/sheet13.xml",
            "xl/worksheets/sheet14.xml",
            "xl/worksheets/sheet15.xml",
            "xl/worksheets/sheet16.xml",
            "xl/worksheets/sheet17.xml",
            "xl/worksheets/sheet18.xml",
            "xl/worksheets/sheet19.xml",
            "xl/worksheets/sheet20.xml",
        } <= set(workbook.namelist())
        articles_xml = workbook.read("xl/worksheets/sheet4.xml").decode()
        executions_xml = workbook.read("xl/worksheets/sheet6.xml").decode()
    assert "=unsafe spreadsheet title" in articles_xml
    assert "<f>" not in articles_xml
    assert "review[Title]" in executions_xml


def test_json_contains_versioned_scientific_and_analysis_documentation() -> None:
    rendered = render_export(ExportFormat.JSON, _dataset())
    payload = json.loads(rendered.content)
    assert payload["schema_version"] == "review-export-5"
    assert payload["search_executions"][0]["source_classification"] == ("BIBLIOGRAPHIC_DATABASE")
    assert payload["search_executions"][0]["filters"] == {"language": "all"}
    assert payload["risk_of_bias"]["assessments"][0]["instrument_version"] == 1
    assert payload["risk_of_bias"]["comparisons"][0]["status"] == "CONFLICT"
    assert payload["outcomes"]["effect_estimates"][0]["variance_scale"] == "LOG"
    assert payload["outcomes"]["analysis_readiness"][0]["status"] == "READY"
    assert payload["analysis"]["meta_analysis_runs"][0]["algorithm_version"] == ("meta-analysis-1")
    assert payload["analysis"]["study_weights"][0]["normalized_weight_percent"] == (
        "100.000000000000"
    )
