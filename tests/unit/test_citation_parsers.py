from backend.app.citations.domain import CitationFormat
from backend.app.citations.parsers import parse_citations


def test_csv_parser_normalizes_identifiers_without_losing_raw_metadata() -> None:
    records = parse_citations(
        CitationFormat.CSV,
        "title,year,doi,pmid,authors\n"
        "Fixture Study,2024,https://doi.org/10.1/ABC,12345,A One;B Two\n",
    )
    assert len(records) == 1
    assert records[0].doi == "10.1/abc"
    assert records[0].pmid == "12345"
    assert records[0].authors == ["A One", "B Two"]
    assert records[0].raw_metadata["doi"] == "https://doi.org/10.1/ABC"


def test_ris_parser_preserves_repeated_authors() -> None:
    records = parse_citations(
        CitationFormat.RIS,
        "TY  - JOUR\nTI  - Fixture RIS\nAU  - One, A\nAU  - Two, B\nPY  - 2023\nER  -\n",
    )
    assert records[0].title == "Fixture RIS"
    assert records[0].authors == ["One, A", "Two, B"]
    assert records[0].publication_year == 2023


def test_bibtex_parser_is_deterministic_and_local() -> None:
    content = (
        "@article{fixture,\n"
        "title={Fixture BibTeX},\n"
        "author={One, A and Two, B},\n"
        "year={2022},\n"
        "doi={doi: 10.2/XYZ}\n"
        "}\n"
    )
    first = parse_citations(CitationFormat.BIBTEX, content)[0]
    second = parse_citations(CitationFormat.BIBTEX, content)[0]
    assert first == second
    assert first.source_key == "fixture"
    assert first.doi == "10.2/xyz"
