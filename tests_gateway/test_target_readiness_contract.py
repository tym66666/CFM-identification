"""Prompt-version isolation and review boundaries, not semantic accuracy claims."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.intake_reading_revision import prepare_recheck
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.target_summary_contract import CONTRACT, READINESS_CONTRACT
from tests_gateway.test_target_summary_contract import fixture, receive
from tests_gateway.test_reading_review_guards import feedback
from examples.business_dispatch_reference import approve


def test_old_profile_and_its_reviews_do_not_silently_become_readiness_profile():
    b,raw=fixture();old=receive(b,raw,CONTRACT);old_request=intake.prepare_request(old)
    new=receive(b,raw,READINESS_CONTRACT)
    assert intake.prepare_request(old)==old_request and intake._checked(old.model_dump(mode='json'))==old
    assert intake.prepare_request(new)['prompt_version']!=old_request['prompt_version']
    q=approve(dispatch.prepare_reader(old,'q1')['query_worksheet'])
    assert dispatch.prepare_reader(new,'q1',query_review=q)['state']=='CHECK_BLOCKED'
    tampered=old.model_dump(mode='json');tampered['target_summary_contract']=READINESS_CONTRACT
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):intake._checked(tampered)


def test_readiness_request_changes_only_guidance_and_field_description():
    b,_=fixture();old=make_compact_request(b,target_summary_contract=CONTRACT)
    new=make_compact_request(b,target_summary_contract=READINESS_CONTRACT)
    old_source,old_schema=old[1].split('\n\n输出 Schema：\n');new_source,new_schema=new[1].split('\n\n输出 Schema：\n')
    a=json.loads(old_schema);z=json.loads(new_schema)
    z['$defs']['CompactSemantics']['properties']['aggregation']['description']=a['$defs']['CompactSemantics']['properties']['aggregation']['description']
    assert a==z and old_source==new_source and old[2]==new[2]
    assert new[0].startswith(old[0])


def test_partial_target_keeps_known_coordinates_but_missing_summary_blocks():
    b,raw=fixture();raw['queries'][0]['semantics']['aggregation']='UNKNOWN'
    s=receive(b,raw,READINESS_CONTRACT);r=intake.inspect(s);p=dispatch.prepare_reader(s,'q1')
    assert s.candidate==raw and p['state']=='NEEDS_INPUT' and p.get('request') is None
    sem=r['report']['draft']['queries'][0]['semantics']
    assert sem['aggregation']['value'] is None and sem['target_population']['value']=='甲店'
    assert sem['policy_assignment']['value']=='三家门店全部启用排班工具' and not r['core_called']


@pytest.mark.parametrize('text',['用户尚未决定目标量','加权均值，但权重待定','不取平均，明确取结果的总和'])
def test_free_text_is_not_keyword_repaired_or_approved(text):
    b,raw=fixture();raw['queries'][0]['semantics']['aggregation']['value']=text
    s=receive(b,raw,READINESS_CONTRACT);p=dispatch.prepare_reader(s,'q1')
    assert s.candidate==raw and p['state']=='REVIEW_REQUIRED' and p.get('request') is None
    # These three fixture phrases are not supported by this fixture's question.
    # A real explicit sum in its own source remains for source review, not regex.
    q=approve(p['query_worksheet']).model_dump(mode='json');q['decisions']['source_entailment']='REJECTED'
    rejected=dispatch.prepare_reader(s,'q1',query_review=q)
    assert rejected['state']=='CHECK_BLOCKED' and rejected.get('request') is None and not rejected['backend_called']


def test_readiness_profile_survives_source_reread_without_approving_changes():
    b,raw=fixture();bad=deepcopy(raw);bad['queries'][0]['semantics']['aggregation']='UNKNOWN'
    s=receive(b,bad,READINESS_CONTRACT);w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    revised=prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
    assert revised.target_summary_contract==READINESS_CONTRACT and revised.reading_revision['steps'][0]['candidate']==bad
    revised=intake.receive_candidate(revised,raw,request_sha256=revised.request_sha256)
    assert intake.inspect(revised)['state']=='REVIEW_REQUIRED' and dispatch.prepare_reader(revised,'q1')['request'] is None
