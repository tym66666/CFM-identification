"""Whole-case source-role receipts must preserve individual-query guards."""
from copy import deepcopy
import inspect
import pytest
from cfm_id import business_case as whole, business_dispatch as dispatch, business_intake as intake
from cfm_id import network_information_evidence as evidence
from examples.network_dispatch_reference import approval_records, approve
from tests_gateway.test_network_information_evidence import fixture
from tests_gateway.test_network_bounded_dispatch import forbidden


def serial(value):
    if hasattr(value,'model_dump'):return value.model_dump(mode='json')
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,list):return [serial(v) for v in value]
    return value


def submission(**kwargs):
    s,e,o,r=fixture(**kwargs)
    o=dict(o,information_evidence_review=r)
    p=dispatch.inspect_methods(s,'q1',**o)
    row=dict(o,**{k:v for k,v in approval_records(p).items() if k!='research_protocol_selected'})
    return s,e,row


def execute(s,rows,**kwargs):
    return whole.execute_case(s,rows,case_review=approve(whole.prepare_case(s)['case_worksheet']),
        research_protocol_selected=True,**kwargs)


def test_whole_case_inputs_cover_dispatch_contract_without_accepting_saved_results():
    # Detect future review arguments omitted from the batch contract. Runtime
    # still uses an explicit allowlist, never reflection or arbitrary kwargs.
    expected=set(inspect.signature(dispatch.execute).parameters)-{'intake','query_id','research_protocol_selected'}
    assert whole.SUBMISSION_FIELDS==expected
    assert not {'result','answers','certificate','mathematical_claim'} & whole.SUBMISSION_FIELDS


@pytest.mark.parametrize('bounds,expected',[(('1/2','1/2'),'POINT'),(('1/4','3/4'),'PARTIAL')])
@pytest.mark.parametrize('json_wire',[False,True])
def test_identical_point_partial_and_replay_through_whole_case(bounds,expected,json_wire):
    s,e,row=submission(center_bounds=bounds)
    if json_wire:row=serial(row)
    before=deepcopy(row)
    direct=dispatch.execute(s,'q1',**row,research_protocol_selected=True)
    result=execute(s,{'q1':row})
    leaf=result['results'][0]['result']
    assert leaf==direct and leaf['state']==expected and leaf['independent_replay']
    assert result['state']=='ALL_QUERIES_IDENTIFIED' and result['identified_query_ids']==['q1']
    assert result['all_queries_point_identified']==(expected=='POINT')
    assert result['partially_identified_query_ids']==(['q1'] if expected=='PARTIAL' else [])
    assert result['mathematical_claim'] is result['certificate'] is None
    assert not result['production_admission'] and not result['estimation_handoff_allowed']
    receipt=leaf['information_evidence_receipt']
    assert not receipt['scientific_approval'] and not receipt['information_entries_merged']
    assert not receipt['candidate_modified'] and row==before


@pytest.mark.parametrize('bad',['missing','pending','rejected','stale_receipt','stale_request','stale_candidate',
    'wrong_authority','overlap','omitted_support','two_tables','foreign_source'])
def test_bad_source_review_stops_both_entries_before_math(bad,monkeypatch):
    from cfm_id import bounded_policy_solver
    s,e,row=submission();record=row['information_evidence_review']
    if bad=='missing':row.pop('information_evidence_review')
    elif bad=='pending':record['disposition']='PENDING'
    elif bad=='rejected':record['disposition']='REJECTED'
    elif bad=='stale_receipt':record['binding_sha256']='0'*64
    elif bad=='stale_request':row['request_sha256']='0'*64
    elif bad=='stale_candidate':row['candidate']['target']['population']=['中心']
    elif bad=='wrong_authority':record['authority']='EXTERNAL_RESEARCH_REVIEW'
    elif bad=='overlap':record['supporting_source_ids']+=record['table_source_ids']
    elif bad=='omitted_support':record['supporting_source_ids']=[]
    elif bad=='two_tables':record['table_source_ids']+=record['supporting_source_ids'];record['supporting_source_ids']=[]
    else:record['supporting_source_ids']=['not-a-current-source']
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    direct=dispatch.execute(s,'q1',**row,research_protocol_selected=True)
    result=execute(s,{'q1':row});leaf=result['results'][0]['result']
    assert leaf['state']==direct['state'] and leaf['reason_code']==direct['reason_code']
    assert not result['backend_called'] and not result['all_queries_identified']
    assert result['unresolved_query_ids']==['q1'] and leaf['mathematical_claim'] is None


