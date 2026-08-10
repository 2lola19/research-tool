from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from enum import StrEnum
from uuid import UUID

from backend.app.citations.domain import Article


class MatchReason(StrEnum):
    DOI_EXACT = "DOI_EXACT"
    PMID_EXACT = "PMID_EXACT"
    TITLE_YEAR_EXACT = "TITLE_YEAR_EXACT"
    TITLE_FUZZY = "TITLE_FUZZY"


class DedupDecisionKind(StrEnum):
    CONFIRMED_DUPLICATE = "CONFIRMED_DUPLICATE"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class CandidateMatch:
    left_article_id: UUID
    right_article_id: UUID
    reason: MatchReason
    score: float


@dataclass(frozen=True, slots=True)
class DeduplicationRun:
    id: UUID
    organization_id: UUID
    review_id: UUID
    algorithm_version: str
    input_hash: str
    article_count: int
    candidate_count: int
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    id: UUID
    deduplication_run_id: UUID
    organization_id: UUID
    review_id: UUID
    left_article_id: UUID
    right_article_id: UUID
    reason: MatchReason
    score: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DeduplicationDecision:
    id: UUID
    candidate_id: UUID
    organization_id: UUID
    review_id: UUID
    decision: DedupDecisionKind
    retained_article_id: UUID | None
    decided_by_user_id: UUID
    reason: str | None
    decided_at: datetime


def normalize_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def deduplication_input_hash(articles: list[Article]) -> str:
    snapshot = [
        {
            "id": str(item.id),
            "doi": item.doi,
            "pmid": item.pmid,
            "title": normalize_title(item.title),
            "year": item.publication_year,
        }
        for item in sorted(articles, key=lambda article: str(article.id))
    ]
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def find_duplicate_candidates(
    articles: list[Article], *, fuzzy_threshold: float = 0.9
) -> list[CandidateMatch]:
    candidates: list[CandidateMatch] = []
    ordered = sorted(articles, key=lambda article: str(article.id))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            match = _compare(left, right, fuzzy_threshold)
            if match is not None:
                candidates.append(match)
    return candidates


def _compare(left: Article, right: Article, fuzzy_threshold: float) -> CandidateMatch | None:
    if left.doi is not None and left.doi == right.doi:
        return CandidateMatch(left.id, right.id, MatchReason.DOI_EXACT, 1.0)
    if left.pmid is not None and left.pmid == right.pmid:
        return CandidateMatch(left.id, right.id, MatchReason.PMID_EXACT, 1.0)
    left_title = normalize_title(left.title)
    right_title = normalize_title(right.title)
    if (
        left_title == right_title
        and left.publication_year is not None
        and left.publication_year == right.publication_year
    ):
        return CandidateMatch(left.id, right.id, MatchReason.TITLE_YEAR_EXACT, 0.98)
    score = SequenceMatcher(None, left_title, right_title, autojunk=False).ratio()
    if score >= fuzzy_threshold:
        return CandidateMatch(left.id, right.id, MatchReason.TITLE_FUZZY, round(score, 6))
    return None
