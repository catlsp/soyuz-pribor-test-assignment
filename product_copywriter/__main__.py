"""Command line entry point: python -m product_copywriter."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .formatting import render
from .service import generate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="product_copywriter",
        description="Создаёт SEO-текст карточки товара по JSON-входу.",
    )
    parser.add_argument("input", help="Путь к JSON-файлу с объектом товара или списком товаров")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", help="Файл для результата; по умолчанию stdout")
    parser.add_argument("--demo", action="store_true", help="Использовать локальный демонстрационный режим")
    return parser


def _read_input(path: str) -> dict[str, Any] | list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8-sig") as source:
        value = json.load(source)
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
        return value
    raise ValueError("Входной JSON должен быть объектом товара или непустым списком объектов")


def _atomic_write(path: str, content: str) -> None:
    target = Path(path)
    parent = target.parent
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as temp:
            temp_name = temp.name
            temp.write(content)
        os.replace(temp_name, target)
    except Exception:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        products = _read_input(args.input)
        batch = isinstance(products, list)
        generated = [generate(item, demo=args.demo) for item in products] if batch else generate(products, demo=args.demo)
        output = render(generated, args.format)
        if args.output:
            _atomic_write(args.output, output)
        else:
            sys.stdout.write(output)
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
