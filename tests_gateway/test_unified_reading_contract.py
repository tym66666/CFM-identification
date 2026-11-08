"""Unified instructions preserve schema, sources, unknowns and review authority."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import compact_unified_contract as unified,compact_inline_evidence_contract as inline
from cfm_id_llm.compact_formulator import make_compact_request,COMPACT_SYSTEM_PROMPT
from cfm_id_llm.compact_reference_contract import split_user,request_context
from cfm_id_llm.schemas import BusinessCase,SourceDocument
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive,wire
from tests_gateway.test_compact_evidence_slots import contrast_raw
from tests_gateway.test_business_field_review import sheet,record,submit


def read(b,raw,short=True):return receive(b,raw,short,profile=unified.CONTRACT)


def no_descriptions(value):
    if isinstance(value,dict):return {k:no_descriptions(v) for k,v in value.items() if k!='description'}
    if isinstance(value,list):return [no_descriptions(v) for v in value]
    return value


@pytest.mark.parametrize('short',[False,True])
@pytest.mark.parametrize('assignment',[None,'joint-assignment-law-1'])
def test_only_reading_instructions_change_not_schema_sources_or_parser(short,assignment):
    b,_=fixture();opts=dict(a0_reference_contract='compact-source-selectors-1' if short else None,assignment_semantics=assignment,target_summary_contract='target-summary-3')
    a=make_compact_request(b,a0_response_contract=inline.CONTRACT,**opts)
    z=make_compact_request(b,a0_response_contract=unified.CONTRACT,**opts)
    _,ap,aschema,_=split_user(a[1]);_,zp,zschema,_=split_user(z[1])
    if short:
        assert ap.pop('reference_context')!=zp.pop('reference_context')
        aschema['properties'].pop('reference_context');zschema['properties'].pop('reference_context')
    assert ap==zp and a[2]==z[2] and no_descriptions(aschema)==no_descriptions(zschema)
    assert z[0].startswith(unified.SYSTEM_PROMPT) and COMPACT_SYSTEM_PROMPT not in z[0]
    assert unified.project is inline.project and unified.apply_gate is inline.apply_gate and unified.review_items is inline.review_items


@pytest.mark.parametrize('target',['target-summary-1','target-summary-2'])
def test_explicit_older_target_profiles_are_not_silently_overridden(target):
    with pytest.raises(ValueError,match='CURRENT_TARGET_SEMANTICS'):
        ReadingConfig(a0_response_contract=unified.CONTRACT,target_summary_contract=target)
    b,_=fixture()
    with pytest.raises(ValueError,match='CURRENT_TARGET_SEMANTICS'):
        make_compact_request(b,a0_response_contract=unified.CONTRACT,target_summary_contract=target)


@pytest.mark.parametrize('error',['null','bare_value','enum_object','missing_context','bad_ref','missing_with_value'])
def test_invalid_wire_is_rejected_without_guessing_or_repair(error):
    b,raw=fixture();s=read(b,wire(raw));bad=deepcopy(s.candidate)
    if error=='null':bad['common']['assignment_law']=None
    elif error=='bare_value':bad['queries'][0]['goal']='业务问题'
    elif error=='enum_object':bad['common']['assignment_family']=dict(state='STATED',value='OBSERVATIONAL',refs=bad['queries'][0]['goal']['refs'])
    elif error=='missing_context':bad.pop('reference_context')
    elif error=='bad_ref':bad['queries'][0]['goal']['refs']=['s9999']
    else:bad['queries'][0]['semantics']['comparator']=dict(state='MISSING',reason='未定',value='补填',refs=bad['queries'][0]['goal']['refs'])
    received=intake.receive_candidate(s,bad,request_sha256=s.request_sha256)
    assert received.candidate==bad and 'report' not in intake.inspect(received)
    assert not intake.inspect(received)['core_called'] and dispatch.prepare_reader(received,'q1')['request'] is None


@pytest.mark.parametrize('operation',['INTERVENTION_MINUS_COMPARATOR','COMPARATOR_MINUS_INTERVENTION','UNSPECIFIED'])
def test_missing_baseline_never_becomes_an_assumed_comparison(operation):
    b,_,raw=contrast_raw(operation=operation);raw.pop('missing_information')
    raw['queries'][0]['semantics']['comparator']=dict(state='MISSING',reason='基准安排尚未决定',refs=raw['queries'][0]['goal']['refs'])
    a=receive(b,raw);s=read(b,raw)
    assert intake.inspect(a)['wire_gate']==intake.inspect(s)['wire_gate']
    assert submit(s,record(sheet(s)))['state'] in ('NEEDS_INPUT','READING_RECHECK_REQUIRED')
    assert not intake.inspect(s)['core_called']


def test_role_error_requires_independent_review_and_is_not_automatically_deleted():
    b,_,raw=contrast_raw();raw.pop('missing_information');q=raw['queries'][0];q['kind']='DIRECT_EFFECT'
    # Boundary fixture: supply the coordinate so a missing-coordinate gate
    # does not hide the independent role rejection being tested here.
    q['semantics']['neighbor_exposure']=dict(state='STATED',value='同伴保持不使用',refs=q['goal']['refs'])
    s=read(b,raw);before=deepcopy(s.candidate);review=record(sheet(s))
    review['decisions']['queries.q1.semantics.policy_assignment']['field_role']='REJECTED'
    assert submit(s,review)['state']=='CHECK_BLOCKED' and s.candidate==before
    assert dispatch.prepare_reader(s,'q1')['request'] is None


def test_reread_and_saved_state_remain_bound_to_instructions(tmp_path):
    from cfm_id import intake_reading_revision as revision
    from tests_gateway.test_reading_review_guards import feedback
    b,raw=fixture();s=read(b,wire(raw));old=receive(b,wire(raw))
    r=intake.receive_candidate(s,old.candidate,request_sha256=s.request_sha256)
    assert intake.inspect(r)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    w=revision.prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    revised=revision.prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
    assert request_context(intake.prepare_request(s)['user_prompt'])!=request_context(intake.prepare_request(revised)['user_prompt'])
    assert revised.case==s.case and revised.reading_revision['steps'][0]['candidate']==s.candidate
    p=tmp_path/'session.json';intake.save(revised,p);assert intake.restore(p)==revised
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):
        intake._checked(dict(old.model_dump(mode='json'),a0_response_contract=unified.CONTRACT))


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_native_network_chain_still_requires_science_and_replay(kind,expected):
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information');s=read(b,raw)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**opts,**approval_records(p));assert r['state']==expected and r['independent_replay']


def test_native_dag_chain_preserves_its_own_scientific_review_and_replay():
    from tests_gateway.test_business_intake_compact import scenario
    from examples.business_dispatch_reference import approvals
    b,raw,facts=scenario();s=intake.configure_fact_format(read(b,wire(raw)),'source_hash')
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['reader_id']=='VARIABLE_DAG_FACTS'
    opts=dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts);r=dispatch.execute(s,'q1',**opts,**approvals(p))
    assert r['state']=='POINT' and r['independent_replay']


def test_transfer_cases_keep_complete_source_and_private_expectations_local():
    data=json.loads((Path(__file__).parents[1]/'evaluation/business_unified_contract_cases.json').read_text('utf8'))
    assert len(data['cases'])==3
    for row in data['cases']:
        b=BusinessCase(case_id=row['id'],business_question=row['business_question'],sources=[SourceDocument(**v) for v in row['sources']])
        s=intake.start_configured(b,ReadingConfig(a0_response_contract=unified.CONTRACT))
        public=split_user(intake.prepare_request(s)['user_prompt'])[1]
        assert public['business_question']==b.business_question and public['sources']==b.model_dump(mode='json')['sources']
        assert 'expected' not in public
