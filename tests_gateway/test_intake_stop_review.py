"""Stop classification cannot repair targets, release reviews or call math."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id.intake_stop_review import prepare_review, review_stop
from cfm_id.intake_reading_revision import prepare_recheck, review_changes
from cfm_id_llm.evidence_refs import build_catalog
from tests_gateway.test_target_summary_contract import fixture, receive
from tests_gateway.test_reading_review_guards import feedback, accept_changes
from examples.business_dispatch_reference import approve


def uncertain(text='下周三家门店全部启用排班工具，只评价甲店。平均准时率还是其他结果量尚未决定。',kind='UNRESOLVED'):
    b,raw=fixture();old={v['ref']:v['source_id'] for v in build_catalog(b)}
    b=b.model_copy(update={'business_question':text});new=build_catalog(b)
    def rebind(x):
        if isinstance(x,dict):
            if 'refs' in x:x['refs']=[v['ref'] for v in new if v['source_id'] in {old[r] for r in x['refs']}]
            for k,v in x.items():
                if k!='refs':rebind(v)
        elif isinstance(x,list):
            for v in x:rebind(v)
    rebind(raw);q=raw['queries'][0];q['goal']['value']=text;q['kind']=kind
    q['semantics']['aggregation']='UNKNOWN';q['semantics']['comparator']='UNKNOWN' if kind=='UNRESOLVED' else 'NOT_APPLICABLE'
    return receive(b,raw,'target-summary-2')


def record(sheet,disposition='MATERIAL_GAP'):
    ids=[k for k,v in sheet['source_catalog'].items() if v['doc_id']=='business_question']
    return dict(version=sheet['version'],binding_sha256=sheet['binding_sha256'],authority='SYNTHETIC_TEST',
        reviewer='Independent synthetic source reviewer',evidence='Reviewed the actual question and source fields; this is not scientific approval.',
        decisions={qid:dict(disposition=disposition,reason='原文尚未决定目标量；已定对象和政策保持，只有该缺项需要补充。',source_ids=ids) for qid in sheet['items']})


def reviewed(s,disposition='MATERIAL_GAP'):
    sheet=prepare_review(s,authority='SYNTHETIC_TEST')['stop_worksheet']
    return review_stop(s,record(sheet,disposition),authority='SYNTHETIC_TEST')


@pytest.mark.parametrize('text',[
 '下周三家门店全部启用排班工具，只评价甲店。平均准时率还是其他结果量尚未决定。',
 '下周三家门店全部启用排班工具，只看甲店；结果口径待负责人确认，目前没有定案。',
 'All three shops will adopt the tool next week. Evaluate Jia Shop (甲店); the outcome summary is not yet decided.',
])
def test_source_confirmed_gap_only_changes_stop_and_not_target(text):
    s=uncertain(text);before=intake.prepare_request(s);raw=deepcopy(s.candidate)
    assert dispatch.prepare_reader(s,'q1')['state']=='READING_RECHECK_REQUIRED'
    result=reviewed(s);r=intake.inspect(result);p=dispatch.prepare_reader(result,'q1')
    assert r['state']=='BUSINESS_CLARIFICATION_REQUIRED' and p['state']=='NEEDS_INPUT'
    assert p['reason_code']=='SOURCE_CONFIRMED_TARGET_GAP' and p['request'] is None
    assert result.candidate==raw and intake.prepare_request(result)==before and not r['core_called']
    assert not r['reading_stop_receipt']['scientific_approval'] and not r['wire_gate']['semantic_correctness_verified']
    plan=intake.clarification_plan(result)
    assert len(plan['questions'])==1 and plan['questions'][0]['field_path'].endswith('.aggregation')
    assert plan['questions'][0]['status']=='SOURCE_CONFIRMED_TARGET_GAP'


def test_known_source_omitted_by_reader_is_reread_not_user_question():
    b,raw=fixture();raw['queries'][0]['semantics']['aggregation']='UNKNOWN';s=receive(b,raw)
    sheet=prepare_review(s,authority='SYNTHETIC_TEST')['stop_worksheet'];r=record(sheet,'READING_ERROR')
    r['decisions']['q1']['reason']='原文已说明甲店准时开门的概率，候选遗漏它；应重读而非要求用户重复说明。'
    revised=review_stop(s,r,authority='SYNTHETIC_TEST')
    assert dispatch.prepare_reader(revised,'q1')['state']=='READING_RECHECK_REQUIRED'
    assert intake.clarification_plan(revised)['questions']==[] and revised.candidate==s.candidate
    assert prepare_recheck(revised,authority='SYNTHETIC_TEST')['request'] is None


@pytest.mark.parametrize('bad',['invalid_na','other','common_na','unexpected_comparator'])
def test_protocol_conflict_cannot_be_relabelled_as_material_gap(bad):
    s=uncertain();raw=deepcopy(s.candidate)
    if bad=='invalid_na':raw['queries'][0]['semantics']['comparator']='NOT_APPLICABLE'
    elif bad=='other':raw['queries'][0]['kind']='OTHER'
    elif bad=='common_na':raw['common']['outcome']='NOT_APPLICABLE'
    else:
        raw['queries'][0]['kind']='FIXED_POLICY_VALUE'
        raw['queries'][0]['semantics']['comparator']=deepcopy(raw['queries'][0]['semantics']['intervention'])
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    sheet=prepare_review(s,authority='SYNTHETIC_TEST')['stop_worksheet']
    assert not sheet['items']['q1']['material_gap_allowed']
    with pytest.raises(ValueError):review_stop(s,record(sheet),authority='SYNTHETIC_TEST')
    revised=review_stop(s,record(sheet,'READING_ERROR'),authority='SYNTHETIC_TEST')
    assert dispatch.prepare_reader(revised,'q1')['request'] is None
    assert intake.clarification_plan(revised)['questions']==[]


@pytest.mark.parametrize('bad',['binding','source','empty_source','duplicate_source','missing_query','extra_query','authority','blank_reason','blank_reviewer','extra_value','accepted'])
def test_invalid_or_stale_review_rejected(bad):
    s=uncertain();sheet=prepare_review(s,authority='SYNTHETIC_TEST')['stop_worksheet'];r=record(sheet)
    if bad=='binding':r['binding_sha256']='0'*64
    elif bad=='source':r['decisions']['q1']['source_ids']=['invented']
    elif bad=='empty_source':r['decisions']['q1']['source_ids']=[]
    elif bad=='duplicate_source':r['decisions']['q1']['source_ids']*=2
    elif bad=='missing_query':r['decisions']={}
    elif bad=='extra_query':r['decisions']['q2']=deepcopy(r['decisions']['q1'])
    elif bad=='authority':r['authority']='EXTERNAL_RESEARCH_REVIEW'
    elif bad=='blank_reason':r['decisions']['q1']['reason']=' '*20
    elif bad=='blank_reviewer':r['reviewer']=' '*20
    elif bad=='extra_value':r['replacement_target']='POINT'
    else:r['decisions']['q1']['disposition']='ACCEPTED'
    with pytest.raises(ValueError):review_stop(s,r,authority='SYNTHETIC_TEST')


def test_stop_review_never_releases_query_or_whole_case():
    s=reviewed(uncertain());p=dispatch.prepare_reader(s,'q1',query_review={'fake':'approval'})
    # Explicit malformed review is now reported before the genuine gap, with
    # both paths remaining blocked; no-review behavior stays NEEDS_INPUT.
    assert p['state']=='CHECK_BLOCKED' and p['query_worksheet'] is not None and p['request'] is None
    r=dispatch.execute(s,'q1',query_review={},candidate={},request_sha256='0'*64,research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called'] and r['mathematical_claim'] is None
    case=business_case.prepare_case(s)
    whole=business_case.execute_case(s,{'q1':{}},case_review=approve(case['case_worksheet']),research_protocol_selected=True)
    assert whole['state']=='CASE_INCOMPLETE' and whole['results'][0]['result']['state']=='NEEDS_INPUT'
    assert not whole['backend_called'] and whole['identified_query_ids']==[]


def test_business_gap_does_not_hide_simultaneous_canonical_reading_conflict():
    s=uncertain();raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics']['policy_assignment']['value']='仅给部分门店启用排班工具'
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    audit=intake.inspect(s)['report']['query_quality'][0]
    assert audit['business_status']=='BUSINESS_CLARIFICATION_REQUIRED'
    assert any(x['owner']=='A0_FORMULATOR' for x in audit['actions'])
    sheet=prepare_review(s,authority='SYNTHETIC_TEST')['stop_worksheet']
    assert not sheet['items']['q1']['material_gap_allowed']
    with pytest.raises(ValueError):review_stop(s,record(sheet),authority='SYNTHETIC_TEST')
    assert dispatch.prepare_reader(reviewed(s,'READING_ERROR'),'q1')['state']=='READING_RECHECK_REQUIRED'


def test_mixed_queries_keep_independent_stops_and_old_reviews_expire():
    s=uncertain();raw=deepcopy(s.candidate);q=deepcopy(raw['queries'][0]);q['kind']='FIXED_POLICY_VALUE'
    q['semantics']['aggregation']=deepcopy(q['semantics']['target_population']);q['semantics']['aggregation']['value']='甲店准时开门的概率'
    q['semantics']['comparator']='NOT_APPLICABLE';raw['queries'].append(q)
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    old=approve(dispatch.prepare_reader(s,'q2')['query_worksheet']);changed=reviewed(s)
    assert dispatch.prepare_reader(changed,'q1')['state']=='NEEDS_INPUT'
    assert dispatch.prepare_reader(changed,'q2')['state']=='REVIEW_REQUIRED'
    assert dispatch.prepare_reader(changed,'q2',query_review=old)['state']=='CHECK_BLOCKED'
    assert len(business_case.prepare_case(changed)['queries'])==2


def test_review_revision_history_and_old_clarification_plan_expire(tmp_path):
    s=reviewed(uncertain(),'PENDING');assert dispatch.prepare_reader(s,'q1')['state']=='REVIEW_REQUIRED'
    gap=reviewed(s);plan=intake.clarification_plan(gap);reread=reviewed(gap,'READING_ERROR')
    assert len(reread.reading_stop_review['history'])==2 and intake.clarification_plan(reread)['questions']==[]
    with pytest.raises(ValueError,match='STALE'):intake.append_reply(reread,plan,plan['questions'][0]['clarification_id'],'取均值')
    intake.save(reread,tmp_path/'review.json');assert intake.restore(tmp_path/'review.json')==reread


@pytest.mark.parametrize('event',['candidate','materials','reread','fact_format','fact_contract'])
def test_new_context_clears_review_and_archives_it(event):
    s=reviewed(uncertain());record_before=deepcopy(s.reading_stop_review)
    if event=='candidate':new=intake.receive_candidate(s,s.candidate,request_sha256=s.request_sha256)
    elif event=='materials':new=intake.revise_materials(s,s.case,reason='New user material needs fresh reading')
    elif event=='fact_format':new=intake.configure_fact_format(s,'source_hash')
    elif event=='fact_contract':new=intake.configure_network_fact_contract(s,'network-source-selections-information-1')
    else:
        sheet=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
        new=prepare_recheck(s,feedback=feedback(sheet),authority='SYNTHETIC_TEST')
    assert new.reading_stop_review is None and new.history[-1]['previous_stop_review']==record_before


def test_clarification_reply_is_original_source_not_review_evidence():
    s=reviewed(uncertain());plan=intake.clarification_plan(s);new=intake.append_reply(s,plan,plan['questions'][0]['clarification_id'],'现在确定只求甲店准时开门的概率。')
    assert new.reading_stop_review is None and new.candidate is None
    assert new.case.sources[-1].text=='现在确定只求甲店准时开门的概率。'
    req=intake.prepare_request(new)
    assert 'Independent synthetic source reviewer' not in req['user_prompt']
    assert 'SOURCE_CONFIRMED_TARGET_GAP' not in req['user_prompt']
    assert intake.inspect(new)['state']=='READING_REQUIRED'


def test_change_review_cannot_be_skipped_and_stale_record_fails_closed():
    s=uncertain();sheet=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    new=prepare_recheck(s,feedback=feedback(sheet),authority='SYNTHETIC_TEST')
    raw=deepcopy(s.candidate);raw['queries'][0]['goal']['value']+=' 需确认。'
    fresh=intake.receive_candidate(new,raw,request_sha256=new.request_sha256)
    with pytest.raises(ValueError):prepare_review(fresh,authority='SYNTHETIC_TEST')
    w=intake.inspect(fresh)['reading_change_worksheet'];accepted=review_changes(fresh,accept_changes(w));stopped=reviewed(accepted)
    changed=review_changes(stopped,accept_changes(w))
    assert changed.reading_stop_review is None and changed.history[-1]['previous_stop_review']==stopped.reading_stop_review
    tampered=stopped.model_dump(mode='json');tampered['candidate']['queries'][0]['goal']['value']+=' different'
    assert intake.inspect(tampered)['state'] in ('REVIEW_REQUIRED','CHECK_BLOCKED')
    other=uncertain();forged=other.model_copy(update={'reading_stop_review':deepcopy(stopped.reading_stop_review)})
    assert intake.inspect(forged)['state']=='CHECK_BLOCKED' and dispatch.prepare_reader(forged,'q1')['request'] is None


def test_unblocked_and_canonical_inputs_do_not_gain_review_or_change_prompt():
    b,raw=fixture();s=receive(b,raw);before=s.model_dump(mode='json')
    assert 'reading_stop_review' not in before
    assert intake.BusinessIntake.model_validate(before).model_dump(mode='json')==before
    with pytest.raises(ValueError,match='NO_CURRENT'):prepare_review(s)
    canonical=intake.start(b,reading_format='canonical')
    with pytest.raises(ValueError):prepare_review(canonical)
    empty=intake.start(b)
    with pytest.raises(ValueError):prepare_review(empty)


def test_cli_worksheet_review_and_stop_are_offline(tmp_path):
    from cfm_id.business_intake_cli import main
    s=uncertain();input_path=tmp_path/'input.json';intake.save(s,input_path)
    sheet_path=tmp_path/'sheet.json';out=tmp_path/'reviewed.json';review_path=tmp_path/'review.json'
    args=['review-stop','--intake',str(input_path),'--authority','SYNTHETIC_TEST']
    assert main([*args,'--output',str(sheet_path)])==0
    intake.write_json(review_path,record(intake.read_json(sheet_path)['stop_worksheet']))
    assert main([*args,'--review',str(review_path),'--output',str(out)])==0
    assert dispatch.prepare_reader(intake.restore(out),'q1')['state']=='NEEDS_INPUT'
