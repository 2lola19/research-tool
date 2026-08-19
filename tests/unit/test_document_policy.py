from __future__ import annotations

import pytest

from backend.app.core.errors import ConflictError
from backend.app.documents.service import DocumentService


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test/document.pdf",
        "https://127.0.0.1/document.pdf",
        "https://localhost/document.pdf",
        "https://user:password@example.test/document.pdf",
        "https://example.test/document.pdf#fragment",
    ],
)
def test_external_document_urls_fail_closed(url: str) -> None:
    with pytest.raises(ConflictError):
        DocumentService._validate_source_url(url)


def test_external_document_urls_accept_https_public_host() -> None:
    DocumentService._validate_source_url("https://example.test/document.pdf")
