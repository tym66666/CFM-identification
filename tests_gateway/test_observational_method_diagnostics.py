"""R3 diagnostics preserve fixed W, joint support and independent review gates."""
from copy import deepcopy
from fractions import Fraction
import json
import pytest
from cfm_id import business_dispatch as dispatch, method_diagnostics as diagnostic, project
from cfm_id import method_requirements as requirements, network_observational_policy_dispatch as r3
from cfm_id_llm.query_conditioning_contract import MATCH_DECISION
from examples.network_observational_policy_reference import setup, approval_records
from tests_gateway.test_query_conditioning_contract import setup as conditioned_setup


def reviews(approvals):
    return {k:v for k,v in approvals.items() if k != 'research_protocol_selected'}


def prepare(fixture):
    s,e,o = fixture
    p = dispatch.inspect_methods(s, 'q1', **o)
    a = approval_records(p) if p.get('methods') else dict(research_protocol_selected=True)
    return s,o,p,a


def method(view):
    assert [r['method'] for r in view['methods']] == list(r3.METHODS)
    assert view['methods'][1]['planning_state']=='NOT_PLANNED_FOR_CURRENT_INPUT'
    return view['methods'][0]


def forbidden(*args, **kwargs):
    pytest.fail('A read-only diagnostic or blocked review called mathematics')


@pytest.mark.parametrize('scene', ['care','depots'])
def test_native_point_preserves_policy_fixed_context_population_and_replay(scene):
    s,o,p,a = prepare(conditioned_setup(scene))
    result = dispatch.execute(s, 'q1', **o, **a)
    before = deepcopy((p,a,result))
    view = diagnostic.describe(p, result=result, **reviews(a)); item = method(view)
    assert result['state'] == 'POINT' and result['independent_replay']
    assert (p,a,result) == before and not view['is_certificate'] and not view['grants_execution']
    assert view['diagnostics_scope'] == 'OBSERVATIONAL_FIXED_CONTEXT_POLICY_MEAN'
    observed = view['observational']; target = observed['prepared_target']
    assert observed['declared_target']['population'] == o['candidate']['target']['population']
    assert json.loads(target['context']) == dict(business_context=o['candidate']['study']['context'],
        fixed_pretreatment_W=o['candidate']['conditioning']['definition'])
    population = set(observed['declared_target']['population'])
    assert [n for n,w in zip(target['node_order'],target['unit_weights']) if Fraction(w)] == [n for n in target['node_order'] if n in population]
    assert observed['target_conditioning_review'] == p['target_conditioning_review']
    assert MATCH_DECISION in {r['key'] for r in item['reading_review']['conditions']}
    assert item['joint_policy_support']['probability'] == '1/2'
    assert item['certificate']['state'] == 'REPLAY_REPORTED' and not item['certificate']['verified_here']
    assert not view['independent_replay'] and not item['joint_policy_support']['checked_here']
    assert set(p['methods'][0]['science_worksheet']['decisions']) == {*r3.BASE_CONDITIONS,'a4_population_operator',*r3.A4_DECLARATIONS}


def test_readonly_entry_uses_existing_gates_without_reexecuting_or_granting_permission(monkeypatch):
    s,o,p,a = prepare(setup())
    result = dispatch.execute(s,'q1',**o,**a)
    from pfn_pipeline import identification_business as core
    monkeypatch.setattr(r3,'_compile',forbidden)
    monkeypatch.setattr(core,'identify_network_business_query',forbidden)
    monkeypatch.setattr(core,'replay_verified_business_outcome',forbidden)
    pending = project.diagnose_methods(s,'q1',**o,**reviews(a))
    assert method(pending)['joint_policy_support']['state'] == 'NOT_CHECKED'
    archived = diagnostic.describe(p,result=result,**reviews(a))
    assert method(archived)['certificate']['state'] == 'REPLAY_REPORTED'
    assert not dispatch.execute(s,'q1',**o,**dict(a,plan_review=archived))['backend_called']
    assert [x['method'] for x in requirements.catalog(r3.FAMILY)] == list(r3.METHODS)
    assert len(requirements.catalog()) == 3
    assert pending['observational']['target_conditioning_review'] is None  # Legacy fixture remains supported.


@pytest.mark.parametrize('layer,condition,decision', [
    ('reading','fixed_conditioning_matches_reviewed_query','PENDING'),
    ('reading','fixed_conditioning_matches_reviewed_query','REJECTED'),
    ('science','full_vector_conditional_exchangeability','PENDING'),
    ('science','full_vector_conditional_exchangeability','REJECTED'),
    ('science','same_study_and_conditioning','REJECTED')])
def test_each_required_review_is_preserved_even_when_declarations_match(monkeypatch,layer,condition,decision):
    s,o,p,a = prepare(conditioned_setup())
    a['native_reviews'][r3.METHOD][layer+'_review'].decisions[condition] = decision
    monkeypatch.setattr(r3,'_compile',forbidden)
    result = dispatch.execute(s,'q1',**o,**a)
    view = diagnostic.describe(p,result=result,**reviews(a)); item = method(view)
    assert not result['backend_called'] and not result['answers']
    assert item[layer+'_review']['state'] == decision
    assert any(r['key'] == condition and r['review_state'] == decision for r in item['outstanding_review_items'])
    assert item['joint_policy_support']['state'] == 'NOT_CHECKED'


@pytest.mark.parametrize('defect,expected', [
    ('unknown_exchangeability','NEEDS_INPUT'), ('refused_exchangeability','ADAPTER_NOT_CONNECTED'),
    ('sample_only','NEEDS_INPUT'), ('missing_policy','NEEDS_INPUT'),
    ('missing_population','NEEDS_INPUT'), ('missing_context','NEEDS_INPUT'),
    ('incomplete_support','NEEDS_INPUT'), ('a4_wrong_context','ADAPTER_NOT_CONNECTED'),
    ('uncovered_population','NEEDS_INPUT')])
