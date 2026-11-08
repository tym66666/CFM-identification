"""Field explanations travel with explicit rereads, never with answer repairs."""
import json
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm import network_field_contract as fields
from cfm_id_llm.network_fact_protocols import network_fact_protocol
from tests_gateway.test_network_model_scope_contract import setup as before_setup,without_descriptions
from tests_gateway.test_network_statement_reading import to_wire,as_selection
from tests_gateway.test_fact_reading_revision import feedback
from examples.network_bounded_dispatch_reference import reference
from examples.business_dispatch_reference import approve
from examples.network_dispatch_reference import approval_records

def setup(**kw):
    old,e,o=before_setup(**kw)
    s=intake.configure_network_fact_contract(old,fields.CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=as_selection(to_wire(reference(e,**kw),e))
    return s,e,dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])

def test_same_wire_parser_and_original_materials_without_ambiguous_definition_stack():
    s,e,o=setup();old=network_fact_protocol('network-source-selections-information-3');new=network_fact_protocol(fields.CONTRACT)
    a=old.make_request(e['bundle'],binding=e['fact_binding_sha256']);b=new.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    assert without_descriptions(json.loads(a['user']))==without_descriptions(json.loads(b['user']))
    assert old.parse is new.parse and old.model is new.model
    from cfm_id_llm.network_model_scope_contract import INFORMATION_SCOPE
    assert INFORMATION_SCOPE not in b['system'] and b['system'].count(fields.INFORMATION_COMPLETENESS)==1
    assert new.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])==old.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])

@pytest.mark.parametrize('path,expected',[
    ('/study',['/study']),('/study/context',['/study']),
    ('/bounded_model/listed_means_are_complete_information/value',['/bounded_model/listed_means_are_complete_information']),
    ('/assignment',[]),('',[p for p,d in fields.FIELD_RULES])])
def test_recheck_and_reviewer_receive_same_selected_public_definitions_without_private_gold(path,expected):
    s,e,o=setup();raw=deepcopy(o['candidate']);w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(w,path=path))
    assert r['state']=='READY_TO_READ'
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    selected=public.get('public_field_constraints',[])
    assert [v['field_path'] for v in selected]==expected
    assert all(v in w['public_field_constraints'] for v in selected)
    schema=json.loads(e['request']['user'].split('\n\n本次只读取')[0])['output_schema']
    descriptions={'/study':schema['properties']['study']['description'],'/bounded_model/listed_means_are_complete_information':schema['$defs']['BoundedModel']['properties']['listed_means_are_complete_information']['description']}
    assert all(v['description']==descriptions[v['field_path']] for v in selected)
    assert all(p not in r['request']['user']+r['request']['system'] for p in ['PRIVATE_REASON_NOT_SENT','Private reviewer identity','Private evidence:'])
    assert o['candidate']==raw and public['previous_candidate']==raw and not r['backend_called']
    assert not r['reading_revision_receipt']['scientific_approval'] and not r['reading_revision_receipt']['candidate_modified']

def test_old_profile_feedback_has_no_new_keys_or_rules():
    s,e,o=before_setup();w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    assert 'public_field_constraints' not in w
    r=prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/study'))
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert set(public)=={'kind','previous_candidate','issues'}

@pytest.mark.parametrize('value',[False,None,True])
def test_sample_never_becomes_population_even_when_completeness_claim_is_wrong(value,monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Samples must not enter mathematics'))
    s,e,o=setup();c=o['candidate'];c['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    c['bounded_model']['listed_means_are_complete_information']['value']=value;raw=deepcopy(c)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called'] and not r['answers'] and c==raw
    assert r['mathematical_claim'] is None

@pytest.mark.parametrize('bounds,state',[(('1/2','1/2'),'POINT'),(('1/4','3/4'),'PARTIAL')])
def test_partial_table_can_still_be_complete_information_after_independent_science(bounds,state):
    s,e,o=setup(center_bounds=bounds)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==state and r['independent_replay'] and r['mathematical_claim']['sharp']

@pytest.mark.parametrize('problem',['unknown','extra_population','rejected_science','coupling'])
def test_reading_explanations_do_not_release_other_missing_or_refused_conditions(problem,monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Unexpected mathematical call'))
    s,e,o=setup();c=o['candidate']
    if problem=='unknown':c['bounded_model']['listed_means_are_complete_information']['value']=None
    elif problem=='extra_population':
        c['bounded_model']['listed_means_are_complete_information']['value']=False
        c['additional_restrictions']=[dict(text='另外已知总体均值真实区间，不能替换为一个点值。',source_ids=c['information'][0]['source_ids'])]
    elif problem=='rejected_science':c['mean_sufficiency']['status']='NOT_ADOPTED'
    else:c['bounded_model']['no_additional_coupling_constraints']['value']=False
    raw=deepcopy(c);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state'] in ('NEEDS_INPUT','ADAPTER_NOT_CONNECTED') and not r['backend_called'] and c==raw

def test_changing_profile_invalidates_old_review_and_old_request_without_touching_a0():
    old,e,o=before_setup();s=intake.configure_network_fact_contract(old,fields.CONTRACT)
    assert s.candidate==old.candidate and intake.prepare_request(s)==intake.prepare_request(old)
    assert dispatch.prepare_reader(s,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    assert dispatch.execute(s,'q1',query_review=q,candidate=o['candidate'],request_sha256=e['request_sha256'])['state']=='CHECK_BLOCKED'
