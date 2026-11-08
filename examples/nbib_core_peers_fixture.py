"""Independent, explicit synthetic NBIB018 E3 two-effect reviewer; third goal stays unsupported."""
from examples.materials_candidate_fixture import *
from evaluation.business_core_pilot_base import target_coordinates
from evaluation.business_core_peers_base import project,compile_inquiry,preview_submission
DATA=Path(__file__).resolve().parents[1]/"assets/peer_scope_fixtures/materials_cases.json"
def load_case(cid="positive"):
    return json.loads(DATA.read_text(encoding="utf8"))[cid]

def synthetic_context(item):
    b,raw,packet=item["bundle"],item["raw"],item["packet"]
    _,d,targets,_=project(b,raw);nodes=[f"unit_{i:03d}" for i in range(300)]
    expected=[dict(kind="comparison",nodes=nodes,aggregation="equal_mean",situation=s,reference=r,
        remaining="original_randomization",treated_nodes=None,unresolved=[]) for s,r in (([1,1],[0,1]),([0,1],[0,0]))]
    if ([target_coordinates(t) for t in targets[:2]]!=expected or targets[2].kind!="optimization"
        or b!=load_case()["bundle"] or list(b["question_slots"])!=["q1","q2","q3"]
        or [x["state"] for x in preview_submission(b,raw)["query_views"]]!=["REVIEW_REQUIRED","REVIEW_REQUIRED","UNSUPPORTED"]
        or d!=load_case()["packet"]["study"] or d!=packet["study"] or packet!=load_case()["packet"]):
        raise ValueError("NOT_THE_INDEPENDENTLY_DECLARED_E3_EFFECTS_AND_OPTIMIZATION")
    text="\n".join(b["documents"].values());case=BusinessCase(case_id="SYNTHETIC_NBIB018_E3_TWO_EFFECTS",business_question=text)
    def cl(quote):
        assert quote in text,quote
        return SemanticClaim(value=quote,basis="EXPLICIT_TEXT",evidence=[EvidenceQuote(source_id="business_question",quote=quote)])
    goals={q:b["question_slots"][q] for q in ("q1","q2")};lines=b["documents"][b["active_goal_document"]].splitlines()
    kinds=[TargetKind.DIRECT_EFFECT,TargetKind.SPILLOVER_EFFECT]
    target_drafts=[TargetDraft(kind=k,description=cl(goals[q])) for k,q in zip(kinds,goals)]
    shared=DraftProblemSpec(target=target_drafts[0],
        units_variables=UnitsVariablesDraft(analysis_unit=cl("300名员工"),treatment=cl("AI知识助手"),outcome=cl("customer_service_quality")),
        structure=StructureDraft(unit_network=cl("合作关系"),network_pretreatment_status=cl("试验前冻结的无向协作边"),
            exposure_mapping=cl("核心伙伴过半启用")),
        information_design=InformationDesignDraft(assignment_family=AssignmentFamily.INDEPENDENT_BERNOULLI,
            assignment_law=cl(b["documents"]["study_protocol.md"].splitlines()[2]),
            population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl("所有 CSV 都是有确定随机种子的仿真样本")))
    queries=[BusinessInquiryV010(query_id=q,target=target_drafts[i],business_goal=cl(goal),
        semantics=QuerySemanticsV010(target_population=cl(lines[0]),aggregation=cl(lines[0]),
            intervention=cl(goal),comparator=cl(goal),neighbor_exposure=cl(goal),standardization_distribution=cl(lines[-1])))
        for i,(q,goal) in enumerate(goals.items())]
    quality=audit_business_quality(case,MultiQueryDraftV010(shared_draft=shared,primary_query_id="q1",queries=queries),
        provider="SYNTHETIC_INDEPENDENT_TWO_EFFECT_REVIEW",prompt_version="nbib-core-peers-v051")
    review=BusinessQueryReviewV011(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.draft_sha256,
        confirmed_query_ids=["q1","q2"],reviewed_by="Synthetic independent business reviewer",decision="CONFIRMED",
        review_note="Two frozen 300-employee equal-mean contrasts; independent hypothetical test fixture, never production")
    reviewed=approve_multiquery(case,quality.legacy_audit,v29_review_from_v011(review,legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    bindings={};crosswalks={}
    for i,qid in enumerate(goals):
        inquiry=compile_inquiry(d,targets[i],b,packet["science"])
        science=ScientificAdmissionV29(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.legacy_audit.draft_sha256,
            query_id=qid,target_sha256=canonical_sha256(target_drafts[i]),formal_family="R1A_EFFECT",
            formal_target_fingerprint=formal_target_fingerprint_v29(inquiry),math_target_description=goals[qid],
            math_target_crosswalk_confirmed=True,scientific_reviewer="Synthetic independent scientist",
            evidence_reference="SYNTHETIC_NBIB018_E3_TWO_EFFECTS_PROTOCOL",
            a4_population_operator_reference=packet["science"]["population_information"],a4_scientifically_admitted=True,
            a5_assumption_reference=packet["science"]["causal_licenses"],a5_scientifically_admitted=True,
            scientific_review_note="Explicit hypothetical supported population arm means and randomization licenses; no exposure sufficiency inferred.",
            is_synthetic_fixture=True)
        science=independently_review_fixture(science,inquiry,reviewed,qid,"R1A_COMPOSITION")
        coords=dict(classification="EffectsInquiryV21",kind="DIRECT" if i==0 else "SPILLOVER",
            node_weights=[[n,"1/300"] for n in nodes],reference_exposure=1 if i==0 else 0,
            comparison_exposure=1,spillover_own_treatment=1 if i==0 else 0)
        intent=independently_confirm_business_intent_v292(reviewed,qid,coords,
            evidence="Independently frozen direct own1-minus0 at high exposure; spillover high-minuslow with own0; all300 equal weights")
        evidence=independently_review_evidence_v292(science,inquiry)
        binding=FormalQueryBindingV29(science,inquiry,intent,evidence);bindings[qid]=binding
        sheet=unapproved_crosswalk_worksheet_v012(case=case,quality=quality,business_review=review,query_id=qid,
            formal_binding=binding,reviewer="Synthetic crosswalk reviewer",evidence="Compared every effect coordinate with separately declared two-question intention")
        sheet.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
        crosswalks[qid]=ApprovedBusinessMathCrosswalkV012.model_validate(sheet)
    port=RealCoreCoveragePortV012(bindings=bindings,crosswalks=crosswalks)
    approval=MaterialsCandidateApprovalV035(bundle_sha256=canonical_hash(b),model_draft_sha256=canonical_hash(raw),
        science_packet_sha256=canonical_hash(packet),gateway_case_sha256=canonical_sha256(case),
        gateway_quality_sha256=canonical_sha256(quality),gateway_review_sha256=review.fingerprint(),reviewed_query_ids=["q1","q2"],
        reviewer="Synthetic independent materials reviewer",reviewed_a4_levels={},
        review_evidence="Only q1/q2 separately reviewed; full three-goal input bound, q3 optimization explicitly excluded; actual core-partner table retained",
        reviewed_materials_to_gateway=True,synthetic_fixture=True)
    return ReviewedMaterialsContextV035(case,quality,review,port,approval)

