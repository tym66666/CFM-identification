"""Predeclared target-variation fixtures; public text is separate from review data.

No production permissions. The independent target is never extracted from the
model reply, and study/A4/A5 remain the preceding synthetic protocol fixtures.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

from examples.intent_routes_fixture import (
    public_bundle as previous_bundle, inquiry as previous_inquiry,
    reviewed_submission, project, sha, actual_scientific_sources, actual_scientific_licenses,
    fixed_policy_target_from_context,
)
from examples.materials_candidate_fixture import (
    BusinessCase, SemanticClaim, EvidenceQuote, TargetDraft, TargetKind,
    DraftProblemSpec, UnitsVariablesDraft, StructureDraft, InformationDesignDraft,
    AssignmentFamily, PopulationInformationLevel, BusinessInquiryV010, MultiQueryDraftV010,
    QuerySemanticsV010, audit_business_quality, BusinessQueryReviewV011, approve_multiquery,
    v29_review_from_v011, ScientificAdmissionV29, formal_target_fingerprint_v29,
    canonical_sha256, independently_review_fixture, independently_confirm_business_intent_v292,
    independently_review_evidence_v292, FormalQueryBindingV29,
    unapproved_crosswalk_worksheet_v012, RealCoreCoveragePortV012, ApprovedBusinessMathCrosswalkV012,
    MaterialsCandidateApprovalV035, ReviewedMaterialsContextV035, canonical_hash,
)


CASES = {
    'mixed_all': dict(study='randomized_full',
        goal='问题1：这次只让A和C使用AI，B不使用。三个人的平均销售额会是多少？每个人权重相同。',
        assignment=[1,0,1], population=['A','B','C'], final='CORE_POINT', route='R1B_FULL_ASSIGNMENT'),
    'mixed_b': dict(study='randomized_full',
        goal='问题1：这次只让A和C使用AI，B不使用。我只关心B的平均销售额是多少。',
        assignment=[1,0,1], population=['B'], final='CORE_POINT', route='R1B_FULL_ASSIGNMENT'),
    'obs_mixed_b': dict(study='observational_full',
        goal='问题1：这次只让A和C使用AI，B不使用。我只关心B的平均销售额是多少。',
        assignment=[1,0,1], population=['B'], final='CORE_POINT', route='R3_FULL_ASSIGNMENT'),
    'signature_subgroup': dict(study='randomized_signature',
        goal='问题1：这次只让hub、l1、l2用AI，l3和l4不用。只看l1和l2的平均销售额，两个人权重相同。',
        assignment=[1,1,1,0,0], population=['l1','l2'], final='CORE_POINT', route='R2_MEAN_SIGNATURE'),
    'obs_signature_subgroup': dict(study='observational_signature',
        goal='问题1：这次只让hub、l1、l2用AI，l3和l4不用。只看l1和l2的平均销售额，两个人权重相同。',
        assignment=[1,1,1,0,0], population=['l1','l2'], final='CORE_POINT', route='R3_MEAN_SIGNATURE'),
    'missing_assignment': dict(study='randomized_full',
        goal='问题1：只确定让A使用AI，B和C是否使用还没有决定。我想知道三个人的平均销售额，每个人权重相同。',
        assignment=[1,None,None], population=['A','B','C'], final='NEEDS_INPUT', route=None),
    'missing_assignment_b': dict(study='randomized_full',
        goal='问题1：这次让A使用AI，B不使用，C是否使用还没有决定。我只想知道B的平均销售额。',
        assignment=[1,0,None], population=['B'], final='NEEDS_INPUT', route=None),
    'signature_unsupported_all': dict(study='randomized_signature',
        goal='问题1：这次只让hub、l1、l2用AI，l3和l4不用。五个人的平均销售额会是多少？每个人权重相同。',
        assignment=[1,1,1,0,0], population=['hub','l1','l2','l3','l4'], final='UNSUPPORTED', route=None),
}


def public_bundle(case_id):
    f=CASES[case_id];b=previous_bundle(f['study'])
    b.update(case_id='V058_'+case_id,question_slots={'q1':f['goal']})
    b['documents']['goal.txt']=f['goal']
    return b


def gold_reading(case_id):
    """Offline test/reference only, never sent to the model or substituted for it."""
    b=public_bundle(case_id);f=CASES[case_id]
    return dict(intents={'q1':dict(kind='水平',quote=f['goal'])},questions={'q1':dict(
        first=dict(zip(b['node_order'],f['assignment'])),second=None,
        population=deepcopy(f['population']),aggregation='等权平均')})


def independent_coordinates(case_id):
    f=CASES[case_id];nodes=public_bundle(case_id)['node_order']
    if None in f['assignment']:raise ValueError('NO_TARGET_FOR_INCOMPLETE_BUSINESS_REQUEST')
    return dict(classification='FIXED_POLICY',node_order=nodes,assignment=deepcopy(f['assignment']),
        unit_weights=[str(Fraction(1,len(f['population']))) if n in f['population'] else '0' for n in nodes])


def inquiry(case_id):
    base=previous_inquiry(CASES[case_id]['study']);coords=independent_coordinates(case_id)
    return replace(base,target=fixed_policy_target_from_context(base.study,tuple(coords['assignment']),
        unit_weights=tuple(coords['unit_weights']),authority='TRUSTED_FIXTURE'))


def synthetic_context(case_id,bundle,raw):
    if bundle!=public_bundle(case_id) or project(bundle,raw)[0]!={'q1':independent_coordinates(case_id)}:
        raise ValueError('READING_DIFFERS_FROM_INDEPENDENT_VARIANT')
    f=CASES[case_id];typed=inquiry(case_id);goal=f['goal']
    text='\n'.join(bundle['documents'].values());lines=bundle['documents']['study.txt'].splitlines()
    case=BusinessCase(case_id='SYNTHETIC_V058_'+case_id,business_question=text)
    def cl(quote):
        assert quote in text
        return SemanticClaim(value=quote,basis='EXPLICIT_TEXT',evidence=[EvidenceQuote(source_id='business_question',quote=quote)])
    target=TargetDraft(kind=TargetKind.FIXED_POLICY_VALUE,description=cl(goal))
    shared=DraftProblemSpec(target=target,
        units_variables=UnitsVariablesDraft(analysis_unit=cl(lines[0]),treatment=cl('使用AI'),outcome=cl('销售额')),
        structure=StructureDraft(unit_network=cl(lines[1]),network_pretreatment_status=cl(lines[1]),exposure_mapping=cl(lines[3])),
        information_design=InformationDesignDraft(assignment_family=AssignmentFamily.OBSERVATIONAL if f['study'].startswith('observational')
            else AssignmentFamily.COMPLETE_RANDOMIZATION if f['study'].endswith('signature') else AssignmentFamily.INDEPENDENT_BERNOULLI,
            assignment_law=cl(lines[2]),population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl(lines[4])))
    query=BusinessInquiryV010(query_id='q1',target=target,business_goal=cl(goal),semantics=QuerySemanticsV010(
        target_population=cl(goal),intervention=cl(goal),aggregation=cl(goal),policy_assignment=cl(goal)))
    quality=audit_business_quality(case,MultiQueryDraftV010(shared_draft=shared,primary_query_id='q1',queries=[query]),
        provider='SYNTHETIC_INDEPENDENT_REVIEW_OF_ACTUAL_READING',prompt_version='intent-target-variants-v058')
    review=BusinessQueryReviewV011(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.draft_sha256,
        confirmed_query_ids=['q1'],reviewed_by='Synthetic independent business reviewer',decision='CONFIRMED',
        review_note='Check both complete assignment and evaluated population against independently predeclared business goal')
    reviewed=approve_multiquery(case,quality.legacy_audit,v29_review_from_v011(review,legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    route=f['route'] or 'R2_MEAN_SIGNATURE'
    family='R3_POLICY' if f['study'].startswith('observational') else 'R2_FIXED_POLICY' if typed.r2_signature else 'R1B_FIXED_POLICY'
    science=ScientificAdmissionV29(case_id=case.case_id,input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256,query_id='q1',target_sha256=canonical_sha256(target),
        formal_family=family,formal_target_fingerprint=formal_target_fingerprint_v29(typed),math_target_description=goal,
        math_target_crosswalk_confirmed=True,scientific_reviewer='Synthetic scientist',evidence_reference='SYNTHETIC_V058_INDEPENDENT_PROTOCOL',
        a4_population_operator_reference='SYNTHETIC_V058_A4',a4_scientifically_admitted=True,
        a5_assumption_reference='SYNTHETIC_V058_A5',a5_scientifically_admitted=True,
        scientific_review_note='Only preceding explicitly declared sources and licenses; no extension to compensate for changed target or absent support.',
        is_synthetic_fixture=True)
    science=independently_review_fixture(science,typed,reviewed,'q1',route)
    intent=independently_confirm_business_intent_v292(reviewed,'q1',independent_coordinates(case_id),
        evidence='Independent complete treatment allocation and separately specified evaluation population; zero weight does not delete treatment coordinates')
    binding=FormalQueryBindingV29(science,typed,intent,independently_review_evidence_v292(science,typed))
    sheet=unapproved_crosswalk_worksheet_v012(case=case,quality=quality,business_review=review,query_id='q1',formal_binding=binding,
        reviewer='Synthetic crosswalk reviewer',evidence='Exact predeclared allocation and population checked against same independently admitted scientific context')
    sheet.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
    port=RealCoreCoveragePortV012(bindings={'q1':binding},crosswalks={'q1':ApprovedBusinessMathCrosswalkV012.model_validate(sheet)})
    packet=dict(mode='SYNTHETIC_BENCHMARK_ONLY',bundle_sha256=canonical_hash(bundle),queries={'q1':dict(
        study_sha256=sha(typed.study),a4_sources_sha256=sha(actual_scientific_sources(typed)),
        a5_licenses_sha256=sha(actual_scientific_licenses(typed)),a4_reference=science.a4_population_operator_reference,
        a5_reference=science.a5_assumption_reference)})
    approval=MaterialsCandidateApprovalV035(bundle_sha256=canonical_hash(bundle),model_draft_sha256=canonical_hash(raw),
        science_packet_sha256=canonical_hash(packet),gateway_case_sha256=canonical_sha256(case),
        gateway_quality_sha256=canonical_sha256(quality),gateway_review_sha256=review.fingerprint(),reviewed_query_ids=['q1'],
        reviewed_a4_levels={},reviewer='Synthetic independent materials reviewer',
        review_evidence='Actual model reading compared to predeclared natural goal; all study and science constraints retained',
        reviewed_materials_to_gateway=True,synthetic_fixture=True)
    context=ReviewedMaterialsContextV035(case,quality,review,port,approval)
    return packet,context,reviewed_submission(bundle,raw,'FIXED_POLICY',packet,context)
