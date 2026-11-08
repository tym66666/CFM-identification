"""Request compatibility/binding only; live accuracy is measured separately."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.assignment_semantics import VERSION, GUIDANCE
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.network_policy_reading import make_request
from tests_gateway.test_business_intake_compact import scenario
from tests_gateway.test_fact_reading_revision import feedback
from tests_gateway.test_reading_review_guards import feedback as a0_feedback
from examples.business_dispatch_reference import approve


def network():
    from examples.network_dispatch_reference import case, candidate
    from cfm_id_llm.evidence_refs import build_catalog
    b,_,docs=case();catalog=build_catalog(b)
    def claim(doc):
        return dict(state='STATED',value=b.business_question if doc=='business_question' else docs[doc],
                    refs=[r['ref'] for r in catalog if r['source_id']==doc])
    raw=dict(common=dict(analysis_unit=claim('study'),treatment=claim('study'),outcome=claim('study'),
        temporal_structure=claim('study'),unit_network=claim('network'),assignment_family='COMPLETE_RANDOMIZATION',assignment_law=claim('assignment')),
        queries=[dict(goal=claim('business_question'),kind='FIXED_POLICY_VALUE',semantics={
            **{f:claim('business_question') for f in ('target_population','intervention','policy_assignment','aggregation')},
            'time_horizon':claim('study')})])
    s=intake.start(b,assignment_semantics=VERSION);s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    return s,q,e,candidate(e)


def test_historical_profile_is_absent_and_legacy_request_remains_exact():
    case,raw,_=scenario();s=intake.start(case,assignment_semantics=None)
    system,user,_=make_compact_request(case)
    assert intake.prepare_request(s)['system_prompt']==system
    assert intake.prepare_request(s)['user_prompt']==user
    assert 'assignment_semantics' not in s.model_dump(mode='json')
    assert intake._checked(s.model_dump(mode='json'))==s
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    assert not intake.inspect(s)['core_called']


def test_profile_change_cannot_reuse_old_request_or_review():
    case,raw,_=scenario();old=intake.start(case,assignment_semantics=None)
    old=intake.receive_candidate(old,raw,request_sha256=old.request_sha256)
    old_review=approve(dispatch.prepare_reader(old,'q1')['query_worksheet'])
    changed=old.model_dump(mode='json');changed['assignment_semantics']=VERSION
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):intake._checked(changed)
    new=intake.start(case,assignment_semantics=VERSION)
    with pytest.raises(ValueError,match='STALE'):intake.receive_candidate(new,raw,request_sha256=old.request_sha256)
    new=intake.receive_candidate(new,raw,request_sha256=new.request_sha256)
    assert dispatch.prepare_reader(new,'q1',query_review=old_review)['state']=='CHECK_BLOCKED'
    with pytest.raises(ValueError):intake.start(case,assignment_semantics='unknown-profile')


def test_assignment_dictionary_does_not_change_wire_or_source_or_dag_facts():
    s,q,e,raw=network();assert e['assignment_semantics']==VERSION
    old=make_request(e['bundle'],binding=e['fact_binding_sha256'])
    new=make_request(e['bundle'],binding=e['fact_binding_sha256'],assignment_semantics=VERSION)
    def without_descriptions(v):
        if isinstance(v,dict):return {k:without_descriptions(x) for k,x in v.items() if k!='description'}
        if isinstance(v,list):return [without_descriptions(x) for x in v]
        return v
    assert without_descriptions(json.loads(old['user']))==without_descriptions(json.loads(new['user']))
    assert GUIDANCE in new['system'] and GUIDANCE not in old['system']
    assert not dispatch.inspect_methods(s,'q1',query_review=q,candidate=raw,request_sha256=e['request_sha256'])['backend_called']
    case,raw,_=scenario();s=intake.start(case);s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert GUIDANCE not in e['request']['system']


def test_profile_survives_both_explicit_rereads_without_approving_anything():
    from cfm_id.intake_reading_revision import prepare_recheck as reread_a0
    from cfm_id.fact_reading_revision import prepare_recheck as reread_fact
    s,q,e,raw=network()
    w=reread_a0(s,authority='SYNTHETIC_TEST');new=reread_a0(s,authority='SYNTHETIC_TEST',feedback=a0_feedback(w['feedback_worksheet']))
    assert new.assignment_semantics==VERSION and GUIDANCE in intake.prepare_request(new)['system_prompt']
    args=dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])
    w=reread_fact(s,'q1',**args);new=reread_fact(s,'q1',**args,feedback=feedback(w['feedback_worksheet']))
    assert new['state']=='READY_TO_READ' and new['assignment_semantics']==VERSION
    assert GUIDANCE in new['request']['system'] and not new['reading_revision_receipt']['scientific_approval']
    assert new['reading_revision']['steps'][0]['candidate']==raw


def test_experimental_profile_is_opt_in_and_never_repairs_a_raw_label():
    case,raw,_=scenario();default=intake.start(case)
    assert default.assignment_semantics is None
    s,_,_,_=network();raw=deepcopy(s.candidate);raw['common']['assignment_family']='OTHER'
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    result=intake.inspect(s)
    assert s.candidate==raw and result['report']['draft']['shared_draft']['information_design']['assignment_family']=='OTHER'
    assert result['report']['prompt_version']==intake.prepare_request(s)['prompt_version']
    assert not result['core_called'] and result['scientific_review_required']
