from copy import deepcopy
import json
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_base import evaluate_draft as old
from evaluation.business_materials_file_roles import evaluate_draft, make_request


def reference(c):
    r = deepcopy(c["reading_reference"])
    for k in ("network_file", "partition_file", "group_column"):
        r["study"].pop(k)
    r["study"]["declared_independent"] = r["study"].pop("draws_independent")
    return r


class DeclarationReadingTests(unittest.TestCase):
    def test_all_ten_mock_decisions_unchanged(self):
        for c in fixtures():
            a = old(c["bundle"], c["reading_reference"], c["packet"], synthetic_protocol_selected=True)
            b = evaluate_draft(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(a["status"], b["status"])
            self.assertEqual(a["results"], b["results"])

    def test_model_cannot_override_file_bindings(self):
        c = fixtures()[0]
        r = reference(c); r["study"]["partition_file"] = "cluster_randomization.csv"
        self.assertEqual(evaluate_draft(c["bundle"], r, c["packet"], synthetic_protocol_selected=True)["status"], "REJECTED")

    def test_declared_independent_does_not_grant_scientific_admission(self):
        c = fixtures()[0]
        self.assertTrue(reference(c)["study"]["declared_independent"])
        r = evaluate_draft(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
        self.assertFalse(any(q["core_called"] for q in r["results"]))

    def test_schema_removes_redundant_file_choice_and_retains_strict_enum(self):
        c = fixtures()[0]
        system, user = make_request(c["bundle"]); data = json.loads(user)
        self.assertNotIn("partition_file", data["output_schema"]["properties"]["study"]["properties"])
        self.assertEqual(data["validated_file_bindings"]["partition_file"], "units.csv")
        self.assertIn("不会取消", system)
        self.assertNotIn("没有发券的门店", data["output_schema"]["$defs"]["Selection"]["properties"]["selection"]["enum"])


if __name__ == "__main__":
    unittest.main()
