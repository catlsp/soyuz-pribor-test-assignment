"""Rendering helpers for generated product copy."""

from __future__ import annotations

import json
from typing import Any


def render_json(results: dict[str, Any] | list[dict[str, Any]]) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2) + "\n"


def _markdown_item(item: dict[str, Any], index: int | None = None) -> str:
    heading = f"## {item.get('seo_title', 'Карточка товара')}"
    if index is not None:
        heading = f"## Товар {index}: {item.get('seo_title', 'Карточка товара')}"
    lines = [heading, "", str(item.get("description", "")), "", "### Характеристики", ""]
    if item.get("mode"):
        lines.insert(1, f"_Режим: {item['mode']}_")
    specs = item.get("specs", [])
    if specs:
        lines.extend(["| Параметр | Значение |", "|---|---|"])
        for spec in specs:
            name = str(spec.get("name", "")).replace("|", "\\|").replace("\n", " ")
            value = str(spec.get("value", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {name} | {value} |")
    else:
        lines.append("Характеристики не указаны.")
    lines.extend(["", "### Поисковые запросы", ""])
    lines.extend(f"- {query}" for query in item.get("queries", []))
    lines.extend(["", "### Коммерческий блок", "", str(item.get("commercial_block", ""))])
    missing = item.get("missing_fields", [])
    if missing:
        lines.extend(["", "### Недостающие данные", "", ", ".join(map(str, missing))])
    return "\n".join(lines)


def render_markdown(results: dict[str, Any] | list[dict[str, Any]]) -> str:
    if isinstance(results, list):
        return "\n\n---\n\n".join(
            _markdown_item(item, i) for i, item in enumerate(results, 1)
        ) + "\n"
    return _markdown_item(results) + "\n"


def render(results: dict[str, Any] | list[dict[str, Any]], output_format: str) -> str:
    if output_format == "json":
        return render_json(results)
    if output_format == "markdown":
        return render_markdown(results)
    raise ValueError(f"Unsupported output format: {output_format}")
