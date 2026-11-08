"""Shared diagnostics preserve ordered targets and native joint proof boundaries."""
from copy import deepcopy
import pytest
from cfm_id import business_dispatch as dispatch, method_diagnostics as diagnostic, project
from cfm_id import method_requirements as requirements, network_contrast_dispatch as contrast
from examples.network_contrast_dispatch_reference import setup, approval_records
from examples.network_r2_contrast_reference import setup as r2_setup


def review_options(records):
    return {k:v for k,v in records.items() if k != 'research_protocol_selected'}


def execute(fixture=setup, **options):
    session, entry, reading = fixture(**options)
    plan = dispatch.inspect_methods(session, 'q1', **reading)
    approvals = approval_records(plan)
    result = dispatch.execute(session, 'q1', **reading, **approvals)
    return session, reading, plan, approvals, result


def rows(report):
    return {r['method']:r for r in report['methods']}


def forbidden(*args, **kwargs):
    pytest.fail('Diagnostic or joint comparison called an unrelated backend')


@pytest.mark.parametrize('kind', ['r1b', 'r2', 'both', 'partial', 'cancellation'])
def test_native_evidence_shapes_share_diagnostics_without_losing_scope(monkeypatch, kind):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver, 'solve', forbidden)
    fixture = r2_setup if kind in ('r2', 'both') else setup
    options = ({'information':'full'} if kind == 'both' else {}
               if kind in ('r1b', 'r2') else {'kind':kind, 'bounds':('1/4','3/4')}
               if kind == 'partial' else {'kind':kind})
    s, o, p, a, result = execute(fixture, **options)
    before = deepcopy((p, a, result))
    view = diagnostic.describe(p, result=result, **review_options(a))
    assert (p, a, result) == before
    assert result['independent_replay'] and not view['is_certificate'] and not view['grants_execution']
    assert view['diagnostics_scope'] == 'ORDERED_POLICY_MEAN_DIFFERENCE'
    assert view['comparison']['ordered_coordinates']['first'] == p['proposed_target']['first']
    assert view['comparison']['ordered_coordinates']['operation'] == 'first_minus_second'
    assert view['comparison']['common_scope']['unit_weights'] == p['proposed_target']['unit_weights']
    for answer in result['answers']:
        item = rows(view)[answer['method']]
        assert item['mathematical_applicability'] == 'NATIVE_RESULT_REPORTED'
        assert item['certificate']['state'] == 'REPLAY_REPORTED' and not item['certificate']['verified_here']
        assert not item['certificate']['separate_interval_subtraction']
    if kind in ('partial', 'cancellation'):
        assert result['attempts'] == []  # A joint solve, not missing endpoint evidence.
        assert result['mathematical_claim']['interval'] == (['-1/2','1/2'] if kind == 'partial' else ['1/5','1/5'])
        assert rows(view)[contrast.BOUNDED_METHOD]['certificate']['calculation_reported'] == 'JOINT_CONTRAST_IN_ONE_MODEL'
        assert rows(view)[contrast.BOUNDED_METHOD]['certificate']['sharp_scope'] == 'CURRENT_REVIEWED_MODEL'
    if kind == 'both':
        failed = rows(view)[contrast.POINT_METHOD]
        assert failed['mathematical_applicability'] == 'NATIVE_NOT_APPLICABLE'
        assert set(failed['native_attempt']['endpoint_attempts']) == {'first','second'}
        assert any(r.get('endpoint') == 'first' for r in view['next_actions'])


def test_readonly_public_entry_uses_registry_and_actual_pair_reviews(monkeypatch):
    s, e, o = setup()
    p = dispatch.inspect_methods(s, 'q1', **o)
    a = approval_records(p)
    monkeypatch.setattr(contrast, '_compile_pair', forbidden)
    before = deepcopy((p, a, o))
    view = project.diagnose_methods(s, 'q1', **o, **review_options(a))
    assert not view['backend_called'] and not view['independent_replay']
    assert (p, a, o) == before
    assert {r['method'] for r in requirements.catalog(contrast.FAMILY)} == {
        contrast.POINT_METHOD,contrast.R2_METHOD,contrast.BOUNDED_METHOD,contrast.mean_order.METHOD}
    assert len(requirements.catalog()) == 3  # Historical default remains the mean family.
    assert set(contrast.PAIR_DECISIONS) <= {r['key'] for r in view['common_review']['conditions']}
    method = rows(view)[contrast.POINT_METHOD]
    assert set(contrast.PAIR_DECISIONS) <= {r['key'] for r in method['reading_review']['conditions']}
    blocked = dispatch.execute(s, 'q1', **o, **dict(a, plan_review=view))
    assert not blocked['backend_called']


