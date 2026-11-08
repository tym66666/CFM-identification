"""Exact source segmentation, unaltered claims and unchanged admission gates."""
from copy import deepcopy
from hashlib import sha256
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase,SourceDocument
from cfm_id_llm.source_paragraphs import build_catalog
from cfm_id_llm.compact_reference_contract import PARAGRAPHS,catalog,request_context,split_user
from cfm_id_llm.evidence_refs import build_catalog as clauses
from cfm_id_llm.focused_field_contract import CONTRACT
from cfm_id_llm.compact_formulator import make_compact_request
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import wire
from tests_gateway.test_business_field_review import sheet,record,submit


def encode_fixture(s,raw):
    """Serialize offline reference spans only; never applied to model responses."""
    rows=catalog(s.case,PARAGRAPHS)
    mapping={old['ref']:next(r['ref'] for r in rows if r['source_id']==old['source_id'] and r['start']<=old['start'] and r['end']>=old['end']) for old in clauses(s.case)}
    def walk(x):
        if isinstance(x,dict):return {k:[mapping[v] for v in val] if k=='refs' else walk(val) for k,val in x.items()}
        if isinstance(x,list):return [walk(v) for v in x]
        return deepcopy(x)
    # Multiple old clauses in one paragraph need one selector in this synthetic serialization.
    def dedupe(x):
        if isinstance(x,dict):return {k:list(dict.fromkeys(v)) if k=='refs' else dedupe(v) for k,v in x.items()}
        if isinstance(x,list):return [dedupe(v) for v in x]
        return x
    return dict(dedupe(walk(raw)),reference_context=request_context(intake.prepare_request(s)['user_prompt']))


def receive(b,raw):
    s=intake.start(b,a0_reference_contract=PARAGRAPHS,a0_response_contract=CONTRACT,target_summary_contract='target-summary-3')
    return intake.receive_candidate(s,encode_fixture(s,raw),request_sha256=s.request_sha256)


@pytest.mark.parametrize('length',[2,999,1000,1001,1002,1999,2000,2001])
def test_bounded_partition_preserves_every_character_without_overlap(length):
    text='汉'*(length-1)+'😀';b=BusinessCase(case_id='chars',business_question='明确问题？',sources=[SourceDocument(source_id='doc',text=text)])
    rows=[r for r in build_catalog(b) if r['source_id']=='doc']
    assert ''.join(r['quote'] for r in rows)==text
    assert all(2<=len(r['quote'])<=1000 and text[r['start']:r['end']]==r['quote'] for r in rows)
    assert all(a['end']==z['start'] for a,z in zip(rows,rows[1:]))
    assert all(r['sha256']==sha256(r['quote'].encode()).hexdigest() for r in rows)


def test_never_merge_lines_documents_or_remove_negative_context():
    text='评价甲站。该站的均值尚未提供。\r\n\r\n乙站均值可用。'
    b=BusinessCase(case_id='bounds',business_question='评价什么？',sources=[SourceDocument(source_id='doc',text=text),SourceDocument(source_id='other',text='甲站均值可用。')])
    rows=[r for r in build_catalog(b) if r['source_id']=='doc']
    assert [r['quote'] for r in rows]==['评价甲站。该站的均值尚未提供。\r\n','乙站均值可用。']
    b2=b.model_copy(update={'sources':[b.sources[0].model_copy(update={'text':text+'新信息。'}),b.sources[1]]})
    assert not set(r['ref'] for r in rows)&set(r['ref'] for r in build_catalog(b2))


def test_exact_quotes_and_review_still_do_not_approve_wrong_claim():
    b,raw=fixture();raw=wire(raw)
    raw['common']['available_information']=dict(state='STATED',value='全部总体均值自动从现有样本获得',refs=raw['queries'][0]['goal']['refs'])
    s=receive(b,raw);before=deepcopy(s.candidate);r=intake.inspect(s)
    assert 'report' in r and not r['core_called'] and s.candidate==before
    sh=sheet(s);rec=record(sh);key='common.available_information'
    rec['decisions'][key]['source_coverage']='REJECTED'
    assert submit(s,rec)['state']=='CHECK_BLOCKED'
    quotes=sh['fields'][key]['actual_citations']
    assert quotes and all(s.case.source_map()[x['source_id']][x['start']:x['end']]==x['quote'] for x in quotes)


def test_missing_reason_remains_unknown_and_uses_new_catalog():
    b,raw=fixture();raw=wire(raw)
    raw['common']['available_information']=dict(state='MISSING',reason='暂未提供总体信息。',refs=raw['queries'][0]['goal']['refs'])
    s=receive(b,raw);r=intake.inspect(s)
    assert r['report']['draft']['shared_draft']['information_design']['population_observable_operator']['value'] is None
    assert sheet(s)['fields']['common.available_information']['candidate']['state']=='MISSING'
    assert not r['core_called']


