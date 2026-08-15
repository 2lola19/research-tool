from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai.persistence import AIExecutionRunRecord, AIRunAttemptRecord


async def list_attempts(
    session: AsyncSession, organization_id: UUID, review_id: UUID, run_id: UUID
) -> list[dict[str, Any]]:
    run = await session.scalar(
        select(AIExecutionRunRecord.id).where(
            AIExecutionRunRecord.id == run_id,
            AIExecutionRunRecord.organization_id == organization_id,
            AIExecutionRunRecord.review_id == review_id,
        )
    )
    if run is None:
        return []
    rows = await session.scalars(
        select(AIRunAttemptRecord)
        .where(
            AIRunAttemptRecord.organization_id == organization_id,
            AIRunAttemptRecord.review_id == review_id,
            AIRunAttemptRecord.ai_run_id == run_id,
        )
        .order_by(AIRunAttemptRecord.attempt_number)
    )
    return [
        {
            "id": row.id,
            "attempt_number": row.attempt_number,
            "provider_key": row.provider_key,
            "model_identifier": row.model_identifier,
            "state": row.state,
            "error_kind": row.error_kind,
            "provider_request_id": row.provider_request_id,
            "usage": row.usage,
            "estimated_cost": row.estimated_cost,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at,
        }
        for row in rows
    ]


async def usage_summary(
    session: AsyncSession, organization_id: UUID, review_id: UUID
) -> dict[str, Any]:
    rows = await session.scalars(
        select(AIRunAttemptRecord).where(
            AIRunAttemptRecord.organization_id == organization_id,
            AIRunAttemptRecord.review_id == review_id,
        )
    )
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    }
    attempts = 0
    unknown_cost_attempts = 0
    known_cost = 0.0
    for row in rows:
        attempts += 1
        for key in totals:
            totals[key] += int(row.usage.get(key) or 0)
        if row.estimated_cost is None:
            unknown_cost_attempts += 1
        else:
            known_cost += float(row.estimated_cost)
    run_count = len(
        list(
            await session.scalars(
                select(AIExecutionRunRecord.id).where(
                    AIExecutionRunRecord.organization_id == organization_id,
                    AIExecutionRunRecord.review_id == review_id,
                )
            )
        )
    )
    return {
        "runs": run_count,
        "attempts": attempts,
        **totals,
        "known_estimated_cost": str(known_cost),
        "unknown_cost_attempts": unknown_cost_attempts,
    }
