from __future__ import annotations

import hashlib
import html
import io
import json
import zipfile
from typing import Any

from backend.app.reporting.domain import (
    PACKAGE_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    RenderedReport,
    ReportFormat,
    canonical_json_bytes,
    content_hash,
)
from backend.app.reporting.xlsx import render_xlsx_workbook

_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_MAX_PACKAGE_BYTES = 50 * 1024 * 1024


def render_report(report_format: ReportFormat, payload: dict[str, Any]) -> RenderedReport:
    if report_format == ReportFormat.JSON:
        content = canonical_json_bytes(payload) + b"\n"
        return _rendered(content, "application/json", "json", payload)
    if report_format == ReportFormat.HTML:
        content = _html(payload)
        return _rendered(content, "text/html; charset=utf-8", "html", payload)
    if report_format == ReportFormat.XLSX:
        content = _xlsx(payload)
        return _rendered(
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
            payload,
        )
    if report_format == ReportFormat.ZIP:
        return render_reproducibility_package(payload)
    raise ValueError("unsupported report format")


def _rendered(
    content: bytes, media_type: str, extension: str, payload: dict[str, Any]
) -> RenderedReport:
    return RenderedReport(
        content=content,
        media_type=media_type,
        extension=extension,
        manifest={
            "schema_version": REPORT_SCHEMA_VERSION,
            "scientific_content_hash": content_hash(payload),
            "artifact_sha256": hashlib.sha256(content).hexdigest(),
            "byte_size": len(content),
        },
    )


