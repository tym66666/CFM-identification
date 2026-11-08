"""Scope instructions preserve values, citations, gaps and scientific gates."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.compact_unified_contract import recheck_field_roles
from cfm_id_llm.material_scope_contract import CONTRACT
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import wire, receive


@pytest.mark.parametrize('state', ['UNKNOWN','STATED','MISSING'])
def test_scope_guidance_preserves_population_claim_and_no_backend_permission(state):
    b, raw=fixture();raw=wire(raw)
    refs=raw['queries'][0]['goal']['refs']
    raw['common']['available_information']=('UNKNOWN' if state=='UNKNOWN' else
        dict(state='STATED',value='已知总体均值',refs=refs) if state=='STATED' else
        dict(state='MISSING',reason='未提供总体均值',refs=refs))
    s=receive(b,raw,profile=CONTRACT);before=deepcopy(s.candidate)
    report=intake.inspect(s)
    assert 'report' in report and not report['core_called']
    assert s.candidate==before
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    old=intake.inspect(receive(b,raw,profile='inline-unified-contract-7'))
    assert report['report']['draft']==old['report']['draft']


@pytest.mark.parametrize('own_state',['UNKNOWN','本店使用','本店不使用'])
def test_peer_state_is_never_inserted_or_erased(own_state):
    b,raw=fixture();raw=wire(raw,'UNSPECIFIED');q=raw['queries'][0];q['kind']='SPILLOVER_EFFECT'
    q['semantics']['policy_assignment']='NOT_APPLICABLE'
    q['semantics']['intervention']=('UNKNOWN' if own_state=='UNKNOWN' else
        dict(state='STATED',value=own_state+'；同伴采用方案甲',refs=q['goal']['refs']))
    s=receive(b,raw,profile=CONTRACT);before=deepcopy(s.candidate);r=intake.inspect(s)
    assert s.candidate==before and not r['core_called']
    actual=s.candidate['queries'][0]['semantics']['intervention']
    assert actual=='UNKNOWN' if own_state=='UNKNOWN' else actual['value']==own_state+'；同伴采用方案甲'
    assert dispatch.prepare_reader(s,'q1')['request'] is None


def test_shared_definitions_change_instructions_only():
    b,_=fixture()
    requests=[make_compact_request(b,a0_response_contract=p) for p in ('inline-unified-contract-7',CONTRACT)]
    schemas=[split_user(r[1])[2] for r in requests]
    def structure(x):
        if isinstance(x,dict):return {k:structure(v) for k,v in x.items() if k!='description'}
        if isinstance(x,list):return [structure(v) for v in x]
        return x
    assert structure(schemas[0])==structure(schemas[1])
    assert '这只是问题方向的类别' in requests[1][0]
    assert '不默认不使用' in requests[1][0]
    for section,model,name in [('common','CompactCommon','available_information'),('common','CompactCommon','sample_data_description'),('semantics','CompactSemantics','intervention')]:
        path='/common/'+name if section=='common' else '/queries/0/semantics/'+name
        row=recheck_field_roles([path],contract=CONTRACT)[0]
        assert row['field_role']==schemas[1]['$defs'][model]['properties'][name]['description']


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_existing_mathematical_replay_is_unchanged(kind,expected):
    from tests_gateway.test_compact_evidence_slots import contrast_raw
    from tests_gateway.test_business_field_review import sheet,record,submit
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information')
    s=receive(b,raw,profile=CONTRACT)
    q=submit(s,record(sheet(s)))['query_review'];entry=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=fact_reference(entry,data),request_sha256=entry['request_sha256'])
    plan=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**opts,**approval_records(plan))
    assert result['state']==expected and result['independent_replay']
