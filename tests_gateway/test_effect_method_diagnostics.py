"""Local effects retain reviewed kind, ordered states, scope and staged proofs."""
from copy import deepcopy
from fractions import Fraction
import pytest
from cfm_id import business_dispatch as dispatch, method_diagnostics as diagnostic, project
from cfm_id import method_requirements as requirements, network_effect_dispatch as effects
from cfm_id_llm.network_design_reading import D6_CONDITION
from examples.network_effect_dispatch_reference import setup, approval_records
from examples.network_design_exposure_reference import setup as design_setup


def reviews(records):
    return {k:v for k,v in records.items() if k != 'research_protocol_selected'}


def run(fixture):
    session, entry, options, plan = fixture
    approvals = approval_records(plan)
    result = dispatch.execute(session, plan['query_id'], **options, **approvals)
    return session, options, plan, approvals, result


def method(view):
    assert [r['method'] for r in view['methods']] == [effects.METHOD]
    return view['methods'][0]


def forbidden(*args, **kwargs):
    pytest.fail('Diagnostics or a blocked reading invoked mathematics')


@pytest.mark.parametrize('qid', ['q1','q2'])
@pytest.mark.parametrize('population', ['all','subset','single'])
def test_local_kind_direction_and_evaluation_scope_survive_native_replay(qid, population):
    s, o, p, a, result = run(setup(qid, population=population))
    before = deepcopy((p,a,result))
    view = diagnostic.describe(p, result=result, **reviews(a))
    assert result['state'] == 'POINT' and result['independent_replay']
    assert (p,a,result) == before and not view['grants_execution'] and not view['is_certificate']
    assert view['diagnostics_scope'] == 'DESIGN_STANDARDIZED_LOCAL_EFFECT'
    target = view['effect']['ordered_target']
    assert target == p['proposed_target']
    assert target['evaluation_population'] == o['candidate']['target']['population']
    assert target['remaining_assignment'] == 'ORIGINAL_DESIGN_CONDITIONAL'
    assert target['first'] == ([1,1] if qid == 'q1' else [0,1])
    assert target['second'] == ([0,1] if qid == 'q1' else [0,0])
    item = method(view)
    assert item['certificate']['state'] == 'REPLAY_REPORTED' and not item['certificate']['verified_here']
    assert item['target_kind'] == ('DIRECT_EFFECT' if qid == 'q1' else 'SPILLOVER_EFFECT')
    assert not item['anchor_is_complete_effect']
    assert [r['stage'] for r in item['native_attempt']['stage_attempts']] == ['ANCHOR','COMPOSITION']


def test_readonly_entry_and_saved_evidence_never_invoke_a_backend(monkeypatch):
    s, o, p, a, result = run(setup())
    from pfn_pipeline import identification_business as core, identification_composition as composition
    monkeypatch.setattr(effects, '_compile', forbidden)
    monkeypatch.setattr(core, 'identify_network_business_query', forbidden)
    monkeypatch.setattr(core, 'replay_verified_business_outcome', forbidden)
    monkeypatch.setattr(composition, 'replay_verified_composition', forbidden)
    pending = project.diagnose_methods(s, 'q1', **o, **reviews(a))
    archived = diagnostic.describe(p, result=result, **reviews(a))
    assert not pending['backend_called'] and method(pending)['mathematical_applicability'] == 'NOT_CHECKED'
    assert method(archived)['certificate']['state'] == 'REPLAY_REPORTED'
    assert [r['method'] for r in requirements.catalog(effects.FAMILY)] == [effects.METHOD]
    assert len(requirements.catalog()) == 3
    assert 'mean_sufficiency_all_assignments_and_weighted_nodes' not in p['methods'][0]['science_worksheet']['decisions']
    assert not dispatch.execute(s, 'q1', **o, **dict(a, plan_review=archived))['backend_called']


