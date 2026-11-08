"""Explicit synthetic R2 comparison fixtures; never a production review service.

The two policies and their common evaluation population are predeclared before
any reader invocation. These helpers may create hypothetical review assertions
only for offline experiments. They never repair an actual candidate, approve a
real enterprise question, call an API, or read credentials.
"""
from copy import deepcopy
from fractions import Fraction as F

from examples import bounded_policy_intake_fixture as single
from examples import intent_routes_fixture as f
from cfm_id import bounded_policy_intake as intake
from cfm_id import fixed_comparison as comparison
from cfm_id.assignment_review import (
    assignment_worksheet, ReviewedQuestionBoundAssignmentFacts,
)
from cfm_id.question_bound_assignment import question_catalog, resolve_reading, CONTRACT
from cfm_id.source_locations import build_catalog

SIDES = ('first', 'second')


def make_case(nodes, edges, quota, first, second, population, *, serial=0, continuous=False):
    """Build one comparison and independently compiled common R2 endpoint inputs.

    Only ``bundle`` belongs in an LLM request. Other returned objects are
    predeclared synthetic mathematics and references, not model-provided facts.
    """
    nodes, edges, population = list(nodes), list(edges), list(population)
    policies = {'first': list(first), 'second': list(second)}
    if (not nodes or len(set(nodes)) != len(nodes) or not population
            or len(set(population)) != len(population) or not set(population) <= set(nodes)
            or any(len(v) != len(nodes) or any(type(z) is not int or z not in (0, 1) for z in v)
                   for v in policies.values())):
        raise ValueError('EXPLICIT_COMPLETE_COMPARISON_FIXTURE_REQUIRED')
    declarations, inquiries, information = {}, {}, {}
    generated = {}
    for side in SIDES:
        b, raw, d, claims, expected = single.make_case(nodes, edges, quota,
            policies[side], population, serial=serial, continuous=continuous)
        record = single.declaration_review(b, raw, d, expected)
        compiled = intake.compile_reviewed(b, raw, query_id='q1', declaration=d,
            review=record, synthetic_protocol_selected=True)
        generated[side] = (b, raw, claims)
        declarations[side], inquiries[side], information[side] = d, compiled.inquiry, compiled.information
    # Identical serial/scientific declarations; target and its binding alone vary.
    if (declarations['first'] != declarations['second']
            or f.sha(inquiries['first'].study) != f.sha(inquiries['second'].study)
            or information['first'].model_dump(exclude={'inquiry_sha256'})
                != information['second'].model_dump(exclude={'inquiry_sha256'})):
        raise ValueError('FIXTURE_ENDPOINTS_DO_NOT_SHARE_ONE_SCIENTIFIC_MODEL')

    def arrangement(vector):
        used = [n for n, z in zip(nodes, vector) if z]
        if not used:
            return '所有小组都不用辅助系统'
        if len(used) == len(nodes):
            return '所有小组都用辅助系统'
        return '、'.join(used) + '用辅助系统，其余小组都不用'

    outcome = '任务得分' if continuous else '按时完成任务的比例'
    goal = ('问题1：方案甲是' + arrangement(policies['first']) + '；方案乙是'
        + arrangement(policies['second']) + '。只评价' + '、'.join(population)
        + '，各小组权重相同。甲相比乙，' + outcome + '平均会高多少？')
    bundle = deepcopy(generated['first'][0])
    bundle['case_id'] = 'GENERATED_CONTRAST_' + str(serial)
    bundle['documents']['goal.txt'] = goal
    bundle['question_slots'] = {'q1': goal}
    claims = deepcopy(generated['first'][2])
    source_ids = [sid for sid, row in build_catalog(bundle['documents']).items()
                  if row['doc_id'] == 'study.txt' and row['text'].strip() == claims['assignment']]
    if len(source_ids) != 1:
        raise ValueError('EXACT_ORIGINAL_ASSIGNMENT_SOURCE_REQUIRED')
    raw = dict(reading=dict(
        intents={'q1': dict(kind='比较', question_id=question_catalog(bundle)['q1']['question_id'])},
        questions={'q1': dict(first=dict(zip(nodes, policies['first'])),
            second=dict(zip(nodes, policies['second'])), population=list(population), aggregation='等权平均')}),
        reported_assignment=dict(mechanism='FIXED_QUOTA_RANDOM', fixed_count=quota,
            maximum_count=None, uniform_subset_declared=True, reported_conflict=False, source_ids=source_ids))
    coordinates = dict(node_order=nodes, first=policies['first'], second=policies['second'],
        unit_weights=[str(F(1, len(population))) if n in population else '0' for n in nodes],
        operation='first_minus_second')
    payload = dict(bundle=bundle, raw=raw, declarations=declarations, inquiries=inquiries,
        information=information, coordinates=coordinates, claims=claims)
    _check_actual_target(payload)
    return payload


