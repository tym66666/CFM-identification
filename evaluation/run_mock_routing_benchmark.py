"""v0.2 offline routing regression; NOT real mathematical or LLM evaluation."""
from __future__ import annotations
import json
from cfm_id_llm import BusinessCase, ProblemFormulator, HumanReviewV02, route_formulation
from cfm_id_llm.mock_core import MockCoreScenario, MockCorePort
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.providers import MockProvider
from tests_gateway.support import case_and_draft


def run():
    c,raw=case_and_draft("complete_formulation_demo")
    case=BusinessCase.model_validate(c)
    report=ProblemFormulator(MockProvider(raw)).formulate(case)
    review=HumanReviewV02(
        input_sha256=report.input_sha256,
        draft_sha256=canonical_sha256(report.draft),
        reviewed_by="OFFLINE_TEST_FIXTURE", decision="CONFIRMED",
        review_note="Not a real human review: mock routing regression fixture",
        admitted_assumptions=[],
    )
    cases = [
      ("no_review", None, MockCoreScenario(status="UNSUPPORTED"), "AWAITING_HUMAN_REVIEW", "NOT_EVALUATED"),
      ("no_core", review, None, "NO_CORE_CONNECTED", "BLOCKED_NO_CORE"),
      ("point_mock", review, MockCoreScenario(status="POINT", route_id="DEMO_R1A", identified_expression="MOCK expr",certificate={"test":True}), "MOCK_CORE_RESULT", "MOCK_ONLY"),
      ("unsupported_mock", review, MockCoreScenario(status="UNSUPPORTED"), "MOCK_CORE_RESULT", "MOCK_ONLY"),
      ("needs_input", review, MockCoreScenario(status="NEEDS_INPUT", missing_requirements=["A4 missing"]), "MOCK_CORE_RESULT", "BLOCKED_NEEDS_INPUT"),
      ("replay_rejected", review, MockCoreScenario(status="POINT", route_id="DEMO_R1A", identified_expression="MOCK expr",certificate={"test":True}, replay_accept=False), "CORE_VERIFICATION_FAILED", "BLOCKED_SAFETY_FAILURE"),
      ("wrong_problem", review, MockCoreScenario(status="POINT", route_id="DEMO_R1A", identified_expression="MOCK expr",certificate={"test":True},corrupt_problem_binding=True),"CORE_BINDING_FAILED","BLOCKED_SAFETY_FAILURE"),
    ]
    detail=[]
    for name, human, scenario, expected, fallback in cases:
        core=MockCorePort(scenario) if scenario else None
        outcome=route_formulation(case,report,human_review=human,core=core)
        passed=(outcome.status==expected and outcome.fallback==fallback and
                outcome.estimation_handoff_allowed is False and
                outcome.verification_level != "CORE_REPLAY_VERIFIED")
        detail.append({"case":name,"expected":expected,"got":outcome.status,"fallback":outcome.fallback,"pass":passed})
    # Ambiguous case cannot be routed even if Core fixture exists.
    c2,raw2=case_and_draft("sales_ambiguous")
    ca=BusinessCase.model_validate(c2)
    ra=ProblemFormulator(MockProvider(raw2)).formulate(ca)
    dummy=MockCorePort(MockCoreScenario(status="UNSUPPORTED"))
    a=route_formulation(ca,ra,core=dummy)
    detail.append({"case":"ambiguous","expected":"NEEDS_CLARIFICATION", "got":a.status,
                   "fallback":a.fallback,"pass":a.status=="NEEDS_CLARIFICATION" and dummy.identify_calls==0})
    return {"fixture_cases":len(detail), "passed":sum(x['pass'] for x in detail),
            "scope":"Mock routing invariants ONLY, NOT real theorem correctness or real LLM accuracy",
            "details":detail}


if __name__ == '__main__':
    result=run()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['passed']!=result['fixture_cases']:
        raise SystemExit(1)
