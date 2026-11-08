"""Single reviewed intent, source mapping, refusal and unchanged native proofs."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch,fact_source_review as source
from cfm_id import fact_reading_revision
from cfm_id_llm import reviewed_intent_handoff as handoff
from tests_gateway.test_target_first_native_compatibility import setup_target_first
from tests_gateway.test_fact_source_review import record,forbid_method_calls
from tests_gateway.test_business_field_review import sheet,record as field_record,submit
from examples.network_dispatch_reference import approval_records


def setup(kind='contrast_partial'):
    return setup_target_first(kind,profile='target-first-skill-1')


@pytest.mark.parametrize('kind',['partial','contrast_partial','effect','r3'])
def test_reviewed_target_requires_alignment_then_preserves_native_claim(kind):
    s,e,o=setup(kind);before=deepcopy(o['candidate']);intent=e['reviewed_intent']
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    assert body['reviewed_intent']['intent_sha256']==intent['intent_sha256']
    assert body['reviewed_intent']['fact_binding_sha256']==e['fact_binding_sha256']
    raw=s.candidate['queries'][0]
    for name in handoff.SEMANTICS:
        claim=raw['semantics'].get(name,'UNKNOWN')
        expected={k:v for k,v in claim.items() if k!='refs'} if isinstance(claim,dict) else claim
        assert intent['slots']['query.'+name]['claim']==expected
    # Ref IDs belong to different catalogs. Exact original spans are retained.
    for slot in intent['slots'].values():
        for link in slot['source_links']:
            doc=e['bundle']['documents'][link['document_id']]
            assert doc[link['start']:link['end']]==link['quote']
            assert all(x in body['source_catalog'] for x in link['fact_source_ids'])
    focus=json.loads(e['request']['user'].rsplit('\n',1)[1])['focus']
    assert set(focus)=={'query_id','reviewed_intent_sha256'}
    missing=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert missing['reason_code']=='REVIEWED_INTENT_ALIGNMENT_REVIEW_REQUIRED'
    assert not missing['backend_called']
    w=source.prepare(e,o['candidate'])
    assert w['fields']['']['reviewed_intent_alignment']['intent_sha256']==intent['intent_sha256']
    o['source_review']=record(w)
    plan=dispatch.inspect_methods(s,'q1',**o)
    assert plan['state']=='REVIEW_REQUIRED',plan
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**o,**approval_records(plan))
    assert result['state']==('PARTIAL' if 'partial' in kind else 'POINT'),result
    assert result['independent_replay'] and before==o['candidate']
    assert not result['reviewed_intent_handoff']['scientific_approval']
    # Same mathematical claim as the previous target-first wire.
    old,oe,oo=setup_target_first(kind)
    oo['source_review']=record(source.prepare(oe,oo['candidate']))
    baseline=dispatch.execute(old,'q1',**oo,**approval_records(dispatch.inspect_methods(old,'q1',**oo)))
    assert result['mathematical_claim']==baseline['mathematical_claim']


@pytest.mark.parametrize('axis',['field_role','value_state','source_coverage'])
def test_alignment_rejection_and_pending_stop_before_any_native_dispatch(monkeypatch,axis):
    s,e,o=setup();w=source.prepare(e,o['candidate']);r=record(w)
    forbid_method_calls(monkeypatch)
    for decision in ('REJECTED','PENDING'):
        r['decisions'][''][axis]=decision
        result=dispatch.execute(s,'q1',**o,source_review=r,research_protocol_selected=True)
        assert result['state']==('READING_RECHECK_REQUIRED' if decision=='REJECTED' else 'REVIEW_REQUIRED')
        assert not result['backend_called'] and not result['independent_replay']


def test_changed_target_or_raw_reply_cannot_reuse_review():
    s,e,o=setup();r=record(source.prepare(e,o['candidate']))
    raw=deepcopy(s.candidate);sem=raw['queries'][0]['semantics']
    sem['first_arrangement'],sem['second_arrangement']=sem['second_arrangement'],sem['first_arrangement']
    newer=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(newer,'q1',query_review=o['query_review'])['request'] is None
    q=submit(newer,field_record(sheet(newer)))['query_review']
    ne=dispatch.prepare_reader(newer,'q1',query_review=q)
    assert ne['reviewed_intent']['intent_sha256']!=e['reviewed_intent']['intent_sha256']
    changed=deepcopy(o['candidate']);changed['target']['first'],changed['target']['second']=changed['target']['second'],changed['target']['first']
    bad=dict(o,candidate=changed,source_review=r)
    result=dispatch.execute(s,'q1',**bad,research_protocol_selected=True)
    assert result['reason_code']=='INVALID_OR_STALE_FACT_SOURCE_REVIEW' and not result['backend_called']


def test_missing_target_and_unapproved_a0_do_not_get_handoff():
    s,e,o=setup()
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics']['target_population']='UNKNOWN'
    newer=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    entry=dispatch.prepare_reader(newer,'q1')
    assert entry['request'] is None and 'reviewed_intent' not in entry


def test_recheck_preserves_intent_but_rebinds_fact_request():
    s,e,o=setup()
    first=fact_reading_revision.prepare_recheck(s,'q1',**o)
    w=first['feedback_worksheet']
    feedback=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority=w['expected_authority'],
        reviewer='Synthetic review',evidence='Explicit synthetic source-located reread, no replacement values.',
        issues=[dict(field_path='/target',kind='OMITTED_OR_MISREAD',source_ids=[next(iter(w['source_catalog']))],
                     reason='Check the comparison direction against the original reviewed intent.')])
    revised=fact_reading_revision.prepare_recheck(s,'q1',**o,feedback=feedback)
    assert revised['state']=='READY_TO_READ',revised
    body=json.JSONDecoder().raw_decode(revised['request']['user'])[0]
    assert revised['reviewed_intent']==e['reviewed_intent']
    assert body['reviewed_intent']['fact_binding_sha256']!=e['fact_binding_sha256']
    assert body['reviewed_intent']['intent_sha256']==e['reviewed_intent']['intent_sha256']
    assert 'reviewed_intent' in json.dumps(w['public_field_constraints'])


def test_incomplete_source_mapping_is_not_guessed():
    origin={'a':dict(source_id='doc',start=0,end=3,quote='甲乙丙')}
    with pytest.raises(ValueError,match='INTENT_SOURCE_SPAN_NOT_COVERED'):
        handoff._source_links(['a'],origin,{'s1':dict(doc_id='doc',start=0,end=1,text='甲')},{'doc':'甲乙丙'})


def test_historical_profile_keeps_original_request_and_review():
    _,entry,options=setup_target_first('partial')
    assert 'reviewed_intent' not in entry
    assert 'reviewed_intent' not in entry['request']['user']
    assert 'reviewed_intent_alignment' not in source.prepare(entry,options['candidate'])['fields']['']
