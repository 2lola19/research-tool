from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path


class InvalidStorageKeyError(ValueError):
    pass


class LocalFileStorageProvider:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _resolve_key(self, key: str) -> Path:
        if not key or Path(key).is_absolute():
            raise InvalidStorageKeyError("Storage keys must be non-empty relative paths.")
        resolved = (self._root / key).resolve()
        if not resolved.is_relative_to(self._root):
            raise InvalidStorageKeyError("Storage key escapes the configured root.")
        return resolved

    async def put(self, key: str, content: bytes) -> None:
        destination = self._resolve_key(key)

        def write() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._resolve_key(key).read_bytes)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._resolve_key(key).unlink, missing_ok=True)

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        yield await self.get(key)
