import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_remaining_declaration import evaluate_draft, project
from tests_gateway.test_business_materials_independence import reference as old_reference


def reference(c):
    raw = old_reference(c)
    for q in raw["questions"].values():
        refs = [w.pop("remaining_source") for w in (q["first"], q["second"])
                if isinstance(w, dict) and w.get("setting") == "局部条件"]
        assert not refs or all(r == refs[0] for r in refs)
        q["remaining_source"] = refs[0] if refs else None
    return raw


class SharedRemainingTests(unittest.TestCase):
    def test_shared_explicit_rule_preserves_all_existing_coordinates(self):
        from evaluation.business_materials_singleton_population import project as old_project
        for c in fixtures():
            self.assertEqual(project(c["bundle"], reference(c)), old_project(c["bundle"], old_reference(c)))

    def test_shared_rule_does_not_need_duplicate_llm_answers(self):
        c = fixtures()[-1]; raw = reference(c)
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["results"][0]["status"], "POINT")
        self.assertTrue(r["results"][0]["certificate_replay"])
        self.assertNotIn("remaining_source", raw["questions"]["q1"]["second"])

    def test_missing_shared_rule_is_not_filled_from_design(self):
        c = fixtures()[-1]; raw = reference(c)
        raw["questions"]["q1"]["remaining_source"] = None
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(r["results"][0]["core_called"])

    def test_missing_field_or_old_per_scenario_answer_rejected(self):
        c = fixtures()[-1]
        r = evaluate_draft(c["bundle"], old_reference(c), c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "QUESTION_REMAINING_SOURCE_REQUIRED")
        raw = reference(c)
        raw["questions"]["q1"]["first"]["remaining_source"] = raw["questions"]["q1"]["remaining_source"]
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "DUPLICATE_REMAINING_DECLARATION")

    def test_fixed_plan_does_not_accept_inapplicable_remaining_rule(self):
        c = fixtures()[4]; raw = reference(c)
        raw["questions"]["q1"]["remaining_source"] = "target_clarification.txt:L1"
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "REMAINING_DECLARATION_WITHOUT_CONDITIONAL_SCENARIO")


if __name__ == "__main__":
    unittest.main()
