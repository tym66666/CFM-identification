"""Synthetic, explicitly admitted illustrative gateway + real-core test fixture.

All population A4/A5 assumptions are *hypothetical* scientist declarations,
not facts inferred from simulated finite-sample CSVs or the LLM.
"""
from __future__ import annotations
from dataclasses import replace

from cfm_id_llm.schemas import (
    BusinessCase, SemanticClaim, EvidenceQuote, DraftProblemSpec, TargetDraft,
    TargetKind, UnitsVariablesDraft, StructureDraft, InformationDesignDraft,
    AssignmentFamily, PopulationInformationLevel,
)
from cfm_id_llm.providers.mock import MockProvider
from cfm_id_llm.multiquery import (
    MultiQueryDraftV09, BusinessInquiryV09, HumanMultiQueryReviewV09,
    approve_multiquery,
)
from cfm_id_llm.multiquery_formulator import MultiQueryFormulatorV09
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_bridge.bridge import ScientificAdmissionV29, FormalQueryBindingV29
from cfm_id_bridge.scientific_binding import (
    ApprovedScienceBindingV291, proposed_binding_snapshot_v291, sha)
from cfm_id_bridge.d1_binding import ReviewedD1ArmPacketV29, prepare_d1_arm_binding_v29

from pfn_pipeline.identification_business import FixedPolicyInquiryV21
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context, declare_network_a4_source,
)
from pfn_pipeline._internal.identification.schemas import Assumption, NetworkExposureSpec
from pfn_pipeline.identification import make_heterogeneous_bernoulli_arm_task
from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED


QUESTION = (
    "本公司有三名销售员A、B、C。三人有固定合作网络：A与B、C合作，B和C没有直接合作，"
    "该网络在实验开始前已确定。上季度我们独立地以各1/2概率给每人开放AI销售助手，"
    "并记录每人是否得到AI权限和每周销售额。公司规定：合作同事中使用AI的人超过一半"
    "才算高使用环境，否则是低使用环境。现在我们想知道销售员A自己未获AI权限、"
    "且处于低使用环境时的平均销售额。同时想知道如果给三人全部开通AI，"
    "团队的平均销售额会怎样。"
)


def claim(quote: str, value: str | None = None):
    assert quote in QUESTION
    return SemanticClaim(value=value or quote, basis="EXPLICIT_TEXT",
                         evidence=[EvidenceQuote(source_id="business_question", quote=quote)])


def case_and_mock_draft():
    case = BusinessCase(case_id="SYNTH_BRIDGE29", business_question=QUESTION)
    own = "销售员A自己未获AI权限、且处于低使用环境时的平均销售额"
    policy = "如果给三人全部开通AI，团队的平均销售额会怎样"
    first = TargetDraft(kind=TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN,
                        description=claim(own))
    second = TargetDraft(kind=TargetKind.FIXED_POLICY_VALUE, description=claim(policy))
    shared = DraftProblemSpec(
        target=first,
        units_variables=UnitsVariablesDraft(
            analysis_unit=claim("三名销售员A、B、C"),
            treatment=claim("给每人开放AI销售助手"),
            outcome=claim("每周销售额"),
        ),
        structure=StructureDraft(
            unit_network=claim("A与B、C合作，B和C没有直接合作"),
            network_pretreatment_status=claim("该网络在实验开始前已确定"),
            exposure_mapping=claim("合作同事中使用AI的人超过一半才算高使用环境，否则是低使用环境"),
        ),
        information_design=InformationDesignDraft(
            assignment_family=AssignmentFamily.INDEPENDENT_BERNOULLI,
            assignment_law=claim("独立地以各1/2概率给每人开放AI销售助手"),
            population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=claim("记录每人是否得到AI权限和每周销售额"),
        ),
    )
    draft = MultiQueryDraftV09(shared_draft=shared, primary_query_id="q1", queries=[
        BusinessInquiryV09(query_id="q1", target=first, business_goal=claim(own)),
        BusinessInquiryV09(query_id="q2", target=second, business_goal=claim(policy)),
    ])
    return case, draft


def reviewed_case():
    case, draft = case_and_mock_draft()
    report = MultiQueryFormulatorV09(MockProvider(draft.model_dump(mode="json"))).formulate(case)
    human = HumanMultiQueryReviewV09(
        case_id=case.case_id, input_sha256=report.input_sha256,
        draft_sha256=report.draft_sha256,
        confirmed_query_ids=["q1", "q2"], reviewed_by="Synthetic study reviewer",
        review_note="Human-confirmed synthetic business target meanings and explicit comparison",
        decision="CONFIRMED")
    return case, approve_multiquery(case, report, human)


