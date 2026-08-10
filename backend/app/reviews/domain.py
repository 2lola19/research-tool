from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReviewProject:
    id: UUID
    organization_id: UUID
    title: str
    owner_user_id: UUID
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
