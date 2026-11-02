"""Input normalization and output validation."""
from __future__ import annotations
import re
import math
from typing import Any

DEFAULT_EXPECTED_FIELDS = ("Диапазон измерений", "Класс точности", "Питание", "Тип корпуса", "Интерфейсы")

class ProductValidationError(ValueError):
    """Product input is missing required data or has an invalid shape."""

def validate_product(product: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(product, dict):
        raise ProductValidationError("Товар должен быть передан в виде объекта.")
    allowed = {"name", "manufacturer", "specs", "description", "expected_fields"}
    extra = set(product) - allowed
    if extra:
        raise ProductValidationError("Неизвестные поля товара: " + ", ".join(sorted(map(str, extra))))
    name = product.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProductValidationError("Обязательное поле name должно содержать название прибора.")
    manufacturer = product.get("manufacturer")
    description = product.get("description")
    manufacturer = "" if manufacturer is None else manufacturer
    description = "" if description is None else description
    if not isinstance(manufacturer, str) or not isinstance(description, str):
        raise ProductValidationError("manufacturer и description должны быть строками.")
    specs = product.get("specs")
    specs = {} if specs is None else specs
    if not isinstance(specs, dict) or not all(isinstance(k, str) and k.strip() and _scalar(v) for k, v in specs.items()):
        raise ProductValidationError("specs должен быть объектом со строковыми названиями и простыми значениями.")
    expected = product.get("expected_fields")
    expected = list(DEFAULT_EXPECTED_FIELDS) if expected is None else expected
    if not isinstance(expected, list) or not all(isinstance(x, str) and x.strip() for x in expected):
        raise ProductValidationError("expected_fields должен быть списком строк.")
    placeholders = {"данных нет", "нет данных", "данные не предоставлены", "не указано"}
    def clean(value):
        value = value.strip()
        return "" if value.casefold().rstrip(".") in placeholders else value
    return {"name": name.strip(), "manufacturer": clean(manufacturer), "specs": dict(specs),
            "description": clean(description), "expected_fields": list(dict.fromkeys(x.strip() for x in expected))}

def _scalar(value: Any) -> bool:
    if value is None or isinstance(value, str):
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)

def deterministic_specs(product: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    specs = product["specs"]
    rows = [{"name": str(k), "value": str(v).strip() if v is not None and str(v).strip() else "данных нет"} for k, v in specs.items()]
    missing = []
    for field in product["expected_fields"]:
        match = next((r for r in rows if r["name"].casefold() == field.casefold()), None)
        if match is None:
            rows.append({"name": field, "value": "данных нет"})
            missing.append(field)
        elif match["value"] == "данных нет":
            missing.append(field)
    for row in rows:
        if row["value"] == "данных нет" and row["name"].casefold() not in {x.casefold() for x in product["expected_fields"]}:
            missing.append(row["name"])
    if not product["manufacturer"]:
        missing.append("manufacturer")
    if not product["description"]:
        missing.append("description")
    return rows, missing

def validate_output(data: Any, product: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Ответ должен быть JSON-объектом.")
    required = {"seo_title", "description", "queries", "commercial_block"}
    if set(data) != required:
        raise ValueError("JSON должен содержать ровно требуемые поля: seo_title, description, queries, commercial_block.")
    title, desc, comm, queries = data["seo_title"], data["description"], data["commercial_block"], data["queries"]
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 70:
        raise ValueError("SEO-заголовок должен содержать до 70 символов.")
    if not isinstance(desc, str) or not 800 <= len(desc.strip()) <= 1200:
        raise ValueError("Описание должно содержать от 800 до 1200 символов.")
    if not isinstance(comm, str) or not comm.strip() or len(comm.strip()) > 600:
        raise ValueError("commercial_block должен быть непустой строкой до 600 символов.")
    if not isinstance(queries, list) or not 3 <= len(queries) <= 5 or not all(isinstance(q, str) and q.strip() for q in queries):
        raise ValueError("queries должен содержать от 3 до 5 непустых строк.")
    if len({q.strip().casefold() for q in queries}) != len(queries):
        raise ValueError("Поисковые запросы должны быть различными.")
    fact_text = str(product).casefold().replace(",", ".")
    nums = set(re.findall(r"\d+(?:[.,]\d+)?", fact_text))
    prose = " ".join([title, desc, comm, *queries])
    if any(n.replace(",", ".") not in {x.replace(",", ".") for x in nums} for n in re.findall(r"\d+(?:[.,]\d+)?", prose)):
        raise ValueError("В тексте найдено числовое значение, которого нет во входных данных.")
    specs, missing = deterministic_specs(product)
    return {"seo_title": title.strip(), "description": desc.strip(), "specs": specs,
            "queries": queries, "commercial_block": comm.strip(), "missing_fields": missing, "mode": "LLM"}
