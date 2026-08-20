from __future__ import annotations

import hashlib
import json
import math
import secrets
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx

from backend.app.documents.contracts import DocumentParserHealth
from backend.app.documents.domain import (
    CanonicalDocument,
    CanonicalDocumentBlock,
    DocumentBlockType,
)


class DocumentParseError(ValueError):
    pass


class DocumentParserLimitError(DocumentParseError):
    pass


class DocumentParserTimeoutError(DocumentParseError):
    pass


class DocumentParserUnavailableError(DocumentParseError):
    pass


class DocumentParserProviderError(DocumentParseError):
    pass


class DocumentParserUnsupportedError(DocumentParseError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentParserLimits:
    maximum_blocks: int = 20_000
    maximum_text_bytes: int = 20_000_000
    maximum_block_text_bytes: int = 1_000_000
    maximum_section_depth: int = 32


def materialize_blocks(canonical: CanonicalDocument) -> tuple[CanonicalDocumentBlock, ...]:
    blocks = list(canonical.blocks)
    prefix: list[CanonicalDocumentBlock] = []
    if canonical.title:
        prefix.append(
            CanonicalDocumentBlock(
                block_id="title",
                block_type=DocumentBlockType.TITLE,
                block_order=len(prefix),
                page_number=1,
                section_path=[],
                text=canonical.title,
            )
        )
    if canonical.abstract:
        prefix.append(
            CanonicalDocumentBlock(
                block_id="abstract",
                block_type=DocumentBlockType.ABSTRACT,
                block_order=len(prefix),
                page_number=1,
                section_path=[],
                text=canonical.abstract,
            )
        )
    if prefix and blocks and all(isinstance(block.block_order, int) for block in blocks):
        minimum_order = min(block.block_order for block in blocks)
        offset = max(0, len(prefix) - minimum_order)
        if offset:
            blocks = [replace(block, block_order=block.block_order + offset) for block in blocks]
    return tuple(prefix + blocks)


def validate_canonical_document(canonical: CanonicalDocument, limits: DocumentParserLimits) -> None:
    if not isinstance(canonical, CanonicalDocument):
        raise DocumentParseError("parser returned an invalid canonical document")
    if not isinstance(canonical.blocks, tuple) or any(
        not isinstance(block, CanonicalDocumentBlock) for block in canonical.blocks
    ):
        raise DocumentParseError("parser returned invalid canonical blocks")
    if limits.maximum_blocks < 1 or limits.maximum_text_bytes < 1:
        raise DocumentParserLimitError("parser limits are invalid")
    total_text_bytes = 0
    seen_block_ids: set[str] = set()
    seen_block_orders: set[int] = set()
    blocks = materialize_blocks(canonical)
    if len(blocks) > limits.maximum_blocks:
        raise DocumentParserLimitError("parser output exceeded the block limit")
    for block in blocks:
        if (
            not isinstance(block.block_id, str)
            or not block.block_id
            or len(block.block_id) > 160
            or any(ord(character) < 0x20 for character in block.block_id)
            or block.block_id in seen_block_ids
        ):
            raise DocumentParseError("parser output contains an invalid or duplicate block id")
        seen_block_ids.add(block.block_id)
        if not isinstance(block.block_type, DocumentBlockType):
            raise DocumentParseError("parser output contains an invalid block type")
        if (
            not isinstance(block.block_order, int)
            or isinstance(block.block_order, bool)
            or block.block_order < 0
        ):
            raise DocumentParseError("parser output contains an invalid block order")
        if block.block_order in seen_block_orders:
            raise DocumentParseError("parser output contains duplicate block order")
        seen_block_orders.add(block.block_order)
        if block.page_number is not None and (
            not isinstance(block.page_number, int)
            or isinstance(block.page_number, bool)
            or block.page_number < 1
        ):
            raise DocumentParseError("parser output contains an invalid block location")
        if not isinstance(block.section_path, list):
            raise DocumentParseError("parser output contains an invalid section path")
        if len(block.section_path) > limits.maximum_section_depth:
            raise DocumentParserLimitError("parser output exceeded the section-depth limit")
        if any(
            not isinstance(section, str) or not section.strip() or len(section) > 500
            for section in block.section_path
        ):
            raise DocumentParseError("parser output contains an invalid section path")
        if not isinstance(block.text, str):
            raise DocumentParseError("parser output contains invalid block text")
        encoded_text = block.text.encode("utf-8")
        if len(encoded_text) > limits.maximum_block_text_bytes:
            raise DocumentParserLimitError("parser output exceeded the block text limit")
        total_text_bytes += len(encoded_text)
        if total_text_bytes > limits.maximum_text_bytes:
            raise DocumentParserLimitError("parser output exceeded the total text limit")
        if block.coordinates is not None and (
            not isinstance(block.coordinates, dict)
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in block.coordinates.values()
            )
        ):
            raise DocumentParseError("parser output contains invalid coordinates")
    if total_text_bytes > limits.maximum_text_bytes:
        raise DocumentParserLimitError("parser output exceeded the total text limit")


