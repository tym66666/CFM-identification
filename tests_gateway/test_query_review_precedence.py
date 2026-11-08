"""An explicit reading rejection cannot be masked by missing target facts."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from tests_gateway.test_intake_stop_review import uncertain,reviewed
from tests_gateway.test_inline_evidence_slots import receive,wire
from tests_gateway.test_business_field_review import sheet,record,submit
from cfm_id import business_field_review as fields
from examples.business_dispatch_reference import approve


def incomplete(profile='inline-unified-contract-1'):
    s=uncertain(kind='FIXED_POLICY_VALUE');raw=deepcopy(s.candidate)
    # Deliberate reader error, independently rejected below, plus a source gap
    # already present in the complete original question's aggregation wording.
    raw['common']['assignment_law']=dict(state='STATED',value='模型编造的历史经理自主决定机制',refs=raw['queries'][0]['goal']['refs'])
    return receive(s.case,wire(raw) if profile else raw,profile=profile)


def field_record(s, disposition='REJECTED'):
    r=record(sheet(s));r['decisions']['common.assignment_law']['source_coverage']=disposition
    return r


def direct_review(s, r, qid='q1'):
    return dict(version='business-dispatch-review-1',
        binding_sha256=intake._sha(dict(intake_sha256=intake._sha(s.model_dump(mode='json')),query_id=qid)),
        **{k:r[k] for k in ('reviewer','evidence','authority')},
        decisions=fields.project_decisions(fields.FieldReview.model_validate(r)),field_review=r)


@pytest.mark.parametrize('profile',[None,'inline-unified-contract-1'])
@pytest.mark.parametrize('decision,state,reason',[
    ('REJECTED','CHECK_BLOCKED','DISPATCH_REVIEW_REJECTED'),
    ('PENDING','REVIEW_REQUIRED','DISPATCH_REVIEW_PENDING'),
    ('ACCEPTED','NEEDS_INPUT','SELECTED_QUERY_COORDINATES_MISSING')])
def test_explicit_review_state_precedes_gap_but_acceptance_cannot_fill_it(profile,decision,state,reason):
    s=incomplete(profile);raw=deepcopy(s.candidate);original=intake.prepare_request(s)
    before=dispatch.prepare_reader(s,'q1');assert before['state']=='NEEDS_INPUT'
    r=field_record(s,decision);result=submit(s,r)
    assert result['state']==state and result['reason_code']==reason
    p=dispatch.prepare_reader(s,'q1',query_review=direct_review(s,r))
    assert p['state']==state and p['request'] is None and not p['backend_called']
    if decision!='ACCEPTED':
        assert p['deferred_clarification_questions']==before['clarification_questions']
        assert result['query_review']['field_review']==r
    assert s.candidate==raw and intake.prepare_request(s)==original
    assert s.candidate['queries'][0]['semantics']['aggregation']=='UNKNOWN'


@pytest.mark.parametrize('bad',['stale','nested_rejection_hidden','wrong_source','other_query','missing_field_review'])
def test_gap_never_hides_invalid_or_incomplete_submitted_review(bad):
    s=incomplete();r=direct_review(s,field_record(s))
    if bad=='stale':r['binding_sha256']='0'*64
    elif bad=='nested_rejection_hidden':r['decisions']={k:'ACCEPTED' for k in r['decisions']}
    elif bad=='wrong_source':r['field_review']['decisions']['common.assignment_law']['source_ids']=['invented']
    elif bad=='other_query':r['binding_sha256']=intake._sha(dict(intake_sha256=intake._sha(s.model_dump(mode='json')),query_id='q2'))
    else:r.pop('field_review')
    p=dispatch.prepare_reader(s,'q1',query_review=r)
    assert p['state']==('REVIEW_REQUIRED' if bad=='missing_field_review' else 'CHECK_BLOCKED')
    assert p['request'] is None and not p['backend_called']


@pytest.mark.parametrize('decision',['REJECTED','PENDING','ACCEPTED'])
def test_source_confirmed_gap_does_not_override_new_query_review(decision):
    s=reviewed(uncertain());old=dispatch.prepare_reader(s,'q1')
    assert old['reason_code']=='SOURCE_CONFIRMED_TARGET_GAP'
    r=field_record(s,decision);p=dispatch.prepare_reader(s,'q1',query_review=direct_review(s,r))
    assert p['state']=={'REJECTED':'CHECK_BLOCKED','PENDING':'REVIEW_REQUIRED','ACCEPTED':'NEEDS_INPUT'}[decision]
    assert p['request'] is None and not p['backend_called']
    if decision=='ACCEPTED':assert p==old
    assert intake.inspect(s)['reading_stop_receipt']


def test_whole_case_and_execute_keep_rejection_instead_of_requesting_only_input():
    s=incomplete();r=direct_review(s,field_record(s));opts=dict(query_review=r,candidate={},request_sha256='0'*64)
    e=dispatch.execute(s,'q1',**opts,research_protocol_selected=True)
    assert e['state']=='CHECK_BLOCKED' and e['reason_code']=='DISPATCH_REVIEW_REJECTED'
    c=business_case.prepare_case(s,query_reviews={'q1':r})
    assert c['queries'][0]['reader_plan']['reason_code']=='DISPATCH_REVIEW_REJECTED'
    whole=business_case.execute_case(s,{'q1':opts},case_review=approve(c['case_worksheet']),research_protocol_selected=True)
    assert whole['state']=='CASE_INCOMPLETE' and not whole['backend_called']
    assert not whole['identified_query_ids'] and whole['results'][0]['result']['reason_code']=='DISPATCH_REVIEW_REJECTED'


def test_no_review_preserves_original_gap_and_does_not_approve_a_reading():
    s=incomplete();p=dispatch.prepare_reader(s,'q1')
    assert p['state']=='NEEDS_INPUT' and p['query_worksheet'] is None
    assert 'deferred_clarification_questions' not in p and p['request'] is None
    assert p['mathematical_claim'] is None and not p['backend_called']


def test_rejection_does_not_turn_into_acceptance_when_missing_coordinate_is_filled():
    s=incomplete();old=direct_review(s,field_record(s));raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics']['aggregation']=dict(state='STATED',value='未经原文给出的等权平均',refs=raw['queries'][0]['goal']['refs'])
    changed=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    p=dispatch.prepare_reader(changed,'q1',query_review=old)
    assert p['state']=='CHECK_BLOCKED' and p['reason_code']=='STALE_OR_WRONG_SCOPE_DISPATCH_REVIEW'
    assert p['request'] is None and not p['backend_called']


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_valid_network_review_retains_existing_scientific_and_replay_gates(kind,expected):
    from tests_gateway.test_unified_reading_contract import test_native_network_chain_still_requires_science_and_replay
    test_native_network_chain_still_requires_science_and_replay(kind,expected)
