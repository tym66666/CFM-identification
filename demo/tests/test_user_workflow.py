"""User workflow contracts using explicit model fixtures, not model accuracy scores."""
from copy import deepcopy
import json
import pytest
from test_live_demo import reading_fixture,fixture_review
from demo.backend import automatic_review as audit,recovery

PASS={'verdict':'PASS','scientific_approval':False,'issues':[]}


def automatic_fixture(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch)
    fact_reply=engine.call;calls=[]
    def reply(run,request,stage):
        calls.append(stage)
        return {'scientific_approval':False,'findings':[]} if stage.startswith('reading_audit_') else fact_reply(run,request,stage)
    monkeypatch.setattr(engine,'call',reply)
    run.automatic_review=True
    return engine,run,calls


def test_background_reading_stops_for_explicit_science_then_point_replay(tmp_path,monkeypatch):
    engine,run,calls=automatic_fixture(tmp_path,monkeypatch)
    engine._continue_automatically(run)
    assert run.review_kind=='science' and run.result is None and not run.reviews
    assert calls==['reading_audit_1','facts','reading_audit_1']  # mocked call has no artifact writer
    assert run.query_review['reviewer']=='Independent LLM reading audit'
    assert '不是人工审核' in run.query_review['evidence']
    engine._review(run,fixture_review(run))
    assert run.result['state']=='POINT' and run.result['independent_replay']


def test_unclear_reading_asks_a_short_question_without_fact_or_core_call(tmp_path,monkeypatch):
    engine,run,calls=automatic_fixture(tmp_path,monkeypatch)
    def reply(run,request,stage):
        payload=json.loads(request['user_prompt'])
        return dict(scientific_approval=False,findings=[dict(kind='NEEDS_CLARIFICATION',
            field=next(iter(payload['fields'])),reason='评价名单在两处材料中没有保持一致',
            question='本次评价全部门店，还是仅评价名单中的两家？',source_ids=[next(iter(payload['source_catalog']))])])
    monkeypatch.setattr(engine,'call',reply)
    engine._continue_automatically(run)
    assert run.submission is None and run.result is None and not run.query_review
    assert run.user_question['items'][0]['question'].startswith('本次评价')


@pytest.mark.parametrize('answer',[
    {'verdict':'PASS','scientific_approval':True,'issues':[]},
    {'verdict':'PASS','scientific_approval':False,'issues':[{}]},
    {'verdict':'READING_ERROR','scientific_approval':False,'issues':[]},
])
def test_auditor_cannot_approve_science_or_submit_inconsistent_result(answer):
    with pytest.raises(ValueError):audit.check(answer,{}, {})


def test_recheck_preserves_old_answer_invalidates_reviews_and_audits_changes(tmp_path,monkeypatch):
    engine,run,calls=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    candidate=run.submission['candidate']
    candidate['additional_restrictions']=[dict(text='这项科学条件仍待审核。',
        source_ids=candidate['scientific_statements']['consistency']['source_ids'])]
    engine._plan(run)
    original=deepcopy(run.submission)
    preview=recovery.prepare(run)
    assert preview['available'] and preview['items'][0]['quotes']
    with pytest.raises(ValueError,match='STALE'):recovery.request(run,'0'*64)
    entry,feedback=recovery.request(run,preview['binding_sha256'])
    run.reviews={'old':'must not survive'}
    engine._recheck(run,entry,feedback)
    assert run.artifacts['facts_before_recheck_1']==original
    assert not run.reviews and run.result is None and run.review_kind=='changes'
    engine._continue_automatically(run)
    assert run.review_kind=='science' and run.result is None
    engine._review(run,fixture_review(run))
    assert run.result['state']=='POINT' and run.result['independent_replay']


def test_unknown_science_never_promoted_by_reading_auditor(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch,missing=True)
    facts=engine.call
    monkeypatch.setattr(engine,'call',lambda run,request,stage:{'scientific_approval':False,'findings':[]} if stage.startswith('reading_audit_') else facts(run,request,stage))
    run.automatic_review=True;engine._continue_automatically(run)
    assert run.result['state']=='NEEDS_INPUT'
    assert not run.result.get('independent_replay') and not run.reviews


def test_reviewer_does_not_overwrite_rejection(tmp_path,monkeypatch):
    engine,run,calls=automatic_fixture(tmp_path,monkeypatch)
    decision=next(iter(run.review_templates['query']['decisions'].values()))
    decision['value_state']='REJECTED'
    with pytest.raises(ValueError,match='OVERRIDE_REJECTION'):audit.records(run,PASS)
    assert decision['value_state']=='REJECTED'


def test_automatic_science_records_are_forbidden(tmp_path,monkeypatch):
    engine,run,calls=automatic_fixture(tmp_path,monkeypatch)
    engine._continue_automatically(run)
    with pytest.raises(ValueError,match='SCIENCE_APPROVAL'):audit.records(run,PASS)
    with pytest.raises(ValueError,match='SCIENCE_APPROVAL'):audit.request(run)


def test_answer_creates_new_material_and_discards_old_approvals(tmp_path,monkeypatch):
    engine,run,calls=automatic_fixture(tmp_path,monkeypatch)
    before=deepcopy(run.case);run.reviews={'old':'approval'}
    seen=[]
    monkeypatch.setattr(engine,'_read_case',lambda r:seen.append(deepcopy(r.case)))
    engine._clarify(run,'本次只评价甲乙两家门店。')
    assert len(seen)==1 and seen[0]['sources'][-1]['text']=='本次只评价甲乙两家门店。'
    assert run.artifacts['input_revision_1']['case']==before
    assert not run.reviews and run.intake is None and run.submission is None and run.result is None


