from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.ai.domain import content_hash
from backend.app.ai.extraction_domain import ExtractionSource, prepare_extraction_input
from backend.app.ai.full_text_domain import normalize_evidence_text
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.risk_of_bias.domain import suggest_domain_judgment, suggest_overall_judgment


class AIRobReadiness(StrEnum):
    READY = "READY"
    BLOCKED_NO_ASSESSMENT = "BLOCKED_NO_ASSESSMENT"
    BLOCKED_NOT_OWNER = "BLOCKED_NOT_OWNER"
    BLOCKED_SUBMITTED = "BLOCKED_SUBMITTED"
    BLOCKED_NO_INSTRUMENT = "BLOCKED_NO_INSTRUMENT"
    BLOCKED_INSTRUMENT_NOT_APPROVED = "BLOCKED_INSTRUMENT_NOT_APPROVED"
    BLOCKED_SOURCE_SCOPE = "BLOCKED_SOURCE_SCOPE"
    BLOCKED_DOCUMENT_PROCESSING = "BLOCKED_DOCUMENT_PROCESSING"
    BLOCKED_NO_PARSED_TEXT = "BLOCKED_NO_PARSED_TEXT"
    BLOCKED_OTHER = "BLOCKED_OTHER"


class AIRobAnswerStatus(StrEnum):
    PROPOSED_ANSWER = "PROPOSED_ANSWER"
    ABSTAIN = "ABSTAIN"


class AIRobReviewAction(StrEnum):
    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class AIRobAccessType(StrEnum):
    ASSISTED_VIEW = "ASSISTED_VIEW"
    POST_SUBMISSION_REVEAL = "POST_SUBMISSION_REVEAL"


class AIRobReferenceStandard(StrEnum):
    ADJUDICATED_ASSESSMENT = "ADJUDICATED_ASSESSMENT"
    DUAL_HUMAN_ASSESSMENT = "DUAL_HUMAN_ASSESSMENT"
    CURATED_GOLD = "CURATED_GOLD"


class AIRobMatchClass(StrEnum):
    AGREEMENT = "AGREEMENT"
    DISAGREEMENT = "DISAGREEMENT"
    AI_ABSTAIN = "AI_ABSTAIN"
    INVALID_PROPOSAL = "INVALID_PROPOSAL"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"


class AIRobErrorCategory(StrEnum):
    WRONG_SIGNALING_ANSWER = "WRONG_SIGNALING_ANSWER"
    UNSUPPORTED_LOW_RISK = "UNSUPPORTED_LOW_RISK"
    DANGEROUS_UNDERESTIMATION = "DANGEROUS_UNDERESTIMATION"
    MISSED_HIGH_RISK = "MISSED_HIGH_RISK"
    ABSTENTION = "ABSTENTION"
    FABRICATED_EVIDENCE = "FABRICATED_EVIDENCE"
    WRONG_DOCUMENT = "WRONG_DOCUMENT"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    WRONG_INSTRUMENT = "WRONG_INSTRUMENT"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class AIRobPolicy:
    id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    mode: AIScreeningMode
    maximum_batch_size: int
    created_by_user_id: UUID


@dataclass(frozen=True, slots=True)
class AIRobProposalLink:
    id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    assessment_id: UUID
    study_id: UUID
    instrument_version_id: UUID
    instrument_content_hash: str
    task_definition_version: int
    assistance_mode: AIScreeningMode
    source_manifest: list[dict[str, Any]]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, Any], ...]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str
    validation_results: dict[str, Any]
    domain_suggestions: dict[str, str | None]
    overall_suggestion: str | None


@dataclass(frozen=True, slots=True)
class AIRobEvaluationDataset:
    id: UUID
    organization_id: UUID
    review_id: UUID
    instrument_version_id: UUID
    logical_key: str
    version: int
    name: str
    reference_standard: AIRobReferenceStandard
    content_hash: str


