# ruff: noqa: E501
from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable, Sequence
from html import escape
from typing import Any


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(reference: str, value: object) -> str:
    if value is None:
        return f'<c r="{reference}"/>'
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, int | float):
        return f'<c r="{reference}"><v>{value}</v></c>'
    return f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def _sheet(rows: Iterable[Sequence[object]]) -> str:
    output: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells = "".join(
            _cell(f"{_column_name(column)}{row_number}", value)
            for column, value in enumerate(row, start=1)
        )
        output.append(f'<row r="{row_number}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(output)}</sheetData></worksheet>"
    )


def _entry(archive: zipfile.ZipFile, name: str, value: str) -> None:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, value.encode())


def render_xlsx_workbook(sheets: list[tuple[str, list[list[Any]]]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        overrides: list[str] = []
        workbook: list[str] = []
        relations: list[str] = []
        for index, (name, rows) in enumerate(sheets, start=1):
            overrides.append(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
            workbook.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
            relations.append(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            _entry(archive, f"xl/worksheets/sheet{index}.xml", _sheet(rows))
        _entry(
            archive,
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(overrides)
            + "</Types>",
        )
        _entry(
            archive,
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        _entry(
            archive,
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + "".join(workbook)
            + "</sheets></workbook>",
        )
        _entry(
            archive,
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(relations)
            + "</Relationships>",
        )
    return buffer.getvalue()
