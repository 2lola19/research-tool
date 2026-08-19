from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from backend.app.storage.contracts import (
    InvalidStorageKeyError,
    StorageIntegrityError,
    StoredObjectMetadata,
    validate_storage_key,
    validate_storage_prefix,
)


class LocalFileStorageProvider:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _resolve_key(self, key: str) -> Path:
        validate_storage_key(key)
        resolved = (self._root / key).resolve()
        if not resolved.is_relative_to(self._root):
            raise InvalidStorageKeyError("Storage key escapes the configured root.")
        return resolved

    async def put(self, key: str, content: bytes, *, media_type: str | None = None) -> None:
        destination = self._resolve_key(key)

        def write() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._resolve_key(key).read_bytes)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._resolve_key(key).unlink, missing_ok=True)

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        source = self._resolve_key(key)
        stream = await asyncio.to_thread(source.open, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(stream.read, 1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(stream.close)

    async def head(self, key: str) -> StoredObjectMetadata:
        source = self._resolve_key(key)

        def inspect() -> StoredObjectMetadata:
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    digest.update(chunk)
            return StoredObjectMetadata(key, size, digest.hexdigest())

        return await asyncio.to_thread(inspect)

    async def put_verified(
        self,
        key: str,
        content: bytes,
        *,
        expected_sha256: str,
        expected_size: int,
        media_type: str | None = None,
    ) -> StoredObjectMetadata:
        self._validate_expected_metadata(expected_sha256, expected_size)
        actual = hashlib.sha256(content).hexdigest()
        if len(content) != expected_size or actual != expected_sha256:
            raise StorageIntegrityError("object bytes do not match expected upload metadata")
        await self.put(key, content, media_type=media_type)
        stored = await self.head(key)
        if stored.size != expected_size or stored.sha256 != expected_sha256:
            raise StorageIntegrityError("stored object failed post-upload verification")
        return StoredObjectMetadata(stored.key, stored.size, stored.sha256, media_type)

    async def get_verified(
        self,
        key: str,
        *,
        expected_sha256: str,
        expected_size: int,
        max_bytes: int,
    ) -> bytes:
        self._validate_expected_metadata(expected_sha256, expected_size)
        if max_bytes < expected_size:
            raise StorageIntegrityError("configured object read limit is below expected size")
        source = self._resolve_key(key)
        declared_size = await asyncio.to_thread(lambda: source.stat().st_size)
        if declared_size > max_bytes:
            raise StorageIntegrityError("stored object exceeds the configured read limit")
        content = await self.get(key)
        actual = hashlib.sha256(content).hexdigest()
        if len(content) != expected_size or actual != expected_sha256:
            raise StorageIntegrityError("stored object checksum verification failed")
        return content

    async def list_keys(self, prefix: str = "") -> list[str]:
        normalized = validate_storage_prefix(prefix)
        root = self._root if not normalized else self._resolve_key(normalized)

        def list_files() -> list[str]:
            if not root.exists():
                return []
            if not root.is_dir():
                return [normalized]
            keys: list[str] = []
            for item in root.rglob("*"):
                if item.is_file() and not item.name.startswith("."):
                    keys.append(item.relative_to(self._root).as_posix())
            return sorted(keys)

        return await asyncio.to_thread(list_files)

    @staticmethod
    def _validate_expected_metadata(expected_sha256: str, expected_size: int) -> None:
        if len(expected_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in expected_sha256.casefold()
        ):
            raise StorageIntegrityError("expected checksum metadata is invalid")
        if expected_size < 0:
            raise StorageIntegrityError("expected object size is invalid")
