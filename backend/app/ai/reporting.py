from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai.persistence import (
    AIExecutionRunRecord,
    AIModelVersionRecord,
    AIOutputProposalRecord,
    AIPromptTemplateVersionRecord,
    AIReviewDecisionRecord,
)


async def accepted_ai_provenance(
    session: AsyncSession, organization_id: UUID, review_id: UUID
) -> list[dict[str, Any]]:
    """Publication-safe AI provenance: accepted proposals only, with no prompt source text."""
    rows = (
        await session.execute(
            select(
                AIReviewDecisionRecord,
                AIOutputProposalRecord,
                AIExecutionRunRecord,
                AIModelVersionRecord,
                AIPromptTemplateVersionRecord,
            )
            .join(
                AIOutputProposalRecord,
                AIOutputProposalRecord.id == AIReviewDecisionRecord.proposal_id,
            )
            .join(AIExecutionRunRecord, AIExecutionRunRecord.id == AIOutputProposalRecord.ai_run_id)
            .join(
                AIModelVersionRecord,
                AIModelVersionRecord.id == AIExecutionRunRecord.model_version_id,
            )
            .join(
                AIPromptTemplateVersionRecord,
                AIPromptTemplateVersionRecord.id == AIExecutionRunRecord.prompt_version_id,
            )
            .where(
                AIReviewDecisionRecord.organization_id == organization_id,
                AIReviewDecisionRecord.review_id == review_id,
                AIReviewDecisionRecord.decision == "ACCEPTED",
            )
            .order_by(AIReviewDecisionRecord.created_at, AIReviewDecisionRecord.id)
        )
    ).all()
    return [
        {
            "proposal_id": str(decision.proposal_id),
            "ai_run_id": str(proposal.ai_run_id),
            "task_type": proposal.task_type,
            "response_hash": proposal.response_hash,
            "model_version_id": str(model.id),
            "provider": model.provider_key,
            "requested_model_identifier": model.model_identifier,
            "model_configuration_hash": model.content_hash,
            "prompt_version_id": str(prompt.id),
            "prompt_key": prompt.prompt_key,
            "prompt_version": prompt.version,
            "prompt_content_hash": prompt.content_hash,
            "input_hash": run.input_hash,
            "rendered_prompt_hash": run.rendered_prompt_hash,
            "human_reviewer_id": str(decision.reviewer_user_id),
            "accepted_at": str(decision.created_at),
        }
        for decision, proposal, run, model, prompt in rows
    ]
