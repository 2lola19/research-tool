from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.app.documents.domain import CanonicalDocument
from backend.app.documents.parsers import materialize_blocks


def build_chunk_manifest(
    canonical: CanonicalDocument, *, content_sha256: str
) -> tuple[list[dict[str, Any]], str, int]:
    """Build a bounded, deterministic manifest for one immutable processing run."""

    blocks = materialize_blocks(canonical)
    manifest: list[dict[str, Any]] = []
    text_byte_size = 0
    for block in blocks:
        text_sha256 = hashlib.sha256(block.text.encode("utf-8")).hexdigest()
        text_byte_size += len(block.text.encode("utf-8"))
        manifest.append(
            {
                "block_id": block.block_id,
                "block_type": block.block_type.value,
                "block_order": block.block_order,
                "page_number": block.page_number,
                "section_path": list(block.section_path),
                "text_sha256": text_sha256,
                "text_byte_size": len(block.text.encode("utf-8")),
                "table_id": block.table_id,
                "figure_id": block.figure_id,
                "coordinates": dict(block.coordinates) if block.coordinates else None,
            }
        )
    envelope: dict[str, Any] = {
        "manifest_version": "document-chunk-manifest-1",
        "content_sha256": content_sha256,
        "blocks": manifest,
    }
    encoded = json.dumps(
        envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return manifest, hashlib.sha256(encoded).hexdigest(), text_byte_size
