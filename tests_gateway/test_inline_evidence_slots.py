"""Exclusive absence/value representation with unchanged scientific boundaries."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm import business_field_contract as fields
from cfm_id_llm.compact_inline_evidence_contract import CONTRACT
from cfm_id_llm.compact_response_contract import evidence_contract
from cfm_id_llm.compact_reference_contract import CONTRACT as SHORT, split_user
from cfm_id_llm.compact_formulator import make_compact_request
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_compact_short_refs import encode_fixture
from tests_gateway.test_compact_evidence_slots import extended, contrast_raw
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_reading_review_guards import feedback
from examples.business_dispatch_reference import approve


def wire(raw, operation='NOT_APPLICABLE'):
    value=extended(raw, operation);value.pop('missing_information');return value


def receive(b, raw, short=True, profile=CONTRACT):
    s=intake.start(b,a0_response_contract=profile,a0_reference_contract=SHORT if short else None,
                   target_summary_contract='target-summary-3')
    return intake.receive_candidate(s,encode_fixture(s,raw) if short else raw,request_sha256=s.request_sha256)


def absent():
    b,raw=fixture();raw=wire(raw)
    raw['common']['network_pretreatment_status']=dict(state='MISSING',reason='关系形成时间没有提供',
        refs=deepcopy(raw['common']['analysis_unit']['refs']))
    return b,raw  # Deliberately wrong absence citation: must await independent review.


def test_known_assignment_family_and_cited_gap_survive_without_becoming_a_law():
    from cfm_id_llm.schemas import SourceDocument
    from cfm_id_llm.evidence_refs import build_catalog
    from cfm_id_llm.quality import MultiQueryDraftV010
    b,raw=fixture();raw=wire(raw)
    previous_catalog=build_catalog(b)
    text='试点从全部门店均匀抽取固定名额，但本材料尚未提供具体名额。'
    b=b.model_copy(update={'sources':[*b.sources,SourceDocument(source_id='assignment',text=text)]})
    refs={a['ref']:z['ref'] for a,z in zip(previous_catalog,build_catalog(b))}
    def rebind_fixture(x):
        if isinstance(x,dict):return {k:([refs[r] for r in v] if k=='refs' else rebind_fixture(v)) for k,v in x.items()}
        if isinstance(x,list):return [rebind_fixture(v) for v in x]
        return x
    raw=rebind_fixture(raw)
    raw['common']['assignment_family']='COMPLETE_RANDOMIZATION'
    raw['common']['assignment_law']=dict(state='MISSING',reason=text,
        refs=[r['ref'] for r in build_catalog(b) if r['source_id']=='assignment'])
    s=receive(b,raw);before=deepcopy(s.candidate);r=intake.inspect(s)
    assert r['state']=='SEMANTIC_REVIEW_REQUIRED' and not r['core_called']
    draft=r['report']['draft'];info=draft['shared_draft']['information_design']
    assert info['assignment_family']=='COMPLETE_RANDOMIZATION'
    assert info['assignment_law']==dict(value=None,basis='UNRESOLVED',evidence=[])
    assert info['assignment_law_gap']==dict(value=text,basis='EXPLICIT_TEXT',
        evidence=[dict(source_id='assignment',quote=text)])
    assert MultiQueryDraftV010.model_validate(draft).model_dump(mode='json')==draft
    w=sheet(s);assert w['fields']['common.assignment_law']['state']=='MISSING'
    rr=record(w);rr['decisions']['common.assignment_law']['source_coverage']='REJECTED'
    assert submit(s,rr)['state']=='CHECK_BLOCKED'
    assert s.candidate==before


def test_assignment_gap_cannot_replace_evidence_or_coexist_with_a_known_law():
    from pydantic import ValidationError
    from cfm_id_llm.schemas import InformationDesignDraft,SemanticClaim
    old=InformationDesignDraft().model_dump(mode='json')
    assert 'assignment_law_gap' not in old
    assert InformationDesignDraft.model_validate(old).model_dump(mode='json')==old
    known=dict(value='均匀抽取两家',basis='EXPLICIT_TEXT',evidence=[dict(source_id='a',quote='均匀抽取两家')])
    gap=dict(value='尚未提供名额',basis='EXPLICIT_TEXT',evidence=[dict(source_id='a',quote='尚未提供名额')])
    for fields in ({}, {'assignment_law_gap':SemanticClaim()},
                   {'assignment_law_gap':dict(gap,basis='INTERPRETATION')},
                   {'assignment_law':known,'assignment_law_gap':gap}):
        with pytest.raises(ValidationError):
            InformationDesignDraft(assignment_family='COMPLETE_RANDOMIZATION',**fields)
    assert 'assignment_law_gap' not in InformationDesignDraft(
        assignment_family='COMPLETE_RANDOMIZATION',assignment_law=known).model_dump(mode='json')


def test_schema_has_one_absence_location_and_same_public_sources():
    b,_=fixture();a=make_compact_request(b,a0_response_contract='evidence-slots-1')
    z=make_compact_request(b,a0_response_contract=CONTRACT)
    assert split_user(a[1])[1]==split_user(z[1])[1] and a[2]==z[2]
    schema=split_user(z[1])[2]
    assert 'missing_information' not in schema['properties'] and 'MissingInformation' not in schema['$defs']
    assert 'MissingClaim' in schema['$defs']
    assert 'value' not in schema['$defs']['MissingClaim']['properties']
    assert 'comparison_order' in schema['$defs']['CompactQuery']['required']
    assert evidence_contract(CONTRACT).CONTRACT==CONTRACT
    assert evidence_contract('evidence-slots-1').CONTRACT=='evidence-slots-1'
    assert evidence_contract(None) is None
    with pytest.raises(ValueError):evidence_contract('unregistered')


@pytest.mark.parametrize('short',[False,True])
def test_missing_reason_is_reviewed_once_with_sources_and_never_becomes_a_value(short):
    b,raw=absent();s=receive(b,raw,short);before=deepcopy(s.candidate);r=intake.inspect(s)
    c=r['report']['draft']['shared_draft']['structure']['network_pretreatment_status']
    assert c['value'] is None and c['basis']=='UNRESOLVED' and c['evidence']==[]
    w=sheet(s);item=w['fields']['common.network_pretreatment_status']
    assert item['state']=='MISSING' and item['actual_citations']
    assert item['candidate']==s.candidate['common']['network_pretreatment_status']
    assert not any('missing_information' in p for p in w['fields'])
    assert 'MISSING' in w['state_rules'] and 'MISSING' not in fields.STATE_RULES
    assert s.candidate==before and not r['core_called']
    review=record(w);review['decisions']['common.network_pretreatment_status']['source_coverage']='REJECTED'
    assert submit(s,review)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('bad',['value_and_reason','missing_reason','null_reason','blank_reason','empty_refs',
    'duplicate_refs','invented_ref','top_level_list','unknown_with_reason','stated_with_reason',
    'goal_missing','covariate_missing','enum_missing','order_missing'])
def test_conflicting_or_misplaced_states_are_rejected_without_repair(bad):
    b,raw=absent();c=raw['common']['network_pretreatment_status']
    if bad=='value_and_reason':c['value']='未提供'
    elif bad=='missing_reason':c.pop('reason')
    elif bad=='null_reason':c['reason']=None
    elif bad=='blank_reason':c['reason']='  '
    elif bad=='empty_refs':c['refs']=[]
    elif bad=='duplicate_refs':c['refs']*=2
    elif bad=='invented_ref':c['refs']=['invented']
    elif bad=='top_level_list':raw['missing_information']=[]
    elif bad=='unknown_with_reason':c['state']='UNKNOWN'
    elif bad=='stated_with_reason':c.update(state='STATED',value='时间未知')
    elif bad=='goal_missing':raw['queries'][0]['goal']=deepcopy(c)
    elif bad=='covariate_missing':raw['common']['covariates']=[deepcopy(c)]
    elif bad=='enum_missing':raw['common']['assignment_family']=deepcopy(c)
    elif bad=='order_missing':raw['queries'][0]['comparison_order']=deepcopy(c)
    s=receive(b,raw,False)
    assert 'report' not in intake.inspect(s) and s.candidate==raw
    assert dispatch.prepare_reader(s,'q1')['request'] is None


def test_stated_absence_is_not_rewritten_by_keywords():
    b,raw=fixture();raw=wire(raw)
    raw['common']['network_pretreatment_status']=dict(state='STATED',value='没有提供关系形成时间',
        refs=raw['common']['analysis_unit']['refs'])
    s=receive(b,raw);assert 'report' in intake.inspect(s)
    r=record(sheet(s));r['decisions']['common.network_pretreatment_status']['value_state']='REJECTED'
    assert submit(s,r)['state']=='CHECK_BLOCKED'
    assert s.candidate['common']['network_pretreatment_status']['state']=='STATED'


def test_known_negative_and_known_covariate_are_not_mapped_to_missing():
    b,raw=fixture();raw=wire(raw)
    # Explicit synthetic candidate, not a claim that the fixture source entails it.
    raw['common']['assignment_law']=dict(state='STATED',value='未抽签，由负责人选择',refs=raw['common']['analysis_unit']['refs'])
    raw['common']['covariates']=[dict(state='STATED',value='启动前员工数，尚未观测',refs=raw['common']['analysis_unit']['refs'])]
    s=receive(b,raw);r=intake.inspect(s)
    assert r['report']['draft']['shared_draft']['information_design']['assignment_law']['value']=='未抽签，由负责人选择'
    assert sheet(s)['fields']['common.covariates[0]']['state']=='STATED'
    assert not r['core_called']


def test_missing_required_target_stays_blocked_after_source_review():
    b,raw=absent();raw['queries'][0]['semantics']['aggregation']=deepcopy(raw['common']['network_pretreatment_status'])
    s=receive(b,raw);r=submit(s,record(sheet(s)))
    assert r['state']=='NEEDS_INPUT' and r['request'] is None
    assert intake.inspect(s)['report']['draft']['queries'][0]['semantics']['aggregation']['value'] is None


def test_field_review_is_required_and_missing_reason_change_invalidates_it(tmp_path):
    b,raw=absent();s=receive(b,raw)
    coarse=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    assert dispatch.prepare_reader(s,'q1',query_review=coarse)['reason_code']=='EXPLICIT_EVIDENCE_FIELD_REVIEW_REQUIRED'
    q=submit(s,record(sheet(s)))['query_review']
    assert dispatch.prepare_reader(s,'q1',query_review=q)['state']=='READY_TO_READ'
    trimmed=deepcopy(q);trimmed.pop('field_review')
    assert dispatch.prepare_reader(s,'q1',query_review=trimmed)['request'] is None
    changed=deepcopy(s.candidate);changed['common']['network_pretreatment_status']['reason']+='；需要核查'
    newer=intake.receive_candidate(s,changed,request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(newer,'q1',query_review=q)['request'] is None
    p=tmp_path/'intake.json';intake.save(s,p);assert intake.restore(p)==s


def test_legacy_contract_cannot_silently_take_inline_missing_and_contexts_are_bound():
    b,raw=absent();old=extended(raw);old.pop('reference_context',None)
    s=receive(b,old,profile='evidence-slots-1')
    assert 'report' not in intake.inspect(s)
    new=receive(b,raw);wrong=deepcopy(new.candidate);wrong['reference_context']='c'+'0'*64
    new=intake.receive_candidate(new,wrong,request_sha256=new.request_sha256)
    assert intake.inspect(new)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'


def test_reread_changed_missing_reason_requires_change_review():
    from cfm_id.intake_reading_revision import prepare_recheck
    b,raw=absent();s=receive(b,raw);w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    newer=prepare_recheck(s,feedback=feedback(w),authority='SYNTHETIC_TEST')
    raw['common']['network_pretreatment_status']='UNKNOWN'
    newer=intake.receive_candidate(newer,encode_fixture(newer,raw),request_sha256=newer.request_sha256)
    assert newer.a0_response_contract==CONTRACT and intake.inspect(newer)['state']=='REVIEW_REQUIRED'
    assert dispatch.prepare_reader(newer,'q1')['request'] is None


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_signed_native_chain_requires_science_and_replays(kind,expected):
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information');s=receive(b,raw)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert 'first/second不是主方案/基准' in e['request']['system']
    opts=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**opts,**approval_records(p))
    assert result['state']==expected and result['independent_replay']


def test_unspecified_order_does_not_guess_direction():
    b,_,raw=contrast_raw(operation='UNSPECIFIED');raw.pop('missing_information');s=receive(b,raw)
    assert dispatch.prepare_reader(s,'q1')['state']=='READING_RECHECK_REQUIRED'
    assert any(i['code']=='COMPARISON_DIRECTION_UNRESOLVED' for i in intake.inspect(s)['wire_gate']['issues'])


def test_dag_target_keeps_its_reader_scientific_review_and_point_replay():
    from tests_gateway.test_business_intake_compact import scenario
    from examples.business_dispatch_reference import approvals
    b,raw,facts=scenario();s=receive(b,wire(raw));s=intake.configure_fact_format(s,'source_hash')
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['reader_id']=='VARIABLE_DAG_FACTS' and 'first/second不是主方案/基准' not in e['request']['system']
    opts=dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'])
    plan=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**opts,**approvals(plan))
    assert result['state']=='POINT' and result['independent_replay']


def test_missing_state_remains_on_its_own_query_review():
    b,raw=fixture();raw=wire(raw);raw['queries'].append(deepcopy(raw['queries'][0]))
    # Distinct unapproved proposals: this test checks scope, not their entailment.
    raw['queries'][1]['goal']['value']+='；另一个待审核的问题'
    raw['queries'][1]['semantics']['standardization_distribution']=dict(state='MISSING',
        reason='第二问未规定平均分布',refs=raw['queries'][1]['goal']['refs'])
    s=receive(b,raw)
    assert not any(p.startswith('queries.q2.') for p in sheet(s,'q1')['fields'])
    assert sheet(s,'q2')['fields']['queries.q2.semantics.standardization_distribution']['state']=='MISSING'


def test_cli_accepts_closed_developer_profile(tmp_path):
    from cfm_id.business_intake_cli import main
    b,_=fixture();p=tmp_path/'case.json';p.write_text(b.model_dump_json(),encoding='utf8');out=tmp_path/'intake.json'
    assert main(['new','--case-json',str(p),'--a0-response-contract',CONTRACT,'--output',str(out)])==0
    assert intake.restore(out).a0_response_contract==CONTRACT