def prepare_rob_input(definition: dict[str, Any], sources: list[ExtractionSource]) -> Any:
    fields = [
        {
            "key": question["key"],
            "label": question["text"],
            "description": question.get("guidance"),
            "field_type": "TEXT",
            "allowed_options": list(question.get("allowed_answers", [])),
            "required": bool(question.get("required", True)),
            "display_order": question.get("order", index),
        }
        for index, question in enumerate(
            question_item
            for domain in definition["domains"]
            for question_item in domain["questions"]
        )
    ]
    return prepare_extraction_input(
        fields,
        sources,
        maximum_characters=24_000,
        maximum_chunks=80,
        characters_per_chunk=3_000,
    )


def source_manifest(source: ExtractionSource) -> dict[str, Any]:
    blocks = [
        {
            "id": str(block.id),
            "block_id": block.block_id,
            "order": block.block_order,
            "page": block.page_number,
            "section": list(block.section_path),
            "text_hash": content_hash(normalize_evidence_text(block.text)),
        }
        for block in sorted(source.blocks, key=lambda item: (item.block_order, item.block_id))
    ]
    parsed_hash = content_hash(blocks)
    return {
        "article_id": str(source.document.article_id),
        "document_id": str(source.document.id),
        "document_version_id": str(source.document.id),
        "processing_run_id": str(source.processing.id),
        "document_role": source.role.value,
        "document_content_hash": source.document.sha256 or content_hash(str(source.document.id)),
        "parser_name": source.processing.parser_name,
        "parser_version": source.processing.parser_version,
        "parsed_content_hash": parsed_hash,
        "block_count": len(blocks),
    }


def question_definitions(definition: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "key": question["key"],
            "text": question["text"],
            "guidance": question.get("guidance"),
            "required": bool(question.get("required", True)),
            "allowed_answers": list(question.get("allowed_answers", [])),
            "domain_key": domain["key"],
            "order": question.get("order", question_index),
        }
        for domain in definition["domains"]
        for question_index, question in enumerate(domain["questions"])
    ]


def validate_rob_output(
    value: dict[str, Any], definition: dict[str, Any], input_data: dict[str, Any]
) -> dict[str, Any]:
    expected = {item["key"]: item for item in question_definitions(definition)}
    raw_answers = value.get("answers")
    if not isinstance(raw_answers, list):
        raw_answers = []
    occurrences: dict[str, list[dict[str, Any]]] = {}
    malformed: list[dict[str, Any]] = []
    for item in raw_answers:
        if not isinstance(item, dict) or not isinstance(item.get("question_key"), str):
            malformed.append({"question_key": None, "valid": False, "errors": ["INVALID_ENVELOPE"]})
            continue
        occurrences.setdefault(str(item["question_key"]), []).append(item)

    results: list[dict[str, Any]] = []
    for key, question in expected.items():
        items = occurrences.get(key, [])
        if not items:
            results.append({"question_key": key, "valid": False, "errors": ["MISSING_ANSWER"]})
            continue
        if len(items) > 1:
            results.append({"question_key": key, "valid": False, "errors": ["DUPLICATE_ANSWER"]})
            continue
        results.append(
            {
                "question_key": key,
                "valid": not (errors := _validate_answer(items[0], question, input_data)),
                "errors": errors,
            }
        )
    for key in sorted(set(occurrences) - set(expected)):
        results.append({"question_key": key, "valid": False, "errors": ["UNKNOWN_QUESTION"]})
    results.extend(malformed)
    confidence = value.get("model_reported_confidence")
    aggregate_errors: list[str] = []
    if not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        aggregate_errors.append("MISSING_RATIONALE")
    elif len(value["rationale"]) > 2_000:
        aggregate_errors.append("RATIONALE_TOO_LARGE")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        aggregate_errors.append("INVALID_CONFIDENCE")
    if value.get("abstention") is not None and (
        not isinstance(value.get("abstention"), str) or len(str(value["abstention"])) > 200
    ):
        aggregate_errors.append("INVALID_ABSTENTION")
    valid_count = sum(item.get("valid") is True for item in results)
    complete = (
        len(raw_answers) == len(expected)
        and not malformed
        and not (set(occurrences) - set(expected))
    )
    all_valid = complete and valid_count == len(expected) and not aggregate_errors
    validated_answers = {
        item["question_key"]: next(
            answer for answer in raw_answers if answer.get("question_key") == item["question_key"]
        )
        for item in results
        if item.get("valid") is True and item.get("question_key") in expected
    }
    answer_values = {
        key: str(item["answer"])
        for key, item in validated_answers.items()
        if item.get("status") == AIRobAnswerStatus.PROPOSED_ANSWER.value
    }
    domain_suggestions: dict[str, str | None] = {}
    if all_valid:
        for domain in definition["domains"]:
            domain_suggestions[domain["key"]] = suggest_domain_judgment(
                definition, domain["key"], answer_values
            )
    overall = None
    if domain_suggestions and all(value is not None for value in domain_suggestions.values()):
        overall = suggest_overall_judgment(
            definition,
            {key: value for key, value in domain_suggestions.items() if value is not None},
        )
    return {
        "validator_version": "ai-rob-validator-1",
        "aggregate_valid": all_valid,
        "acceptance_ready": all_valid,
        "complete": complete,
        "requested_question_count": len(expected),
        "returned_answer_count": len(raw_answers),
        "valid_answer_count": valid_count,
        "aggregate_errors": aggregate_errors,
        "answer_results": results,
        "domain_suggestions": domain_suggestions,
        "overall_suggestion": overall,
    }


