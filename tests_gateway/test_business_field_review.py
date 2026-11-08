"""Independent field decisions, current scope and existing mathematical gates."""
from copy import deepcopy
import json
import pytest

from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id import business_field_review as review
from cfm_id_llm import business_field_contract as contract
from cfm_id_llm.compact_formulator import CompactCommon,CompactQuery,CompactSemantics,make_compact_request
from cfm_id_llm.compact_reference_contract import CONTRACT as SHORT,split_user
from cfm_id_llm.evidence_refs import build_catalog
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_compact_short_refs import encode_fixture
from tests_gateway.test_business_intake_compact import scenario
from examples.business_dispatch_reference import approve,approvals


META = dict(authority='SYNTHETIC_TEST',reviewer='Independent fixture reviewer',
            evidence='Explicit synthetic source comparison; not a real scientific approval.')


def received(case, raw, short=False, **options):
    s=intake.start(case,a0_reference_contract=SHORT if short else None,**options)
    return intake.receive_candidate(s,encode_fixture(s,raw) if short else raw,request_sha256=s.request_sha256)


def setup(short=False):
    b,raw=fixture();return received(b,raw,short)


def sheet(s, qid='q1'):
    return review.prepare(s,qid,authority='SYNTHETIC_TEST')['field_worksheet']


def record(w, disposition='ACCEPTED'):
    # Synthetic fixture only: production has no accept-all helper.
    return dict(version=review.VERSION,binding_sha256=w['binding_sha256'],**META,
        decisions={p:dict(**{k:disposition for k in review.DIMENSIONS},
            reason='Independent synthetic fixture comparison to all original materials.',
            source_ids=list(w['source_catalog'])) for p in w['fields']})


def submit(s, r, qid='q1'):
    return review.submit(s,qid,r,authority='SYNTHETIC_TEST')


def test_registry_covers_schema_and_drives_existing_wire_descriptions():
    contract.assert_coverage(CompactCommon.model_fields,CompactSemantics.model_fields,set(CompactQuery.model_fields)-{'semantics'})
    b,_=fixture();schema=split_user(make_compact_request(b)[1])[2]
    for section,model in [('common','CompactCommon'),('semantics','CompactSemantics')]:
        for name,text in contract.descriptions(section).items():
            assert schema['$defs'][model]['properties'][name]['description']==text
    assert contract.inapplicable_fields()=={'comparator','policy_assignment'}
    with pytest.raises(ValueError,match='SCHEMA_DRIFT'):
        contract.assert_coverage([*CompactCommon.model_fields,'new_field'],CompactSemantics.model_fields,{'goal','kind'})


@pytest.mark.parametrize('short',[False,True])
def test_worksheet_preserves_sources_original_values_and_pending_defaults(short):
    s=setup(short);before=s.model_dump(mode='json');request=intake.prepare_request(s)
    w=sheet(s)
    assert len(w['fields'])==23 and set(w['fields'])==set(w['decisions'])
    assert w['original_materials']==s.case.model_dump(mode='json')
    assert all(all(d[k]=='PENDING' for k in review.DIMENSIONS) for d in w['decisions'].values())
    item=w['fields']['queries.q1.semantics.policy_assignment']
    assert item['candidate']==s.candidate['queries'][0]['semantics']['policy_assignment']
    assert [r['ref'] for r in item['actual_citations']]==item['candidate']['refs']
    assert w['fields']['common.available_information']['state']=='UNKNOWN'
    assert not w['fields']['common.available_information']['raw_present']
    assert s.model_dump(mode='json')==before and intake.prepare_request(s)==request
    r=submit(s,record(w,'PENDING'))
    assert r['state']=='REVIEW_REQUIRED' and r['request'] is None and not r['scientific_approval']


@pytest.mark.parametrize('path,dimension',[
    ('common.variable_causal_graph','field_role'),('common.available_information','value_state'),
    ('queries.q1.semantics.policy_assignment','source_coverage')])
def test_rejected_role_state_or_citation_reaches_existing_query_block(path,dimension):
    s=setup(True);w=sheet(s);r=record(w);r['decisions'][path][dimension]='REJECTED'
    result=submit(s,r)
    assert result['state']=='CHECK_BLOCKED' and result['query_review']['field_review']==r
    entry=dispatch.prepare_reader(s,'q1',query_review=result['query_review'])
    assert entry['state']=='CHECK_BLOCKED' and entry['request'] is None and not entry['backend_called']


@pytest.mark.parametrize('corruption',['missing_field','extra_field','missing_dimension','invalid_dimension',
    'unknown_source','duplicate_source','missing_source','blank_reason','wrong_binding','wrong_authority'])
