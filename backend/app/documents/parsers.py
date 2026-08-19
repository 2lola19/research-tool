from __future__ import annotations

import math
from dataclasses import dataclass, replace
from xml.etree import ElementTree

from backend.app.documents.domain import (
    CanonicalDocument,
    CanonicalDocumentBlock,
    DocumentBlockType,
)


class DocumentParseError(ValueError):
    pass


class DocumentParserLimitError(DocumentParseError):
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
        for div in root.findall(
            f".//{self._namespace}text/{self._namespace}body/{self._namespace}div"
        ):
            heading = text_of(div.find(f"./{self._namespace}head"))
            section_path = [heading] if heading else []
            for paragraph in div.findall(f"./{self._namespace}p"):
                paragraph_text = text_of(paragraph)
                if paragraph_text is None:
                    continue
                blocks.append(
                    CanonicalDocumentBlock(
                        block_id=f"grobid-block-{order}",
                        block_type=DocumentBlockType.PARAGRAPH,
                        block_order=order,
                        page_number=None,
                        section_path=section_path,
                        text=paragraph_text,
                    )
                )
                order += 1
        if not blocks and abstract is None and title is None:
            raise DocumentParseError("GROBID TEI contains no canonical document content")
        return CanonicalDocument(title=title, abstract=abstract, blocks=tuple(blocks))
