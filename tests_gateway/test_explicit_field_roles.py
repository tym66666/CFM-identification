"""Model-facing shared roles preserve wire, source and independent review boundaries."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import business_field_contract as fields
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user,CONTRACT as SHORT
from cfm_id_llm.compact_response_contract import CONTRACT,FIELD_ROLES
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_compact_short_refs import encode_fixture
from tests_gateway.test_business_field_review import sheet,record,submit
from tests_gateway.test_reading_review_guards import feedback
from cfm_id.intake_reading_revision import prepare_recheck
from examples.business_dispatch_reference import approve


def start(b,raw,short=False):
    s=intake.start_configured(b,ReadingConfig(a0_response_contract=FIELD_ROLES,
        a0_reference_contract=SHORT if short else None,target_summary_contract='target-summary-3'))
    return intake.receive_candidate(s,encode_fixture(s,raw) if short else raw,request_sha256=s.request_sha256)


def test_model_receives_shared_definitions_without_source_or_schema_shape_changes():
    b,_=fixture();a=make_compact_request(b,a0_response_contract=CONTRACT,target_summary_contract='target-summary-3')
    z=make_compact_request(b,a0_response_contract=FIELD_ROLES,target_summary_contract='target-summary-3')
    _,ap,ajs,_=split_user(a[1]);_,zp,zjs,_=split_user(z[1])
    assert ap==zp and a[2]==z[2] and z[0].startswith(a[0])
    for section,model in [('common','CompactCommon'),('query','CompactQuery'),('semantics','CompactSemantics')]:
        for f in fields.fields(section):
            text=zjs['$defs'][model]['properties'][f.name]['description']
            assert f.meaning in text and f.excludes in text
            ajs['$defs'][model]['properties'][f.name].pop('description',None)
            zjs['$defs'][model]['properties'][f.name].pop('description',None)
    assert ajs==zjs  # All types, required fields, enums and defaults remain equal.


def test_shared_review_definition_updates_are_not_hidden_from_new_request(monkeypatch):
    from dataclasses import replace
    b,_=fixture();old=make_compact_request(b,a0_response_contract=CONTRACT)
    before=make_compact_request(b,a0_response_contract=FIELD_ROLES)
    changed=tuple(replace(f,meaning=f.meaning+' 新增明确职责。') if f.name=='network_pretreatment_status' else f for f in fields.COMMON)
    monkeypatch.setattr(fields,'COMMON',changed)
    assert fields.definitions()['common'][8]['meaning'].endswith('新增明确职责。')
    assert make_compact_request(b,a0_response_contract=FIELD_ROLES)!=before
    assert make_compact_request(b,a0_response_contract=CONTRACT)==old


@pytest.mark.parametrize('short',[False,True])
@pytest.mark.parametrize('missing',['common','semantics'])
def test_missing_sections_are_still_rejected(short,missing):
    b,raw=fixture()
    (raw if missing=='common' else raw['queries'][0]).pop(missing)
    s=start(b,raw,short);r=intake.inspect(s)
    assert r['reason_code']=='A0_RESPONSE_SECTION_MISSING' and not r['core_called']
    assert dispatch.prepare_reader(s,'q1')['request'] is None


@pytest.mark.parametrize('value',[{'state':'INTERPRETED','value':'OBSERVATIONAL','refs':['s0001']},None,'RANDOM_TRIAL'])
def test_malformed_enum_is_not_converted_or_guessed(value):
    b,raw=fixture();raw['common']['assignment_family']=value;s=start(b,raw)
    assert s.candidate==raw
    assert intake.inspect(s)['reason_code']=='COMPACT_SCHEMA_REJECTED'


@pytest.mark.parametrize('field',['assignment_law','network_pretreatment_status','variable_causal_graph','exposure_mapping'])
def test_true_quote_in_wrong_field_needs_independent_rejection_not_keyword_repair(field):
    b,raw=fixture();raw['common'][field]=deepcopy(raw['common']['unit_network'])
    s=start(b,raw);assert s.candidate==raw
    w=sheet(s);r=record(w);r['decisions']['common.'+field]['field_role']='REJECTED'
    result=submit(s,r)
    assert result['state']=='CHECK_BLOCKED' and result['request'] is None
    assert not result['scientific_approval']


def test_unknown_common_fields_remain_unknown_and_not_science():
    b,raw=fixture();s=start(b,raw);r=intake.inspect(s)
    assert r['state']=='SEMANTIC_REVIEW_REQUIRED' and not r['core_called']
    assert s.candidate==raw and dispatch.prepare_reader(s,'q1')['request'] is None
    assert sheet(s)['fields']['common.network_pretreatment_status']['state']=='UNKNOWN'


def test_new_contract_rejects_old_response_context_and_old_approvals(tmp_path):
    b,raw=fixture();old=intake.start(b,a0_response_contract=CONTRACT,a0_reference_contract=SHORT,target_summary_contract='target-summary-3')
    encoded=encode_fixture(old,raw);old=intake.receive_candidate(old,encoded,request_sha256=old.request_sha256)
    q=approve(dispatch.prepare_reader(old,'q1')['query_worksheet'])
    new=start(b,raw,True)
    assert dispatch.prepare_reader(new,'q1',query_review=q)['state']=='CHECK_BLOCKED'
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):
        intake._checked({**old.model_dump(mode='json'),'a0_response_contract':FIELD_ROLES})
    wrong=intake.receive_candidate(new,encoded,request_sha256=new.request_sha256)
    assert intake.inspect(wrong)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    p=tmp_path/'new.json';intake.save(new,p);assert intake.restore(p)==new


def test_reread_retains_new_contract_and_requires_all_changes_review():
    b,raw=fixture();bad=deepcopy(raw);bad['queries'][0]['semantics']['aggregation']='UNKNOWN'
    s=start(b,bad,True);w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    new=prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
    new=intake.receive_candidate(new,encode_fixture(new,raw),request_sha256=new.request_sha256)
    assert new.a0_response_contract==FIELD_ROLES and intake.inspect(new)['state']=='REVIEW_REQUIRED'
    assert business_case.prepare_case(new)['case_worksheet'] is None


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_roles_do_not_skip_native_science_or_independent_replay(kind,expected):
    from examples.network_contrast_dispatch_reference import material,a0_reference,fact_reference,approval_records
    b,data=material(kind);s=start(b,a0_reference(b),True)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    options=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**options)
    assert not dispatch.execute(s,'q1',**options,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**options,**approval_records(p))
    assert result['state']==expected and result['independent_replay']


def test_cli_accepts_developer_response_contract_without_route_selection(tmp_path):
    from cfm_id.business_intake_cli import main
    b,_=fixture();p=tmp_path/'case.json';p.write_text(b.model_dump_json(),encoding='utf8');dest=tmp_path/'intake.json'
    assert main(['new','--case-json',str(p),'--a0-response-contract',FIELD_ROLES,'--output',str(dest)])==0
    assert intake.restore(dest).a0_response_contract==FIELD_ROLES
