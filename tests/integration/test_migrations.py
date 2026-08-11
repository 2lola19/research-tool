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
        timeout=60,
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

    assert version == ("20260811_0013",)
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
    } <= tables
