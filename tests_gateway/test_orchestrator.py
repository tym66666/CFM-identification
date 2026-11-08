from __future__ import annotations
import copy
import unittest
from pydantic import ValidationError
from cfm_id_llm import BusinessCase, GatewayV02, HumanReviewV02, ProblemFormulator
from cfm_id_llm.audit import audit_draft
from cfm_id_llm.formulator import DraftValidationError
from cfm_id_llm.mock_core import MockCorePort, MockCoreScenario
from cfm_id_llm.orchestrator import ConfirmationError, confirm_formulation, route_formulation
from cfm_id_llm.orchestration_schemas import (
    ConfirmedProblemV02, CoreDecisionV02, CoreReplayV02, OrchestrationReportV02, canonical_sha256,
)
from cfm_id_llm.providers import MockProvider
from tests_gateway.support import case_and_draft


def case_report(name="complete_formulation_demo"):
    case, raw = case_and_draft(name)
    c = BusinessCase.model_validate(case)
    r = ProblemFormulator(MockProvider(raw)).formulate(c)
    return c, r


def approved(report, **kwargs):
    fields = dict(
        input_sha256=report.input_sha256, draft_sha256=canonical_sha256(report.draft),
        reviewed_by="researcher-test", decision="CONFIRMED",
        review_note="Read protocol and check the full mathematical formulation",
        admitted_assumptions=["full_vector_randomization"],
    )
    fields.update(kwargs)
    return HumanReviewV02(**fields)


def point_core(**kwargs):
    data = dict(status="POINT", route_id="DEMO_R1A",
                identified_expression="E[Yobs|Ti=1,Si=1,W]",
                certificate={"mock_only": "not a mathematical proof"})
    data.update(kwargs)
    return MockCorePort(MockCoreScenario(**data))


class TestOnlyProductionPort:
    """Contract simulation ONLY. This does not exercise any real identification theorem."""
    mode = "PRODUCTION"
    def __init__(self, scenario):
        self.mock = MockCorePort(scenario)
    def describe_capabilities(self):
        return self.mock.describe_capabilities()
    def identify(self, problem):
        return self.mock.identify(problem)
    def replay_verify(self, problem, result):
        reply = self.mock.replay_verify(problem, result)
        return reply.model_copy(update={"verifier_id": "TEST_ONLY_dummy_replay_contract"})


