from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable

from backend.app.citations.domain import CitationFormat, ParsedCitation


class CitationParseError(ValueError):
    pass


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _doi(value: str | None) -> str | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    normalized = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", cleaned, flags=re.I)
    return normalized.casefold()


def _pmid(value: str | None) -> str | None:
    cleaned = _clean(value)
    return cleaned if cleaned is not None and cleaned.isdigit() else None


def _year(value: str | None) -> int | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    match = re.search(r"(?:19|20)\d{2}", cleaned)
    return int(match.group()) if match else None


def _citation(
    *,
    source_key: str | None,
    title: str | None,
    abstract: str | None,
    year: str | None,
    doi: str | None,
    pmid: str | None,
    authors: list[str],
    journal: str | None,
    raw: dict[str, object],
) -> ParsedCitation:
    clean_title = _clean(title)
    if clean_title is None:
        raise CitationParseError("every citation must have a title")
    return ParsedCitation(
        source_key=_clean(source_key),
        title=clean_title,
        abstract=_clean(abstract),
        publication_year=_year(year),
        doi=_doi(doi),
        pmid=_pmid(pmid),
        authors=[item for value in authors if (item := _clean(value)) is not None],
        journal=_clean(journal),
        raw_metadata=raw,
    )


def parse_csv(content: str) -> list[ParsedCitation]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise CitationParseError("CSV header is required")
    rows = []
    for row in reader:
        normalized = {str(key).strip().casefold(): value or "" for key, value in row.items()}
        rows.append(
            _citation(
                source_key=normalized.get("id") or normalized.get("key"),
                title=normalized.get("title"),
                abstract=normalized.get("abstract"),
                year=normalized.get("year"),
                doi=normalized.get("doi"),
                pmid=normalized.get("pmid"),
                authors=(normalized.get("authors") or "").split(";"),
                journal=normalized.get("journal"),
                raw=dict(normalized),
            )
        )
    return rows


def parse_ris(content: str) -> list[ParsedCitation]:
    records: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] = {}
    for line in content.splitlines():
        match = re.match(r"^([A-Z0-9]{2})\s*-\s?(.*)$", line)
        if match is None:
            continue
        tag, value = match.groups()
        current.setdefault(tag, []).append(value)
        if tag == "ER":
            records.append(current)
            current = {}
    if current:
        records.append(current)
    parsed = []
    for item in records:
        raw: dict[str, object] = {key: values for key, values in item.items()}
        parsed.append(
            _citation(
                source_key=_first_ris(item, "ID"),
                title=_first_ris(item, "TI", "T1"),
                abstract=_first_ris(item, "AB"),
                year=_first_ris(item, "PY", "Y1"),
                doi=_first_ris(item, "DO"),
                pmid=_first_ris(item, "PM", "AN"),
                authors=item.get("AU", []),
                journal=_first_ris(item, "JO", "JF", "T2"),
                raw=raw,
            )
        )
    return parsed


def _first_ris(item: dict[str, list[str]], *tags: str) -> str | None:
    return next((item[tag][0] for tag in tags if item.get(tag)), None)


def parse_bibtex(content: str) -> list[ParsedCitation]:
    entry_pattern = re.compile(r"@\w+\s*\{\s*([^,]+),((?:[^{}]|\{[^{}]*\})*)\}", re.S)
    field_pattern = re.compile(r"(\w+)\s*=\s*(?:\{([^{}]*)\}|\"([^\"]*)\")\s*,?", re.S)
    parsed = []
    for entry in entry_pattern.finditer(content):
        key, body = entry.groups()
        fields = {
            name.casefold(): _clean(braced if braced is not None else quoted) or ""
            for name, braced, quoted in field_pattern.findall(body)
        }
        parsed.append(
            _citation(
                source_key=key,
                title=fields.get("title"),
                abstract=fields.get("abstract"),
                year=fields.get("year"),
                doi=fields.get("doi"),
                pmid=fields.get("pmid"),
                authors=re.split(r"\s+and\s+", fields.get("author", ""), flags=re.I),
                journal=fields.get("journal"),
                raw=dict(fields),
            )
        )
    return parsed


PARSERS: dict[CitationFormat, Callable[[str], list[ParsedCitation]]] = {
    CitationFormat.CSV: parse_csv,
    CitationFormat.RIS: parse_ris,
    CitationFormat.BIBTEX: parse_bibtex,
}


def parse_citations(source_format: CitationFormat, content: str) -> list[ParsedCitation]:
    records = PARSERS[source_format](content)
    if not records:
        raise CitationParseError("citation import contained no records")
    return records
