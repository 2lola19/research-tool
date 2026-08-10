import pytest

from backend.app.documents.domain import DocumentBlockType
from backend.app.documents.parsers import DocumentParseError, FixtureDocumentParser, GrobidTeiParser


def test_fixture_parser_normalizes_a_deterministic_block() -> None:
    parsed = FixtureDocumentParser().parse(b"%PDF-FIXTURE\nMethods text.")

    assert parsed.blocks[0].block_id == "fixture-block-1"
    assert parsed.blocks[0].block_type == DocumentBlockType.PARAGRAPH
    assert parsed.blocks[0].page_number == 1


def test_fixture_parser_rejects_non_fixture_content() -> None:
    with pytest.raises(DocumentParseError):
        FixtureDocumentParser().parse(b"%PDF-1.7\nnot supported")


def test_grobid_adapter_normalizes_representative_tei() -> None:
    content = b"""
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader>
        <fileDesc><titleStmt><title>Fixture Title</title></titleStmt></fileDesc>
      </teiHeader>
      <text><front><abstract><p>Fixture abstract.</p></abstract></front>
        <body><div><head>Methods</head><p>Participants were eligible.</p></div></body>
      </text>
    </TEI>
    """

    parsed = GrobidTeiParser().parse(content)

    assert parsed.title == "Fixture Title"
    assert parsed.abstract == "Fixture abstract."
    assert parsed.blocks[0].section_path == ["Methods"]
    assert parsed.blocks[0].text == "Participants were eligible."


@pytest.mark.parametrize("content", [b"", b"<TEI>"])
def test_grobid_adapter_rejects_malformed_or_empty_output(content: bytes) -> None:
    with pytest.raises(DocumentParseError):
        GrobidTeiParser().parse(content)