@dataclass(frozen=True, slots=True)
class FixtureDocumentParser:
    name: str = "fixture"
    version: str = "1"

    def health(self) -> DocumentParserHealth:
        return DocumentParserHealth(healthy=True, provider=self.name, version=self.version)

    def parse(self, content: bytes) -> CanonicalDocument:
        marker = b"%PDF-FIXTURE\n"
        if not content.startswith(marker):
            raise DocumentParseError("the development parser accepts fixture documents only")
        text = content.removeprefix(marker).decode("utf-8").strip()
        if not text:
            raise DocumentParseError("fixture document has no text")
        return CanonicalDocument(
            title=None,
            abstract=None,
            blocks=(
                CanonicalDocumentBlock(
                    block_id="fixture-block-1",
                    block_type=DocumentBlockType.PARAGRAPH,
                    block_order=1,
                    page_number=1,
                    section_path=[],
                    text=text,
                ),
            ),
        )


class GrobidTeiParser:
    """Adapter for representative GROBID TEI output, independent of GROBID SDKs."""

    name = "grobid-tei"
    version = "1"
    _namespace = "{http://www.tei-c.org/ns/1.0}"

    def parse(self, content: bytes) -> CanonicalDocument:
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            raise DocumentParseError("GROBID TEI is malformed") from exc

        def text_of(element: ElementTree.Element | None) -> str | None:
            if element is None:
                return None
            value = " ".join("".join(element.itertext()).split())
            return value or None

        title = text_of(root.find(f".//{self._namespace}titleStmt/{self._namespace}title"))
        abstract = text_of(root.find(f".//{self._namespace}abstract"))
        blocks: list[CanonicalDocumentBlock] = []
        order = 1
        page_number: int | None = None

        def page_from_break(element: ElementTree.Element) -> int | None:
            raw_page = element.attrib.get("n") or element.attrib.get("facs")
            if raw_page is None:
                return None
            try:
                parsed_page = int(raw_page.split("#")[-1])
            except ValueError:
                return None
            return parsed_page if parsed_page > 0 else None

        def walk_div(div: ElementTree.Element, parent_sections: list[str]) -> None:
            nonlocal order, page_number
            heading = text_of(div.find(f"./{self._namespace}head"))
            section_path = [*parent_sections, heading] if heading else parent_sections
            for child in list(div):
                local_name = child.tag.removeprefix(self._namespace)
                if local_name == "pb":
                    page_number = page_from_break(child) or page_number
                elif local_name == "p":
                    paragraph_text = text_of(child)
                    if paragraph_text is None:
                        continue
                    blocks.append(
                        CanonicalDocumentBlock(
                            block_id=f"grobid-block-{order}",
                            block_type=DocumentBlockType.PARAGRAPH,
                            block_order=order,
                            page_number=page_number,
                            section_path=list(section_path),
                            text=paragraph_text,
                        )
                    )
                    order += 1
                elif local_name == "div":
                    walk_div(child, section_path)

        body = root.find(f".//{self._namespace}text/{self._namespace}body")
        if body is not None:
            for child in list(body):
                if child.tag == f"{self._namespace}pb":
                    page_number = page_from_break(child) or page_number
                elif child.tag == f"{self._namespace}div":
                    walk_div(child, [])
        if not blocks and abstract is None and title is None:
            raise DocumentParseError("GROBID TEI contains no canonical document content")
        return CanonicalDocument(title=title, abstract=abstract, blocks=tuple(blocks))


