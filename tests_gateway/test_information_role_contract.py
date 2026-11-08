"""Information roles and source-only rechecks, without mathematical changes."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id import intake_reading_revision as revision
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import compact_unified_contract as unified
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.evidence_refs import build_catalog
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_unified_reading_contract import no_descriptions
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_compact_short_refs import encode_fixture

PROFILE = unified.INFORMATION_CONTRACT


@pytest.mark.parametrize('short', [False, True])
def test_information_roles_keep_schema_original_materials_and_pending_review(short):
    b, raw = fixture()
    options = dict(a0_reference_contract='compact-source-selectors-1' if short else None)
    old = make_compact_request(b,a0_response_contract=unified.STRUCTURE_CONTRACT,**options)
    new = make_compact_request(b,a0_response_contract=PROFILE,**options)
    _,op,oschema,_=split_user(old[1]);_,np,nschema,_=split_user(new[1])
    if short:
        assert op.pop('reference_context')!=np.pop('reference_context')
        oschema['properties'].pop('reference_context');nschema['properties'].pop('reference_context')
    assert op==np and old[2]==new[2] and no_descriptions(oschema)==no_descriptions(nschema)
    s=receive(b,wire(raw),short,profile=PROFILE)
    assert sheet(s)['original_materials']==b.model_dump(mode='json')
    for name in ('analysis_unit','outcome','sample_data_description','available_information'):
        definition=sheet(s)['fields']['common.'+name]['definition']
        assert definition['meaning']+' '+definition['excludes']==nschema['$defs']['CompactCommon']['properties'][name]['description']
    assert not intake.inspect(s)['core_called']
    assert dispatch.prepare_reader(s,'q1')['state']=='REVIEW_REQUIRED'


@pytest.mark.parametrize('path', ['common.analysis_unit','common.available_information'])
def test_semantically_wrong_value_is_preserved_until_independent_rejection(path):
    b,raw=fixture();name=path.split('.')[1]
    raw['common'][name]=dict(state='STATED',value='任务完成事件；另行采用的均值界限',refs=raw['common']['analysis_unit']['refs'])
    s=receive(b,wire(raw),profile=PROFILE);before=deepcopy(s.candidate)
    audit=record(sheet(s));audit['decisions'][path]['field_role']='REJECTED'
    reviewed=submit(s,audit)
    e=dispatch.prepare_reader(s,'q1',query_review=reviewed['query_review'])
    assert e['state']=='CHECK_BLOCKED' and e['request'] is None and not e['backend_called']
    assert s.candidate==before


@pytest.mark.parametrize('state',['UNKNOWN','MISSING'])
def test_unknown_or_explicitly_missing_information_is_not_filled_from_science(state):
    b,raw=fixture()
    raw['common']['available_information']='UNKNOWN' if state=='UNKNOWN' else dict(
        state='MISSING',reason='原文明确未提供总体信息',refs=raw['common']['analysis_unit']['refs'])
    s=receive(b,wire(raw),profile=PROFILE)
    field=sheet(s)['fields']['common.available_information']
    assert field['state']==state and field['candidate']==s.candidate['common']['available_information']
    assert not intake.inspect(s)['core_called']


@pytest.mark.parametrize('profile',[None,unified.STRUCTURE_CONTRACT,PROFILE])
def test_recheck_sends_only_current_public_field_roles_and_no_private_reason(profile,tmp_path):
    b,raw=fixture();raw['common']['analysis_unit']['value']='门店的准时开门事件'
    s=receive(b,raw if profile is None else wire(raw),profile=profile)
    w=revision.prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    f=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',
        reviewer='PRIVATE_REVIEWER',evidence='PRIVATE_EVIDENCE_MUST_STAY_LOCAL',
        issues=[dict(field_path='/common/analysis_unit/value',kind='OMITTED_OR_MISREAD',
            source_ids=list(w['source_catalog']),reason='PRIVATE_EXPECTED_VALUE_AND_ANSWER_MUST_STAY_LOCAL')])
    fresh=revision.prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST')
    req=intake.prepare_request(fresh)
    text=req['system_prompt']+req['user_prompt']
    assert all(v not in text for v in ('PRIVATE_REVIEWER','PRIVATE_EVIDENCE','PRIVATE_EXPECTED_VALUE'))
    public=json.loads(req['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert ('field_role_constraints' in public)==(profile==PROFILE)
    if profile==PROFILE:
        role=public['field_role_constraints'][0]
        schema=split_user(intake.prepare_request(s)['user_prompt'])[2]
        assert role['field_role']==schema['$defs']['CompactCommon']['properties']['analysis_unit']['description']
        assert set(role)=={'field_path','field_role'} and role['field_path']=='/common/analysis_unit/value'
    assert fresh.case==s.case and fresh.reading_revision['steps'][0]['candidate']==s.candidate
    assert fresh.candidate is None
    intake.save(fresh,tmp_path/'state.json');assert intake.restore(tmp_path/'state.json')==fresh
    _,correct=fixture()
    received=intake.receive_candidate(fresh,encode_fixture(fresh,correct if profile is None else wire(correct)),request_sha256=fresh.request_sha256)
    assert intake.inspect(received)['state']=='REVIEW_REQUIRED'
    assert not dispatch.prepare_reader(received,'q1')['backend_called']


def bounded_intake(**kwargs):
    from examples.network_bounded_dispatch_reference import case,reference
    b,_=case(**kwargs);cat=build_catalog(b)
    def claim(value,doc='business_question'):
        return dict(state='STATED',value=value,refs=[r['ref'] for r in cat if r['source_id']==doc])
    docs=b.source_map()
    raw=dict(common=dict(analysis_unit=claim('服务网点','study'),treatment=claim('使用AI','study'),
        outcome=claim('本周任务是否按时完成','study'),unit_network=claim(docs['network'],'network'),
        available_information=claim(docs['information'],'information')),
        queries=[dict(goal=claim(b.business_question),kind='FIXED_POLICY_VALUE',semantics=dict(
            target_population=claim('全部这些网点'),intervention=claim('所有网点使用AI'),
            policy_assignment=claim('所有网点使用AI'),aggregation=claim('网点等权平均按时完成率'),
            time_horizon=claim('本周','study'),comparator='NOT_APPLICABLE'))])
    s=receive(b,wire(raw),profile=PROFILE)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    return s,dict(query_review=q,candidate=reference(e,**kwargs),request_sha256=e['request_sha256'])


@pytest.mark.parametrize('bounds,expected,interval',[
    (('1/2','1/2'),'POINT',['1/2','1/2']),
    (('1/4','3/4'),'PARTIAL',['13/28','15/28']),
    (('0','1'),'PARTIAL',['3/7','4/7'])])
def test_same_target_and_information_keep_native_point_and_sharp_bounds(bounds,expected,interval):
    from examples.network_dispatch_reference import approval_records
    s,o=bounded_intake(center_bounds=bounds)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    plan=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(plan))
    assert r['state']==expected and r['independent_replay']
    assert r['mathematical_claim']['interval']==interval and r['mathematical_claim']['sharp']
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


@pytest.mark.parametrize('negative',['bounds','sufficiency','sample','scope','extra'])
def test_missing_negative_or_extra_condition_never_reaches_solver(negative,monkeypatch):
    from cfm_id import bounded_policy_solver
    def forbidden(*args,**kwargs):raise AssertionError('Premature mathematical call')
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    s,o=bounded_intake(extra=negative=='extra',missing_scope=negative=='scope')
    raw=o['candidate']
    if negative=='bounds':raw['bounded_model']['bounds'][0]['lower']=None
    elif negative=='sufficiency':raw['mean_sufficiency']['value']=None
    elif negative=='sample':
        raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    before=deepcopy(raw)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==('ADAPTER_NOT_CONNECTED' if negative=='extra' else 'NEEDS_INPUT')
    assert not r['backend_called'] and not r['answers'] and r['mathematical_claim'] is None
    assert raw==before


def test_old_candidate_and_reviews_stay_bound_to_old_information_contract():
    b,raw=fixture()
    old=receive(b,wire(raw),profile=unified.STRUCTURE_CONTRACT)
    new=receive(b,wire(raw),profile=PROFILE)
    r=intake.receive_candidate(new,old.candidate,request_sha256=new.request_sha256)
    assert intake.inspect(r)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    with pytest.raises(ValueError,match='STALE'):
        submit(new,record(sheet(old)))
    assert ReadingConfig(a0_response_contract=PROFILE).a0_response_contract==PROFILE
    with pytest.raises(ValueError,match='CURRENT_TARGET_SEMANTICS'):
        ReadingConfig(a0_response_contract=PROFILE,target_summary_contract='target-summary-1')


def test_business_packets_preserve_complete_sources_and_never_send_reference_answers():
    from cfm_id_llm.schemas import BusinessCase
    base=Path(__file__).parents[1]/'evaluation/network_partial_roles'
    public=json.loads((base/'public.json').read_text(encoding='utf8'))['cases']
    private=json.loads((base/'research_references.json').read_text(encoding='utf8'))
    assert set(public)==set(private['references']) and private['not_for_model_input']
    assert len(public['plain_narrow']['sources'])==len(public['task_units']['sources'])==1
    for data in public.values():
        b=BusinessCase.model_validate(data)
        s=intake.start_configured(b,ReadingConfig(a0_response_contract=PROFILE))
        payload=split_user(intake.prepare_request(s)['user_prompt'])[1]
        assert payload['business_question']==data['business_question']
        assert payload['sources']==data['sources']
        assert not {'references','native','spec','interval','not_for_model_input'} & set(payload)
