"""Source-located, explicit rereading; no hidden candidate edits or approvals."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_dispatch as dispatch,business_intake as intake,business_case
from cfm_id.fact_reading_revision import prepare_recheck,ReadingFeedback,MAX_ROUNDS
from examples.network_bounded_dispatch_reference import setup,reference
from examples.network_dispatch_reference import approval_records
from examples.business_dispatch_reference import approve


def accept_changes(sheet):
    # Synthetic fixture only: separate from model output and native science.
    return dict(version='reading-change-review-1',binding_sha256=sheet['binding_sha256'],
        authority=sheet['expected_authority'],reviewer='Synthetic source reviewer',
        evidence='Independently checked the hand-authored fixture against original material.',
        decisions={k:dict(disposition='ACCEPTED',reason='Synthetic fixture correction agrees with the original stated material.',
            source_ids=list(sheet['source_catalog'])) for k in sheet['changes']})


def feedback(sheet,path='/assignment',kind='OMITTED_OR_MISREAD',doc='assignment'):
    sources=[k for k,v in sheet['source_catalog'].items() if v['doc_id']==doc]
    return ReadingFeedback(binding_sha256=sheet['binding_sha256'],authority=sheet['expected_authority'],
        reviewer='Private reviewer identity',evidence='Private evidence: source comparison, not scientific permission.',
        issues=[dict(field_path=path,kind=kind,source_ids=sources,
            reason='PRIVATE_REASON_NOT_SENT: independent source comparison; do not grant science.')])


def revised(**kwargs):
    s,e,o,p=setup(**kwargs);bad=deepcopy(o['candidate']);bad['assignment'].update(kind='OTHER',fixed_count=None)
    args=dict(query_review=o['query_review'],candidate=bad,request_sha256=e['request_sha256'])
    w=prepare_recheck(s,'q1',**args)
    r=prepare_recheck(s,'q1',**args,feedback=feedback(w['feedback_worksheet']))
    assert r['state']=='READY_TO_READ'
    fresh=reference(r,**kwargs)  # Newly authored mock reply; never used on actual LLM JSON.
    new=dict(query_review=o['query_review'],candidate=fresh,request_sha256=r['request_sha256'],reading_revision=r['reading_revision'])
    sheet=dispatch.inspect_methods(s,'q1',**new)['reading_change_worksheet']
    new['change_review']=accept_changes(sheet)
    return s,e,o,p,bad,r,new


def test_feedback_requires_independent_record_and_is_not_a_business_reply():
    s,e,o,p=setup();before=s.model_dump(mode='json');raw=deepcopy(o['candidate'])
    out=prepare_recheck(s,'q1',**o)
    assert out['state']=='REVIEW_REQUIRED' and out['request'] is None and not out['backend_called']
    assert out['feedback_worksheet']['is_approval'] is False and not out['feedback_worksheet']['issues']
    assert s.model_dump(mode='json')==before and o['candidate']==raw


def test_entire_object_can_be_rechecked_when_schema_fields_are_absent():
    s,e,o,p=setup();o['candidate']={}
    sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    assert sheet['field_paths']==['']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path=''))
    assert r['state']=='READY_TO_READ' and r['reading_revision']['steps'][0]['candidate']=={}
    assert not r['backend_called'] and not r['reading_revision_receipt']['scientific_approval']


def test_request_keeps_original_sources_and_only_sends_locations_not_review_or_gold():
    s,e,o,p,bad,r,new=revised()
    assert e['bundle']==r['bundle'] and s.candidate and r['reading_revision']['steps'][0]['candidate']==bad
    assert r['request_sha256']!=e['request_sha256'] and r['fact_binding_sha256']!=e['fact_binding_sha256']
    user=r['request']['user'];system=r['request']['system']
    assert all(x not in user+system for x in ('PRIVATE_REASON_NOT_SENT','Private reviewer identity','Private evidence:'))
    original=json.loads(e['request']['user'].split('\n\n本次只读取')[0])
    changed=json.loads(user.split('\n\n本次只读取')[0])
    assert original['source_catalog']==changed['source_catalog']
    context=json.loads(user.split('独立复查定位（不是新增事实）：\n')[1])
    assert set(context)=={'kind','previous_candidate','issues'} and context['previous_candidate']==bad
    assert context['issues'][0]['source_refs'] and 'expected_value' not in user
    receipt=r['reading_revision_receipt']
    assert not receipt['candidate_modified'] and not receipt['scientific_approval'] and not receipt['automatic_retry']


@pytest.mark.parametrize('corruption',['binding','authority','field','unknown_source','duplicate_source','empty_sources','duplicate_issue','blank_reason','extra_answer'])
def test_invalid_feedback_never_creates_request(corruption):
    s,e,o,p=setup();sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet'];record=feedback(sheet).model_dump(mode='json')
    issue=record['issues'][0]
    if corruption=='binding':record['binding_sha256']='0'*64
    elif corruption=='authority':record['authority']='EXTERNAL_RESEARCH_REVIEW'
    elif corruption=='field':issue['field_path']='/invented_field'
    elif corruption=='unknown_source':issue['source_ids']=['src_'+'0'*64]
    elif corruption=='duplicate_source':issue['source_ids']*=2
    elif corruption=='empty_sources':issue['source_ids']=[]
    elif corruption=='duplicate_issue':record['issues'].append(deepcopy(issue))
    elif corruption=='blank_reason':issue['reason']=' '*20
    else:record['expected_value']='POINT'
    r=prepare_recheck(s,'q1',**o,feedback=record)
    assert r['state']=='CHECK_BLOCKED' and r['request'] is None and not r['backend_called']


@pytest.mark.parametrize('change',['candidate','feedback','request','source','query_review','prompt'])
def test_rebuilt_revision_rejects_changed_history_or_input(monkeypatch,change):
    s,e,o,p,bad,r,new=revised();rev=deepcopy(r['reading_revision']);q=o['query_review']
    if change=='candidate':rev['steps'][0]['candidate']['assignment']['fixed_count']=5
    elif change=='feedback':rev['steps'][0]['feedback']['binding_sha256']='0'*64
    elif change=='request':rev['steps'][0]['request_sha256']='0'*64
    elif change=='source':
        case=s.case.model_dump(mode='json');case['sources'][0]['text']+=' Revised original material.'
        s=intake.revise_materials(s,case,reason='Original material changed')
    elif change=='query_review':q=q.model_copy(update={'evidence':'Different independent review of the original query.'})
    else:
        from cfm_id_llm import network_policy_reading
        monkeypatch.setattr(network_policy_reading,'SYSTEM',network_policy_reading.SYSTEM+' Changed prompt.')
    result=dispatch.prepare_reader(s,'q1',query_review=q,reading_revision=rev)
    assert result['state']!='READY_TO_READ' and result.get('request') is None


def test_new_context_rejects_old_reply_and_old_plan_and_requires_fresh_science():
    s,e,o,p,bad,r,new=revised();old_approvals=approval_records(p)
    wrong=dict(new,candidate=o['candidate'])
    assert dispatch.execute(s,'q1',**wrong,research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    assert dispatch.execute(s,'q1',**dict(new,request_sha256=e['request_sha256']))['state']=='CHECK_BLOCKED'
    pending=dispatch.execute(s,'q1',**new,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    assert dispatch.execute(s,'q1',**new,**old_approvals)['state']=='CHECK_BLOCKED'
    plan=dispatch.inspect_methods(s,'q1',**new)
    result=dispatch.execute(s,'q1',**new,**approval_records(plan))
    assert result['state']=='PARTIAL' and result['independent_replay']
    assert result['reading_revision']['steps'][0]['candidate']==bad
    assert result['reading_revision_receipt']['history_sha256']==r['reading_revision_receipt']['history_sha256']


@pytest.mark.parametrize('case_options,state',[(dict(missing_scope=True),'NEEDS_INPUT'),(dict(extra=True),'ADAPTER_NOT_CONNECTED')])
def test_rereading_does_not_remove_real_gaps_or_extra_restrictions(case_options,state):
    s,e,o,p,bad,r,new=revised(**case_options)
    result=dispatch.execute(s,'q1',**new,research_protocol_selected=True)
    assert result['state']==state and not result['backend_called'] and not result['answers']
    if case_options.get('extra'):assert result['facts']['additional_restrictions']
    else:assert result['facts']['bounded_model']['no_additional_coupling_constraints']['value'] is None


def test_each_round_requires_new_feedback_and_limit_prevents_automatic_loop():
    s,e,o,p=setup();args=deepcopy(o)
    for i in range(MAX_ROUNDS):
        sheet=prepare_recheck(s,'q1',**args)['feedback_worksheet']
        r=prepare_recheck(s,'q1',**args,feedback=feedback(sheet))
        assert r['state']=='READY_TO_READ' and len(r['reading_revision']['steps'])==i+1
        args=dict(query_review=o['query_review'],candidate=reference(r),request_sha256=r['request_sha256'],reading_revision=r['reading_revision'])
    limit=prepare_recheck(s,'q1',**args)
    assert limit['state']=='READING_RECHECK_REQUIRED' and limit['reason_code']=='EXPLICIT_RECHECK_ROUND_LIMIT'
    assert limit['request'] is None and not limit['backend_called']


def test_dag_uses_same_rereading_protocol_and_keeps_other_query_pending():
    from examples.business_case_reference import scenario,submission,short_fixture
    from examples.business_dispatch_reference import approvals
    s,native=scenario();row,e,p=submission(s,native,'q1',[0])
    args={k:row[k] for k in ('query_review','candidate','request_sha256')}
    sheet=prepare_recheck(s,'q1',**args)['feedback_worksheet']
    doc=next(iter(sheet['source_catalog'].values()))['doc_id']
    r=prepare_recheck(s,'q1',**args,feedback=feedback(sheet,path='/target',doc=doc))
    assert r['state']=='READY_TO_READ' and r['remaining_query_ids']==['q2']
    new=dict(query_review=row['query_review'],candidate=short_fixture(r,native,[0]),request_sha256=r['request_sha256'],reading_revision=r['reading_revision'])
    plan=dispatch.inspect_methods(s,'q1',**new)
    result=dispatch.execute(s,'q1',**new,**approvals(plan))
    assert result['state']=='POINT' and result['independent_replay'] and result['remaining_query_ids']==['q2']
    other=dispatch.prepare_reader(s,'q2',query_review=approve(dispatch.prepare_reader(s,'q2')['query_worksheet']),reading_revision=r['reading_revision'])
    assert other['state']=='CHECK_BLOCKED'


def test_cli_and_whole_case_keep_revision_and_require_reviews(tmp_path):
    from cfm_id.business_dispatch_cli import main
    s,e,o,p=setup();intake.save(s,tmp_path/'intake.json')
    intake.write_json(tmp_path/'reader.json',e);intake.write_json(tmp_path/'query.json',o['query_review'].model_dump(mode='json'))
    intake.write_json(tmp_path/'candidate.json',o['candidate'])
    args=['recheck-plan','--intake',str(tmp_path/'intake.json'),'--query','q1','--query-review',str(tmp_path/'query.json'),
          '--reader-plan',str(tmp_path/'reader.json'),'--candidate',str(tmp_path/'candidate.json')]
    assert main([*args,'--output',str(tmp_path/'worksheet.json')])==0
    sheet=intake.read_json(tmp_path/'worksheet.json')['feedback_worksheet']
    intake.write_json(tmp_path/'feedback.json',feedback(sheet).model_dump(mode='json'))
    assert main([*args,'--feedback',str(tmp_path/'feedback.json'),'--output',str(tmp_path/'new_reader.json')])==0
    e2=intake.read_json(tmp_path/'new_reader.json');intake.write_json(tmp_path/'revision.json',e2['reading_revision'])
    intake.write_json(tmp_path/'new_candidate.json',reference(e2))
    follow=['method-plan','--intake',str(tmp_path/'intake.json'),'--query','q1','--query-review',str(tmp_path/'query.json'),
            '--reader-plan',str(tmp_path/'new_reader.json'),'--candidate',str(tmp_path/'new_candidate.json'),
            '--reading-revision',str(tmp_path/'revision.json'),'--output',str(tmp_path/'new_plan.json')]
    assert main(follow)==0;p2=intake.read_json(tmp_path/'new_plan.json')
    row=dict(query_review=o['query_review'],candidate=reference(e2),request_sha256=e2['request_sha256'],reading_revision=e2['reading_revision'])
    case_review=approve(business_case.prepare_case(s)['case_worksheet'])
    pending=business_case.execute_case(s,{'q1':row},case_review=case_review,research_protocol_selected=True)
    assert pending['state']=='CASE_INCOMPLETE' and not pending['backend_called']
    row.update({k:v for k,v in approval_records(p2).items() if k!='research_protocol_selected'})
    result=business_case.execute_case(s,{'q1':row},case_review=case_review,research_protocol_selected=True)
    assert result['state']=='ALL_QUERIES_IDENTIFIED' and result['partially_identified_query_ids']==['q1']
    assert result['results'][0]['result']['reading_revision']==e2['reading_revision']
