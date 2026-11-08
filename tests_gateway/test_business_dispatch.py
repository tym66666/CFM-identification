"""Neutral A0 -> shared DAG facts -> native checks. Offline synthetic approvals."""
from copy import deepcopy

import pytest

from cfm_id import business_intake as intake, business_dispatch as work
from cfm_id import dag_business as native
from cfm_id.dag_method_dispatch import native_reviews_from_json
from examples.business_dispatch_reference import from_case, prepare, approvals, approve
from examples.dag_business_reference import cases as backdoor_cases
from examples.dag_adjustment_business_reference import cases as adjustment_cases
from examples.dag_frontdoor_business_reference import _case as frontdoor_case


def result(case):
    s, options, plan = prepare(case)
    return work.execute(s, 'q1', **options, **approvals(plan))


@pytest.mark.parametrize('case,expected', [
    (backdoor_cases()[0], {native.CLASSICAL_ROUTE, native.ADJUSTMENT_ROUTE}),
    (adjustment_cases()[0], {native.ADJUSTMENT_ROUTE}),
    (frontdoor_case('implicit_frontdoor', 'implicit_role'), {native.FRONTDOOR_ROUTE}),
], ids=['observed_confounder', 'adjustment_only', 'frontdoor_only'])
def test_methods_are_checked_without_user_selecting_one(case, expected):
    r = result(case)
    assert r['state'] == 'POINT' and r['independent_replay']
    assert {a['method'] for a in r['answers']} == expected
    assert r['mathematical_claim'] == r['answers'][0]['mathematical_claim']
    assert r['certificate'] == r['answers'][0]['certificate']
    assert r['method_matching'] == 'CHECKED_BY_NATIVE_BACKENDS'
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


def test_reader_reuses_fact_contract_and_contains_no_method_answer_or_approval():
    s, wire = from_case(backdoor_cases()[0])
    pending = work.prepare_reader(s, 'q1')
    assert pending['state'] == 'REVIEW_REQUIRED' and pending['request'] is None
    review = approve(pending['query_worksheet'])
    ready = work.prepare_reader(s, 'q1', query_review=review)
    assert ready['reader_id'] == 'VARIABLE_DAG_FACTS'
    assert ready['method_matching'] == 'NOT_PERFORMED'
    assert 'ACCEPTED' not in ready['request']['user']
    assert review.reviewer not in ready['request']['user']
    assert 'expected_state' not in ready['request']['user']
    assert ready['bundle']['question'] == s.case.business_question


