"""Independent synthetic review for the NBIB002 D2/E4 clarification; never production."""
from examples.materials_candidate_fixture import *
from evaluation.business_d2_submission import project,compile_inquiry
from evaluation.business_core_pilot_base import target_coordinates
DATA=Path(__file__).resolve().parents[1]/"assets/d2_material_fixtures/materials_cases.json"
def load_case(cid="NBIB-002-unit017-v046"):
    return json.loads(DATA.read_text(encoding="utf8"))[cid]
def synthetic_context(item):
    b,raw,packet=item["bundle"],item["raw"],item["packet"]
    _,d,targets=project(b,raw)
    expected=dict(kind="arm",nodes=["unit_017"],aggregation="single",situation=[1,1],
        reference=None,remaining="original_randomization",treated_nodes=None,unresolved=[])
    frozen=load_case()
    if (len(targets)!=1 or target_coordinates(targets[0])!=expected or d!=frozen["packet"]["study"]
        or b["structure"]!=frozen["bundle"]["structure"] or d!=packet["study"] or packet["bundle_sha256"]!=canonical_hash(b)):
        raise ValueError("NOT_THE_INDEPENDENTLY_DECLARED_D2_ARM")
    inquiry=compile_inquiry(d,targets[0],b,packet["science"])
    text="\n".join(b["documents"].values());case=BusinessCase(case_id="SYNTHETIC_NBIB002_D2_ARM",business_question=text)
    def cl(quote):
        assert quote in text,quote
        return SemanticClaim(value=quote,basis="EXPLICIT_TEXT",evidence=[EvidenceQuote(source_id="business_question",quote=quote)])
    lines=b["documents"][b["active_goal_document"]].splitlines();goal=b["question_slots"]["q1"]
    target=TargetDraft(kind=TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN,description=cl(goal))
    shared=DraftProblemSpec(target=target,units_variables=UnitsVariablesDraft(
        analysis_unit=cl("48个站点"),treatment=cl("新排班系统"),outcome=cl("delivery_delay")),
        structure=StructureDraft(unit_network=cl("互相支援的站点关系"),network_pretreatment_status=cl("试验前冻结的无向协作边"),
            exposure_mapping=cl("邻站实际使用人数定义为0、1、2三种状态")),
        information_design=InformationDesignDraft(assignment_family=AssignmentFamily.COMPLETE_RANDOMIZATION,
            assignment_law=cl("48个站点依照预先锁定的名册均匀抽出恰好24个"),
            population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl("所有 CSV 都是有确定随机种子的仿真样本")))
    query=BusinessInquiryV010(query_id="q1",target=target,business_goal=cl(goal),semantics=QuerySemanticsV010(
        target_population=cl(lines[0]),intervention=cl(goal),neighbor_exposure=cl(goal),
        aggregation=cl(goal),standardization_distribution=cl(lines[-1])))
    quality=audit_business_quality(case,MultiQueryDraftV010(shared_draft=shared,primary_query_id="q1",queries=[query]),
        provider="SYNTHETIC_INDEPENDENT_D2_REVIEW",prompt_version="nbib-d2-reviewed-v046")
    review=BusinessQueryReviewV011(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.draft_sha256,
        confirmed_query_ids=["q1"],reviewed_by="Synthetic independent business reviewer",decision="CONFIRMED",
        review_note="Frozen unit017 own1 exact one neighbor treated; conditional average under global 24/48 draw")
    reviewed=approve_multiquery(case,quality.legacy_audit,v29_review_from_v011(review,legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    science=ScientificAdmissionV29(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.legacy_audit.draft_sha256,
        query_id="q1",target_sha256=canonical_sha256(target),formal_family="R1A_ARM",
        formal_target_fingerprint=formal_target_fingerprint_v29(inquiry),math_target_description=goal,
        math_target_crosswalk_confirmed=True,scientific_reviewer="Synthetic independent scientist",
        evidence_reference="SYNTHETIC_NBIB002_D2_ARM_PROTOCOL",
        a4_population_operator_reference=packet["science"]["population_information"],a4_scientifically_admitted=True,
        a5_assumption_reference=packet["science"]["causal_licenses"],a5_scientifically_admitted=True,
        scientific_review_note="Hypothetical population operator and randomized consistency/fixed network assumptions; no exposure sufficiency.",
        is_synthetic_fixture=True)
    science=independently_review_fixture(science,inquiry,reviewed,"q1","R1A_RANDOMIZED_ARM")
    intent=independently_confirm_business_intent_v292(reviewed,"q1",dict(classification="RANDOMIZED_ARM",
        node_order=[f"unit_{i:03d}" for i in range(48)],node_id="unit_017",own_treatment=1,exposure_state=1),
        evidence="Independent target: only unit017, treated, exactly one treated neighbor under original global24/48 conditional law")
    evidence=independently_review_evidence_v292(science,inquiry)
    binding=FormalQueryBindingV29(science,inquiry,intent,evidence)
    sheet=unapproved_crosswalk_worksheet_v012(case=case,quality=quality,business_review=review,query_id="q1",formal_binding=binding,
        reviewer="Synthetic crosswalk reviewer",evidence="Verified D2/E4 arm and exact independent business coordinates")
    sheet.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
    port=RealCoreCoveragePortV012(bindings={"q1":binding},crosswalks={"q1":ApprovedBusinessMathCrosswalkV012.model_validate(sheet)})
    approval=MaterialsCandidateApprovalV035(bundle_sha256=canonical_hash(b),model_draft_sha256=canonical_hash(raw),
        science_packet_sha256=canonical_hash(packet),gateway_case_sha256=canonical_sha256(case),gateway_quality_sha256=canonical_sha256(quality),
        gateway_review_sha256=review.fingerprint(),reviewed_query_ids=["q1"],reviewer="Independent synthetic materials reviewer",
        reviewed_a4_levels={},review_evidence="Exact complete-randomization arm; all science independently and hypothetically declared",
        reviewed_materials_to_gateway=True,synthetic_fixture=True)
    return ReviewedMaterialsContextV035(case,quality,review,port,approval)

