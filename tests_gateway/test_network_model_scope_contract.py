"""Information completeness is not outcome-table completeness or a license."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm import network_model_scope_contract as current
from cfm_id_llm.network_fact_protocols import network_fact_protocol
from cfm_id_llm.network_information_contract import CONTRACT as OLD, make_request as old_request
from cfm_id_llm.wire_type_diagnostics import diagnose
from tests_gateway.test_network_information_contract import setup as before_setup
from tests_gateway.test_network_statement_reading import to_wire, as_selection
from tests_gateway.test_fact_reading_revision import feedback
from examples.business_dispatch_reference import approve
from examples.network_bounded_dispatch_reference import reference
from examples.network_dispatch_reference import approval_records


def setup(**kwargs):
    old,e0,o0=before_setup(**kwargs)
    s=intake.configure_network_fact_contract(old,current.CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=as_selection(to_wire(reference(e,**kwargs),e))
    return s,e,dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])


def without_descriptions(value):
    if isinstance(value,dict):return {k:without_descriptions(v) for k,v in value.items() if k!='description'}
    if isinstance(value,list):return [without_descriptions(v) for v in value]
    return value


def test_opt_in_request_preserves_wire_sources_and_exact_parser():
    s,e,o=setup();old=old_request(e['bundle'],binding=e['fact_binding_sha256'])
    new=current.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    a=json.loads(old['user']);b=json.loads(new['user'])
    assert without_descriptions(a)==without_descriptions(b)
    assert network_fact_protocol(OLD).parse is network_fact_protocol(current.CONTRACT).parse
    assert old_request(e['bundle'],binding=e['fact_binding_sha256'])==old
    assert Draft202012Validator(b['output_schema']).is_valid(o['candidate'])
    assert current.INFORMATION_SCOPE==b['output_schema']['$defs']['BoundedModel']['properties']['listed_means_are_complete_information']['description']
    assert current.FREE_MEANS==b['output_schema']['properties']['unresolved']['description']
    assert intake.prepare_request(s)['system_prompt']


def test_configuration_keeps_a0_and_invalidates_old_downstream_review(tmp_path):
    old,e,o=before_setup();new=intake.configure_network_fact_contract(old,current.CONTRACT)
    assert new.candidate==old.candidate and intake.prepare_request(new)==intake.prepare_request(old)
    assert dispatch.prepare_reader(new,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
    intake.save(new,tmp_path/'new.json');assert intake.restore(tmp_path/'new.json')==new
    q=approve(dispatch.prepare_reader(new,'q1')['query_worksheet'])
    assert dispatch.execute(new,'q1',query_review=q,candidate=o['candidate'],request_sha256=e['request_sha256'])['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('bounds,state,interval',[
    (('1/2','1/2'),'POINT',['1/2','1/2']),
    (('1/4','3/4'),'PARTIAL',['13/28','15/28']),
    (('0','1'),'PARTIAL',['3/7','4/7'])])
def test_incomplete_table_with_explicit_complete_model_retains_sharp_endpoints(bounds,state,interval):
    s,e,o=setup(center_bounds=bounds)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==state and r['independent_replay'] and r['mathematical_claim']['sharp']
    assert r['mathematical_claim']['interval']==interval
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


@pytest.mark.parametrize('gap',['complete_unknown','extra_interval','bounds','sufficiency','sample','extra'])
def test_typed_missing_or_extra_information_stays_blocked_without_solver(gap,monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**k:pytest.fail('Unexpected mathematical call'))
    s,e,o=setup(extra=gap=='extra');r=o['candidate'];b=r['bounded_model']
    if gap=='complete_unknown':b['listed_means_are_complete_information']['value']=None
    elif gap=='extra_interval':
        b['listed_means_are_complete_information']['value']=False
        r['additional_restrictions']=[dict(source_ids=r['information'][0]['source_ids'],text='Known population interval retained; synthetic interface test, not an adopted fact.')]
    elif gap=='bounds':b['bounds'][0]['lower']=None
    elif gap=='sufficiency':r['mean_sufficiency']['status']='NOT_ADOPTED'
    elif gap=='sample':r['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    original=deepcopy(r)
    out=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert out['state'] in ('NEEDS_INPUT','ADAPTER_NOT_CONNECTED')
    assert not out['backend_called'] and not out['answers'] and out['mathematical_claim'] is None
    assert r==original


@pytest.mark.parametrize('disposition,expected',[
    ('PENDING','REVIEW_REQUIRED'),('MATERIAL_GAP','NEEDS_INPUT'),
    ('READING_ERROR','READING_RECHECK_REQUIRED'),('DEFER_TO_MATHEMATICS','REVIEW_REQUIRED')])
def test_notes_never_self_approve_or_rewrite_the_candidate(disposition,expected):
    s,e,o=setup();raw=o['candidate']
    raw['unresolved']=[dict(source_ids=raw['information'][0]['source_ids'],text='Whether this fixed target follows from the supplied information is a question for mathematics.')]
    original=deepcopy(raw);p=dispatch.inspect_methods(s,'q1',**o);w=p['note_review_worksheet']
    note=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',reviewer='test_only',
        evidence='Synthetic interface decisions, not a live source approval.',decisions={n:dict(disposition=disposition,reason='Exercise independent note review while retaining complete raw source and typed data.',source_ids=list(w['source_catalog'])) for n in w['notes']})
    result=dispatch.execute(s,'q1',**o,note_review=note,research_protocol_selected=True)
    assert result['state']==expected and not result['backend_called'] and raw==original


def test_recheck_keeps_sample_diagnostics_and_does_not_send_private_answers():
    s,e,o=setup();r=o['candidate'];r['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    rows=diagnose(e,r)
    assert {x['error_code'] for x in rows}=={'SIGNATURE_CELLS_WITH_OTHER_OPERATOR','EXACT_VALUE_WITH_NONEXACT_INFORMATION'}
    w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    fresh=prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/information/0/signature_cells',kind='WIRE_FORMAT_ERROR',doc='information'))
    assert fresh['network_fact_contract']==current.CONTRACT and not fresh['backend_called']
    assert current.INFORMATION_SCOPE in fresh['request']['system']
    assert 'PRIVATE_REASON_NOT_SENT' not in fresh['request']['user']
