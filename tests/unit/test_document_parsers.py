import httpx
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
    DocumentParserProviderError,
    DocumentParserTimeoutError,
    DocumentParserUnavailableError,
    DocumentParserUnsupportedError,
    FixtureDocumentParser,
    GrobidDocumentParser,
    GrobidTeiParser,
    canonical_document_hash,
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


def test_live_grobid_adapter_posts_pdf_and_probes_pinned_version() -> None:
    tei = b"""
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader><fileDesc><titleStmt><title>Live Title</title></titleStmt></fileDesc></teiHeader>
      <text><front><abstract><p>Live abstract.</p></abstract></front>
        <body><pb n="2"/><div><head>Methods</head><p>Live body text.</p></div></body>
      </text>
    </TEI>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"status": "ready"}, request=request)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.9.1"}, request=request)
        assert request.url.path == "/api/processFulltextDocument"
        assert b"application/pdf" in request.content
        return httpx.Response(200, content=tei, request=request)

    parser = GrobidDocumentParser(
        base_url="http://grobid:8070",
        expected_version="0.9.1",
        timeout_seconds=2,
        maximum_request_bytes=1_000,
        maximum_response_bytes=10_000,
        transport=httpx.MockTransport(handler),
    )

    health = parser.health()
    parsed = parser.parse(b"%PDF-1.7\nfixture")

    assert health.healthy is True
    assert health.version == "0.9.1"
    assert parser.version == "grobid-0.9.1+adapter-1"
    assert parsed.title == "Live Title"
    assert parsed.abstract == "Live abstract."
    assert parsed.blocks[0].page_number == 2
    assert parsed.blocks[0].section_path == ["Methods"]
    assert canonical_document_hash(parsed) == canonical_document_hash(parsed)


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, DocumentParserUnsupportedError),
        (500, DocumentParserProviderError),
        (503, DocumentParserUnavailableError),
    ],
)
def test_live_grobid_adapter_classifies_provider_failures(
    status_code: int, error_type: type[Exception]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    parser = GrobidDocumentParser(
        base_url="http://grobid:8070",
        expected_version="0.9.1",
        timeout_seconds=2,
        maximum_request_bytes=1_000,
        maximum_response_bytes=10_000,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(error_type):
        parser.parse(b"%PDF-1.7\nfixture")


def test_live_grobid_adapter_bounds_output_and_maps_timeout() -> None:
    def oversized_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 101, request=request)

    limited = GrobidDocumentParser(
        base_url="http://grobid:8070",
        expected_version="0.9.1",
        timeout_seconds=2,
        maximum_request_bytes=1_000,
        maximum_response_bytes=100,
        transport=httpx.MockTransport(oversized_handler),
    )
    with pytest.raises(DocumentParserLimitError):
        limited.parse(b"%PDF-1.7\nfixture")

    def declared_oversized_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": "101"},
            content=b"<TEI />",
            request=request,
        )

    declared_limited = GrobidDocumentParser(
        base_url="http://grobid:8070",
        expected_version="0.9.1",
        timeout_seconds=2,
        maximum_request_bytes=1_000,
        maximum_response_bytes=100,
        transport=httpx.MockTransport(declared_oversized_handler),
    )
    with pytest.raises(DocumentParserLimitError):
        declared_limited.parse(b"%PDF-1.7\nfixture")

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    timed_out = GrobidDocumentParser(
        base_url="http://grobid:8070",
        expected_version="0.9.1",
        timeout_seconds=2,
        maximum_request_bytes=1_000,
        maximum_response_bytes=10_000,
        transport=httpx.MockTransport(timeout_handler),
    )
    with pytest.raises(DocumentParserTimeoutError):
        timed_out.parse(b"%PDF-1.7\nfixture")


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
