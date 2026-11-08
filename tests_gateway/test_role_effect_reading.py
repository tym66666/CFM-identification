"""Role-coordinate projection and real native checks, using synthetic references."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm import role_coordinate_contract as contract,role_effect_reading as facts
from cfm_id_llm.requested_change_contract import POSITIONS
from tests_gateway import test_ordered_comparison_contract as prior
from tests_gateway.test_requested_change_contract import converted
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet,record,submit
from examples.network_effect_dispatch_reference import approval_records


def setup(monkeypatch,amount='REDUCTION',kind='DIRECT_EFFECT',reverse=True,network_profile=None):
    def receiver(case,raw,short=True):
        from cfm_id_llm.compact_reference_contract import CONTRACT as SHORT
        from tests_gateway.test_compact_short_refs import encode_fixture
        session=intake.start(case,a0_response_contract=contract.CONTRACT,a0_reference_contract=SHORT if short else None,
            target_summary_contract='target-summary-3',network_fact_contract=network_profile)
        value=converted(raw,amount)
        return intake.receive_candidate(session,encode_fixture(session,value) if short else value,request_sha256=session.request_sha256)
    monkeypatch.setattr(prior,'received',receiver)
    s,e,o=prior.execution(kind,reverse)
    expected=deepcopy(o['candidate']['target']);target=o['candidate']['target']
    first,second=POSITIONS[amount]
    a,b=target.pop('first'),target.pop('second');target.pop('operation')
    target.update({first:a,second:b});o['candidate']['version']=facts.VERSION
    return s,e,o,expected


@pytest.mark.parametrize('amount',list(POSITIONS)[:-1])
@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('reverse',[False,True])
def test_same_roles_compile_reviewed_quantity_into_exact_native_target(monkeypatch,amount,kind,reverse):
    s,e,o,expected=setup(monkeypatch,amount,kind,reverse);before=deepcopy(o['candidate'])
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED'
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']
    for side in ('first','second'):
        assert r['mathematical_claim']['target'][side]==[expected[side][k] for k in ('own','exposure')]
    assert o['candidate']==before and p['reading_candidate']==before
    assert not p['role_compilation']['source_entailment_verified']
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator.check_schema(body['output_schema'])
    assert Draft202012Validator(body['output_schema']).is_valid(before)
    focus=json.loads(e['request']['user'].rsplit('\n',1)[1])['focus']['reviewed_business_roles']
    assert not focus['is_citable_source'] and not focus['scientific_approval']
    assert focus['reference']['value']==s.candidate['queries'][0]['comparison_request']['reference']['value']


@pytest.mark.parametrize('defect',['legacy_first','operation','quantity','missing_role','bool_coordinate','foreign_source','stale_context'])
def test_bad_role_wire_is_rejected_without_repair(monkeypatch,defect):
    from cfm_id_llm.wire_type_diagnostics import diagnose
    s,e,o,_=setup(monkeypatch);r=o['candidate'];t=r['target']
    if defect=='legacy_first':t['first']=t.pop('reference')
    elif defect=='operation':t['operation']='FIRST_MINUS_SECOND'
    elif defect=='quantity':t['quantity']='REDUCTION'
    elif defect=='missing_role':t.pop('evaluated')
    elif defect=='bool_coordinate':t['reference']['own']=True
    elif defect=='foreign_source':t['reference']['source_ids']=['invented']
    else:r['reference_context']='c'+'0'*12
    before=deepcopy(r);p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='CHECK_BLOCKED' and not p['backend_called'] and r==before
    if defect not in ('foreign_source','stale_context'):
        errors=diagnose(e,r);assert errors and any(x['field_path'].startswith('/target/') for x in errors)


@pytest.mark.parametrize('missing',['own','exposure'])
def test_missing_coordinate_stays_missing(monkeypatch,missing):
    s,e,o,_=setup(monkeypatch);o['candidate']['target']['reference'][missing]=None
    before=deepcopy(o['candidate']);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called'] and o['candidate']==before


def test_review_cannot_be_reused_after_quantity_change(monkeypatch):
    s,e,o,_=setup(monkeypatch);raw=deepcopy(s.candidate)
    raw['queries'][0]['comparison_request']['quantity']='INCREASE'
    changed=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(changed,'q1',query_review=o['query_review'])['request'] is None


@pytest.mark.parametrize('defect',['rejected_role','pending_science','real_restriction','sample_only'])
def test_role_compilation_grants_no_admission(monkeypatch,defect):
    s,e,o,_=setup(monkeypatch)
    if defect=='real_restriction':o['candidate']['additional_restrictions']=[dict(text='Additional real model bound',source_ids=o['candidate']['study']['source_ids'])]
    if defect=='sample_only':
        for info in o['candidate']['information']:info.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
    p=dispatch.inspect_methods(s,'q1',**o)
    approvals={}
    if p.get('methods'):
        approvals=approval_records(p);pair=next(iter(approvals['native_reviews'].values()))
        if defect=='rejected_role':pair['reading_review'].decisions['local_states_and_first_minus_second_direction']='REJECTED'
        if defect=='pending_science':pair['science_review'].decisions['consistency']='PENDING'
    r=dispatch.execute(s,'q1',**o,**(approvals or dict(research_protocol_selected=True)))
    assert not r['backend_called'] and not r['independent_replay']


@pytest.mark.parametrize('network_profile',[None,'network-source-selections-dependencies-1','network-source-selections-alignment-1'])
def test_recheck_keeps_roles_and_reports_actual_wire_locations(monkeypatch,network_profile):
    from cfm_id.fact_reading_revision import prepare_recheck
    s,e,o,_=setup(monkeypatch,network_profile=network_profile);w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    f=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',reviewer='Source reviewer',
        evidence='Private audit of roles, not substitute coordinates.',issues=[dict(field_path='/target/reference',
        kind='OMITTED_OR_MISREAD',source_ids=list(w['source_catalog'])[:1],reason='PRIVATE_DO_NOT_SEND; reread the source role.')])
    next_entry=prepare_recheck(s,'q1',**o,feedback=f)
    assert next_entry['request'] and 'PRIVATE_DO_NOT_SEND' not in next_entry['request']['user']
    assert 'reviewed_business_roles' in next_entry['request']['user']
    assert 'reviewed_ordered_target' not in next_entry['request']['user']
    assert next_entry['effect_fact_contract']==facts.VERSION
    body=json.JSONDecoder().raw_decode(next_entry['request']['user'])[0]
    rules=body.get('source_dependency_contract',{}).get('field_constraints',[])
    if network_profile is None:
        rules=body['role_coordinate_contract']['field_constraints']
        assert any(x['field_path']=='/target/reference' for x in rules)
        return
    assert any(x['field_path']=='/target/reference/source_ids' for x in rules)
    assert not any(x['field_path'].startswith(('/target/first','/target/second')) for x in rules)
    assert not dispatch.execute(s,'q1',**dict(o,reading_revision=next_entry['reading_revision']),research_protocol_selected=True)['backend_called']


@pytest.mark.parametrize('kind',['point','partial','dag'])
def test_other_readers_and_native_replays_unchanged(monkeypatch,kind):
    monkeypatch.setattr(prior,'received',lambda case,raw,short=True:receive(case,converted(raw),short=short,profile=contract.CONTRACT))
    if kind=='dag':prior.test_dag_retains_original_wire_and_native_replay()
    else:prior.test_complete_policy_contrast_preserves_business_roles_and_replay(kind)
