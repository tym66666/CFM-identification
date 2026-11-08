"""Wire compatibility, exact provenance and stale-response boundaries."""
from copy import deepcopy
import json
import pytest

from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from cfm_id.intake_reading_revision import prepare_recheck,review_changes
from cfm_id.intake_stop_review import prepare_review,review_stop
from cfm_id_llm.compact_formulator import CompactFormulator,make_compact_request
from cfm_id_llm.compact_reference_contract import CONTRACT,catalog,request_context,split_user
from cfm_id_llm.evidence_refs import build_catalog,_BoundDraftProvider
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_intake_stop_review import uncertain,record
from tests_gateway.test_reading_review_guards import feedback,accept_changes
from examples.business_dispatch_reference import approve


def encode_fixture(s,raw):
    """Fixture-only serialization; never used to repair a live reply."""
    refs={a['ref']:b['ref'] for a,b in zip(build_catalog(s.case),catalog(s.case,CONTRACT))}
    def walk(x):
        if isinstance(x,dict):return {k:([refs[r] for r in v] if k=='refs' else walk(v)) for k,v in x.items()}
        if isinstance(x,list):return [walk(v) for v in x]
        return deepcopy(x)
    return dict(walk(raw),reference_context=request_context(intake.prepare_request(s)['user_prompt']))


def receive(s,raw):
    return intake.receive_candidate(s,raw,request_sha256=s.request_sha256)


def setup():
    b,raw=fixture();s=intake.start(b,a0_reference_contract=CONTRACT,target_summary_contract='target-summary-2')
    return receive(s,encode_fixture(s,raw)),raw


def test_default_request_checkpoint_and_source_spans_are_unchanged():
    b,raw=fixture();old=intake.start(b);base=make_compact_request(b)
    assert 'a0_reference_contract' not in old.model_dump(mode='json')
    assert make_compact_request(b,a0_reference_contract=None)==base
    new=make_compact_request(b,a0_reference_contract=CONTRACT)
    _,p,a,_=split_user(base[1]);_,q,z,_=split_user(new[1])
    q.pop('reference_context')
    for i,r in enumerate(q['source_catalog']):r['ref']=p['source_catalog'][i]['ref']
    assert p==q
    z['properties'].pop('reference_context');z['required'].remove('reference_context')
    for name in ('CompactClaim','GroundedOrUnknownClaim'):
        z['$defs'][name]['properties']['refs']=deepcopy(a['$defs'][name]['properties']['refs'])
    assert a==z and new[0].startswith(base[0])
    assert [dict(r,ref=base[2][i]['ref']) for i,r in enumerate(new[2])]==base[2]


def test_equivalent_selectors_keep_exact_original_meaning_and_quotes():
    s,raw=setup();before=deepcopy(s.candidate)
    old=receive(intake.start(s.case,target_summary_contract='target-summary-2'),raw)
    a=intake.inspect(s);b=intake.inspect(old)
    assert a['report']['draft']==b['report']['draft'] and a['wire_gate']==b['wire_gate']
    assert s.candidate==before and a['state']=='SEMANTIC_REVIEW_REQUIRED'
    assert dispatch.prepare_reader(s,'q1')['state']=='REVIEW_REQUIRED' and not a['core_called']
    rejected=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']).model_dump(mode='json')
    rejected['decisions']['source_entailment']='REJECTED'
    assert dispatch.prepare_reader(s,'q1',query_review=rejected)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('bad',['s0000','s9999','s1','S0001','s0001 ','s000l','e0123456789ab_0001',17,None])
def test_invalid_selector_is_rejected_without_fuzzy_repair(bad):
    s,_=setup();raw=deepcopy(s.candidate);raw['queries'][0]['goal']['refs']=[bad]
    s=receive(s,raw);r=intake.inspect(s)
    assert r['state']=='READING_RECHECK_REQUIRED' and r['reason_code']=='A0_REFERENCE_NOT_FOUND'
    assert s.candidate==raw and dispatch.prepare_reader(s,'q1')['request'] is None


