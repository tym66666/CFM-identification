import copy
import json
import unittest
from fractions import Fraction
from pydantic import ValidationError
from examples.materials_candidate_fixture import load_case, synthetic_context
from evaluation.business_candidate_base import candidate_math_context
from evaluation import business_candidate_schedule as wrapper
from evaluation.witness_schedule import inspect_two_worlds, TwoWorldScheduleV037
from tests_gateway.test_business_candidate_base import RecordingMock


def witness_for(math):
    n = len(math["node_order"])
    return dict(schema_version="two-world-schedule-v0.37", node_order=math["node_order"],
        world_a=dict(default_outcomes=["0"]*n, overrides=[]),
        world_b=dict(default_outcomes=["0"]*n, overrides=[
            dict(assignment=math["target_assignment"], outcomes=["1"]*n)]))


def set_nonpoint(candidate):
    p = candidate["proposal"]
    p.update(claimed_identification="NOT_POINT",
        a4_used=dict(source="REVIEWED_OPERATOR", operator="NODE_FULL_LAW", level="NODE_FULL_LAW"),
        nonidentification_witness=dict(
            world_a="Synthetic zero schedule across all assignments.",
            world_b="Synthetic second schedule explicitly provided in the attachment.",
            why_observables_match="Compare all supported assignments exactly.",
            why_targets_differ="Evaluate the declared weighted target in both worlds."))


