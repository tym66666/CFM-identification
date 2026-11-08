"""Complete comparison states remain source proposals, never implicit permits."""
from copy import deepcopy
from pydantic import TypeAdapter
import pytest

from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import compact_response_contract as profiles, compact_unified_contract as unified
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.compact_formulator import make_compact_request
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_compact_evidence_slots import contrast_raw
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_unified_reading_contract import no_descriptions

PROFILE=unified.ENDPOINT_CONTRACT


def test_configuration_cli_and_request_use_one_closed_profile_inventory():
    from cfm_id.business_intake_cli import A0_RESPONSE_PROFILES
    values=next(s['enum'] for s in TypeAdapter(profiles.Profile).json_schema()['anyOf'] if 'enum' in s)
    assert tuple(values)==profiles.PROFILES==A0_RESPONSE_PROFILES
    assert profiles.UNIFIED_PROFILES==unified.CONTRACTS
    assert ReadingConfig(a0_response_contract=PROFILE).a0_response_contract==PROFILE
    assert ReadingConfig().a0_response_contract is None


@pytest.mark.parametrize('short',[False,True])
def test_new_instructions_keep_wire_materials_parser_and_unknown_states(short):
    b,_=fixture();opts=dict(target_summary_contract='target-summary-3',a0_reference_contract='compact-source-selectors-1' if short else None)
    old=make_compact_request(b,a0_response_contract=unified.LOCAL_STATE_CONTRACT,**opts)
    new=make_compact_request(b,a0_response_contract=PROFILE,**opts)
    _,op,os,_=split_user(old[1]);_,np,ns,_=split_user(new[1])
    if short:
        assert op.pop('reference_context')!=np.pop('reference_context')
        os['properties'].pop('reference_context');ns['properties'].pop('reference_context')
    assert op==np and old[2]==new[2] and no_descriptions(os)==no_descriptions(ns)
    assert profiles.evidence_contract(PROFILE).project is profiles.evidence_contract(unified.LOCAL_STATE_CONTRACT).project
    assert '比较方向与比较条件分开：' in old[0] and '共同条件属于两端' not in old[0]
    assert '共同条件属于两端' in new[0] and new[0].count('比较方向与比较条件分开。')==1


def test_recheck_and_review_use_current_endpoint_duties_without_replacement_values():
    from cfm_id import intake_reading_revision as revision
    from tests_gateway.test_reading_review_guards import feedback
    b,raw=fixture();s=receive(b,wire(raw),True,profile=PROFILE)
    w=revision.prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    f=feedback(w);f['issues'][0].update(field_path='/queries/0/semantics/intervention',kind='OMITTED_OR_MISREAD')
    r=revision.prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST')
    text=intake.prepare_request(r)['user_prompt']
    assert '共同条件与本端变化条件' in text and 'PRIVATE_REASON_STAYS_LOCAL' not in text
    assert r.case==s.case and r.candidate is None and r.reading_revision['steps'][0]['candidate']==s.candidate
    assert '共同条件与本端变化条件' in str(sheet(s)['fields']['queries.q1.semantics.intervention']['definition'])


@pytest.mark.parametrize('operation',['INTERVENTION_MINUS_COMPARATOR','COMPARATOR_MINUS_INTERVENTION','UNSPECIFIED'])
def test_unknown_comparison_end_never_filled_by_complete_endpoint_guidance(operation):
    b,_,raw=contrast_raw(operation=operation);raw.pop('missing_information')
    raw['queries'][0]['semantics']['comparator']=dict(state='MISSING',reason='基准安排尚未决定',refs=raw['queries'][0]['goal']['refs'])
    s=receive(b,raw,True,profile=PROFILE);before=deepcopy(s.candidate)
    result=submit(s,record(sheet(s)))
    assert result['state'] in ('NEEDS_INPUT','READING_RECHECK_REQUIRED') and s.candidate==before
    assert dispatch.prepare_reader(s,'q1',query_review=result['query_review'])['request'] is None


@pytest.mark.parametrize('path,dimension',[
    ('common.variable_causal_graph','field_role'),
    ('queries.q1.semantics.intervention','field_role'),
    ('queries.q1.semantics.target_population','source_coverage'),
])
def test_independent_role_or_citation_rejection_blocks_without_rewriting(path,dimension):
    b,raw=fixture();s=receive(b,wire(raw),True,profile=PROFILE);before=deepcopy(s.candidate)
    r=record(sheet(s));r['decisions'][path][dimension]='REJECTED'
    result=submit(s,r)
    assert result['state']=='CHECK_BLOCKED' and s.candidate==before
    entry=dispatch.prepare_reader(s,'q1',query_review=result['query_review'])
    assert entry['request'] is None and not entry['backend_called']


def test_old_candidate_and_review_cannot_cross_the_new_request_binding():
    b,raw=fixture();old=receive(b,wire(raw),True,profile=unified.LOCAL_STATE_CONTRACT)
    new=receive(b,wire(raw),True,profile=PROFILE)
    wrong=intake.receive_candidate(new,old.candidate,request_sha256=new.request_sha256)
    assert intake.inspect(wrong)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    with pytest.raises(ValueError,match='STALE_FIELD_REVIEW'):
        submit(new,record(sheet(old)))


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_existing_network_comparison_requires_science_and_independent_replay(kind,expected):
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information');s=receive(b,raw,True,profile=PROFILE)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**opts,**approval_records(p))
    assert r['state']==expected and r['independent_replay']


def test_variable_dag_keeps_its_separate_contract_and_replay():
    from tests_gateway.test_business_intake_compact import scenario
    from examples.business_dispatch_reference import approvals
    b,raw,facts=scenario();s=intake.configure_fact_format(receive(b,wire(raw),True,profile=PROFILE),'source_hash')
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['reader_id']=='VARIABLE_DAG_FACTS'
    opts=dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    r=dispatch.execute(s,'q1',**opts,**approvals(p))
    assert r['state']=='POINT' and r['independent_replay']
