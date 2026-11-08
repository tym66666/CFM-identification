"""Real Core, saved live business readings, and MOCK candidate safety tests."""
import copy
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from cfm_id_llm.orchestration_schemas import canonical_sha256
from examples.materials_candidate_fixture import load_case, synthetic_context
from evaluation import business_candidate_base as candidate
from evaluation import business_materials as materials


class RecordingMock:
    name = "MOCK-CANDIDATE-V035"

    def __init__(self, mutation=None):
        self.calls = []
        self.mutation = mutation

    def generate_json(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        payload, _ = json.JSONDecoder().raw_decode(user_prompt.split("\n", 1)[1])
        result = dict(
            query_id=payload["query_id_exact"], target_sha256=payload["target_sha256_exact"],
            semantics_sha256=payload["semantics_sha256_exact"],
            science_scope_sha256=payload["science_scope_sha256_exact"],
            proposal=dict(
                target_kind=payload["target_kind_exact"], target_description=payload["target_description_exact"],
                claimed_identification="UNDETERMINED", scope="AS_REVIEWED",
                a4_used=dict(source="UNRESOLVED", operator=None, level=None),
                admitted_assumptions_used=[], additional_requirements=[], candidate_expression=None,
                nonidentification_witness=None, reasoning_steps=["The unsupported policy needs further mathematical analysis"],
                caveats=["This mock answer is not a mathematical proof"], suggested_checks=["Check alternatives without assuming exposure sufficiency"]),
            proposed_validation_checks=["Independently verify support, premises and the exact estimand"],
            known_core_coverage_gap="The actual R1b Core does not cover this within-workshop split policy")
        if self.mutation:
            self.mutation(result)
        return result


class TestMaterialsCandidateV035(unittest.TestCase):
    def setUp(self):
        self.item = load_case()
        self.context = synthetic_context(self.item)
        self.provider = RecordingMock()

    def run_case(self, **kw):
        return candidate.evaluate_with_candidates(
            self.item["bundle"], self.item["raw"], self.item["packet"],
            provider=self.provider, context=self.context,
            synthetic_protocol_selected=True, enable_candidates=kw.pop("enable_candidates", True), **kw)

    def test_real_gap_calls_once_preserves_core_and_unverified_boundary(self):
        original = materials.evaluate_draft(self.item["bundle"], self.item["raw"], self.item["packet"],
                                            synthetic_protocol_selected=True)
        r = self.run_case()
        self.assertEqual(r["identification"], original)
        self.assertEqual(r["identification"]["results"][0]["status"], "UNSUPPORTED")
        self.assertEqual(r["candidate_model_calls"], 1)
        self.assertEqual(len(self.provider.calls), 1)
        c = r["candidate_results"][0]
        self.assertEqual((c["status"], c["mode"], c["verification_level"]),
                         ("UNDETERMINED_UNVERIFIED", "TRUSTED_CORE_GAP", "LLM_UNVERIFIED"))
        self.assertIsNone(c["mathematical_certificate"])
        self.assertEqual(r["core_verified_query_count"], 0)
        self.assertEqual(r["unverified_candidate_count"], 1)
        self.assertFalse(r["estimation_handoff_allowed"])
        self.assertFalse(r["policy_called"])

    def test_no_opt_in_never_calls(self):
        self.assertEqual(self.run_case(enable_candidates=False)["candidate_gate"], "CANDIDATE_OPT_IN_REQUIRED")
        self.assertEqual(len(self.provider.calls), 0)

    def test_no_review_never_calls(self):
        self.context = None
        self.assertEqual(self.run_case()["candidate_gate"], "REVIEWED_MATERIALS_CONTEXT_REQUIRED")
        self.assertFalse(self.provider.calls)

    def test_supported_real_core_has_zero_candidate_calls(self):
        self.item = load_case("G32-03")
        r = self.run_case()
        self.assertEqual(r["core_verified_query_count"], 1)
        self.assertEqual(r["candidate_gate"], "NO_ELIGIBLE_CORE_GAP")
        self.assertFalse(self.provider.calls)

    def test_unclear_business_goal_has_zero_candidate_calls(self):
        self.item = load_case("G32-05")
        r = self.run_case()
        self.assertTrue(any(q["status"] == "NEEDS_INPUT" for q in r["identification"]["results"]))
        self.assertFalse(self.provider.calls)

    def test_missing_randomization_independence_has_zero_calls(self):
        self.item = load_case("G32-07")
        r = self.run_case()
        self.assertEqual(r["identification"]["status"], "NEEDS_INPUT")
        self.assertFalse(self.provider.calls)

    def test_materials_review_all_hashes_rechecked(self):
        fields = ["bundle_sha256", "model_draft_sha256", "science_packet_sha256",
                  "gateway_case_sha256", "gateway_quality_sha256", "gateway_review_sha256"]
        for name in fields:
            with self.subTest(name=name):
                self.context = synthetic_context(self.item)
                setattr(self.context.approval, name, "0"*64)
                self.assertEqual(self.run_case()["candidate_gate"], "MATERIALS_CONTEXT_REJECTED")
        self.assertFalse(self.provider.calls)

    def test_mutated_review_flag_rejected(self):
        self.context.approval.reviewed_materials_to_gateway = False
        self.assertEqual(self.run_case()["candidate_gate"], "MATERIALS_CONTEXT_REJECTED")
        self.assertFalse(self.provider.calls)

    def test_unreviewed_query_rejected(self):
        self.context.approval.reviewed_query_ids = ["q2"]
        self.assertEqual(self.run_case()["candidate_gate"], "MATERIALS_CONTEXT_REJECTED")
        self.assertFalse(self.provider.calls)

    def test_injected_mock_core_port_rejected(self):
        self.context = replace(self.context, core_port=object())
        self.assertEqual(self.run_case()["candidate_gate"], "MATERIALS_CONTEXT_REJECTED")
        self.assertFalse(self.provider.calls)

    def test_changed_typed_inquiry_rejected(self):
        b = self.context.core_port.bindings["q1"]
        assumptions = list(b.inquiry.assumptions)
        assumptions[0] = assumptions[0].model_copy(update={"evidence": ["different independent source"]})
        self.context.core_port.bindings["q1"] = replace(b, inquiry=replace(b.inquiry, assumptions=tuple(assumptions)))
        self.assertEqual(self.run_case()["candidate_gate"], "MATERIALS_CONTEXT_REJECTED")
        self.assertFalse(self.provider.calls)

    def test_stale_legacy_crosswalk_rejected_by_real_port(self):
        self.context.core_port.crosswalks["q1"].business_semantics_sha256 = "0"*64
        r = self.run_case()
        self.assertEqual(r["candidate_results"][0]["status"], "BLOCKED")
        self.assertFalse(self.provider.calls)

    def test_core_exception_not_bypassed(self):
        with patch("cfm_id_bridge.bridge.identify_network_business_query", side_effect=RuntimeError("synthetic failure")):
            r = self.run_case()
        self.assertEqual(r["candidate_results"][0]["status"], "BLOCKED")
        self.assertFalse(self.provider.calls)

    def test_fake_saved_gap_cannot_bypass_actual_core(self):
        with patch("cfm_id_bridge.bridge.replay_verified_business_outcome", return_value=False):
            # For the real unsupported query no replay exists; separately forge
            # only the lookup to test reasoner refusal of certificate failure.
            original = self.context.core_port.lookup
            def failed(**kw):
                return original(**kw).model_copy(update={"status": "CORE_VERIFICATION_FAILED", "fallback": "BLOCKED"})
            with patch.object(self.context.core_port, "lookup", side_effect=failed):
                r = self.run_case()
        self.assertEqual(r["candidate_results"][0]["status"], "BLOCKED")
        self.assertFalse(self.provider.calls)

    def test_unadmitted_assumption_rejected(self):
        self.provider = RecordingMock(lambda d: d["proposal"].update(admitted_assumptions_used=["mean_signature_sufficiency"]))
        r = self.run_case()
        self.assertEqual(r["candidate_results"][0]["status"], "REJECTED_UNSAFE_OUTPUT")
        self.assertEqual(r["core_verified_query_count"], 0)

    def test_target_rewrite_rejected(self):
        self.provider = RecordingMock(lambda d: d.update(target_sha256="0"*64))
        self.assertEqual(self.run_case()["candidate_results"][0]["status"], "REJECTED_UNSAFE_OUTPUT")

    def test_explicit_node_full_law_is_usable_without_new_a4(self):
        def reviewed_a4(d):
            d["proposal"]["a4_used"] = dict(source="REVIEWED_OPERATOR", operator="NODE_FULL_LAW", level="NODE_FULL_LAW")
        self.provider = RecordingMock(reviewed_a4)
        r = self.run_case()
        self.assertEqual(r["candidate_results"][0]["status"], "UNDETERMINED_UNVERIFIED")

    def test_missing_a4_level_review_blocks(self):
        self.context.approval.reviewed_a4_levels = {}
        self.assertEqual(self.run_case()["candidate_gate"], "MATERIALS_CONTEXT_REJECTED")
        self.assertFalse(self.provider.calls)

    def test_a4_level_review_cannot_upgrade_node_to_joint_law(self):
        self.context.approval.reviewed_a4_levels = {s: "FULL_JOINT_LAW" for s in self.context.approval.reviewed_a4_levels}
        self.assertEqual(self.run_case()["candidate_gate"], "MATERIALS_CONTEXT_REJECTED")
        self.assertFalse(self.provider.calls)

    def test_fake_certificate_rejected(self):
        self.provider = RecordingMock(lambda d: d.update(mathematical_certificate="FAKE"))
        self.assertEqual(self.run_case()["candidate_results"][0]["status"], "REJECTED_UNSAFE_OUTPUT")

    def test_provider_failure_is_one_attempt_no_message_leak(self):
        def fail(d):
            raise RuntimeError("PRIVATE_SENTINEL")
        self.provider = RecordingMock(fail)
        r = self.run_case()
        self.assertEqual(r["candidate_results"][0]["status"], "PROVIDER_FAILED")
        self.assertEqual(len(self.provider.calls), 1)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(r))

    def test_prompt_contains_exact_design_and_target_no_reference_answer(self):
        self.run_case()
        system, user = self.provider.calls[0]
        extra = json.loads(user.rsplit("\n", 1)[1])
        self.assertEqual(extra["target_assignment"], [1, 1, 1, 0, 0, 0]*4)
        self.assertEqual(len(extra["network_edges"]), 50)
        self.assertEqual(len(extra["assignment_design"]["clusters"]), 4)
        self.assertEqual(extra["target_unit_weights"], ["1/24"]*24)
        for banned in ["gold_status", "expected_result", "scoring_references", "reviewer_confirmed", "science_packet"]:
            self.assertNotIn(banned, user)
        self.assertIn("不是定理证明", system)

    def test_input_objects_not_mutated(self):
        before = canonical_sha256(self.item)
        self.run_case()
        self.assertEqual(canonical_sha256(self.item), before)


if __name__ == "__main__":
    unittest.main()