def test_incomplete_forged_or_stale_field_review_is_rejected(corruption):
    s=setup();r=record(sheet(s));p='common.variable_causal_graph';d=r['decisions'][p]
    if corruption=='missing_field':r['decisions'].pop(p)
    elif corruption=='extra_field':r['decisions']['common.invented']=deepcopy(d)
    elif corruption=='missing_dimension':d.pop('field_role')
    elif corruption=='invalid_dimension':d['field_role']='VERIFIED'
    elif corruption=='unknown_source':d['source_ids']=['invented']
    elif corruption=='duplicate_source':d['source_ids']*=2
    elif corruption=='missing_source':d['source_ids']=[]
    elif corruption=='blank_reason':d['reason']=' '*20
    elif corruption=='wrong_binding':r['binding_sha256']='0'*64
    else:r['authority']='EXTERNAL_RESEARCH_REVIEW'
    with pytest.raises(ValueError):submit(s,r)


def test_top_level_acceptance_cannot_override_nested_rejection():
    s=setup();r=record(sheet(s));r['decisions']['common.variable_causal_graph']['field_role']='REJECTED'
    value=submit(s,r)['query_review'];value['decisions']={k:'ACCEPTED' for k in value['decisions']}
    entry=dispatch.prepare_reader(s,'q1',query_review=value)
    assert entry['state']=='CHECK_BLOCKED' and entry['request'] is None
    value=submit(s,record(sheet(s)))['query_review'];value['reviewer']='Another reviewer'
    assert dispatch.prepare_reader(s,'q1',query_review=value)['state']=='CHECK_BLOCKED'


def test_graph_role_is_reviewed_not_guessed_from_keywords():
    b,raw=fixture();raw['common']['variable_causal_graph']=deepcopy(raw['common']['unit_network'])
    s=received(b,raw);w=sheet(s)
    assert intake.inspect(s)['state']=='SEMANTIC_REVIEW_REQUIRED'
    assert all(d['field_role']=='PENDING' for d in w['decisions'].values())
    assert w['fields']['common.variable_causal_graph']['candidate']==raw['common']['variable_causal_graph']
    r=record(w);r['decisions']['common.variable_causal_graph']['field_role']='REJECTED'
    assert submit(s,r)['state']=='CHECK_BLOCKED' and s.candidate==raw


def test_reviewer_sources_never_fill_missing_candidate_citations():
    s=setup();raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics']['policy_assignment']['value']+='，甲乙丙均为1'
    s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256);w=sheet(s)
    p='queries.q1.semantics.policy_assignment';original=deepcopy(w['fields'][p]['actual_citations'])
    r=record(w);r['decisions'][p]['source_coverage']='REJECTED'
    result=submit(s,r)
    assert result['state']=='CHECK_BLOCKED' and sheet(s)['fields'][p]['actual_citations']==original
    assert s.candidate==raw


def test_known_absence_text_is_preserved_for_state_review_not_silently_changed():
    b,raw=fixture();source=raw['common']['analysis_unit']['refs']
    raw['common']['available_information']=dict(state='STATED',value='没有提供总体信息',refs=source)
    s=received(b,raw);w=sheet(s);item=w['fields']['common.available_information']
    assert item['state']=='STATED' and item['candidate']['value']=='没有提供总体信息'
    r=record(w);r['decisions']['common.available_information']['value_state']='REJECTED'
    assert submit(s,r)['state']=='CHECK_BLOCKED' and s.candidate==raw


def test_correctly_accepted_unknown_target_does_not_resolve_the_target():
    b,raw=fixture();raw['queries'][0]['semantics']['aggregation']='UNKNOWN'
    s=received(b,raw);result=submit(s,record(sheet(s)))
    assert result['state']=='NEEDS_INPUT' and result['query_review'] is None and result['request'] is None
    assert intake.inspect(s)['state']=='BUSINESS_CLARIFICATION_REQUIRED'


def test_same_candidate_new_receive_and_other_query_cannot_reuse_review():
    s=setup();r=record(sheet(s));old=submit(s,r)['query_review']
    new=intake.receive_candidate(s,s.candidate,request_sha256=s.request_sha256)
    with pytest.raises(ValueError,match='STALE'):submit(new,r)
    assert dispatch.prepare_reader(new,'q1',query_review=old)['state']=='CHECK_BLOCKED'
    b,raw=fixture();old_catalog={r['ref']:r['source_id'] for r in build_catalog(b)}
    b=b.model_copy(update={'business_question':b.business_question+'另问相同政策下，下周乙店准时开门的概率。'})
    cat=build_catalog(b)
    def rebind(x):
        if isinstance(x,dict):
            return {k:([r['ref'] for r in cat if r['source_id'] in {old_catalog[vv] for vv in v}]
                       if k=='refs' else rebind(v)) for k,v in x.items()}
        if isinstance(x,list):return [rebind(v) for v in x]
        return x
    raw=rebind(raw);other=deepcopy(raw['queries'][0])
    other['goal']['value']='相同政策下，下周乙店准时开门的概率。'
    other['semantics']['target_population']['value']='乙店'
    other['semantics']['aggregation']['value']='乙店准时开门的概率'
    raw['queries'].append(other);multi=received(b,raw)
    w=sheet(multi,'q1');assert not any(p.startswith('queries.q2.') for p in w['fields'])
    with pytest.raises(ValueError,match='STALE'):submit(multi,record(w),'q2')


