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
        processing_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(document_processing_runs)").fetchall()
        }

    assert version == ("20260819_0036",)
    assert {
        "users",
        "organizations",
        "memberships",
        "local_credentials",
        "reviews",
        "review_memberships",
        "workflow_runs",
        "workflow_jobs",
        "workflow_job_attempts",
        "workflow_workers",
        "workflow_step_checkpoints",
        "workflow_recovery_operations",
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
        "search_provider_attempts",
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
        "ai_model_versions",
        "ai_prompt_template_versions",
        "ai_execution_runs",
        "ai_run_attempts",
        "ai_validation_results",
        "ai_output_proposals",
        "ai_review_decisions",
        "ai_screening_policy_versions",
        "ai_screening_proposal_links",
        "ai_screening_access_events",
        "ai_screening_decision_links",
        "ai_screening_evaluation_datasets",
        "ai_screening_evaluation_cases",
        "ai_screening_evaluation_results",
        "ai_screening_evaluation_case_results",
        "ai_screening_error_classifications",
        "ai_full_text_proposal_links",
        "ai_full_text_access_events",
        "ai_full_text_decision_links",
        "ai_full_text_evaluation_datasets",
        "ai_full_text_evaluation_cases",
        "ai_full_text_evaluation_results",
        "ai_full_text_evaluation_case_results",
        "ai_full_text_error_classifications",
        "ai_extraction_policy_versions",
        "ai_extraction_proposal_links",
        "ai_extraction_sources",
        "ai_extraction_evidence",
        "ai_extraction_access_events",
        "ai_extraction_field_reviews",
        "ai_extraction_evaluation_datasets",
        "ai_extraction_evaluation_cases",
        "ai_extraction_evaluation_results",
        "ai_extraction_evaluation_case_results",
        "ai_extraction_error_classifications",
        "ai_rob_policy_versions",
        "ai_rob_proposal_links",
        "ai_rob_sources",
        "ai_rob_evidence",
        "ai_rob_access_events",
        "ai_rob_answer_reviews",
        "ai_rob_evaluation_datasets",
        "ai_rob_evaluation_cases",
        "ai_rob_evaluation_results",
        "ai_rob_evaluation_case_results",
        "ai_rob_error_classifications",
        "ai_outcome_policy_versions",
        "ai_outcome_proposal_links",
        "ai_outcome_access_events",
        "ai_outcome_human_reviews",
        "ai_outcome_evaluation_datasets",
        "ai_outcome_evaluation_results",
        "ai_outcome_error_classifications",
        "ai_certainty_policy_versions",
        "ai_certainty_proposal_links",
        "ai_certainty_access_events",
        "ai_certainty_human_reviews",
        "ai_certainty_evaluation_datasets",
        "ai_certainty_evaluation_results",
        "ai_certainty_error_classifications",
        "ai_copilot_policy_versions",
        "ai_copilot_queries",
        "report_snapshots",
        "report_artifacts",
    } <= tables

    assert {
        "failure_class",
        "content_sha256",
        "content_size",
        "chunk_manifest_hash",
        "chunk_manifest",
        "block_count",
        "text_byte_size",
    } <= processing_columns

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
    assert "search_provider_attempts" not in remaining_tables
    assert "rob_assessments" not in remaining_tables
    assert "outcome_definitions" not in remaining_tables
    assert "effect_estimates" not in remaining_tables
    assert "analysis_specifications" not in remaining_tables
    assert "meta_analysis_runs" not in remaining_tables
    assert "certainty_assessments" not in remaining_tables
    assert "summary_of_findings_snapshots" not in remaining_tables
    assert "report_specifications" not in remaining_tables
    assert "ai_execution_runs" not in remaining_tables
    assert "ai_screening_policy_versions" not in remaining_tables
    assert "ai_screening_proposal_links" not in remaining_tables
    assert "ai_screening_evaluation_datasets" not in remaining_tables
    assert "ai_screening_evaluation_results" not in remaining_tables
    assert "ai_full_text_proposal_links" not in remaining_tables
    assert "ai_full_text_evaluation_results" not in remaining_tables
    assert "ai_rob_policy_versions" not in remaining_tables
    assert "ai_rob_proposal_links" not in remaining_tables
    assert "ai_rob_evaluation_results" not in remaining_tables
    assert "ai_outcome_policy_versions" not in remaining_tables
    assert "ai_outcome_proposal_links" not in remaining_tables
    assert "ai_outcome_evaluation_results" not in remaining_tables
    assert "ai_certainty_policy_versions" not in remaining_tables
    assert "ai_certainty_proposal_links" not in remaining_tables
    assert "ai_certainty_evaluation_results" not in remaining_tables
    assert "ai_copilot_policy_versions" not in remaining_tables
    assert "ai_copilot_queries" not in remaining_tables
    assert "workflow_job_attempts" not in remaining_tables
    assert "workflow_workers" not in remaining_tables
    assert "workflow_step_checkpoints" not in remaining_tables
    assert "workflow_recovery_operations" not in remaining_tables
    assert "report_snapshots" not in remaining_tables
    assert "report_artifacts" not in remaining_tables
