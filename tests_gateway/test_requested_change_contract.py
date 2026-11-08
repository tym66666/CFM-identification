"""Quantity syntax is auditable compilation, not text inference or proof approval."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm import requested_change_contract as change
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.compact_wire_diagnostics import diagnose
from tests_gateway import test_ordered_comparison_contract as prior
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet,record,submit
from examples.network_effect_dispatch_reference import approval_records

def converted(raw,quantity='EVALUATED_MINUS_REFERENCE'):
    raw=deepcopy(raw)
    for q in raw['queries']:
        if q['kind'] not in change.ordered.LOCAL_KINDS:continue
        e=q.pop('comparison_expression');first,second=change.POSITIONS[quantity]
        q['comparison_request']={first:e['first'],second:e['second'],'quantity':quantity,'refs':e['refs']}
    return raw

def enable(monkeypatch,quantity='EVALUATED_MINUS_REFERENCE'):
    monkeypatch.setattr(prior,'received',lambda case,raw,short=True:receive(case,converted(raw,quantity),short=short,profile=change.CONTRACT))

@pytest.mark.parametrize('quantity',change.QUANTITIES[:-1])
@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('reverse',[False,True])
def test_each_quantity_preserves_exact_requested_contrast_and_replay(monkeypatch,quantity,kind,reverse):
    enable(monkeypatch,quantity);s,e,o=prior.execution(kind,reverse);raw=deepcopy(s.candidate)
    p=dispatch.inspect_methods(s,'q1',**o)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay'] and s.candidate==raw
    assert r['mathematical_claim']['target']['first']==[o['candidate']['target']['first'][k] for k in ('own','exposure')]
    focus=json.loads(e['request']['user'].rsplit('\n',1)[1])['focus']['reviewed_ordered_target']
    request=raw['queries'][0]['comparison_request'];mapping=change.POSITIONS[quantity]
    for output,role in zip(('first','second'),mapping):assert focus[output]['value']==request[role]['value']
    assert focus['compilation']['quantity']==quantity and not focus['scientific_approval'] and not focus['is_citable_source']
    sh=sheet(s)
    assert all('comparison_expression' not in k and '.comparison_order' not in k for k in sh['fields'])
    assert all(f'queries.q1.comparison_request.{k}' in sh['fields'] for k in change.RULES)

@pytest.mark.parametrize('missing',['reference','evaluated','direction'])
def test_missing_endpoint_or_order_stays_blocked(missing):
    case,_,raw=prior.local_fixture();raw=converted(raw);r=raw['queries'][0]['comparison_request']
    if missing=='direction':r['quantity']='UNSPECIFIED'
    else:r[missing]=dict(state='MISSING',reason='原材料明确尚未决定所需状态',refs=r[missing]['refs'])
    s=receive(case,raw,profile=change.CONTRACT)
    before=deepcopy(s.candidate)
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    assert not dispatch.execute(s,'q1',query_review=None,candidate={},request_sha256='0'*64)['backend_called']
    assert s.candidate==before

@pytest.mark.parametrize('defect',['quantity','missing','extra','legacy','null','unknown_value','no_refs','duplicate_refs','foreign_refs','scope'])
def test_invalid_request_reports_original_field_and_never_repairs(defect):
    case,_,raw=prior.local_fixture();raw=converted(raw);q=raw['queries'][0];r=q['comparison_request']
    if defect=='quantity':r['quantity']='ABSOLUTE_DECREASE'
    elif defect=='missing':r.pop('evaluated')
    elif defect=='extra':r['answer']='success'
    elif defect=='legacy':q['comparison_expression']={}
    elif defect=='null':r['reference']=None
    elif defect=='unknown_value':r['reference']=dict(state='UNKNOWN',value='人为补的状态',refs=[])
    elif defect=='no_refs':r['refs']=[]
    elif defect=='duplicate_refs':r['refs']*=2
    elif defect=='foreign_refs':r['reference']['refs']=['invented']
    else:q['kind']='FIXED_POLICY_VALUE'
    before=deepcopy(raw);rows=diagnose(case,raw,response_contract=change.CONTRACT)
    assert rows and all('/comparison_request' in row['field_path'] or '/comparison_expression' in row['field_path'] for row in rows)
    assert raw==before

def test_quantity_itself_is_reviewed_and_old_approval_invalidates():
    case,_,raw=prior.local_fixture();raw=converted(raw);s=receive(case,raw,profile=change.CONTRACT)
    w=sheet(s);r=record(w);r['decisions']['queries.q1.comparison_request.quantity']['value_state']='REJECTED'
    assert submit(s,r)['state']=='CHECK_BLOCKED'
    good=submit(s,record(w))['query_review'];raw=deepcopy(s.candidate);raw['queries'][0]['comparison_request']['quantity']='REDUCTION'
    newer=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(newer,'q1',query_review=good)['request'] is None

def test_schema_review_and_null_rules_agree():
    case,_,raw=prior.local_fixture();raw=converted(raw)
    system,user,_=make_compact_request(case,a0_response_contract=change.CONTRACT);schema=split_user(user)[2]
    Draft202012Validator.check_schema(schema);assert Draft202012Validator(schema).is_valid(raw)
    assert '禁止null和Schema说明键' not in system and 'value省略或为null、refs为空' in system
    assert '采用有序表达comparison_expression' not in system
    s=receive(case,raw,profile=change.CONTRACT);w=sheet(s)
    for name in change.RULES:assert schema['$defs']['LocalChangeRequest']['properties'][name]['description']==w['fields'][f'queries.q1.comparison_request.{name}']['definition']['wire_description']
    raw['common']['variable_causal_graph']=dict(state='UNKNOWN',value=None,refs=[])
    assert 'report' in intake.inspect(receive(case,raw,profile=change.CONTRACT))

@pytest.mark.parametrize('kind',['point','partial','dag'])
def test_nonlocal_contract_and_proof_unchanged(monkeypatch,kind):
    enable(monkeypatch)
    if kind=='dag':prior.test_dag_retains_original_wire_and_native_replay()
    else:prior.test_complete_policy_contrast_preserves_business_roles_and_replay(kind)

def test_fact_recheck_retains_reviewed_target_and_public_background_rules(monkeypatch):
    from cfm_id.fact_reading_revision import prepare_recheck
    enable(monkeypatch,'REDUCTION');s,e,o=prior.execution('SPILLOVER_EFFECT',True)
    w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    f=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',reviewer='source reviewer',
        evidence='Private original-source audit locates ambiguous background, not a replacement answer.',
        issues=[dict(field_path='/additional_restrictions',kind='OMITTED_OR_MISREAD',source_ids=list(w['source_catalog'])[:1],reason='PRIVATE_REASON_NOT_SENT; original background role requires review.')])
    r=prepare_recheck(s,'q1',**o,feedback=f);assert r['request'] is not None
    assert 'reviewed_ordered_target' in r['request']['user'] and 'PRIVATE_REASON_NOT_SENT' not in r['request']['user']
    assert 'REDUCTION' in r['request']['user'] and change.BACKGROUND in r['request']['system']
    assert any(x['field_path']=='/additional_restrictions' and x['description']==change.BACKGROUND for x in w['public_field_constraints'])
    assert r['reading_revision'] and r['request_sha256']!=e['request_sha256']
    body=json.JSONDecoder().raw_decode(r['request']['user'])[0]
    assert body['output_schema']['properties']['additional_restrictions']['description']==change.BACKGROUND
    assert body['residual_field_contract']['fields']['additional_restrictions']==change.BACKGROUND
    assert not any('reviewed_ordered_target' in v['doc_id'] for v in body['source_catalog'].values())

def test_true_restrictions_and_refusal_are_not_discarded(monkeypatch):
    enable(monkeypatch);s,e,o=prior.execution();raw=o['candidate'];raw['additional_restrictions']=[dict(text='所有潜在结果的均值必须小于某个尚未给出的上界',source_ids=raw['study']['source_ids'])]
    before=deepcopy(raw);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not r['backend_called'] and raw==before
    prior.test_ordered_wire_does_not_bypass_science_information_or_source_review('refused','ADAPTER_NOT_CONNECTED')

def test_a0_recheck_uses_quantity_paths_and_current_rules():
    from cfm_id.intake_reading_revision import prepare_recheck
    from tests_gateway.test_reading_review_guards import feedback
    case,_,raw=prior.local_fixture();s=receive(case,converted(raw),profile=change.CONTRACT)
    w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet'];f=feedback(w)
    f['issues'][0]['field_path']='/queries/0/comparison_request/quantity'
    revised=prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST');req=intake.prepare_request(revised)
    context=json.loads(req['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert any(change.GUIDANCE in row['field_role'] for row in context['field_role_constraints'])
    assert 'PRIVATE_REASON_STAYS_LOCAL' not in req['user_prompt']

def test_multiple_queries_bind_the_selected_raw_request():
    case,data,raw=prior.local_fixture();raw=converted(raw);second=deepcopy(raw['queries'][0])
    second['kind']='SPILLOVER_EFFECT';second['goal']['value']=data['questions']['q2']
    second['comparison_request']['reference']['value']='自己未启用且合作对象过半启用'
    second['comparison_request']['evaluated']['value']='自己未启用且合作对象至多一半启用'
    second['semantics']['neighbor_exposure']['value']='自己未启用，同伴过半与至多一半的比较'
    second['comparison_request']['quantity']='REDUCTION';raw['queries'].append(second)
    s=receive(case,raw,profile=change.CONTRACT);w=sheet(s,'q2')
    r=submit(s,record(w),'q2');e=dispatch.prepare_reader(s,'q2',query_review=r['query_review'])
    assert e['request'] is not None
    f=json.loads(e['request']['user'].rsplit('\n',1)[1])['focus']
    assert f['query_id']=='q2' and f['reviewed_ordered_target']['compilation']['query_index']==1
    assert f['reviewed_ordered_target']['compilation']['quantity']=='REDUCTION'
    assert f['reviewed_ordered_target']['first']['value']==s.candidate['queries'][1]['comparison_request']['reference']['value']