def _validate_answer(
    item: dict[str, Any], question: dict[str, Any], input_data: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    allowed = {"question_key", "status", "answer", "evidence", "confidence", "note"}
    if set(item) - allowed:
        errors.append("UNEXPECTED_PROPERTY")
    try:
        status = AIRobAnswerStatus(str(item.get("status", "")))
    except ValueError:
        return [*errors, "INVALID_STATUS"]
    confidence = item.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        errors.append("INVALID_CONFIDENCE")
    note = item.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 1_000):
        errors.append("INVALID_NOTE")
    evidence = item.get("evidence")
    if status is AIRobAnswerStatus.ABSTAIN:
        if item.get("answer") is not None:
            errors.append("ABSTAIN_WITH_ANSWER")
        if evidence not in ([], None):
            errors.append("ABSTAIN_WITH_EVIDENCE")
        return errors
    answer = str(item.get("answer", "")).strip().upper()
    if answer not in set(question.get("allowed_answers", [])):
        errors.append("ANSWER_NOT_ALLOWED")
    if not isinstance(evidence, list) or not evidence:
        errors.append("MISSING_EVIDENCE")
    else:
        errors.extend(_evidence_errors(evidence, input_data))
    return list(dict.fromkeys(errors))


def _evidence_errors(evidence: list[Any], input_data: dict[str, Any]) -> list[str]:
    chunks = {
        str(item.get("chunk_id")): item
        for item in input_data.get("chunks", [])
        if isinstance(item, dict)
    }
    documents = {
        str(item.get("document_id")): item
        for item in input_data.get("source_documents", [])
        if isinstance(item, dict)
    }
    errors: list[str] = []
    for span in evidence:
        if not isinstance(span, dict):
            errors.append("INVALID_EVIDENCE")
            continue
        document_id = str(span.get("document_id", ""))
        source = documents.get(document_id)
        if source is None:
            errors.append("WRONG_DOCUMENT")
            continue
        if str(span.get("document_version_id", "")) != str(source.get("document_version_id", "")):
            errors.append("WRONG_DOCUMENT_VERSION")
        chunk = chunks.get(str(span.get("chunk_id", "")))
        if chunk is None:
            errors.append("INVALID_CHUNK_REFERENCE")
            continue
        if str(chunk.get("document_id")) != document_id:
            errors.append("WRONG_DOCUMENT")
        if str(span.get("source_block_id", "")) != str(chunk.get("source_block_id", "")):
            errors.append("WRONG_SOURCE_BLOCK")
        if span.get("page") != chunk.get("page"):
            errors.append("PAGE_MISMATCH")
        if span.get("section") != chunk.get("section"):
            errors.append("SECTION_MISMATCH")
        quote = span.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            errors.append("MISSING_EVIDENCE_QUOTE")
            continue
        if len(quote) > 500:
            errors.append("EVIDENCE_TOO_LARGE")
            continue
        if normalize_evidence_text(quote) not in normalize_evidence_text(
            str(chunk.get("text", ""))
        ):
            errors.append("QUOTE_MISMATCH")
    return list(dict.fromkeys(errors))


