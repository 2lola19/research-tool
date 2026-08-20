from __future__ import annotations

from backend.app.core.config import Settings
from backend.app.documents.contracts import ConfiguredDocumentParser
from backend.app.documents.parsers import FixtureDocumentParser, GrobidDocumentParser


def build_document_parser(settings: Settings) -> ConfiguredDocumentParser:
    if settings.document_parser_provider == "grobid":
        return GrobidDocumentParser(
            base_url=settings.grobid_url,
            expected_version=settings.grobid_version,
            timeout_seconds=settings.document_parser_timeout_seconds,
            maximum_request_bytes=settings.max_document_file_size_bytes,
            maximum_response_bytes=settings.max_document_parser_response_bytes,
        )
    return FixtureDocumentParser()
