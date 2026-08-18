from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.ai.domain import (
    AIAttemptState,
    AIExecutionPolicy,
    AIOutputProposal,
    AIProposalState,
    AIProviderErrorKind,
    AIRun,
    AIRunState,
    AITaskDefinition,
    AITaskType,
    AIValidationStage,
    content_hash,
    estimate_cost,
    render_prompt,
)
from backend.app.ai.execution import call_with_timeout
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.provider import AIProvider, AIProviderError, ProviderRequest
from backend.app.ai.tasks import SEARCH_QUERY_TASK, TASKS, prompt_definition
from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.service import ReviewService

VALIDATOR_VERSION = "ai-structured-validator-1"
RETRY_POLICY_VERSION = "bounded-transient-retry-1"
MAX_OUTPUT_BYTES = 32_768
_GOVERNED_SCREENING_TASKS = {
    AITaskType.SCREENING_SUGGESTION,
    AITaskType.FULL_TEXT_SCREENING_SUGGESTION,
    AITaskType.EXTRACTION_SUGGESTION,
}


class AIExecutionService:
    def __init__(
        self,
        repository: SqlAlchemyAIRepository,
        reviews: ReviewService,
        provenance: SqlAlchemyProvenanceRepository,
        providers: dict[str, AIProvider],
    ) -> None:
        self._repository = repository
        self._reviews = reviews
        self._provenance = provenance
        self._providers = providers

    async def ensure_defaults(
        self,
        actor: ActorContext,
        task_type: AITaskType = AITaskType.SEARCH_QUERY_SUGGESTION,
    ) -> tuple[Any, Any]:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        task = TASKS.get(task_type)
        if task is None:
            raise ValueError(f"AI task is not enabled: {task_type.value}")
        models = await self._repository.list_models(actor.organization_id)
        if models:
            model = models[-1]
        else:
            definition = {
                "provider_key": "mock",
                "model_identifier": "deterministic-mock-v1",
                "display_name": "Deterministic Mock",
                "configuration_version": 1,
                "capabilities": ["structured_generation"],
                "structured_output_supported": True,
                "context_window": 4096,
                "pricing": {},
                "configuration": {"temperature": 0.0, "seed": 23},
                "active": True,
                "deprecated": False,
            }
            model = await self._repository.create_model(
                organization_id=actor.organization_id,
                **definition,
                content_hash=content_hash(definition),
            )
        prompts = await self._repository.list_prompts(actor.organization_id)
        prompt = next((item for item in prompts if item.task_type is task_type), None)
        if prompt is None:
            definition = prompt_definition(task)
            prompt = await self._repository.create_prompt(
                organization_id=actor.organization_id,
                created_by_user_id=actor.user_id,
                **definition,
                content_hash=content_hash(definition),
            )
        return model, prompt

    async def registry(self, actor: ActorContext) -> dict[str, Any]:
        await self.ensure_defaults(actor, AITaskType.SEARCH_QUERY_SUGGESTION)
        await self.ensure_defaults(actor, AITaskType.SCREENING_SUGGESTION)
        await self.ensure_defaults(actor, AITaskType.FULL_TEXT_SCREENING_SUGGESTION)
        await self.ensure_defaults(actor, AITaskType.EXTRACTION_SUGGESTION)
        models = await self._repository.list_models(actor.organization_id)
        prompts = await self._repository.list_prompts(actor.organization_id)
        return {
            "providers": [
                {
                    "key": "mock",
                    "capabilities": ["structured_generation"],
                    "network_required": False,
                }
            ],
            "models": models,
            "prompts": prompts,
            "tasks": list(TASKS.values()),
        }

    async def create_and_execute(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        task_type: AITaskType,
        input_data: dict[str, Any],
        model_version_id: UUID | None = None,
        prompt_version_id: UUID | None = None,
        maximum_attempts: int = 3,
        timeout_seconds: int = 30,
        per_run_token_ceiling: int | None = 4096,
        target_type: str | None = None,
        target_id: UUID | None = None,
    ) -> tuple[AIRun, AIOutputProposal | None]:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        task = TASKS.get(task_type)
        if task is None:
            raise ValueError(f"AI task is not enabled: {task_type.value}")
        if maximum_attempts < 1 or maximum_attempts > 5:
            raise ValueError("maximum attempts must be from 1 through 5")
        model, prompt = await self.ensure_defaults(actor, task_type)
        if model_version_id is not None:
            model = await self._repository.get_model(actor.organization_id, model_version_id)
        if prompt_version_id is not None:
            prompt = await self._repository.get_prompt(actor.organization_id, prompt_version_id)
        if model is None or not model.active or model.deprecated:
            raise ResourceNotFoundError("AI model version was not found or is not allowed")
        if prompt is None or prompt.task_type is not task_type:
            raise ResourceNotFoundError("AI prompt version was not found")
        self._validate_input(input_data, task)
        sanitized = self._sanitize_input(input_data, task)
        rendered, prompt_hash = render_prompt(prompt, sanitized)
        snapshot = {
            "variables": sanitized,
            "references": input_data.get("references", []),
            "copyright_policy": "minimal-necessary-content",
        }
        input_hash = content_hash(snapshot)
        prior = await self._repository.find_identical_run(
            actor.organization_id, review_id, task_type.value, prompt.id, model.id, input_hash
        )
        policy = AIExecutionPolicy(
            version="ai-policy-1",
            enabled=True,
            allowed_task_types=(task_type,),
            allowed_model_version_ids=(model.id,),
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            per_run_token_ceiling=per_run_token_ceiling,
        )
        run = await self._repository.create_run(
            organization_id=actor.organization_id,
            review_id=review_id,
            task_type=task_type.value,
            task_definition_key=task.key,
            task_definition_version=task.version,
            output_schema_version=int(task.output_schema.get("version", 1)),
            prompt_version_id=prompt.id,
            model_version_id=model.id,
            policy_snapshot={
                "version": policy.version,
                "maximum_attempts": maximum_attempts,
                "timeout_seconds": timeout_seconds,
                "per_run_token_ceiling": per_run_token_ceiling,
                "human_review_required": task.human_review_required,
                "allow_fallback": False,
            },
            input_snapshot=snapshot,
            input_hash=input_hash,
            rendered_prompt=rendered,
            rendered_prompt_hash=prompt_hash,
            parameters={"temperature": 0.0, "seed": 23},
            state=AIRunState.QUEUED.value,
            identical_prior_run_id=prior,
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            run.id,
            "AI_RUN_CREATED",
            {"task_type": task_type.value, "input_hash": input_hash},
        )
        run = await self._repository.update_run(
            run.id, actor.organization_id, review_id, state=AIRunState.RUNNING.value
        )
        provider = self._providers.get(model.provider_key)
        if provider is None:
            raise ValueError("configured AI provider is unavailable")
        proposal: AIOutputProposal | None = None
        for attempt_number in range(1, maximum_attempts + 1):
            try:
                result = await call_with_timeout(
                    provider,
                    ProviderRequest(
                        task_type=task_type.value,
                        provider_model_identifier=model.model_identifier,
                        system_prompt=rendered,
                        structured_input=sanitized,
                        output_schema=prompt.output_schema,
                        timeout_seconds=timeout_seconds,
                        temperature=0.0,
                        top_p=None,
                        seed=23,
                    ),
                    timeout_seconds,
                )
                total = result.usage.get("input_tokens", 0) or 0
                total += result.usage.get("output_tokens", 0) or 0
                if per_run_token_ceiling is not None and total > per_run_token_ceiling:
                    raise ValueError("provider usage exceeded the per-run token ceiling")
                response_hash = content_hash(result.output)
                await self._repository.append_attempt(
                    organization_id=actor.organization_id,
                    review_id=review_id,
                    ai_run_id=run.id,
                    attempt_number=attempt_number,
                    provider_key=model.provider_key,
                    model_identifier=result.provider_model_identifier,
                    state=AIAttemptState.SUCCEEDED.value,
                    error_kind=None,
                    error_message=None,
                    provider_request_id=result.provider_request_id,
                    response_snapshot=result.output,
                    response_hash=response_hash,
                    usage=result.usage,
                    estimated_cost=estimate_cost(result.usage, model.pricing),
                    duration_ms=result.duration_ms,
                )
                errors = self._validate_output(result.output, task, sanitized)
                await self._repository.append_validation(
                    organization_id=actor.organization_id,
                    review_id=review_id,
                    ai_run_id=run.id,
                    stage=AIValidationStage.SCHEMA.value,
                    valid=not errors,
                    errors=errors,
                    validator_version=VALIDATOR_VERSION,
                )
                if errors:
                    run = await self._repository.update_run(
                        run.id,
                        actor.organization_id,
                        review_id,
                        state=AIRunState.INVALID_OUTPUT.value,
                        failure_reason="structured output validation failed",
                        completed_at=datetime.now(UTC),
                    )
                    await self._audit(
                        actor, review_id, run.id, "AI_OUTPUT_INVALID", {"errors": errors}
                    )
                    return run, None
                assert isinstance(result.output, dict)
                evidence_references = result.output.get("evidence_references")
                if not isinstance(evidence_references, list):
                    evidence_references = result.output.get("evidence", [])
                if not isinstance(evidence_references, list):
                    evidence_references = []
                proposal = await self._repository.create_proposal(
                    organization_id=actor.organization_id,
                    review_id=review_id,
                    ai_run_id=run.id,
                    task_type=task_type.value,
                    target_type=target_type if target_type is not None else "SEARCH_QUERY_DRAFT",
                    target_id=target_id,
                    structured_value=result.output,
                    evidence_references=evidence_references,
                    model_reported_confidence=result.output.get("model_reported_confidence"),
                    response_hash=response_hash,
                )
                run = await self._repository.update_run(
                    run.id,
                    actor.organization_id,
                    review_id,
                    state=AIRunState.SUCCEEDED.value,
                    completed_at=datetime.now(UTC),
                )
                await self._audit(
                    actor,
                    review_id,
                    run.id,
                    "AI_RUN_SUCCEEDED",
                    {"proposal_id": str(proposal.id), "response_hash": response_hash},
                )
                return run, proposal
            except AIProviderError as exc:
                state = (
                    AIAttemptState.TIMED_OUT
                    if exc.kind is AIProviderErrorKind.TIMEOUT
                    else AIAttemptState.RATE_LIMITED
                    if exc.kind is AIProviderErrorKind.RATE_LIMIT
                    else AIAttemptState.FAILED
                )
                await self._repository.append_attempt(
                    organization_id=actor.organization_id,
                    review_id=review_id,
                    ai_run_id=run.id,
                    attempt_number=attempt_number,
                    provider_key=model.provider_key,
                    model_identifier=model.model_identifier,
                    state=state.value,
                    error_kind=exc.kind.value,
                    error_message=str(exc),
                    provider_request_id=None,
                    response_snapshot=None,
                    response_hash=None,
                    usage={},
                    estimated_cost=None,
                    duration_ms=None,
                )
                transient = exc.kind in {
                    AIProviderErrorKind.TIMEOUT,
                    AIProviderErrorKind.RATE_LIMIT,
                    AIProviderErrorKind.UNAVAILABLE,
                }
                if transient and attempt_number < maximum_attempts:
                    continue
                final_state = (
                    AIRunState.TIMED_OUT
                    if exc.kind is AIProviderErrorKind.TIMEOUT
                    else AIRunState.FAILED
                )
                run = await self._repository.update_run(
                    run.id,
                    actor.organization_id,
                    review_id,
                    state=final_state.value,
                    failure_reason=str(exc),
                    completed_at=datetime.now(UTC),
                )
                await self._audit(
                    actor, review_id, run.id, "AI_RUN_FAILED", {"error_kind": exc.kind.value}
                )
                return run, None
        return run, proposal

    async def list_runs(self, actor: ActorContext, review_id: UUID) -> list[AIRun]:
        await self._reviews.get(actor, review_id)
        runs = await self._repository.list_runs(actor.organization_id, review_id)
        return [item for item in runs if item.task_type not in _GOVERNED_SCREENING_TASKS]

    async def proposal(
        self, actor: ActorContext, review_id: UUID, proposal_id: UUID
    ) -> AIOutputProposal:
        await self._reviews.get(actor, review_id)
        item = await self._repository.get_proposal(actor.organization_id, review_id, proposal_id)
        if item is None or item.task_type in _GOVERNED_SCREENING_TASKS:
            raise ResourceNotFoundError("AI proposal was not found")
        return item

    async def decide(
        self,
        actor: ActorContext,
        review_id: UUID,
        proposal_id: UUID,
        decision: AIProposalState,
        reason: str | None,
    ) -> AIOutputProposal:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        item = await self.proposal(actor, review_id, proposal_id)
        if item.state is not AIProposalState.PENDING_REVIEW:
            raise ConflictError("AI proposal already has a final human decision")
        if decision not in {AIProposalState.ACCEPTED, AIProposalState.REJECTED}:
            raise ValueError("decision must be ACCEPTED or REJECTED")
        decided = await self._repository.decide(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal_id,
            decision=decision.value,
            reason=reason,
            canonical_subject_type="SEARCH_QUERY_DRAFT"
            if decision is AIProposalState.ACCEPTED
            else None,
            canonical_subject_id=proposal_id if decision is AIProposalState.ACCEPTED else None,
            reviewer_user_id=actor.user_id,
        )
        if decision is AIProposalState.ACCEPTED:
            await self._provenance.append_provenance(
                organization_id=actor.organization_id,
                review_id=review_id,
                subject_type="SEARCH_QUERY_DRAFT",
                subject_id=proposal_id,
                source_type="AI_PROPOSAL",
                source_id=proposal_id,
                source_locator={"ai_run_id": str(item.ai_run_id)},
                method_name="human-accepted-ai-search-query-draft",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                actor_user_id=actor.user_id,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.HUMAN_VERIFIED,
            )
        await self._audit(
            actor,
            review_id,
            proposal_id,
            f"AI_PROPOSAL_{decision.value}",
            {"ai_run_id": str(item.ai_run_id), "reason": reason},
        )
        return decided

    @staticmethod
    def _validate_input(value: dict[str, Any], task: AITaskDefinition = SEARCH_QUERY_TASK) -> None:
        missing = []
        for key in task.input_contract["required"]:
            current = value.get(key)
            if key in {
                "eligibility_criteria",
                "exclusion_criteria",
                "schema_fields",
                "source_documents",
                "chunks",
            }:
                valid = isinstance(current, list) and bool(current)
            else:
                valid = isinstance(current, str) and bool(current.strip())
            if not valid:
                missing.append(key)
        if missing:
            raise ValueError(f"missing required AI task input: {', '.join(missing)}")
        serialized = json.dumps(value, default=str)
        if len(serialized.encode()) > 65_536:
            raise ValueError("AI task input is too large")
        lowered = serialized.casefold()
        if any(
            marker in lowered
            for marker in ("api_key", "authorization: bearer", "database_url", "private key")
        ):
            raise ValueError("AI task input appears to contain a secret")
        if task.task_type in {
            AITaskType.SCREENING_SUGGESTION,
            AITaskType.FULL_TEXT_SCREENING_SUGGESTION,
        }:
            for key in ("eligibility_criteria", "exclusion_criteria"):
                if not isinstance(value.get(key), list) or not value[key]:
                    raise ValueError(f"{key} must be a non-empty list")
            if value.get("abstract") is not None and not isinstance(value["abstract"], str):
                raise ValueError("article abstract must be text or null")
        if task.task_type is AITaskType.FULL_TEXT_SCREENING_SUGGESTION:
            chunks = value.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                raise ValueError("full-text screening requires selected document chunks")
            if len(chunks) > 80:
                raise ValueError("full-text screening input exceeds the chunk limit")
        if task.task_type is AITaskType.EXTRACTION_SUGGESTION:
            fields = value.get("schema_fields")
            chunks = value.get("chunks")
            documents = value.get("source_documents")
            if not isinstance(fields, list) or not fields or len(fields) > 200:
                raise ValueError("structured extraction requires 1 through 200 schema fields")
            if not isinstance(chunks, list) or not chunks or len(chunks) > 80:
                raise ValueError("structured extraction requires 1 through 80 selected chunks")
            if not isinstance(documents, list) or not documents or len(documents) > 8:
                raise ValueError("structured extraction requires 1 through 8 source documents")

    @staticmethod
    def _sanitize_input(
        value: dict[str, Any], task: AITaskDefinition = SEARCH_QUERY_TASK
    ) -> dict[str, Any]:
        if task.task_type is AITaskType.SEARCH_QUERY_SUGGESTION:
            return {"query": value["query"].strip(), "objective": value["objective"].strip()}
        if task.task_type is AITaskType.FULL_TEXT_SCREENING_SUGGESTION:
            return {
                "review_id": str(value["review_id"]),
                "protocol_version_id": str(value["protocol_version_id"]),
                "eligibility_criteria": value["eligibility_criteria"],
                "exclusion_criteria": value["exclusion_criteria"],
                "article_id": str(value["article_id"]),
                "citation": value["citation"],
                "document_identity": value["document_identity"],
                "chunks": value["chunks"],
                "input_preparation": value["input_preparation"],
            }
        if task.task_type is AITaskType.EXTRACTION_SUGGESTION:
            return {
                "review_id": str(value["review_id"]),
                "study_id": str(value["study_id"]),
                "assignment_id": str(value["assignment_id"]),
                "schema_version_id": str(value["schema_version_id"]),
                "schema_identity": value["schema_identity"],
                "schema_fields": value["schema_fields"],
                "source_documents": value["source_documents"],
                "chunks": value["chunks"],
                "input_preparation": value["input_preparation"],
            }
        citation = value.get("citation")
        if not isinstance(citation, dict):
            citation = {
                "article_id": str(value["article_id"]),
                "title": value["title"].strip(),
                "abstract": value.get("abstract"),
            }
        return {
            "review_id": str(value["review_id"]),
            "protocol_version_id": str(value["protocol_version_id"]),
            "eligibility_criteria": value["eligibility_criteria"],
            "exclusion_criteria": value["exclusion_criteria"],
            "article_id": str(value["article_id"]),
            "title": value["title"].strip(),
            "abstract": value.get("abstract"),
            "citation": citation,
        }

    @staticmethod
    def _validate_output(
        value: dict[str, Any] | str,
        task: AITaskDefinition = SEARCH_QUERY_TASK,
        input_data: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        if not isinstance(value, dict):
            return [
                {"code": "INVALID_JSON_OBJECT", "message": "structured output must be an object"}
            ]
        if len(json.dumps(value, default=str).encode()) > MAX_OUTPUT_BYTES:
            return [{"code": "OUTPUT_TOO_LARGE", "message": "structured output exceeds limit"}]
        required = set(task.output_schema["required"])
        allowed = set(task.output_schema["allowed"])
        missing = sorted(required - value.keys())
        extra = sorted(value.keys() - allowed)
        errors = [{"code": "MISSING_FIELD", "message": key} for key in missing] + [
            {"code": "UNEXPECTED_FIELD", "message": key} for key in extra
        ]
        if task.task_type is AITaskType.SCREENING_SUGGESTION:
            errors.extend(AIExecutionService._validate_screening_output(value, input_data))
            return errors
        if task.task_type is AITaskType.FULL_TEXT_SCREENING_SUGGESTION:
            errors.extend(
                AIExecutionService._validate_full_text_screening_output(value, input_data)
            )
            return errors
        if task.task_type is AITaskType.EXTRACTION_SUGGESTION:
            if str(value.get("schema_version_id", "")) != str(
                (input_data or {}).get("schema_version_id", "")
            ):
                errors.append(
                    {"code": "WRONG_SCHEMA_VERSION", "message": "schema version does not match"}
                )
            if not isinstance(value.get("fields"), list):
                errors.append({"code": "INVALID_FIELDS", "message": "fields must be a list"})
            return errors
        if "evidence_references" in value and not isinstance(value["evidence_references"], list):
            errors.append(
                {"code": "INVALID_EVIDENCE", "message": "evidence_references must be a list"}
            )
        if isinstance(value.get("evidence_references"), list) and value["evidence_references"]:
            errors.append(
                {
                    "code": "UNSUPPORTED_EVIDENCE_REFERENCE",
                    "message": "search-query demonstration cannot cite evidence objects",
                }
            )
        confidence = value.get("model_reported_confidence")
        if confidence is not None and (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            errors.append(
                {
                    "code": "INVALID_CONFIDENCE",
                    "message": "model confidence must be from 0 through 1",
                }
            )
        return errors

    @staticmethod
    def _validate_screening_output(
        value: dict[str, Any], input_data: dict[str, Any] | None
    ) -> list[dict[str, str]]:
        errors: list[dict[str, str]] = []
        suggestion = value.get("suggestion")
        if suggestion not in {"INCLUDE", "EXCLUDE", "MAYBE", "ABSTAIN"}:
            errors.append({"code": "INVALID_SUGGESTION", "message": "unknown screening suggestion"})
        criterion_ids = value.get("exclusion_criterion_ids")
        if not isinstance(criterion_ids, list) or not all(
            isinstance(item, str) for item in criterion_ids
        ):
            errors.append(
                {
                    "code": "INVALID_CRITERIA",
                    "message": "exclusion_criterion_ids must be a list of strings",
                }
            )
        elif input_data is not None:
            allowed_ids = {
                str(item.get("id"))
                for item in input_data.get("exclusion_criteria", [])
                if isinstance(item, dict) and item.get("id") is not None
            }
            if any(item not in allowed_ids for item in criterion_ids):
                errors.append(
                    {
                        "code": "UNKNOWN_CRITERION",
                        "message": "output referenced an exclusion criterion not in the protocol",
                    }
                )
        rationale = value.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append({"code": "INVALID_RATIONALE", "message": "rationale must be text"})
        confidence = value.get("model_reported_confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1
        ):
            errors.append(
                {
                    "code": "INVALID_CONFIDENCE",
                    "message": "model confidence must be from 0 through 1",
                }
            )
        evidence = value.get("evidence")
        if not isinstance(evidence, list):
            errors.append({"code": "INVALID_EVIDENCE", "message": "evidence must be a list"})
        else:
            source = ""
            if input_data is not None:
                source = (
                    f"{input_data.get('title', '')}\n{input_data.get('abstract') or ''}".casefold()
                )
            for item in evidence:
                quote = (
                    item
                    if isinstance(item, str)
                    else item.get("quote")
                    if isinstance(item, dict)
                    else None
                )
                if not isinstance(quote, str) or not quote.strip():
                    errors.append(
                        {"code": "INVALID_EVIDENCE", "message": "each evidence item needs a quote"}
                    )
                elif len(quote) > 500:
                    errors.append(
                        {
                            "code": "EVIDENCE_TOO_LARGE",
                            "message": "evidence quotes are limited to 500 characters",
                        }
                    )
                elif input_data is not None and quote.casefold() not in source:
                    errors.append(
                        {
                            "code": "EVIDENCE_NOT_IN_SOURCE",
                            "message": (
                                "evidence quote was not found in the supplied title or abstract"
                            ),
                        }
                    )
        uncertainty = value.get("uncertainty_reason")
        if suggestion in {"MAYBE", "ABSTAIN"} and (
            not isinstance(uncertainty, str) or not uncertainty.strip()
        ):
            errors.append(
                {
                    "code": "UNCERTAINTY_REASON_REQUIRED",
                    "message": "MAYBE and ABSTAIN require an uncertainty reason",
                }
            )
        if suggestion == "INCLUDE" and criterion_ids:
            errors.append(
                {
                    "code": "INCLUDE_HAS_EXCLUSION_CRITERIA",
                    "message": "INCLUDE cannot cite exclusion criteria",
                }
            )
        if suggestion == "EXCLUDE" and not criterion_ids:
            errors.append(
                {
                    "code": "EXCLUDE_MISSING_CRITERIA",
                    "message": "EXCLUDE must cite at least one listed exclusion criterion",
                }
            )
        return errors

    @staticmethod
    def _validate_full_text_screening_output(
        value: dict[str, Any], input_data: dict[str, Any] | None
    ) -> list[dict[str, str]]:
        from backend.app.ai.full_text_domain import validate_full_text_output

        return validate_full_text_output(value, input_data or {})

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_id: UUID,
        action: str,
        snapshot: dict[str, Any],
    ) -> None:
        await self._provenance.append_audit_event(
            organization_id=actor.organization_id,
            review_id=review_id,
            entity_type="AI_EXECUTION",
            entity_id=entity_id,
            action=action,
            actor_user_id=actor.user_id,
            before_snapshot=None,
            after_snapshot=snapshot,
            reason=None,
        )
