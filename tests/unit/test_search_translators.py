from backend.app.search.translators import FixtureSearchTranslator, PubMedTranslator


def _content() -> dict[str, object]:
    return {
        "name": "Hypertension search",
        "concepts": [
            {
                "label": "population",
                "terms": [
                    {"text": "high blood pressure", "field": "title_abstract"},
                    {"text": "Hypertension", "field": "mesh"},
                ],
            },
            {
                "label": "intervention",
                "terms": [{"text": "exercise", "field": "all"}],
            },
        ],
    }


def test_pubmed_translation_is_deterministic_and_field_aware() -> None:
    expected = (
        '("high blood pressure"[Title/Abstract] OR "Hypertension"[MeSH Terms]) '
        'AND ("exercise"[All Fields])'
    )
    assert PubMedTranslator().translate(_content()) == expected
    assert PubMedTranslator().translate(_content()) == expected


def test_fixture_translation_is_offline_and_stable() -> None:
    assert FixtureSearchTranslator().translate(_content()) == (
        "population(title_abstract:high blood pressure|mesh:Hypertension) "
        "& intervention(all:exercise)"
    )