@pytest.mark.parametrize('change',['context','selector','duplicate'])
def test_wrong_context_selector_and_duplicate_remain_blocked(change):
    b,raw=fixture();s=receive(b,wire(raw));bad=deepcopy(s.candidate)
    if change=='context':bad['reference_context']='c'+'0'*64
    elif change=='selector':bad['queries'][0]['goal']['refs']=['s9999']
    else:bad['queries'][0]['goal']['refs']*=2
    s=intake.receive_candidate(s,bad,request_sha256=s.request_sha256)
    assert intake.inspect(s)['state']=='READING_RECHECK_REQUIRED'


def test_changed_reference_profile_cannot_reuse_candidate_or_review():
    b,raw=fixture();s=receive(b,wire(raw));old=intake.start(b,a0_reference_contract='compact-source-selectors-1',a0_response_contract=CONTRACT,target_summary_contract='target-summary-3')
    wrong=intake.receive_candidate(old,s.candidate,request_sha256=old.request_sha256)
    assert intake.inspect(wrong)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_math_still_requires_reviews_and_independent_replay(kind,expected):
    from tests_gateway.test_compact_evidence_slots import contrast_raw
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information');s=receive(b,raw)
    review=submit(s,record(sheet(s)))['query_review'];entry=dispatch.prepare_reader(s,'q1',query_review=review)
    opts=dict(query_review=review,candidate=fact_reference(entry,data),request_sha256=entry['request_sha256'])
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**opts,**approval_records(dispatch.inspect_methods(s,'q1',**opts)))
    assert result['state']==expected and result['independent_replay']


def test_focused_roles_shared_by_request_and_recheck_without_new_fields():
    from cfm_id_llm.compact_unified_contract import recheck_field_roles
    b,_=fixture();old=make_compact_request(b,a0_response_contract='inline-unified-contract-9');new=make_compact_request(b,a0_response_contract=CONTRACT)
    def types(x):
        if isinstance(x,dict):return {k:types(v) for k,v in x.items() if k!='description'}
        if isinstance(x,list):return [types(v) for v in x]
        return x
    assert types(split_user(old[1])[2])==types(split_user(new[1])[2])
    role=recheck_field_roles(['/queries/0/semantics/aggregation'],contract=CONTRACT)[0]['field_role']
    assert role==split_user(new[1])[2]['$defs']['CompactSemantics']['properties']['aggregation']['description']
    assert '无需复述' in role and '完整安排' in role


def test_paragraph_requests_use_their_own_limit_not_the_legacy_clause_limit():
    from cfm_id_llm.quality_formulator import A0QualityValidationError
    b=BusinessCase(case_id='many-sentences',business_question='比较门店效果？',
        sources=[SourceDocument(source_id='memo',text='已有记录。'*600)])
    with pytest.raises(A0QualityValidationError,match='Source catalog exceeds limit'):
        make_compact_request(b,a0_reference_contract='compact-source-selectors-1')
    request=make_compact_request(b,a0_reference_contract=PARAGRAPHS,a0_response_contract=CONTRACT)
    assert request[2]==catalog(b,PARAGRAPHS)
    assert len(request[2])<10
    assert ''.join(r['quote'] for r in request[2] if r['source_id']=='memo')==b.sources[0].text
    s=intake.start(b,a0_reference_contract=PARAGRAPHS,a0_response_contract=CONTRACT)
    assert request_context(intake.prepare_request(s)['user_prompt'])


def test_paragraph_reread_preserves_original_and_requires_all_change_review(tmp_path):
    from cfm_id.intake_reading_revision import prepare_recheck,review_changes
    from tests_gateway.test_reading_review_guards import feedback,accept_changes
    b,raw=fixture();raw=wire(raw);bad=deepcopy(raw)
    bad['queries'][0]['semantics']['time_horizon']['value']='五十年后'
    s=receive(b,bad);original=deepcopy(s.candidate)
    w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    assert all(k.startswith('s') for k in w['source_catalog'])
    revised=prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
    stale=intake.receive_candidate(revised,s.candidate,request_sha256=revised.request_sha256)
    assert intake.inspect(stale)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    fresh=intake.receive_candidate(revised,encode_fixture(revised,raw),request_sha256=revised.request_sha256)
    r=intake.inspect(fresh)
    assert r['state']=='REVIEW_REQUIRED' and not r['core_called']
    assert dispatch.prepare_reader(fresh,'q1')['request'] is None
    checked=review_changes(fresh,accept_changes(r['reading_change_worksheet']))
    assert checked.reading_revision['steps'][0]['candidate']==original
    assert intake.inspect(checked)['state']=='SEMANTIC_REVIEW_REQUIRED'
    intake.save(checked,tmp_path/'reread.json')
    assert intake.restore(tmp_path/'reread.json')==checked
