import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.db.session import engine

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, database_engine: AsyncEngine) -> None:
        self._database_engine = database_engine

    async def database_is_ready(self) -> bool:
        try:
            async with self._database_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("database_readiness_failed", exc_info=True)
            return False
        return True


def get_health_service() -> HealthService:
    return HealthService(engine)