def _html(payload: dict[str, Any]) -> bytes:
    sections = []
    for name, value in payload.get("sections", {}).items():
        sections.append(
            f"<section><h2>{html.escape(name.replace('_', ' ').title())}</h2>"
            "<pre>"
            f"{html.escape(json.dumps(value, ensure_ascii=False, indent=2, default=str))}"
            "</pre>"
            "</section>"
        )
    title = html.escape(str(payload.get("review", {}).get("title", "Structured review report")))
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{title}</title><style>body{{font-family:system-ui,sans-serif;max-width:72rem;"
        "margin:2rem auto;padding:0 1rem;color:#172033}table{border-collapse:collapse}"
        "th,td{border:1px solid #ccd3df;padding:.4rem;text-align:left}pre{white-space:pre-wrap;"
        "background:#f5f7fa;padding:1rem;overflow:auto}h1,h2{color:#17365d}</style></head>"
        f"<body><h1>{title}</h1>{''.join(sections)}</body></html>"
    )
    return document.encode("utf-8")


def _xlsx(payload: dict[str, Any]) -> bytes:
    sheets: list[tuple[str, list[list[Any]]]] = []
    summary = [["Field", "Value"]]
    for key, value in payload.get("review", {}).items():
        summary.append([key, value])
    sheets.append(("Review Summary", summary))
    for name, value in payload.get("sections", {}).items():
        rows: list[list[Any]] = [["JSON"]]
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            keys = sorted({key for item in value for key in item})
            rows = [keys] + [[_cell(item.get(key)) for key in keys] for item in value]
        elif isinstance(value, dict):
            rows = [["Field", "Value"]] + [[key, _cell(value[key])] for key in sorted(value)]
        else:
            rows.append([_cell(value)])
        if len(rows) > 1:
            sheets.append((_sheet_name(name), rows))
    return render_xlsx_workbook(sheets)


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def _sheet_name(value: str) -> str:
    result = value.replace("_", " ").title()[:31]
    return result or "Data"


def render_reproducibility_package(payload: dict[str, Any]) -> RenderedReport:
    sections = payload.get("sections", {})
    files: dict[str, bytes] = {
        "review/report.json": canonical_json_bytes(payload.get("review", {})) + b"\n",
        "protocol/protocol.json": canonical_json_bytes(sections.get("protocol", [])) + b"\n",
        "search/searches.json": canonical_json_bytes(sections.get("search", [])) + b"\n",
        "citations/citations.json": canonical_json_bytes(sections.get("citations", [])) + b"\n",
        "screening/screening.json": canonical_json_bytes(sections.get("screening", {})) + b"\n",
        "prisma/prisma.json": canonical_json_bytes(sections.get("prisma", {})) + b"\n",
        "studies/studies.json": canonical_json_bytes(sections.get("studies", [])) + b"\n",
        "extraction/extraction.json": canonical_json_bytes(sections.get("extraction", {})) + b"\n",
        "risk-of-bias/risk-of-bias.json": canonical_json_bytes(sections.get("risk_of_bias", {}))
        + b"\n",
        "outcomes/outcomes.json": canonical_json_bytes(sections.get("outcomes", {})) + b"\n",
        "analysis/analysis.json": canonical_json_bytes(sections.get("analysis", {})) + b"\n",
        "certainty/certainty.json": canonical_json_bytes(sections.get("certainty", {})) + b"\n",
        "audit/provenance.json": canonical_json_bytes(sections.get("provenance", [])) + b"\n",
    }
    checksums = {
        path: hashlib.sha256(content).hexdigest() for path, content in sorted(files.items())
    }
    scientific_manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "review_id": payload.get("review", {}).get("id"),
        "included_files": sorted(files),
        "checksums": checksums,
        "source_references": payload.get("source_references", {}),
        "known_limitations": [
            "Full-text binaries are excluded.",
            "Raw provider artifacts are represented by metadata and checksums only.",
            "Docker/PostgreSQL, live GROBID, and R/metafor execution are not validated here.",
        ],
    }
    package_hash = content_hash(scientific_manifest)
    manifest = {
        **scientific_manifest,
        "package_hash": package_hash,
        "hash_excludes": ["generation_timestamp", "actor", "archive_entry_timestamps"],
        "excluded_content": [
            "document binaries",
            "raw provider bytes",
            "secrets",
            "environment files",
            "runtime files",
        ],
    }
    files["manifest.json"] = canonical_json_bytes(manifest) + b"\n"
    files["manifest-checksums.json"] = canonical_json_bytes(checksums) + b"\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in sorted(files.items()):
            _safe_archive_name(path)
            info = zipfile.ZipInfo(path, _ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    content = buffer.getvalue()
    if len(content) > _MAX_PACKAGE_BYTES:
        raise ValueError("reproducibility package exceeds the configured 50 MiB limit")
    validation = validate_reproducibility_package(content)
    if not validation["valid"]:
        raise ValueError("generated reproducibility package failed checksum validation")
    return RenderedReport(
        content=content,
        media_type="application/zip",
        extension="zip",
        manifest={
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "package_hash": package_hash,
            "artifact_sha256": hashlib.sha256(content).hexdigest(),
            "byte_size": len(content),
            "files": sorted(files),
        },
    )


def validate_reproducibility_package(content: bytes) -> dict[str, Any]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("duplicate archive names")
            for name in names:
                try:
                    _safe_archive_name(name)
                except ValueError as exc:
                    errors.append(str(exc))
            manifest = json.loads(archive.read("manifest.json"))
            checksums = json.loads(archive.read("manifest-checksums.json"))
            if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
                errors.append("unsupported manifest schema")
            for name, expected in checksums.items():
                if name not in names:
                    errors.append(f"missing file: {name}")
                elif hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    errors.append(f"checksum mismatch: {name}")
            scientific = {
                key: value
                for key, value in manifest.items()
                if key not in {"package_hash", "hash_excludes", "excluded_content"}
            }
            if content_hash(scientific) != manifest.get("package_hash"):
                errors.append("package hash mismatch")
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        errors.append(f"invalid package: {exc}")
    return {"valid": not errors, "errors": errors}


def _safe_archive_name(name: str) -> None:
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        raise ValueError(f"unsafe archive name: {name}")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts) or ":" in parts[0]:
        raise ValueError(f"unsafe archive name: {name}")
