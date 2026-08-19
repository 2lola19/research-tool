from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Protocol


class InvalidStorageKeyError(ValueError):
    """Raised when an object key is not an opaque, repository-safe relative key."""


class StorageIntegrityError(ValueError):
    """Raised when stored bytes do not match their durable metadata."""


@dataclass(frozen=True, slots=True)
class StoredObjectMetadata:
    key: str
    size: int
    sha256: str
    media_type: str | None = None


_SAFE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")


def validate_storage_key(key: str) -> str:
    if (
        not key
        or len(key) > 500
        or "\\" in key
        or any(ord(character) < 0x20 for character in key)
        or PurePosixPath(key).is_absolute()
        or PureWindowsPath(key).is_absolute()
        or not _SAFE_KEY.fullmatch(key)
    ):
        raise InvalidStorageKeyError("storage keys must be opaque relative paths")
    parts = key.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise InvalidStorageKeyError("storage keys cannot contain traversal segments")
    return key


def validate_storage_prefix(prefix: str) -> str:
    normalized = prefix.strip("/")
    if not normalized:
        return ""
    return validate_storage_key(normalized)


class ObjectStorageProvider(Protocol):
    async def put(self, key: str, content: bytes, *, media_type: str | None = None) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    def stream(self, key: str) -> AsyncIterator[bytes]: ...


class VerifiedObjectStorageProvider(ObjectStorageProvider, Protocol):
    """Storage boundary required for immutable document artifacts."""

    async def put_verified(
        self,
        key: str,
        content: bytes,
        *,
        expected_sha256: str,
        expected_size: int,
        media_type: str | None = None,
    ) -> StoredObjectMetadata: ...

    async def get_verified(
        self,
        key: str,
        *,
        expected_sha256: str,
        expected_size: int,
        max_bytes: int,
    ) -> bytes: ...

    async def head(self, key: str) -> StoredObjectMetadata: ...

    async def list_keys(self, prefix: str = "") -> list[str]: ...


class S3ObjectClient(Protocol):
    """Minimal vendor-neutral S3-compatible client boundary."""

    async def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        *,
        content_type: str | None,
        metadata: Mapping[str, str],
    ) -> None: ...

    async def get_object(self, bucket: str, key: str) -> bytes: ...

    async def head_object(self, bucket: str, key: str) -> StoredObjectMetadata: ...

    async def delete_object(self, bucket: str, key: str) -> None: ...

    async def list_objects(self, bucket: str, prefix: str) -> list[str]: ...
