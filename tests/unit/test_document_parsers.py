import pytest

from backend.app.documents.domain import (
    CanonicalDocument,
    CanonicalDocumentBlock,
    DocumentBlockType,
)
from backend.app.documents.manifests import build_chunk_manifest
from backend.app.documents.parsers import (
    DocumentParseError,
    DocumentParserLimitError,
    DocumentParserLimits,
    FixtureDocumentParser,
    GrobidTeiParser,
    materialize_blocks,
    validate_canonical_document,
)


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


def test_parser_limits_and_chunk_manifest_are_deterministic() -> None:
    parsed = FixtureDocumentParser().parse(b"%PDF-FIXTURE\nMethods text.")
    validate_canonical_document(parsed, DocumentParserLimits(maximum_blocks=2))

    manifest, manifest_hash, text_size = build_chunk_manifest(parsed, content_sha256="a" * 64)

    assert manifest[0]["text_sha256"]
    assert len(manifest_hash) == 64
    assert text_size == len(b"Methods text.")


def test_materialization_preserves_title_abstract_and_body_order() -> None:
    canonical = CanonicalDocument(
        title="Title",
        abstract="Abstract",
        blocks=(
            CanonicalDocumentBlock(
                block_id="body-1",
                block_type=DocumentBlockType.PARAGRAPH,
                block_order=1,
                page_number=1,
                section_path=[],
                text="Body",
            ),
        ),
    )

    blocks = materialize_blocks(canonical)

    assert [(item.block_id, item.block_order) for item in blocks] == [
        ("title", 0),
        ("abstract", 1),
        ("body-1", 2),
    ]
    validate_canonical_document(canonical, DocumentParserLimits(maximum_blocks=3))


def test_parser_limits_reject_oversized_canonical_output() -> None:
    canonical = CanonicalDocument(
        title=None,
        abstract=None,
        blocks=(
            CanonicalDocumentBlock(
                block_id="paragraph-1",
                block_type=DocumentBlockType.PARAGRAPH,
                block_order=1,
                page_number=1,
                section_path=[],
                text="too large",
            ),
        ),
    )

    with pytest.raises(DocumentParserLimitError):
        validate_canonical_document(
            canonical,
            DocumentParserLimits(maximum_blocks=10, maximum_block_text_bytes=2),
        )
