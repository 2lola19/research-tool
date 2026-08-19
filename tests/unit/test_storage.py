import hashlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from backend.app.storage.contracts import StoredObjectMetadata
from backend.app.storage.local import InvalidStorageKeyError, LocalFileStorageProvider
from backend.app.storage.s3 import S3CompatibleObjectStorageProvider


@pytest.mark.asyncio
async def test_local_storage_round_trip(tmp_path: Path) -> None:
    storage = LocalFileStorageProvider(tmp_path)

    content = b"content"
    checksum = hashlib.sha256(content).hexdigest()
    await storage.put_verified(
        "review/document.pdf",
        content,
        expected_sha256=checksum,
        expected_size=len(content),
        media_type="application/pdf",
    )

    assert (
        await storage.get_verified(
            "review/document.pdf",
            expected_sha256=checksum,
            expected_size=len(content),
            max_bytes=100,
        )
        == content
    )
    assert [part async for part in storage.stream("review/document.pdf")] == [content]
    assert await storage.list_keys("review") == ["review/document.pdf"]
    await storage.delete("review/document.pdf")
    assert not (tmp_path / "review" / "document.pdf").exists()


@pytest.mark.parametrize("key", ["", "../secret", "/absolute/path"])
def test_local_storage_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    storage = LocalFileStorageProvider(tmp_path)

    with pytest.raises(InvalidStorageKeyError):
        storage._resolve_key(key)


@pytest.mark.asyncio
async def test_local_storage_detects_corruption(tmp_path: Path) -> None:
    storage = LocalFileStorageProvider(tmp_path)
    content = b"original"
    checksum = hashlib.sha256(content).hexdigest()
    await storage.put("review/document.pdf", content)
    (tmp_path / "review" / "document.pdf").write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="checksum"):
        await storage.get_verified(
            "review/document.pdf",
            expected_sha256=checksum,
            expected_size=len(content),
            max_bytes=100,
        )


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        *,
        content_type: str | None,
        metadata: Mapping[str, str],
    ) -> None:
        self.objects[(bucket, key)] = body

    async def get_object(self, bucket: str, key: str) -> bytes:
        return self.objects[(bucket, key)]

    async def head_object(self, bucket: str, key: str) -> StoredObjectMetadata:
        content = self.objects[(bucket, key)]
        import hashlib

        return StoredObjectMetadata(key, len(content), hashlib.sha256(content).hexdigest())

    async def delete_object(self, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)

    async def list_objects(self, bucket: str, prefix: str) -> list[str]:
        return [
            key
            for (item_bucket, key) in self.objects
            if item_bucket == bucket and key.startswith(prefix)
        ]


@pytest.mark.asyncio
async def test_s3_adapter_uses_vendor_neutral_client_boundary() -> None:
    client = FakeS3Client()
    storage = S3CompatibleObjectStorageProvider("review-bucket", client)
    content = b"s3 fixture"
    checksum = hashlib.sha256(content).hexdigest()

    await storage.put_verified(
        "organization/review/document.pdf",
        content,
        expected_sha256=checksum,
        expected_size=len(content),
        media_type="application/pdf",
    )

    assert (
        await storage.get_verified(
            "organization/review/document.pdf",
            expected_sha256=checksum,
            expected_size=len(content),
            max_bytes=100,
        )
        == content
    )
    assert await storage.list_keys("organization/review") == ["organization/review/document.pdf"]
