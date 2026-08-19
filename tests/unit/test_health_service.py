import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.services.health import HealthService


@pytest.mark.asyncio
async def test_database_health_executes_query() -> None:
    database_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        assert await HealthService(database_engine).database_is_ready() is True
    finally:
        await database_engine.dispose()


@pytest.mark.asyncio
async def test_database_health_can_require_current_migration() -> None:
    database_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with database_engine.begin() as connection:
            await connection.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
            await connection.execute(text("INSERT INTO alembic_version VALUES ('20260819_0035')"))

        assert await HealthService(
            database_engine,
            require_migrations=True,
            expected_revision="20260819_0035",
        ).database_is_ready()
        assert not await HealthService(
            database_engine,
            require_migrations=True,
            expected_revision="20260819_0034",
        ).database_is_ready()
    finally:
        await database_engine.dispose()
