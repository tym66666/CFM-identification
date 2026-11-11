"""Synthetic end-to-end protocol tests; no claim of live model/human review."""
from copy import deepcopy
import pytest
from cfm_id import project, business_intake as intake, business_dispatch as dispatch
from cfm_id import business_field_review, fact_source_review
from cfm_id.iv_route_contract import IVReview, IVProblem, SCIENCE_DECISIONS, digest
from cfm_id.iv_business_dispatch import METHOD
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.iv_fact_reading import reference_catalog
from examples.iv_business_materials import case

META = dict(authority='SYNTHETIC_TEST', reviewer='Synthetic fixture reviewer',
            evidence='Synthetic test declarations only; no real scientific approval or model call.')


def field_record(sheet):
    return dict(binding_sha256=sheet['binding_sha256'], **META,
        decisions={p: dict(field_role='ACCEPTED', value_state='ACCEPTED', source_coverage='ACCEPTED',
            reason='Synthetic fixture checked against declared material; not a human review.',
            source_ids=list(sheet['source_catalog'])) for p in sheet['fields']})


def prepared(case_id='A'):
    s = project.start(case(case_id))
    request = intake.prepare_request(s)
    payload = split_user(request['user_prompt'])[1]
    refs = [r['ref'] for r in payload['source_catalog']]
    def claim(value): return dict(state='STATED', value=value, refs=refs)
    kind = 'ATE' if case_id == 'B' else 'LATE'
    raw = dict(reference_context=payload['reference_context'], common=dict(
        analysis_unit=claim('报名者'), treatment=claim('实际参加培训'), outcome=claim('三个月内就业'),
        assignment_family='UNRESOLVED', assignment_law='UNKNOWN', unit_network='UNKNOWN',
        variable_causal_graph='UNKNOWN'), queries=[dict(goal=claim(s.case.business_question), kind=kind,
        comparison_order=dict(operation='FIRST_MINUS_SECOND',refs=refs), semantics=dict(
            target_population=claim('全部报名者' if kind=='ATE' else '因获得资格才参加者'),
            first_arrangement=claim('参加培训'), second_arrangement=claim('不参加培训'),
            outcome=claim('就业'), aggregation=claim('等权平均'), time_horizon=claim('三个月'),
            conditioning_context='UNKNOWN', decision_constraints='UNKNOWN',
            standardization_distribution='UNKNOWN', neighbor_exposure='UNKNOWN'))])
    s = intake.receive_candidate(s, raw, request_sha256=request['request_sha256'])
    report = intake.inspect(s)
    assert 'report' in report, report
    w = business_field_review.prepare(s,'q1',authority='SYNTHETIC_TEST')['field_worksheet']
    qr = business_field_review.submit(s,'q1',field_record(w),authority='SYNTHETIC_TEST')['query_review']
    entry = dispatch.prepare_reader(s,'q1',query_review=qr)
    assert entry['state']=='READY_TO_READ',entry
    references=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    ids=list(references['aliases'])
    statement=lambda text:dict(state='STATED',text=text,source_ids=ids)
    values = [1,0,0,0,.5,0,0,.5] if case_id!='D' else [.3,.3,.3,.1,.35,.05,.15,.45]
    facts=dict(version='binary-iv-facts-1',reference_context=references['context'],
        target=dict(kind=kind,direction='Y1_MINUS_Y0',population='报名总体',context='三个月观察期',source_ids=ids),
        instrument=statement('资格Z:0未获得,1获得'),treatment=statement('参加D:0未参加,1参加'),
        outcome=statement('就业Y:0未就业,1就业'),monotonicity='IMPOSED',monotonicity_source_ids=ids,
        information=dict(kind='POPULATION_CONDITIONAL_LAW',source_ids=ids,cells=[
            dict(z=z,d=d,y=y,probability=str(values[z*4+d*2+y]),source_ids=ids)
            for z in (0,1) for d in (0,1) for y in (0,1)]),
        assumptions={k:statement(k) for k in SCIENCE_DECISIONS},additional_restrictions=[],unresolved=[])
    if case_id=='C':facts['assumptions']['exclusion_restriction']=dict(state='UNKNOWN',text='未确定',source_ids=ids)
    opts=dict(query_review=qr,candidate=facts,request_sha256=entry['request_sha256'])
    opts['source_review']=field_record(fact_source_review.prepare(entry,facts))
    return s,entry,opts


def approvals(plan):
    row=plan['methods'][0];w=row['native_worksheet'];h=w['problem_sha256']
    record=dict(version='binary-iv-research-1',problem_sha256=h,
        reading_review=dict(**META,problem_sha256=h,decisions={k:'ACCEPTED' for k in w['reading_decisions']}),
        science_review=dict(**META,problem_sha256=h,decisions={k:'ACCEPTED' for k in w['science_decisions']}))
    return dict(plan_review=dict(**META,binding_sha256=plan['plan_worksheet']['binding_sha256'],
        decisions={k:'ACCEPTED' for k in plan['plan_worksheet']['decisions']}),
        native_reviews={METHOD:IVReview.model_validate(record)},research_protocol_selected=True)


