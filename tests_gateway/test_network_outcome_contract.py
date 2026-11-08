"""Outcome explanations preserve raw scales, independent blockers and reviews."""
from copy import deepcopy
from fractions import Fraction
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm import network_outcome_contract as rules
from cfm_id_llm.network_fact_protocols import network_fact_protocol
from tests_gateway.test_network_field_contract import setup as prior_setup
from tests_gateway.test_network_model_scope_contract import without_descriptions
from tests_gateway.test_network_statement_reading import as_selection,to_wire
from tests_gateway.test_fact_reading_revision import feedback
from examples.network_bounded_dispatch_reference import reference
from examples.business_dispatch_reference import approve
from examples.network_dispatch_reference import approval_records


def setup(**kw):
    prior,_,_=prior_setup(**kw)
    s=intake.configure_network_fact_contract(prior,rules.CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=as_selection(to_wire(reference(e,**kw),e))
    return s,e,dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])


def test_opt_in_descriptions_keep_wire_materials_parser_and_a0_unchanged():
    s,e,o=setup()
    old=network_fact_protocol(rules.previous.CONTRACT);new=network_fact_protocol(rules.CONTRACT)
    a=old.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    b=new.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    assert a['system']==b['system']
    assert without_descriptions(json.loads(a['user']))==without_descriptions(json.loads(b['user']))
    assert old.model is new.model and old.parse is new.parse
    raw=deepcopy(o['candidate'])
    assert old.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])==new.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
    assert raw==o['candidate']
    prior=intake.configure_network_fact_contract(s,rules.previous.CONTRACT)
    assert intake.prepare_request(prior)==intake.prepare_request(s)


@pytest.mark.parametrize('path',[
    '/bounded_model/outcome_definition','/bounded_model/outcome_unit',
    '/bounded_model/outcome_period','/bounded_model/no_additional_coupling_constraints/value',
    '/bounded_model','/assignment'])
def test_initial_review_and_recheck_share_selected_public_rules_without_gold(path):
    s,e,o=setup();w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(w,path=path));assert r['state']=='READY_TO_READ'
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    selected=public.get('public_field_constraints',[])
    assert selected==rules.field_constraints([path])
    schema=json.loads(e['request']['user'].split('\n\n本次只读取')[0])['output_schema']
    for row in selected:
        assert row in w['public_field_constraints']
        name=row['field_path'].split('/')[-1]
        assert row['description']==schema['$defs']['BoundedModel']['properties'][name]['description']
    assert all(s not in r['request']['user']+r['request']['system'] for s in ['PRIVATE_REASON_NOT_SENT','Private reviewer identity','Private evidence:'])
    assert public['previous_candidate']==o['candidate'] and not r['reading_revision_receipt']['candidate_modified']
    assert not r['backend_called'] and not r['reading_revision_receipt']['scientific_approval']


def test_legacy_profile_does_not_receive_new_outcome_or_coupling_explanations():
    s,e,o=prior_setup();w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/bounded_model/outcome_unit'))
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert 'public_field_constraints' not in public
    assert rules.OUTCOME_UNIT not in r['request']['user']
    assert all(v['field_path']!='/bounded_model/outcome_unit' for v in w['public_field_constraints'])


@pytest.mark.parametrize('field',['outcome_definition','outcome_unit','outcome_period'])
def test_known_binary_kind_or_bounds_never_fill_missing_outcome_metadata(field,monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Missing metadata must block'))
    s,e,o=setup();o['candidate']['bounded_model'][field]=None;raw=deepcopy(o['candidate'])
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['reason_code']=='BOUNDED_MODEL_DECLARATIONS_INCOMPLETE'
    assert not r['backend_called'] and r['mathematical_claim'] is None and o['candidate']==raw


@pytest.mark.parametrize('complete,coupling',[(True,None),(None,True),(True,False),(False,True),(None,None)])
def test_declarations_keep_independent_values_and_never_fill_each_other(complete,coupling,monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Incomplete model must block'))
    s,e,o=setup();b=o['candidate']['bounded_model']
    b['listed_means_are_complete_information']['value']=complete
    b['no_additional_coupling_constraints']['value']=coupling
    raw=deepcopy(o['candidate']);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not r['backend_called'] and r['mathematical_claim'] is None and o['candidate']==raw
    assert r['state']==('ADAPTER_NOT_CONNECTED' if False in (complete,coupling) else 'NEEDS_INPUT')


@pytest.mark.parametrize('kind,unit,scale,interval',[
    ('BINARY','无量纲0/1达标指标',1,['13/28','15/28']),
    ('CONTINUOUS','分钟',100,['325/7','375/7']),
    ('CONTINUOUS','万元',1,['13/28','15/28'])])
def test_reviewed_existing_model_preserves_declared_scale_and_replays(kind,unit,scale,interval):
    s,e,o=setup(center_bounds=('1/4','3/4'));c=o['candidate'];c['study']['outcome_kind']=kind
    c['bounded_model']['outcome_unit']=unit
    for info in c['information']:
        for cell in info['signature_cells']:cell['value']=str(Fraction(cell['value'])*scale)
    for row in c['bounded_model']['bounds']:
        for name in ('lower','upper'):row[name]=str(Fraction(row[name])*scale)
    raw=deepcopy(c)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='PARTIAL' and r['independent_replay'] and r['mathematical_claim']['sharp']
    assert r['mathematical_claim']['interval']==interval and c==raw
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


def test_changed_description_profile_invalidates_previous_downstream_approval():
    old,e,o=prior_setup();s=intake.configure_network_fact_contract(old,rules.CONTRACT)
    assert s.candidate==old.candidate and intake.prepare_request(s)==intake.prepare_request(old)
    assert dispatch.prepare_reader(s,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    assert dispatch.execute(s,'q1',query_review=q,candidate=o['candidate'],request_sha256=e['request_sha256'])['state']=='CHECK_BLOCKED'