class ScheduleMock:
    name = "MOCK-V037"
    def __init__(self, mutation=None, unknown=False):
        self.mutation, self.unknown = mutation, unknown
        self.calls = []
    def generate_json(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        c = RecordingMock().generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        math = json.loads(user_prompt.split(wrapper.MATH_MARKER, 1)[1])
        if not self.unknown:
            set_nonpoint(c)
        env = dict(schema_version="candidate-envelope-v0.37", candidate=c,
                   two_world_schedule=None if self.unknown else witness_for(math))
        if self.mutation:
            self.mutation(env)
        return env


class WitnessScheduleTests(unittest.TestCase):
    def setUp(self):
        self.item = load_case()
        self.context = synthetic_context(self.item)
        self.math = candidate_math_context(self.context.core_port.bindings["q1"].inquiry)
        # A fixture proposal for the standalone arithmetic diagnostic.
        self.proposal = dict(proposal=dict(
            claimed_identification="NOT_POINT", scope="AS_REVIEWED",
            additional_requirements=[], target_kind="FIXED_POLICY_VALUE",
            a4_used=dict(source="REVIEWED_OPERATOR", operator="NODE_FULL_LAW", level="NODE_FULL_LAW")))
        self.witness = witness_for(self.math)

    def check(self):
        return inspect_two_worlds(self.math, self.proposal, self.witness)

    def test_valid_full_schedules_pass_all_16_support_assignments(self):
        r = self.check()
        self.assertEqual(r["status"], "PASSED_EXACT_CONSTRUCTION")
        self.assertEqual(r["assignments_checked"], 16)
        self.assertEqual(r["support_probability_sum"], "1")
        self.assertEqual((r["theta_a"], r["theta_b"]), ("0", "1"))
        self.assertFalse(r["core_certified"])
        self.assertFalse(r["full_candidate_text_verified"])
        self.assertIsNone(r["mathematical_certificate"])

    def test_global_shift_detected_even_with_same_randomization(self):
        self.witness["world_b"] = dict(default_outcomes=["1"]*24, overrides=[])
        r = self.check()
        self.assertEqual(r["status"], "OBSERVABLE_LAWS_DIFFER")
        self.assertTrue(any(not row["equal"] for row in r["support_rows"]))

    def test_equal_targets_detected(self):
        self.witness["world_b"] = copy.deepcopy(self.witness["world_a"])
        self.assertEqual(self.check()["status"], "TARGETS_EQUAL")

    def test_difference_on_just_one_supported_assignment_is_detected(self):
        self.witness["world_b"]["overrides"].append(dict(assignment=[0]*24, outcomes=["1"]*24))
        self.assertEqual(self.check()["status"], "OBSERVABLE_LAWS_DIFFER")

    def test_no_interference_or_mean_sufficiency_is_not_assumed(self):
        for extra in ("no_interference", "mean_signature_sufficiency"):
            with self.subTest(extra=extra):
                changed = copy.deepcopy(self.math)
                changed["a5_admitted_names"].append(extra)
                self.assertEqual(inspect_two_worlds(changed, self.proposal, self.witness)["status"], "UNSUPPORTED_SCOPE")

    def test_missing_randomization_license_rejected(self):
        self.math["a5_admitted_names"].remove("full_vector_randomization")
        self.assertEqual(self.check()["status"], "UNSUPPORTED_SCOPE")

    def test_conditional_claim_cannot_be_checked_as_reviewed(self):
        self.proposal["proposal"].update(scope="IF_ADDITIONAL_REQUIREMENTS",
            additional_requirements=[dict(kind="A5_ASSUMPTION",description="no interference",why_needed="for another claim")])
        self.assertEqual(self.check()["status"], "UNSUPPORTED_SCOPE")

    def test_unresolved_or_unapproved_a4_rejected(self):
        self.proposal["proposal"]["a4_used"]["source"] = "UNRESOLVED"
        self.assertEqual(self.check()["status"], "UNSUPPORTED_SCOPE")

    def test_actual_observed_value_information_not_overwritten_by_counterexample(self):
        self.math["a4_operators"][0]["availability"] = "OBSERVED_NUMERIC_OPERATOR"
        self.assertEqual(self.check()["status"], "UNSUPPORTED_SCOPE")

    def test_no_artifact_is_explicitly_unchecked(self):
        self.witness = None
        self.assertEqual(self.check()["status"], "NO_ARTIFACT")

    def test_duplicate_override_rejected(self):
        self.witness["world_b"]["overrides"] *= 2
        self.assertEqual(self.check()["status"], "INVALID_ARTIFACT")

    def test_boolean_float_and_code_are_not_rational_schedule_inputs(self):
        for bad in (True, 0.0, "__import__('os')", "1/0", "NaN", "1e999"):
            with self.subTest(bad=bad):
                w = copy.deepcopy(self.witness)
                w["world_b"]["default_outcomes"][0] = bad
                self.assertEqual(inspect_two_worlds(self.math, self.proposal, w)["status"], "INVALID_ARTIFACT")

    def test_boolean_assignment_is_not_binary_integer(self):
        self.witness["world_b"]["overrides"][0]["assignment"][0] = True
        self.assertEqual(self.check()["status"], "INVALID_ARTIFACT")

    def test_vector_width_and_node_order_checked(self):
        w = copy.deepcopy(self.witness)
        w["world_b"]["default_outcomes"].pop()
        self.assertEqual(inspect_two_worlds(self.math, self.proposal, w)["status"], "INVALID_ARTIFACT")
        self.witness["node_order"] = list(reversed(self.math["node_order"]))
        self.assertEqual(self.check()["status"], "BINDING_MISMATCH")

    def test_negative_or_out_of_range_downtime_is_not_accepted(self):
        for value in ("-1", "2"):
            self.witness["world_b"]["default_outcomes"][0] = value
            self.assertEqual(self.check()["status"], "INVALID_INPUT")

    def test_target_and_weights_are_used_exactly(self):
        self.math["target_unit_weights"] = ["1/2","1/2"] + ["0"]*22
        self.witness["world_b"]["overrides"][0]["outcomes"] = ["1"]+["0"]*23
        self.assertEqual(self.check()["theta_b"], "1/2")
        self.math["target_unit_weights"] = ["0","1"]+["0"]*22
        self.assertEqual(self.check()["status"], "TARGETS_EQUAL")

    def test_target_on_support_cannot_use_the_off_support_fixture(self):
        self.math["target_assignment"] = [0]*24
        self.assertEqual(self.check()["status"], "TARGETS_EQUAL")

    def test_overlapping_clusters_and_bad_probability_rejected(self):
        self.math["assignment_design"]["clusters"][0].append("F_07")
        self.assertEqual(self.check()["status"], "UNSUPPORTED_SCOPE")

    def test_changed_target_is_not_replaced_by_artifact_target(self):
        self.math["target_assignment"] = [0,1]*12
        self.assertEqual(self.check()["status"], "TARGETS_EQUAL")

    def test_unknown_outcome_domain_fails_closed(self):
        self.math["outcome"] = "binary_purchase"
        self.assertEqual(self.check()["status"], "UNSUPPORTED_SCOPE")


class ScheduleIntegrationTests(unittest.TestCase):
    def run_case(self, provider, case="G32-08", **kw):
        item = load_case(case)
        return wrapper.evaluate_with_candidates(item["bundle"], item["raw"], item["packet"],
            context=synthetic_context(load_case()), provider=provider,
            enable_candidates=kw.pop("enable_candidates", True),
            synthetic_protocol_selected=True, **kw)

    def test_real_core_and_structured_mock_keep_certification_separate(self):
        p = ScheduleMock()
        r = self.run_case(p)
        self.assertEqual(len(p.calls), 1)
        self.assertEqual(r["identification"]["results"][0]["status"], "UNSUPPORTED")
        self.assertEqual(r["candidate_results"][0]["status"], "UNVERIFIED_CANDIDATE")
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"], "PASSED_EXACT_CONSTRUCTION")
        self.assertEqual(r["core_verified_query_count"], 0)
        self.assertEqual(r["mathematical_candidate_verification"], "NOT_PERFORMED")
        self.assertFalse(r["estimation_handoff_allowed"])

    def test_rejected_identity_cannot_run_witness_checker(self):
        p = ScheduleMock(lambda e: e["candidate"].update(target_sha256="0"*64))
        r = self.run_case(p)
        self.assertEqual(r["candidate_results"][0]["status"], "REJECTED_UNSAFE_OUTPUT")
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"], "BLOCKED_CANDIDATE_REJECTED")

    def test_extra_envelope_field_not_silently_trimmed(self):
        r = self.run_case(ScheduleMock(lambda e: e.update(mathematical_certificate="fake")))
        self.assertEqual(r["candidate_envelope_errors"][0]["code"], "INVALID_V037_ENVELOPE")
        self.assertEqual(r["candidate_results"][0]["status"], "PROVIDER_FAILED")
        self.assertFalse(r["schedule_diagnostics"])

    def test_unknown_is_allowed_without_structured_witness(self):
        r = self.run_case(ScheduleMock(unknown=True))
        self.assertEqual(r["candidate_results"][0]["status"], "UNDETERMINED_UNVERIFIED")
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"], "NO_ARTIFACT")

    def test_bad_math_does_not_promote_core_or_repair_candidate(self):
        def shift(e):
            e["two_world_schedule"]["world_b"] = dict(default_outcomes=["1"]*24, overrides=[])
        r = self.run_case(ScheduleMock(shift))
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"], "OBSERVABLE_LAWS_DIFFER")
        self.assertEqual(r["candidate_results"][0]["status"], "UNVERIFIED_CANDIDATE")
        self.assertEqual(r["candidate_envelopes"]["q1"]["two_world_schedule"]["world_b"]["default_outcomes"], ["1"]*24)
        self.assertEqual(r["core_verified_query_count"], 0)

    def test_supported_or_missing_input_cases_do_not_call_llm(self):
        for case in ("G32-03","G32-05","G32-07"):
            p=ScheduleMock()
            self.run_case(p,case)
            self.assertFalse(p.calls)

    def test_opt_in_required(self):
        p=ScheduleMock()
        self.run_case(p,enable_candidates=False)
        self.assertFalse(p.calls)

    def test_prompt_exposes_new_schema_preserves_original_cross_field_rules(self):
        p=ScheduleMock(unknown=True)
        self.run_case(p)
        system,user=p.calls[0]
        self.assertIn("CandidateEnvelopeV037",system)
        self.assertNotIn("输出严格符合 CandidateProposalV011 JSON Schema 的唯一 JSON 对象",system)
        schema,_=json.JSONDecoder().raw_decode(user.split(wrapper.SCHEMA_MARKER,1)[1])
        self.assertIn("two_world_schedule",schema["required"])
        self.assertIn("allOf",schema["$defs"]["CandidateDraftV03"])
        self.assertIn("allOf",schema["$defs"]["CandidateA4UseV03"])
        self.assertNotIn("world_a(z)=0",system+user)
        self.assertNotIn("OFF_SUPPORT_REVIEW_AID",system+user)


if __name__ == "__main__":
    unittest.main()

