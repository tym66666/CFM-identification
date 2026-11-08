"""SYNTHETIC test-scientist reviews for frozen, previously observed business drafts.

Not a production approval service. The G32-08 policy is checked against an
independently specified 24-line / first-three-per-workshop target before review.
"""
import json
from pathlib import Path
from dataclasses import replace

from cfm_id_llm.schemas import (
    BusinessCase, SemanticClaim, EvidenceQuote, TargetDraft, TargetKind,
    DraftProblemSpec, UnitsVariablesDraft, StructureDraft, InformationDesignDraft,
    AssignmentFamily, PopulationInformationLevel,
)
from cfm_id_llm.quality import (
    BusinessInquiryV010, MultiQueryDraftV010, QuerySemanticsV010, audit_business_quality,
)
from cfm_id_llm.candidate_queries import BusinessQueryReviewV011
from cfm_id_llm.trusted_core import (
    RealCoreCoveragePortV012, ApprovedBusinessMathCrosswalkV012,
    unapproved_crosswalk_worksheet_v012, v29_review_from_v011,
)
from cfm_id_llm.multiquery import approve_multiquery
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_bridge.bridge import ScientificAdmissionV29, FormalQueryBindingV29, formal_target_fingerprint_v29
from cfm_id_bridge.scientific_binding import scientific_target_coordinates
from examples.llm_core_fixture import (
    independently_review_fixture, independently_confirm_business_intent_v292,
    independently_review_evidence_v292,
)
from evaluation.business_candidate_base import MaterialsCandidateApprovalV035, ReviewedMaterialsContextV035
from evaluation.business_materials import project
from evaluation.business_materials_base import compile_inquiry
from evaluation.business_core_pilot_base import canonical_hash

DATA = Path(__file__).resolve().parents[1] / "assets/candidate_material_fixtures/materials_cases.json"


def load_case(case_id="G32-08"):
    return json.loads(DATA.read_text(encoding="utf8"))["cases"][case_id]


