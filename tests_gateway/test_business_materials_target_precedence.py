import json
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_target_precedence import make_request, evaluate_draft, project
from tests_gateway.test_business_materials_plan_references import reference


class ActiveTargetTests(unittest.TestCase):
    def test_current_target_and_old_background_are_explicitly_separate(self):
        c = fixtures()[7]; _, user = make_request(c["bundle"]); m = json.loads(user)
        self.assertEqual(m["document_roles"]["target_clarification.txt"], "CURRENT_TARGET")
        self.assertEqual(m["document_roles"]["business_question.md"], "ORIGINAL_BUSINESS_BACKGROUND_NOT_CURRENT_TARGET")
        self.assertIn("candidate_policies.csv", m["finite_table_summaries"])

    def test_level_extra_reference_is_rejected_not_erased(self):
        c = fixtures()[7]; raw = reference(c)
        raw["questions"]["q1"]["second"] = dict(setting="完整安排", treated=dict(selection="全体"))
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "LEVEL_MUST_NOT_HAVE_REFERENCE")
        self.assertIsNotNone(raw["questions"]["q1"]["second"])

    def test_missing_exposure_citation_is_not_auto_filled(self):
        c = fixtures()[6]; raw = reference(c); raw["study"]["exposure_source"] = None
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(r["results"][0]["core_called"])

    def test_original_goal_role_and_existing_target_coordinates_unchanged(self):
        from evaluation.business_materials_plan_references import project as old
        for c in fixtures():
            self.assertEqual(project(c["bundle"], reference(c)), old(c["bundle"], reference(c)))
            if c["variant"] == "original":
                _, user = make_request(c["bundle"])
                self.assertEqual(json.loads(user)["document_roles"]["business_question.md"], "CURRENT_TARGET")


if __name__ == "__main__":
    unittest.main()
