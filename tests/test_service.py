from __future__ import annotations

import json
import math
import os
import urllib.error
import unittest
from unittest.mock import patch

from product_copywriter import models, service
from product_copywriter.formatting import render_markdown


PRODUCT = {
    "name": "Прибор М-7",
    "manufacturer": "Тестприбор",
    "description": "Прибор для контроля параметров процесса.",
    "specs": {"Диапазон измерений": "0,5–10 мм", "Питание": "24 В"},
}


class ServiceTests(unittest.TestCase):
    def test_demo_preserves_input_specs_and_marks_absent_fields(self):
        result = service.generate(PRODUCT, demo=True)
        self.assertEqual(result["specs"][:2], [
            {"name": "Диапазон измерений", "value": "0,5–10 мм"},
            {"name": "Питание", "value": "24 В"},
        ])
        self.assertIn("Класс точности", result["missing_fields"])
        self.assertIn("Тип корпуса", result["missing_fields"])
        self.assertEqual(result["mode"], "DEMO — не LLM")
        self.assertTrue(result["description"].endswith("."))
        self.assertTrue(800 <= len(result["description"]) <= 1200)
        self.assertLessEqual(len(result["seo_title"]), 70)
        self.assertGreaterEqual(len(result["queries"]), 3)
        self.assertLessEqual(len(result["queries"]), 5)
        self.assertIn("DEMO — не LLM", render_markdown(result))

    def test_blank_and_null_specs_are_reported_missing(self):
        product = dict(PRODUCT, specs={"Диапазон измерений": "  ", "Питание": None})
        result = service.generate(product, demo=True)
        self.assertEqual(result["specs"][0]["value"], "данных нет")
        self.assertIn("Диапазон измерений", result["missing_fields"])
        self.assertIn("Питание", result["missing_fields"])

    def test_boolean_and_nonfinite_spec_values_are_rejected(self):
        for invalid in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid), self.assertRaises(models.ProductValidationError):
                models.validate_product(dict(PRODUCT, specs={"x": invalid}))

    def test_valid_decimal_comma_input_and_output_are_accepted(self):
        normalized = models.validate_product(dict(PRODUCT, specs={"Шаг": "0,5 мм"}))
        self.assertEqual(normalized["specs"]["Шаг"], "0,5 мм")
        answer = {
            "seo_title": "М-7 — прибор для контроля",
            "description": "Точная величина 0,5 подтверждена входными данными. " + "А" * 850,
            "commercial_block": "Запросите предложение для предприятия.",
            "queries": ["прибор М-7", "купить прибор М-7", "М-7 для производства"],
        }
        validated = models.validate_output(answer, normalized)
        self.assertEqual(validated["specs"][0]["value"], "0,5 мм")

    def test_unknown_numeric_value_is_rejected(self):
        product = models.validate_product(dict(PRODUCT, specs={"Номинал": "5 В"}))
        answer = {
            "seo_title": "Прибор М-7",
            "description": "Неподтверждённый параметр 777. " + "Описание. " * 100,
            "commercial_block": "Запросите предложение.",
            "queries": ["прибор М-7", "купить М-7", "М-7 промышленный"],
        }
        with self.assertRaisesRegex(ValueError, "числовое значение"):
            models.validate_output(answer, product)

    def test_missing_api_key_is_clear_and_safe(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                service.generate(PRODUCT)

    def test_http_unauthorized_error_does_not_leak_response_or_key(self):
        secret = "super-secret-token"
        error = urllib.error.HTTPError("https://api.test", 401, "unauthorized", {}, None)
        error.read = lambda: b"private provider response"
        with patch.dict(os.environ, {"OPENAI_API_KEY": secret}), patch.object(service, "_open_request", side_effect=error):
            with self.assertRaises(RuntimeError) as raised:
                service.generate(PRODUCT)
        self.assertNotIn(secret, str(raised.exception))
        self.assertNotIn("private provider response", str(raised.exception))
        self.assertIn("401", str(raised.exception))

    def test_rate_limit_retries_are_bounded(self):
        error = urllib.error.HTTPError("https://api.test", 429, "busy", {}, None)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}), \
             patch.object(service, "_open_request", side_effect=error) as opener, \
             patch.object(service.time, "sleep") as sleep:
            with self.assertRaises(RuntimeError):
                service.generate(PRODUCT)
        self.assertEqual(opener.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_timeout_is_sanitized(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}), \
             patch.object(service, "_open_request", side_effect=TimeoutError("socket detail")):
            with self.assertRaises(RuntimeError) as raised:
                service.generate(PRODUCT)
        self.assertNotIn("socket detail", str(raised.exception))

    def test_malformed_api_envelope_is_sanitized(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps({"choices": None}).encode()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}), \
             patch.object(service, "_open_request", return_value=Response()):
            with self.assertRaises(RuntimeError) as raised:
                service.generate(PRODUCT)
        self.assertNotIn("Traceback", str(raised.exception))

    def test_invalid_model_json_gets_one_correction_retry(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}), \
             patch.object(service, "_call_api", side_effect=[ValueError("invalid output"), ValueError("still invalid")]) as call:
            with self.assertRaises(RuntimeError):
                service.generate(PRODUCT)
        self.assertEqual(call.call_count, 2)


if __name__ == "__main__":
    unittest.main()
