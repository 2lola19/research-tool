from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree

from backend.app.documents.domain import (
    CanonicalDocument,
    CanonicalDocumentBlock,
    DocumentBlockType,
)


class DocumentParseError(ValueError):
    pass


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
