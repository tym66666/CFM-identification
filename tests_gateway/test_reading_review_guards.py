"""Bounded source rereads and exact change gates; not a semantic classifier."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from cfm_id.intake_reading_revision import prepare_recheck,review_changes,MAX_ROUNDS
from cfm_id.fact_reading_revision import prepare_recheck as fact_recheck
from cfm_id.reading_change_review import changes
from tests_gateway.test_business_intake_compact import scenario,receive
from tests_gateway.test_fact_reading_revision import feedback as fact_feedback,accept_changes
from examples.business_dispatch_reference import approve


def feedback(sheet):
    return dict(version='intake-reading-feedback-1',binding_sha256=sheet['binding_sha256'],
        authority=sheet['expected_authority'],reviewer='Private reviewer',evidence='PRIVATE_EVIDENCE_STAYS_LOCAL',
        issues=[dict(field_path='',kind='OMITTED_OR_MISREAD',source_ids=list(sheet['source_catalog']),reason='PRIVATE_REASON_STAYS_LOCAL and is never a replacement answer.')])


def corrected():
    case,raw,_=scenario();bad=deepcopy(raw);bad['queries'][0]['semantics']['time_horizon']['value']='五十年后'
    s=receive(case,bad);w=prepare_recheck(s,authority='SYNTHETIC_TEST');next_s=prepare_recheck(s,feedback=feedback(w['feedback_worksheet']),authority='SYNTHETIC_TEST')
    return s,next_s,intake.receive_candidate(next_s,raw,request_sha256=next_s.request_sha256)


def test_a0_source_reread_keeps_history_and_no_private_feedback_or_science():
    s,next_s,fresh=corrected();request=intake.prepare_request(next_s)
    assert next_s.case==s.case and next_s.candidate is None
    assert next_s.reading_revision['steps'][0]['candidate']==s.candidate
    assert next_s.request_sha256!=s.request_sha256 and request['reading_revision_sha256']
    assert all(x not in request['system_prompt']+request['user_prompt'] for x in ('PRIVATE_REASON_STAYS_LOCAL','PRIVATE_EVIDENCE_STAYS_LOCAL','Private reviewer'))
    assert 'A0_RECHECK_CONTEXT_NOT_EVIDENCE' in request['user_prompt']
    assert intake.inspect(fresh)['state']=='REVIEW_REQUIRED'
    assert not intake.inspect(fresh)['core_called']
    with pytest.raises(intake.IntakeError,match='STALE'):intake.receive_candidate(next_s,s.candidate,request_sha256=s.request_sha256)


def test_changed_a0_cannot_enter_query_or_whole_case_before_source_review(tmp_path):
    s,next_s,fresh=corrected();old=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    assert dispatch.prepare_reader(fresh,'q1',query_review=old)['state']=='REVIEW_REQUIRED'
    assert business_case.prepare_case(fresh)['case_worksheet'] is None
    pending=intake.inspect(fresh);sheet=pending['reading_change_worksheet']
    accepted=review_changes(fresh,accept_changes(sheet))
    assert intake.prepare_request(accepted)==intake.prepare_request(fresh)
    assert intake.inspect(accepted)['state']=='SEMANTIC_REVIEW_REQUIRED'
    assert dispatch.prepare_reader(accepted,'q1',query_review=old)['state']=='CHECK_BLOCKED'
    assert dispatch.prepare_reader(accepted,'q1')['state']=='REVIEW_REQUIRED'
    assert not intake.inspect(accepted)['reading_change_receipt']['scientific_approval']
    intake.save(accepted,tmp_path/'rechecked.json');assert intake.restore(tmp_path/'rechecked.json')==accepted
    rejected=accept_changes(sheet)
    for item in rejected['decisions'].values():item['disposition']='REJECTED'
    stopped=review_changes(fresh,rejected)
    assert intake.inspect(stopped)['state']=='READING_RECHECK_REQUIRED'
    assert business_case.execute_case(stopped,{},research_protocol_selected=True)['state']=='READING_RECHECK_REQUIRED'


@pytest.mark.parametrize('bad',['binding','source','path','authority','extra','blank'])
def test_a0_invalid_feedback_is_not_a_request(bad):
    case,raw,_=scenario();s=receive(case,raw);w=prepare_recheck(s,authority='SYNTHETIC_TEST');f=feedback(w['feedback_worksheet'])
    if bad=='binding':f['binding_sha256']='0'*64
    elif bad=='source':f['issues'][0]['source_ids']=['not a source']
    elif bad=='path':f['issues'][0]['field_path']='/invented'
    elif bad=='authority':f['authority']='EXTERNAL_RESEARCH_REVIEW'
    elif bad=='extra':f['expected_value']='POINT'
    else:f['evidence']=' '*20
    with pytest.raises(ValueError):prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST')


@pytest.mark.parametrize('bad',['candidate','feedback','request','source','prompt'])
def test_a0_history_cannot_be_rebound(bad,monkeypatch):
    s,next_s,fresh=corrected();raw=fresh.model_dump(mode='json')
    if bad=='candidate':raw['reading_revision']['steps'][0]['candidate']['queries'][0]['goal']['value']='different'
    elif bad=='feedback':raw['reading_revision']['steps'][0]['feedback']['issues'][0]['reason']+='changed'
    elif bad=='request':raw['reading_revision']['steps'][0]['request_sha256']='0'*64
    elif bad=='source':raw['case']['business_question']+=' New text.'
    else:
        from cfm_id_llm import compact_formulator
        monkeypatch.setattr(compact_formulator,'COMPACT_SYSTEM_PROMPT',compact_formulator.COMPACT_SYSTEM_PROMPT+' changed')
    with pytest.raises(ValueError):intake.inspect(raw)


def test_ordinary_checkpoint_wire_and_hash_unchanged_and_material_revision_clears_reread():
    case,raw,_=scenario();s=receive(case,raw);payload=s.model_dump(mode='json')
    assert 'reading_revision' not in payload and 'reading_change_review' not in payload
    assert intake._sha(payload)==intake._sha(intake.BusinessIntake.model_validate(payload).model_dump(mode='json'))
    s,next_s,fresh=corrected();new=intake.revise_materials(fresh,fresh.case,reason='User supplied new material')
    assert new.reading_revision is None and new.reading_change_review is None and new.candidate is None
    assert new.history[-1]['previous_reading_revision']==fresh.reading_revision
    assert intake.inspect(new)['state']=='READING_REQUIRED'


def test_a0_round_limit_and_empty_candidate_and_canonical_scope():
    case,raw,_=scenario();s=receive(case,{})
    for i in range(MAX_ROUNDS):
        w=prepare_recheck(s,authority='SYNTHETIC_TEST')
        s=prepare_recheck(s,feedback=feedback(w['feedback_worksheet']),authority='SYNTHETIC_TEST')
        s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
        assert len(s.reading_revision['steps'])==i+1
    with pytest.raises(ValueError,match='ROUND_LIMIT'):prepare_recheck(s)
    canonical=intake.start(case,reading_format='canonical');canonical=intake.receive_candidate(canonical,{},request_sha256=canonical.request_sha256)
    with pytest.raises(ValueError,match='COMPACT_FORMAT'):prepare_recheck(canonical)


def test_pending_change_review_can_be_revised_with_history_and_stale_approvals_rejected():
    s,_,fresh=corrected();sheet=intake.inspect(fresh)['reading_change_worksheet'];r=accept_changes(sheet)
    pending=deepcopy(r)
    for d in pending['decisions'].values():d['disposition']='PENDING'
    first=review_changes(fresh,pending)
    assert intake.inspect(first)['state']=='REVIEW_REQUIRED'
    accepted=review_changes(first,r)
    assert accepted.history[-1]['previous_change_review']==pending
    old=approve(dispatch.prepare_reader(accepted,'q1')['query_worksheet'])
    changed=deepcopy(r);changed['evidence']+=' Another independent source review.'
    updated=review_changes(accepted,changed)
    assert intake.prepare_request(updated)==intake.prepare_request(fresh)
    assert dispatch.prepare_reader(updated,'q1',query_review=old)['state']=='CHECK_BLOCKED'
    with pytest.raises(ValueError,match='REQUIRED'):review_changes(updated,None)


@pytest.mark.parametrize('bad',['binding','source','missing_decision','authority','candidate','private_reason'])
def test_changed_candidate_requires_exact_review(bad):
    s,next_s,fresh=corrected();sheet=intake.inspect(fresh)['reading_change_worksheet'];r=accept_changes(sheet)
    if bad=='binding':r['binding_sha256']='0'*64
    elif bad=='source':next(iter(r['decisions'].values()))['source_ids']=['invented']
    elif bad=='missing_decision':r['decisions']={}
    elif bad=='authority':r['authority']='EXTERNAL_RESEARCH_REVIEW'
    elif bad=='private_reason':next(iter(r['decisions'].values()))['reason']=' '*20
    else:
        changed=deepcopy(fresh.candidate);changed['queries'][0]['semantics']['time_horizon']['value']='另一时期'
        fresh=intake.receive_candidate(fresh,changed,request_sha256=fresh.request_sha256)
    with pytest.raises(ValueError):review_changes(fresh,r)


def test_change_gate_sees_untargeted_model_flag_and_blocks_even_if_extra_text_remains():
    from examples.network_bounded_dispatch_reference import setup,reference
    s,e,o,p=setup(extra=True);old=deepcopy(o['candidate']);old['bounded_model']['no_additional_coupling_constraints']['value']=False
    args=dict(o,candidate=old);w=fact_recheck(s,'q1',**args)['feedback_worksheet']
    e2=fact_recheck(s,'q1',**args,feedback=fact_feedback(w,path='/additional_restrictions',kind='POSSIBLE_DUPLICATION',doc='extra'))
    new=reference(e2,extra=True);new['bounded_model']['no_additional_coupling_constraints']['value']=True
    opts=dict(query_review=o['query_review'],candidate=new,request_sha256=e2['request_sha256'],reading_revision=e2['reading_revision'])
    pending=dispatch.execute(s,'q1',**opts,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called'] and 'plan_worksheet' not in pending
    sheet=pending['reading_change_worksheet'];assert any(v['field_path'].endswith('/no_additional_coupling_constraints/value') for v in sheet['changes'].values())
    r=accept_changes(sheet)
    for key,v in sheet['changes'].items():
        if v['field_path'].endswith('/no_additional_coupling_constraints/value'):r['decisions'][key]['disposition']='REJECTED'
    rejected=dispatch.execute(s,'q1',**opts,change_review=r,research_protocol_selected=True)
    assert rejected['state']=='READING_RECHECK_REQUIRED' and not rejected['backend_called'] and not rejected['answers']
    assert rejected['reading_candidate']==new and new['additional_restrictions']
    case_review=approve(business_case.prepare_case(s)['case_worksheet'])
    whole=business_case.execute_case(s,{'q1':dict(opts,change_review=r)},case_review=case_review,research_protocol_selected=True)
    assert whole['results'][0]['result']['state']=='READING_RECHECK_REQUIRED' and not whole['backend_called']


def test_diff_keeps_false_zero_null_removal_and_does_not_interpret_equivalence():
    assert changes({'a':[False]},{'a':[0]})['d0001']['field_path']=='/a/0'
    delta=changes({'a':False,'b':None,'c':['1/2']},{'a':0,'c':['0.5'],'reference_context':'new'})
    assert {v['field_path'] for v in delta.values()}=={'/a','/b','/c/0'}
    assert delta['d0002']['before_present'] and not delta['d0002']['after_present']


def test_cli_can_recheck_and_reject_new_candidate_without_any_provider(tmp_path):
    from cfm_id.business_intake_cli import main
    s,next_s,fresh=corrected();intake.save(s,tmp_path/'old.json')
    args=['recheck','--intake',str(tmp_path/'old.json'),'--authority','SYNTHETIC_TEST']
    assert main([*args,'--output',str(tmp_path/'sheet.json')])==0
    f=feedback(intake.read_json(tmp_path/'sheet.json')['feedback_worksheet']);intake.write_json(tmp_path/'feedback.json',f)
    assert main([*args,'--feedback',str(tmp_path/'feedback.json'),'--output',str(tmp_path/'next.json')])==0
    next_s=intake.restore(tmp_path/'next.json');received=intake.receive_candidate(next_s,fresh.candidate,request_sha256=next_s.request_sha256)
    intake.save(received,tmp_path/'received.json');sheet=intake.inspect(received)['reading_change_worksheet'];r=accept_changes(sheet)
    for d in r['decisions'].values():d['disposition']='REJECTED'
    intake.write_json(tmp_path/'review.json',r)
    assert main(['review-changes','--intake',str(tmp_path/'received.json'),'--review',str(tmp_path/'review.json'),'--output',str(tmp_path/'stopped.json')])==0
    assert intake.inspect(intake.restore(tmp_path/'stopped.json'))['state']=='READING_RECHECK_REQUIRED'
