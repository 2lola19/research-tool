from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections.abc import Iterable, Sequence
from html import escape
from typing import Any

from backend.app.exports.domain import ExportArticle, ExportDataset, ExportFormat, RenderedExport

EXPORT_SCHEMA_VERSION = "review-export-6"
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def render_export(export_format: ExportFormat, dataset: ExportDataset) -> RenderedExport:
    renderers = {
        ExportFormat.CSV: _render_csv,
        ExportFormat.XLSX: _render_xlsx,
        ExportFormat.JSON: _render_json,
        ExportFormat.RIS: _render_ris,
    }
    return renderers[export_format](dataset)


def _article_rows(dataset: ExportDataset) -> list[list[str | int | None]]:
    return [
        [
            str(article.id),
            article.title,
            article.abstract,
            article.publication_year,
            article.doi,
            article.pmid,
            "; ".join(article.authors),
            article.journal,
            ";".join(str(item) for item in article.source_record_ids),
            ";".join(article.study_keys),
        ]
        for article in dataset.articles
    ]


ARTICLE_HEADERS = [
    "article_id",
    "title",
    "abstract",
    "publication_year",
    "doi",
    "pmid",
    "authors",
    "journal",
    "source_record_ids",
    "study_keys",
]


def _safe_csv_value(value: str | int | None) -> str | int | None:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _render_csv(dataset: ExportDataset) -> RenderedExport:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ARTICLE_HEADERS)
    writer.writerows([_safe_csv_value(value) for value in row] for row in _article_rows(dataset))
    content = stream.getvalue().encode("utf-8-sig")
    return RenderedExport(
        content,
        "text/csv; charset=utf-8",
        "csv",
        {"articles": len(dataset.articles)},
    )


def _json_article(article: ExportArticle) -> dict[str, Any]:
    return {
        "id": str(article.id),
        "title": article.title,
        "abstract": article.abstract,
        "publication_year": article.publication_year,
        "doi": article.doi,
        "pmid": article.pmid,
        "authors": list(article.authors),
        "journal": article.journal,
        "source_record_ids": [str(item) for item in article.source_record_ids],
        "study_keys": list(article.study_keys),
    }