@pytest.mark.parametrize('case_id,expected',[('A','POINT'),('B','PARTIAL'),('C','NEEDS_INPUT'),('D','INCOMPATIBLE')])
def test_recommended_intake_to_reviewed_iv(case_id,expected):
    s,e,opts=prepared(case_id)
    assert 'name: causal-business-reading' in intake.prepare_request(s)['system_prompt']
    plan=dispatch.inspect_methods(s,'q1',**opts)
    if case_id=='C':
        assert plan['state']==expected and not plan['backend_called'];return
    assert plan['state']=='REVIEW_REQUIRED',plan
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**opts,**approvals(plan))
    assert result['state']==expected,result
    assert result['independent_replay']
    if case_id=='A':assert result['mathematical_claim']['value']==1
    if case_id=='B':assert result['mathematical_claim']['interval']==pytest.approx([.5,1])


def test_missing_source_science_and_changed_input_cannot_reuse_approval():
    s,e,opts=prepared('B')
    bare={k:v for k,v in opts.items() if k!='source_review'}
    assert dispatch.inspect_methods(s,'q1',**bare)['reason_code']=='IV_SOURCE_REVIEW_REQUIRED'
    plan=dispatch.inspect_methods(s,'q1',**opts);approval=approvals(plan)
    approval['native_reviews'][METHOD].science_review.decisions['monotonicity_direction']='PENDING'
    result=dispatch.execute(s,'q1',**opts,**approval)
    assert result['state']=='REVIEW_REQUIRED' and not result['backend_called']
    changed=deepcopy(opts);changed['candidate']['target']['population']='不同总体'
    result=dispatch.execute(s,'q1',**changed,**approvals(plan))
    assert result['state']=='CHECK_BLOCKED' and not result['backend_called']


def test_extra_restrictions_sample_law_and_target_switch_stop():
    s,e,opts=prepared('A')
    for change,expected in [('sample','NEEDS_INPUT'),('target','READING_RECHECK_REQUIRED'),('extra','ADAPTER_NOT_CONNECTED')]:
        option=deepcopy(opts);c=option['candidate']
        if change=='sample':c['information']['kind']='FINITE_SAMPLE'
        if change=='target':c['target']['kind']='ATE'
        if change=='extra':c['additional_restrictions']=[deepcopy(c['instrument'])]
        option['source_review']=field_record(fact_source_review.prepare(e,c))
        result=dispatch.inspect_methods(s,'q1',**option)
        assert result['state']==expected and not result['backend_called']


def test_fact_recheck_uses_registered_request_and_preserves_original():
    from cfm_id.fact_reading_revision import prepare_recheck
    s,e,opts=prepared('A')
    before=deepcopy(opts['candidate'])
    plan=prepare_recheck(s,'q1',query_review=opts['query_review'],candidate=before,
        request_sha256=e['request_sha256'])
    assert plan['state']=='REVIEW_REQUIRED'
    assert before==opts['candidate']


@pytest.mark.parametrize('field',['conditioning_context','standardization_distribution'])
def test_conditioned_or_standardized_iv_target_is_not_silently_dropped(field):
    s,_,_=prepared('A')
    raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics'][field]=deepcopy(raw['queries'][0]['semantics']['time_horizon'])
    s=intake.receive_candidate(s,raw,request_sha256=intake.prepare_request(s)['request_sha256'])
    w=business_field_review.prepare(s,'q1',authority='SYNTHETIC_TEST')['field_worksheet']
    qr=business_field_review.submit(s,'q1',field_record(w),authority='SYNTHETIC_TEST')['query_review']
    entry=dispatch.prepare_reader(s,'q1',query_review=qr)
    assert entry['state']=='ADAPTER_NOT_CONNECTED',entry
    assert entry['request'] is None and not entry['backend_called']


@pytest.mark.parametrize('content,exit_code',[('{"synthetic":true}',0),('{bad json',2)])
def test_model_call_records_raw_response_without_fabricating_review(tmp_path,monkeypatch,content,exit_code):
    """Fake transport only; these temporary records are not live acceptance evidence."""
    import json
    import sys
    from examples import iv_model_call as runner
    from tests_gateway.test_final_content_observer import Response
    provider_type=runner.FinalContentObservedChatProvider
    calls=[]
    def transport(request,*,timeout):
        calls.append(json.loads(request.data))
        return Response(dict(choices=[dict(finish_reason='stop',message=dict(content=content))]))
    monkeypatch.setattr(runner,'FinalContentObservedChatProvider',
        lambda **kwargs:provider_type(**kwargs,transport=transport))
    monkeypatch.setenv('IV_SYNTHETIC_TEST_KEY','not-a-real-credential')
    config=tmp_path/'config.json';request=tmp_path/'request.json';out=tmp_path/'record'
    config.write_text(json.dumps(dict(model='synthetic-test',base_url='https://example.invalid/v1',
        api_key_env='IV_SYNTHETIC_TEST_KEY')),encoding='utf-8')
    request.write_text(json.dumps(dict(system_prompt='Synthetic test',user_prompt='No real business')),
        encoding='utf-8')
    args=['--request',str(request),'--config',str(config),'--output',str(out),'--stage','a0-first']
    with pytest.raises(SystemExit):runner.main(args)
    assert not calls and not out.exists()
    assert runner.main([*args,'--allow-model-call'])==exit_code
    assert len(calls)==1 and (out/'model_final_text.txt').read_text(encoding='utf-8')==content
    record=json.loads((out/'run.json').read_text(encoding='utf-8'))
    assert record['command']==sys.orig_argv
    assert record['human_review']=='NOT_PERFORMED' and record['transport_calls']==1
    assert record['exit_code']==exit_code and not record['automatic_retry']
    assert (out/'model_candidate.json').exists()==(exit_code==0)
    with pytest.raises(FileExistsError):runner.main([*args,'--allow-model-call'])
    assert len(calls)==1
