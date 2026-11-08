from copy import deepcopy
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_target_provenance import evaluate_draft, target_sources, project
from evaluation.business_core_pilot_base import canonical_hash
from tests_gateway.test_business_materials_independence import reference


class TargetProvenanceTests(unittest.TestCase):
    def test_generic_protocol_cannot_replace_target_statement(self):
        c = fixtures()[8]; raw = reference(c)
        raw["questions"]["q1"]["first"]["remaining_source"] = "study_protocol.md:L3"
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "TARGET_STATEMENT_SOURCE_REQUIRED")

    def test_paraphrase_does_not_require_fixed_tokens(self):
        c = deepcopy(fixtures()[8])
        c["bundle"]["documents"]["target_clarification.txt"] = c["bundle"]["documents"]["target_clarification.txt"].replace(
            "其他站点仍遵循原两组抽签规则，在满足上述条件的方案中平均。",
            "别的站点怎么抽仍照试点的办法；只在符合前面情形的抽签结果里，按各结果本来的可能性取平均。")
        c["packet"]["bundle_sha256"] = canonical_hash(c["bundle"])
        raw = reference(c)
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["results"][0]["status"], "POINT")
        self.assertTrue(r["results"][0]["certificate_replay"])
        self.assertIn("target_clarification.txt:L3", target_sources(c["bundle"]))

    def test_unknown_operation_retains_partial_without_entering_core(self):
        c = fixtures()[8]; raw = reference(c)
        raw["questions"]["q1"]["operation"] = "不明确"
        before = deepcopy(raw)
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(raw, before)
        self.assertEqual(r["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(r["results"][0]["core_called"])
        self.assertEqual(r["partial_scenarios_pending_operation"]["q1"]["first"], raw["questions"]["q1"]["first"])
        self.assertEqual(r["model_draft_sha256"], canonical_hash(raw))

    def test_partial_unknown_node_still_rejected(self):
        c = fixtures()[8]; raw = reference(c)
        raw["questions"]["q1"].update(operation="不明确",
            first=dict(setting="完整安排", treated=dict(selection="指定", ids=["invented"])))
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "UNKNOWN_NODE_ID")

    def test_partial_invalid_source_still_rejected(self):
        c = fixtures()[8]; raw = reference(c)
        raw["questions"]["q1"]["operation"] = "不明确"
        raw["questions"]["q1"]["first"]["remaining_source"] = "missing:L1"
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "TARGET_STATEMENT_SOURCE_REQUIRED")

    def test_missing_remaining_statement_never_filled(self):
        c = fixtures()[8]; raw = reference(c)
        raw["questions"]["q1"]["first"]["remaining_source"] = None
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(r["results"][0]["core_called"])

    def test_no_science_packet_cannot_be_promoted_by_complete_target(self):
        c = deepcopy(fixtures()[8]); raw = reference(c)
        c["packet"]["science"] = dict(population_information=None, causal_licenses=None)
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(r["results"][0]["core_called"])

    def test_all_existing_explicit_targets_and_decisions_unchanged(self):
        from evaluation.business_materials_independence import project as old_project, evaluate_draft as old_eval
        for c in fixtures():
            raw = reference(c)
            self.assertEqual(project(c["bundle"], raw), old_project(c["bundle"], raw))
            a = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
            b = old_eval(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(a["results"], b["results"])


if __name__ == "__main__":
    unittest.main()
