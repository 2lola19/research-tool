from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from workers.review_worker import main as worker


class ImmediateEvent:
    async def wait(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_worker_lifecycle_disposes_database(monkeypatch: pytest.MonkeyPatch) -> None:
    dispose_database = AsyncMock()
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(app_log_level="INFO"))
    monkeypatch.setattr(worker, "configure_logging", lambda _: None)
    monkeypatch.setattr(worker.asyncio, "Event", ImmediateEvent)
    monkeypatch.setattr(worker, "dispose_database", dispose_database)

    await worker.worker_main()

    dispose_database.assert_awaited_once_with()


def test_worker_run_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupt(coroutine: Coroutine[Any, Any, None]) -> None:
        coroutine.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(asyncio, "run", interrupt)

    worker.run()


def test_worker_emits_lifecycle_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def exercise_worker() -> None:
        monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(app_log_level="INFO"))
        monkeypatch.setattr(worker, "configure_logging", lambda _: None)
        monkeypatch.setattr(worker.asyncio, "Event", ImmediateEvent)
        monkeypatch.setattr(worker, "dispose_database", AsyncMock())
        await worker.worker_main()

    with caplog.at_level(logging.INFO, logger=worker.__name__):
        asyncio.run(exercise_worker())

    assert [record.message for record in caplog.records] == ["worker_started", "worker_stopped"]
