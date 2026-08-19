from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.ai.domain import content_hash
from backend.app.ai.extraction_domain import ExtractionSource, prepare_extraction_input
from backend.app.ai.full_text_domain import normalize_evidence_text


class AICertaintyReadiness(StrEnum):
    READY = "READY"
    BLOCKED_NO_ASSESSMENT = "BLOCKED_NO_ASSESSMENT"
    BLOCKED_NOT_OWNER = "BLOCKED_NOT_OWNER"
    BLOCKED_SUBMITTED = "BLOCKED_SUBMITTED"
    BLOCKED_FRAMEWORK = "BLOCKED_FRAMEWORK"
    BLOCKED_SOURCE_SCOPE = "BLOCKED_SOURCE_SCOPE"
    BLOCKED_DOCUMENT_PROCESSING = "BLOCKED_DOCUMENT_PROCESSING"
    BLOCKED_NO_PARSED_TEXT = "BLOCKED_NO_PARSED_TEXT"
    BLOCKED_OTHER = "BLOCKED_OTHER"


class AICertaintyReviewAction(StrEnum):
    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class AICertaintyAccessType(StrEnum):
    HUMAN_REVIEW = "HUMAN_REVIEW"


class AICertaintyReferenceStandard(StrEnum):
    HUMAN_RATIONALE = "HUMAN_RATIONALE"
    CURATED_GOLD = "CURATED_GOLD"
    FINAL_CANONICAL = "FINAL_CANONICAL"


class AICertaintyErrorCategory(StrEnum):
    WRONG_FRAMEWORK = "WRONG_FRAMEWORK"
    WRONG_ASSESSMENT = "WRONG_ASSESSMENT"
    WRONG_DOMAIN = "WRONG_DOMAIN"
    UNSUPPORTED_DOWNGRADE = "UNSUPPORTED_DOWNGRADE"
    UNSUPPORTED_UPGRADE = "UNSUPPORTED_UPGRADE"
    WRONG_MAGNITUDE = "WRONG_MAGNITUDE"
    UNSUPPORTED_FINAL_DECISION = "UNSUPPORTED_FINAL_DECISION"
    UNSUPPORTED_THRESHOLD = "UNSUPPORTED_THRESHOLD"
    PUBLICATION_BIAS_INFERENCE = "PUBLICATION_BIAS_INFERENCE"
    FABRICATED_EVIDENCE = "FABRICATED_EVIDENCE"
    WRONG_DOCUMENT = "WRONG_DOCUMENT"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class PreparedCertaintyInput:
    chunks: tuple[dict[str, Any], ...]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, Any], ...]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str


@dataclass(frozen=True, slots=True)
class AICertaintyPolicy:
    id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    maximum_batch_size: int
    created_by_user_id: UUID


@dataclass(frozen=True, slots=True)
class AICertaintyProposalLink:
    id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    assessment_id: UUID
    outcome_version_id: UUID
    outcome_version_hash: str
    framework_version_id: UUID
    framework_version_hash: str
    assessment_snapshot_hash: str
    evidence_profile_hash: str
    task_definition_version: int
    source_manifest: list[dict[str, Any]]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, Any], ...]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str
    validation_results: dict[str, Any]


def prepare_certainty_input(
    framework_definition: dict[str, Any],
    sources: list[ExtractionSource],
    *,
    maximum_characters: int = 24_000,
    maximum_chunks: int = 80,
) -> PreparedCertaintyInput:
    """Select bounded evidence deterministically; the provider has no retrieval authority."""
    fields = [
        {
            "key": "evidence_summary",
            "label": "certainty evidence summary",
            "description": "Relevant evidence for a human certainty rationale.",
            "field_type": "TEXT",
            "required": True,
        },
        *[
            {
                "key": f"domain:{domain['key']}",
                "label": domain["label"],
                "description": domain.get("guidance"),
                "field_type": "TEXT",
                "required": False,
            }
            for domain in framework_definition.get("domains", [])
            if isinstance(domain, dict) and domain.get("key")
        ],
    ]
    prepared = prepare_extraction_input(
        fields,
        sources,
        maximum_characters=maximum_characters,
        maximum_chunks=maximum_chunks,
    )
    return PreparedCertaintyInput(
        chunks=prepared.chunks,
        selected_chunk_ids=prepared.selected_chunk_ids,
        omitted_chunks=prepared.omitted_chunks,
        selection_method=prepared.selection_method,
        chunk_manifest_hash=prepared.chunk_manifest_hash,
        selected_text_hash=prepared.selected_text_hash,
    )