@pytest.mark.parametrize('qid', ['q1','q2'])
def test_direction_change_invalidates_old_review_and_keeps_signed_native_proof(qid):
    s, o, p, a, result = run(setup(qid, population='subset'))
    changed = deepcopy(o); target = changed['candidate']['target']
    target['first'],target['second'] = target['second'],target['first']
    new_plan = dispatch.inspect_methods(s, qid, **changed)
    blocked = dispatch.execute(s, qid, **changed, **a)
    view = diagnostic.describe(new_plan, result=blocked, **reviews(a))
    assert view['common_review']['state'] == 'INVALID' and not blocked['backend_called']
    with pytest.raises(ValueError, match='DIAGNOSTIC_RESULT_PLAN_BINDING_MISMATCH'):
        diagnostic.describe(new_plan, result=result)
    fresh = approval_records(new_plan)
    reverse = dispatch.execute(s, qid, **changed, **fresh)
    view = diagnostic.describe(new_plan, result=reverse, **reviews(fresh))
    assert reverse['state'] == 'POINT' and reverse['independent_replay']
    def coefficients(r):
        return {(x['node_id'],x['own_treatment'],x['exposure_state']):Fraction(x['coefficient'])
                for x in r['certificate']['results'][0]['constituent_arms']}
    assert coefficients(result) == {k:-v for k,v in coefficients(reverse).items()}
    assert view['effect']['ordered_target']['first'] == p['proposed_target']['second']
    assert method(view)['certificate']['calculation_reported'] == (
        'REVERSED_DIRECT_NATIVE_LINEAR_COMPOSITION' if qid == 'q1' else 'NATIVE_NAMED_EFFECT_COMPOSITION')


def test_d6_additional_science_and_nonbinary_exposure_are_not_flattened():
    s, o, p, a, result = run(design_setup('D6','E4','spillover'))
    view = diagnostic.describe(p, result=result, **reviews(a))
    target = view['effect']['ordered_target']
    assert target['first'][1] == 2 and target['exposure'] == 'EXACT_TREATED_NEIGHBOR_COUNT'
    assert target['assignment']['quota_profiles'] == o['candidate']['assignment']['quota_profiles']
    assert D6_CONDITION in {r['key'] for r in method(view)['science_review']['conditions']}
    assert D6_CONDITION not in {r['key'] for r in method(view)['template']['review_topics']}  # Conditional, not universal.
    a['native_reviews'][effects.METHOD]['science_review'].decisions[D6_CONDITION] = 'REJECTED'
    blocked = dispatch.execute(s, 'q1', **o, **a)
    rejected = diagnostic.describe(p, result=blocked, **reviews(a))
    assert not blocked['backend_called'] and method(rejected)['science_review']['state'] == 'REJECTED'


def test_recommended_scoped_reading_keeps_reviewed_kind_origin_and_count_domain(monkeypatch):
    from tests_gateway.test_scoped_effect_reading import setup as scoped
    s, e, o = scoped(monkeypatch, kind='SPILLOVER_EFFECT', count=True, reverse=True)
    p = dispatch.inspect_methods(s, 'q1', **o); a = approval_records(p)
    result = dispatch.execute(s, 'q1', **o, **a)
    view = diagnostic.describe(p, result=result, **reviews(a))
    assert view['effect']['target_kind_origin'] == p['target_kind_origin']
    domain = view['effect']['ordered_target']['outcome_domain_embedding']
    assert domain['business_kind'] == 'COUNT' and not domain['distributional_continuity_assumed']
    assert not domain['sharp_bound_or_nonidentification_transfer']


@pytest.mark.parametrize('defect,expected', [
    ('missing_population','NEEDS_INPUT'), ('missing_remaining','NEEDS_INPUT'),
    ('sample_only','NEEDS_INPUT'), ('post_assignment','ADAPTER_NOT_CONNECTED'),
    ('mixed_direct_states','READING_RECHECK_REQUIRED'), ('changed_kind','READING_RECHECK_REQUIRED'),
    ('missing_a4_arm','NEEDS_INPUT'), ('refused_science','ADAPTER_NOT_CONNECTED')])
def test_input_gaps_and_semantic_conflicts_remain_blocked(monkeypatch, defect, expected):
    kwargs = {defect:True} if defect in ('sample_only','post_assignment','missing_remaining') else {}
    s,e,o,p = setup(**kwargs); raw = o['candidate']
    if defect == 'missing_population':raw['target']['population'] = None
    if defect == 'mixed_direct_states':raw['target']['second']['exposure'] = 0
    if defect == 'changed_kind':raw['target']['kind'] = 'SPILLOVER_EFFECT'
    if defect == 'missing_a4_arm':raw['information'][0]['arm_cells'] = raw['information'][0]['arm_cells'][4:]
    if defect == 'refused_science':raw['scientific_statements']['consistency']['status'] = 'NOT_ADOPTED'
    before = deepcopy(raw)
    monkeypatch.setattr(effects, '_compile', forbidden)
    p = dispatch.inspect_methods(s, 'q1', **o)
    view = project.diagnose_methods(s, 'q1', **o)
    result = dispatch.execute(s, 'q1', **o, research_protocol_selected=True)
    assert view['source_plan_state'] == result['state'] == expected
    assert raw == before and not result['backend_called'] and not view['grants_execution']
    assert view['effect']['declared_target'] == p['facts']['target']
    assert not view['effect']['target_prepared']
    assert method(view)['certificate']['state'] == 'NOT_REPORTED'


