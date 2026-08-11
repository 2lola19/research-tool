from __future__ import annotations

import csv
import io
import zipfile
from uuid import UUID

from backend.app.exports.domain import ExportArticle, ExportDataset, ExportFormat, ExportStudy
from backend.app.exports.renderers import render_export


def _dataset() -> ExportDataset:
    article_id = UUID("00000000-0000-0000-0000-000000000004")
    return ExportDataset(
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        review_id=UUID("00000000-0000-0000-0000-000000000002"),
        review_title="Deterministic review",
        prisma_snapshot_id=UUID("00000000-0000-0000-0000-000000000003"),
        prisma_algorithm_version="prisma-2020-deterministic-1",
        prisma_counts={
            "records_identified_databases": 1,
            "full_text_exclusion_reasons": {"population": 1},
        },
        prisma_readiness={"ready_for_final": False, "blockers": [{"code": "INCOMPLETE"}]},
        prisma_source_references={"article_ids": [str(article_id)]},
        articles=(
            ExportArticle(
                id=article_id,
                title=" \t=unsafe spreadsheet title",
                abstract="Stable abstract",
                publication_year=2026,
                doi="10.1000/test",
                pmid="123",
                authors=("Researcher, A",),
                journal="Journal",
                source_record_ids=(UUID("00000000-0000-0000-0000-000000000005"),),
                study_keys=("study-1",),
            ),
        ),
        studies=(
            ExportStudy(
                id=UUID("00000000-0000-0000-0000-000000000006"),
                study_key="study-1",
                label="Study one",
                article_ids=(article_id,),
            ),
        ),
    )


def test_all_export_formats_are_byte_reproducible() -> None:
    dataset = _dataset()
    for export_format in ExportFormat:
        first = render_export(export_format, dataset)
        second = render_export(export_format, dataset)
        assert first.content == second.content
        assert first.content


def test_csv_neutralizes_spreadsheet_formula_prefixes() -> None:
    rendered = render_export(ExportFormat.CSV, _dataset())
    rows = list(csv.reader(io.StringIO(rendered.content.decode("utf-8-sig"))))
    assert rows[1][1] == "' \t=unsafe spreadsheet title"


def test_xlsx_contains_expected_portable_sheets() -> None:
    rendered = render_export(ExportFormat.XLSX, _dataset())
    with zipfile.ZipFile(io.BytesIO(rendered.content)) as workbook:
        assert workbook.testzip() is None
        assert {
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
            "xl/worksheets/sheet3.xml",
            "xl/worksheets/sheet4.xml",
            "xl/worksheets/sheet5.xml",
        } <= set(workbook.namelist())
        articles_xml = workbook.read("xl/worksheets/sheet4.xml").decode()
    assert "=unsafe spreadsheet title" in articles_xml
    assert "<f>" not in articles_xml