def synthetic_context(item):
    if item["case_id"] != "G32-08":
        raise ValueError("This explicit synthetic review covers G32-08 only")
    bundle, raw, packet = item["bundle"], item["raw"], item["packet"]
    _, d, targets = project(bundle, raw)
    t = targets[0]
    nodes = [f"F_{i:02d}" for i in range(1, 25)]
    treated = [n for i, n in enumerate(nodes) if i % 6 < 3]
    if (len(targets) != 1 or t.kind != "fixed_plan" or t.nodes != nodes
            or t.treated_nodes != treated or t.aggregation != "equal_mean"
            or d != packet["study"] or packet["bundle_sha256"] != canonical_hash(bundle)):
        raise ValueError("Does not match independently specified synthetic business intention")
    inquiry = compile_inquiry(d, t, bundle, packet["science"])
    coords = scientific_target_coordinates(inquiry)
    assert coords["assignment"] == [int(n in treated) for n in nodes]
    assert coords["unit_weights"] == ["1/24"] * 24

    text = "\n".join(bundle["documents"].values())
    case = BusinessCase(case_id="SYNTHETIC_MATERIALS_G32_08", business_question=text)
    def cl(quote):
        assert quote in text
        return SemanticClaim(value=quote, basis="EXPLICIT_TEXT",
                             evidence=[EvidenceQuote(source_id="business_question", quote=quote)])
    protocol = bundle["documents"]["study_protocol.md"].splitlines()
    goal = bundle["question_slots"]["q1"]
    target = TargetDraft(kind=TargetKind.FIXED_POLICY_VALUE, description=cl(goal))
    shared = DraftProblemSpec(
        target=target,
        units_variables=UnitsVariablesDraft(analysis_unit=cl("24条产线"),
            treatment=cl("预警工具"), outcome=cl("downtime_hours表示每条产线八周内的停机小时")),
        structure=StructureDraft(unit_network=cl(protocol[0]),
            network_pretreatment_status=cl("试验前固定的协作联系"),
            exposure_mapping=cl(protocol[2])),
        information_design=InformationDesignDraft(
            assignment_family=AssignmentFamily.CLUSTER_RANDOMIZATION,
            assignment_law=cl(protocol[1]),
            population_information_level=PopulationInformationLevel.UNRESOLVED),
    )
    query = BusinessInquiryV010(query_id="q1", target=target, business_goal=cl(goal),
        semantics=QuerySemanticsV010(
            target_population=cl("所有24条产线都计入"), intervention=cl("每个车间三条线用工具、其余三条不用"),
            aggregation=cl("每条线的分量一样"), policy_assignment=cl(goal)))
    quality = audit_business_quality(case,
        MultiQueryDraftV010(shared_draft=shared, primary_query_id="q1", queries=[query]),
        provider="SYNTHETIC_REVIEW_OF_SAVED_LIVE_DRAFT", prompt_version="materials-candidate-fixture-v035")
    review = BusinessQueryReviewV011(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.draft_sha256, confirmed_query_ids=["q1"],
        reviewed_by="Synthetic independent business reviewer", decision="CONFIRMED",
        review_note="Synthetic independent review of the original 24-line half-per-workshop policy; not a real approval")
    reviewed = approve_multiquery(case, quality.legacy_audit,
        v29_review_from_v011(review, legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    science = ScientificAdmissionV29(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256, query_id="q1",
        target_sha256=canonical_sha256(target), formal_family="R1B_FIXED_POLICY",
        formal_target_fingerprint=formal_target_fingerprint_v29(inquiry),
        math_target_description="All 24 production lines equally weighted under the explicit half_each_workshop allocation",
        math_target_crosswalk_confirmed=True, scientific_reviewer="Synthetic test scientist",
        evidence_reference="SYNTHETIC_G32_08_INDEPENDENT_PROTOCOL",
        a4_population_operator_reference=packet["science"]["population_information"],
        a4_scientifically_admitted=True, a5_assumption_reference=packet["science"]["causal_licenses"],
        a5_scientifically_admitted=True,
        scientific_review_note="Hypothetical population law and randomization licenses; no exposure mean sufficiency is admitted",
        is_synthetic_fixture=True)
    science = independently_review_fixture(science, inquiry, reviewed, "q1", "R1B_FULL_ASSIGNMENT")
    intent = independently_confirm_business_intent_v292(reviewed, "q1",
        dict(classification="FIXED_POLICY", node_order=nodes,
             assignment=[int(n in treated) for n in nodes], unit_weights=["1/24"]*24),
        evidence="Independent synthetic original-goal check: every workshop first three lines enabled, other three disabled")
    evidence = independently_review_evidence_v292(science, inquiry)
    binding = FormalQueryBindingV29(science, inquiry, intent, evidence)
    worksheet = unapproved_crosswalk_worksheet_v012(case=case, quality=quality,
        business_review=review, query_id="q1", formal_binding=binding,
        reviewer="Synthetic independent crosswalk reviewer",
        evidence="Explicit test-scientist comparison against original policy table and independent science packet")
    # TEST ONLY: all approvals in this example are hypothetical fixture assertions.
    worksheet.update(reviewer_confirmed_business_to_math=True, reviewer_confirmed_a4_a5_and_route=True)
    port = RealCoreCoveragePortV012(bindings={"q1": binding},
        crosswalks={"q1": ApprovedBusinessMathCrosswalkV012.model_validate(worksheet)})
    approval = MaterialsCandidateApprovalV035(
        bundle_sha256=canonical_hash(bundle), model_draft_sha256=canonical_hash(raw),
        science_packet_sha256=canonical_hash(packet), gateway_case_sha256=canonical_sha256(case),
        gateway_quality_sha256=canonical_sha256(quality), gateway_review_sha256=review.fingerprint(),
        reviewed_query_ids=["q1"], reviewer="Synthetic independent materials reviewer",
        reviewed_a4_levels={s.source_id: PopulationInformationLevel.NODE_FULL_LAW for s in inquiry.r1b_sources},
        review_evidence="Reviewed saved live draft and original business wording against independent 24-line target",
        reviewed_materials_to_gateway=True, synthetic_fixture=True)
    return ReviewedMaterialsContextV035(case, quality, review, port, approval)