def _render_json(dataset: ExportDataset) -> RenderedExport:
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "organization_id": str(dataset.organization_id),
        "review": {"id": str(dataset.review_id), "title": dataset.review_title},
        "prisma": {
            "snapshot_id": str(dataset.prisma_snapshot_id),
            "algorithm_version": dataset.prisma_algorithm_version,
            "counts": dataset.prisma_counts,
            "readiness": dataset.prisma_readiness,
            "source_references": dataset.prisma_source_references,
        },
        "articles": [_json_article(article) for article in dataset.articles],
        "studies": [
            {
                "id": str(study.id),
                "study_key": study.study_key,
                "label": study.label,
                "article_ids": [str(item) for item in study.article_ids],
            }
            for study in dataset.studies
        ],
        "search_executions": [
            {
                "id": str(execution.id),
                "source_name": execution.source_name,
                "provider_name": execution.provider_name,
                "platform_name": execution.platform_name,
                "source_classification": execution.source_classification,
                "method": execution.method,
                "executed_at": execution.executed_at.isoformat(),
                "search_strategy_version_id": (
                    str(execution.search_strategy_version_id)
                    if execution.search_strategy_version_id
                    else None
                ),
                "search_translation_id": (
                    str(execution.search_translation_id)
                    if execution.search_translation_id
                    else None
                ),
                "exact_query": execution.exact_query,
                "filters": dict(execution.filters),
                "software_version": execution.software_version,
                "status": execution.status,
                "provider_result_count": execution.provider_result_count,
                "imported_record_count": execution.imported_record_count,
                "status_history": [
                    {
                        "sequence": sequence,
                        "status": status,
                        "occurred_at": occurred_at.isoformat(),
                        "provider_result_count": result_count,
                        "note": note,
                    }
                    for sequence, status, occurred_at, result_count, note in (
                        execution.status_history
                    )
                ],
            }
            for execution in dataset.search_executions
        ],
        "risk_of_bias": {
            "assessments": [
                {
                    "id": str(assessment.id),
                    "study_id": str(assessment.study_id),
                    "instrument_version_id": str(assessment.instrument_version_id),
                    "instrument_version": assessment.instrument_version,
                    "instrument_content_hash": assessment.instrument_content_hash,
                    "assessor_user_id": str(assessment.assessor_user_id),
                    "round_number": assessment.round_number,
                    "revision": assessment.revision,
                    "supersedes_assessment_id": (
                        str(assessment.supersedes_assessment_id)
                        if assessment.supersedes_assessment_id
                        else None
                    ),
                    "status": assessment.status,
                    "overall_suggested_judgment": assessment.overall_suggested_judgment,
                    "overall_final_judgment": assessment.overall_final_judgment,
                    "overall_rationale": assessment.overall_rationale,
                    "answers": [
                        {
                            "question_key": key,
                            "answer": answer,
                            "rationale": rationale,
                            "evidence_location_id": str(evidence_id) if evidence_id else None,
                        }
                        for key, answer, rationale, evidence_id in assessment.answers
                    ],
                    "domains": [
                        {
                            "domain_key": key,
                            "suggested_judgment": suggested,
                            "final_judgment": final,
                            "rationale": rationale,
                            "override_reason": override,
                            "evidence_location_id": str(evidence_id) if evidence_id else None,
                        }
                        for key, suggested, final, rationale, override, evidence_id in (
                            assessment.domain_judgments
                        )
                    ],
                }
                for assessment in dataset.risk_of_bias_assessments
            ],
            "comparisons": [
                {
                    "id": str(comparison.id),
                    "study_id": str(comparison.study_id),
                    "instrument_version_id": str(comparison.instrument_version_id),
                    "round_number": comparison.round_number,
                    "assessment_a_id": str(comparison.assessment_a_id),
                    "assessment_b_id": str(comparison.assessment_b_id),
                    "status": comparison.status,
                    "differences": list(comparison.differences),
                    "adjudicated_snapshot": comparison.adjudicated_snapshot,
                    "adjudicated_by_user_id": (
                        str(comparison.adjudicated_by_user_id)
                        if comparison.adjudicated_by_user_id
                        else None
                    ),
                    "adjudication_reason": comparison.adjudication_reason,
                }
                for comparison in dataset.risk_of_bias_comparisons
            ],
        },
        "outcomes": {
            "definitions": list(dataset.outcome_versions),
            "mappings": list(dataset.outcome_mappings),
            "effect_estimates": list(dataset.effect_estimates),
            "synthesis_candidate_sets": list(dataset.synthesis_candidate_sets),
            "analysis_readiness": list(dataset.analysis_readiness),
        },
        "analysis": {
            "specification_versions": list(dataset.analysis_specification_versions),
            "analysis_sets": list(dataset.analysis_sets),
            "meta_analysis_runs": list(dataset.meta_analysis_runs),
            "study_weights": list(dataset.analysis_study_weights),
            "leave_one_out_sensitivity": list(dataset.analysis_sensitivities),
            "artifacts": list(dataset.analysis_artifacts),
        },
        "certainty": {
            "framework_versions": list(dataset.certainty_framework_versions),
            "decision_threshold_versions": list(dataset.certainty_threshold_versions),
            "assessments": list(dataset.certainty_assessments),
            "comparisons": list(dataset.certainty_comparisons),
            "summary_of_findings": list(dataset.summary_of_findings),
        },
    }
    content = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    return RenderedExport(
        content,
        "application/json",
        "json",
        {
            "articles": len(dataset.articles),
            "studies": len(dataset.studies),
            "search_executions": len(dataset.search_executions),
            "risk_of_bias_assessments": len(dataset.risk_of_bias_assessments),
            "risk_of_bias_comparisons": len(dataset.risk_of_bias_comparisons),
            "outcome_versions": len(dataset.outcome_versions),
            "outcome_mappings": len(dataset.outcome_mappings),
            "effect_estimates": len(dataset.effect_estimates),
            "synthesis_candidate_sets": len(dataset.synthesis_candidate_sets),
            "analysis_readiness": len(dataset.analysis_readiness),
            "analysis_specification_versions": len(dataset.analysis_specification_versions),
            "analysis_sets": len(dataset.analysis_sets),
            "meta_analysis_runs": len(dataset.meta_analysis_runs),
            "analysis_study_weights": len(dataset.analysis_study_weights),
            "analysis_sensitivities": len(dataset.analysis_sensitivities),
            "analysis_artifacts": len(dataset.analysis_artifacts),
            "certainty_framework_versions": len(dataset.certainty_framework_versions),
            "certainty_threshold_versions": len(dataset.certainty_threshold_versions),
            "certainty_assessments": len(dataset.certainty_assessments),
            "certainty_comparisons": len(dataset.certainty_comparisons),
            "summary_of_findings": len(dataset.summary_of_findings),
        },
    )


