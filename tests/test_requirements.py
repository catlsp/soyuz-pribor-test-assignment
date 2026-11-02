"""Regression tests for behavior promised by the input and API contracts."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from product_copywriter import models, service


class InputContractTests(unittest.TestCase):
    def test_optional_nulls_and_empty_values_are_normalized_as_missing(self):
        product = models.validate_product({
            "name": "Прибор П-1",
            "manufacturer": None,
            "description": None,
            "specs": {"Питание": None, "Диапазон": "  "},
        })

        self.assertEqual(product["manufacturer"], "")
        self.assertEqual(product["description"], "")
        self.assertEqual(product["specs"]["Питание"], None)
        rows, missing = models.deterministic_specs(product)
        self.assertEqual({r["name"]: r["value"] for r in rows}["Питание"], "данных нет")
        self.assertIn("Питание", missing)
        self.assertIn("manufacturer", missing)
        self.assertIn("description", missing)


class ApiTransportTests(unittest.TestCase):
    def test_invalid_credential_fails_without_leaking_it_or_sending_request(self):
        credential = "private-key-value\ninvalid-header"
        with patch.dict(os.environ, {"OPENAI_API_KEY": credential}), \
             patch.object(service, "_open_request") as opener:
            with self.assertRaises(RuntimeError) as raised:
                service.generate({"name": "Прибор"})
        self.assertNotIn("private-key-value", str(raised.exception))
        opener.assert_not_called()

    def test_connection_reset_is_reported_without_transport_details_or_traceback(self):
        secret_detail = "private socket endpoint detail"
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}), \
             patch.object(service, "_open_request", side_effect=ConnectionResetError(secret_detail)):
            with self.assertRaises(RuntimeError) as raised:
                service.generate({"name": "Прибор П-1"})

        message = str(raised.exception)
        self.assertNotIn(secret_detail, message)
        self.assertNotIn("Traceback", message)


class OutputContractTests(unittest.TestCase):
    def test_invalid_seo_lengths_and_query_counts_are_rejected(self):
        product = models.validate_product({"name": "Прибор"})
        valid = {
            "seo_title": "Прибор", "description": "Описание. " * 90,
            "commercial_block": "Для специалиста по подбору; задачи применения: данных нет.",
            "queries": ["прибор", "купить прибор", "прибор характеристики"],
        }
        models.validate_output(valid, product)
        for field, value in (
            ("seo_title", "А" * 71), ("description", "А" * 799),
            ("description", "А" * 1201), ("queries", ["один", "два"]),
            ("queries", ["а", "б", "в", "г", "д", "е"]),
        ):
            with self.subTest(field=field, length=len(value)), self.assertRaises(ValueError):
                models.validate_output(dict(valid, **{field: value}), product)


if __name__ == "__main__":
    unittest.main()
