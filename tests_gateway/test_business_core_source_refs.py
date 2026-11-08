from copy import deepcopy
import unittest
from evaluation.business_core_cases import fixtures
from evaluation.business_core_pilot import numeric_projection
from evaluation.business_core_pilot_base import ModelDraft, target_coordinates
from evaluation.business_core_source_refs import (
    source_catalog, resolve_sources, evaluate_draft, reference_schema)
from tests_gateway.test_business_core_pilot import readable_reference


def reference_ids(question, readable):
    catalog = source_catalog(question)
    def visit(value):
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if k == "quote" or k.endswith("_quote"):
                    name = "source" if k == "quote" else k[:-6] + "_source"
                    matches = [ref for ref, text in catalog.items() if v is not None and v in text]
                    if v is not None and len(matches) != 1:
                        raise ValueError("Test reference must be uniquely grounded")
                    out[name] = None if v is None else matches[0]
                else:
                    out[k] = visit(v)
            return out
        if isinstance(value, list):
            return [visit(v) for v in value]
        return value
    return visit(readable)


class SourceReferenceTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures()[0]
        self.question = self.case["business_question"]
        self.raw = reference_ids(self.question, readable_reference(self.case["offline_reference_draft"]))

    def test_source_catalog_preserves_exact_text_and_schema_uses_ids(self):
        self.assertEqual("".join(source_catalog(self.question).values()), self.question)
        defs = reference_schema(self.question)["$defs"]
        self.assertIn("question_source", defs["ReadableTarget"]["properties"])
        self.assertNotIn("question_quote", defs["ReadableTarget"]["properties"])
        self.assertIn("enum", defs["ReadableState"]["properties"]["source"])

    def test_all_six_fixtures_have_unchanged_semantic_targets(self):
        for c in fixtures():
            raw = reference_ids(c["business_question"], readable_reference(c["offline_reference_draft"]))
            projected = ModelDraft.model_validate(numeric_projection(resolve_sources(c["business_question"], raw)))
            expected = ModelDraft.model_validate(c["offline_reference_draft"])
            self.assertEqual([target_coordinates(t) for t in projected.targets],
                             [target_coordinates(t) for t in expected.targets])

    def test_unknown_reference_and_generated_quote_rejected(self):
        raw = deepcopy(self.raw)
        raw["targets"][0]["reference"]["source"] = "s999"
        with self.assertRaisesRegex(ValueError, "SOURCE_REFERENCE_NOT_FOUND"):
            resolve_sources(self.question, raw)
        raw = deepcopy(self.raw)
        raw["targets"][0]["reference"]["quote"] = "拼接文字"
        with self.assertRaisesRegex(ValueError, "GENERATED_QUOTE"):
            resolve_sources(self.question, raw)

    def test_complete_original_sentence_replaces_reference_not_model_words(self):
        resolved = resolve_sources(self.question, self.raw)
        r = resolved["targets"][0]
        self.assertEqual(r["situation"]["quote"], r["reference"]["quote"])
        self.assertIn(r["reference"]["quote"], self.question)
        result = evaluate_draft(self.question, self.raw, self.case["packet"], synthetic_protocol_selected=True)
        self.assertTrue(all(q["certificate_replay"] for q in result["results"]))
        self.assertFalse(result["semantic_correctness_verified"])


if __name__ == "__main__":
    unittest.main()
