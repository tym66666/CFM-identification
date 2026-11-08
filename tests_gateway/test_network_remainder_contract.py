"""Remainder guidance never removes actual constraints or releases a review."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm import network_remainder_contract as rules
from cfm_id_llm.network_fact_protocols import network_fact_protocol
from tests_gateway.test_network_outcome_contract import setup as previous_setup
from tests_gateway.test_network_model_scope_contract import without_descriptions
from tests_gateway.test_network_statement_reading import as_selection, to_wire
from tests_gateway.test_fact_reading_revision import feedback, accept_changes
from examples.business_dispatch_reference import approve
from examples.network_bounded_dispatch_reference import reference
from examples.network_dispatch_reference import approval_records


def setup(**kw):
    old,_,_=previous_setup(**kw)
    s=intake.configure_network_fact_contract(old,rules.CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=as_selection(to_wire(reference(e,**kw),e))
    return s,e,dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])


def test_request_changes_only_public_meanings_not_types_sources_parser_or_a0():
    s,e,o=setup()
    old=network_fact_protocol(rules.previous.CONTRACT);new=network_fact_protocol(rules.CONTRACT)
    a=old.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    b=new.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    assert without_descriptions(json.loads(a['user']))==without_descriptions(json.loads(b['user']))
    assert old.model is new.model and old.parse is new.parse
    raw=deepcopy(o['candidate'])
    assert old.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])==new.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
    assert raw==o['candidate']
    assert intake.prepare_request(intake.configure_network_fact_contract(s,rules.previous.CONTRACT))==intake.prepare_request(s)


@pytest.mark.parametrize('path',['/additional_restrictions','/additional_restrictions/0','/unresolved',''])
def test_located_recheck_uses_initial_public_definitions_without_private_answer(path):
    s,e,o=setup();raw=o['candidate']
    raw['additional_restrictions']=[dict(text='重复的均值界限说明，或可能还含未表达的关系。',source_ids=raw['bounded_model']['source_ids'])]
    w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(w,path=path,kind='POSSIBLE_DUPLICATION'))
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['public_field_constraints']==rules.field_constraints([path])
    assert public['previous_candidate']==raw and r['reading_revision']['steps'][0]['candidate']==raw
    assert not r['reading_revision_receipt']['candidate_modified'] and not r['reading_revision_receipt']['scientific_approval']
    schema=json.loads(e['request']['user'].split('\n\n本次只读取')[0])['output_schema']
    for name in ('additional_restrictions','unresolved'):
        assert dict(field_path='/'+name,description=schema['properties'][name]['description']) in w['public_field_constraints']
    assert all(t not in r['request']['user']+r['request']['system'] for t in ('PRIVATE_REASON_NOT_SENT','Private reviewer identity','Private evidence:'))


@pytest.mark.parametrize('text',[
    '全部均值都在已经记录的逐对象范围内；这是重复的说明。',
    '固定其他对象的启用状态，启用本对象不会降低其均值；除此之外无其他限制。',
    '已有界限仍成立，并且两个对象在所有安排下的均值必须相等。',
    '除了已有点值，还掌握另一总体均值在1/4到3/4内；这是总体信息，不是科学界限。',
])
def test_no_automatic_deduplication_or_release_of_any_remainder(text,monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Remainder must block'))
    s,e,o=setup();c=o['candidate'];c['additional_restrictions']=[dict(text=text,source_ids=c['bounded_model']['source_ids'])]
    before=deepcopy(c);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called'] and r['mathematical_claim'] is None
    assert c==before and r['facts']['additional_restrictions'][0]['text']==text


def test_unknown_unit_is_not_filled_from_bounds_or_removing_duplicate_notes(monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Unit is still missing'))
    s,e,o=setup();c=o['candidate'];c['study']['outcome_kind']='CONTINUOUS';c['bounded_model']['outcome_unit']=None
    before=deepcopy(c);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called'] and c==before


@pytest.mark.parametrize('coupling',[False,None])
def test_empty_remainder_does_not_overrule_independent_model_declaration(coupling,monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Declaration must block'))
    s,e,o=setup();o['candidate']['bounded_model']['no_additional_coupling_constraints']['value']=coupling
    before=deepcopy(o['candidate']);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not r['backend_called'] and r['mathematical_claim'] is None and o['candidate']==before


def test_recheck_omitting_a_real_relation_requires_full_change_review():
    s,e,o=setup();c=o['candidate'];c['additional_restrictions']=[dict(text='固定其他对象的状态，本对象启用后的均值不低于未启用。',source_ids=c['bounded_model']['source_ids'])]
    before=deepcopy(c);w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    entry=prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/additional_restrictions',kind='POSSIBLE_DUPLICATION'))
    # Hand-authored adversarial fixture; no actual model reply is repaired.
    fresh=as_selection(to_wire(reference(entry),entry))
    args=dict(query_review=o['query_review'],candidate=fresh,request_sha256=entry['request_sha256'],reading_revision=entry['reading_revision'])
    p=dispatch.inspect_methods(s,'q1',**args)
    assert p.get('reading_change_worksheet') and not p.get('plan_worksheet')
    r=dispatch.execute(s,'q1',**args,research_protocol_selected=True)
    assert not r['backend_called'] and r['mathematical_claim'] is None
    review=accept_changes(p['reading_change_worksheet'])
    for d in review['decisions'].values():d['disposition']='REJECTED'
    rejected=dispatch.execute(s,'q1',**args,change_review=review,research_protocol_selected=True)
    assert not rejected['backend_called'] and rejected['mathematical_claim'] is None and c==before


@pytest.mark.parametrize('bounds,state',[(('1/2','1/2'),'POINT'),(('1/4','3/4'),'PARTIAL')])
def test_empty_remainder_still_requires_science_and_replays_original_solver(bounds,state):
    s,e,o=setup(center_bounds=bounds);raw=deepcopy(o['candidate'])
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==state and r['independent_replay'] and r['mathematical_claim']['sharp']
    assert o['candidate']==raw and not r['production_admission'] and not r['estimation_handoff_allowed']


def test_new_explanation_invalidates_stale_review_but_keeps_old_requests():
    old,e,o=previous_setup();s=intake.configure_network_fact_contract(old,rules.CONTRACT)
    assert dispatch.prepare_reader(s,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    assert dispatch.execute(s,'q1',query_review=q,candidate=o['candidate'],request_sha256=e['request_sha256'])['state']=='CHECK_BLOCKED'
    w=prepare_recheck(old,'q1',**o)['feedback_worksheet']
    assert all(r['field_path'] not in ('/additional_restrictions','/unresolved') for r in w['public_field_constraints'])
