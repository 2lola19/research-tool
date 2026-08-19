from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator

from backend.app.storage.contracts import (
    S3ObjectClient,
    StorageIntegrityError,
    StoredObjectMetadata,
    validate_storage_key,
    validate_storage_prefix,
)


class S3CompatibleObjectStorageProvider:
    """S3-compatible adapter with no vendor SDK or URL authority in domain code."""

    def __init__(self, bucket: str, client: S3ObjectClient) -> None:
        if not bucket or any(character.isspace() for character in bucket):
            raise ValueError("S3 bucket must be a non-empty identifier")
        self._bucket = bucket
        self._client = client

    async def put(self, key: str, content: bytes, *, media_type: str | None = None) -> None:
        validate_storage_key(key)
        await self._client.put_object(
            self._bucket,
            key,
            content,
            content_type=media_type,
            metadata={"sha256": hashlib.sha256(content).hexdigest(), "size": str(len(content))},
        )

    async def get(self, key: str) -> bytes:
        validate_storage_key(key)
        return await self._client.get_object(self._bucket, key)

    async def delete(self, key: str) -> None:
        validate_storage_key(key)
        await self._client.delete_object(self._bucket, key)

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        yield await self.get(key)

    async def head(self, key: str) -> StoredObjectMetadata:
        validate_storage_key(key)
        return await self._client.head_object(self._bucket, key)

    async def put_verified(
        self,
        key: str,
        content: bytes,
        *,
        expected_sha256: str,
        expected_size: int,
        media_type: str | None = None,
    ) -> StoredObjectMetadata:
        self._validate_expected_metadata(expected_sha256, expected_size, max_bytes=None)
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
        self._validate_expected_metadata(expected_sha256, expected_size, max_bytes=max_bytes)
        if expected_size > max_bytes:
            raise StorageIntegrityError("stored object exceeds the configured read limit")
        content = await self.get(key)
        actual = hashlib.sha256(content).hexdigest()
        if len(content) != expected_size or actual != expected_sha256:
            raise StorageIntegrityError("stored object checksum verification failed")
        return content

    async def list_keys(self, prefix: str = "") -> list[str]:
        normalized_prefix = validate_storage_prefix(prefix)
        keys = [
            validate_storage_key(key)
            for key in await self._client.list_objects(self._bucket, normalized_prefix)
        ]
        return sorted(
            key
            for key in keys
            if not normalized_prefix
            or key == normalized_prefix
            or key.startswith(f"{normalized_prefix}/")
        )

    @staticmethod
    def _validate_expected_metadata(
        expected_sha256: str, expected_size: int, *, max_bytes: int | None
    ) -> None:
        if len(expected_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in expected_sha256.casefold()
        ):
            raise StorageIntegrityError("expected checksum metadata is invalid")
        if expected_size < 0 or (max_bytes is not None and max_bytes < expected_size):
            raise StorageIntegrityError("expected object size is invalid")
