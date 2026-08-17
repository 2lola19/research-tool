from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.ai.domain import content_hash
from backend.app.ai.screening_domain import AIScreeningMode, AIScreeningSuggestion
from backend.app.documents.domain import DocumentBlock, DocumentBlockType


class FullTextDocumentRole(StrEnum):
    PRIMARY_FULL_TEXT = "PRIMARY_FULL_TEXT"
    SUPPLEMENT = "SUPPLEMENT"
    APPENDIX = "APPENDIX"
    OTHER_SUPPORTING_DOCUMENT = "OTHER_SUPPORTING_DOCUMENT"


class FullTextReadiness(StrEnum):
    READY = "READY"
    BLOCKED_NO_DOCUMENT = "BLOCKED_NO_DOCUMENT"
    BLOCKED_PROCESSING = "BLOCKED_PROCESSING"
    BLOCKED_NO_TEXT = "BLOCKED_NO_TEXT"
    BLOCKED_STALE_DOCUMENT = "BLOCKED_STALE_DOCUMENT"
    BLOCKED_PROTOCOL = "BLOCKED_PROTOCOL"
    BLOCKED_ASSIGNMENT = "BLOCKED_ASSIGNMENT"
    BLOCKED_OTHER = "BLOCKED_OTHER"


class MissingInformationReason(StrEnum):
    FULL_TEXT_INCOMPLETE = "FULL_TEXT_INCOMPLETE"
    SUPPLEMENT_REQUIRED = "SUPPLEMENT_REQUIRED"
    POPULATION_UNCLEAR = "POPULATION_UNCLEAR"
    INTERVENTION_UNCLEAR = "INTERVENTION_UNCLEAR"
    COMPARATOR_UNCLEAR = "COMPARATOR_UNCLEAR"
    OUTCOME_UNCLEAR = "OUTCOME_UNCLEAR"
    STUDY_DESIGN_UNCLEAR = "STUDY_DESIGN_UNCLEAR"
    PUBLICATION_TYPE_UNCLEAR = "PUBLICATION_TYPE_UNCLEAR"
    LANGUAGE_OR_TRANSLATION_LIMITATION = "LANGUAGE_OR_TRANSLATION_LIMITATION"
    PARSER_LIMITATION = "PARSER_LIMITATION"
    TABLE_OR_FIGURE_REQUIRED = "TABLE_OR_FIGURE_REQUIRED"
    RELATED_REPORT_REQUIRED = "RELATED_REPORT_REQUIRED"
    PROTOCOL_AMBIGUITY = "PROTOCOL_AMBIGUITY"
    OTHER = "OTHER"


class FullTextReferenceStandard(StrEnum):
    ADJUDICATED_FULL_TEXT = "ADJUDICATED_FULL_TEXT"
    REVIEWER_CONSENSUS = "REVIEWER_CONSENSUS"
    FINAL_HUMAN_FULL_TEXT = "FINAL_HUMAN_FULL_TEXT"
    CURATED_DATASET = "CURATED_DATASET"


class FullTextErrorCategory(StrEnum):
    POPULATION_MISUNDERSTANDING = "POPULATION_MISUNDERSTANDING"
    INTERVENTION_MISUNDERSTANDING = "INTERVENTION_MISUNDERSTANDING"
    COMPARATOR_MISUNDERSTANDING = "COMPARATOR_MISUNDERSTANDING"
    OUTCOME_MISUNDERSTANDING = "OUTCOME_MISUNDERSTANDING"
    DESIGN_MISUNDERSTANDING = "DESIGN_MISUNDERSTANDING"
    PUBLICATION_TYPE_MISUNDERSTANDING = "PUBLICATION_TYPE_MISUNDERSTANDING"
    WRONG_PROTOCOL_CRITERION = "WRONG_PROTOCOL_CRITERION"
    MISSING_ELIGIBILITY_EVIDENCE = "MISSING_ELIGIBILITY_EVIDENCE"
    FABRICATED_EVIDENCE = "FABRICATED_EVIDENCE"
    PARSER_OMISSION = "PARSER_OMISSION"
    SUPPLEMENT_MISSING = "SUPPLEMENT_MISSING"
    WRONG_RELATED_REPORT = "WRONG_RELATED_REPORT"
    MIXED_POPULATION = "MIXED_POPULATION"
    SECTION_CONTEXT_MISUNDERSTANDING = "SECTION_CONTEXT_MISUNDERSTANDING"
    OTHER = "OTHER"


