from __future__ import annotations

from decimal import Decimal
from html import escape
from typing import Any

from backend.app.analysis.domain import FOREST_RENDERER_VERSION


def forest_plot_model(
    *, effect_measure: str, result: dict[str, Any], study_labels: dict[str, str]
) -> dict[str, Any]:
    return {
        "effect_measure": effect_measure,
        "model": result["model"],
        "estimator": result["estimator"],
        "number_of_studies": result["number_of_studies"],
        "null_value": "1" if effect_measure in {"RR", "OR", "HR"} else "0",
        "studies": [
            {
                **item,
                "label": study_labels.get(item["study_id"], item["study_id"]),
            }
            for item in result["weights"]
        ],
        "pooled": {
            "estimate": result["presentation_estimate"],
            "ci_lower": result["presentation_ci_lower"],
            "ci_upper": result["presentation_ci_upper"],
        },
        "heterogeneity": result["heterogeneity"],
        "renderer_version": FOREST_RENDERER_VERSION,
    }


def render_forest_svg(model: dict[str, Any]) -> bytes:
    studies = model["studies"]
    width = 900
    left = 310
    right = 850
    header_y = 45
    row_height = 34
    pooled_y = header_y + (len(studies) + 2) * row_height
    height = pooled_y + 90
    values = [Decimal(model["null_value"])]
    for item in studies:
        values.extend((Decimal(item["ci_lower"]), Decimal(item["ci_upper"])))
    values.extend((Decimal(model["pooled"]["ci_lower"]), Decimal(model["pooled"]["ci_upper"])))
    minimum, maximum = min(values), max(values)
    padding = (maximum - minimum) * Decimal("0.08") or Decimal("1")
    minimum -= padding
    maximum += padding

    def x(value: str | Decimal) -> Decimal:
        number = Decimal(value)
        return Decimal(left) + (number - minimum) / (maximum - minimum) * Decimal(right - left)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Forest plot">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#172033}.small{font-size:12px}"
        ".label{font-size:13px}.head{font-size:15px;font-weight:700}</style>",
        f'<text x="20" y="25" class="head">{escape(model["effect_measure"])} '
        f"{escape(model['model'].replace('_', ' ').title())}</text>",
        f'<line x1="{x(model["null_value"])}" y1="{header_y}" '
        f'x2="{x(model["null_value"])}" y2="{pooled_y + 18}" stroke="#8a93a5" '
        'stroke-dasharray="4 4"/>',
    ]
    for index, item in enumerate(studies, start=1):
        y = header_y + index * row_height
        estimate_x = x(item["presentation_estimate"])
        lower_x = x(item["ci_lower"])
        upper_x = x(item["ci_upper"])
        size = Decimal("5") + Decimal(item["normalized_weight_percent"]) / Decimal("20")
        parts.extend(
            (
                f'<text x="20" y="{y + 4}" class="label">{escape(item["label"])}</text>',
                f'<line x1="{lower_x}" y1="{y}" x2="{upper_x}" y2="{y}" '
                'stroke="#243b63" stroke-width="2"/>',
                f'<rect x="{estimate_x - size / 2}" y="{Decimal(y) - size / 2}" '
                f'width="{size}" height="{size}" fill="#315da8"/>',
                f'<text x="860" y="{y + 4}" class="small" text-anchor="end">'
                f"{escape(item['presentation_estimate'])} "
                f"[{escape(item['ci_lower'])}, {escape(item['ci_upper'])}] · "
                f"{escape(item['normalized_weight_percent'])}%</text>",
            )
        )
    pooled = model["pooled"]
    pooled_x = x(pooled["estimate"])
    pooled_lower = x(pooled["ci_lower"])
    pooled_upper = x(pooled["ci_upper"])
    parts.extend(
        (
            f'<text x="20" y="{pooled_y + 4}" class="head">Pooled</text>',
            f'<polygon points="{pooled_lower},{pooled_y} {pooled_x},{pooled_y - 8} '
            f'{pooled_upper},{pooled_y} {pooled_x},{pooled_y + 8}" fill="#a83245"/>',
            f'<line x1="{left}" y1="{pooled_y + 25}" x2="{right}" y2="{pooled_y + 25}" '
            'stroke="#172033"/>',
            f'<text x="{left}" y="{pooled_y + 45}" class="small">{minimum}</text>',
            f'<text x="{right}" y="{pooled_y + 45}" class="small" text-anchor="end">'
            f"{maximum}</text>",
            f'<text x="20" y="{pooled_y + 68}" class="small">Q='
            f"{escape(model['heterogeneity']['q'])}; I²="
            f"{escape(model['heterogeneity']['i_squared_percent'])}%; τ²="
            f"{escape(model['heterogeneity']['tau_squared'])}</text>",
            "</svg>",
        )
    )
    return "".join(parts).encode()
