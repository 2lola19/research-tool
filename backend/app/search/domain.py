from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


def search_content_hash(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SearchStrategyVersion:
    id: UUID
    organization_id: UUID
    review_id: UUID
    protocol_version_id: UUID
    version: int
    content: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SearchTranslation:
    id: UUID
    search_strategy_version_id: UUID
    organization_id: UUID
    review_id: UUID
    provider: str
    translator_version: str
    query: str
    created_by_user_id: UUID
    created_at: datetime


class SearchTranslator(Protocol):
    provider: str
    version: str

    def translate(self, content: dict[str, Any]) -> str: ...