def evaluate_rob_case(
    prediction: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    reference_answers: dict[str, str],
    reference_domains: dict[str, str] | None = None,
    reference_overall: str | None = None,
) -> dict[str, Any]:
    if not prediction or not validation or not validation.get("aggregate_valid"):
        return {
            "classification": AIRobMatchClass.INVALID_PROPOSAL.value,
            "signalling_agreement": False,
            "domain_agreement": False,
            "overall_agreement": False,
            "evidence_grounding_valid": False,
            "abstention": False,
            "dangerous_underestimation": False,
        }
    answers = {
        str(item.get("question_key")): str(item.get("answer"))
        for item in prediction.get("answers", [])
        if item.get("status") == AIRobAnswerStatus.PROPOSED_ANSWER.value
    }
    abstained = any(
        item.get("status") == AIRobAnswerStatus.ABSTAIN.value
        for item in prediction.get("answers", [])
    )
    signalling_agreement = answers == reference_answers
    suggested_domains = validation.get("domain_suggestions") or {}
    domain_agreement = reference_domains is None or suggested_domains == reference_domains
    overall = validation.get("overall_suggestion")
    overall_agreement = reference_overall is None or overall == reference_overall
    classification = (
        AIRobMatchClass.AGREEMENT.value
        if signalling_agreement and domain_agreement and overall_agreement
        else AIRobMatchClass.AI_ABSTAIN.value
        if abstained
        else AIRobMatchClass.DISAGREEMENT.value
    )
    return {
        "classification": classification,
        "signalling_agreement": signalling_agreement,
        "domain_agreement": domain_agreement,
        "overall_agreement": overall_agreement,
        "evidence_grounding_valid": True,
        "abstention": abstained,
        "dangerous_underestimation": False,
    }


def aggregate_rob_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    signalling = sum(bool(row.get("signalling_agreement")) for row in rows)
    domains = sum(bool(row.get("domain_agreement")) for row in rows)
    overall = sum(bool(row.get("overall_agreement")) for row in rows)
    grounded = sum(bool(row.get("evidence_grounding_valid")) for row in rows)
    abstentions = sum(bool(row.get("abstention")) for row in rows)
    dangerous = sum(bool(row.get("dangerous_underestimation")) for row in rows)
    confusion: dict[str, int] = {}
    for row in rows:
        key = str(row.get("classification", "INVALID_PROPOSAL"))
        confusion[key] = confusion.get(key, 0) + 1
    return {
        "case_count": total,
        "signalling_question_agreement": signalling / total if total else None,
        "domain_level_agreement": domains / total if total else None,
        "overall_agreement": overall / total if total else None,
        "evidence_grounding_validity": grounded / total if total else None,
        "abstention_rate": abstentions / total if total else None,
        "dangerous_underestimation_count": dangerous,
        "high_risk_error_count": dangerous,
        "confusion_counts": confusion,
        "calibration": {"status": "DESCRIPTIVE_ONLY", "bins": []},
        "coverage": (total - abstentions) / total if total else None,
        "threshold_label": "HYPOTHETICAL EVALUATION ONLY",
    }
