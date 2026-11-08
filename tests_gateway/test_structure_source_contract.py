"""Structure/source guidance cannot invent, erase, or approve causal facts."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.compact_unified_contract import recheck_field_roles
from cfm_id_llm.material_scope_contract import STRUCTURE_SOURCE_CONTRACT as CONTRACT
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import wire, receive


def test_instruction_roles_and_recheck_share_schema_without_type_changes():
    b,_=fixture()
    old,new=[make_compact_request(b,a0_response_contract=p) for p in ('inline-unified-contract-8',CONTRACT)]
    def structure(x):
        if isinstance(x,dict):return {k:structure(v) for k,v in x.items() if k!='description'}
        if isinstance(x,list):return [structure(v) for v in x]
        return x
    assert structure(split_user(old[1])[2])==structure(split_user(new[1])[2])
    assert '每条refs须支持整个value' not in new[0]
    assert '本字段所选refs的原文合起来须支持整个value' in new[0]
    assert '不要把研究动机改写成已声明的因果图' in new[0]
    for field in ('unit_network','variable_causal_graph','exposure_mapping'):
        role=recheck_field_roles(['/common/'+field],contract=CONTRACT)[0]['field_role']
        assert role==split_user(new[1])[2]['$defs']['CompactCommon']['properties'][field]['description']
    assert '不要求出现DAG一词' in recheck_field_roles(['/common/variable_causal_graph'],contract=CONTRACT)[0]['field_role']


@pytest.mark.parametrize('field,value',[
    ('variable_causal_graph','UNKNOWN'),
    ('variable_causal_graph','管理经验影响是否采用工具，也影响经营结果；采用工具影响经营结果。'),
    ('variable_causal_graph','合作门店互相影响。'),  # Deliberately wrong role: no silent repair.
    ('exposure_mapping','UNKNOWN'),
    ('exposure_mapping','合作对象中超过一半使用记1，否则记0。'),
    ('available_information','各对象四个状态的总体条件均值可用。'),
])
def test_stated_graph_or_mapping_neither_invented_nor_erased(field,value):
    b,raw=fixture();raw=wire(raw)
    raw['common'][field]='UNKNOWN' if value=='UNKNOWN' else dict(state='STATED',value=value,refs=raw['queries'][0]['goal']['refs'])
    state=receive(b,raw,profile=CONTRACT);before=deepcopy(state.candidate)
    report=intake.inspect(state)
    assert state.candidate==before and not report['core_called']
    assert dispatch.prepare_reader(state,'q1')['request'] is None
    prior=intake.inspect(receive(b,raw,profile='inline-unified-contract-8'))
    assert report['report']['draft']==prior['report']['draft']


def test_old_request_response_binding_cannot_be_reused():
    b,raw=fixture();raw=wire(raw)
    old=receive(b,raw,profile='inline-unified-contract-8')
    new=receive(b,raw,profile=CONTRACT)
    assert old.request_sha256!=new.request_sha256
    with pytest.raises(ValueError):
        intake.receive_candidate(new,old.candidate,request_sha256=old.request_sha256)


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_current_native_results_still_need_scientific_review_and_replay(kind,expected):
    from tests_gateway.test_compact_evidence_slots import contrast_raw
    from tests_gateway.test_business_field_review import sheet,record,submit
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information')
    state=receive(b,raw,profile=CONTRACT)
    review=submit(state,record(sheet(state)))['query_review']
    entry=dispatch.prepare_reader(state,'q1',query_review=review)
    opts=dict(query_review=review,candidate=fact_reference(entry,data),request_sha256=entry['request_sha256'])
    plan=dispatch.inspect_methods(state,'q1',**opts)
    assert not dispatch.execute(state,'q1',**opts,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(state,'q1',**opts,**approval_records(plan))
    assert result['state']==expected and result['independent_replay']
