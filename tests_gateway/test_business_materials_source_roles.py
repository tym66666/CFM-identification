import json
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_source_roles import make_request, evaluate_draft
from tests_gateway.test_business_materials_independence import reference


class SourceRoleTests(unittest.TestCase):
    def test_protocol_allowed_for_design_not_goal_citations(self):
        c = fixtures()[5]
        _, user = make_request(c["bundle"])
        m = json.loads(user)
        self.assertIn("study_protocol.md:L3", m["source_role_rules"]["study_fields_use_all_materials"])
        self.assertNotIn("study_protocol.md:L3", m["source_role_rules"]["only_question_population_and_remaining_use_target_document"])

    def test_prompt_clarification_does_not_fill_missing_model_declaration(self):
        c = fixtures()[5]; raw = reference(c)
        raw["study"]["declared_independent"] = None
        raw["study"]["independence_source"] = None
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["status"], "NEEDS_INPUT")
        self.assertEqual(r["results"], [])


if __name__ == "__main__":
    unittest.main()