def test_real_additional_restriction_does_not_trigger_a_blind_reread(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch)
    original=engine.call;facts=[]
    def reply(run,request,stage):
        if stage.startswith('reading_audit_'):return {'scientific_approval':False,'findings':[]}
        raw=original(run,request,stage)
        raw['additional_restrictions']=[dict(text='额外要求全部对象的总体均值相等。',
            source_ids=raw['scientific_statements']['consistency']['source_ids'])]
        facts.append(raw);return raw
    monkeypatch.setattr(engine,'call',reply);run.automatic_review=True
    engine._continue_automatically(run)
    assert len(facts)==1 and run.automatic_rechecks==0
    assert run.submission['candidate']['additional_restrictions']
    assert not run.reviews and run.result['state']!='POINT'


def test_audit_uses_existing_source_ids_and_public_field_contract(tmp_path,monkeypatch):
    engine,run,calls=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    request,fields,sources=audit.request(run);payload=json.loads(request['user_prompt'])
    refs=run.submission['candidate']['scientific_statements']['consistency']['source_ids']
    assert all(ref in sources for ref in refs)
    assert 'field_contract' in payload and payload['output_schema']['properties']['scientific_approval']=={'const':False}
def test_terminal_query_gate_does_not_loop_audit_or_call_facts(tmp_path,monkeypatch):
    from demo.backend.engine import Engine,Run
    engine=Engine(tmp_path/'runs');run=Run(owner='test',automatic_review=True,review_kind='query')
    run.result={'state':'ADAPTER_NOT_CONNECTED','reason_code':'TARGET_CONTEXT_NOT_CONNECTED'}
    def forbidden(*args,**kwargs):raise AssertionError('A final gate must not call the model again')
    monkeypatch.setattr(engine,'call',forbidden)
    engine._continue_automatically(run)
    assert run.result['state']=='ADAPTER_NOT_CONNECTED' and run.submission is None


@pytest.mark.parametrize('fixed', [True, False])
def test_source_audit_locates_one_reread_before_scientific_review(tmp_path,monkeypatch,fixed):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    run.submission['candidate']['unresolved']=[dict(text='模型误将明确的一致性条件记录为未决定。',
        source_ids=run.submission['candidate']['scientific_statements']['consistency']['source_ids'])]
    engine._plan(run)
    original=deepcopy(run.submission);fact_reply=engine.call;calls=[]
    path='source:/unresolved/0';reason='原文已经声明该条件，候选却又把同一条件记为未决定。'
    def reply(current,request,stage):
        calls.append(stage)
        if stage.startswith('reading_audit_') or stage.startswith('focused_audit'):
            body=json.loads(request['user_prompt'])
            if path not in body['fields']:
                return {'scientific_approval':False,'findings':[]}
            refs=current.submission['candidate']['unresolved'][0]['source_ids']
            if stage.startswith('focused_audit'):
                return dict(scientific_approval=False,assessments=[dict(field=path,source_ids=refs,
                    comparison=reason,matches_source=False,question=None)])
            return dict(scientific_approval=False,findings=[dict(kind='READING_ERROR',field=path,
                reason=reason,question=None,source_ids=refs)])
        # The production recheck includes precise source/field locations and
        # public definitions, never private audit reasons or replacement values.
        assert '/unresolved/0' in request['request']['user']
        assert reason not in request['request']['user']
        raw=fact_reply(current,request,stage)
        if not fixed:raw['unresolved']=deepcopy(original['candidate']['unresolved'])
        return raw
    monkeypatch.setattr(engine,'call',reply)
    engine._continue_automatically(run)
    assert calls[:3]==['reading_audit_1','focused_audit','facts']
    assert calls.count('facts')==1 and run.automatic_rechecks==1
    assert run.artifacts['facts_before_recheck_1']==original
    assert run.result is None and not run.reviews
    if fixed:
        assert run.review_kind=='science' and run.error is None
        engine._review(run,fixture_review(run))
        assert run.result['state']=='POINT' and run.result['independent_replay']
    else:
        assert run.error['code']=='READING_REVIEW_DISAGREEMENT' and run.user_question is None


@pytest.mark.parametrize('issue', [
    dict(kind='NEEDS_CLARIFICATION',field='source:/unresolved/0',source_ids=['unused']),
    dict(kind='READING_ERROR',field='source:/missing',source_ids=['unused']),
    dict(kind='READING_ERROR',field='source:/unresolved/0',source_ids=['fabricated']),
    dict(kind='READING_ERROR',field='query:/unresolved/0',source_ids=['unused']),
])
def test_recovery_cannot_guess_audit_field_or_source_or_rewrite_unknown(tmp_path,monkeypatch,issue):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    run.submission['candidate']['unresolved']=[dict(text='此项条件尚未决定。',
        source_ids=run.submission['candidate']['scientific_statements']['consistency']['source_ids'])]
    engine._plan(run);original=deepcopy(run.submission)
    finding={**issue,'reason':'必须保留原文中尚未决定的条件，不能默认批准。'}
    assert not recovery.prepare(run,allow_busy=True,audit_findings=[finding])['available']
    assert run.submission==original and not run.reviews
