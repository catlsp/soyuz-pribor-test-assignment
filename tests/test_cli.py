from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_copywriter import __main__ as cli
from product_copywriter.formatting import render_json, render_markdown


PRODUCT = {"name": "Термометр Т-1", "specs": {"диапазон измерений": "-20…100 °C"}}
RESULT = {
    "seo_title": "Термометр Т-1 купить",
    "description": "Описание товара.",
    "specs": [{"name": "диапазон измерений", "value": "-20…100 °C"}],
    "queries": ["купить термометр Т-1"],
    "commercial_block": "Закажите товар.",
    "missing_fields": [],
}


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def input_file(self, content: str, *, bom: bool = False) -> str:
        path = self.root / "input.json"
        path.write_text(("\ufeff" if bom else "") + content, encoding="utf-8")
        return str(path)

    def test_help(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ex:
                cli.main(["--help"])
        self.assertEqual(ex.exception.code, 0)

    def test_bom_json_input_and_stdout_output(self):
        path = self.input_file(json.dumps(PRODUCT, ensure_ascii=False), bom=True)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(cli, "generate", return_value=RESULT) as generate:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.main([path])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), RESULT)
        self.assertEqual(stderr.getvalue(), "")
        generate.assert_called_once_with(PRODUCT, demo=False)

    def test_batch_markdown_demo_and_output_file(self):
        path = self.input_file(json.dumps([PRODUCT, PRODUCT], ensure_ascii=False))
        output_path = str(self.root / "result.md")
        result = dict(RESULT, mode="demo")
        with patch.object(cli, "generate", return_value=result) as generate:
            code = cli.main([path, "--format", "markdown", "--output", output_path, "--demo"])
        rendered = Path(output_path).read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertEqual(generate.call_count, 2)
        self.assertIn("Товар 1", rendered)
        self.assertIn("Товар 2", rendered)
        self.assertIn("_Режим: demo_", rendered)

    def test_bad_json_reports_safe_error(self):
        path = self.input_file("{")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main([path])
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Ошибка:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_empty_list_and_missing_file_fail_without_output(self):
        for path in (self.input_file("[]"), str(self.root / "missing.json")):
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.main([path])
            self.assertEqual(code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertTrue(stderr.getvalue())

    def test_malformed_batch_is_rejected_before_generation(self):
        path = self.input_file(json.dumps([PRODUCT, "bad"]))
        with patch.object(cli, "generate") as generate, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main([path]), 2)
        generate.assert_not_called()

    def test_generation_failure_does_not_write_partial_batch(self):
        path = self.input_file(json.dumps([PRODUCT, PRODUCT]))
        out = self.root / "result.json"
        out.write_text("previous", encoding="utf-8")
        with patch.object(cli, "generate", side_effect=[RESULT, RuntimeError("provider failed")]):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main([path, "--output", str(out)]), 2)
        self.assertEqual(out.read_text(encoding="utf-8"), "previous")

    def test_renderers_preserve_unicode_and_escape_markdown_table(self):
        item = dict(RESULT, specs=[{"name": "Параметр|тип", "value": "значение\nстрока"}])
        self.assertIn("Термометр", render_json(item))
        markdown = render_markdown(item)
        self.assertIn("Параметр\\|тип", markdown)
        self.assertIn("значение строка", markdown)


if __name__ == "__main__":
    unittest.main()
