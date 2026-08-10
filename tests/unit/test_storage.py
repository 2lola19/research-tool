from pathlib import Path

import pytest

from backend.app.storage.local import InvalidStorageKeyError, LocalFileStorageProvider


@pytest.mark.asyncio
async def test_local_storage_round_trip(tmp_path: Path) -> None:
    storage = LocalFileStorageProvider(tmp_path)

    await storage.put("review/document.pdf", b"content")

    assert await storage.get("review/document.pdf") == b"content"
    assert [part async for part in storage.stream("review/document.pdf")] == [b"content"]
    await storage.delete("review/document.pdf")
    assert not (tmp_path / "review" / "document.pdf").exists()


@pytest.mark.parametrize("key", ["", "../secret", "/absolute/path"])
def test_local_storage_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    storage = LocalFileStorageProvider(tmp_path)

    with pytest.raises(InvalidStorageKeyError):
        storage._resolve_key(key)