def test_preparation_does_not_call_any_solver(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('solver called before review')
    for module in ('dag_backdoor', 'dag_adjustment', 'dag_frontdoor'):
        monkeypatch.setattr('cfm_id.' + module + '.solve', forbidden)
    s, options, plan = prepare(backdoor_cases()[0])
    assert plan['state'] == 'REVIEW_REQUIRED' and not plan['backend_called']
    assert all(r['applicability'] == 'NOT_CHECKED_BEFORE_SCIENCE_REVIEW' for r in plan['methods'])
    for review, native_reviews, select in [(None, None, True), (approve(plan['plan_worksheet']), None, True),
                                          (None, None, False), (None, None, 1)]:
        r = work.execute(s, 'q1', **options, plan_review=review, native_reviews=native_reviews,
                         research_protocol_selected=select)
        assert r['state'] == 'REVIEW_REQUIRED' and not r['backend_called']


@pytest.mark.parametrize('case,state', [
    (backdoor_cases()[3], 'NEEDS_INPUT'),
    (backdoor_cases()[4], 'NEEDS_INPUT'),
    (backdoor_cases()[5], 'NEEDS_INPUT'),
    (frontdoor_case('positive_unknown', 'unknown_positive'), 'NEEDS_INPUT'),
    (frontdoor_case('role_unknown', 'undecided'), 'NEEDS_INPUT'),
    (frontdoor_case('both_roles', 'both'), 'ADAPTER_NOT_CONNECTED'),
])
def test_missing_or_combined_conditions_never_silently_repaired(case, state):
    s, options, plan = prepare(case)
    assert plan['state'] == state
    r = work.execute(s, 'q1', **options, research_protocol_selected=True)
    assert r['state'] == state and not r['backend_called']
    assert r['mathematical_claim'] is None and r['certificate'] is None and not r['answers']


def test_failure_of_all_sufficient_methods_is_not_nonidentification():
    r = result(backdoor_cases()[6])
    assert r['state'] == 'UNSUPPORTED' and not r['nonidentification_proved']
    assert len(r['attempts']) == 3
    assert r['mathematical_claim'] is r['certificate'] is None and not r['answers']


@pytest.mark.parametrize('variant,methods', [
    ('specified', {native.FRONTDOOR_ROUTE}),
    ('forbidden', {native.CLASSICAL_ROUTE, native.ADJUSTMENT_ROUTE}),
    ('control', {native.CLASSICAL_ROUTE, native.ADJUSTMENT_ROUTE}),
])
def test_explicit_roles_restrict_search_without_becoming_assumptions(variant, methods):
    s, options, plan = prepare(frontdoor_case('role_' + variant, variant))
    assert {r['method'] for r in plan['methods']} == methods
    assert plan['exclusions']
    r = work.execute(s, 'q1', **options, **approvals(plan))
    assert r['state'] == ('POINT' if variant == 'specified' else 'UNSUPPORTED')


@pytest.mark.parametrize('decision,expected', [('PENDING', 'REVIEW_REQUIRED'), ('REJECTED', 'CHECK_BLOCKED')])
@pytest.mark.parametrize('layer', ['query', 'plan', 'reading', 'science'])
def test_pending_or_rejected_review_cannot_be_bypassed_by_another_method(monkeypatch, decision, expected, layer):
    s, options, plan = prepare(backdoor_cases()[0]); args = approvals(plan)
    if layer == 'query':
        record = options['query_review']; key = next(iter(record.decisions))
        options['query_review'] = record.model_copy(update={'decisions': {**record.decisions, key: decision}})
    elif layer == 'plan':
        record = args['plan_review']; key = next(iter(record.decisions))
        args['plan_review'] = record.model_copy(update={'decisions': {**record.decisions, key: decision}})
    else:
        # Last method: prevent earlier valid methods from solving before this is checked.
        pair = args['native_reviews'][native.FRONTDOOR_ROUTE]
        field = layer + '_review'; record = pair[field]; key = next(iter(record.decisions))
        pair[field] = record.model_copy(update={'decisions': {**record.decisions, key: decision}})
    def forbidden(*args, **kwargs): raise AssertionError('a review was bypassed')
    monkeypatch.setattr(native, 'submit_reviewed', forbidden)
    r = work.execute(s, 'q1', **options, **args)
    assert r['state'] == expected and not r['backend_called'] and not r['answers']


def test_stale_request_candidate_role_and_science_reviews_block_before_math(monkeypatch):
    s, options, plan = prepare(backdoor_cases()[0]); args = approvals(plan)
    def forbidden(*args, **kwargs): raise AssertionError('stale input reached mathematics')
    monkeypatch.setattr(native, 'submit_reviewed', forbidden)
    r = work.execute(s, 'q1', **{**options, 'request_sha256': '0' * 64}, **args)
    assert r['reason_code'] == 'STALE_FACT_READING_REQUEST'
    changed = deepcopy(options['candidate'])
    changed['frontdoor_choice'] = dict(status='FORBIDDEN', variable=None, source_ids=changed['target']['source_ids'])
    # Same common projections, different role: the outer full-reading binding must fail.
    r = work.execute(s, 'q1', **{**options, 'candidate': changed}, **args)
    assert r['state'] == 'CHECK_BLOCKED'
    pair = args['native_reviews'][native.ADJUSTMENT_ROUTE]
    pair['science_review'] = pair['science_review'].model_copy(update={'problem_sha256': '0' * 64})
    r = work.execute(s, 'q1', **options, **args)
    assert r['reason_code'] == 'STALE_NATIVE_REVIEW'


def test_changed_intake_or_other_query_cannot_reuse_approvals():
    s, options, plan = prepare(backdoor_cases()[0]); args = approvals(plan)
    new = intake.receive_candidate(s, s.candidate, request_sha256=s.request_sha256)
    r = work.execute(new, 'q1', **options, **args)
    assert r['state'] == 'CHECK_BLOCKED' and not r['backend_called']
    r = work.execute(s, 'q2', **options, **args)
    assert r['reason_code'] == 'EXACT_CURRENT_QUERY_REQUIRED'


def test_reader_omission_is_recheck_not_a_new_fact_requested_from_user():
    s, _ = from_case(backdoor_cases()[0]); raw = deepcopy(s.candidate)
    raw['shared_draft']['units_variables']['treatment'] = dict(value=None, basis='UNRESOLVED', evidence=[])
    s = intake.receive_candidate(s, raw, request_sha256=s.request_sha256)
    view = work.prepare_reader(s, 'q1')
    assert view['reading_audit']['business_status'] == 'FORMULATION_RECHECK_REQUIRED'
    assert view['state'] == 'READING_RECHECK_REQUIRED'
    assert not view['backend_called'] and view['request'] is None
    assert view['clarification_questions'] == []
    assert view['evidence_status'] == 'CURRENT_READING_NOT_PROVEN_SOURCE_ABSENCE'


@pytest.mark.parametrize('variant', ['missing_native', 'extra_native', 'authority', 'extra_constraint', 'bad_quote', 'model_approval'])
def test_invalid_reviews_and_reading_do_not_gain_permission(variant):
    s, options, plan = prepare(backdoor_cases()[0]); args = approvals(plan)
    if variant == 'missing_native': args['native_reviews'].pop(native.FRONTDOOR_ROUTE)
    elif variant == 'extra_native': args['native_reviews']['invented_method'] = {}
    elif variant == 'authority':
        args['plan_review'] = args['plan_review'].model_copy(update={'authority': 'EXTERNAL_RESEARCH_REVIEW'})
    else:
        wire = deepcopy(options['candidate']); options['candidate'] = wire
        if variant == 'extra_constraint':
            wire['additional_restrictions'] = [dict(text='额外单调性限制', source_ids=wire['target']['source_ids'])]
        elif variant == 'bad_quote': wire['variables'][0]['source_ids'] = ['not-in-the-materials']
        else: wire['review'] = {'all_conditions': 'ACCEPTED'}
    r = work.execute(s, 'q1', **options, **args)
    assert r['state'] in ('CHECK_BLOCKED', 'UNSUPPORTED')
    assert not r['backend_called'] and not r['answers'] and r['certificate'] is None


@pytest.mark.parametrize('corruption', ['formula', 'certificate', 'mutation', 'missing_proof'])
def test_publication_rechecks_native_output_and_preserves_input(monkeypatch, corruption):
    s, options, plan = prepare(backdoor_cases()[0]); args = approvals(plan)
    original = native.submit_reviewed
    def damaged(bundle, wire, **kwargs):
        r = original(bundle, wire, **kwargs)
        if kwargs['route_id'] == native.ADJUSTMENT_ROUTE and r['state'] == 'POINT':
            if corruption == 'formula': r['mathematical_claim']['functional'] = {'wrong': True}
            elif corruption == 'certificate': r['certificate']['target'] = {'wrong': True}
            elif corruption == 'mutation': bundle['question'] += ' changed after solving'
            else: r['certificate'] = None
        return r
    monkeypatch.setattr(native, 'submit_reviewed', damaged)
    before = deepcopy(options['candidate'])
    r = work.execute(s, 'q1', **options, **args)
    assert r['state'] == 'CHECK_BLOCKED' and not r['independent_replay']
    assert not r['answers'] and r['mathematical_claim'] is r['certificate'] is None
    assert options['candidate'] == before


def test_native_review_json_is_only_deserialized_not_approved():
    s, options, plan = prepare(backdoor_cases()[0]); args = approvals(plan)
    wire = {method: {k: v.model_dump(mode='json') for k, v in pair.items()}
            for method, pair in args['native_reviews'].items()}
    restored = native_reviews_from_json(plan, wire)
    assert restored == args['native_reviews']
    wire[native.ADJUSTMENT_ROUTE]['science_review']['decisions'].clear()
    restored = native_reviews_from_json(plan, wire)
    r = work.execute(s, 'q1', **options, **{**args, 'native_reviews': restored})
    assert r['state'] == 'CHECK_BLOCKED' and not r['backend_called']


def test_network_and_combined_structures_are_visible_bridge_gaps():
    s, _ = from_case(backdoor_cases()[0])
    for combined in (False, True):
        raw = deepcopy(s.candidate)
        structure = raw['shared_draft']['structure']
        structure['unit_network'] = deepcopy(structure['variable_causal_graph'])
        if not combined: structure['variable_causal_graph'] = dict(value=None, basis='UNRESOLVED', evidence=[])
        new = intake.receive_candidate(s, raw, request_sha256=s.request_sha256)
        pending = work.prepare_reader(new, 'q1')
        r = work.prepare_reader(new, 'q1', query_review=approve(pending['query_worksheet']))
        assert r['state'] == 'ADAPTER_NOT_CONNECTED' and not r['backend_called']
        assert r['request'] is None


def test_selected_query_is_explicit_and_other_queries_are_retained():
    s, wire = from_case(backdoor_cases()[0]); raw = deepcopy(s.candidate)
    case = s.case.model_dump(mode='json')
    text = '我们还想知道哪个做法更好，但尚未决定比较哪些做法。'
    case['sources'].append(dict(source_id='another_question', kind='BUSINESS_NARRATIVE', text=text))
    s = intake.revise_materials(s, case, reason='补充第二个尚未明确的业务问题')
    second = deepcopy(raw['queries'][0]); second['query_id'] = 'q2'
    second['business_goal'] = dict(value=text, basis='EXPLICIT_TEXT',
                                   evidence=[dict(source_id='another_question', quote=text)])
    second['target'] = dict(kind='UNRESOLVED', description=dict(value=None, basis='UNRESOLVED', evidence=[]), alternatives=[])
    raw['queries'].append(second)
    s = intake.receive_candidate(s, raw, request_sha256=s.request_sha256)
    pending = work.prepare_reader(s, 'q1'); review = approve(pending['query_worksheet'])
    ready = work.prepare_reader(s, 'q1', query_review=review)
    assert ready['remaining_query_ids'] == ['q2']
    other = work.prepare_reader(s, 'q2', query_review=review)
    assert other['state'] == 'CHECK_BLOCKED' and other['request'] is None
    assert other['reason_code'] == 'STALE_OR_WRONG_SCOPE_DISPATCH_REVIEW'
    # The genuine q2 gap remains, but a q1 review cannot mask its own scope error.
    without_review = work.prepare_reader(s, 'q2')
    assert without_review['state'] == 'NEEDS_INPUT'
    assert without_review['reason_code'] == 'SELECTED_QUERY_READING_NOT_READY'
    options = dict(query_review=review, candidate=wire, request_sha256=ready['request_sha256'])
    plan = work.inspect_methods(s, 'q1', **options)
    answer = work.execute(s, 'q1', **options, **approvals(plan))
    assert answer['state'] == 'POINT' and answer['result_scope'] == 'SELECTED_QUERY_ONLY'
    assert answer['remaining_query_ids'] == ['q2']


def test_cli_flow_uses_query_selection_but_no_method_selection(tmp_path):
    from cfm_id.business_dispatch_cli import main
    s, options, plan = prepare(backdoor_cases()[0]); args = approvals(plan)
    paths = {name: tmp_path / (name + '.json') for name in
             ('intake', 'query_review', 'reader_plan', 'candidate', 'plan_review', 'native_reviews', 'result')}
    intake.save(s, paths['intake'])
    intake.write_json(paths['query_review'], options['query_review'].model_dump(mode='json'))
    intake.write_json(paths['candidate'], options['candidate'])
    intake.write_json(paths['plan_review'], args['plan_review'].model_dump(mode='json'))
    intake.write_json(paths['native_reviews'], {m: {k: v.model_dump(mode='json') for k, v in pair.items()}
                                              for m, pair in args['native_reviews'].items()})
    base = ['--intake', str(paths['intake']), '--query', 'q1', '--query-review', str(paths['query_review'])]
    assert main(['reader-plan', *base, '--output', str(paths['reader_plan'])]) == 0
    assert main(['execute', *base, '--reader-plan', str(paths['reader_plan']), '--candidate', str(paths['candidate']),
                 '--plan-review', str(paths['plan_review']), '--native-reviews', str(paths['native_reviews']),
                 '--select-research-protocol', '--output', str(paths['result'])]) == 0
    r = intake.read_json(paths['result'])
    assert r['state'] == 'POINT' and len(r['answers']) == 2
