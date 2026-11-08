"""Prompt field boundaries do not infer facts, relax gates or change math."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import compact_inline_evidence_contract as old, compact_target_roles_contract as new
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive,wire
from tests_gateway.test_compact_evidence_slots import contrast_raw
from tests_gateway.test_business_field_review import sheet,record,submit


def read(b,raw,short=True):return receive(b,raw,short,profile=new.CONTRACT)


def test_request_changes_only_explanations_not_material_schema_or_parser():
    b,_=fixture();a=make_compact_request(b,a0_response_contract=old.CONTRACT)
    z=make_compact_request(b,a0_response_contract=new.CONTRACT)
    _,ap,ajs,_=split_user(a[1]);_,zp,zjs,_=split_user(z[1])
    assert ap==zp and a[2]==z[2] and z[0].startswith(a[0])
    for model,name in new.ROLE_NOTES:
        ajs['$defs'][model]['properties'][name].pop('description',None)
        zjs['$defs'][model]['properties'][name].pop('description',None)
    assert ajs==zjs
    assert new.project is old.project and new.review_items is old.review_items and new.apply_gate is old.apply_gate
    assert new.EXTRA_STATE_RULES==old.EXTRA_STATE_RULES


@pytest.mark.parametrize('operation',['INTERVENTION_MINUS_COMPARATOR','COMPARATOR_MINUS_INTERVENTION','UNSPECIFIED'])
@pytest.mark.parametrize('short',[False,True])
def test_known_direction_never_fills_unknown_baseline_or_changes_legacy_gate(operation,short):
    b,_,raw=contrast_raw(operation=operation);raw.pop('missing_information')
    raw['queries'][0]['semantics']['comparator']=dict(state='MISSING',reason='比较基准尚未决定',refs=raw['queries'][0]['goal']['refs'])
    a=receive(b,raw,short);z=read(b,raw,short)
    ai,zi=intake.inspect(a),intake.inspect(z)
    assert ai['wire_gate']==zi['wire_gate']
    assert {k:v for k,v in z.candidate.items() if k!='reference_context'}=={k:v for k,v in a.candidate.items() if k!='reference_context'}
    assert zi['report']['draft']['queries'][0]['semantics']['comparator']['value'] is None
    assert dispatch.prepare_reader(z,'q1')['request'] is None
    assert submit(z,record(sheet(z)))['state'] in ('NEEDS_INPUT','READING_RECHECK_REQUIRED')


@pytest.mark.parametrize('missing',[False,True])
def test_explicit_peer_condition_is_preserved_and_missing_peer_stays_blocked(missing):
    b,raw=fixture();raw=wire(raw,'INTERVENTION_MINUS_COMPARATOR');q=raw['queries'][0];q['kind']='DIRECT_EFFECT'
    q['semantics']['comparator']=deepcopy(q['semantics']['intervention'])
    q['semantics']['comparator']['value']='本人不启用'
    q['semantics']['policy_assignment']='NOT_APPLICABLE'
    peers=dict(state='MISSING',reason='同伴条件尚未决定',refs=q['goal']['refs']) if missing else dict(state='STATED',value='两种本人状态下同伴均不启用',refs=q['goal']['refs'])
    q['semantics']['neighbor_exposure']=peers
    # These are parser/boundary fixtures, not claims about source entailment.
    z=read(b,raw);r=intake.inspect(z)
    assert sheet(z)['fields']['queries.q1.semantics.neighbor_exposure']['candidate']==z.candidate['queries'][0]['semantics']['neighbor_exposure']
    field=r['report']['draft']['queries'][0]['semantics']['neighbor_exposure']
    assert field['value']==(None if missing else peers['value'])
    if missing:assert submit(z,record(sheet(z)))['state']=='NEEDS_INPUT'
    assert not r['core_called']


@pytest.mark.parametrize('path,dimension',[('queries.q1.semantics.neighbor_exposure','field_role'),('queries.q1.comparison_order','value_state')])
def test_wrong_role_or_sign_requires_independent_rejection_not_automatic_repair(path,dimension):
    b,_,raw=contrast_raw();raw.pop('missing_information')
    raw['queries'][0]['semantics']['neighbor_exposure']=dict(state='STATED',value='按同伴使用数分档的定义',refs=raw['queries'][0]['goal']['refs'])
    s=read(b,raw);before=deepcopy(s.candidate);review=record(sheet(s));review['decisions'][path][dimension]='REJECTED'
    assert submit(s,review)['state']=='CHECK_BLOCKED' and s.candidate==before
    assert not intake.inspect(s)['core_called']


def test_new_contract_invalidates_old_context_and_review_and_preserves_history(tmp_path):
    b,raw=fixture();raw=wire(raw);a=receive(b,raw);z=read(b,raw)
    old_review=submit(a,record(sheet(a)))['query_review']
    assert dispatch.prepare_reader(z,'q1',query_review=old_review)['request'] is None
    wrong=intake.receive_candidate(z,a.candidate,request_sha256=z.request_sha256)
    assert intake.inspect(wrong)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    p=tmp_path/'intake.json';intake.save(z,p);assert intake.restore(p)==z
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):
        intake._checked(dict(a.model_dump(mode='json'),a0_response_contract=new.CONTRACT))


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_unchanged_native_math_and_replay_need_scientific_review(kind,expected):
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information');s=read(b,raw)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**opts,**approval_records(p));assert r['state']==expected and r['independent_replay']


def test_dag_reader_and_replay_are_unaffected():
    from tests_gateway.test_business_intake_compact import scenario
    from examples.business_dispatch_reference import approvals
    b,raw,facts=scenario();s=intake.configure_fact_format(read(b,wire(raw)),'source_hash')
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['reader_id']=='VARIABLE_DAG_FACTS'
    opts=dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts);r=dispatch.execute(s,'q1',**opts,**approvals(p))
    assert r['state']=='POINT' and r['independent_replay']


def test_business_cases_send_only_original_material_not_expected_labels():
    data=json.loads((Path(__file__).parents[1]/'evaluation/business_target_role_cases.json').read_text('utf8'))
    assert len(data['cases'])==len({r['id'] for r in data['cases']})==7
    for row in data['cases']:
        b=BusinessCase(case_id=row['id'],business_question=row['business_question'],sources=[SourceDocument(**s) for s in row['sources']])
        s=intake.start_configured(b,ReadingConfig(a0_response_contract=new.CONTRACT));req=intake.prepare_request(s)
        public=split_user(req['user_prompt'])[1]
        assert public['business_question']==row['business_question'] and public['sources']==b.model_dump(mode='json')['sources']
        assert 'expected' not in public


def test_cli_accepts_profile_without_route_selection(tmp_path):
    from cfm_id.business_intake_cli import main
    b,_=fixture();p=tmp_path/'case.json';p.write_text(b.model_dump_json(),encoding='utf8');out=tmp_path/'intake.json'
    assert main(['new','--case-json',str(p),'--a0-response-contract',new.CONTRACT,'--output',str(out)])==0
    assert intake.restore(out).a0_response_contract==new.CONTRACT