@pytest.mark.parametrize('decision', ['PENDING','REJECTED','STALE'])
def test_exact_review_requirements_still_gate_execution(monkeypatch, decision):
    s,e,o,p = setup(); a = approval_records(p)
    record = a['native_reviews'][effects.METHOD]['science_review']
    if decision == 'STALE':
        a['native_reviews'][effects.METHOD]['science_review'] = record.model_copy(update={'binding_sha256':'0'*64})
    else:record.decisions['full_vector_randomization'] = decision
    monkeypatch.setattr(effects, '_compile', forbidden)
    result = dispatch.execute(s, 'q1', **o, **a)
    view = diagnostic.describe(p, result=result, **reviews(a))
    assert method(view)['science_review']['state'] == ('INVALID' if decision == 'STALE' else decision)
    assert not result['backend_called'] and method(view)['execution'] == 'NOT_RUN'


@pytest.mark.parametrize('probability', ['0','1'])
def test_zero_support_before_or_after_anchor_never_certifies_effect(probability):
    s,e,o,p = setup(); o['candidate']['assignment']['probabilities']['甲店'] = probability
    p = dispatch.inspect_methods(s, 'q1', **o); a = approval_records(p)
    result = dispatch.execute(s, 'q1', **o, **a)
    view = diagnostic.describe(p, result=result, **reviews(a))
    assert result['state'] == 'UNSUPPORTED' and result['backend_called']
    assert method(view)['certificate']['state'] == 'NOT_REPORTED' and not view['nonidentification_proved']
    assert not result['partial_fallback_performed']
    if probability == '1':assert method(view)['native_attempt']['stage_attempts'][0]['state'] == 'POINT'


@pytest.mark.parametrize('reverse,defect', [
    (False,'swapped_target'), (False,'changed_scope'), (False,'anchor_only'),
    (False,'duplicated_stage'), (False,'wrong_kind'), (False,'wrong_formula'),
    (True,'wrong_sign'), (True,'changed_input'), (True,'wrong_envelope'), (True,'blocked_state')])
def test_saved_record_mismatch_cannot_be_shown_as_replayed_effect(reverse, defect):
    fixture = design_setup('D2','E4',reverse=True) if reverse else setup()
    s,o,p,a,result = run(fixture); bad = deepcopy(result); answer = bad['answers'][0]
    if defect == 'swapped_target':
        target = answer['mathematical_claim']['target'];target['first'],target['second'] = target['second'],target['first']
    if defect == 'changed_scope':answer['mathematical_claim']['target']['evaluation_population'].pop()
    if defect == 'anchor_only':bad['attempts'].pop()
    if defect == 'duplicated_stage':bad['attempts'].append(deepcopy(bad['attempts'][0]))
    if defect == 'wrong_kind':answer['certificate']['results'][0]['kind'] = 'SPILLOVER'
    if defect == 'wrong_formula':answer['mathematical_claim']['expression'] = '0'
    if defect == 'wrong_sign':answer['certificate']['results'][0]['constituent_arms'][0]['coefficient'] = '-1/6'
    if defect == 'changed_input':answer['native_evidence']['a4_source']['source_id'] += '_other'
    if defect == 'wrong_envelope':answer['certificate']['contract_version'] = 'unrelated-certificate'
    if defect == 'blocked_state':bad['state'] = 'CHECK_BLOCKED'
    with pytest.raises(ValueError, match='DIAGNOSTIC_'):
        diagnostic.describe(p, result=bad, **reviews(a))


@pytest.mark.parametrize('reverse', [False,True])
def test_failed_native_replay_is_an_attempt_not_a_verified_effect(monkeypatch, reverse):
    from pfn_pipeline import identification_business as core, identification_composition as composition
    s,e,o,p = design_setup('D2','E4',reverse=True) if reverse else setup()
    a = approval_records(p)
    monkeypatch.setattr(composition if reverse else core,
                        'replay_verified_composition' if reverse else 'replay_verified_business_outcome',
                        lambda *args, **kwargs: False)
    result = dispatch.execute(s, 'q1', **o, **a)
    view = diagnostic.describe(p, result=result, **reviews(a))
    assert result['state'] == 'CHECK_BLOCKED' and result['backend_called'] and not result['independent_replay']
    assert method(view)['execution'] == 'EXECUTOR_REPORTED_ATTEMPT'
    assert method(view)['certificate']['state'] == 'NOT_REPORTED'
    assert method(view)['mathematical_applicability'] == 'NOT_ESTABLISHED'
