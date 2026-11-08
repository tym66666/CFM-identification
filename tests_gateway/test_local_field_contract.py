from copy import deepcopy
import json
import pytest
from cfm_id import business_dispatch as dispatch, business_intake as intake
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm import local_field_contract as contract
from cfm_id_llm.compact_reference_contract import split_user
from tests_gateway import test_scoped_effect_reading as previous
from tests_gateway.test_business_field_review import sheet, record, submit
from examples.network_effect_dispatch_reference import approval_records


def setup(monkeypatch, **kwargs):
    monkeypatch.setattr(previous, 'contract', contract)
    return previous.setup(monkeypatch, **kwargs)


@pytest.mark.parametrize('field', ['analysis_unit', 'available_information'])
@pytest.mark.parametrize('suffix', ['', '/value', '/refs/0'])
def test_initial_review_and_recheck_have_one_common_field_definition(monkeypatch, field, suffix):
    s,e,o=setup(monkeypatch)
    schema=split_user(intake.prepare_request(s)['user_prompt'])[2]
    expected=schema['$defs']['CompactCommon']['properties'][field]['description']
    assert sheet(s)['fields']['common.'+field]['definition']['wire_description']==expected
    path='/common/'+field+suffix
    assert contract.recheck_field_roles([path,path])==[dict(field_path=path,field_role=expected)]


@pytest.mark.parametrize('network_contract',[None,'network-source-selections-dependencies-1','network-source-selections-alignment-1'])
@pytest.mark.parametrize('endpoint',['reference','evaluated'])
def test_actual_fact_recheck_uses_selected_profile_field_owner(monkeypatch,network_contract,endpoint):
    s,e,o=setup(monkeypatch,network_contract=network_contract)
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    expected=body['output_schema']['$defs']['LocalArm']['properties']['source_ids']['description']
    assert expected==contract.ARM_SELECTION
    w=prepare_recheck(s,'q1',**o)['feedback_worksheet'];path='/target/'+endpoint+'/source_ids/0'
    f=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority=w['expected_authority'],
        reviewer='Independent fixture reviewer',evidence='Locate original endpoint evidence, without giving substitute values.',
        issues=[dict(field_path=path,kind='OMITTED_OR_MISREAD',source_ids=list(w['source_catalog'])[:1],reason='PRIVATE_REPLACEMENT_NOT_SENT')])
    revised=prepare_recheck(s,'q1',**o,feedback=f)
    public=json.loads(revised['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    exact=[r for r in public['public_field_constraints'] if r['field_path']==path]
    assert exact==[dict(field_path=path,description=expected)]
    assert 'PRIVATE_REPLACEMENT_NOT_SENT' not in revised['request']['user']
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']


@pytest.mark.parametrize('field,axis',[('analysis_unit','field_role'),('available_information','value_state'),('available_information','source_coverage')])
def test_common_field_rejection_prevents_fact_request(monkeypatch,field,axis):
    s,e,o=setup(monkeypatch);r=record(sheet(s));r['decisions']['common.'+field][axis]='REJECTED'
    rejected=submit(s,r)
    assert rejected['state']=='CHECK_BLOCKED'
    assert dispatch.prepare_reader(s,'q1',query_review=rejected['query_review'])['request'] is None


@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('quantity',['INCREASE','REDUCTION'])
def test_native_point_replay_and_raw_candidate_preserved(monkeypatch,kind,quantity):
    s,e,o=setup(monkeypatch,kind=kind,quantity=quantity,count=True);before=deepcopy(o['candidate'])
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED' and not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay'] and before==o['candidate']


@pytest.mark.parametrize('endpoint',['reference','evaluated'])
def test_source_entailment_rejection_blocks_correct_endpoint_values(monkeypatch,endpoint):
    s,e,o=setup(monkeypatch)
    o['candidate']['target'][endpoint]['source_ids']=list(o['candidate']['study']['source_ids'])
    before=deepcopy(o['candidate']);p=dispatch.inspect_methods(s,'q1',**o)
    reviews=approval_records(p)
    for pair in reviews['native_reviews'].values():pair['reading_review'].decisions['source_entailment']='REJECTED'
    result=dispatch.execute(s,'q1',**o,**reviews)
    assert not result['backend_called'] and not result['independent_replay'] and o['candidate']==before


@pytest.mark.parametrize('known_scope',[False,True])
def test_sample_only_still_requires_population_information(monkeypatch,known_scope):
    monkeypatch.setattr(previous,'contract',contract)
    previous.test_finite_records_never_become_population_information(monkeypatch,known_scope)


@pytest.mark.parametrize('bad',['scientific_pending','scientific_refused','extra_restriction'])
def test_semantic_instructions_do_not_grant_scientific_permission(monkeypatch,bad):
    monkeypatch.setattr(previous,'contract',contract)
    previous.test_valid_wire_still_requires_source_and_scientific_review(monkeypatch,bad)


@pytest.mark.parametrize('kind',['point','partial','dag'])
def test_nonlocal_routes_remain_compatible(monkeypatch,kind):
    monkeypatch.setattr(previous,'contract',contract)
    previous.test_other_routes_keep_original_contract(monkeypatch,kind)