def certainty_source_manifest(sources: list[ExtractionSource]) -> list[dict[str, Any]]:
    return [
        {
            "article_id": str(source.document.article_id),
            "document_id": str(source.document.id),
            "document_version_id": str(source.document.id),
            "document_role": source.role.value,
            "document_content_hash": source.document.sha256
            or content_hash(
                {
                    "document_id": str(source.document.id),
                    "source_identifier": source.document.source_identifier,
                }
            ),
            "processing_run_id": str(source.processing.id),
            "parser_name": source.processing.parser_name,
            "parser_version": source.processing.parser_version,
            "parsed_content_hash": content_hash(
                [
                    {
                        "block_id": block.block_id,
                        "block_type": block.block_type.value,
                        "order": block.block_order,
                        "page": block.page_number,
                        "section_path": block.section_path,
                        "table_id": block.table_id,
                        "figure_id": block.figure_id,
                        "text_hash": content_hash(block.text),
                    }
                    for block in source.blocks
                ]
            ),
            "block_count": len(source.blocks),
        }
        for source in sources
    ]


def validate_certainty_output(
    value: dict[str, Any], input_data: dict[str, Any]
) -> list[dict[str, str]]:
    """Validate bounded suggestions without calculating or accepting certainty."""
    errors: list[dict[str, str]] = []
    if str(value.get("assessment_id", "")) != str(input_data.get("assessment_id", "")):
        errors.append({"code": "WRONG_ASSESSMENT", "message": "assessment does not match"})
    if str(value.get("framework_version_id", "")) != str(
        input_data.get("framework_version_id", "")
    ):
        errors.append({"code": "WRONG_FRAMEWORK", "message": "framework version does not match"})
    if str(value.get("outcome_version_id", "")) != str(input_data.get("outcome_version_id", "")):
        errors.append({"code": "WRONG_OUTCOME", "message": "outcome version does not match"})

    forbidden = {
        "candidate_certainty",
        "final_certainty",
        "overall_judgment",
        "starting_certainty",
        "threshold",
        "upgrade_decision",
        "downgrade_decision",
    }
    for key in sorted(set(value) & forbidden):
        errors.append(
            {
                "code": "UNSUPPORTED_SCIENTIFIC_DECISION",
                "message": f"AI cannot provide {key}",
            }
        )

    rationale = value.get("evidence_summary")
    if rationale is not None and (not isinstance(rationale, str) or len(rationale.strip()) > 4_000):
        errors.append(
            {"code": "INVALID_EVIDENCE_SUMMARY", "message": "summary must be bounded text"}
        )
    confidence = value.get("model_reported_confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        errors.append(
            {"code": "INVALID_CONFIDENCE", "message": "confidence must be from 0 through 1"}
        )

    abstention = value.get("abstention")
    if abstention is not None and (
        not isinstance(abstention, str) or not abstention.strip() or len(abstention) > 500
    ):
        errors.append({"code": "INVALID_ABSTENTION", "message": "abstention must be bounded text"})
    suggestions = value.get("domain_suggestions")
    if not isinstance(suggestions, list):
        errors.append(
            {"code": "INVALID_DOMAIN_SUGGESTIONS", "message": "domain_suggestions must be a list"}
        )
        suggestions = []
    if len(suggestions) > len(input_data.get("framework_definition", {}).get("domains", [])):
        errors.append(
            {
                "code": "TOO_MANY_DOMAIN_SUGGESTIONS",
                "message": "domain suggestions exceed framework domains",
            }
        )

    if abstention and suggestions:
        errors.append(
            {
                "code": "ABSTENTION_HAS_SUGGESTIONS",
                "message": "abstention cannot include domain suggestions",
            }
        )
    if not abstention and not suggestions and not str(rationale or "").strip():
        errors.append(
            {
                "code": "EMPTY_NON_ABSTAINING_OUTPUT",
                "message": "output needs a summary or domain suggestion",
            }
        )

    framework_domains = {
        str(item.get("key")): item
        for item in input_data.get("framework_definition", {}).get("domains", [])
        if isinstance(item, dict) and item.get("key")
    }
    seen: set[str] = set()
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            errors.append(
                {"code": "INVALID_DOMAIN_SUGGESTION", "message": "suggestion must be an object"}
            )
            continue
        allowed = {
            "domain_key",
            "direction",
            "judgment",
            "magnitude",
            "rationale",
            "evidence",
            "confidence",
        }
        for key in sorted(set(suggestion) - allowed):
            errors.append({"code": "UNEXPECTED_DOMAIN_PROPERTY", "message": key})
        key = str(suggestion.get("domain_key", ""))
        domain = framework_domains.get(key)
        if domain is None:
            errors.append({"code": "WRONG_DOMAIN", "message": "domain is not in the framework"})
            continue
        if key in seen:
            errors.append(
                {"code": "DUPLICATE_DOMAIN", "message": "domain suggestion is duplicated"}
            )
        seen.add(key)
        direction = str(suggestion.get("direction", ""))
        expected_direction = str(domain.get("direction", ""))
        if direction != expected_direction:
            errors.append(
                {
                    "code": "UNSUPPORTED_DOWNGRADE"
                    if direction == "DOWNGRADE"
                    else "UNSUPPORTED_UPGRADE",
                    "message": "domain direction does not match the immutable framework",
                }
            )
        choices = [item for item in domain.get("choices", []) if isinstance(item, dict)]
        choice = next(
            (item for item in choices if item.get("value") == suggestion.get("judgment")), None
        )
        if choice is None:
            errors.append({"code": "UNSUPPORTED_JUDGMENT", "message": "judgment is not allowed"})
        else:
            try:
                magnitude = int(str(suggestion.get("magnitude")))
            except (TypeError, ValueError):
                errors.append(
                    {"code": "WRONG_MAGNITUDE", "message": "magnitude must be an integer"}
                )
            else:
                if magnitude != int(str(choice.get("magnitude", -1))):
                    errors.append(
                        {
                            "code": "WRONG_MAGNITUDE",
                            "message": "magnitude does not match the choice",
                        }
                    )
        item_rationale = suggestion.get("rationale")
        if (
            not isinstance(item_rationale, str)
            or not item_rationale.strip()
            or len(item_rationale) > 4_000
        ):
            errors.append(
                {
                    "code": "INVALID_DOMAIN_RATIONALE",
                    "message": "domain rationale must be bounded text",
                }
            )
        evidence = suggestion.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(
                {
                    "code": "MISSING_DOMAIN_EVIDENCE",
                    "message": "domain suggestions require evidence",
                }
            )
        else:
            errors.extend(_evidence_errors(evidence, input_data))
        suggestion_confidence = suggestion.get("confidence")
        if suggestion_confidence is not None and (
            isinstance(suggestion_confidence, bool)
            or not isinstance(suggestion_confidence, (int, float))
            or not 0 <= suggestion_confidence <= 1
        ):
            errors.append(
                {"code": "INVALID_DOMAIN_CONFIDENCE", "message": "domain confidence is invalid"}
            )

    summary_evidence = value.get("evidence_summary_evidence")
    if not isinstance(summary_evidence, list):
        errors.append(
            {"code": "INVALID_SUMMARY_EVIDENCE", "message": "summary evidence must be a list"}
        )
    elif str(rationale or "").strip():
        if not summary_evidence:
            errors.append(
                {"code": "MISSING_SUMMARY_EVIDENCE", "message": "summary requires evidence"}
            )
        else:
            errors.extend(_evidence_errors(summary_evidence, input_data))
    elif summary_evidence:
        errors.extend(_evidence_errors(summary_evidence, input_data))
    return _dedupe_errors(errors)


