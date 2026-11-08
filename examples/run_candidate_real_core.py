"""Integrated v3.0: real v2.9.2 mathematical Core + Mock Candidate demo (synthetic ONLY).

From the integrated v3.0 root:
    python -m examples.run_candidate_real_core

This fixture's approval records are hypothetical *test-scientist* assertions.
Never copy its automatic fixture preparation to production review workflows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cfm_id_llm.audit import fingerprint_business_case
from cfm_id_llm.candidate_queries import BusinessQueryReviewV011, CandidateReasonerV011
from cfm_id_llm.multiquery import HumanMultiQueryReviewV09, approve_multiquery
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality import (
    BusinessInquiryV010, MultiQueryDraftV010, QuerySemanticsV010, audit_business_quality,
)
from cfm_id_llm.schemas import (
    AssignmentFamily, BusinessCase, DraftProblemSpec, EvidenceQuote, InformationDesignDraft,
    PopulationInformationLevel, SemanticClaim, StructureDraft, TargetDraft, TargetKind,
    UnitsVariablesDraft,
)
from cfm_id_llm.trusted_core import (
    ApprovedBusinessMathCrosswalkV012, RealCoreCoveragePortV012,
    unapproved_crosswalk_worksheet_v012, v29_review_from_v011,
)


def synth_data(*, off_support: bool):
    """Only synthetic, audited-for-consistency business text and A0 Mock draft."""
    assignment = (
        "员工A从不获分配AI权限；员工B和C分别独立地以1/2概率获分配AI权限"
        if off_support else "员工A、B、C分别独立地以1/2概率获分配AI权限"
    )
    question = (
        "公司有三名销售员A、B、C。A与B、C合作，B和C没有直接合作，该网络在实验开始前已固定。"
        + assignment + "。记录每人的AI权限和每周销售额。"
        + "如果合作同事中使用AI的人超过一半，我们把它称为高使用环境，否则称为低使用环境。"
        + "我们要分析员工A未获得AI权限且处于低使用环境时的平均销售额。"
        + "此外，公司也想知道如果给三人全部开通AI，整个团队的平均销售额会怎样。"
    )
    case = BusinessCase(case_id='SYNTH_V012_OFF_SUPPORT' if off_support else 'SYNTH_V012_SUPPORTED',
                        business_question=question)

    def cl(quote, value=None):
        assert quote in question, quote
        return SemanticClaim(value=value or quote, basis='EXPLICIT_TEXT',
            evidence=[EvidenceQuote(source_id='business_question', quote=quote)])

    arm = '员工A未获得AI权限且处于低使用环境时的平均销售额'
    policy = '如果给三人全部开通AI，整个团队的平均销售额会怎样'
    q1_target=TargetDraft(kind=TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN,
                          description=cl(arm))
    q2_target=TargetDraft(kind=TargetKind.FIXED_POLICY_VALUE,description=cl(policy))
    shared = DraftProblemSpec(
        target=q1_target,
        units_variables=UnitsVariablesDraft(analysis_unit=cl('三名销售员A、B、C'),
            treatment=cl('AI权限'),outcome=cl('每周销售额')),
        structure=StructureDraft(unit_network=cl('A与B、C合作，B和C没有直接合作'),
            network_pretreatment_status=cl('该网络在实验开始前已固定'),
            exposure_mapping=cl('合作同事中使用AI的人超过一半')),
        information_design=InformationDesignDraft(
            assignment_family=AssignmentFamily.INDEPENDENT_BERNOULLI,
            assignment_law=cl(assignment),
            population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl('记录每人的AI权限和每周销售额')),
    )
    draft=MultiQueryDraftV010(
        shared_draft=shared,primary_query_id='q1',queries=[
            BusinessInquiryV010(query_id='q1',target=q1_target,business_goal=cl(arm),
                semantics=QuerySemanticsV010(target_population=cl('员工A'),
                    intervention=cl('员工A未获得AI权限'),
                    neighbor_exposure=cl('低使用环境'))),
            BusinessInquiryV010(query_id='q2',target=q2_target,business_goal=cl(policy),
                semantics=QuerySemanticsV010(target_population=cl('三名销售员A、B、C'),
                    intervention=cl('三人全部开通AI'),
                    policy_assignment=cl('三人全部开通AI'),
                    aggregation=cl('整个团队的平均销售额'))),
        ])
    quality=audit_business_quality(case,draft,provider='MOCK-synthetic-review',
                                    prompt_version='synthetic-v012-test-fixture')
    review=BusinessQueryReviewV011(
        case_id=case.case_id,input_sha256=quality.input_sha256,
        draft_sha256=quality.draft_sha256,
        confirmed_query_ids=['q1','q2'],reviewed_by='Synthetic business study reviewer',
        decision='CONFIRMED',review_note='Independent synthetic business review of two exact user targets and case materials')
    return case,quality,review


def synthetic_bindings(*, off_support: bool, case, quality, business_review):
    """Construct TEST-only independently declared typed A4/A5; never inferred from CSV."""
    from cfm_id_bridge.bridge import ScientificAdmissionV29, FormalQueryBindingV29, formal_target_fingerprint_v29
    from cfm_id_bridge.scientific_binding import (
        ApprovedScienceBindingV291, proposed_binding_snapshot_v291, sha)
    from cfm_id_bridge.d1_binding import ReviewedD1ArmPacketV29, prepare_d1_arm_binding_v29
    from cfm_id_llm.multiquery import approve_multiquery
    from pfn_pipeline._internal.identification.schemas import Assumption, NetworkExposureSpec
    from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED
    from pfn_pipeline.identification import make_heterogeneous_bernoulli_arm_task
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21
    from pfn_pipeline.network_inquiry_shadow import (
        declare_network_study, fixed_policy_target_from_context, declare_network_a4_source)

    reviewed = approve_multiquery(case,quality.legacy_audit,v29_review_from_v011(business_review, legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    probabilities={'A':'0' if off_support else '1/2','B':'1/2','C':'1/2'}
    net=NetworkExposureSpec(network_id='SYNTH_GATEWAY_V012_NETWORK',
                            node_ids=['A','B','C'],undirected_edges=[('A','B'),('A','C')])
    task=make_heterogeneous_bernoulli_arm_task(net,propensities=probabilities,
        node_id='A',own_treatment_value=0,exposure_value=0,
        source='SYNTHETIC_REVIEWED_POPULATION_OPERATOR_V012',
        evidence='Separately admitted synthetic scientific A4 and A5 scope',admitted=True,
        query_authority='TRUSTED_FIXTURE',synthetic=True)
    study=declare_network_study(
        network_id='SYNTH_GATEWAY_V012_NETWORK',node_order=('A','B','C'),
        undirected_edges=(('A','B'),('A','C')),
        treatment_variable='ai_access',outcome_variable='weekly_sales',
        outcome_kind='continuous',context_reference='W',observation_regime='experimental',
        assignment_design={'kind':'heterogeneous_bernoulli_binary_v1','propensities':probabilities},
        protocol_provenance='SYNTHETIC_EXACT_D1_DESIGN_V012',
        network_provenance='SYNTHETIC_PRETREATMENT_NETWORK_V012',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED',
    )
    target=fixed_policy_target_from_context(study,(1,1,1),authority='TRUSTED_FIXTURE')
    source=declare_network_a4_source(study,source_id='SYNTHETIC_POPULATION_NODE_FULL_LAW_V012',
            operator='NODE_FULL_LAW',provenance='SYNTHETIC_POPULATION_OPERATOR_APPROVAL',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=study.node_order)
    assumptions=tuple(Assumption(name=n,source='demo_specification',confirmed=True,
        evidence=['Synthetic scientific A5 license for test only']) for n in REQUIRED)
    policy_inquiry=FixedPolicyInquiryV21(study=study,target=target,
        assumptions=assumptions,r1b_sources=(source,))
    typed_targets={'q1':task,'q2':policy_inquiry}
    def scientist(qid,family,fingerprint):
        q=next(x for x in quality.draft.queries if x.query_id==qid)
        return ScientificAdmissionV29(case_id=case.case_id,
            input_sha256=quality.input_sha256,draft_sha256=quality.legacy_audit.draft_sha256,
            query_id=qid,target_sha256=canonical_sha256(q.target),formal_family=family,
            math_target_description=('Synthetic node A untreated/low-exposure arm' if qid=='q1'
                else 'Synthetic all-three-treated equal-weight fixed full policy'),
            formal_target_fingerprint=fingerprint,math_target_crosswalk_confirmed=True,
            scientific_reviewer='Separate synthetic mathematics reviewer',
            evidence_reference='SYNTHETIC_INDEPENDENT_PROTOCOL_AND_SCIENCE_V012',
            a4_population_operator_reference='SYNTHETIC_POPULATION_OPERATOR_APPROVAL',
            a4_scientifically_admitted=True,
            a5_assumption_reference='SYNTHETIC_KNOWN_RANDOMIZATION_AND_CONSISTENCY',
            a5_scientifically_admitted=True,
            scientific_review_note=('All typed coordinates and scientific assumptions are '
                'hypothetical and independently declared for regression testing only.'),
            is_synthetic_fixture=True)
    arm_science=scientist('q1','R1A_ARM',task.target_fingerprint)
    packet=ReviewedD1ArmPacketV29(scientific_admission=arm_science,
        network_id=net.network_id,node_order=['A','B','C'],
        undirected_edges=[('A','B'),('A','C')],propensities=probabilities,
        target_node_id='A',target_own_treatment=0,target_exposure=0,
        protocol_evidence='SYNTHETIC_DESIGN_MATCHED_TO_BUSINESS_DESCRIPTION_V012')
    arm=prepare_d1_arm_binding_v29(packet)
    policy_science=scientist('q2','R1B_FIXED_POLICY',target.target_digest)
    policy=FormalQueryBindingV29(policy_science,policy_inquiry)
    bindings={'q1':arm,'q2':policy}
    with_approval={}
    for qid,b in bindings.items():
        query=next(q for q in quality.draft.queries if q.query_id==qid)
        route='R1A_RANDOMIZED_ARM' if qid=='q1' else 'R1B_FULL_ASSIGNMENT'
        sheet=proposed_binding_snapshot_v291(b.inquiry,
            business_review_sha256=sha(reviewed.human_review),
            target_sha256=canonical_sha256(query.target),
            business_quote=query.target.description.evidence[0].quote,
            a4_reference=b.admission.a4_population_operator_reference,
            a5_reference=b.admission.a5_assumption_reference,
            theorem_route=route,reviewer=b.admission.scientific_reviewer,
            evidence=b.admission.evidence_reference)
        # SYNTHETIC TEST ONLY: this line imitates an independent reviewer's
        # explicit decisions. The production path has no such auto-approval.
        sheet.update(reviewer_confirmed_exact_coordinates=True,
                     reviewer_confirmed_sources_and_licenses=True)
        approved=ApprovedScienceBindingV291.model_validate(sheet)
        science=b.admission.model_copy(update={'approved_scientific_binding':approved})
        # SYNTHETIC TEST FIXTURE ONLY: two separately declared human-approved
        # objects needed by current v2.9.2 Core. Never create these from the
        # LLM response in any production service.
        from dataclasses import replace
        from examples.llm_core_fixture import (
            independently_confirm_business_intent_v292,
            independently_review_evidence_v292,
        )
        # These coordinates are assertions about the ORIGINAL business text,
        # not snapshots of a generated candidate policy.
        if qid == 'q1':
            business_coords = dict(classification='RANDOMIZED_ARM',
                node_order=['A','B','C'], node_id='A', own_treatment=0,
                exposure_state=0)
        else:
            # The study scope and weight strings must match the original
            # separately read synthetic protocol, not a model-generated target.
            from cfm_id_bridge.scientific_binding import scientific_target_coordinates
            original = scientific_target_coordinates(b.inquiry)
            business_coords = {key: original[key] for key in
                ('classification','node_order','assignment','unit_weights')}
            assert business_coords['assignment'] == [1,1,1]
        intent=independently_confirm_business_intent_v292(
            reviewed, qid, business_coords,
            evidence='Independent synthetic business approval of actual original query coordinates')
        manifest=independently_review_evidence_v292(science,b.inquiry)
        with_approval[qid]=replace(FormalQueryBindingV29(science,b.inquiry),
            business_intent=intent, evidence_manifest=manifest)
    return with_approval


def synthetic_env(*, off_support: bool):
    case, quality, review=synth_data(off_support=off_support)
    bindings=synthetic_bindings(off_support=off_support, case=case,
                                quality=quality,business_review=review)
    approved_crosswalks={}
    for qid,binding in bindings.items():
        worksheet=unapproved_crosswalk_worksheet_v012(
            case=case, quality=quality, business_review=review,
            query_id=qid,formal_binding=binding,
            reviewer='Synthetic independent crosswalk reviewer',
            evidence='Synthetic reviewer examined original business goal and exact typed coordinates')
        # SYNTHETIC TEST ONLY: in a real system a separate reviewer fills both.
        worksheet.update(reviewer_confirmed_business_to_math=True,
                         reviewer_confirmed_a4_a5_and_route=True)
        approved_crosswalks[qid]=ApprovedBusinessMathCrosswalkV012.model_validate(worksheet)
    port=RealCoreCoveragePortV012(bindings=bindings,crosswalks=approved_crosswalks)
    return case,quality,review,port


def run_example(*, off_support:bool=True):
    case,quality,review,port=synthetic_env(off_support=off_support)
    q2=quality.draft.queries[1]
    from cfm_id_llm.candidate_queries import (
        TrustedScienceScopeV011, ApprovedA4ReferenceV011, ApprovedA5LicenseV011,
    )
    from cfm_id_llm.orchestration_schemas import canonical_sha256
    approved=port.bindings['q2'].admission.approved_scientific_binding
    scope=TrustedScienceScopeV011(
        scientific_review_sha256=canonical_sha256(approved),
        a4_sources=[ApprovedA4ReferenceV011(**x) for x in approved.approved_a4_sources],
        a5_licenses=[ApprovedA5LicenseV011(**x) for x in approved.approved_a5_licenses],
    )
    # Demo's candidate is an illustrative UNDETERMINED claim, not a theorem.
    candidate={
        'schema_version':'cfm-id-candidate-proposal-v0.11',
        'query_id':'q2',
        'target_sha256':canonical_sha256(q2.target),
        'semantics_sha256':canonical_sha256(q2.semantics),
        'science_scope_sha256':scope.fingerprint(),
        'proposal':{
            'schema_version':'cfm-id-candidate-draft-v0.3',
            'target_kind':q2.target.kind.value,
            'target_description':q2.target.description.value,
            'claimed_identification':'UNDETERMINED',
            'scope':'AS_REVIEWED',
            'a4_used':{'source':'UNRESOLVED','level':None,'operator':None},
            'admitted_assumptions_used':[],
            'additional_requirements':[],
            'candidate_expression':None,
            'nonidentification_witness':None,
            'reasoning_steps':['检查是否存在超出现有R1b范围的可靠结构条件'],
            'caveats':['实际数学适用性需独立研究人员审查；UNSUPPORTED不等于非识别'],
            'suggested_checks':['仔细检查总体信息与额外A5约束'],
        },
        'proposed_validation_checks':['确认同一因果目标下的其他已注册定理及条件'],
        'known_core_coverage_gap':'Core真实执行，仅R1b完整分配支持不足；不是数学非识别证明',
    }
    provider=MockProvider(candidate)
    result=CandidateReasonerV011(provider,port).run(
        case=case,quality=quality,business_review=review)
    return case,quality,review,result,provider.calls,port.calls,port.last_real_results


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--supported',action='store_true',help='All units randomized: full policy supported')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    case,quality,review,result,calls,core_calls,core_results=run_example(off_support=not args.supported)
    summary={
      'mode':'REAL_v3.0_CORE__MOCK_LLM_CANDIDATE',
      'synthetic_fixture':True,'online_api_calls':0,
      'case_id':case.case_id,
      'experiment_design_description':case.business_question,
      'candidate_model_calls':calls,'actual_core_lookups':core_calls,
      'actual_core_results':core_results,
      'results':[dict(query_id=r.query_id, status=r.status,
                      reason_code=r.reason_code, mode=r.mode,
                      verification_level=r.verification_level,
                      estimated_effects_available=False) for r in result.results],
      'candidate_formula_proven':False,
      'estimation_handoff_allowed':False,
    }
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