def scientist(case: BusinessCase, reviewed, qid: str, family: str) -> ScientificAdmissionV29:
    query = next(q for q in reviewed.report.draft.queries if q.query_id == qid)
    text = ("Node A arm mean under D1 Bernoulli(1/2), strict majority E1, "
            "own treatment 0 and low exposure state 0, conditional on W"
            if qid == "q1" else
            "Full policy value of all treated (1,1,1) with equal weights 1/3, "
            "given a fixed 3-node pretreatment network and contextual W")
    if qid == "q1":
        preview_net=NetworkExposureSpec(network_id="SYNTH_BRIDGE29_GRAPH",
                    node_ids=["A","B","C"], undirected_edges=[("A","B"),("A","C")])
        preview_task=make_heterogeneous_bernoulli_arm_task(
            preview_net,propensities={n:"1/2" for n in "ABC"}, node_id="A",
            own_treatment_value=0, exposure_value=0,
            source="SYNTHETIC_FORMAL_TARGET_PREVIEW",
            evidence="Exact target fingerprint preview in synthetic study",
            admitted=True, query_authority="TRUSTED_FIXTURE", synthetic=True)
        formal_fingerprint=preview_task.target_fingerprint
    else:
        preview_study=demo_study()
        formal_fingerprint=fixed_policy_target_from_context(
             preview_study,(1,1,1),authority="TRUSTED_FIXTURE").target_digest
    return ScientificAdmissionV29(
        formal_target_fingerprint=formal_fingerprint,
        case_id=case.case_id,
        input_sha256=reviewed.report.input_sha256,
        draft_sha256=reviewed.report.draft_sha256,
        query_id=qid, target_sha256=canonical_sha256(query.target),
        formal_family=family, math_target_description=text,
        math_target_crosswalk_confirmed=True,
        scientific_reviewer="Synthetic mathematics domain reviewer",
        evidence_reference="SYNTHETIC_PROTOCOL_SEPARATE_A4_A5_ADMISSION_29",
        a4_population_operator_reference="SYNTHETIC_SYMBOLIC_NODE_FULL_LAW_ASSUMPTION_29",
        a4_scientifically_admitted=True,
        a5_assumption_reference="SYNTHETIC_KNOWN_FULL_VECTOR_RANDOMIZATION_CONSISTENCY_29",
        a5_scientifically_admitted=True,
        scientific_review_note=("This is a hypothetical population identification exercise:"
                                " the source and causal licenses were separately explicitly admitted. "
                                "The finite-sample business narrative does not imply A4."),
        is_synthetic_fixture=True,
    )


def independently_review_fixture(science, inquiry, reviewed, query_id, route):
    """Explicit *synthetic* separate scientific review of the full typed input.

    A real reviewer must compare the worksheet to external source evidence;
    this test helper is not a production scientific auto-approval mechanism.
    """
    q = next(q for q in reviewed.report.draft.queries if q.query_id==query_id)
    sheet=proposed_binding_snapshot_v291(inquiry,
        business_review_sha256=sha(reviewed.human_review),
        target_sha256=canonical_sha256(q.target),
        business_quote=q.target.description.evidence[0].quote,
        a4_reference=science.a4_population_operator_reference,
        a5_reference=science.a5_assumption_reference,
        theorem_route=route,reviewer=science.scientific_reviewer,
        evidence=science.evidence_reference)
    # Separate reviewer action; UNAPPROVED worksheet has no automatic True flags.
    approved=ApprovedScienceBindingV291.model_validate({**sheet,
        'reviewer_confirmed_exact_coordinates':True,
        'reviewer_confirmed_sources_and_licenses':True})
    return science.model_copy(update={'approved_scientific_binding':approved})


def d1_arm_packet(case, reviewed) -> ReviewedD1ArmPacketV29:
    packet=ReviewedD1ArmPacketV29(
        scientific_admission=scientist(case, reviewed, "q1", "R1A_ARM"),
        network_id="SYNTH_BRIDGE29_GRAPH", node_order=["A", "B", "C"],
        undirected_edges=[("A", "B"), ("A", "C")],
        propensities={n: "1/2" for n in "ABC"},
        target_node_id="A", target_own_treatment=0, target_exposure=0,
        protocol_evidence="SYNTHETIC_EXPLICIT_D1_E1_EXPERIMENTAL_DESIGN", outcome_kind="continuous",
    )
    typed=prepare_d1_arm_binding_v29(packet).inquiry
    admission=independently_review_fixture(packet.scientific_admission,typed,reviewed,'q1','R1A_RANDOMIZED_ARM')
    return packet.model_copy(update={'scientific_admission':admission})


