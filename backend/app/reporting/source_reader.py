from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.reporting.domain import content_hash

SCIENTIFIC_TABLES: dict[str, str] = {
    "protocol_versions": "protocol",
    "protocol_decisions": "protocol",
    "search_strategy_versions": "search",
    "search_translations": "search",
    "identification_sources": "search",
    "search_executions": "search",
    "search_execution_events": "search",
    "search_execution_citation_links": "search",
    "citation_import_batches": "citations",
    "citation_source_records": "citations",
    "articles": "citations",
    "deduplication_runs": "screening",
    "duplicate_candidates": "screening",
    "deduplication_decisions": "screening",
    "screening_rounds": "screening",
    "screening_assignments": "screening",
    "screening_decisions": "screening",
    "screening_outcomes": "screening",
    "screening_adjudications": "screening",
    "screening_progressions": "screening",
    "full_text_screenings": "screening",
    "full_text_criterion_judgments": "screening",
    "documents": "documents",
    "document_processing_runs": "documents",
    "document_warnings": "documents",
    "studies": "studies",
    "study_article_links": "studies",
    "extraction_schemas": "extraction",
    "extraction_schema_versions": "extraction",
    "extraction_runs": "extraction",
    "extraction_values": "extraction",
    "extraction_conflicts": "extraction",
    "extraction_verifications": "extraction",
    "rob_instruments": "risk_of_bias",
    "rob_instrument_versions": "risk_of_bias",
    "rob_instrument_decisions": "risk_of_bias",
    "rob_assessments": "risk_of_bias",
    "rob_answers": "risk_of_bias",
    "rob_domain_judgments": "risk_of_bias",
    "rob_comparisons": "risk_of_bias",
    "rob_adjudications": "risk_of_bias",
    "outcome_definitions": "outcomes",
    "outcome_definition_versions": "outcomes",
    "outcome_timepoint_windows": "outcomes",
    "outcome_unit_definitions": "outcomes",
    "outcome_measurement_scales": "outcomes",
    "outcome_mappings": "outcomes",
    "effect_estimates": "outcomes",
    "effect_estimate_sources": "outcomes",
    "synthesis_candidate_sets": "outcomes",
    "synthesis_candidate_estimates": "outcomes",
    "analysis_readiness_snapshots": "outcomes",
    "analysis_specifications": "analysis",
    "analysis_specification_versions": "analysis",
    "analysis_sets": "analysis",
    "analysis_set_estimates": "analysis",
    "meta_analysis_runs": "analysis",
    "meta_analysis_study_weights": "analysis",
    "meta_analysis_sensitivity_results": "analysis",
    "analysis_artifacts": "analysis",
    "certainty_frameworks": "certainty",
    "certainty_framework_versions": "certainty",
    "certainty_threshold_versions": "certainty",
    "certainty_assessments": "certainty",
    "certainty_domain_judgments": "certainty",
    "certainty_comparisons": "certainty",
    "summary_of_findings_snapshots": "certainty",
}

_EXCLUDED_COLUMNS = {"content", "raw_payload", "storage_key", "password_hash"}


async def read_scientific_tables(
    session: AsyncSession, organization_id: UUID, review_id: UUID
) -> dict[str, list[dict[str, Any]]]:
    connection = await session.connection()
    names = set(await connection.run_sync(_table_names))
    result: dict[str, list[dict[str, Any]]] = {}
    for table in sorted(set(SCIENTIFIC_TABLES) & names):
        columns = await connection.run_sync(_column_names, table)
        if "organization_id" not in columns or "review_id" not in columns:
            continue
        safe = [name for name in columns if name not in _EXCLUDED_COLUMNS]
        selected = ",".join(f'"{name}"' for name in safe)
        rows = (
            (
                await session.execute(
                    text(
                        f'SELECT {selected} FROM "{table}" WHERE organization_id = '
                        ":organization_id AND review_id = :review_id ORDER BY id"
                    ),
                    {"organization_id": organization_id.hex, "review_id": review_id.hex},
                )
            )
            .mappings()
            .all()
        )
        result[table] = [_safe_row(row) for row in rows]
    return result


def table_hashes(tables: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    return {table: content_hash(rows) for table, rows in tables.items()}


def _table_names(connection: Any) -> list[str]:
    return list(inspect(connection).get_table_names())


def _column_names(connection: Any, table: str) -> list[str]:
    return [str(item["name"]) for item in inspect(connection).get_columns(table)]


def _safe_row(row: Any) -> dict[str, Any]:
    return {
        key: value.hex()
        if isinstance(value, bytes)
        else str(value)
        if isinstance(value, (UUID, datetime))
        else value
        for key, value in sorted(row.items())
    }
