from copy import deepcopy
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_conditional_sources import evaluate_draft, conditional_sources
from tests_gateway.test_business_materials_independence import reference


class ConditionalSourceTests(unittest.TestCase):
    def test_plain_design_protocol_cannot_stand_in_for_conditional_target(self):
        c = fixtures()[8]
        raw = reference(c); raw["questions"]["q1"]["first"]["remaining_source"] = "study_protocol.md:L3"
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "CONDITIONAL_AVERAGING_SOURCE_REQUIRED")
        self.assertEqual(r["results"], [])

    def test_original_sources_do_not_invent_a_conditional_target(self):
        for c in fixtures()[:3]:
            self.assertEqual(conditional_sources(c["bundle"]), {})
        c = fixtures()[0]; raw = reference(c)
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertFalse(any(q["core_called"] for q in r["results"]))

    def test_all_explicit_fixtures_remain_unchanged(self):
        from evaluation.business_materials_independence import evaluate_draft as old
        for c in fixtures():
            a = old(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
            b = evaluate_draft(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(a["results"], b["results"])

    def test_unknown_reference_or_implicit_wording_is_not_filled(self):
        c = fixtures()[8]
        b = deepcopy(c["bundle"])
        b["documents"]["target_clarification.txt"] = b["documents"]["target_clarification.txt"].replace(
            "其他站点仍遵循原两组抽签规则，在满足上述条件的方案中平均。", "其他安排照旧。")
        self.assertEqual(conditional_sources(b), {})


if __name__ == "__main__":
    unittest.main()
