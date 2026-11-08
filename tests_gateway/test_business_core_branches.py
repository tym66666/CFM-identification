from copy import deepcopy
import unittest
from evaluation.business_core_cases import fixtures
from evaluation.business_core_branches import FIELDS, branch_schema, expand_branches, evaluate_draft
from tests_gateway.test_business_core_pilot import readable_reference
from tests_gateway.test_business_core_source_refs import reference_ids


def branch_reference(c):
    raw = reference_ids(c["business_question"], readable_reference(c["offline_reference_draft"]))
    raw["targets"] = [{k:v for k,v in t.items() if k in FIELDS[t["kind"]]} for t in raw["targets"]]
    return raw


class BranchTests(unittest.TestCase):
    def test_fixed_plan_schema_cannot_request_arm_states(self):
        schema = branch_schema(fixtures()[2]["business_question"])
        branches = schema["$defs"]["ReadableTarget"]["oneOf"]
        policy = next(b for b in branches if b["properties"]["kind"]["const"] == "fixed_plan")
        self.assertFalse({"situation", "reference", "remaining"} & set(policy["properties"]))
        self.assertFalse(policy["additionalProperties"])

    def test_irrelevant_field_is_rejected_not_silently_deleted(self):
        c = fixtures()[2]
        raw = branch_reference(c)
        raw["targets"][0]["situation"] = {"own": 1}
        with self.assertRaisesRegex(ValueError, "BRANCH_FIELDS_INVALID"):
            expand_branches(raw)

    def test_arm_scope_is_not_inferred_from_company_size(self):
        c = fixtures()[1]
        raw = branch_reference(c)
        raw["targets"][0]["nodes"] = ["01", "02"]
        with self.assertRaises(ValueError):
            expand_branches(raw)

    def test_all_six_offline_branches_reach_expected_real_core(self):
        for c in fixtures():
            with self.subTest(name=c["case_id"]):
                raw = branch_reference(c)
                original = deepcopy(raw)
                result = evaluate_draft(c["business_question"], raw, c["packet"],
                                        synthetic_protocol_selected=True)
                expected = "UNSUPPORTED" if c["case_id"] == "NBIB-008-R20" else "POINT"
                self.assertTrue(all(q["status"] == expected and q["core_called"] for q in result["results"]))
                self.assertEqual(raw, original)
                self.assertFalse(result["production_admission"])


if __name__ == "__main__":
    unittest.main()
