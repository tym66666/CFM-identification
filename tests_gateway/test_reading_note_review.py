"""Review notes explicitly without weakening fact, scientific or proof gates."""
from copy import deepcopy
import pytest
from cfm_id import business_dispatch as dispatch,business_case,business_intake as intake
from cfm_id.reading_note_review import ReadingNoteReview
from examples.network_dispatch_reference import setup as point_setup,approval_records
from examples.network_bounded_dispatch_reference import setup as bounded_setup
from examples.business_dispatch_reference import approve


def with_note(kind='partial'):
    s,e,o,p=(point_setup(design='D1',sufficiency=False) if kind=='r1b' else
             point_setup() if kind=='r2' else bounded_setup(center_bounds=('1/2','1/2')) if kind=='point' else bounded_setup())
    o['candidate']['unresolved']=[dict(text='是否能够确定还需要识别分析，读取助手不应给出数学答案。',
                                      source_ids=o['candidate']['target']['source_ids'])]
    return s,e,o,dispatch.inspect_methods(s,'q1',**o)


def review(plan,disposition='DEFER_TO_MATHEMATICS'):
    """Explicit synthetic assertion for a known fixture, never model inference."""
    sheet=plan['note_review_worksheet'];sources=list(sheet['source_catalog'])
    return ReadingNoteReview(binding_sha256=sheet['binding_sha256'],authority=sheet['expected_authority'],
        reviewer='Independent synthetic note reviewer',
        evidence='Frozen fixture note independently compared with original question and declared conditions.',
        decisions={key:dict(disposition=disposition,reason='Original target is defined; applicability is checked by the unchanged mathematical backend.',
                           source_ids=[sources[-1]]) for key in sheet['notes']})


def prepare_reviewed(kind='partial',disposition='DEFER_TO_MATHEMATICS'):
    s,e,o,p=with_note(kind);o['note_review']=review(p,disposition)
    return s,e,o,dispatch.inspect_methods(s,'q1',**o)


def forbidden(*a,**kw):raise AssertionError('Backend must not run')


def test_unreviewed_note_requires_review_not_a_new_user_fact():
    s,e,o,p=with_note()
    assert p['state']=='REVIEW_REQUIRED' and 'plan_worksheet' not in p
    assert p['clarification_questions']==[] and not p['backend_called'] and not p['methods']
    assert p['note_review_worksheet']['is_approval'] is False
    assert all(v['disposition']=='PENDING' for v in p['note_review_worksheet']['decisions'].values())
    assert p['reading_candidate']==o['candidate'] and p['facts']['unresolved']


@pytest.mark.parametrize('kind',['r1b','r2','point','partial'])
@pytest.mark.parametrize('disposition',['NONBLOCKING_COMMENT','DEFER_TO_MATHEMATICS'])
def test_note_release_preserves_candidate_and_independent_science(kind,disposition):
    s,e,o,p=prepare_reviewed(kind,disposition);raw=deepcopy(o['candidate'])
    assert p['state']=='REVIEW_REQUIRED' and 'plan_worksheet' in p
    pending=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==('PARTIAL' if kind=='partial' else 'POINT') and r['independent_replay']
    assert o['candidate']==raw and p['facts']['unresolved'] and r['note_review_receipt']['original_notes']
    assert not r['note_review_receipt']['candidate_modified'] and not r['note_review_receipt']['scientific_approval']


@pytest.mark.parametrize('disposition,state',[('PENDING','REVIEW_REQUIRED'),('MATERIAL_GAP','NEEDS_INPUT'),
                                            ('READING_ERROR','READING_RECHECK_REQUIRED')])
def test_reviewer_can_keep_gap_or_require_rereading(monkeypatch,disposition,state):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    s,e,o,p=prepare_reviewed(disposition=disposition)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==state and not r['backend_called'] and not r['answers']
    assert bool(r['clarification_questions'])==(disposition=='MATERIAL_GAP')
    assert bool(r['reading_recheck_notes'])==(disposition=='READING_ERROR')


@pytest.mark.parametrize('gap',['population','randomization','a4_value','bounds','complete_model','coupling','additional_restriction'])
def test_releasing_comment_cannot_fill_typed_fields_or_drop_restrictions(monkeypatch,gap):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    s,e,o,p=with_note();c=o['candidate']
    if gap=='population':c['target']['population']=None
    elif gap=='randomization':c['assumptions']['full_vector_randomization']['value']=None
    elif gap=='a4_value':c['information'][0]['signature_cells'][0]['value']=None
    elif gap=='bounds':c['bounded_model']['bounds'].pop()
    elif gap=='complete_model':c['bounded_model']['listed_means_are_complete_information']['value']=None
    elif gap=='coupling':c['bounded_model']['no_additional_coupling_constraints']['value']=None
    else:c['additional_restrictions']=[dict(text='仍需额外的单调性约束。',source_ids=c['target']['source_ids'])]
    raw=deepcopy(c);p=dispatch.inspect_methods(s,'q1',**o);o['note_review']=review(p)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==('ADAPTER_NOT_CONNECTED' if gap=='additional_restriction' else 'NEEDS_INPUT')
    assert not r['backend_called'] and not r['answers'] and o['candidate']==raw


@pytest.mark.parametrize('corrupt',['authority','binding','unknown_source','missing_source','extra_note','missing_note','blank_reason','extra_approval'])
def test_invalid_review_has_no_mathematical_permission(corrupt):
    s,e,o,p=with_note();r=review(p).model_dump(mode='json')
    if corrupt=='authority':r['authority']='EXTERNAL_RESEARCH_REVIEW'
    elif corrupt=='binding':r['binding_sha256']='0'*64
    elif corrupt=='unknown_source':r['decisions']['n0001']['source_ids']=['src_'+'0'*64]
    elif corrupt=='missing_source':r['decisions']['n0001']['source_ids']=[]
    elif corrupt=='extra_note':r['decisions']['n0002']=deepcopy(r['decisions']['n0001'])
    elif corrupt=='missing_note':r['decisions']={}
    elif corrupt=='blank_reason':r['decisions']['n0001']['reason']=' '*20
    else:r['scientific_approval']=True
    o['note_review']=r;out=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert out['state']=='CHECK_BLOCKED' and not out['backend_called']