def _check_actual_target(payload):
    """Compare current candidate with an independent reference; never overwrite it."""
    bundle, raw = payload['bundle'], payload['raw']
    if set(bundle['question_slots']) != {'q1'}:
        raise ValueError('EXACT_SINGLE_COMPARISON_FIXTURE_REQUIRED')
    _, _, _, actual = comparison.project(bundle, raw)
    if actual != {'q1': payload['coordinates']}:
        raise ValueError('ACTUAL_COMPARISON_DIFFERS_FROM_PREDECLARED_SYNTHETIC_TARGET')
    for side in SIDES:
        target = payload['inquiries'][side].target
        expected = payload['coordinates']
        if (list(target.node_order) != expected['node_order']
                or list(target.policy_assignment) != expected[side]
                or list(target.unit_weights) != expected['unit_weights']):
            raise ValueError('TYPED_ENDPOINT_DIFFERS_FROM_PREDECLARED_SYNTHETIC_TARGET')


def _endpoint_context(payload, side):
    """Bind one R2 endpoint to the unchanged original comparison input."""
    bundle, raw, claims = payload['bundle'], payload['raw'], payload['claims']
    resolved, _ = resolve_reading(bundle, raw)
    inquiry, info = payload['inquiries'][side], payload['information'][side]
    coordinates = payload['coordinates']
    text = '\n'.join(bundle['documents'].values())
    goal = bundle['question_slots']['q1']
    case = f.BusinessCase(case_id=bundle['case_id'], business_question=text)

    def claim(value):
        if value not in text:
            raise ValueError('INDEPENDENT_CLAIM_HAS_NO_PUBLIC_QUOTE')
        return f.SemanticClaim(value=value, basis='EXPLICIT_TEXT', evidence=[
            f.EvidenceQuote(source_id='business_question', quote=value)])

    target = f.TargetDraft(kind=f.TargetKind.FIXED_POLICY_VALUE, description=claim(goal))
    shared = f.DraftProblemSpec(target=target,
        units_variables=f.UnitsVariablesDraft(analysis_unit=claim(claims['analysis_unit']),
            treatment=claim(claims['treatment']), outcome=claim(claims['outcome'])),
        structure=f.StructureDraft(unit_network=claim(claims['network']),
            network_pretreatment_status=claim(claims['network']), exposure_mapping=claim(claims['exposure'])),
        information_design=f.InformationDesignDraft(
            assignment_family=f.AssignmentFamily.COMPLETE_RANDOMIZATION,
            assignment_law=claim(claims['assignment']),
            population_information_level=f.PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=claim(claims['information'])))
    query = f.BusinessInquiryV010(query_id='q1', target=target, business_goal=claim(goal),
        semantics=f.QuerySemanticsV010(target_population=claim(goal), intervention=claim(goal),
            aggregation=claim(goal), policy_assignment=claim(goal)))
    quality = f.audit_business_quality(case, f.MultiQueryDraftV010(shared_draft=shared,
        primary_query_id='q1', queries=[query]), provider='OFFLINE_INDEPENDENT_SYNTHETIC_ENDPOINT_REVIEW',
        prompt_version='bounded-contrast-fixture-1')
    review = f.BusinessQueryReviewV011(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.draft_sha256, confirmed_query_ids=['q1'],
        reviewed_by='Independent synthetic endpoint reviewer', decision='CONFIRMED',
        review_note='The ' + side + ' endpoint of the original ordered comparison; both sides remain separately bound.')
    reviewed = f.approve_multiquery(case, quality.legacy_audit,
        f.v29_review_from_v011(review, legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    science = f.ScientificAdmissionV29(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256, query_id='q1',
        target_sha256=f.canonical_sha256(target), formal_family='R2_FIXED_POLICY',
        formal_target_fingerprint=f.formal_target_fingerprint_v29(inquiry),
        math_target_description=side + ' endpoint: ' + goal, math_target_crosswalk_confirmed=True,
        scientific_reviewer='Independent synthetic scientist', evidence_reference='EXPLICIT_CONTRAST_MEAN_PROTOCOL',
        a4_population_operator_reference=info.source_id, a4_scientifically_admitted=True,
        a5_assumption_reference='EXPLICIT_ALL_ARRANGEMENT_MEAN_SUFFICIENCY', a5_scientifically_admitted=True,
        scientific_review_note='Only the independent common exact signature means and explicit hypothetical conditions apply.',
        is_synthetic_fixture=True)
    science = f.independently_review_fixture(science, inquiry, reviewed, 'q1', 'R2_MEAN_SIGNATURE')
    endpoint_coordinates = dict(classification='FIXED_POLICY', node_order=coordinates['node_order'],
        assignment=coordinates[side], unit_weights=coordinates['unit_weights'])
    intent = f.independently_confirm_business_intent_v292(reviewed, 'q1', endpoint_coordinates,
        evidence='Predeclared ' + side + ' endpoint with the same explicit comparison population')
    binding = f.FormalQueryBindingV29(science, inquiry, intent,
        f.independently_review_evidence_v292(science, inquiry))
    sheet = f.unapproved_crosswalk_worksheet_v012(case=case, quality=quality, business_review=review,
        query_id='q1', formal_binding=binding, reviewer='Independent synthetic scientist',
        evidence='Separate ordered endpoint, complete exact A4 mean information and explicit all-arrangement A5 review')
    sheet.update(reviewer_confirmed_business_to_math=True, reviewer_confirmed_a4_a5_and_route=True)
    port = f.RealCoreCoveragePortV012(bindings={'q1': binding},
        crosswalks={'q1': f.ApprovedBusinessMathCrosswalkV012.model_validate(sheet)},
        comparison_endpoint_sources={'q1':dict(bundle=bundle,raw=raw,query_id='q1',side=side)})
    packet = dict(mode='SYNTHETIC_BENCHMARK_ONLY', bundle_sha256=f.canonical_hash(bundle), queries={'q1': dict(
        study_sha256=f.sha(inquiry.study), a4_sources_sha256=f.sha(f.actual_scientific_sources(inquiry)),
        a5_licenses_sha256=f.sha(f.actual_scientific_licenses(inquiry)),
        a4_reference=science.a4_population_operator_reference, a5_reference=science.a5_assumption_reference)})
    approval = f.MaterialsCandidateApprovalV035(bundle_sha256=f.canonical_hash(bundle),
        model_draft_sha256=f.canonical_hash(resolved['reading']), science_packet_sha256=f.canonical_hash(packet),
        gateway_case_sha256=f.canonical_sha256(case), gateway_quality_sha256=f.canonical_sha256(quality),
        gateway_review_sha256=review.fingerprint(), reviewed_query_ids=['q1'], reviewed_a4_levels={},
        reviewer='Independent synthetic materials reviewer',
        review_evidence='Actual original comparison and ordered endpoint compared with the independent synthetic reference',
        reviewed_materials_to_gateway=True, synthetic_fixture=True)
    return packet, f.ReviewedMaterialsContextV035(case, quality, review, port, approval)


def reviews(payload):
    """Create test-only endpoint assertions, but no joint/bounds approval.

    Callers must obtain the new entry's separate pair review. The original
    comparison candidate is checked against the independent coordinates before
    any fixture assertion is created. A mismatch raises; nothing is repaired.
    """
    _check_actual_target(payload)
    packets, contexts, facts = {}, {}, {}
    for side in SIDES:
        packets[side], contexts[side] = _endpoint_context(payload, side)
        facts[side] = ReviewedQuestionBoundAssignmentFacts(**assignment_worksheet(
            payload['bundle'], payload['raw'], packets[side], contexts[side], contract=CONTRACT),
            reviewer='Independent synthetic assignment reviewer',
            evidence='Exact original uniform quota, public source and ordered R2 endpoint study checked independently',
            reviewed_original_assignment_and_sources=True, synthetic_fixture=True)
    return dict(packet=packets, context=contexts, assignment_review=facts, synthetic_protocol_selected=True)
