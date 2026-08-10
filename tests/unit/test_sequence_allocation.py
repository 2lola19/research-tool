from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Integer, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.app.db.sequence import insert_next_unique_integer


class ProbeBase(DeclarativeBase):
    pass


class SequenceProbe(ProbeBase):
    __tablename__ = "sequence_probe"
    __table_args__ = (UniqueConstraint("scope", "value", name="uq_sequence_probe_scope_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(80))
    value: Mapped[int] = mapped_column(Integer)


async def _create_factory(database_path: Path) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
        connect_args={"timeout": 10},
    )
    async with engine.begin() as connection:
        await connection.run_sync(ProbeBase.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _allocate(session: AsyncSession, scope: str) -> int:
    async def read_next() -> int:
        query = select(SequenceProbe.value).where(SequenceProbe.scope == scope)
        values = (await session.scalars(query)).all()
        return (max(values) if values else 0) + 1

    record = await insert_next_unique_integer(
        session,
        read_next,
        lambda value: SequenceProbe(scope=scope, value=value),
    )
    await session.commit()
    return record.value


@pytest.mark.asyncio
async def test_sequence_allocation_is_ordinary_and_unique(tmp_path: Path) -> None:
    factory = await _create_factory(tmp_path / "ordinary.db")

    async with factory() as session:
        assert await _allocate(session, "review") == 1
        assert await _allocate(session, "review") == 2
        assert await _allocate(session, "other-review") == 1


@pytest.mark.asyncio
async def test_sequence_allocation_retries_after_simulated_concurrent_winner(
    tmp_path: Path,
) -> None:
    factory = await _create_factory(tmp_path / "retry.db")
    first_read = True

    async with factory() as session:
        session.add(SequenceProbe(scope="review", value=1))
        await session.commit()

        async def read_next() -> int:
            nonlocal first_read
            query = select(SequenceProbe.value).where(SequenceProbe.scope == "review")
            values = (await session.scalars(query)).all()
            if first_read:
                first_read = False
                return 1
            return (max(values) if values else 0) + 1

        record = await insert_next_unique_integer(
            session,
            read_next,
            lambda value: SequenceProbe(scope="review", value=value),
        )
        await session.commit()

        assert record.value == 2
        values = (
            await session.scalars(
                select(SequenceProbe.value).where(SequenceProbe.scope == "review")
            )
        ).all()
        assert sorted(values) == [1, 2]


@pytest.mark.asyncio
@dataclass
class SimulatedConcurrentDatabase:
    values: set[int]
    lock: asyncio.Lock

    async def read_next(self) -> int:
        await asyncio.sleep(0)
        return max(self.values, default=0) + 1

    async def insert(self, value: int) -> None:
        async with self.lock:
            if value in self.values:
                raise IntegrityError("simulated unique sequence collision", {}, None)
            self.values.add(value)


class SimulatedSession:
    def __init__(self, database: SimulatedConcurrentDatabase) -> None:
        self._database = database
        self._candidate: int | None = None

    def begin_nested(self) -> SimulatedSession:
        return self

    async def __aenter__(self) -> SimulatedSession:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def add(self, record: SequenceProbe) -> None:
        self._candidate = record.value

    async def flush(self) -> None:
        assert self._candidate is not None
        await self._database.insert(self._candidate)


@pytest.mark.asyncio
async def test_simulated_concurrent_allocators_produce_unique_values() -> None:
    database = SimulatedConcurrentDatabase(values=set(), lock=asyncio.Lock())

    async def allocate_in_session() -> int:
        session = SimulatedSession(database)
        record = await insert_next_unique_integer(
            session, database.read_next, lambda value: SequenceProbe(scope="review", value=value)
        )
        return record.value

    values = await asyncio.gather(allocate_in_session(), allocate_in_session())

    assert sorted(values) == [1, 2]


@pytest.mark.asyncio
async def test_sequence_allocation_failure_rolls_back_only_failed_savepoint(
    tmp_path: Path,
) -> None:
    factory = await _create_factory(tmp_path / "failure.db")

    async with factory() as session:
        await _allocate(session, "review")

        async def read_duplicate() -> int:
            return 1

        with pytest.raises(IntegrityError):
            await insert_next_unique_integer(
                session,
                read_duplicate,
                lambda value: SequenceProbe(scope="review", value=value),
                max_attempts=1,
            )

        values = (
            await session.scalars(
                select(SequenceProbe.value).where(SequenceProbe.scope == "review")
            )
        ).all()
        assert values == [1]
