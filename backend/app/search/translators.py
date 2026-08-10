from __future__ import annotations

from typing import Any, ClassVar

from backend.app.search.domain import SearchTranslator


def _quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class PubMedTranslator:
    provider = "pubmed"
    version = "1"
    _fields: ClassVar[dict[str, str]] = {
        "all": "All Fields",
        "title_abstract": "Title/Abstract",
        "mesh": "MeSH Terms",
    }

    def translate(self, content: dict[str, Any]) -> str:
        concepts: list[str] = []
        for concept in content["concepts"]:
            terms = [
                f"{_quoted(term['text'])}[{self._fields[term['field']]}]"
                for term in concept["terms"]
            ]
            concepts.append("(" + " OR ".join(terms) + ")")
        return " AND ".join(concepts)


class FixtureSearchTranslator:
    provider = "fixture"
    version = "1"

    def translate(self, content: dict[str, Any]) -> str:
        concepts = []
        for concept in content["concepts"]:
            terms = "|".join(f"{term['field']}:{term['text']}" for term in concept["terms"])
            concepts.append(f"{concept['label']}({terms})")
        return " & ".join(concepts)


TRANSLATORS: tuple[SearchTranslator, ...] = (
    PubMedTranslator(),
    FixtureSearchTranslator(),
)


def get_translator(provider: str) -> SearchTranslator | None:
    normalized = provider.strip().casefold()
    return next((item for item in TRANSLATORS if item.provider == normalized), None)
