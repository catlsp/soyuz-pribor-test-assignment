from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from product_copywriter import service
from product_copywriter.grounding import build_catalog, default_plan, render_plan


PRODUCT = {
    "name": "Измеритель М-24",
    "manufacturer": "Завод Прибор",
    "description": "Измеритель контролирует давление в технологической линии.",
    "specs": {"Питание": "24 В", "Диапазон": "0–10 бар"},
    "expected_fields": ["Питание", "Диапазон", "Интерфейс"],
}


class _Response:
    def __init__(self, body: dict):
        self.body = json.dumps(body, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def _api_response(plan: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(plan, ensure_ascii=False)}}]}


class GroundingTests(unittest.TestCase):
    def test_service_sends_json_plan_request_and_renders_api_plan(self):
        catalog = build_catalog(service.validate_product(PRODUCT))
        plan = default_plan(catalog)
        response = _Response(_api_response(plan))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
             patch.object(service, "_open_request", return_value=response) as opener:
            result = service.generate(PRODUCT)

        self.assertEqual(result["mode"], "LLM")
        self.assertEqual(result["specs"][0], {"name": "Питание", "value": "24 В"})
        request, = opener.call_args.args[:1]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "user"])
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    def test_plan_rejects_free_prose_and_unknown_ids(self):
        product = service.validate_product(PRODUCT)
        catalog = build_catalog(product)
        base = default_plan(catalog)
        hallucinated = dict(base, description="Измеритель имеет сертификат и корпус из нержавеющей стали.")
        unknown_id = dict(base, title_id="invented_title")
        for plan in (hallucinated, unknown_id):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                render_plan(plan, product)

    def test_plan_rejects_duplicates_and_invalid_query_counts(self):
        product = service.validate_product(PRODUCT)
        catalog = build_catalog(product)
        base = default_plan(catalog)
        duplicate_fact = dict(base, fact_order=[base["fact_order"][0]] * len(base["fact_order"]))
        duplicate_query = dict(base, query_ids=[base["query_ids"][0]] * 3)
        too_few = dict(base, query_ids=list(catalog["queries"])[:2])
        available_queries = list(catalog["queries"])
        too_many = dict(base, query_ids=available_queries + [available_queries[0]])
        for plan in (duplicate_fact, duplicate_query, too_few, too_many):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                render_plan(plan, product)

    def test_reordering_changes_copy_without_changing_source_facts(self):
        product = service.validate_product(PRODUCT)
        catalog = build_catalog(product)
        first = default_plan(catalog)
        second = dict(first)
        second["fact_order"] = list(reversed(first["fact_order"]))
        second["advice_order"] = list(reversed(first["advice_order"]))
        a, b = render_plan(first, product), render_plan(second, product)

        self.assertNotEqual(a["description"], b["description"])
        for result in (a, b):
            self.assertIn("24 В", result["description"])
            self.assertNotIn("24 А", result["description"])
            self.assertEqual(result["specs"][0]["value"], "24 В")
            self.assertNotIn("сертификат", result["description"].casefold())

    def test_sparse_demo_and_very_long_source_stay_within_output_bounds(self):
        sparse = service.generate({"name": "Простой прибор"}, demo=True)
        self.assertOutputBounds(sparse)
        self.assertIn("manufacturer", sparse["missing_fields"])
        self.assertIn("description", sparse["missing_fields"])

        long_key = "Параметр " + "К" * 700
        long_value = "Значение " + "В" * 700
        source = {
            "name": "Название " + "М" * 400,
            "manufacturer": "Производитель " + "П" * 700,
            "description": "Исходный текст " + "Т" * 5000,
            "specs": {long_key: long_value, "Питание": "24 В"},
            "expected_fields": ["Питание"],
        }
        result = service.generate(source, demo=True)
        self.assertOutputBounds(result)
        rows = {row["name"]: row["value"] for row in result["specs"]}
        self.assertEqual(rows[long_key], long_value)
        self.assertEqual(rows["Питание"], "24 В")
        self.assertLessEqual(len(result["commercial_block"]), 600)

    def assertOutputBounds(self, result):
        self.assertLessEqual(len(result["seo_title"]), 70)
        self.assertGreaterEqual(len(result["description"]), 800)
        self.assertLessEqual(len(result["description"]), 1200)
        self.assertGreaterEqual(len(result["queries"]), 3)
        self.assertLessEqual(len(result["queries"]), 5)

    def test_all_oversized_source_fields_keep_a_valid_catalog(self):
        source = {
            "name": "М" * 400, "manufacturer": "П" * 400,
            "description": "Т" * 500, "specs": {"К" * 200: "В" * 200},
            "expected_fields": [],
        }
        result = service.generate(source, demo=True)
        self.assertOutputBounds(result)
        self.assertIn(source["name"], result["queries"][0])
        self.assertEqual(result["specs"], [{"name": "К" * 200, "value": "В" * 200}])


if __name__ == "__main__":
    unittest.main()