class RoutingV02Tests(unittest.TestCase):
    def test_old_v01_report_stays_compatible(self):
        case, report = case_report()
        self.assertEqual(report.schema_version, "cfm-id-draft-v0.1")
        self.assertEqual(report.mathematical_verification, "NOT_PERFORMED")
        self.assertEqual(route_formulation(case, report).status, "AWAITING_HUMAN_REVIEW")

    def test_ambiguous_case_never_calls_core_even_if_review_supplied(self):
        case, report = case_report("sales_ambiguous")
        core = point_core()
        result = route_formulation(case, report, human_review=approved(report), core=core)
        self.assertEqual(result.status, "NEEDS_CLARIFICATION")
        self.assertEqual(result.fallback, "BLOCKED_NEEDS_INPUT")
        self.assertEqual(core.identify_calls, 0)
        self.assertTrue(result.next_steps)

    def test_no_implicit_confirmation(self):
        case, report = case_report()
        core = point_core()
        result = route_formulation(case, report, core=core)
        self.assertEqual(result.status, "AWAITING_HUMAN_REVIEW")
        self.assertEqual(core.identify_calls, 0)

    def test_explicit_confirmation_binds_the_case_and_draft(self):
        case, report = case_report()
        confirmed = confirm_formulation(case, report, approved(report))
        self.assertIsInstance(confirmed, ConfirmedProblemV02)
        self.assertEqual(confirmed.draft_sha256, canonical_sha256(report.draft))
        self.assertEqual(confirmed.human_review.admitted_assumptions, ["full_vector_randomization"])
        self.assertEqual(len(confirmed.fingerprint()), 64)

    def test_unchecked_assumptions_remain_unadmitted(self):
        case, report = case_report()
        review = approved(report, admitted_assumptions=[])
        confirmed = confirm_formulation(case, report, review)
        self.assertFalse(confirmed.human_review.admitted_assumptions)
        self.assertTrue(all(a.status in ("PROPOSED", "UNRESOLVED") for a in confirmed.draft.assumptions))

    def test_unknown_admitted_assumption_rejected(self):
        case, report = case_report()
        with self.assertRaises(ConfirmationError):
            confirm_formulation(case, report, approved(report, admitted_assumptions=["fake_exposure_sufficiency"]))

    def test_changed_case_rejected_even_if_report_says_ready(self):
        case, report = case_report()
        changed = case.model_copy(update={"business_question": case.business_question + " changed"})
        with self.assertRaises(ConfirmationError):
            route_formulation(changed, report, human_review=approved(report))

    def test_mutated_draft_invalidates_review(self):
        case, report = case_report()
        changed = report.model_copy(deep=True)
        changed.draft.normalization_notes.append("New interpretation")
        with self.assertRaises(ConfirmationError):
            confirm_formulation(case, changed, approved(report))

    def test_report_status_edit_cannot_bypass_readiness(self):
        case, report = case_report("sales_ambiguous")
        modified = report.model_copy(update={"review_status": "DRAFT_READY_FOR_HUMAN_REVIEW", "issues": []})
        with self.assertRaises(ConfirmationError):
            confirm_formulation(case, modified, approved(report))
        self.assertEqual(route_formulation(case, modified).status, "NEEDS_CLARIFICATION")

    def test_review_approval_cannot_be_from_untrusted_llm_schema(self):
        case, report = case_report()
        data=approved(report).model_dump(mode="json")
        data["decision"] = "AUTO_CONFIRMED_BY_LLM"
        with self.assertRaises(ValidationError):
            HumanReviewV02.model_validate(data)

    def test_confirmed_without_core_is_not_unsupported(self):
        case, report = case_report()
        result = route_formulation(case, report, human_review=approved(report))
        self.assertEqual(result.status, "NO_CORE_CONNECTED")
        self.assertEqual(result.fallback, "BLOCKED_NO_CORE")
        self.assertIsNotNone(result.confirmed_problem_sha256)

    def test_mock_point_is_never_verification(self):
        case, report = case_report()
        core = point_core()
        result = route_formulation(case, report, human_review=approved(report), core=core)
        self.assertEqual(result.status, "MOCK_CORE_RESULT")
        self.assertEqual(result.verification_level, "MOCK_ONLY")
        self.assertEqual(result.candidate_math_claim, "POINT")
        self.assertEqual(core.identify_calls, 1)
        self.assertEqual(core.replay_calls, 1)
        self.assertFalse(result.estimation_handoff_allowed)

    def test_mock_unsupported_does_not_prove_non_identification(self):
        case, report = case_report()
        core=MockCorePort(MockCoreScenario(status="UNSUPPORTED"))
        result = route_formulation(case, report, human_review=approved(report), core=core)
        self.assertEqual(result.status, "MOCK_CORE_RESULT")
        self.assertEqual(result.core_status, "UNSUPPORTED")
        self.assertIsNone(result.candidate_math_claim)
        self.assertEqual(result.fallback, "MOCK_ONLY")

    def test_needs_input_never_enters_fallback(self):
        case, report = case_report()
        core=MockCorePort(MockCoreScenario(status="NEEDS_INPUT", missing_requirements=["A4: node arm means"]))
        result=route_formulation(case, report, human_review=approved(report), core=core)
        self.assertEqual(result.fallback, "BLOCKED_NEEDS_INPUT")
        self.assertEqual(result.next_steps, ["A4: node arm means"])

    def test_mismatched_core_problem_fingerprint_fails_closed(self):
        case, report=case_report()
        core=point_core(corrupt_problem_binding=True)
        r=route_formulation(case, report, human_review=approved(report), core=core)
        self.assertEqual(r.status,"CORE_BINDING_FAILED")
        self.assertEqual(r.verification_level,"FAILED")
        self.assertEqual(core.replay_calls,0)

    def test_replay_rejection_and_binding_fails_closed(self):
        case, report=case_report()
        for overrides in ({"replay_accept":False}, {"corrupt_replay_binding":True},
                          {"corrupt_replay_decision_binding":True}):
            with self.subTest(overrides=overrides):
                core=point_core(**overrides)
                r=route_formulation(case, report, human_review=approved(report), core=core)
                self.assertEqual(r.status,"CORE_VERIFICATION_FAILED")
                self.assertEqual(r.fallback,"BLOCKED_SAFETY_FAILURE")
                self.assertIsNone(r.candidate_math_claim)

    def test_unknown_route_in_claim_is_rejected(self):
        case, report=case_report()
        core=point_core(route_id="EXTERNAL_UNKNOWN")
        r=route_formulation(case,report,human_review=approved(report),core=core)
        self.assertEqual(r.status,"CORE_BINDING_FAILED")
        self.assertEqual(core.replay_calls,0)

    def test_mathematical_claim_requires_actual_certificate_field(self):
        with self.assertRaises(ValidationError):
            CoreDecisionV02(status="POINT", problem_sha256="a"*64,
                            route_id="DEMO_R1A", identified_expression="dummy")

    def test_unsupported_must_not_carry_unsafe_math_expression(self):
        with self.assertRaises(ValidationError):
            CoreDecisionV02(status="UNSUPPORTED", problem_sha256="a"*64,
                            identified_expression="UNVERIFIED")

    def test_contract_fallback_only_for_real_unsupported(self):
        case, report=case_report()
        for status, expected_flow, expected_fallback in (
            ("UNSUPPORTED", "CORE_UNSUPPORTED", "ELIGIBLE_NOT_IMPLEMENTED"),
            ("NEEDS_INPUT", "CORE_NEEDS_INPUT", "BLOCKED_NEEDS_INPUT"),
            ("NO_ADAPTER", "CORE_NO_ADAPTER", "BLOCKED_SAFETY_FAILURE"),
            ("INCOMPATIBLE", "CORE_INCOMPATIBLE", "BLOCKED_SAFETY_FAILURE"),
            ("ERROR", "CORE_ERROR", "BLOCKED_SAFETY_FAILURE"),
        ):
            with self.subTest(status=status):
                core=TestOnlyProductionPort(MockCoreScenario(status=status))
                r=route_formulation(case,report,human_review=approved(report),core=core)
                self.assertEqual((r.status, r.fallback), (expected_flow, expected_fallback))
                self.assertEqual(r.verification_level, "NOT_PERFORMED")
                self.assertIsNone(r.candidate_math_claim)

    def test_a_future_real_adapter_requires_replay_before_core_verified(self):
        # This TEST DOUBLE validates the plumbing, not actual mathematical truth.
        case, report=case_report()
        core=TestOnlyProductionPort(MockCoreScenario(
            status="POINT", route_id="DEMO_R1A", identified_expression="symbolic_dummy",
            certificate={"test": "synthetic_non_proof"}))
        r=route_formulation(case,report,human_review=approved(report),core=core)
        self.assertEqual(r.status,"CORE_VERIFIED")
        self.assertEqual(r.verification_level,"CORE_REPLAY_VERIFIED")
        self.assertFalse(r.estimation_handoff_allowed)
        self.assertEqual(core.mock.replay_calls,1)

    def test_output_schema_rejects_verification_without_verification_state(self):
        case, report=case_report()
        with self.assertRaises(ValidationError):
            OrchestrationReportV02(case_id=case.case_id, input_sha256=report.input_sha256,
                                   draft_sha256=canonical_sha256(report.draft),
                                   status="MOCK_CORE_RESULT", explanation="x",
                                   verification_level="CORE_REPLAY_VERIFIED")

    def test_facade_keeps_formulator_and_router_separate(self):
        case, raw=case_and_draft("complete_formulation_demo")
        gateway=GatewayV02(MockProvider(raw))
        result=gateway.run(BusinessCase.model_validate(case))
        self.assertEqual(result.formulation.review_status,"DRAFT_READY_FOR_HUMAN_REVIEW")
        self.assertEqual(result.routing.status,"AWAITING_HUMAN_REVIEW")

    def test_json_round_trip(self):
        case,report=case_report()
        core=point_core()
        r=route_formulation(case,report,human_review=approved(report),core=core)
        out=OrchestrationReportV02.model_validate_json(r.model_dump_json())
        self.assertEqual(out,r)


if __name__ == "__main__": unittest.main()
