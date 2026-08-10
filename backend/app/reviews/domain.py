from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReviewProject:
    id: UUID
    organization_id: UUID
    title: str
    project_slug: str
    description: str | None
    owner_user_id: UUID
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    archived_by_user_id: UUID | None


@dataclass(frozen=True, slots=True)
class ReviewParticipant:
    user_id: UUID
    email: str
    display_name: str
    organization_role: str
