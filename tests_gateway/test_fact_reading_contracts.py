"""R3 lifecycle pairing, real guards/replay, and compatibility boundaries."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from pydantic import BaseModel
from cfm_id import business_dispatch as d,business_case,fact_reading_revision as revision,fact_source_review as source
from cfm_id import network_observational_policy_dispatch as native
from cfm_id_llm import fact_reading_contracts as registry,network_observational_policy_reading as reading
from cfm_id_llm.fact_wire_models import model_for
from cfm_id_llm.wire_type_diagnostics import diagnose
from cfm_id_llm import query_conditioning_contract as conditioning
from examples.network_observational_policy_reference import setup as legacy,approval_records,approve,fact_reference,material
from tests_gateway.test_query_conditioning_contract import setup as conditioned
from tests_gateway.test_organized_reading_contract import setup as organized
from tests_gateway.test_fact_source_review import record
from tests_gateway.test_fact_reading_revision import feedback,accept_changes


def test_contract_matches_actual_business_reader_and_source_schema():
    from cfm_id.capability_registry import business_binding
    contract=registry.registered_contract(native.FAMILY)
    s,e,o=conditioned();body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    assert contract.reader_id==business_binding(native.FAMILY).reader_id
    assert contract.make_request is reading.make_request and contract.parse is reading.parse
    assert contract.model is model_for(e) is reading.ObservationalPolicyReading
    refs=contract.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    assert refs==revision._references(e)
    assert body['reference_context']==refs['context']
    assert body['source_catalog']=={k:dict(doc_id=r['doc_id'],text=r['text']) for k,r in refs['aliases'].items()}
    assert body['output_schema']['properties']['version']['const']==contract.wire_version
    assert e[contract.version_field]==contract.wire_version
    assert contract.target_context.description in body['output_schema']['properties']['conditioning']['description']
    assert registry.contract_for_entry(dict(e,observational_fact_contract=reading.VERSION))==contract


@pytest.mark.parametrize('change',['request','parser','references','model','documents','version','context_request','context_rules','context_decision'])
def test_incomplete_registration_is_a_wiring_error(change):
    c=registry.registered_contract(native.FAMILY)
    field={'request':'make_request','parser':'parse','references':'reference_catalog','documents':'documents'}
    with pytest.raises(registry.ReadingContractError):
        if change in field:replace(c,**{field[change]:None})
        elif change=='model':replace(c,model=BaseModel)
        elif change=='version':replace(c,wire_version='unmatched-version')
        else:
            key={'context_request':'clarify_request','context_rules':'field_constraints','context_decision':'decision'}[change]
            replace(c,target_context=replace(c.target_context,**{key:None}))


def test_duplicate_registration_never_silently_selects_first(monkeypatch):
    c=registry.registered_contract(native.FAMILY)
    monkeypatch.setattr(registry,'registrations',lambda:(c,c))
    with pytest.raises(registry.ReadingContractError):registry.registered_contract(native.FAMILY)


@pytest.mark.parametrize('patch',[{'observational_fact_contract':'foreign-version'},
    {'observational_fact_contract':None},{'reference_format':'source_hash'},{'reader_id':'NETWORK_FIXED_POLICY_FACTS'}])
def test_cross_contract_metadata_blocks_before_native_execution(patch):
    s,e,o=conditioned();bad=dict(e,**patch)
    p=native.inspect_methods(bad,o['candidate'])
    assert p['state']=='CHECK_BLOCKED' and not p['backend_called'] and p['mathematical_claim'] is None
    assert not p['methods']


def test_legacy_entry_without_version_and_direct_reader_api_remain_compatible():
    s,e,o=legacy();before=deepcopy(e);minimal=dict(e);minimal.pop('observational_fact_contract')
    c=registry.contract_for_entry(minimal)
    assert c.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])==reading.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])
    assert native.inspect_methods(minimal,o['candidate'])['state']=='REVIEW_REQUIRED'
    assert e==before
    assert model_for({'reference_format':'short_refs'}) is None


def test_registered_parser_is_used_by_business_inspection(monkeypatch):
    s,e,o=conditioned();c=registry.registered_contract(native.FAMILY)
    calls=[]
    def rejected(*args,**kwargs):calls.append(True);raise ValueError('synthetic parser rejection')
    monkeypatch.setattr(registry,'registrations',lambda:(replace(c,parse=rejected),))
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert calls and r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_initial_recheck_source_and_format_use_registered_components(monkeypatch):
    c=registry.registered_contract(native.FAMILY);calls=[]
    def watch(name,fn):
        def wrapper(*args,**kwargs):calls.append(name);return fn(*args,**kwargs)
        return wrapper
    tracked=replace(c,make_request=watch('request',c.make_request),reference_catalog=watch('references',c.reference_catalog),
        target_context=replace(c.target_context,clarify_request=watch('condition_request',c.target_context.clarify_request),
                               field_constraints=watch('condition_rules',c.target_context.field_constraints)))
    monkeypatch.setattr(registry,'registrations',lambda:(tracked,))
    s,e,o=conditioned();bad=deepcopy(o['candidate']);bad['conditioning']['kind']='INVALID_CONDITION'
    assert any(x['field_path']=='/conditioning/kind' for x in diagnose(e,bad))
    w=revision.prepare_recheck(s,'q1',**dict(o,candidate=bad))['feedback_worksheet']
    r=revision.prepare_recheck(s,'q1',**dict(o,candidate=bad),feedback=feedback(w,path='/conditioning/kind',kind='WIRE_FORMAT_ERROR',doc='conditioning'))
    assert r['state']=='READY_TO_READ' and r['reviewed_target_context']==e['reviewed_target_context']
    assert {'request','references','condition_request','condition_rules'}<=set(calls)
    assert calls.count('request')>=2 and calls.count('condition_request')>=2
    body=json.JSONDecoder().raw_decode(r['request']['user'])[0]
    assert conditioning.FACT_DESCRIPTION==body['output_schema']['properties']['conditioning']['description']
    assert 'INVALID_CONDITION' not in json.dumps(diagnose(e,bad))  # no raw values in type feedback
    source.prepare(e,o['candidate'])


@pytest.mark.parametrize('setup',[legacy,conditioned,organized],ids=['legacy','conditioning','organized'])
def test_source_review_and_native_replay_survive_whole_case(setup):
    s,e,o=setup();original=deepcopy(o['candidate']);o['source_review']=record(source.prepare(e,original))
    plan=d.inspect_methods(s,'q1',**o)
    pending=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    if e.get('reviewed_target_context'):
        c=registry.contract_for_entry(e)
        assert c.target_context.decision in plan['methods'][0]['reading_worksheet']['decisions']
        assert plan['target_conditioning_review']==c.target_context.review_item(e['reviewed_target_context'],plan['facts']['conditioning'])
    a=approval_records(plan);r=d.execute(s,'q1',**o,**a)
    assert r['state']=='POINT' and r['independent_replay'] and original==o['candidate']
    whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert whole['results'][0]['result']==r


@pytest.mark.parametrize('kwargs,expected',[({'exchangeability':None},'NEEDS_INPUT'),({'exchangeability':False},'ADAPTER_NOT_CONNECTED'),
    ({'sample_only':True},'NEEDS_INPUT'),({'zero_support':True},'UNSUPPORTED')])
def test_registration_never_grants_missing_science_or_population_information(kwargs,expected):
    s,e,o=conditioned(**kwargs);o['source_review']=record(source.prepare(e,o['candidate']))
    p=d.inspect_methods(s,'q1',**o);a=approval_records(p) if p.get('methods') else dict(research_protocol_selected=True)
    r=d.execute(s,'q1',**o,**a)
    assert r['state']==expected and not r['independent_replay'] and r['mathematical_claim'] is None
    if expected!='UNSUPPORTED':assert not r['backend_called']


@pytest.mark.parametrize('decision,expected',[('REJECTED','CHECK_BLOCKED'),('PENDING','REVIEW_REQUIRED'),('OMITTED','CHECK_BLOCKED')])
def test_registered_target_context_still_requires_independent_review(decision,expected):
    s,e,o=conditioned();p=d.inspect_methods(s,'q1',**o);a=approval_records(p)
    key=registry.contract_for_entry(e).target_context.decision
    decisions=a['native_reviews'][native.METHOD]['reading_review'].decisions
    if decision=='OMITTED':decisions.pop(key)
    else:decisions[key]=decision
    r=d.execute(s,'q1',**o,**a)
    assert r['state']==expected and not r['backend_called']


def test_recheck_rejects_old_candidate_and_approvals_and_requires_change_review():
    s,e,o=conditioned();old=d.inspect_methods(s,'q1',**o);old_reviews=approval_records(old)
    bad=deepcopy(o['candidate']);bad['conditioning']['kind']='UNKNOWN'
    args=dict(o,candidate=bad);w=revision.prepare_recheck(s,'q1',**args)['feedback_worksheet']
    revised=revision.prepare_recheck(s,'q1',**args,feedback=feedback(w,path='/conditioning',doc='conditioning'))
    assert revised['state']=='READY_TO_READ' and revised['request_sha256']!=e['request_sha256']
    _,data=material();fresh=fact_reference(revised,data)
    new=dict(query_review=o['query_review'],candidate=fresh,request_sha256=revised['request_sha256'],reading_revision=revised['reading_revision'])
    assert d.execute(s,'q1',**dict(new,candidate=o['candidate']),research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    plan=d.inspect_methods(s,'q1',**new);assert plan['state']=='REVIEW_REQUIRED'
    new['change_review']=accept_changes(plan['reading_change_worksheet'])
    assert d.execute(s,'q1',**new,**old_reviews)['state']=='CHECK_BLOCKED'
    assert not d.execute(s,'q1',**new,research_protocol_selected=True)['backend_called']
    result=d.execute(s,'q1',**new,**approval_records(d.inspect_methods(s,'q1',**new)))
    assert result['state']=='POINT' and result['independent_replay']
    assert revised['reading_revision']['steps'][0]['candidate']==bad
