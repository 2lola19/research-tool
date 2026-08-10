from datetime import UTC, datetime
from uuid import uuid4

from backend.app.citations.domain import Article
from backend.app.deduplication.domain import (
    MatchReason,
    find_duplicate_candidates,
    normalize_title,
)


def _article(
    title: str, *, doi: str | None = None, pmid: str | None = None, year: int | None = 2024
) -> Article:
    return Article(
        id=uuid4(),
        organization_id=uuid4(),
        review_id=uuid4(),
        title=title,
        abstract=None,
        publication_year=year,
        doi=doi,
        pmid=pmid,
        authors=[],
        journal=None,
        created_at=datetime.now(UTC),
    )


def test_title_normalization_is_case_punctuation_and_accent_insensitive() -> None:
    assert normalize_title("  Café-Based: Trial! ") == "cafe based trial"


def test_exact_identifier_matching_precedes_title_similarity() -> None:
    left = _article("Completely different", doi="10.1/shared")
    right = _article("No title overlap", doi="10.1/shared")
    matches = find_duplicate_candidates([right, left])
    assert len(matches) == 1
    assert matches[0].reason == MatchReason.DOI_EXACT
    assert matches[0].score == 1.0


def test_title_year_exact_and_fuzzy_candidates_are_deterministic() -> None:
    exact_left = _article("A Clinical Trial")
    exact_right = _article("A clinical-trial")
    fuzzy = _article("A clinical trials")
    matches = find_duplicate_candidates([fuzzy, exact_right, exact_left])
    reasons = {match.reason for match in matches}
    assert MatchReason.TITLE_YEAR_EXACT in reasons
    assert MatchReason.TITLE_FUZZY in reasons
    assert matches == find_duplicate_candidates([fuzzy, exact_right, exact_left])