def certainty_evaluation_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    valid = sum(bool(item.get("validation_valid")) for item in cases)
    abstentions = sum(bool(item.get("abstention")) for item in cases)
    references = [item for item in cases if item.get("reference_type")]
    agreement = sum(bool(item.get("reference_match")) for item in references)
    unsupported = sum(
        sum(
            str(category)
            in {
                AICertaintyErrorCategory.UNSUPPORTED_DOWNGRADE.value,
                AICertaintyErrorCategory.UNSUPPORTED_UPGRADE.value,
                AICertaintyErrorCategory.WRONG_MAGNITUDE.value,
            }
            for category in item.get("error_categories", [])
        )
        for item in cases
    )
    high_risk = sum(
        bool(
            set(item.get("error_categories", []))
            & {
                AICertaintyErrorCategory.UNSUPPORTED_FINAL_DECISION.value,
                AICertaintyErrorCategory.UNSUPPORTED_THRESHOLD.value,
                AICertaintyErrorCategory.PUBLICATION_BIAS_INFERENCE.value,
            }
        )
        for item in cases
    )
    return {
        "case_count": total,
        "evidence_grounding_valid_count": valid,
        "evidence_grounding_rate": valid / total if total else None,
        "abstention_count": abstentions,
        "abstention_rate": abstentions / total if total else None,
        "reference_case_count": len(references),
        "reference_agreement_count": agreement,
        "reference_agreement_rate": agreement / len(references) if references else None,
        "unsupported_adjustment_count": unsupported,
        "high_risk_error_count": high_risk,
        "calibration": {"status": "DESCRIPTIVE_ONLY", "bins": []},
        "threshold_label": "HYPOTHETICAL_EVALUATION_ONLY",
    }


