"""A bounded protocol retry, never semantic repair or approval."""
from copy import deepcopy
import json
import pytest
from demo.backend.engine import Engine,Run
from reference import fixture,a0_candidate

@pytest.mark.parametrize('second_valid',[True,False])
@pytest.mark.parametrize('problem',['wire_type','canonical_pair'])
def test_one_schema_retry_keeps_original_and_still_requires_review(tmp_path,monkeypatch,second_valid,problem):
    case,info=fixture();engine=Engine(tmp_path/'runs')
    run=Run(owner='test',case=case.model_dump(mode='json'),automatic_review=True,synthetic=True)
    original=deepcopy(run.case);calls=[]
    def reply(run,request,stage):
        calls.append(stage);good=a0_candidate(run.intake,info)
        if stage=='a0' or not second_valid:
            if problem=='wire_type':
                good['common']['assignment_family']={'value':'INDEPENDENT_BERNOULLI','state':'STATED','refs':[]}
            else:
                # An observational regime may legitimately have an unknown assignment law.
                # A specified randomized design still needs its original-law statement.
                good['common']['assignment_family']='COMPLETE_RANDOMIZATION'
                good['common']['assignment_law']='UNKNOWN'
        if stage=='a0_format_retry':
            body=json.loads(request['user_prompt'].split('本次格式检查反馈（不是新的业务材料）：\n')[1])
            path=['common','assignment_family'] if problem=='wire_type' else ['shared_draft','information_design']
            assert path in [x['path'] for x in body['diagnostics']['issues']]
            assert body['previous_response']==run.artifacts['a0_candidate']
        engine.save(run,stage+'_candidate',good)
        return good
    monkeypatch.setattr(engine,'call',reply);engine._read_case(run)
    assert calls==['a0','a0_format_retry'] and run.automatic_a0_format_repairs==1
    assert run.case==original and not run.reviews and run.submission is None
    reason='COMPACT_SCHEMA_REJECTED' if problem=='wire_type' else 'A0_SCHEMA_REJECTED'
    assert run.artifacts['a0_initial_inspection']['reason_code']==reason
    if problem=='wire_type':assert isinstance(run.artifacts['a0_candidate']['common']['assignment_family'],dict)
    else:assert run.artifacts['a0_candidate']['common']['assignment_law']=='UNKNOWN'
    if second_valid:assert run.review_kind=='query' and run.result is None
    else:assert run.stage=='STOPPED' and run.result['reason_code']==reason

def test_valid_unknowns_are_not_retried_until_the_model_fills_them(tmp_path,monkeypatch):
    case,info=fixture();engine=Engine(tmp_path/'runs')
    run=Run(owner='test',case=case.model_dump(mode='json'),automatic_review=True,synthetic=True);calls=[]
    def reply(run,request,stage):
        calls.append(stage);good=a0_candidate(run.intake,info)
        good['queries'][0]['semantics']['conditioning_context']='UNKNOWN'
        return good
    monkeypatch.setattr(engine,'call',reply);engine._read_case(run)
    assert calls==['a0'] and run.automatic_a0_format_repairs==0 and run.submission is None


@pytest.mark.parametrize('problem',['omitted_slot','omitted_direction','wrong_context'])
def test_missing_wire_slot_and_context_get_one_retry_without_filling_values(tmp_path,monkeypatch,problem):
    case,info=fixture();engine=Engine(tmp_path/'runs')
    run=Run(owner='test',case=case.model_dump(mode='json'),automatic_review=True,synthetic=True);calls=[]
    def reply(run,request,stage):
        calls.append(stage);good=a0_candidate(run.intake,info)
        if stage=='a0':
            if problem=='omitted_slot':del good['queries'][0]['semantics']['aggregation']
            elif problem=='omitted_direction':del good['queries'][0]['comparison_order']
            else:good['reference_context']='0'*64
        return good
    monkeypatch.setattr(engine,'call',reply);engine._read_case(run)
    assert calls==['a0','a0_format_retry'] and run.review_kind=='query'
    assert run.result is None and run.submission is None and not run.reviews