@pytest.mark.parametrize('bad',['missing','changed','null','number','extra','duplicate'])
def test_context_and_schema_are_strict(bad):
    s,_=setup();raw=deepcopy(s.candidate)
    if bad=='missing':raw.pop('reference_context')
    elif bad=='changed':raw['reference_context']='c'+'0'*64
    elif bad=='null':raw['reference_context']=None
    elif bad=='number':raw['reference_context']=1
    elif bad=='extra':raw['unrequested_field']='POINT'
    else:raw['queries'][0]['goal']['refs']*=2
    r=intake.inspect(receive(s,raw))
    assert r['state']=='READING_RECHECK_REQUIRED' and not r['core_called']


@pytest.mark.parametrize('change',['case','same_case_new_intake','material_revision','profile'])
def test_other_material_session_revision_or_profile_rejects_old_context(change):
    s,_=setup();b=s.case
    if change=='case':b=b.model_copy(update={'case_id':'other','business_question':b.business_question+'新增问题。'})
    if change=='material_revision':new=intake.revise_materials(s,b,reason='重新核对材料')
    else:new=intake.start(b,a0_reference_contract=CONTRACT,target_summary_contract=None if change=='profile' else 'target-summary-2')
    with pytest.raises(ValueError,match='STALE'):intake.receive_candidate(new,s.candidate,request_sha256=s.request_sha256)
    r=intake.inspect(receive(new,s.candidate))
    assert r['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH' and not r['core_called']


def test_old_protocol_and_old_approvals_cannot_be_used_as_short_contract():
    s,raw=setup();old=receive(intake.start(s.case,target_summary_contract='target-summary-2'),raw)
    assert intake.inspect(receive(s,raw))['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    assert intake.inspect(receive(old,s.candidate))['reason_code']=='COMPACT_SCHEMA_REJECTED'
    old_review=approve(dispatch.prepare_reader(old,'q1')['query_worksheet'])
    assert dispatch.prepare_reader(s,'q1',query_review=old_review)['state']=='CHECK_BLOCKED'
    changed=old.model_dump(mode='json');changed['a0_reference_contract']=CONTRACT
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):intake._checked(changed)
    with pytest.raises(ValueError):intake.start(s.case,a0_reference_contract='invented')
    with pytest.raises(ValueError,match='REQUIRES_COMPACT'):intake.start(s.case,a0_reference_contract=CONTRACT,reading_format='canonical')


def test_missing_target_stops_and_reply_changes_context_without_old_approval(tmp_path):
    old=uncertain();s=intake.start(old.case,a0_reference_contract=CONTRACT,target_summary_contract='target-summary-2')
    s=receive(s,encode_fixture(s,old.candidate))
    w=prepare_review(s,authority='SYNTHETIC_TEST')['stop_worksheet']
    assert all(k.startswith('s') for k in w['source_catalog'])
    checked=review_stop(s,record(w),authority='SYNTHETIC_TEST');plan=intake.clarification_plan(checked)
    assert len(plan['questions'])==1 and dispatch.prepare_reader(checked,'q1')['request'] is None
    new=intake.append_reply(checked,plan,plan['questions'][0]['clarification_id'],'只看甲店准时开门的概率。')
    assert new.a0_reference_contract==CONTRACT and new.candidate is None and new.reading_stop_review is None
    assert new.case.sources[:-1]==s.case.sources and new.case.sources[-1].text=='只看甲店准时开门的概率。'
    assert intake.inspect(receive(new,s.candidate))['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    intake.save(new,tmp_path/'new.json');assert intake.restore(tmp_path/'new.json')==new


def test_explicit_rereads_use_fresh_context_and_all_change_review(tmp_path):
    s,raw=setup();bad=deepcopy(raw);bad['queries'][0]['semantics']['time_horizon']['value']='五十年后'
    s=receive(s,encode_fixture(s,bad));old=deepcopy(s.candidate)
    for i in range(2):
        w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
        assert all(k.startswith('s') for k in w['source_catalog'])
        revised=prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
        req=intake.prepare_request(revised)
        assert 'PRIVATE_REASON_STAYS_LOCAL' not in req['user_prompt']
        assert intake.inspect(receive(revised,s.candidate))['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
        next_raw=raw if i==0 else bad
        candidate=encode_fixture(revised,next_raw);fresh=receive(revised,candidate)
        checked=intake.inspect(fresh)
        assert checked['state']=='REVIEW_REQUIRED' and not checked['core_called']
        assert dispatch.prepare_reader(fresh,'q1')['request'] is None
        s=review_changes(fresh,accept_changes(checked['reading_change_worksheet']))
        assert intake.inspect(s)['state']=='SEMANTIC_REVIEW_REQUIRED'
        assert s.candidate==candidate and len(s.reading_revision['steps'])==i+1
    assert s.reading_revision['steps'][0]['candidate']==old
    intake.save(s,tmp_path/'reread.json');assert intake.restore(tmp_path/'reread.json')==s


def test_real_source_id_is_not_entailment_or_scientific_permission():
    s,_=setup();raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics']['aggregation']['value']='凭空增加两个对象，三比一权重'
    s=receive(s,raw);pending=dispatch.prepare_reader(s,'q1')
    assert pending['state']=='REVIEW_REQUIRED' and pending['request'] is None
    r=approve(pending['query_worksheet']).model_dump(mode='json');r['decisions']['source_entailment']='REJECTED'
    assert dispatch.prepare_reader(s,'q1',query_review=r)['state']=='CHECK_BLOCKED'
    assert not business_case.execute_case(s,{},research_protocol_selected=True)['backend_called']


def test_short_contract_supports_existing_point_chain_only_after_reviews():
    from examples.network_dispatch_reference import case,candidate,approval_records
    b,_,_=case();cat=build_catalog(b)
    def c(text,doc):return dict(state='STATED',value=text,refs=[r['ref'] for r in cat if r['source_id']==doc])
    goal=c(b.business_question,'business_question')
    raw=dict(common={k:c(b.source_map()[d],d) for k,d in [('analysis_unit','study'),('treatment','study'),('outcome','study'),('unit_network','network')]},queries=[dict(goal=goal,kind='FIXED_POLICY_VALUE',semantics=dict(target_population=goal,intervention=goal,policy_assignment=goal,aggregation=goal,time_horizon=c('本周','study'),comparator='NOT_APPLICABLE'))])
    s=intake.start(b,a0_reference_contract=CONTRACT);s=receive(s,encode_fixture(s,raw))
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    qr=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=qr)
    opts=dict(query_review=qr,candidate=candidate(e),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    blocked=dispatch.execute(s,'q1',**opts,research_protocol_selected=True)
    assert not blocked['backend_called'] and blocked['mathematical_claim'] is None
    result=dispatch.execute(s,'q1',**opts,**approval_records(p))
    assert result['state']=='POINT' and result['independent_replay'] and result['mathematical_claim']['numeric_value'] is None


def test_cli_new_short_contract_is_offline_and_checkpoint_roundtrips(tmp_path):
    from cfm_id.business_intake_cli import main
    b,_=fixture();path=tmp_path/'case.json';path.write_text(b.model_dump_json(),encoding='utf8')
    dest=tmp_path/'intake.json';request=tmp_path/'request.json'
    assert main(['new','--case-json',str(path),'--a0-reference-contract',CONTRACT,'--output',str(dest)])==0
    assert main(['request','--intake',str(dest),'--output',str(request)])==0
    assert intake.restore(dest).a0_reference_contract==CONTRACT
    assert request_context(intake.read_json(request)['user_prompt']).startswith('c')