@pytest.mark.parametrize('defect,expected', [
    ('missing_second','NEEDS_INPUT'), ('unknown_direction','NEEDS_INPUT'),
    ('different_population','ADAPTER_NOT_CONNECTED'), ('different_context','ADAPTER_NOT_CONNECTED'),
    ('incomplete_model','NEEDS_INPUT'), ('extra_constraint','ADAPTER_NOT_CONNECTED')])
def test_native_input_stops_and_sources_remain_visible(monkeypatch, defect, expected):
    s, e, o = setup('partial')
    raw = o['candidate']; target = raw['target']
    if defect == 'missing_second':target['second']['assignment'] = None
    if defect == 'unknown_direction':target['operation'] = 'UNKNOWN'
    if defect == 'different_population':target['second']['population'] = ['甲店']
    if defect == 'different_context':target['shared_outcome_and_context']['value'] = False
    if defect == 'incomplete_model':raw['bounded_model']['no_additional_coupling_constraints']['value'] = None
    if defect == 'extra_constraint':raw['additional_restrictions'] = [dict(text='还要求甲乙两店均值相等。', source_ids=target['source_ids'])]
    before = deepcopy(raw)
    monkeypatch.setattr(contrast, '_compile_pair', forbidden)
    view = project.diagnose_methods(s, 'q1', **o)
    result = dispatch.execute(s, 'q1', **o, research_protocol_selected=True)
    assert view['source_plan_state'] == result['state'] == expected
    assert not view['backend_called'] and not result['backend_called'] and raw == before
    native_target = dispatch.inspect_methods(s, 'q1', **o)['contrast_target']
    assert view['comparison']['declared_target'] == native_target
    # Parsing resolves source aliases. It must preserve the actual question fields.
    for side in ('first','second'):
        assert native_target[side]['assignment'] == target[side]['assignment']
        assert native_target[side]['population'] == target[side]['population']
    assert native_target['operation'] == target['operation']
    assert all(r['certificate']['state'] == 'NOT_REPORTED' for r in view['methods'])


def test_one_successful_endpoint_never_becomes_a_successful_difference():
    s, o, p, a, result = execute(r2_setup, quota=1)
    view = diagnostic.describe(p, result=result, **review_options(a))
    method = rows(view)[contrast.R2_METHOD]
    endpoints = method['native_attempt']['endpoint_attempts']
    assert endpoints['second']['state'] == 'POINT' and endpoints['first']['state'] == 'UNSUPPORTED'
    assert method['certificate']['state'] == 'NOT_REPORTED' and not view['nonidentification_proved']
    assert not result['partial_fallback_performed']


def test_endpoint_exclusions_explain_unplanned_method_without_guessing_missing_conditions():
    s, e, o = r2_setup(sufficiency=None)
    view = project.diagnose_methods(s, 'q1', **o)
    assert view['source_plan_state'] == 'NEEDS_INPUT'
    method = rows(view)[contrast.R2_METHOD]
    assert method['planning_state'] == 'NOT_PLANNED_FOR_CURRENT_INPUT'
    assert method['endpoint_plans']['first']['method_exclusion']['reason_code'] == 'R2_ADDITIONAL_DECLARATIONS_NOT_ESTABLISHED'
    assert method['mathematical_applicability'] == 'NOT_CHECKED'


@pytest.mark.parametrize('decision', ['PENDING','REJECTED','STALE'])
def test_all_branch_preflight_preserved(monkeypatch, decision):
    s, e, o = r2_setup(information='full')
    p = dispatch.inspect_methods(s, 'q1', **o); a = approval_records(p)
    record = a['native_reviews'][contrast.R2_METHOD]['science_review']
    if decision == 'STALE':
        a['native_reviews'][contrast.R2_METHOD]['science_review'] = record.model_copy(update={'binding_sha256':'0'*64})
    else:record.decisions[next(iter(record.decisions))] = decision
    monkeypatch.setattr(contrast, '_compile_pair', forbidden)
    result = dispatch.execute(s, 'q1', **o, **a)
    view = diagnostic.describe(p, result=result, **review_options(a))
    assert not result['backend_called'] and not view['branches_independently_authorized']
    assert rows(view)[contrast.POINT_METHOD]['science_review']['state'] == 'ACCEPTED'
    assert rows(view)[contrast.R2_METHOD]['science_review']['state'] == ('INVALID' if decision == 'STALE' else decision)
    assert all(m['execution'] == 'NOT_RUN' for m in view['methods'])


