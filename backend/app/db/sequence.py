from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def insert_next_unique_integer[RecordT](
    session: AsyncSession,
    read_next: Callable[[], Awaitable[int]],
    build_record: Callable[[int], RecordT],
    *,
    max_attempts: int = 3,
) -> RecordT:
    """Insert a scoped sequential record using the database unique constraint."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    for attempt in range(max_attempts):
        try:
            async with session.begin_nested():
                next_value = await read_next()
                record = build_record(next_value)
                session.add(record)
                await session.flush()
        except IntegrityError:
            if attempt == max_attempts - 1:
                raise
        else:
            return record

    raise AssertionError("sequence allocation loop exited unexpectedly")