def test_definition_change_invalidates_review_without_changing_legacy_prompt(monkeypatch):
    s=setup();r=record(sheet(s));old_request=intake.prepare_request(s)
    monkeypatch.setattr(contract,'EVIDENCE_RULE',contract.EVIDENCE_RULE+'新增审核范围。')
    assert intake.prepare_request(s)==old_request
    with pytest.raises(ValueError,match='STALE'):submit(s,r)


def test_attached_review_is_not_a_plan_or_science_approval():
    s=setup();r=dispatch.DispatchReview.model_validate(submit(s,record(sheet(s)))['query_review'])
    with pytest.raises(ValueError,match='WRONG_SCOPE'):
        dispatch.checked_review(r,dispatch.worksheet(r.binding_sha256,dispatch.QUERY_DECISIONS))


def test_invalid_or_canonical_reading_has_no_compact_field_review():
    s=setup();bad=deepcopy(s.candidate);bad['queries'][0]['goal']['refs']=['invented']
    invalid=intake.receive_candidate(s,bad,request_sha256=s.request_sha256)
    with pytest.raises(ValueError,match='CURRENT_VALID'):sheet(invalid)
    from examples.business_dispatch_reference import from_case
    from examples.dag_business_reference import cases
    canonical,_=from_case(cases()[0])
    with pytest.raises(ValueError,match='CURRENT_VALID'):sheet(canonical)


def test_removing_details_changes_fact_binding_and_keeps_legacy_explicit_review_compatible():
    s=setup();detailed=submit(s,record(sheet(s)))['query_review']
    a=dispatch.prepare_reader(s,'q1',query_review=detailed)
    old=deepcopy(detailed);old.pop('field_review');b=dispatch.prepare_reader(s,'q1',query_review=old)
    assert a['state']==b['state']=='READY_TO_READ' and a['request_sha256']!=b['request_sha256']
    assert 'field_review' not in dispatch.DispatchReview.model_validate(old).model_dump(mode='json')


def test_covariate_items_and_empty_collection_have_separate_rows():
    b,raw=fixture();raw['common']['covariates']=[deepcopy(raw['common']['analysis_unit'])]*2
    s=received(b,raw);w=sheet(s)
    assert 'common.covariates' not in w['fields']
    assert w['fields']['common.covariates[0]']['state']=='STATED'
    assert w['fields']['common.covariates[1]']['actual_citations']
    assert sheet(setup())['fields']['common.covariates']['state']=='COLLECTION'


def test_dag_chain_keeps_scientific_review_and_independent_replay():
    b,raw,facts=scenario();s=received(b,raw,fact_format='source_hash')
    q=submit(s,record(sheet(s)))['query_review'];entry=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=facts,request_sha256=entry['request_sha256'])
    plan=dispatch.inspect_methods(s,'q1',**opts)
    blocked=dispatch.execute(s,'q1',**opts,research_protocol_selected=True)
    assert not blocked['backend_called']
    done=dispatch.execute(s,'q1',**opts,**approvals(plan))
    assert done['state']=='POINT' and done['independent_replay']


def test_network_chain_keeps_scientific_review_and_independent_replay():
    from examples.network_dispatch_reference import case,candidate,approval_records
    b,_,_=case();cat=build_catalog(b)
    def c(value,doc):return dict(state='STATED',value=value,refs=[r['ref'] for r in cat if r['source_id']==doc])
    goal=c(b.business_question,'business_question')
    raw=dict(common={k:c(b.source_map()[d],d) for k,d in [('analysis_unit','study'),('treatment','study'),('outcome','study'),('unit_network','network')]},queries=[dict(goal=goal,kind='FIXED_POLICY_VALUE',semantics=dict(target_population=goal,intervention=goal,policy_assignment=goal,aggregation=goal,time_horizon=c('本周','study'),comparator='NOT_APPLICABLE'))])
    s=received(b,raw,True);q=submit(s,record(sheet(s)))['query_review'];entry=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=candidate(entry),request_sha256=entry['request_sha256'])
    plan=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    done=dispatch.execute(s,'q1',**opts,**approval_records(plan))
    assert done['state']=='POINT' and done['independent_replay']


def test_cli_emits_pending_sheet_and_rejects_invalid_review_without_api(tmp_path):
    s=setup();p=tmp_path/'intake.json';intake.save(s,p);out=tmp_path/'sheet.json'
    assert review.main(['worksheet','--intake',str(p),'--query','q1','--output',str(out),'--authority','SYNTHETIC_TEST'])==0
    w=intake.read_json(out)['field_worksheet'];r=record(w,'PENDING');rp=tmp_path/'record.json';intake.write_json(rp,r)
    result=tmp_path/'result.json'
    assert review.main(['submit','--intake',str(p),'--query','q1','--record',str(rp),'--output',str(result),'--authority','SYNTHETIC_TEST'])==0
    assert intake.read_json(result)['state']=='REVIEW_REQUIRED'