@pytest.mark.parametrize('change',['value','text','order','remove','source'])
def test_candidate_changes_invalidate_note_review(change):
    s,e,o,p=with_note();o['candidate']['unresolved'].append(dict(text='还需检查支持条件是否满足。',source_ids=o['candidate']['target']['source_ids']))
    p=dispatch.inspect_methods(s,'q1',**o);o['note_review']=review(p);c=o['candidate']
    if change=='value':c['bounded_model']['bounds'][0]['lower']='1/4'
    elif change=='text':c['unresolved'][0]['text']='用户的评价对象尚未决定。'
    elif change=='order':c['unresolved'].reverse()
    elif change=='remove':c['unresolved']=[]
    else:c['unresolved'][0]['source_ids']=c['study']['source_ids']
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_changed_adjudication_invalidates_plan_and_native_reviews():
    s,e,o,p=prepare_reviewed();a=approval_records(p)
    changed=o['note_review'].model_dump(mode='json');changed['decisions']['n0001']['disposition']='NONBLOCKING_COMMENT'
    o['note_review']=changed
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('status',['PENDING','REJECTED'])
def test_released_notes_do_not_override_native_science_decisions(status):
    s,e,o,p=prepare_reviewed();a=approval_records(p)
    method=p['methods'][0]['method']
    science=a['native_reviews'][method]['science_review'].model_dump(mode='json')
    science['decisions'][next(iter(science['decisions']))]=status
    a['native_reviews'][method]['science_review']=science
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==('REVIEW_REQUIRED' if status=='PENDING' else 'CHECK_BLOCKED')
    assert not r['backend_called'] and not r['answers']


@pytest.mark.parametrize('field',['query_id','request_sha256','documents'])
def test_note_review_is_bound_to_query_request_and_original_material(field):
    from cfm_id.reading_note_review import inspect_notes
    from cfm_id_llm.network_policy_reading import documents
    from cfm_id.business_dispatch import DispatchError
    s,e,o,p=with_note();record=review(p);docs=documents(e['bundle'])
    entry=deepcopy(e)
    if field=='documents':docs[next(iter(docs))]+=' Changed original material.'
    elif field=='query_id':entry['query_id']='q2'
    else:entry['request_sha256']='0'*64
    with pytest.raises(DispatchError):
        inspect_notes(entry,o['candidate'],p['facts']['unresolved'],docs,record)


def test_candidate_cannot_supply_its_own_review():
    s,e,o,p=with_note();o['candidate']['note_review']=review(p).model_dump(mode='json')
    r=dispatch.inspect_methods(s,'q1',**o)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_real_gap_in_one_note_cannot_be_hidden_by_other_release():
    s,e,o,p=with_note();o['candidate']['unresolved'].append(dict(text='研究者尚未决定完整模型范围。',source_ids=o['candidate']['target']['source_ids']))
    p=dispatch.inspect_methods(s,'q1',**o);record=review(p).model_dump(mode='json')
    record['decisions']['n0002']['disposition']='MATERIAL_GAP';o['note_review']=record
    r=dispatch.inspect_methods(s,'q1',**o)
    assert r['state']=='NEEDS_INPUT' and r['clarification_questions']==['研究者尚未决定完整模型范围。']


def test_unknown_note_review_is_not_ignored_for_dag():
    from examples.business_dispatch_reference import prepare
    from examples.dag_business_reference import cases
    s,o,p=prepare(cases()[0])
    r=dispatch.inspect_methods(s,'q1',**o,note_review={})
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']


def test_note_review_is_preserved_through_whole_case_and_single_query_cli(tmp_path):
    from cfm_id.business_dispatch_cli import main
    s,e,o,p=prepare_reviewed();a=approval_records(p);case_review=approve(business_case.prepare_case(s)['case_worksheet'])
    row=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
    r=business_case.execute_case(s,{'q1':row},case_review=case_review,research_protocol_selected=True)
    assert r['state']=='ALL_QUERIES_IDENTIFIED' and r['partially_identified_query_ids']==['q1']
    assert r['results'][0]['result']['note_review_receipt']['review_sha256']==p['note_review_receipt']['review_sha256']
    def serial(v):
        if hasattr(v,'model_dump'):return v.model_dump(mode='json')
        if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
        return v
    intake.save(s,tmp_path/'intake.json')
    for name,value in [('reader',e),('query',o['query_review']),('candidate',o['candidate']),('note',o['note_review']),
                       ('plan_review',a['plan_review']),('native',a['native_reviews'])]:
        intake.write_json(tmp_path/(name+'.json'),serial(value))
    args=['execute','--intake',str(tmp_path/'intake.json'),'--query','q1',
          '--query-review',str(tmp_path/'query.json'),'--reader-plan',str(tmp_path/'reader.json'),
          '--candidate',str(tmp_path/'candidate.json'),'--note-review',str(tmp_path/'note.json'),
          '--plan-review',str(tmp_path/'plan_review.json'),'--native-reviews',str(tmp_path/'native.json'),
          '--select-research-protocol','--output',str(tmp_path/'result.json')]
    assert main(args)==0
    result=intake.read_json(tmp_path/'result.json')
    assert result['state']=='PARTIAL' and result['independent_replay']
    assert result['note_review_receipt']['original_notes']