def test_reversed_direction_requires_new_reviews_and_reports_negative_joint_value():
    s, o, p, a, result = execute(kind='cancellation')
    changed = deepcopy(o); t = changed['candidate']['target']; t['first'],t['second'] = t['second'],t['first']
    new_plan = dispatch.inspect_methods(s, 'q1', **changed)
    blocked = dispatch.execute(s, 'q1', **changed, **a)
    view = diagnostic.describe(new_plan, result=blocked, **review_options(a))
    assert view['common_review']['state'] == 'INVALID' and not blocked['backend_called']
    with pytest.raises(ValueError, match='DIAGNOSTIC_RESULT_PLAN_BINDING_MISMATCH'):
        diagnostic.describe(new_plan, result=result)
    fresh = approval_records(new_plan)
    reversed_result = dispatch.execute(s, 'q1', **changed, **fresh)
    view = diagnostic.describe(new_plan, result=reversed_result, **review_options(fresh))
    assert reversed_result['mathematical_claim']['interval'] == ['-1/5','-1/5']
    assert view['comparison']['ordered_coordinates']['first'] == p['proposed_target']['second']
    assert rows(view)[contrast.BOUNDED_METHOD]['certificate']['conclusion'] == 'POINT'


@pytest.mark.parametrize('kind,defect', [
    ('point','reversed_certificate'), ('point','changed_weights'), ('point','missing_endpoint'),
    ('point','duplicate_endpoint'), ('point','wrong_family'), ('point','replay_false'),
    ('partial','endpoint_certificate'), ('partial','changed_interval'), ('partial','changed_input'),
    ('partial','blocked_state')])
def test_incoherent_records_cannot_be_displayed_as_replayed_evidence(kind, defect):
    s, o, p, a, result = execute(kind=kind)
    bad = deepcopy(result); answer = bad['answers'][0]
    if defect == 'reversed_certificate':
        t = answer['certificate']['target']; t['first'],t['second'] = t['second'],t['first']
    if defect == 'changed_weights':answer['mathematical_claim']['target']['unit_weights'][0] = '1'
    if defect == 'missing_endpoint':bad['attempts'].pop()
    if defect == 'duplicate_endpoint':bad['attempts'].append(deepcopy(bad['attempts'][0]))
    if defect == 'wrong_family':bad['fact_family'] = requirements.FAMILY
    if defect == 'replay_false':answer['independent_replay'] = False
    if defect == 'endpoint_certificate':answer['certificate']['version'] = 'bounded-policy-1'
    if defect == 'changed_interval':answer['mathematical_claim']['interval'] = ['0','0']
    if defect == 'changed_input':answer['native_evidence']['information']['second']['bounds'][0]['upper'] = '2'
    if defect == 'blocked_state':bad['state'] = 'CHECK_BLOCKED'
    with pytest.raises(ValueError, match='DIAGNOSTIC_'):
        diagnostic.describe(p, result=bad, **review_options(a))


def test_incompatible_joint_model_does_not_gain_a_certificate():
    s, e, o = setup('partial')
    o['candidate']['target']['second'] = deepcopy(o['candidate']['target']['first'])
    o['candidate']['bounded_model']['bounds'][0].update(lower='3/4', upper='1')
    p = dispatch.inspect_methods(s, 'q1', **o); a = approval_records(p)
    result = dispatch.execute(s, 'q1', **o, **a)
    view = diagnostic.describe(p, result=result, **review_options(a))
    assert result['state'] == 'INCOMPATIBLE' and not result['independent_replay']
    assert rows(view)[contrast.BOUNDED_METHOD]['certificate']['state'] == 'NOT_REPORTED'
    assert not result['backend_called']  # Native model validation stops before solving.
    assert rows(view)[contrast.BOUNDED_METHOD]['execution'] == 'NOT_RUN'
    assert view['execution_record']['state'] == 'INCOMPATIBLE'


@pytest.mark.parametrize('kind', ['point','partial'])
def test_failed_native_replay_reports_attempt_without_a_certificate(monkeypatch, kind):
    from cfm_id import fixed_comparison, bounded_contrast_verify
    module = fixed_comparison if kind == 'point' else bounded_contrast_verify
    monkeypatch.setattr(module, 'replay', lambda *a, **kw: False)
    s, o, p, a, result = execute(kind=kind)
    view = diagnostic.describe(p, result=result, **review_options(a))
    method = contrast.POINT_METHOD if kind == 'point' else contrast.BOUNDED_METHOD
    assert result['state'] == 'CHECK_BLOCKED' and result['backend_called']
    assert not result['independent_replay']
    assert rows(view)[method]['execution'] == 'EXECUTOR_REPORTED_ATTEMPT'
    assert rows(view)[method]['mathematical_applicability'] == 'NOT_ESTABLISHED'
    assert rows(view)[method]['certificate']['state'] == 'NOT_REPORTED'