def canonical_document_hash(canonical: CanonicalDocument) -> str:
    """Hash the bounded canonical representation, not provider-specific TEI bytes."""

    payload: dict[str, Any] = {
        "canonical_version": "document-canonical-1",
        "title": canonical.title,
        "abstract": canonical.abstract,
        "blocks": [
            {
                "block_id": block.block_id,
                "block_type": block.block_type.value,
                "block_order": block.block_order,
                "page_number": block.page_number,
                "section_path": list(block.section_path),
                "text": block.text,
                "table_id": block.table_id,
                "figure_id": block.figure_id,
                "coordinates": dict(block.coordinates) if block.coordinates else None,
            }
            for block in canonical.blocks
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


class GrobidDocumentParser:
    """HTTP adapter for a pinned GROBID service and the local TEI normalizer."""

    _adapter_version = "1"

    def __init__(
        self,
        *,
        base_url: str,
        expected_version: str,
        timeout_seconds: float,
        maximum_request_bytes: int,
        maximum_response_bytes: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("GROBID URL must be an HTTP(S) URL without credentials or query data")
        if not expected_version.strip():
            raise ValueError("GROBID version is required")
        self._base_url = base_url.rstrip("/")
        self._expected_version = expected_version.strip()
        self._timeout_seconds = timeout_seconds
        self._maximum_request_bytes = maximum_request_bytes
        self._maximum_response_bytes = maximum_response_bytes
        self._transport = transport
        self._tei_parser = GrobidTeiParser()

    @property
    def name(self) -> str:
        return "grobid"

    @property
    def version(self) -> str:
        return f"grobid-{self._expected_version}+adapter-{self._adapter_version}"

    def health(self) -> DocumentParserHealth:
        try:
            with self._client() as client:
                health_response = client.get(self._endpoint("/api/health"))
                if health_response.status_code != 200:
                    return DocumentParserHealth(
                        healthy=False,
                        provider=self.name,
                        error_class="UNAVAILABLE",
                    )
                try:
                    health_payload = health_response.json()
                except ValueError:
                    return DocumentParserHealth(
                        healthy=False,
                        provider=self.name,
                        error_class="INVALID_OUTPUT",
                    )
                if not isinstance(health_payload, dict):
                    return DocumentParserHealth(
                        healthy=False,
                        provider=self.name,
                        error_class="INVALID_OUTPUT",
                    )
                version_response = client.get(self._endpoint("/api/version"))
                if version_response.status_code != 200:
                    return DocumentParserHealth(
                        healthy=False,
                        provider=self.name,
                        error_class="UNAVAILABLE",
                    )
                version = self._version_text(version_response)
                if version is None or self._expected_version not in version:
                    return DocumentParserHealth(
                        healthy=False,
                        provider=self.name,
                        version=version,
                        error_class="VERSION_MISMATCH",
                    )
                return DocumentParserHealth(healthy=True, provider=self.name, version=version)
        except httpx.TimeoutException:
            return DocumentParserHealth(healthy=False, provider=self.name, error_class="TIMEOUT")
        except (httpx.HTTPError, OSError):
            return DocumentParserHealth(
                healthy=False, provider=self.name, error_class="UNAVAILABLE"
            )

    def parse(self, content: bytes) -> CanonicalDocument:
        if len(content) > self._maximum_request_bytes:
            raise DocumentParserLimitError("document exceeds the parser request size limit")
        body, content_type = self._multipart_body(content)
        try:
            with (
                self._client() as client,
                client.stream(
                    "POST",
                    self._endpoint("/api/processFulltextDocument"),
                    content=body,
                    headers={"Content-Type": content_type, "Accept": "application/xml"},
                ) as response,
            ):
                if response.status_code == 503:
                    raise DocumentParserUnavailableError("GROBID is unavailable")
                if response.status_code in {400, 422}:
                    raise DocumentParserUnsupportedError("GROBID could not process the document")
                if response.status_code >= 500:
                    raise DocumentParserProviderError("GROBID returned a provider error")
                if response.status_code == 204:
                    raise DocumentParserUnsupportedError(
                        "GROBID returned no structured document content"
                    )
                if response.status_code != 200:
                    raise DocumentParseError("GROBID returned an invalid provider status")
                declared_size = response.headers.get("content-length")
                if declared_size is not None:
                    try:
                        declared_size_value = int(declared_size)
                    except ValueError as exc:
                        raise DocumentParseError(
                            "GROBID returned an invalid response size"
                        ) from exc
                    if declared_size_value > self._maximum_response_bytes:
                        raise DocumentParserLimitError(
                            "GROBID output exceeds the parser response size limit"
                        )
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._maximum_response_bytes:
                        raise DocumentParserLimitError(
                            "GROBID output exceeds the parser response size limit"
                        )
                    chunks.append(chunk)
                tei = b"".join(chunks)
        except (DocumentParseError, DocumentParserLimitError):
            raise
        except httpx.TimeoutException as exc:
            raise DocumentParserTimeoutError("GROBID request exceeded its time limit") from exc
        except (httpx.HTTPError, OSError) as exc:
            raise DocumentParserUnavailableError("GROBID is unavailable") from exc
        if not tei.lstrip().startswith(b"<"):
            raise DocumentParseError("GROBID returned a non-TEI response")
        return self._tei_parser.parse(tei)

    def _endpoint(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self._timeout_seconds,
            follow_redirects=False,
            transport=self._transport,
        )

    @staticmethod
    def _version_text(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            value = response.text.strip()
            return value[:120] or None
        if isinstance(payload, dict):
            for key in ("version", "grobidVersion", "revision"):
                version_value: object = payload.get(key)
                if isinstance(version_value, str) and version_value.strip():
                    return version_value.strip()[:120]
        if isinstance(payload, str) and payload.strip():
            return payload.strip()[:120]
        return None

    @staticmethod
    def _multipart_body(content: bytes) -> tuple[bytes, str]:
        boundary = f"ResearchTool-{secrets.token_hex(16)}".encode("ascii")
        chunks = [
            b"--" + boundary + b"\r\n",
            b'Content-Disposition: form-data; name="input"; filename="document.pdf"\r\n',
            b"Content-Type: application/pdf\r\n\r\n",
            content,
            b"\r\n--" + boundary + b"\r\n",
            b'Content-Disposition: form-data; name="consolidateHeader"\r\n\r\n0\r\n',
            b"--" + boundary + b"\r\n",
            b'Content-Disposition: form-data; name="includeRawCitations"\r\n\r\n0\r\n',
            b"--" + boundary + b"--\r\n",
        ]
        return b"".join(chunks), f"multipart/form-data; boundary={boundary.decode('ascii')}"