@pytest.mark.parametrize('block',['policy','population','assumption_unknown','assumption_refused','extra_constraint'])
def test_accepted_source_review_does_not_supply_missing_facts_or_science(block,monkeypatch):
    from cfm_id import bounded_policy_solver
    s,e,row=submission();c=row['candidate']
    if block=='policy':c['target']['assignment']=None
    elif block=='population':c['target']['population']=None
    elif block=='assumption_unknown':c['assumptions']['full_vector_randomization']['value']=None
    elif block=='assumption_refused':c['assumptions']['full_vector_randomization']['value']=False
    else:c['additional_restrictions']=[dict(text='另有跨对象均值相等限制。',source_ids=c['study']['source_ids'])]
    # Independently recheck evidence roles only; no replacement facts or science.
    row['information_evidence_review']['binding_sha256']=evidence.prepare(e,c)['binding_sha256']
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    direct=dispatch.execute(s,'q1',**row,research_protocol_selected=True)
    result=execute(s,{'q1':row});leaf=result['results'][0]['result']
    assert leaf==direct and leaf['state'] in ('NEEDS_INPUT','ADAPTER_NOT_CONNECTED')
    assert not result['backend_called'] and result['unresolved_query_ids']==['q1']


@pytest.mark.parametrize('bad',['missing_science','pending_science','rejected_science','missing_plan','stale_plan'])
def test_provenance_receipt_does_not_replace_independent_approvals(bad,monkeypatch):
    from cfm_id import bounded_policy_solver
    s,e,row=submission()
    if bad=='missing_science':row.pop('native_reviews')
    elif bad=='missing_plan':row.pop('plan_review')
    elif bad=='stale_plan':row['plan_review']=row['plan_review'].model_copy(update={'binding_sha256':'0'*64})
    else:
        for records in row['native_reviews'].values():
            r=records['science_review'];state='PENDING' if bad=='pending_science' else 'REJECTED'
            records['science_review']=r.model_copy(update={'decisions':{k:state for k in r.decisions}})
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    direct=dispatch.execute(s,'q1',**row,research_protocol_selected=True)
    result=execute(s,{'q1':row});leaf=result['results'][0]['result']
    assert leaf['state']==direct['state'] and leaf['reason_code']==direct['reason_code']
    assert not result['backend_called'] and not result['identified_query_ids']


@pytest.mark.parametrize('block',['missing_case_review','rejected_case_review','unselected_research','saved_result'])
def test_case_admission_is_still_required(block,monkeypatch):
    from cfm_id import bounded_policy_solver
    s,e,row=submission();review=approve(whole.prepare_case(s)['case_worksheet'])
    if block=='missing_case_review':review=None
    elif block=='rejected_case_review':review=review.model_copy(update={'decisions':{k:'REJECTED' for k in review.decisions}})
    elif block=='saved_result':row['result']=dict(state='POINT',independent_replay=True)
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    result=whole.execute_case(s,{'q1':row},case_review=review,research_protocol_selected=block!='unselected_research')
    assert result['state'] in ('REVIEW_REQUIRED','CHECK_BLOCKED')
    assert not result['backend_called'] and not result['identified_query_ids']


def test_receipt_cannot_transfer_to_r3_reader(monkeypatch):
    from examples.network_observational_policy_reference import setup
    from pfn_pipeline import identification_business
    _,_,row=submission();receipt=row['information_evidence_review']
    s,e,o=setup();o['information_evidence_review']=receipt
    monkeypatch.setattr(identification_business,'identify_network_business_query',forbidden)
    result=execute(s,{'q1':o});leaf=result['results'][0]['result']
    assert leaf['reason_code']=='INFORMATION_EVIDENCE_REVIEW_NOT_CONNECTED_FOR_READER'
    assert not result['backend_called'] and result['unresolved_query_ids']==['q1']


