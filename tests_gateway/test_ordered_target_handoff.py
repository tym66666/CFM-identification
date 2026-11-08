"""Reviewed target handoff is context, never evidence or a mathematical proof."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm import ordered_target_handoff as handoff
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from tests_gateway import test_ordered_comparison_contract as prior
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet,record,submit


def enable(monkeypatch):
    monkeypatch.setattr(prior,'received',lambda case,raw,short=True:receive(case,raw,short=short,profile=handoff.CONTRACT))


def focus(entry):
    return json.loads(entry['request']['user'].rsplit('\n',1)[1])['focus']


def test_clean_schema_roles_and_review_share_one_local_meaning():
    case,_,raw=prior.local_fixture()
    system,user,_=make_compact_request(case,a0_response_contract=handoff.CONTRACT)
    schema=split_user(user)[2]
    assert 'CompactQuery' not in schema['$defs']
    assert '从A变到B的增加量=B−A，减少量=A−B' in system
    assert '把operation中的两端名称替换成本次已填的业务状态' not in system
    s=receive(case,raw,profile=handoff.CONTRACT);w=sheet(s)
    for name in handoff.LOCAL_ROLES:
        assert schema['$defs']['OrderedLocalSemantics']['properties'][name]['description']==w['fields'][f'queries.q1.semantics.{name}']['definition']['wire_description']
    for name in handoff.ordered.RULES:
        assert schema['$defs']['OrderedLocalExpression']['properties'][name]['description']==w['fields'][f'queries.q1.comparison_expression.{name}']['definition']['wire_description']


@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('reverse',[False,True])
def test_native_positions_and_proof_preserved_with_reviewed_handoff(monkeypatch,kind,reverse):
    from examples.network_effect_dispatch_reference import approval_records
    enable(monkeypatch)
    s,e,o=prior.execution(kind,reverse);before=deepcopy(s.candidate);f=focus(e)
    p=dispatch.inspect_methods(s,'q1',**o)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert result['state']=='POINT' and result['independent_replay']
    assert result['mathematical_claim']['target']['first']==[o['candidate']['target']['first'][k] for k in ('own','exposure')]
    selected=s.candidate['queries'][0];bound=f['reviewed_ordered_target']
    assert bound['binding_sha256']==e['fact_binding_sha256']
    for name in ('first','second'):
        assert bound[name]=={k:v for k,v in selected['comparison_expression'][name].items() if k!='refs'}
        assert 'own' not in bound[name] and 'exposure' not in bound[name]
    assert bound['conditions']['aggregation']['value']==selected['semantics']['aggregation']['value']
    assert '比较运算：主方案减基准方案' not in json.dumps(f,ensure_ascii=False)
    assert not bound['scientific_approval'] and not bound['is_citable_source']
    assert 'semantics' not in f and 'intervention' not in bound['conditions']
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    assert all('reviewed_ordered_target' not in v['doc_id'] for v in body['source_catalog'].values())
    assert '如果原文与已审核目标不一致' in e['request']['system']
    assert s.candidate==before


def test_handoff_requires_current_full_review_and_scope(monkeypatch):
    enable(monkeypatch);case,_,raw=prior.local_fixture()
    s=receive(case,raw,profile=handoff.CONTRACT)
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    good=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=good)
    old=receive(case,raw,profile='ordered-local-comparison-1')
    assert dispatch.prepare_reader(old,'q1',query_review=good)['request'] is None
    changed=deepcopy(s.candidate);a=changed['queries'][0]['comparison_expression'];a['first'],a['second']=a['second'],a['first']
    newer=intake.receive_candidate(s,changed,request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(newer,'q1',query_review=good)['request'] is None
    assert not e['production_admission']
    bad=deepcopy(raw['queries'][0]);bad['comparison_expression']['form']='UNSPECIFIED'
    with pytest.raises(ValueError,match='REVIEWED_ORDER_REQUIRED'):handoff.fact_focus(bad,query_id='q1',binding='0'*64)


def test_raw_meanings_are_never_parsed_to_coordinates_or_repaired(monkeypatch):
    enable(monkeypatch);case,_,raw=prior.local_fixture()
    # Deliberately incorrect but syntactically valid candidate: the code cannot approve semantics.
    raw['queries'][0]['comparison_expression']['first']['value']='另一状态，具体做法未确定'
    s=receive(case,raw,profile=handoff.CONTRACT);w=sheet(s);r=record(w)
    r['decisions']['queries.q1.comparison_expression.first']['value_state']='REJECTED'
    assert submit(s,r)['state']=='CHECK_BLOCKED'
    b=handoff.fact_focus(raw['queries'][0],query_id='q1',binding='0'*64)
    assert b['reviewed_ordered_target']['first']['value']=='另一状态，具体做法未确定'
    assert not b['reviewed_ordered_target']['scientific_approval']


@pytest.mark.parametrize('missing',['first','second','direction'])
def test_new_prompt_cannot_release_missing_target(monkeypatch,missing):
    enable(monkeypatch);prior.test_missing_end_or_unknown_order_never_fills_or_executes(missing,'MISSING')


def test_reversed_fact_candidate_requires_rejection_and_never_inherits_a0_approval(monkeypatch):
    from examples.network_effect_dispatch_reference import approval_records
    enable(monkeypatch);s,e,o=prior.execution('SPILLOVER_EFFECT',True)
    raw=o['candidate'];raw['target']['first'],raw['target']['second']=raw['target']['second'],raw['target']['first']
    before=deepcopy(raw);p=dispatch.inspect_methods(s,'q1',**o)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    approvals=approval_records(p)
    for review in approvals['native_reviews'].values():
        review['reading_review'].decisions['local_states_and_first_minus_second_direction']='REJECTED'
    r=dispatch.execute(s,'q1',**o,**approvals)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called'] and raw==before


@pytest.mark.parametrize('kind',['point','partial'])
def test_policy_contract_stays_nonlocal(monkeypatch,kind):
    enable(monkeypatch);prior.test_complete_policy_contrast_preserves_business_roles_and_replay(kind)


def test_dag_and_mixed_queries_stay_separate(monkeypatch):
    enable(monkeypatch);prior.test_dag_retains_original_wire_and_native_replay()
    prior.test_mixed_queries_keep_distinct_raw_review_paths_and_source_context()


def test_recheck_shares_current_direction_duties_without_replacement_answer(monkeypatch):
    from cfm_id.intake_reading_revision import prepare_recheck
    from tests_gateway.test_reading_review_guards import feedback
    enable(monkeypatch);case,_,raw=prior.local_fixture();s=receive(case,raw,profile=handoff.CONTRACT)
    w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet'];f=feedback(w)
    f['issues'][0]['field_path']='/queries/0/comparison_expression/first'
    newer=prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST');request=intake.prepare_request(newer)
    context=json.loads(request['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert handoff.DIRECTION in context['field_role_constraints'][0]['field_role']
    assert 'PRIVATE_REASON_STAYS_LOCAL' not in request['user_prompt']