def test_input_gaps_and_refusals_remain_native_stops(monkeypatch,defect,expected):
    kwargs = (dict(exchangeability=None) if defect == 'unknown_exchangeability' else
              dict(exchangeability=False) if defect == 'refused_exchangeability' else
              dict(sample_only=True) if defect == 'sample_only' else {})
    s,e,o = setup(**kwargs); f = o['candidate']
    if defect == 'missing_policy': f['target']['assignment'] = None
    elif defect == 'missing_population': f['target']['population'] = None
    elif defect == 'missing_context': f['conditioning']['definition'] = None
    elif defect == 'incomplete_support': f['information'][0]['complete_positive_assignment_support']['value'] = None
    elif defect == 'a4_wrong_context': f['information'][0]['same_study_and_conditioning']['value'] = False
    elif defect == 'uncovered_population': f['information'][0]['outcome_nodes'] = f['study']['nodes'][:1]
    monkeypatch.setattr(r3,'_compile',forbidden)
    p = dispatch.inspect_methods(s,'q1',**o)
    result = dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    view = diagnostic.describe(p)
    assert p['state'] == result['state'] == expected and not result['backend_called']
    assert method(view)['planning_state'] == 'NOT_PLANNED_FOR_CURRENT_INPUT'
    assert method(view)['joint_policy_support']['state'] == 'NOT_CHECKED'
    assert not view['nonidentification_proved'] and view['mathematical_claim'] is None
    assert view['clarification_questions'] == p['clarification_questions']


def test_positive_marginals_do_not_override_zero_full_policy_support():
    s,o,p,a = prepare(setup(zero_support=True))
    rows = o['candidate']['information'][0]['assignment_masses']
    assert all(0 < sum(Fraction(r['probability'])*r['assignment'][n] for r in rows) < 1 for n in o['candidate']['study']['nodes'])
    before = diagnostic.describe(p,**reviews(a))
    assert method(before)['joint_policy_support']['state'] == 'NOT_CHECKED'
    result = dispatch.execute(s,'q1',**o,**a)
    after = diagnostic.describe(p,result=result,**reviews(a))
    assert result['state'] == 'UNSUPPORTED' and result['reason_code'] == 'ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT'
    assert method(after)['joint_policy_support']['state'] == 'NATIVE_ZERO_SUPPORT_REPORTED'
    assert method(after)['certificate']['state'] == 'NOT_REPORTED'
    assert not after['nonidentification_proved'] and not result['partial_fallback_performed']


@pytest.mark.parametrize('changed', ['policy','fixed_context','population'])
def test_target_changes_invalidate_old_review_and_cannot_reuse_certificate(changed):
    s,o,p,a = prepare(conditioned_setup())
    result = dispatch.execute(s,'q1',**o,**a)
    new = deepcopy(o); f = new['candidate']
    if changed == 'policy': f['target']['assignment'] = {n:0 for n in f['study']['nodes']}
    elif changed == 'fixed_context': f['conditioning']['definition'] = '另一个处理前需求背景'
    else: f['target']['population'] = f['target']['population'][:1]
    np = dispatch.inspect_methods(s,'q1',**new)
    blocked = dispatch.execute(s,'q1',**new,**a)
    view = diagnostic.describe(np,result=blocked,**reviews(a))
    assert not blocked['backend_called'] and view['common_review']['state'] == 'INVALID'
    with pytest.raises(ValueError,match='DIAGNOSTIC_RESULT_PLAN_BINDING_MISMATCH'):
        diagnostic.describe(np,result=result)


@pytest.mark.parametrize('defect', ['context','policy','weights','support','formula','duplicate_attempt','input','replay','blocked'])
def test_inconsistent_saved_evidence_is_not_shown_as_replayed(defect):
    s,o,p,a = prepare(setup())
    result = dispatch.execute(s,'q1',**o,**a); bad = deepcopy(result); answer = bad['answers'][0]
    if defect == 'context': answer['native_evidence']['target']['context'] = '另一个背景'
    elif defect == 'policy': answer['native_evidence']['target']['policy_assignment'][0] = 0
    elif defect == 'weights': answer['native_evidence']['target']['unit_weights'] = ['1','0','0']
    elif defect == 'support': answer['certificate']['target_observational_probability'] = '1/4'
    elif defect == 'formula': answer['mathematical_claim']['expression'] = '0'
    elif defect == 'duplicate_attempt': bad['attempts'] *= 2
    elif defect == 'input': answer['reviewed_input_sha256'] = 'foreign'
    elif defect == 'replay': answer['independent_replay'] = False
    elif defect == 'blocked': bad['state'] = 'CHECK_BLOCKED'
    with pytest.raises(ValueError,match='DIAGNOSTIC_'):
        diagnostic.describe(p,result=bad,**reviews(a))


def test_failed_native_replay_keeps_attempt_but_never_reports_verified_support(monkeypatch):
    from pfn_pipeline import identification_business as core
    s,o,p,a = prepare(setup())
    monkeypatch.setattr(core,'replay_verified_business_outcome',lambda *a,**k:False)
    result = dispatch.execute(s,'q1',**o,**a)
    view = diagnostic.describe(p,result=result,**reviews(a)); item = method(view)
    assert result['state'] == 'CHECK_BLOCKED' and result['backend_called'] and not result['independent_replay']
    assert item['native_attempt']['raw_attempt']['state'] == 'POINT'
    assert item['certificate']['state'] == 'NOT_REPORTED'
    assert item['joint_policy_support']['state'] == 'NOT_ESTABLISHED'
