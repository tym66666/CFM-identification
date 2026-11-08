"""Local enum presentation and field-owned citations preserve strict admission."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.intake_reading_revision import prepare_recheck
from cfm_id_llm import compact_unified_contract as unified
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.schemas import SourceDocument
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_unified_reading_contract import no_descriptions
from tests_gateway.test_compact_short_refs import encode_fixture

PROFILE=unified.WIRE_EVIDENCE_CONTRACT


@pytest.mark.parametrize('short',[False,True])
def test_local_enum_presentation_preserves_materials_types_and_review_definition(short):
    b,raw=fixture();opts=dict(a0_reference_contract='compact-source-selectors-1' if short else None)
    old=make_compact_request(b,a0_response_contract=unified.INFORMATION_CONTRACT,**opts)
    new=make_compact_request(b,a0_response_contract=PROFILE,**opts)
    _,a,sa,_=split_user(old[1]);_,z,sz,_=split_user(new[1])
    if short:
        assert a.pop('reference_context')!=z.pop('reference_context')
        sa['properties'].pop('reference_context');sz['properties'].pop('reference_context')
    assert a==z and old[2]==new[2]
    for model,name in [('CompactCommon','assignment_family'),('CompactQuery','kind')]:
        p=sz['$defs'][model]['properties'][name];d=sz['$defs'][p['$ref'].split('/')[-1]]
        assert p.pop('enum')==d['enum'] and p.pop('type')==d['type']=='string'
    assert no_descriptions(sa)==no_descriptions(sz)
    s=receive(b,wire(raw),short,profile=PROFILE);w=sheet(s)
    for path,model,name in [('common.assignment_family','CompactCommon','assignment_family'),
                            ('common.temporal_structure','CompactCommon','temporal_structure'),
                            ('queries.q1.kind','CompactQuery','kind')]:
        assert w['fields'][path]['definition']['wire_description']==sz['$defs'][model]['properties'][name]['description']
    assert dispatch.prepare_reader(s,'q1')['state']=='REVIEW_REQUIRED'


@pytest.mark.parametrize('model,name',[('CompactCommon','assignment_family'),('CompactQuery','kind')])
def test_every_enum_choice_and_wrong_shape_has_identical_schema_acceptance(model,name):
    b,_=fixture();old=split_user(make_compact_request(b,a0_response_contract=unified.INFORMATION_CONTRACT)[1])[2]
    new=split_user(make_compact_request(b,a0_response_contract=PROFILE)[1])[2]
    a=Draft202012Validator(dict(old['$defs'][model]['properties'][name],**{'$defs':old['$defs']}))
    z=Draft202012Validator(dict(new['$defs'][model]['properties'][name],**{'$defs':new['$defs']}))
    values=new['$defs'][model]['properties'][name]['enum']
    bad=[None,1,True,{},[],{'state':'STATED','value':values[0],'refs':['s0001']},'UNKNOWN_ENUM',values[0].lower()]
    assert all(a.is_valid(v) and z.is_valid(v) for v in values)
    assert all(not a.is_valid(v) and not z.is_valid(v) for v in bad)


@pytest.mark.parametrize('bad',['enum_claim','enum_null','enum_misspelled','invalid_ref','missing_with_value'])
def test_wrong_output_is_not_coerced_or_repaired(bad):
    b,raw=fixture();s=receive(b,wire(raw),True,profile=PROFILE);r=deepcopy(s.candidate)
    if bad=='enum_claim':r['common']['assignment_family']=dict(state='STATED',value='COMPLETE_RANDOMIZATION',refs=r['queries'][0]['goal']['refs'])
    elif bad=='enum_null':r['queries'][0]['kind']=None
    elif bad=='enum_misspelled':r['queries'][0]['kind']='FIXED_POLICY_MEANS'
    elif bad=='invalid_ref':r['queries'][0]['goal']['refs']=['s9999']
    else:r['common']['available_information']=dict(state='MISSING',reason='未给出',value='补造值',refs=r['queries'][0]['goal']['refs'])
    result=intake.receive_candidate(s,r,request_sha256=s.request_sha256)
    assert 'report' not in intake.inspect(result) and result.candidate==r
    assert dispatch.prepare_reader(result,'q1')['request'] is None


@pytest.mark.parametrize('include_own_time_ref',[False,True])
def test_separate_fragments_need_this_fields_own_coverage_and_independent_review(include_own_time_ref):
    b,raw=fixture();old_catalog=build_catalog(b)
    extra=SourceDocument(source_id='history_period',text='历史试点的记录时间是上个月，不能将这一时间替代下周的目标。')
    b=b.model_copy(update={'sources':[*b.sources,extra]});cat=build_catalog(b)
    refs={a['ref']:next(c['ref'] for c in cat if (c['source_id'],c['start'],c['end'])==(a['source_id'],a['start'],a['end'])) for a in old_catalog}
    def fixture_refs(value):
        if isinstance(value,dict):return {k:[refs[r] for r in v] if k=='refs' else fixture_refs(v) for k,v in value.items()}
        if isinstance(value,list):return [fixture_refs(v) for v in value]
        return value
    raw=fixture_refs(raw)  # New test material, never a model response repair.
    q=[c['ref'] for c in cat if c['source_id']=='business_question']
    h=[c['ref'] for c in cat if c['source_id']=='history_period']
    raw['common']['temporal_structure']=dict(state='STATED',value='历史试点在上个月，评价目标在下周',refs=h+q if include_own_time_ref else h)
    s=receive(b,wire(raw),False,profile=PROFILE);w=sheet(s)
    assert s.candidate['queries'][0]['semantics']['time_horizon']['refs']==q
    actual=w['fields']['common.temporal_structure']['actual_citations']
    assert {c['ref'] for c in actual}==set(h+q if include_own_time_ref else h)
    assert dispatch.prepare_reader(s,'q1')['state']=='REVIEW_REQUIRED'
    review=record(w)
    if not include_own_time_ref:review['decisions']['common.temporal_structure']['source_coverage']='REJECTED'
    out=submit(s,review);e=dispatch.prepare_reader(s,'q1',query_review=out['query_review'])
    assert e['state']==('READY_TO_READ' if include_own_time_ref else 'CHECK_BLOCKED')
    assert not e['backend_called'] and s.candidate['common']['temporal_structure']['refs']==(h+q if include_own_time_ref else h)


@pytest.mark.parametrize('path',['/common/assignment_family','/common/temporal_structure','/queries/0/kind'])
def test_recheck_keeps_public_local_shape_and_never_sends_private_expected_values(path):
    b,raw=fixture()
    raw['common']['assignment_family']='UNRESOLVED'
    raw['common']['temporal_structure']=dict(state='STATED',value='评价目标在下周',refs=raw['queries'][0]['goal']['refs'])
    s=receive(b,wire(raw),True,profile=PROFILE)
    w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    f=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',reviewer='PRIVATE_REVIEWER',
        evidence='PRIVATE_EXPECTED_VALUES_MUST_NOT_BE_SENT',issues=[dict(field_path=path,kind='OMITTED_OR_MISREAD',
            source_ids=list(w['source_catalog']),reason='PRIVATE_CORRECT_ANSWER_MUST_NOT_BE_SENT')])
    fresh=prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST');req=intake.prepare_request(fresh)
    assert 'PRIVATE_' not in req['system_prompt']+req['user_prompt']
    public=json.loads(req['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['field_role_constraints'][0]['field_path']==path
    assert 'JSON格式' in public['field_role_constraints'][0]['field_role']
    again=intake.receive_candidate(fresh,encode_fixture(fresh,wire(raw)),request_sha256=fresh.request_sha256)
    # Identical content needs semantic review, not a fabricated change review.
    assert intake.inspect(again)['state']=='SEMANTIC_REVIEW_REQUIRED' and not dispatch.prepare_reader(again,'q1')['backend_called']


def test_old_request_context_and_review_cannot_authorize_new_contract(tmp_path):
    b,raw=fixture();old=receive(b,wire(raw),True,profile=unified.INFORMATION_CONTRACT);new=receive(b,wire(raw),True,profile=PROFILE)
    r=intake.receive_candidate(new,old.candidate,request_sha256=new.request_sha256)
    assert intake.inspect(r)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'
    with pytest.raises(ValueError,match='STALE'):submit(new,record(sheet(old)))
    intake.save(new,tmp_path/'state.json');assert intake.restore(tmp_path/'state.json')==new


@pytest.mark.parametrize('bounds,expected',[ (('1/2','1/2'),'POINT'), (('1/4','3/4'),'PARTIAL')])
def test_native_network_result_still_requires_science_and_independent_replay(bounds,expected,monkeypatch):
    from tests_gateway import test_information_role_contract as fixture_module
    from examples.network_dispatch_reference import approval_records
    monkeypatch.setattr(fixture_module,'PROFILE',PROFILE)
    s,o=fixture_module.bounded_intake(center_bounds=bounds)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==expected and r['independent_replay'] and r['mathematical_claim']['sharp']
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


@pytest.mark.parametrize('negative',['bounds','sufficiency','sample','scope','extra'])
def test_negative_network_cases_still_stop_before_native_solver(negative,monkeypatch):
    from tests_gateway import test_information_role_contract as fixture_module
    monkeypatch.setattr(fixture_module,'PROFILE',PROFILE)
    fixture_module.test_missing_negative_or_extra_condition_never_reaches_solver(negative,monkeypatch)
