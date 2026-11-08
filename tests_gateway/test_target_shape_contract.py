"""Target wording experiment; no keyword repairs, implicit approval or model scoring."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from cfm_id.business_reading_config import ReadingConfig
from cfm_id.intake_reading_revision import prepare_recheck
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.schemas import BusinessCase,SourceDocument
from cfm_id_llm.target_summary_contract import SHAPE_CONTRACT,READINESS_CONTRACT
from examples.business_dispatch_reference import approve
from examples.network_contrast_dispatch_reference import material,a0_reference,fact_reference,approval_records
from tests_gateway.test_target_summary_contract import fixture,receive
from tests_gateway.test_reading_review_guards import feedback


def test_new_request_only_changes_guidance_and_three_descriptions():
    b,_=fixture()
    a=make_compact_request(b,target_summary_contract=READINESS_CONTRACT)
    z=make_compact_request(b,target_summary_contract=SHAPE_CONTRACT)
    ap,ajs=a[1].split('\n\n输出 Schema：\n');zp,zjs=z[1].split('\n\n输出 Schema：\n')
    assert ap==zp and a[2]==z[2]
    old,new=json.loads(ajs),json.loads(zjs)
    for model,field in [('CompactQuery','kind'),('CompactSemantics','comparator'),('CompactSemantics','policy_assignment')]:
        old['$defs'][model]['properties'][field].pop('description',None)
        new['$defs'][model]['properties'][field].pop('description',None)
    assert old==new and z[0].startswith(a[0])


def test_config_serialization_and_old_review_invalidation(tmp_path):
    b,raw=fixture();old=receive(b,raw,READINESS_CONTRACT)
    s=intake.start_configured(b,ReadingConfig(target_summary_contract=SHAPE_CONTRACT))
    with pytest.raises(ValueError,match='STALE'):
        intake.receive_candidate(s,raw,request_sha256=old.request_sha256)
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    p=tmp_path/'new.json';intake.save(s,p);assert intake.restore(p)==s
    review=approve(dispatch.prepare_reader(old,'q1')['query_worksheet'])
    assert dispatch.prepare_reader(s,'q1',query_review=review)['state']=='CHECK_BLOCKED'
    with pytest.raises(ValueError,match='PROMPT_CHANGED'):
        intake._checked({**old.model_dump(mode='json'),'target_summary_contract':SHAPE_CONTRACT})


@pytest.mark.parametrize('kind',['TOTAL_EFFECT','FIXED_POLICY_VALUE','UNRESOLVED'])
@pytest.mark.parametrize('comparator',['UNKNOWN','NOT_APPLICABLE'])
def test_profile_does_not_relabel_candidate_or_relax_comparison_gate(kind,comparator):
    b,raw=fixture();raw['queries'][0]['kind']=kind;raw['queries'][0]['semantics']['comparator']=comparator
    old=receive(b,raw,READINESS_CONTRACT);new=receive(b,raw,SHAPE_CONTRACT)
    assert new.candidate==raw
    assert intake.inspect(new)['wire_gate']==intake.inspect(old)['wire_gate']
    p=dispatch.prepare_reader(new,'q1');assert p['request'] is None and not p['backend_called']
    if kind=='TOTAL_EFFECT':assert p['state'] in ('NEEDS_INPUT','READING_RECHECK_REQUIRED')


def test_misclassified_contrast_is_not_repaired_by_new_guidance():
    b,raw=fixture();raw['queries'][0]['semantics']['comparator']=deepcopy(raw['queries'][0]['semantics']['intervention'])
    s=receive(b,raw,SHAPE_CONTRACT)
    assert s.candidate==raw and dispatch.prepare_reader(s,'q1')['state']=='READING_RECHECK_REQUIRED'
    assert any(x['code']=='UNEXPECTED_COMPARATOR' for x in intake.inspect(s)['wire_gate']['issues'])


def test_recheck_still_requires_changes_review_and_science():
    b,raw=fixture();bad=deepcopy(raw);bad['queries'][0]['semantics']['aggregation']='UNKNOWN'
    s=receive(b,bad,SHAPE_CONTRACT);w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    new=prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
    new=intake.receive_candidate(new,raw,request_sha256=new.request_sha256)
    assert new.target_summary_contract==SHAPE_CONTRACT and new.reading_revision['steps'][0]['candidate']==bad
    assert intake.inspect(new)['state']=='REVIEW_REQUIRED'
    assert dispatch.prepare_reader(new,'q1')['request'] is None and business_case.prepare_case(new)['case_worksheet'] is None


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL'),('cancellation','POINT')])
def test_new_guidance_keeps_reviewed_native_comparison_and_replay(kind,expected):
    b,data=material(kind,bounds=('1/4','3/4') if kind=='partial' else ('0','1'))
    s=intake.start_configured(b,ReadingConfig(target_summary_contract=SHAPE_CONTRACT))
    s=intake.receive_candidate(s,a0_reference(b),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    plan=dispatch.inspect_methods(s,'q1',**opts)
    assert dispatch.execute(s,'q1',**opts)['state']=='REVIEW_REQUIRED'
    result=dispatch.execute(s,'q1',**opts,**approval_records(plan))
    assert result['state']==expected and result['independent_replay'] is True


def test_business_cases_only_send_original_sources_not_private_expectations():
    data=json.loads((Path(__file__).parents[1]/'evaluation/business_target_reading_cases.json').read_text('utf8'))
    assert len({c['id'] for c in data['cases']})==len(data['cases'])==8
    for row in data['cases']:
        b=BusinessCase(case_id=row['id'],business_question=row['business_question'],sources=[SourceDocument(**s) for s in row['sources']])
        _,text,_=make_compact_request(b,target_summary_contract=SHAPE_CONTRACT)
        public=json.loads(text.split('\n\n输出 Schema：\n')[0].split('\n',1)[1])
        assert public['business_question']==row['business_question']
        assert public['sources']==b.model_dump(mode='json')['sources']
        assert 'expected' not in public and set(public)=={'case_id','business_question','sources','response_language','source_catalog'}
        assert b.source_map().keys()=={'business_question','background'} or b.source_map().keys()=={'background'}
