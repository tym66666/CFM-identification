from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm import local_population_contract as contract, scoped_role_contract as older
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.compact_response_contract import (LOCAL_PROFILE_MODULES, LOCAL_COMPARISON_PROFILES,
    REVIEWED_TARGET_PROFILES, ROLE_REQUEST_PROFILES, PROFILES, evidence_contract)
from cfm_id_llm.business_field_contract import fields
from tests_gateway import test_scoped_effect_reading as previous
from tests_gateway.test_business_field_review import sheet, record, submit
from examples.network_effect_dispatch_reference import approval_records


def setup(monkeypatch, **kwargs):
    monkeypatch.setattr(previous, 'contract', contract)
    return previous.setup(monkeypatch, **kwargs)


@pytest.mark.parametrize('kind', ['DIRECT_EFFECT', 'SPILLOVER_EFFECT'])
@pytest.mark.parametrize('path,section,name,model', [
    ('/common/analysis_unit','common','analysis_unit','CompactCommon'),
    ('/queries/0/semantics/target_population','semantics','target_population','OrderedLocalSemantics')])
@pytest.mark.parametrize('suffix', ['', '/value', '/refs/0'])
def test_first_recheck_and_review_share_exact_field_owner(monkeypatch,kind,path,section,name,model,suffix):
    s,e,o=setup(monkeypatch,kind=kind)
    request=intake.prepare_request(s);schema=split_user(request['user_prompt'])[2]
    expected=schema['$defs'][model]['properties'][name]['description']
    key=f'common.{name}' if section=='common' else f'queries.q1.semantics.{name}'
    assert sheet(s)['fields'][key]['definition']['wire_description']==expected
    rows=contract.recheck_field_roles([path+suffix,path+suffix])
    assert [r for r in rows if r['field_path']==path+suffix]==[dict(field_path=path+suffix,field_role=expected)]
    assert expected != older.recheck_field_roles([path+suffix])[0]['field_role']


@pytest.mark.parametrize('profile', LOCAL_COMPARISON_PROFILES)
def test_closed_profile_registration_and_fact_pairing(profile):
    adapter=evidence_contract(profile)
    assert profile in PROFILES and adapter.CONTRACT==profile
    assert adapter.__name__.split('.')[-1]==LOCAL_PROFILE_MODULES[profile]
    assert callable(adapter.describe) and callable(adapter.review_definition)
    if profile in ROLE_REQUEST_PROFILES:
        assert profile in REVIEWED_TARGET_PROFILES and hasattr(adapter,'fact_focus')
    if hasattr(adapter,'FACT_VERSION'):
        assert callable(adapter.clarify_fact_request)


@pytest.mark.parametrize('kind', ['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('quantity',['REDUCTION','INCREASE'])
def test_native_point_and_independent_replay_unchanged(monkeypatch,kind,quantity):
    s,e,o=setup(monkeypatch,kind=kind,quantity=quantity,count=True)
    before=deepcopy(o['candidate']);p=dispatch.inspect_methods(s,'q1',**o)
    assert e['effect_fact_contract']==older.FACT_VERSION and p['state']=='REVIEW_REQUIRED'
    assert e['reviewed_local_request']['contract']==contract.CONTRACT
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay'] and o['candidate']==before


@pytest.mark.parametrize('status,expected',[(None,'NEEDS_INPUT'),(False,'ADAPTER_NOT_CONNECTED')])
def test_known_roster_never_approves_unknown_or_post_assignment_selection(monkeypatch,status,expected):
    s,e,o=setup(monkeypatch);o['candidate']['target']['population_fixed_before_assignment']['value']=status
    before=deepcopy(o['candidate']);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==expected and not r['backend_called'] and o['candidate']==before


@pytest.mark.parametrize('axis',['field_role','value_state','source_coverage'])
def test_population_rejection_remains_blocking(monkeypatch,axis):
    s,e,o=setup(monkeypatch);r=record(sheet(s));r['decisions']['queries.q1.semantics.target_population'][axis]='REJECTED'
    rejected=submit(s,r);assert rejected['state']=='CHECK_BLOCKED'
    assert dispatch.prepare_reader(s,'q1',query_review=rejected['query_review'])['request'] is None


def test_changed_population_qualifier_cannot_reuse_review(monkeypatch):
    s,e,o=setup(monkeypatch);raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics']['target_population']['value']+='；改为分配后按实际表现选择。'
    changed=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(changed,'q1',query_review=e['query_review'])['request'] is None


def test_actual_recheck_uses_specific_role_not_private_feedback(monkeypatch):
    from cfm_id.intake_reading_revision import prepare_recheck
    s,e,o=setup(monkeypatch);w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    path='/queries/0/semantics/target_population'
    feedback=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority=w['expected_authority'],
        reviewer='Synthetic source reviewer',evidence='Locate original population scope, without substitute answer.',
        issues=[dict(field_path=path,kind='OMITTED_OR_MISREAD',source_ids=list(w['source_catalog'])[:1],reason='PRIVATE_REPLACEMENT_NOT_SENT')])
    revised=prepare_recheck(s,feedback=feedback,authority='SYNTHETIC_TEST');r=intake.prepare_request(revised)
    assert 'PRIVATE_REPLACEMENT_NOT_SENT' not in r['user_prompt']
    public=json.loads(r['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    expected=contract.review_definition(contract.RULES[('semantics','target_population')])['wire_description']
    assert next(x for x in public['field_role_constraints'] if x['field_path']==path)['field_role']==expected


@pytest.mark.parametrize('kind',['point','partial','dag'])
def test_other_native_routes_still_available(monkeypatch,kind):
    monkeypatch.setattr(previous,'contract',contract)
    previous.test_other_routes_keep_original_contract(monkeypatch,kind)
