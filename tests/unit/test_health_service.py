import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.services.health import HealthService


@pytest.mark.asyncio
async def test_database_health_executes_query() -> None:
    database_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        assert await HealthService(database_engine).database_is_ready() is True
    finally:
        await database_engine.dispose()