def _ris_value(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


def _render_ris(dataset: ExportDataset) -> RenderedExport:
    lines: list[str] = []
    for article in dataset.articles:
        lines.extend(("TY  - JOUR", f"ID  - {article.id}", f"TI  - {_ris_value(article.title)}"))
        lines.extend(f"AU  - {_ris_value(author)}" for author in article.authors)
        if article.publication_year is not None:
            lines.append(f"PY  - {article.publication_year}")
        if article.journal:
            lines.append(f"JO  - {_ris_value(article.journal)}")
        if article.doi:
            lines.append(f"DO  - {_ris_value(article.doi)}")
        if article.pmid:
            lines.append(f"AN  - PMID:{_ris_value(article.pmid)}")
        if article.abstract:
            lines.append(f"AB  - {_ris_value(article.abstract)}")
        lines.extend(("ER  -", ""))
    return RenderedExport(
        "\r\n".join(lines).encode(),
        "application/x-research-info-systems; charset=utf-8",
        "ris",
        {"articles": len(dataset.articles)},
    )


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell_xml(reference: str, value: object) -> str:
    if value is None:
        return f'<c r="{reference}"/>'
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, int | float):
        return f'<c r="{reference}"><v>{value}</v></c>'
    clean = _CONTROL_CHARACTERS.sub("", str(value))
    return (
        f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">{escape(clean)}</t></is></c>'
    )


def _sheet_xml(rows: Iterable[Sequence[object]]) -> str:
    row_xml: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells = "".join(
            _cell_xml(f"{_column_name(column)}{row_number}", value)
            for column, value in enumerate(row, start=1)
        )
        row_xml.append(f'<row r="{row_number}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(row_xml)}</sheetData></worksheet>"
    )


def _zip_entry(archive: zipfile.ZipFile, name: str, content: str) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, content.encode())