class EvidenceValidationIssue(StrEnum):
    INVALID_CHUNK_REFERENCE = "INVALID_CHUNK_REFERENCE"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    WRONG_DOCUMENT = "WRONG_DOCUMENT"
    WRONG_DOCUMENT_VERSION = "WRONG_DOCUMENT_VERSION"
    PAGE_MISMATCH = "PAGE_MISMATCH"
    SECTION_MISMATCH = "SECTION_MISMATCH"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    EVIDENCE_TOO_LARGE = "EVIDENCE_TOO_LARGE"
    REFERENCE_LIST_ONLY = "REFERENCE_LIST_ONLY"


@dataclass(frozen=True, slots=True)
class PreparedFullTextInput:
    chunks: tuple[dict[str, Any], ...]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, str], ...]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str


@dataclass(frozen=True, slots=True)
class AIFullTextProposalLink:
    id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    article_id: UUID
    assignment_id: UUID
    protocol_version_id: UUID
    document_id: UUID
    document_version_id: UUID
    processing_run_id: UUID
    document_role: FullTextDocumentRole
    parser_name: str
    parser_version: str
    protocol_content_hash: str
    exclusion_criteria_hash: str
    citation_content_hash: str
    document_content_hash: str
    parsed_representation_hash: str
    selected_text_hash: str
    chunk_manifest_hash: str
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, str], ...]
    selection_method: str
    task_definition_version: int
    assistance_mode: AIScreeningMode
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FullTextEvaluationDataset:
    id: UUID
    organization_id: UUID
    review_id: UUID
    logical_key: str
    version: int
    protocol_version_id: UUID
    name: str
    reference_standard: FullTextReferenceStandard
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FullTextEvaluationCase:
    id: UUID
    dataset_id: UUID
    organization_id: UUID
    review_id: UUID
    article_id: UUID
    document_id: UUID
    document_version_id: UUID
    processing_run_id: UUID
    ordinal: int
    reference_decision: str
    reference_exclusion_criterion_id: str | None
    reference_source_type: FullTextReferenceStandard
    reference_source_id: UUID | None
    evidence_snapshot_hash: str


def normalize_evidence_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def prepare_full_text_input(
    document_id: UUID,
    blocks: list[DocumentBlock],
    *,
    maximum_characters: int = 12_000,
    maximum_chunks: int = 40,
    characters_per_chunk: int = 3_000,
) -> PreparedFullTextInput:
    """Create a bounded, ordered, reconstructable structured-document snapshot."""
    if maximum_characters < 1 or maximum_chunks < 1 or characters_per_chunk < 1:
        raise ValueError("full-text input limits must be positive")
    candidates: list[dict[str, Any]] = []
    for block in sorted(blocks, key=lambda item: (item.block_order, item.block_id)):
        text = normalize_evidence_text(block.text)
        if not text:
            continue
        parts = [
            text[index : index + characters_per_chunk]
            for index in range(0, len(text), characters_per_chunk)
        ]
        for part_index, part in enumerate(parts, start=1):
            scoped_id = f"{document_id}:{block.block_id}:p{part_index}"
            candidates.append(
                {
                    "chunk_id": scoped_id,
                    "source_block_id": str(block.id),
                    "parser_block_id": block.block_id,
                    "block_type": block.block_type.value,
                    "page": block.page_number,
                    "section_path": list(block.section_path),
                    "section": block.section_path[-1] if block.section_path else None,
                    "table_id": block.table_id,
                    "figure_id": block.figure_id,
                    "text": part,
                    "text_hash": content_hash(part),
                }
            )
    selected: list[dict[str, Any]] = []
    omitted: list[dict[str, str]] = []
    used = 0
    for chunk in candidates:
        size = len(str(chunk["text"]))
        if len(selected) < maximum_chunks and used + size <= maximum_characters:
            selected.append(chunk)
            used += size
        else:
            omitted.append(
                {"chunk_id": str(chunk["chunk_id"]), "text_hash": str(chunk["text_hash"])}
            )
    manifest = [
        {
            "chunk_id": item["chunk_id"],
            "text_hash": item["text_hash"],
            "page": item["page"],
            "section": item["section"],
            "block_type": item["block_type"],
        }
        for item in candidates
    ]
    return PreparedFullTextInput(
        chunks=tuple(selected),
        selected_chunk_ids=tuple(str(item["chunk_id"]) for item in selected),
        omitted_chunks=tuple(omitted),
        selection_method="ordered-structured-bounded-v1",
        chunk_manifest_hash=content_hash(manifest),
        selected_text_hash=content_hash(
            [{"chunk_id": item["chunk_id"], "text_hash": item["text_hash"]} for item in selected]
        ),
    )


