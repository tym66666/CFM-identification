"""Source aliasing, explicit kernel views and whole-case completeness, offline."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case as work
from cfm_id import dag_business as native_api
from cfm_id_llm.dag_query_reading import parse, reference_catalog
from examples.business_case_reference import scenario, submission, short_fixture
from examples.business_dispatch_reference import approve, approvals, from_case
from examples.dag_business_reference import cases
from examples.dag_frontdoor_business_reference import _case as frontdoor_case


def execute(s, rows, review=None):
    return work.execute_case(s, rows, case_review=review or approve(work.prepare_case(s)['case_worksheet']),
                             research_protocol_selected=True)


def test_short_sources_expand_exactly_without_repair_or_approval():
    s, native = scenario()
    row, entry, plan = submission(s, native, 'q1', [0])
    before = deepcopy(row['candidate'])
    decoded = parse(entry['bundle'], before, binding=entry['fact_binding_sha256'])
    assert decoded['native_candidate'] == native
    assert row['candidate'] == before
    assert plan['reading_candidate'] == before and plan['native_candidate'] == native
    assert plan['state'] == 'REVIEW_REQUIRED' and not plan['backend_called']
    payload = json.loads(entry['request']['user'].split('\n\n本次只读取')[0])
    assert all(len(k) == 5 and k.startswith('s') for k in payload['source_catalog'])
    assert 'src_' not in json.dumps(payload, ensure_ascii=False)
    for alias, item in payload['source_catalog'].items():
        full = reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256'])['aliases'][alias]
        assert item['text'] == full['text'] and item['doc_id'] == full['doc_id']
    assert 'requested_intervention_values_and_kernel_view' in plan['plan_worksheet']['decisions']


@pytest.mark.parametrize('corruption', ['unknown', 'duplicate', 'full_hash', 'context', 'version', 'extra_approval'])
def test_invalid_short_wire_blocked_without_guessing(monkeypatch, corruption):
    s, native = scenario(); row, entry, plan = submission(s, native, 'q1', [0])
    raw = deepcopy(row['candidate'])
    if corruption == 'unknown': raw['variables'][0]['source_ids'] = ['s9999']
    elif corruption == 'duplicate': raw['variables'][0]['source_ids'] *= 2
    elif corruption == 'full_hash': raw['variables'][0]['source_ids'] = native['variables'][0]['source_ids']
    elif corruption == 'context': raw['reference_context'] = 'c000000000000'
    elif corruption == 'version': raw['version'] = 'dag-frontdoor-reading-2'
    else: raw['approved'] = True
    row['candidate'] = raw
    def forbidden(*args, **kwargs): raise AssertionError('invalid source reached a solver')
    monkeypatch.setattr(native_api, 'submit_reviewed', forbidden)
    result = execute(s, {'q1': row})
    assert result['results'][0]['result']['state'] == 'CHECK_BLOCKED'
    assert not result['backend_called'] and not result['all_queries_identified']
    assert row['candidate'] == raw


def test_changed_material_and_other_query_do_not_rebind_short_ids():
    s, native = scenario(); row, entry, _ = submission(s, native, 'q1', [0])
    b = deepcopy(entry['bundle']); b['documents']['context'] += '\n新增范围说明。'
    with pytest.raises(ValueError, match='STALE_QUERY_REFERENCE_CONTEXT'):
        parse(b, row['candidate'], binding=entry['fact_binding_sha256'])
    other, other_entry, _ = submission(s, native, 'q2', [1])
    assert other['candidate']['reference_context'] != row['candidate']['reference_context']
    other['candidate'] = row['candidate']
    r = execute(s, {'q2':other})
    assert r['results'][1]['result']['state'] == 'CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('values', [[True], [2], [0,0], [], ['0']])
def test_invalid_intervention_values_do_not_enter_native_core(values):
    s, native = scenario(); row, _, _ = submission(s, native, 'q1', [0])
    row['candidate']['query_scope']['values'] = values
    result = execute(s, {'q1':row})
    assert result['results'][0]['result']['state'] == 'CHECK_BLOCKED'
    assert not result['backend_called']


@pytest.mark.parametrize('kind,state', [('UNKNOWN','NEEDS_INPUT'), ('OTHER','ADAPTER_NOT_CONNECTED')])
def test_unknown_or_other_scope_is_not_defaulted_to_whole_kernel(kind,state):
    s,native = scenario(); row,_,_ = submission(s,native,'q1',[0])
    row['candidate']['query_scope'].update(kind=kind,values=[])
    result = execute(s, {'q1':row})
    assert result['results'][0]['result']['state'] == state and not result['backend_called']


def test_whole_case_needs_every_query_and_retains_separate_targets():
    s,native = scenario()
    rows = {qid:submission(s,native,qid,[i])[0] for i,qid in enumerate(('q1','q2'))}
    one = execute(s, {'q1':rows['q1']})
    assert one['state'] == 'CASE_INCOMPLETE' and one['identified_query_ids'] == ['q1']
    assert one['unresolved_query_ids'] == ['q2'] and not one['all_queries_identified']
    both = execute(s, rows)
    assert both['state'] == 'ALL_QUERIES_IDENTIFIED' and both['all_queries_identified']
    assert both['expected_query_ids'] == both['identified_query_ids'] == ['q1','q2']
    assert both['mathematical_claim'] is both['certificate'] is None
    assert not both['production_admission'] and not both['estimation_handoff_allowed']
    for i,item in enumerate(both['results']):
        assert item['query_id'] == f'q{i+1}'
        for answer in item['result']['answers']:
            view = answer['query_view']
            assert view['intervention_values'] == [i] and view['kernel_view_checked']
            assert view['kernel_claim_sha256'] == intake._sha(answer['mathematical_claim'])
            assert view['certificate_sha256'] == intake._sha(answer['certificate'])
            assert answer['independent_replay']


def test_frontdoor_view_keeps_inner_treatment_sum_unmodified():
    s,native = scenario(frontdoor_case('kernel_view', 'implicit_role'))
    row,_,_ = submission(s,native,'q1',[0])
    result = execute(s,{'q1':row})['results'][0]['result']
    assert result['state'] == 'POINT'
    answer = result['answers'][0]
    assert answer['query_view']['intervention_values'] == [0]
    functional = answer['mathematical_claim']['functional']
    assert functional == answer['certificate']['functional']
    assert functional['free_values']['intervention_value']['domain'] == [0,1]
    inner = functional['expression']['summand']['factors'][1]
    assert inner['bind']['role'] == 'treatment_marginal_value' and inner['bind']['domain'] == [0,1]


@pytest.mark.parametrize('status', ['PENDING','REJECTED'])
def test_case_coverage_review_needed_before_any_solver(monkeypatch,status):
    s,native = scenario(); row,_,_ = submission(s,native,'q1',[0])
    review = approve(work.prepare_case(s)['case_worksheet'])
    review = review.model_copy(update={'decisions':{k:status for k in review.decisions}})
    def forbidden(*a,**kw): raise AssertionError('case coverage approval bypassed')
    monkeypatch.setattr(native_api,'submit_reviewed',forbidden)
    r = execute(s,{'q1':row},review)
    assert r['state'] == ('REVIEW_REQUIRED' if status=='PENDING' else 'CHECK_BLOCKED')
    assert not r['backend_called'] and not r['results']


def test_missing_case_review_and_scientific_review_are_not_created():
    s,native = scenario(); row,_,_ = submission(s,native,'q1',[0])
    r = work.execute_case(s,{'q1':row},research_protocol_selected=True)
    assert r['state'] == 'REVIEW_REQUIRED' and not r['backend_called']
    row.pop('native_reviews')
    r = execute(s,{'q1':row})
    assert r['results'][0]['result']['state'] == 'REVIEW_REQUIRED' and not r['backend_called']


def test_scope_change_invalidates_plan_approval_even_with_identical_native_model(monkeypatch):
    s,native = scenario(); row,_,_ = submission(s,native,'q1',[0])
    row['candidate']['query_scope']['values'] = [1]
    def forbidden(*a,**kw): raise AssertionError('scope changed after plan approval')
    monkeypatch.setattr(native_api,'submit_reviewed',forbidden)
    r = execute(s,{'q1':row})
    assert r['results'][0]['result']['state'] == 'CHECK_BLOCKED' and not r['backend_called']


def test_rejected_second_query_never_becomes_success_from_first_query_proof():
    s,native=scenario()
    first,_,_=submission(s,native,'q1',[0])
    second,_,_=submission(s,native,'q2',[1])
    review=second['plan_review']
    second['plan_review']=review.model_copy(update={'decisions':{k:'REJECTED' for k in review.decisions}})
    result=execute(s,{'q1':first,'q2':second})
    assert result['state']=='CASE_INCOMPLETE' and result['identified_query_ids']==['q1']
    assert result['results'][1]['result']['state']=='CHECK_BLOCKED'
    assert result['unresolved_query_ids']==['q2']


def test_all_values_is_a_full_kernel_view_without_estimation():
    s,native=scenario(two_queries=False)
    row,_,_=submission(s,native,'q1',None)
    result=execute(s,{'q1':row})
    assert result['all_queries_identified']
    view=result['results'][0]['result']['answers'][0]['query_view']
    assert view['intervention_values']==[0,1] and view['requested_scope']=='ALL_TREATMENT_VALUES'
    assert view['numeric_value'] is None and not result['estimation_handoff_allowed']


@pytest.mark.parametrize('bad', ['unknown_query','saved_result','stale_request','wrong_authority'])
def test_invalid_whole_case_inputs_cannot_claim_completion(bad):
    s,native = scenario(); row,_,_ = submission(s,native,'q1',[0]); rows={'q1':row}
    if bad=='unknown_query': rows['q99']=deepcopy(row)
    elif bad=='saved_result': row['result']={'state':'POINT','independent_replay':True}
    elif bad=='stale_request': row['request_sha256']='0'*64
    else:
        row['query_review']=row['query_review'].model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    r=execute(s,rows)
    assert not r['all_queries_identified'] and not r['backend_called']


def test_dropping_a_query_invalidates_whole_case_coverage_review():
    s,native = scenario(); row,_,_ = submission(s,native,'q1',[0])
    review=approve(work.prepare_case(s)['case_worksheet'])
    raw=deepcopy(s.candidate);raw['queries'].pop()
    new=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    r=execute(new,{'q1':row},review)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_negative_query_remains_unanswered_not_whole_case_success():
    s,native = scenario(cases()[5])
    rows={qid:submission(s,native,qid,[i])[0] for i,qid in enumerate(('q1','q2'))}
    r=execute(s,rows)
    assert r['state']=='CASE_INCOMPLETE' and not r['backend_called']
    assert [x['result']['state'] for x in r['results']]==['NEEDS_INPUT','NEEDS_INPUT']
    assert r['unresolved_query_ids']==['q1','q2']


def test_legacy_fact_reading_is_explicit_and_not_silently_treated_as_query_scope():
    s,_=from_case(cases()[0])
    assert s.fact_format=='source_hash'
    r=execute(s,{})
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['all_queries_identified']
    original=s.candidate
    new=intake.configure_fact_format(s,'short_refs')
    assert new.candidate==original and new.request_sha256==s.request_sha256
    assert intake._sha(new.model_dump(mode='json'))!=intake._sha(s.model_dump(mode='json'))


def test_whole_case_cli_recomputes_results_without_query_or_method_choice(tmp_path):
    from cfm_id.business_case_cli import main
    s,native=scenario();row,_,_=submission(s,native,'q1',[0])
    def serial(v):
        if hasattr(v,'model_dump'):return v.model_dump(mode='json')
        if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
        if isinstance(v,list):return [serial(x) for x in v]
        return v
    intake.save(s,tmp_path/'intake.json')
    intake.write_json(tmp_path/'submissions.json',serial({'q1':row}))
    intake.write_json(tmp_path/'case_review.json',serial(approve(work.prepare_case(s)['case_worksheet'])))
    base=['--intake',str(tmp_path/'intake.json')]
    assert main(['plan',*base,'--output',str(tmp_path/'plan.json')])==0
    assert main(['execute',*base,'--submissions',str(tmp_path/'submissions.json'),
        '--case-review',str(tmp_path/'case_review.json'),'--select-research-protocol',
        '--output',str(tmp_path/'result.json')])==0
    assert intake.read_json(tmp_path/'result.json')['unresolved_query_ids']==['q2']
