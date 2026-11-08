"""Request binding and review safety; fixtures are not real LLM accuracy."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id.intake_reading_revision import prepare_recheck
from cfm_id_llm.target_summary_contract import CONTRACT
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm.evidence_refs import build_catalog
from tests_gateway.test_reading_review_guards import feedback
from examples.business_dispatch_reference import approve


def fixture():
    b=BusinessCase(case_id='single_target_summary',business_question='下周三家门店全部启用排班工具，只评价甲店，想知道甲店准时开门的概率。',
        sources=[SourceDocument(source_id='study',text='研究对象是甲店、乙店、丙店。门店是研究单位。启用工具记1，否则记0。下周是否准时开门，准时记1否则记0。'),
                 SourceDocument(source_id='network',text='固定双向协作边为甲店与乙店、乙店与丙店，没有其他边。')])
    cat=build_catalog(b)
    def c(value,doc='business_question'):
        return dict(state='STATED',value=value,refs=[v['ref'] for v in cat if v['source_id']==doc])
    raw=dict(common=dict(analysis_unit=c('门店','study'),treatment=c('启用工具记1，否则记0','study'),outcome=c('下周是否准时开门，准时记1否则记0','study'),unit_network=c(b.source_map()['network'],'network')),
        queries=[dict(goal=c(b.business_question),kind='FIXED_POLICY_VALUE',semantics=dict(
            target_population=c('甲店'),intervention=c('启用排班工具'),policy_assignment=c('三家门店全部启用排班工具'),
            aggregation=c('甲店准时开门的概率'),time_horizon=c('下周'),comparator='NOT_APPLICABLE'))])
    return b,raw


def receive(b,raw,contract=CONTRACT):
    s=intake.start(b,target_summary_contract=contract)
    return intake.receive_candidate(s,raw,request_sha256=s.request_sha256)


def test_opt_in_changes_explanation_not_sources_schema_or_default():
    b,_=fixture();old=make_compact_request(b);new=make_compact_request(b,target_summary_contract=CONTRACT)
    def body(user):
        payload,schema=user.split('\n\n输出 Schema：\n')
        return payload,json.loads(schema)
    p,a=body(old[1]);q,z=body(new[1])
    assert old[2]==new[2] and p==q and old[0]!=new[0]
    z['$defs']['CompactSemantics']['properties']['aggregation']['description']=a['$defs']['CompactSemantics']['properties']['aggregation']['description']
    assert a==z
    assert make_compact_request(b,target_summary_contract=None)==old
    s=intake.start(b);assert 'target_summary_contract' not in s.model_dump(mode='json')
    assert intake._checked(s.model_dump(mode='json'))==s
    with pytest.raises(ValueError):intake.start(b,target_summary_contract='unknown')


def test_contract_change_cannot_reuse_old_request_candidate_or_review():
    b,raw=fixture();old=receive(b,raw,None);new=intake.start(b,target_summary_contract=CONTRACT)
    old_review=approve(dispatch.prepare_reader(old,'q1')['query_worksheet'])
    stale=old.model_dump(mode='json');stale['target_summary_contract']=CONTRACT
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):intake._checked(stale)
    with pytest.raises(ValueError,match='STALE'):intake.receive_candidate(new,raw,request_sha256=old.request_sha256)
    new=intake.receive_candidate(new,raw,request_sha256=new.request_sha256)
    assert dispatch.prepare_reader(new,'q1',query_review=old_review)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('mode',['omitted','unknown','inapplicable'])
def test_singleton_does_not_silently_fill_a_missing_summary(mode):
    b,raw=fixture();sem=raw['queries'][0]['semantics']
    if mode=='omitted':del sem['aggregation']
    else:sem['aggregation']='UNKNOWN' if mode=='unknown' else 'NOT_APPLICABLE'
    s=receive(b,raw);r=intake.inspect(s);p=dispatch.prepare_reader(s,'q1')
    assert s.candidate==raw and not r['core_called'] and p.get('request') is None
    assert p['state'] in ('NEEDS_INPUT','READING_RECHECK_REQUIRED')
    assert r['report']['draft']['queries'][0]['semantics']['aggregation']['value'] is None


def test_singleton_probability_still_requires_query_and_science_review():
    b,raw=fixture();s=receive(b,raw);r=intake.inspect(s)
    assert r['state']=='SEMANTIC_REVIEW_REQUIRED' and not r['core_called'] and r['scientific_review_required']
    assert r['report']['prompt_version']==intake.prepare_request(s)['prompt_version']
    p=dispatch.prepare_reader(s,'q1');assert p['state']=='REVIEW_REQUIRED' and p['request'] is None
    q=approve(p['query_worksheet']);p=dispatch.prepare_reader(s,'q1',query_review=q)
    assert p['state']=='READY_TO_READ' and not p['backend_called']
    assert not r['wire_gate']['semantic_correctness_verified']


def test_source_recheck_preserves_contract_and_requires_all_change_review():
    b,correct=fixture();bad=deepcopy(correct);bad['queries'][0]['semantics']['aggregation']='UNKNOWN'
    s=receive(b,bad);w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    revised=prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
    assert revised.target_summary_contract==CONTRACT and revised.reading_revision['steps'][0]['candidate']==bad
    revised=intake.receive_candidate(revised,correct,request_sha256=revised.request_sha256)
    assert intake.inspect(revised)['state']=='REVIEW_REQUIRED'
    assert dispatch.prepare_reader(revised,'q1')['request'] is None
    assert business_case.prepare_case(revised)['case_worksheet'] is None


def test_valid_source_ids_do_not_certify_invented_target_weights():
    b,raw=fixture();raw['queries'][0]['semantics']['aggregation']['value']='三家门店等权均值'
    s=receive(b,raw);r=intake.inspect(s)
    assert r['state']=='SEMANTIC_REVIEW_REQUIRED' and not r['wire_gate']['semantic_correctness_verified']
    assert s.candidate==raw and not r['core_called']
    assert dispatch.prepare_reader(s,'q1')['request'] is None
