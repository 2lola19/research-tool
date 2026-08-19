from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_TEST_DATABASE_URL"),
    reason="requires an explicitly supplied disposable PostgreSQL database",
)
def test_alembic_upgrade_applies_current_schema_to_postgresql() -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = environment["POSTGRES_TEST_DATABASE_URL"]

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
