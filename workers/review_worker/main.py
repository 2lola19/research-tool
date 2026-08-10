import asyncio
import logging
from contextlib import suppress

from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.db.session import dispose_database

logger = logging.getLogger(__name__)


async def worker_main() -> None:
    settings = get_settings()
    configure_logging(settings.app_log_level)
    logger.info("worker_started", extra={"orchestration_adapter": "foundation"})
    try:
        shutdown_event = asyncio.Event()
        await shutdown_event.wait()
    finally:
        await dispose_database()
        logger.info("worker_stopped")


def run() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(worker_main())
