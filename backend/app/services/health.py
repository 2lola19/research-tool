import logging
from typing import cast

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.core.config import Settings
from backend.app.db.session import engine
from backend.app.malware.contracts import MalwareScanner
from backend.app.malware.factory import build_malware_scanner

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(
        self,
        database_engine: AsyncEngine,
        *,
        require_migrations: bool = False,
        expected_revision: str = "20260820_0037",
        malware_scanner: MalwareScanner | None = None,
    ) -> None:
        self._database_engine = database_engine
        self._require_migrations = require_migrations
        self._expected_revision = expected_revision
        self._malware_scanner = malware_scanner

    async def database_is_ready(self) -> bool:
        try:
            async with self._database_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                if self._require_migrations:
                    current_revision = await connection.scalar(
                        text("SELECT version_num FROM alembic_version")
                    )
                    if current_revision != self._expected_revision:
                        logger.warning(
                            "database_migration_readiness_failed",
                            extra={
                                "expected_revision": self._expected_revision,
                                "current_revision": current_revision or "missing",
                            },
                        )
                        return False
        except SQLAlchemyError:
            logger.warning("database_readiness_failed", exc_info=True)
            return False
        return True

    async def malware_scanner_is_ready(self) -> bool:
        if self._malware_scanner is None:
            return True
        return (await self._malware_scanner.health()).healthy


def get_health_service(request: Request) -> HealthService:
    settings = cast(Settings, request.app.state.settings)
    return HealthService(
        engine,
        require_migrations=settings.database_require_migrations,
        expected_revision=settings.database_expected_revision,
        malware_scanner=build_malware_scanner(settings),
    )
