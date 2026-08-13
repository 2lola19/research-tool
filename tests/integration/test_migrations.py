from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path


def test_alembic_upgrade_applies_current_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr
    with closing(sqlite3.connect(database_path)) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert version == ("20260813_0023",)
    assert {
        "users",
        "organizations",
        "memberships",
        "local_credentials",
        "reviews",
        "review_memberships",
        "workflow_runs",
        "workflow_jobs",
        "job_events",
        "human_checkpoints",
        "prompt_versions",
        "ai_runs",
        "scientific_provenance",
        "audit_events",
        "protocol_versions",
        "protocol_decisions",
        "search_strategy_versions",
        "search_translations",
        "citation_import_batches",
        "citation_source_records",
        "articles",
        "deduplication_runs",
        "duplicate_candidates",
        "deduplication_decisions",
        "screening_rounds",
        "screening_assignments",
        "screening_decisions",
        "screening_outcomes",
        "screening_adjudications",
        "screening_progressions",
        "documents",
        "document_processing_runs",
        "document_blocks",
        "document_evidence_locations",
        "document_warnings",
        "full_text_screenings",
        "full_text_criterion_judgments",
        "studies",
        "study_article_links",
        "extraction_schemas",
        "extraction_schema_versions",
        "extraction_runs",
        "extraction_values",
        "extraction_conflicts",
        "extraction_verifications",
        "prisma_snapshots",
        "export_artifacts",
        "identification_sources",
        "search_executions",
        "search_execution_events",
        "search_execution_citation_links",
        "search_execution_artifacts",
        "rob_instruments",
        "rob_instrument_versions",
        "rob_instrument_decisions",
        "rob_assessments",
        "rob_answers",
        "rob_domain_judgments",
        "rob_comparisons",
        "rob_adjudications",
        "outcome_definitions",
        "outcome_definition_versions",
        "outcome_timepoint_windows",
        "outcome_unit_definitions",
        "outcome_measurement_scales",
        "outcome_mappings",
        "effect_estimates",
        "effect_estimate_sources",
        "synthesis_candidate_sets",
        "synthesis_candidate_estimates",
        "analysis_readiness_snapshots",
        "analysis_specifications",
        "analysis_specification_versions",
        "analysis_sets",
        "analysis_set_estimates",
        "meta_analysis_runs",
        "meta_analysis_study_weights",
        "meta_analysis_sensitivity_results",
        "analysis_artifacts",
        "certainty_frameworks",
        "certainty_framework_versions",
        "certainty_threshold_versions",
        "certainty_assessments",
        "certainty_domain_judgments",
        "certainty_comparisons",
        "summary_of_findings_snapshots",
        "report_specifications",
        "report_snapshots",
        "report_artifacts",
    } <= tables

    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert downgrade.returncode == 0, downgrade.stderr
    with closing(sqlite3.connect(database_path)) as connection:
        remaining_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        versions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    assert versions == []
    assert "prisma_snapshots" not in remaining_tables
    assert "export_artifacts" not in remaining_tables
    assert "search_executions" not in remaining_tables
    assert "rob_assessments" not in remaining_tables
    assert "outcome_definitions" not in remaining_tables
    assert "effect_estimates" not in remaining_tables
    assert "analysis_specifications" not in remaining_tables
    assert "meta_analysis_runs" not in remaining_tables
    assert "certainty_assessments" not in remaining_tables
    assert "summary_of_findings_snapshots" not in remaining_tables
    assert "report_specifications" not in remaining_tables
    assert "report_snapshots" not in remaining_tables
    assert "report_artifacts" not in remaining_tables
