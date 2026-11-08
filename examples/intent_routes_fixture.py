"""Independent synthetic acceptance fixtures; never a production review service.

Business targets are declared below before any model call. The model receives
only public_bundle(), not inquiries, licenses, labels or these review helpers.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product

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
from cfm_id_bridge.scientific_binding import sha, actual_scientific_sources, actual_scientific_licenses
from pfn_pipeline.network_inquiry_shadow import declare_network_study, fixed_policy_target_from_context
from pfn_pipeline.identification_coverage import _full_source, _assumptions
from pfn_pipeline.identification_business import FixedPolicyInquiryV21, ObservationalPolicyInquiryV23
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, declare_signature_population_source, admit_mean_signature_sufficiency,
)
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline._internal.identification.schemas import Assumption
from cfm_id.intent_submission import submission_worksheet, ReviewedIntentSubmissionV057
from evaluation.business_fixed_intent_base import project


CASES = ('randomized_full', 'randomized_signature', 'observational_full', 'observational_signature')
ROUTES = dict(zip(CASES, ('R1B_FULL_ASSIGNMENT', 'R2_MEAN_SIGNATURE', 'R3_FULL_ASSIGNMENT', 'R3_MEAN_SIGNATURE')))


def public_bundle(case_id, negative=None):
    if case_id not in CASES:
        raise ValueError('UNKNOWN_FIXTURE')
    signature = case_id.endswith('signature')
    nodes = ['hub', 'l1', 'l2', 'l3', 'l4'] if signature else ['A', 'B', 'C']
    people = '5名员工' if signature else '3名员工'
    network = ('处理前冻结的合作网络是hub分别与l1、l2、l3、l4相连，其他人之间没有连边。' if signature
               else '处理前冻结的合作网络是A与B、C相连，B与C没有连边。')
    if case_id.startswith('observational'):
        protocol = '过去员工自主决定是否使用AI，未随机分配。'
    elif signature:
        protocol = '过去公司从5人中均匀随机抽出恰好4人开放AI权限。'
    else:
        protocol = '过去公司给每人独立抽签，各有一半机会开放AI权限。'
    goal = '问题1：如果这次让所有员工都用AI，我想知道全体员工的平均销售额，每个人权重相同。'
    if negative == 'partial':
        goal = f'问题1：如果这次让{nodes[0]}用AI，其他人是否使用还没决定，我想知道全体员工的平均销售额，每个人权重相同。'
    elif negative == 'comparison':
        goal = '问题1：使用AI有没有影响？要比较哪两种安排还没决定。评价全体员工的平均销售额，每个人权重相同。'
    return dict(case_id=case_id + ('_' + negative if negative else ''), node_order=nodes,
        documents={'study.txt': f'我们公司有{people}，研究员工使用AI对销售额的作用。\n{network}\n{protocol}\n'
            '研究中的高暴露表示合作同事严格超过一半使用AI，低暴露表示其余情况。这个分组本身不表示他人的具体安排不影响结果。\n'
            '这些是合成业务材料，样本数据不被声明为已知总体信息。', 'goal.txt': goal},
        question_slots={'q1': goal})


def gold_reading(case_id, negative=None):
    """Offline test only; never substitute this object for an actual model reply."""
    b = public_bundle(case_id, negative)
    first = {n: 1 if not negative or (negative == 'partial' and i == 0) else None
             for i, n in enumerate(b['node_order'])}
    kind = '比较' if negative == 'comparison' else '水平'
    return dict(intents={'q1': dict(kind=kind, quote=b['question_slots']['q1'])}, questions={'q1': dict(
        first=first, second={n: None for n in b['node_order']} if kind == '比较' else None,
        population=b['node_order'], aggregation='等权平均')})


def independent_coordinates(case_id):
    nodes = public_bundle(case_id)['node_order']
    return dict(classification='FIXED_POLICY', node_order=nodes, assignment=[1]*len(nodes),
                unit_weights=[str(Fraction(1, len(nodes)))]*len(nodes))


def inquiry(case_id, variant=None):
    b = public_bundle(case_id)
    nodes = tuple(b['node_order'])
    signature, obs = case_id.endswith('signature'), case_id.startswith('observational')
    design = None if obs else {'kind': 'complete_randomization_binary_v1', 'm': 4} if signature else {
        'kind': 'heterogeneous_bernoulli_binary_v1', 'propensities': {n: '1/2' for n in nodes}}
    study = declare_network_study(network_id='INTENT_ACCEPTANCE_' + case_id, node_order=nodes,
        undirected_edges=tuple((nodes[0], n) for n in nodes[1:]), treatment_variable='AI',
        outcome_variable='sales', outcome_kind='continuous', context_reference='W',
        observation_regime='observational' if obs else 'experimental', assignment_design=design,
        protocol_provenance=b['documents']['study.txt'], network_provenance='Synthetic fixed pretreatment star',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    target = fixed_policy_target_from_context(study, (1,)*len(nodes), authority='TRUSTED_FIXTURE')
    sig = declare_policy_signature(study, grouping='strict_majority_ties_low')
    suff = admit_mean_signature_sufficiency(study, sig, covered_nodes=nodes,
        assumption=Assumption(name='mean_signature_sufficiency', source='demo_specification', confirmed=True,
            status='ADMITTED', evidence=['Separate hypothetical scientist explicitly posits mean signature sufficiency']))
    if obs:
        masses = ([(tuple(int(i != k) for i in range(5)), Fraction(1, 5)) for k in range(5)] if signature
                  else [(z, Fraction(1, 8)) for z in product((0, 1), repeat=3)])
        source = declare_observational_population_v23(study, source_id='SYNTHETIC_OBS_POPULATION',
            provenance='Separate hypothetical population law, not sample CSV', assignment_masses=masses)
        names = ['full_vector_conditional_exchangeability', 'consistency', 'fixed_pretreatment_network', 'finite_conditional_first_moments']
        if variant == 'missing_exchangeability': names.remove('full_vector_conditional_exchangeability')
        a5 = tuple(Assumption(name=n, source='demo_specification', confirmed=True, status='ADMITTED',
            evidence=['Separate hypothetical scientist licenses only this named condition']) for n in names)
        return ObservationalPolicyInquiryV23(study, target, source, a5,
            sig if signature and variant != 'missing_sufficiency' else None,
            suff if signature and variant != 'missing_sufficiency' else None)
    if signature and variant != 'missing_sufficiency':
        source = declare_signature_population_source(study, sig, source_id='SYNTHETIC_SIGNATURE_MEANS',
            operator='NODE_SIGNATURE_MEANS', outcome_nodes=nodes, signature_cells=tuple((n,1,1) for n in nodes),
            admission='ADMITTED', availability='SYMBOLIC_POPULATION_OPERATOR',
            provenance='Separate hypothetical population signature means, not sample data')
        return FixedPolicyInquiryV21(study, target, _assumptions(), r2_signature=sig,
                                     r2_sufficiency=suff, r2_sources=(source,))
    return FixedPolicyInquiryV21(study, target, _assumptions(), r1b_sources=(_full_source(study),))


def synthetic_context(case_id, bundle, raw, variant=None):
    """Admit only the independently specified public goal; never fix the reading."""
    if bundle != public_bundle(case_id) or project(bundle, raw)[0] != {'q1': independent_coordinates(case_id)}:
        raise ValueError('READING_DIFFERS_FROM_INDEPENDENT_FIXTURE')
    typed = inquiry(case_id, variant)
    text = '\n'.join(bundle['documents'].values())
    goal = bundle['question_slots']['q1']
    study_lines = bundle['documents']['study.txt'].splitlines()
    case = BusinessCase(case_id='SYNTHETIC_V057_' + case_id, business_question=text)
    def cl(quote):
        assert quote in text
        return SemanticClaim(value=quote, basis='EXPLICIT_TEXT', evidence=[EvidenceQuote(source_id='business_question', quote=quote)])
    target = TargetDraft(kind=TargetKind.FIXED_POLICY_VALUE, description=cl(goal))
    shared = DraftProblemSpec(target=target,
        units_variables=UnitsVariablesDraft(analysis_unit=cl(study_lines[0]), treatment=cl('使用AI'), outcome=cl('销售额')),
        structure=StructureDraft(unit_network=cl(study_lines[1]), network_pretreatment_status=cl(study_lines[1]), exposure_mapping=cl(study_lines[3])),
        information_design=InformationDesignDraft(assignment_family=AssignmentFamily.OBSERVATIONAL if case_id.startswith('observational')
            else AssignmentFamily.COMPLETE_RANDOMIZATION if case_id.endswith('signature') else AssignmentFamily.INDEPENDENT_BERNOULLI,
            assignment_law=cl(study_lines[2]), population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl(study_lines[4])))
    query = BusinessInquiryV010(query_id='q1', target=target, business_goal=cl(goal), semantics=QuerySemanticsV010(
        target_population=cl(goal), intervention=cl(goal), aggregation=cl(goal), policy_assignment=cl(goal)))
    quality = audit_business_quality(case, MultiQueryDraftV010(shared_draft=shared, primary_query_id='q1', queries=[query]),
        provider='SYNTHETIC_INDEPENDENT_REVIEW_OF_ACTUAL_READING', prompt_version='intent-routes-v057')
    review = BusinessQueryReviewV011(case_id=case.case_id, input_sha256=quality.input_sha256, draft_sha256=quality.draft_sha256,
        confirmed_query_ids=['q1'], reviewed_by='Synthetic independent business reviewer', decision='CONFIRMED',
        review_note='Independent all-treated equal-mean target; hypothetical test review, not production authorization')
    reviewed = approve_multiquery(case, quality.legacy_audit, v29_review_from_v011(review, legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    route = ROUTES[case_id]
    family = 'R3_POLICY' if case_id.startswith('observational') else 'R2_FIXED_POLICY' if typed.r2_signature else 'R1B_FIXED_POLICY'
    if variant == 'missing_sufficiency': route = 'R3_FULL_ASSIGNMENT' if case_id.startswith('observational') else 'R1B_FULL_ASSIGNMENT'
    science = ScientificAdmissionV29(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256, query_id='q1', target_sha256=canonical_sha256(target),
        formal_family=family, formal_target_fingerprint=formal_target_fingerprint_v29(typed),
        math_target_description=goal, math_target_crosswalk_confirmed=True, scientific_reviewer='Synthetic scientist',
        evidence_reference='SYNTHETIC_V057_INDEPENDENT_PROTOCOL', a4_population_operator_reference='SYNTHETIC_V057_A4',
        a4_scientifically_admitted=True, a5_assumption_reference='SYNTHETIC_V057_A5_' + str(variant), a5_scientifically_admitted=True,
        scientific_review_note='Only the recorded licenses are hypothetically admitted; omitted exchangeability or sufficiency is not granted.',
        is_synthetic_fixture=True)
    science = independently_review_fixture(science, typed, reviewed, 'q1', route)
    intent = independently_confirm_business_intent_v292(reviewed, 'q1', independent_coordinates(case_id),
        evidence='Independent predeclared public goal: all roster employees treated, equal population average')
    binding = FormalQueryBindingV29(science, typed, intent, independently_review_evidence_v292(science, typed))
    sheet = unapproved_crosswalk_worksheet_v012(case=case, quality=quality, business_review=review, query_id='q1',
        formal_binding=binding, reviewer='Synthetic crosswalk reviewer', evidence='Independent exact target, explicitly scoped sources and licenses')
    sheet.update(reviewer_confirmed_business_to_math=True, reviewer_confirmed_a4_a5_and_route=True)
    port = RealCoreCoveragePortV012(bindings={'q1': binding}, crosswalks={'q1': ApprovedBusinessMathCrosswalkV012.model_validate(sheet)})
    packet = dict(mode='SYNTHETIC_BENCHMARK_ONLY', bundle_sha256=canonical_hash(bundle), queries={'q1': dict(
        study_sha256=sha(typed.study), a4_sources_sha256=sha(actual_scientific_sources(typed)),
        a5_licenses_sha256=sha(actual_scientific_licenses(typed)), a4_reference=science.a4_population_operator_reference,
        a5_reference=science.a5_assumption_reference)})
    approval = MaterialsCandidateApprovalV035(bundle_sha256=canonical_hash(bundle), model_draft_sha256=canonical_hash(raw),
        science_packet_sha256=canonical_hash(packet), gateway_case_sha256=canonical_sha256(case),
        gateway_quality_sha256=canonical_sha256(quality), gateway_review_sha256=review.fingerprint(), reviewed_query_ids=['q1'],
        reviewed_a4_levels={}, reviewer='Synthetic independent materials reviewer',
        review_evidence='Actual model reading compared with independently declared natural goal and synthetic science',
        reviewed_materials_to_gateway=True, synthetic_fixture=True)
    context = ReviewedMaterialsContextV035(case, quality, review, port, approval)
    outer = reviewed_submission(bundle, raw, 'FIXED_POLICY', packet, context)
    return packet, context, outer


def reviewed_submission(bundle, raw, entry, packet, context, envelope=None):
    return ReviewedIntentSubmissionV057(**submission_worksheet(bundle, raw, entry, packet, context, envelope),
        reviewer='Synthetic independent intent reviewer', evidence='Explicitly checked intent and all coordinates against the predeclared business goal',
        reviewed_intent_and_conditions=True, synthetic_fixture=True)
