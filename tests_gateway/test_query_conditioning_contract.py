"""Target conditions cannot disappear between A0, source review and native R3."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as d, business_case
from cfm_id import network_observational_policy_dispatch as r3
from cfm_id_llm import query_conditioning_contract as c
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.compact_wire_diagnostics import diagnose
from examples.network_observational_policy_reference import material, a0_reference, fact_reference, approval_records, approve
from tests_gateway.test_inline_evidence_slots import wire, receive
from tests_gateway.test_business_field_review import sheet, record, submit


def draft(scene='care', **kwargs):
    case,data=material(scene,**kwargs);raw=wire(a0_reference(case,data))
    refs=[r['ref'] for r in build_catalog(case) if r['source_id']=='conditioning']
    raw['queries'][0]['semantics'][c.FIELD]=dict(state='STATED',value=data['conditioning'],refs=refs)
    return case,data,raw


def setup(scene='care', **kwargs):
    case,data,raw=draft(scene,**kwargs);s=receive(case,raw,profile=c.CONTRACT)
    review=submit(s,record(sheet(s)))['query_review'];e=d.prepare_reader(s,'q1',query_review=review)
    assert e['state']=='READY_TO_READ',e
    o=dict(query_review=review,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    return s,e,o


@pytest.mark.parametrize('scene',['care','depots'])
def test_schema_review_reading_and_native_target_preserve_same_condition(scene):
    s,e,o=setup(scene);before=deepcopy(s.candidate)
    schema=split_user(intake.prepare_request(s)['user_prompt'])[2]
    Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(s.candidate)
    for model in ('CompactSemantics','OrderedLocalSemantics'):
        assert c.FIELD in schema['$defs'][model]['required']
        assert schema['$defs'][model]['properties'][c.FIELD]['description']==c.DESCRIPTION
    item=sheet(s)['fields']['queries.q1.semantics.'+c.FIELD]
    assert item['definition']['wire_description']==c.DESCRIPTION and item['actual_citations']
    reading=intake.inspect(s)
    assert reading['wire_gate']['slot_states']['q1'][c.FIELD]=='STATED'
    assert reading['wire_gate']['query_conditioning']['queries']['q1']['value']==item['candidate']['value']
    assert e['reviewed_target_context']['conditioning_context']==before['queries'][0]['semantics'][c.FIELD]
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    assert body['output_schema']['properties']['conditioning']['description']==c.FACT_DESCRIPTION
    p=d.inspect_methods(s,'q1',**o);assert p['state']=='REVIEW_REQUIRED',p
    assert p['target_conditioning_review']['decision']==c.MATCH_DECISION
    a=approval_records(p);r=d.execute(s,'q1',**o,**a)
    assert r['state']=='POINT' and r['independent_replay'] and s.candidate==before
    assert json.loads(r['mathematical_claim']['target']['context'])['fixed_pretreatment_W']==o['candidate']['conditioning']['definition']
    whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert whole['results'][0]['result']['independent_replay']


@pytest.mark.parametrize('axis',['field_role','value_state','source_coverage'])
@pytest.mark.parametrize('decision',['REJECTED','PENDING'])
def test_each_condition_field_review_dimension_blocks_request(axis,decision):
    s,_,_=setup();w=sheet(s);review=record(w)
    review['decisions']['queries.q1.semantics.'+c.FIELD][axis]=decision
    rejected=submit(s,review);e=d.prepare_reader(s,'q1',query_review=rejected['query_review'])
    assert e['request'] is None and not e['backend_called']


@pytest.mark.parametrize('defect',['omitted','null','blank','missing_refs','wrong_ref','duplicate_refs','inapplicable','missing_and_value','unknown_and_value'])
def test_bad_condition_state_or_reference_rejected_without_repair(defect):
    case,_,raw=draft();sem=raw['queries'][0]['semantics'];v=sem[c.FIELD]
    if defect=='omitted':sem.pop(c.FIELD)
    elif defect=='null':sem[c.FIELD]=None
    elif defect=='blank':v['value']='  '
    elif defect=='missing_refs':v['refs']=[]
    elif defect=='wrong_ref':v['refs']=['foreign']
    elif defect=='duplicate_refs':v['refs']*=2
    elif defect=='inapplicable':sem[c.FIELD]='NOT_APPLICABLE'
    elif defect=='missing_and_value':v.update(state='MISSING',reason='未定')
    else:v['state']='UNKNOWN'
    before=deepcopy(raw);s=receive(case,raw,short=False,profile=c.CONTRACT)
    assert 'report' not in intake.inspect(s) and d.prepare_reader(s,'q1')['request'] is None
    issues=diagnose(case,raw,response_contract=c.CONTRACT)
    assert issues and issues[0]['field_path']=='/queries/0/semantics/'+c.FIELD
    assert raw==before and s.candidate==before


@pytest.mark.parametrize('gap',['unknown','covariates_only','missing','standardized','undecided_average'])
def test_different_or_missing_target_does_not_inherit_r3_condition(gap):
    case,_,raw=draft();sem=raw['queries'][0]['semantics'];condition=sem[c.FIELD]
    if gap in ('unknown','covariates_only'):
        sem[c.FIELD]='UNKNOWN'
        if gap=='covariates_only':raw['common']['covariates']=[condition]
    elif gap=='missing':sem[c.FIELD]=dict(state='MISSING',reason='目标背景尚未决定',refs=condition['refs'])
    elif gap=='undecided_average':sem['standardization_distribution']=dict(state='MISSING',reason='按什么背景分布平均尚未决定',refs=condition['refs'])
    else:sem['standardization_distribution']=dict(condition,value='跨背景按明确目标分布平均')
    s=receive(case,raw,profile=c.CONTRACT);review=submit(s,record(sheet(s)))['query_review']
    e=d.prepare_reader(s,'q1',query_review=review)
    assert e['state']==('ADAPTER_NOT_CONNECTED' if gap=='standardized' else 'NEEDS_INPUT')
    assert e['request'] is None and not e['backend_called']


@pytest.mark.parametrize('decision',['PENDING','REJECTED','OMIT'])
def test_even_equal_condition_text_needs_independent_cross_stage_review(monkeypatch,decision):
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);a=approval_records(p)
    decisions=a['native_reviews'][r3.METHOD]['reading_review'].decisions
    if decision=='OMIT':decisions.pop(c.MATCH_DECISION)
    else:decisions[c.MATCH_DECISION]=decision
    monkeypatch.setattr(r3,'_compile',lambda *a:pytest.fail('review before compile'))
    r=d.execute(s,'q1',**o,**a)
    assert not r['backend_called'] and not r['independent_replay']


@pytest.mark.parametrize('defect',['sample_only','unknown_science','refused_science','post_treatment'])
def test_new_field_never_grants_a4_a5_or_timing_permission(defect):
    s,e,o=setup(**({'sample_only':True} if defect=='sample_only' else
                  {'exchangeability':None} if defect=='unknown_science' else
                  {'exchangeability':False} if defect=='refused_science' else {}))
    if defect=='post_treatment':o['candidate']['conditioning'].update(kind='OTHER',definition='采用工具后的实际需求')
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==('NEEDS_INPUT' if defect in ('sample_only','unknown_science') else 'ADAPTER_NOT_CONNECTED')
    assert not r['backend_called'] and r['mathematical_claim'] is None


def test_fact_recheck_preserves_context_and_requires_new_full_review():
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_fact_reading_revision import feedback,accept_changes
    s,e,o=setup();old=approval_records(d.inspect_methods(s,'q1',**o))
    o['candidate']['conditioning']['definition']='错误的目标背景，待复查'
    w=prepare_recheck(s,'q1',**o)['feedback_worksheet'];path='/conditioning/definition'
    fresh=prepare_recheck(s,'q1',**o,feedback=feedback(w,path=path,doc='conditioning'))
    assert fresh['reviewed_target_context']==e['reviewed_target_context']
    public=json.loads(fresh['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['public_field_constraints']==[dict(field_path=path,description=c.FACT_DESCRIPTION)]
    assert 'PRIVATE_REASON_NOT_SENT' not in fresh['request']['user']
    _,data=material();new=dict(query_review=o['query_review'],candidate=fact_reference(fresh,data),
        request_sha256=fresh['request_sha256'],reading_revision=fresh['reading_revision'])
    pending=d.inspect_methods(s,'q1',**new);assert pending['state']=='REVIEW_REQUIRED'
    new['change_review']=accept_changes(pending['reading_change_worksheet'])
    assert not d.execute(s,'q1',**new,**old)['backend_called']
    p=d.inspect_methods(s,'q1',**new);r=d.execute(s,'q1',**new,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']


def test_a0_recheck_exposes_owned_field_and_changed_condition_invalidates_review():
    from cfm_id.intake_reading_revision import prepare_recheck,review_changes
    from tests_gateway.test_reading_review_guards import feedback
    from tests_gateway.test_fact_reading_revision import accept_changes
    from tests_gateway.test_compact_short_refs import encode_fixture
    s,e,o=setup();w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet'];f=feedback(w)
    path='/queries/0/semantics/'+c.FIELD+'/value';f['issues'][0]['field_path']=path
    next_s=prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST')
    assert c.DESCRIPTION in intake.prepare_request(next_s)['user_prompt']
    case,_,raw=draft();raw['queries'][0]['semantics'][c.FIELD]['value']='改变后的目标背景，须重新核查'
    fresh=intake.receive_candidate(next_s,encode_fixture(next_s,raw),request_sha256=next_s.request_sha256)
    pending=intake.inspect(fresh);assert pending['state']=='REVIEW_REQUIRED'
    changes=pending['reading_change_worksheet'];assert any(c.FIELD in row['field_path'] for row in changes['changes'].values())
    accepted=review_changes(fresh,accept_changes(changes))
    assert d.prepare_reader(accepted,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'


def test_two_queries_keep_distinct_conditions_and_cannot_swap_reviews(tmp_path):
    case,data,raw=draft();second=deepcopy(raw['queries'][0]);second['goal']['value']+='另评价另一明确背景。'
    second['semantics'][c.FIELD]['value']='另一明确背景';raw['queries'].append(second)
    # This synthetic adversarial candidate is not claimed faithful to the source.
    s=receive(case,raw,profile=c.CONTRACT);first=submit(s,record(sheet(s)))['query_review']
    second_review=submit(s,record(sheet(s,'q2')),'q2')['query_review']
    e1=d.prepare_reader(s,'q1',query_review=first);e2=d.prepare_reader(s,'q2',query_review=second_review)
    assert e1['reviewed_target_context']!=e2['reviewed_target_context']
    assert d.prepare_reader(s,'q2',query_review=first)['state']=='CHECK_BLOCKED'
    intake.save(s,tmp_path/'session.json');restored=intake.restore(tmp_path/'session.json')
    assert d.prepare_reader(restored,'q2',query_review=second_review)==e2


def test_single_policy_reader_preserves_explicit_conditions_for_native_review():
    from tests_gateway.test_target_summary_contract import fixture
    case,raw=fixture();raw=wire(raw);sem=raw['queries'][0]['semantics'];sem[c.FIELD]=deepcopy(sem['target_population'])
    s=receive(case,raw,profile=c.CONTRACT);review=submit(s,record(sheet(s)))['query_review']
    result=d.prepare_reader(s,'q1',query_review=review)
    assert result['state']=='READY_TO_READ'
    assert result['reader_id']=='NETWORK_FIXED_POLICY_FACTS'
    actual=result['reviewed_target_context']['conditioning_context']
    assert actual['state']==sem[c.FIELD]['state'] and actual['value']==sem[c.FIELD]['value']
    assert actual['refs']==['s0001']  # Existing short-reference transport, same original source.
    assert c.admission(result['reviewed_target_context'],'UNREGISTERED_READER')==('ADAPTER_NOT_CONNECTED','CONDITIONED_TARGET_NOT_CONNECTED_TO_SELECTED_READER')
    sem[c.FIELD]='UNKNOWN';s=receive(case,raw,profile=c.CONTRACT);review=submit(s,record(sheet(s)))['query_review']
    assert d.prepare_reader(s,'q1',query_review=review)['state']=='READY_TO_READ'


@pytest.mark.parametrize('profile',['local-role-ownership-4',c.CONTRACT])
def test_omitted_optional_information_claim_is_unknown_not_an_exception(profile):
    case,data,raw=draft(sample_only=True)
    if profile!=c.CONTRACT:raw['queries'][0]['semantics'].pop(c.FIELD)
    assert 'available_information' not in raw['common']
    s=receive(case,raw,profile=profile);review=submit(s,record(sheet(s)))['query_review']
    e=d.prepare_reader(s,'q1',query_review=review)
    r=d.execute(s,'q1',query_review=review,candidate=fact_reference(e,data),
        request_sha256=e['request_sha256'],research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called']


@pytest.mark.parametrize('kind',['point','partial','dag'])
def test_unconditioned_nonlocal_targets_still_reach_native_result(monkeypatch,kind):
    from tests_gateway import test_owned_effect_reading as owned
    def accept(case,raw,short=True):
        value=owned.owned(raw)
        for q in value['queries']:q['semantics'][c.FIELD]='UNKNOWN'
        return receive(case,value,short=short,profile=c.CONTRACT)
    monkeypatch.setattr(owned.old,'received',accept)
    if kind=='dag':owned.old.test_dag_retains_original_wire_and_native_replay()
    else:owned.old.test_complete_policy_contrast_preserves_business_roles_and_replay(kind)


@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
def test_local_comparison_keeps_conditions_separate_from_peer_state(monkeypatch,kind):
    from tests_gateway import test_owned_effect_reading as owned
    from tests_gateway import test_scoped_effect_reading as scoped
    original=owned.receive
    def received(case,raw,**options):
        raw=deepcopy(raw)
        for q in raw['queries']:q['semantics'][c.FIELD]='UNKNOWN'
        return original(case,raw,**dict(options,profile=c.CONTRACT))
    monkeypatch.setattr(owned,'receive',received);monkeypatch.setattr(scoped,'contract',c)
    s,e,o=scoped.setup(monkeypatch,kind=kind,count=True)
    p=d.inspect_methods(s,'q1',**o);assert p['state']=='REVIEW_REQUIRED',p
    from examples.network_effect_dispatch_reference import approval_records as approvals
    r=d.execute(s,'q1',**o,**approvals(p))
    assert r['state']=='POINT' and r['independent_replay']
    assert e['reviewed_target_context']['conditioning_context']=='UNKNOWN'
    assert e['reviewed_local_request']['raw_query']['comparison_request']['shared_condition']!='UNKNOWN'
