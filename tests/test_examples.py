"""Keep the submitted current examples consistent with source facts and limits."""
import json
import unittest
from pathlib import Path

from product_copywriter.grounding import build_catalog
from product_copywriter.models import validate_output, validate_product


class SubmittedExamplesTests(unittest.TestCase):
    def test_live_examples_obey_source_catalog_and_all_output_constraints(self):
        root = Path(__file__).resolve().parents[1]
        inputs = json.loads((root / "examples/inputs.json").read_text(encoding="utf-8-sig"))
        outputs = json.loads((root / "examples/results.llm.checked.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(len(inputs), len(outputs))
        self.assertEqual(len(outputs), 2)
        for source, result in zip(inputs, outputs):
            product = validate_product(source)
            prose = {key: result[key] for key in ("seo_title", "description", "queries", "commercial_block")}
            self.assertEqual(validate_output(prose, product), result)
            catalog = build_catalog(product)
            self.assertIn(result["seo_title"], catalog["titles"].values())
            self.assertIn(result["commercial_block"], catalog["commercial"].values())
            self.assertTrue(all(query in catalog["queries"].values() for query in result["queries"]))
            remaining = result["description"]
            clauses = [*catalog["facts"].values(), *catalog["advice"].values()]
            while remaining:
                matches = [clause for clause in clauses if remaining.startswith(clause)]
                self.assertTrue(matches, "Submitted prose contains an unapproved clause")
                remaining = remaining[len(max(matches, key=len)):].lstrip()


if __name__ == "__main__":
    unittest.main()
