from copy import deepcopy
import unittest

from evaluation.business_core_cases import fixtures
from evaluation.business_reading_provenance import output_schema, project, evaluate_draft
from tests_gateway.test_business_reading_base import reading_reference


def reference(case):
    r = reading_reference(case)
    for q in r["questions"].values():
        for name in ("first", "second"):
            if q[name] is not None:
                q[name].pop("source")
    return r


class AnchoredReadingTests(unittest.TestCase):
    def test_schema_references_resolve_and_six_outputs_replay(self):
        for i, c in enumerate(fixtures()):
            with self.subTest(case=c["case_id"]):
                raw = reference(c)
                original = deepcopy(raw)
                schema = output_schema(c["business_question"])
                def check_refs(value):
                    if isinstance(value, dict):
                        if "$ref" in value:
                            self.assertTrue(value["$ref"].startswith("#/$defs/"))
                            self.assertIn(value["$ref"].split("/")[-1], schema["$defs"])
                        for item in value.values():
                            check_refs(item)
                    elif isinstance(value, list):
                        for item in value:
                            check_refs(item)
                check_refs(schema)
                self.assertEqual(set(schema["properties"]["questions"]["required"]), set(raw["questions"]))
                result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
                self.assertEqual(raw, original)
                self.assertTrue(all(r["core_called"] for r in result["results"]))
                self.assertTrue(all(r["certificate_replay"] for r in result["results"] if r["status"] == "POINT"))
                self.assertEqual(result["results"][0]["status"], "UNSUPPORTED" if i == 3 else "POINT")

    def test_scenario_provenance_is_original_question_not_definition(self):
        c = fixtures()[0]
        result, _ = project(c["business_question"], reference(c))
        for t in result["targets"]:
            self.assertEqual(t["situation"]["quote"], t["question_quote"])
            self.assertEqual(t["reference"]["quote"], t["question_quote"])

    def test_wrapper_or_model_source_is_not_silently_repaired(self):
        c = fixtures()[0]
        for wrapper in (True, False):
            raw = reference(c)
            q = next(iter(raw["questions"].values()))
            if wrapper:
                q["first"] = {"local_condition": q["first"]}
            else:
                q["first"]["source"] = "s04"
            result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(result["status"], "REJECTED")
            self.assertEqual(result["results"], [])

    def test_missing_target_does_not_get_a_new_generated_slot(self):
        c = fixtures()[0]
        raw = reference(c)
        raw["questions"].pop(next(iter(raw["questions"])))
        result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