def _render_xlsx(dataset: ExportDataset) -> RenderedExport:
    blockers = dataset.prisma_readiness.get("blockers", [])
    manifest_rows: list[list[object]] = [
        ["field", "value"],
        ["schema_version", EXPORT_SCHEMA_VERSION],
        ["organization_id", str(dataset.organization_id)],
        ["review_id", str(dataset.review_id)],
        ["review_title", dataset.review_title],
        ["prisma_snapshot_id", str(dataset.prisma_snapshot_id)],
        ["prisma_algorithm_version", dataset.prisma_algorithm_version],
        ["prisma_ready_for_final", bool(dataset.prisma_readiness.get("ready_for_final"))],
        ["prisma_blocker_count", len(blockers) if isinstance(blockers, list) else 0],
        ["article_count", len(dataset.articles)],
        ["study_count", len(dataset.studies)],
        ["search_execution_count", len(dataset.search_executions)],
        ["risk_of_bias_assessment_count", len(dataset.risk_of_bias_assessments)],
        ["risk_of_bias_comparison_count", len(dataset.risk_of_bias_comparisons)],
        ["outcome_version_count", len(dataset.outcome_versions)],
        ["outcome_mapping_count", len(dataset.outcome_mappings)],
        ["effect_estimate_count", len(dataset.effect_estimates)],
        ["synthesis_candidate_set_count", len(dataset.synthesis_candidate_sets)],
        ["analysis_readiness_count", len(dataset.analysis_readiness)],
        ["analysis_specification_version_count", len(dataset.analysis_specification_versions)],
        ["analysis_set_count", len(dataset.analysis_sets)],
        ["meta_analysis_run_count", len(dataset.meta_analysis_runs)],
        ["analysis_artifact_count", len(dataset.analysis_artifacts)],
        ["certainty_assessment_count", len(dataset.certainty_assessments)],
        ["certainty_comparison_count", len(dataset.certainty_comparisons)],
        ["summary_of_findings_count", len(dataset.summary_of_findings)],
    ]
    prisma_rows: list[list[object]] = [["counter", "value"]]
    exclusion_rows: list[list[object]] = [["reason", "count"]]
    for key, value in sorted(dataset.prisma_counts.items()):
        if key == "full_text_exclusion_reasons" and isinstance(value, dict):
            exclusion_rows.extend([[reason, count] for reason, count in sorted(value.items())])
        else:
            prisma_rows.append([key, value])
    article_rows: list[list[object]] = [list(ARTICLE_HEADERS)]
    article_rows.extend([list(row) for row in _article_rows(dataset)])
    study_rows: list[list[object]] = [["study_id", "study_key", "label", "article_ids"]]
    study_rows.extend(
        [
            str(study.id),
            study.study_key,
            study.label,
            ";".join(str(item) for item in study.article_ids),
        ]
        for study in dataset.studies
    )
    search_execution_rows: list[list[object]] = [
        [
            "search_execution_id",
            "source_name",
            "provider_name",
            "platform_name",
            "source_classification",
            "method",
            "executed_at",
            "search_strategy_version_id",
            "search_translation_id",
            "exact_query",
            "filters",
            "software_version",
            "status",
            "provider_result_count",
            "imported_record_count",
            "status_history",
        ]
    ]
    search_execution_rows.extend(
        [
            str(execution.id),
            execution.source_name,
            execution.provider_name,
            execution.platform_name,
            execution.source_classification,
            execution.method,
            execution.executed_at.isoformat(),
            (
                str(execution.search_strategy_version_id)
                if execution.search_strategy_version_id
                else None
            ),
            (str(execution.search_translation_id) if execution.search_translation_id else None),
            execution.exact_query,
            json.dumps(dict(execution.filters), sort_keys=True, separators=(",", ":")),
            execution.software_version,
            execution.status,
            execution.provider_result_count,
            execution.imported_record_count,
            json.dumps(
                [
                    {
                        "sequence": sequence,
                        "status": status,
                        "occurred_at": occurred_at.isoformat(),
                        "provider_result_count": result_count,
                        "note": note,
                    }
                    for sequence, status, occurred_at, result_count, note in (
                        execution.status_history
                    )
                ],
                sort_keys=True,
                separators=(",", ":"),
            ),
        ]
        for execution in dataset.search_executions
    )
    risk_assessment_rows: list[list[object]] = [
        [
            "assessment_id",
            "study_id",
            "instrument_version_id",
            "instrument_version",
            "instrument_content_hash",
            "assessor_user_id",
            "round_number",
            "revision",
            "supersedes_assessment_id",
            "status",
            "overall_suggested_judgment",
            "overall_final_judgment",
            "overall_rationale",
            "answers",
        ]
    ]
    risk_assessment_rows.extend(
        [
            str(item.id),
            str(item.study_id),
            str(item.instrument_version_id),
            item.instrument_version,
            item.instrument_content_hash,
            str(item.assessor_user_id),
            item.round_number,
            item.revision,
            str(item.supersedes_assessment_id) if item.supersedes_assessment_id else None,
            item.status,
            item.overall_suggested_judgment,
            item.overall_final_judgment,
            item.overall_rationale,
            json.dumps(
                [
                    {
                        "question_key": key,
                        "answer": answer,
                        "rationale": rationale,
                        "evidence_location_id": str(evidence_id) if evidence_id else None,
                    }
                    for key, answer, rationale, evidence_id in item.answers
                ],
                sort_keys=True,
                separators=(",", ":"),
            ),
        ]
        for item in dataset.risk_of_bias_assessments
    )
    risk_domain_rows: list[list[object]] = [
        [
            "assessment_id",
            "study_id",
            "domain_key",
            "suggested_judgment",
            "final_judgment",
            "rationale",
            "override_reason",
            "evidence_location_id",
        ]
    ]
    risk_domain_rows.extend(
        [
            str(assessment.id),
            str(assessment.study_id),
            key,
            suggested,
            final,
            rationale,
            override,
            str(evidence_id) if evidence_id else None,
        ]
        for assessment in dataset.risk_of_bias_assessments
        for key, suggested, final, rationale, override, evidence_id in (assessment.domain_judgments)
    )
    risk_conflict_rows: list[list[object]] = [
        [
            "comparison_id",
            "study_id",
            "instrument_version_id",
            "round_number",
            "assessment_a_id",
            "assessment_b_id",
            "status",
            "differences",
            "adjudicated_snapshot",
            "adjudicated_by_user_id",
            "adjudication_reason",
        ]
    ]
    risk_conflict_rows.extend(
        [
            str(item.id),
            str(item.study_id),
            str(item.instrument_version_id),
            item.round_number,
            str(item.assessment_a_id),
            str(item.assessment_b_id),
            item.status,
            json.dumps(list(item.differences), sort_keys=True, separators=(",", ":")),
            (
                json.dumps(item.adjudicated_snapshot, sort_keys=True, separators=(",", ":"))
                if item.adjudicated_snapshot
                else None
            ),
            str(item.adjudicated_by_user_id) if item.adjudicated_by_user_id else None,
            item.adjudication_reason,
        ]
        for item in dataset.risk_of_bias_comparisons
    )
    outcome_rows = _structured_rows(
        dataset.outcome_versions,
        [
            "id",
            "outcome_id",
            "outcome_key",
            "version",
            "definition",
            "content_hash",
            "protocol_version_id",
        ],
    )
    mapping_rows = _structured_rows(
        dataset.outcome_mappings,
        [
            "id",
            "study_id",
            "extraction_value_id",
            "outcome_version_id",
            "method",
            "rationale",
            "confidence",
            "reported_value",
            "reported_unit",
            "reported_unit_id",
            "normalized_value",
            "normalized_unit_id",
            "conversion_rule_version",
            "reported_time_value",
            "reported_time_unit",
            "reported_time_anchor",
            "normalized_time_days",
            "timepoint_window_id",
            "timepoint_rule_version",
            "measurement_scale_id",
            "direction_transformation",
            "transformation_reason",
            "extraction_verified",
            "supersedes_mapping_id",
        ],
    )
    estimate_rows = _structured_rows(
        dataset.effect_estimates,
        [
            "id",
            "study_id",
            "outcome_version_id",
            "effect_measure",
            "origin",
            "estimate",
            "standard_error",
            "variance",
            "variance_scale",
            "ci_lower",
            "ci_upper",
            "confidence_level",
            "adjustment",
            "analysis_population",
            "covariates",
            "model_description",
            "timepoint_window_id",
            "unit_id",
            "measurement_scale_id",
            "components",
            "source_mapping_ids",
            "source_evidence_location_id",
            "calculation_version",
            "zero_event_pattern",
        ],
    )
    candidate_rows = _structured_rows(
        dataset.synthesis_candidate_sets,
        [
            "id",
            "outcome_version_id",
            "effect_measure",
            "timepoint_window_id",
            "population_label",
            "estimate_ids",
        ],
    )
    readiness_rows = _structured_rows(
        dataset.analysis_readiness,
        ["id", "candidate_set_id", "algorithm_version", "status", "blockers"],
    )
    specification_rows = _structured_rows(
        dataset.analysis_specification_versions,
        ["id", "specification_id", "version", "definition", "content_hash"],
    )
    analysis_set_rows = _structured_rows(
        dataset.analysis_sets,
        [
            "id",
            "specification_version_id",
            "candidate_set_id",
            "included_estimate_ids",
            "excluded_estimates",
            "input_hash",
        ],
    )
    meta_result_rows = _structured_rows(
        dataset.meta_analysis_runs,
        [
            "id",
            "specification_version_id",
            "analysis_set_id",
            "status",
            "algorithm_name",
            "algorithm_version",
            "provider",
            "provider_version",
            "input_hash",
            "result_hash",
            "result",
            "diagnostics",
            "failure_reason",
        ],
    )
    weight_rows = _structured_rows(
        dataset.analysis_study_weights,
        [
            "run_id",
            "study_id",
            "estimate_id",
            "analysis_estimate",
            "presentation_estimate",
            "ci_lower",
            "ci_upper",
            "raw_weight",
            "normalized_weight_percent",
        ],
    )
    sensitivity_rows = _structured_rows(
        dataset.analysis_sensitivities,
        ["run_id", "omitted_study_id", "omitted_estimate_id", "result", "result_hash"],
    )
    analysis_artifact_rows = _structured_rows(
        dataset.analysis_artifacts,
        [
            "id",
            "run_id",
            "artifact_type",
            "renderer_version",
            "media_type",
            "filename",
            "sha256",
            "byte_size",
        ],
    )
    certainty_assessment_rows = _structured_rows(
        dataset.certainty_assessments,
        [
            "id",
            "outcome_version_id",
            "timepoint_window_id",
            "analysis_specification_version_id",
            "meta_analysis_run_id",
            "framework_version_id",
            "threshold_version_id",
            "assessor_user_id",
            "round_number",
            "revision",
            "supersedes_assessment_id",
            "evidence_body_type",
            "starting_certainty",
            "candidate_certainty",
            "final_certainty",
            "status",
            "evidence_hash",
        ],
    )
    certainty_domain_rows = _structured_rows(
        tuple(
            {"assessment_id": item["id"], **domain}
            for item in dataset.certainty_assessments
            for domain in item["domains"]
        ),
        [
            "assessment_id",
            "domain_key",
            "direction",
            "judgment",
            "magnitude",
            "rationale",
            "evidence",
            "evidence_location_id",
        ],
    )
    certainty_conflict_rows = _structured_rows(
        dataset.certainty_comparisons,
        [
            "id",
            "outcome_version_id",
            "framework_version_id",
            "round_number",
            "assessment_a_id",
            "assessment_b_id",
            "status",
            "differences",
            "adjudicated_snapshot",
            "adjudicated_by_user_id",
            "adjudication_reason",
        ],
    )
    evidence_profile_rows = _structured_rows(
        tuple(
            {
                "assessment_id": item["id"],
                "evidence_hash": item["evidence_hash"],
                "evidence_snapshot": item["evidence_snapshot"],
            }
            for item in dataset.certainty_assessments
            if item["status"] == "SUBMITTED"
        ),
        ["assessment_id", "evidence_hash", "evidence_snapshot"],
    )
    sof_rows = _structured_rows(
        dataset.summary_of_findings,
        ["id", "assessment_id", "model_version", "row", "content_hash"],
    )
    sheets = [
        ("Manifest", manifest_rows),
        ("PRISMA", prisma_rows),
        ("Exclusion Reasons", exclusion_rows),
        ("Articles", article_rows),
        ("Studies", study_rows),
        ("Search Executions", search_execution_rows),
        ("Risk of Bias Assessments", risk_assessment_rows),
        ("RoB Domains", risk_domain_rows),
        ("RoB Conflicts", risk_conflict_rows),
        ("Outcomes", outcome_rows),
        ("Outcome Mappings", mapping_rows),
        ("Effect Estimates", estimate_rows),
        ("Synthesis Candidates", candidate_rows),
        ("Analysis Readiness", readiness_rows),
        ("Analysis Specifications", specification_rows),
        ("Analysis Sets", analysis_set_rows),
        ("Meta-Analysis Results", meta_result_rows),
        ("Study Weights", weight_rows),
        ("Sensitivity Analyses", sensitivity_rows),
        ("Analysis Artifacts", analysis_artifact_rows),
        ("Certainty Assessments", certainty_assessment_rows),
        ("Certainty Domains", certainty_domain_rows),
        ("Certainty Conflicts", certainty_conflict_rows),
        ("Evidence Profiles", evidence_profile_rows),
        ("Summary of Findings", sof_rows),
    ]
    content_types = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    workbook_sheets = "".join(
        f'<sheet name="{escape(name, quote=True)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(sheets, start=1)
    )
    workbook_relationships = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        _zip_entry(
            archive,
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            f"{content_types}</Types>",
        )
        _zip_entry(
            archive,
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        )
        _zip_entry(
            archive,
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{workbook_sheets}</sheets></workbook>",
        )
        _zip_entry(
            archive,
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{workbook_relationships}</Relationships>",
        )
        for index, (_, rows) in enumerate(sheets, start=1):
            _zip_entry(archive, f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
    return RenderedExport(
        stream.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
        {
            "articles": len(dataset.articles),
            "studies": len(dataset.studies),
            "search_executions": len(dataset.search_executions),
            "risk_of_bias_assessments": len(dataset.risk_of_bias_assessments),
            "risk_of_bias_domains": sum(
                len(item.domain_judgments) for item in dataset.risk_of_bias_assessments
            ),
            "risk_of_bias_comparisons": len(dataset.risk_of_bias_comparisons),
            "outcome_versions": len(dataset.outcome_versions),
            "outcome_mappings": len(dataset.outcome_mappings),
            "effect_estimates": len(dataset.effect_estimates),
            "synthesis_candidate_sets": len(dataset.synthesis_candidate_sets),
            "analysis_readiness": len(dataset.analysis_readiness),
            "analysis_specification_versions": len(dataset.analysis_specification_versions),
            "analysis_sets": len(dataset.analysis_sets),
            "meta_analysis_runs": len(dataset.meta_analysis_runs),
            "analysis_study_weights": len(dataset.analysis_study_weights),
            "analysis_sensitivities": len(dataset.analysis_sensitivities),
            "analysis_artifacts": len(dataset.analysis_artifacts),
        },
    )


def _structured_rows(items: Sequence[dict[str, Any]], headers: list[str]) -> list[list[object]]:
    rows: list[list[object]] = [list(headers)]
    for item in items:
        rows.append(
            [
                (
                    json.dumps(value, sort_keys=True, separators=(",", ":"))
                    if isinstance(value, dict | list)
                    else value
                )
                for value in (item.get(header) for header in headers)
            ]
        )
    return rows
