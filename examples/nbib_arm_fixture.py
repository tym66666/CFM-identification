"""Explicit synthetic reviewer for NBIB-003-single-store, not production."""
from examples.materials_candidate_fixture import *
from evaluation.business_core_pilot_base import target_coordinates

def load_case():
    """Offline reference only; never a replacement for a live model output."""
    import copy
    from evaluation.nbib_acceptance import DATA,material_input
    ref=json.loads((DATA/"research_only/formal_references.json").read_text(encoding="utf8"))["NBIB-003-single-store"]
    bundle=material_input("NBIB-003-single-store")
    raw=copy.deepcopy(ref["raw_reading"])
    raw["questions"]["q1"]["remaining_evidence_span"]=bundle["documents"]["target_clarification.txt"].splitlines()[2]
    return dict(case_id="NBIB-003-single-store",bundle=bundle,raw=raw,packet=ref["science_packet"])

def synthetic_context(item,spec=None):
    bundle,raw,packet=item["bundle"],item["raw"],item["packet"]
    if item["case_id"]!="NBIB-003-single-store":raise ValueError("SINGLE_CASE_FIXTURE_ONLY")
    _,d,targets=project(bundle,raw)
    expected=dict(kind="arm",nodes=["unit_037"],aggregation="single",situation=[0,1],
        reference=None,remaining="original_randomization",treated_nodes=None,unresolved=[])
    if (len(targets)!=1 or target_coordinates(targets[0])!=expected or d!=packet["study"]
        or packet["bundle_sha256"]!=canonical_hash(bundle)):
        raise ValueError("Live reading differs from independently declared original target/design")
    inquiry=compile_inquiry(d,targets[0],bundle,packet["science"])
    text="\n".join(bundle["documents"].values())
    case=BusinessCase(case_id="SYNTHETIC_REVIEW_NBIB003_ARM",business_question=text)
    def cl(quote):
        assert quote in text,quote
        return SemanticClaim(value=quote,basis="EXPLICIT_TEXT",evidence=[EvidenceQuote(source_id="business_question",quote=quote)])
    goal=bundle["question_slots"]["q1"]
    target=TargetDraft(kind=TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN,description=cl(goal))
    shared=DraftProblemSpec(target=target,units_variables=UnitsVariablesDraft(
        analysis_unit=cl("72家门店"),treatment=cl("新会员券"),outcome=cl("store_revenue")),
        structure=StructureDraft(unit_network=cl("门店之间的转介网络"),
            network_pretreatment_status=cl("试验前冻结的无向协作边"),
            exposure_mapping=cl("邻店中至少一家发券记作高暴露")),
        information_design=InformationDesignDraft(assignment_family=AssignmentFamily.CLUSTER_RANDOMIZATION,
            assignment_law=cl("每个商圈以独立50%概率整体入选"),
            population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl("所有 CSV 都是有确定随机种子的仿真样本")))
    query=BusinessInquiryV010(query_id="q1",target=target,business_goal=cl(goal),semantics=QuerySemanticsV010(
        target_population=cl("只评价名册中编号为unit_037的那家门店"),
        intervention=cl("这家店自己不发券"),neighbor_exposure=cl("相邻门店至少一家发券"),
        aggregation=cl("它的平均营业额"),
        standardization_distribution=cl("其余门店的安排仍按原商圈抽签规则，在满足这些条件的方案中平均")))
    quality=audit_business_quality(case,MultiQueryDraftV010(shared_draft=shared,primary_query_id="q1",queries=[query]),
        provider="SYNTHETIC_INDEPENDENT_ARM_REVIEW",prompt_version="nbib-reviewed-arm-v0431")
    review=BusinessQueryReviewV011(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.draft_sha256,
        confirmed_query_ids=["q1"],reviewed_by="Synthetic independent business reviewer",decision="CONFIRMED",
        review_note="Frozen unit_037 untreated/any-neighbor-treated target with original conditional randomization; hypothetical fixture")
    reviewed=approve_multiquery(case,quality.legacy_audit,v29_review_from_v011(review,legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    science=ScientificAdmissionV29(case_id=case.case_id,input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256,query_id="q1",target_sha256=canonical_sha256(target),formal_family="R1A_ARM",
        formal_target_fingerprint=formal_target_fingerprint_v29(inquiry),
        math_target_description="The unit_037 untreated, any-neighbor-treated arm mean under the original cluster assignment conditional law",
        math_target_crosswalk_confirmed=True,scientific_reviewer="Synthetic independent scientist",
        evidence_reference="SYNTHETIC_NBIB003_ARM_PROTOCOL_V0431",
        a4_population_operator_reference=packet["science"]["population_information"],a4_scientifically_admitted=True,
        a5_assumption_reference=packet["science"]["causal_licenses"],a5_scientifically_admitted=True,
        scientific_review_note="Hypothetical population operator and randomization licenses. Not inferred from finite CSV data or LLM; no exposure sufficiency.",
        is_synthetic_fixture=True)
    science=independently_review_fixture(science,inquiry,reviewed,"q1","R1A_RANDOMIZED_ARM")
    intent=independently_confirm_business_intent_v292(reviewed,"q1",dict(classification="RANDOMIZED_ARM",
        node_order=[f"unit_{i:03d}" for i in range(72)],node_id="unit_037",own_treatment=0,exposure_state=1),
        evidence="Independent business reading: only unit_037, own no coupon, at least one treated neighbor, original randomization conditional average")
    evidence=independently_review_evidence_v292(science,inquiry)
    binding=FormalQueryBindingV29(science,inquiry,intent,evidence)
    sheet=unapproved_crosswalk_worksheet_v012(case=case,quality=quality,business_review=review,query_id="q1",formal_binding=binding,
        reviewer="Synthetic independent crosswalk reviewer",evidence="Exact independently frozen single-store conditional arm target")
    sheet.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
    port=RealCoreCoveragePortV012(bindings={"q1":binding},crosswalks={"q1":ApprovedBusinessMathCrosswalkV012.model_validate(sheet)})
    approval=MaterialsCandidateApprovalV035(bundle_sha256=canonical_hash(bundle),model_draft_sha256=canonical_hash(raw),
        science_packet_sha256=canonical_hash(packet),gateway_case_sha256=canonical_sha256(case),gateway_quality_sha256=canonical_sha256(quality),
        gateway_review_sha256=review.fingerprint(),reviewed_query_ids=["q1"],reviewer="Synthetic independent materials reviewer",
        reviewed_a4_levels={},review_evidence="Draft coordinates compared with independently declared unit_037 conditional arm, original source and exact typed scope",
        reviewed_materials_to_gateway=True,synthetic_fixture=True)
    return ReviewedMaterialsContextV035(case,quality,review,port,approval)