def _evidence_errors(evidence: list[Any], input_data: dict[str, Any]) -> list[dict[str, str]]:
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
    errors: list[dict[str, str]] = []
    for span in evidence:
        if not isinstance(span, dict):
            errors.append(
                {"code": "INVALID_EVIDENCE", "message": "evidence item must be an object"}
            )
            continue
        document_id = str(span.get("document_id", ""))
        source = documents.get(document_id)
        if source is None:
            errors.append(
                {"code": "WRONG_DOCUMENT", "message": "document is not in the pinned source set"}
            )
            continue
        if str(span.get("document_version_id", "")) != str(source.get("document_version_id", "")):
            errors.append(
                {"code": "WRONG_DOCUMENT_VERSION", "message": "document version is not pinned"}
            )
        chunk = chunks.get(str(span.get("chunk_id", "")))
        if chunk is None:
            errors.append(
                {"code": "INVALID_CHUNK_REFERENCE", "message": "chunk is not in the selected input"}
            )
            continue
        if str(chunk.get("document_id")) != document_id:
            errors.append(
                {"code": "WRONG_DOCUMENT", "message": "chunk belongs to another document"}
            )
        if str(span.get("source_block_id", "")) != str(chunk.get("source_block_id", "")):
            errors.append({"code": "WRONG_SOURCE_BLOCK", "message": "source block does not match"})
        if span.get("page") != chunk.get("page"):
            errors.append({"code": "PAGE_MISMATCH", "message": "page does not match"})
        if span.get("section") != chunk.get("section"):
            errors.append({"code": "SECTION_MISMATCH", "message": "section does not match"})
        quote = span.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            errors.append({"code": "MISSING_EVIDENCE_QUOTE", "message": "quote is required"})
        elif len(quote) > 500:
            errors.append(
                {"code": "EVIDENCE_TOO_LARGE", "message": "quote is limited to 500 characters"}
            )
        elif normalize_evidence_text(quote) not in normalize_evidence_text(
            str(chunk.get("text", ""))
        ):
            errors.append({"code": "QUOTE_MISMATCH", "message": "quote is not in the pinned chunk"})
    return errors


def _dedupe_errors(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for error in errors:
        key = (str(error.get("code")), str(error.get("message")))
        if key not in seen:
            seen.add(key)
            result.append(error)
    return result