def demo_study():
    return declare_network_study(
        network_id="SYNTH_BRIDGE29_GRAPH", node_order=("A", "B", "C"),
        undirected_edges=(("A", "B"), ("A", "C")),
        treatment_variable="ai_access", outcome_variable="sales_amount",
        outcome_kind="continuous", context_reference="W",
        observation_regime="experimental",
        assignment_design={"kind": "heterogeneous_bernoulli_binary_v1",
                           "propensities": {n: "1/2" for n in "ABC"}},
        protocol_provenance="SYNTHETIC_EXPLICIT_RANDOMIZATION",
        network_provenance="SYNTHETIC_FIXED_PRETREATMENT_GRAPH",
        graph_timing_claim="DECLARED_PRETREATMENT_FIXED",
    )


def bindings(case, reviewed):
    d1 = prepare_d1_arm_binding_v29(d1_arm_packet(case, reviewed))
    d1 = replace(d1, business_intent=independently_confirm_business_intent_v292(
        reviewed,'q1',dict(classification='RANDOMIZED_ARM',
        node_order=['A','B','C'], node_id='A',own_treatment=0,exposure_state=0),
        evidence='Synthetic reviewer independently matched node A, untreated, low exposure'))
    d1=replace(d1,evidence_manifest=independently_review_evidence_v292(
        d1.admission,d1.inquiry))
    a = scientist(case, reviewed, "q2", "R1B_FIXED_POLICY")
    study = demo_study()
    target = fixed_policy_target_from_context(study, (1, 1, 1), authority="TRUSTED_FIXTURE")
    source = declare_network_a4_source(study, source_id="SYNTHETIC_POPULATION_NODE_FULL_LAW",
                                       operator="NODE_FULL_LAW", provenance=a.a4_population_operator_reference,
                                       admission="ADMITTED", availability="SYMBOLIC_POPULATION_OPERATOR",
                                       outcome_nodes=study.node_order)
    assumptions = tuple(Assumption(name=name, source="demo_specification",
                                   confirmed=True, evidence=[a.evidence_reference]) for name in REQUIRED)
    inquiry=FixedPolicyInquiryV21(study=study, target=target,
        assumptions=assumptions, r1b_sources=(source,))
    a=independently_review_fixture(a,inquiry,reviewed,'q2','R1B_FULL_ASSIGNMENT')
    policy=FormalQueryBindingV29(a,inquiry,
        independently_confirm_business_intent_v292(reviewed,'q2',
        dict(classification='FIXED_POLICY',node_order=['A','B','C'],
             assignment=[1,1,1],unit_weights=['1/3','1/3','1/3']),
        evidence='Synthetic business reviewer interpreted 全部 as all A B C treated'),
        independently_review_evidence_v292(a,inquiry))
    return d1, policy


def independently_confirm_business_intent_v292(reviewed, query_id, coordinates, *, evidence):
    """Human-authored synthetic business target; MUST NOT be inferred from Core.

    Production callers must build this from the *business* review, not from any
    science packet. `coordinates` below are typed assertions of business meaning.
    """
    from cfm_id_bridge.business_intent import ApprovedBusinessIntentV292
    query=next(q for q in reviewed.report.draft.queries if q.query_id==query_id)
    return ApprovedBusinessIntentV292(
        case_id=reviewed.report.case_id, query_id=query_id,
        input_sha256=reviewed.report.input_sha256,
        draft_sha256=reviewed.report.draft_sha256,
        target_sha256=canonical_sha256(query.target),
        business_review_sha256=sha(reviewed.human_review),
        business_quote=query.business_goal.evidence[0].quote,
        binding_coordinates=coordinates,
        business_reviewer=reviewed.human_review.reviewed_by,
        independent_business_review_evidence=evidence,
        reviewer_confirmed_coordinates=True)


def independently_review_evidence_v292(admission,inquiry):
    """Explicit synthetic evidence ledger; real files and reviewer need external trust."""
    from cfm_id_bridge.evidence import ReviewedScientificEvidenceV292
    from cfm_id_bridge.scientific_binding import actual_scientific_sources,actual_scientific_licenses
    a4='SYNTHETIC ONLY: hypothetical independently stipulated exact population information for '+admission.case_id
    a5='SYNTHETIC ONLY: independently stipulated causal assumptions for '+admission.case_id
    return ReviewedScientificEvidenceV292(
        case_id=admission.case_id,query_id=admission.query_id,
        a4_reference=admission.a4_population_operator_reference,
        a5_reference=admission.a5_assumption_reference,
        a4_typed_sources_digest=sha(actual_scientific_sources(inquiry)),
        a5_typed_licenses_digest=sha(actual_scientific_licenses(inquiry)),
        a4_evidence_record=a4,a5_evidence_record=a5,
        a4_evidence_digest=sha(a4),a5_evidence_digest=sha(a5),
        evidence_reviewer=admission.scientific_reviewer,
        evidence_record_type='HYPOTHETICAL_SYNTHETIC',
        reviewer_confirmed_evidence_link=True)
