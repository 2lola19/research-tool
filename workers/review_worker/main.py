import asyncio
import logging
from contextlib import suppress

from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.db.session import dispose_database, session_factory
from backend.app.workflow.execution_domain import default_job_handler_registry
from backend.app.workflow.execution_persistence import SqlAlchemyWorkflowExecutionRepository
from backend.app.workflow.execution_service import LocalWorkerRunner, WorkflowExecutionService

logger = logging.getLogger(__name__)


async def run_worker_once() -> int:
    settings = get_settings()
    async with session_factory() as session:
        execution = WorkflowExecutionService(
            SqlAlchemyWorkflowExecutionRepository(session),
            default_job_handler_registry(),
        )
        processed = await LocalWorkerRunner(
            execution,
            worker_id=settings.worker_id,
            max_concurrency=settings.worker_max_concurrency,
            lease_seconds=settings.worker_lease_seconds,
        ).run_once()
        await session.commit()
        return processed


async def recover_expired_once() -> int:
    async with session_factory() as session:
        execution = WorkflowExecutionService(SqlAlchemyWorkflowExecutionRepository(session))
        recovered = await execution.requeue_expired()
        await session.commit()
        return recovered


async def worker_main(*, run_once: bool = False, recover_expired: bool = False) -> None:
    settings = get_settings()
    configure_logging(settings.app_log_level)
    logger.info("worker_started", extra={"orchestration_adapter": "foundation"})
    try:
        if recover_expired:
            recovered = await recover_expired_once()
            logger.info("worker_recovery_completed", extra={"recovered_attempts": recovered})
        if run_once:
            processed = await run_worker_once()
            logger.info("worker_cycle_completed", extra={"processed_jobs": processed})
            return
        if recover_expired:
            return
        shutdown_event = asyncio.Event()
        await shutdown_event.wait()
    finally:
        await dispose_database()
        logger.info("worker_stopped")


def run(*, run_once: bool = False, recover_expired: bool = False) -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(worker_main(run_once=run_once, recover_expired=recover_expired))