def validate_full_text_output(
    value: dict[str, Any], input_data: dict[str, Any]
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    suggestion = value.get("suggestion")
    if suggestion not in {item.value for item in AIScreeningSuggestion}:
        errors.append({"code": "INVALID_SUGGESTION", "message": "unknown suggestion"})

    criterion_ids = value.get("exclusion_criterion_ids")
    allowed_criteria = {
        str(item.get("id"))
        for item in input_data.get("exclusion_criteria", [])
        if isinstance(item, dict) and item.get("id") is not None
    }
    if not isinstance(criterion_ids, list) or not all(
        isinstance(item, str) for item in criterion_ids
    ):
        errors.append({"code": "INVALID_CRITERIA", "message": "criterion IDs must be strings"})
        criterion_ids = []
    elif any(item not in allowed_criteria for item in criterion_ids):
        errors.append({"code": "UNKNOWN_CRITERION", "message": "criterion is not pinned"})

    rationale = value.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 2_000:
        errors.append({"code": "INVALID_RATIONALE", "message": "concise rationale required"})
    confidence = value.get("model_reported_confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        errors.append({"code": "INVALID_CONFIDENCE", "message": "confidence must be 0 through 1"})

    missing = value.get("missing_information")
    allowed_missing = {item.value for item in MissingInformationReason}
    if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
        errors.append({"code": "INVALID_MISSING_INFORMATION", "message": "invalid missing reasons"})
        missing = []
    elif any(item not in allowed_missing for item in missing):
        errors.append({"code": "UNKNOWN_MISSING_INFORMATION", "message": "unknown missing reason"})

    uncertainty = value.get("uncertainty_reason")
    if suggestion in {"MAYBE", "ABSTAIN"} and (
        not isinstance(uncertainty, str) or not uncertainty.strip() or not missing
    ):
        errors.append(
            {
                "code": "UNCERTAINTY_REQUIRED",
                "message": "uncertainty reason and category required",
            }
        )
    if suggestion == "INCLUDE" and criterion_ids:
        errors.append(
            {"code": "INCLUDE_HAS_EXCLUSION_CRITERIA", "message": "include cannot exclude"}
        )
    if suggestion == "EXCLUDE" and not criterion_ids:
        errors.append({"code": "EXCLUDE_MISSING_CRITERIA", "message": "exclude requires criterion"})

    identity = input_data.get("document_identity", {})
    expected_document = str(identity.get("document_id", input_data.get("document_id", "")))
    expected_version = str(
        identity.get("document_version_id", input_data.get("document_version_id", ""))
    )
    chunks = {
        str(item.get("chunk_id")): item
        for item in input_data.get("chunks", [])
        if isinstance(item, dict) and item.get("chunk_id") is not None
    }
    evidence = value.get("evidence")
    valid_substantive = 0
    if not isinstance(evidence, list):
        errors.append({"code": "INVALID_EVIDENCE", "message": "evidence must be a list"})
        evidence = []
    for item in evidence:
        if not isinstance(item, dict):
            errors.append({"code": "INVALID_EVIDENCE", "message": "evidence must be objects"})
            continue
        if str(item.get("document_id", "")) != expected_document:
            errors.append({"code": "WRONG_DOCUMENT", "message": "evidence document does not match"})
        if str(item.get("document_version_id", "")) != expected_version:
            errors.append(
                {"code": "WRONG_DOCUMENT_VERSION", "message": "document version does not match"}
            )
        chunk = chunks.get(str(item.get("chunk_id", "")))
        if chunk is None:
            errors.append({"code": "INVALID_CHUNK_REFERENCE", "message": "unknown selected chunk"})
            continue
        quote = item.get("quoted_text")
        if not isinstance(quote, str) or not quote.strip():
            errors.append({"code": "MISSING_EVIDENCE_QUOTE", "message": "quote required"})
        elif len(quote) > 500:
            errors.append({"code": "EVIDENCE_TOO_LARGE", "message": "quote exceeds 500 characters"})
        elif normalize_evidence_text(quote) not in normalize_evidence_text(
            str(chunk.get("text", ""))
        ):
            errors.append({"code": "QUOTE_MISMATCH", "message": "quote is not in the cited chunk"})
        expected_page = chunk.get("page")
        if item.get("page") != expected_page:
            errors.append({"code": "PAGE_MISMATCH", "message": "page metadata does not match"})
        expected_section = chunk.get("section")
        if item.get("section") != expected_section:
            errors.append(
                {"code": "SECTION_MISMATCH", "message": "section metadata does not match"}
            )
        if chunk.get("block_type") != DocumentBlockType.REFERENCE.value:
            valid_substantive += 1
    if suggestion == "EXCLUDE" and not evidence:
        errors.append({"code": "EXCLUDE_MISSING_EVIDENCE", "message": "exclude requires evidence"})
    if suggestion == "EXCLUDE" and evidence and valid_substantive == 0:
        errors.append(
            {"code": "REFERENCE_LIST_ONLY", "message": "reference-list text cannot alone exclude"}
        )
    return errors