def test_failed_replay_cannot_mark_case_complete(monkeypatch):
    from cfm_id import bounded_policy_verify
    s,e,row=submission()
    monkeypatch.setattr(bounded_policy_verify,'replay',lambda *a,**kw:False)
    result=execute(s,{'q1':row});leaf=result['results'][0]['result']
    assert leaf['state']=='CHECK_BLOCKED' and leaf['reason_code']=='BOUNDED_INPUT_OR_REPLAY_MISMATCH'
    assert result['backend_called'] and not result['all_queries_identified']
    assert not leaf['independent_replay'] and not leaf['answers'] and leaf['mathematical_claim'] is None


def test_successful_first_query_cannot_cover_second_query_with_foreign_receipt():
    from examples.network_bounded_dispatch_reference import case,reference
    from examples.network_dispatch_reference import intake_mock
    business,_=case();original_question=business.business_question
    second_question='在同样的全员使用安排下，只评价中心网点，按时完成的平均概率是多少？'
    business=business.model_copy(update={'business_question':original_question+'\n'+second_question})
    s=intake_mock(business);raw=deepcopy(s.candidate);first=raw['queries'][0]
    first['business_goal']['value']=original_question
    first['business_goal']['evidence'][0]['quote']=original_question
    first['target']['description']=deepcopy(first['business_goal'])
    second=deepcopy(first);second['query_id']='q2'
    second['business_goal']['value']=second_question
    second['business_goal']['evidence'][0]['quote']=second_question
    second['target']['description']=deepcopy(second['business_goal'])
    for q in (first,second):
        for name in ('target_population','intervention','policy_assignment','aggregation'):
            q['semantics'][name]=deepcopy(q['business_goal'])
    raw['queries']=[first,second];raw['shared_draft']['target']=deepcopy(first['target'])
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    rows={}
    for qid in ('q1','q2'):
        qr=approve(dispatch.prepare_reader(s,qid)['query_worksheet'])
        e=dispatch.prepare_reader(s,qid,query_review=qr);c=reference(e)
        if qid=='q2':c['target']['population']=['中心']
        c['information'][0]['source_ids']+=c['exposure']['source_ids']
        w=evidence.prepare(e,c);table=[sid for sid,v in w['source_catalog'].items() if v['doc_id']=='information']
        receipt=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',
            reviewer='independent_fixture_audit',evidence='All cells come from the information table; exposure citations define its columns only.',
            disposition='ACCEPTED',table_source_ids=table,supporting_source_ids=[sid for sid in w['source_catalog'] if sid not in table])
        o=dict(query_review=qr,candidate=c,request_sha256=e['request_sha256'],information_evidence_review=receipt)
        p=dispatch.inspect_methods(s,qid,**o)
        rows[qid]=dict(o,**{k:v for k,v in approval_records(p).items() if k!='research_protocol_selected'})
    assert execute(s,rows)['all_queries_identified']
    rows['q2']['information_evidence_review']=rows['q1']['information_evidence_review']
    result=execute(s,rows)
    assert result['identified_query_ids']==['q1'] and result['unresolved_query_ids']==['q2']
    assert result['state']=='CASE_INCOMPLETE' and not result['all_queries_identified']
    assert not result['results'][1]['result']['backend_called']


@pytest.mark.parametrize('bounds,expected',[(('1/2','1/2'),'POINT'),(('1/4','3/4'),'PARTIAL')])
def test_offline_cli_preserves_receipt_and_replay_after_restore(tmp_path,bounds,expected):
    from cfm_id.business_case_cli import main
    s,e,row=submission(center_bounds=bounds)
    intake.save(s,tmp_path/'intake.json')
    intake.write_json(tmp_path/'submissions.json',serial({'q1':row}))
    intake.write_json(tmp_path/'review.json',serial(approve(whole.prepare_case(s)['case_worksheet'])))
    assert main(['execute','--intake',str(tmp_path/'intake.json'),'--submissions',str(tmp_path/'submissions.json'),
        '--case-review',str(tmp_path/'review.json'),'--select-research-protocol','--output',str(tmp_path/'result.json')])==0
    result=intake.read_json(tmp_path/'result.json');leaf=result['results'][0]['result']
    assert result['all_queries_identified'] and leaf['state']==expected and leaf['independent_replay']
    assert leaf['information_evidence_receipt']['review']==row['information_evidence_review']
