"""Public field rules, source fidelity and mathematical admission stay separate."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm.network_information_contract import CONTRACT, make_request
from cfm_id_llm.network_reading_contract import make_request as old_request
from cfm_id_llm.network_statement_reading import parse_selection
from cfm_id_llm.wire_type_diagnostics import diagnose
from tests_gateway.test_network_reading_contract import setup as old_setup
from tests_gateway.test_fact_reading_revision import feedback, accept_changes
from tests_gateway.test_network_statement_reading import as_selection, to_wire
from examples.network_bounded_dispatch_reference import reference
from examples.network_dispatch_reference import candidate, approval_records
from examples.business_dispatch_reference import approve


def setup(kind='partial', **kwargs):
    previous, _, _ = old_setup(kind, **kwargs)
    s = intake.configure_network_fact_contract(previous, CONTRACT)
    q = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    raw = (reference(e, **kwargs) if kind == 'partial' else
           candidate(e, **(dict(design='D1', sufficiency=False) if kind == 'r1b' else {})))
    return s, e, dict(query_review=q, candidate=as_selection(to_wire(raw, e)), request_sha256=e['request_sha256'])


def schema(entry):
    return Draft202012Validator(json.JSONDecoder().raw_decode(entry['request']['user'])[0]['output_schema'])


@pytest.mark.parametrize('operator,availability,cell_kind,valid,code', [
    ('FINITE_SAMPLE','FINITE_SAMPLE','empty',True,None),
    ('FINITE_SAMPLE','FINITE_SAMPLE','value',False,'SIGNATURE_CELLS_WITH_OTHER_OPERATOR'),
    ('NODE_SIGNATURE_MEANS','FINITE_SAMPLE','value',False,'EXACT_VALUE_WITH_NONEXACT_INFORMATION'),
    ('NODE_SIGNATURE_MEANS','UNKNOWN','value',False,'EXACT_VALUE_WITH_NONEXACT_INFORMATION'),
    ('NODE_SIGNATURE_MEANS','SYMBOLIC_POPULATION_OPERATOR','null',True,None),
    ('NODE_SIGNATURE_MEANS','EXACT_POPULATION_VALUE','value',True,None),
    ('UNKNOWN','UNKNOWN','empty',True,None),
    ('FULL_JOINT_LAW','SYMBOLIC_POPULATION_OPERATOR','empty',True,None),
    ('NODE_FULL_LAW','SYMBOLIC_POPULATION_OPERATOR','empty',True,None),
    ('FINITE_SAMPLE','FINITE_SAMPLE','assignment',False,'ASSIGNMENT_CELLS_WITH_OTHER_OPERATOR'),
])
def test_schema_and_parser_agree_without_repair(operator, availability, cell_kind, valid, code):
    _, e, o = setup();raw=o['candidate'];info=raw['information'][0]
    cells=deepcopy(info['signature_cells'])
    info.update(operator=operator,availability=availability,signature_cells=[],assignment_cells=[])
    if cell_kind in ('null','value'):
        info['signature_cells']=cells
        if cell_kind=='null':
            for c in cells:c['value']=None
    if cell_kind=='assignment':info['assignment_cells']=[[0]*len(raw['study']['nodes'])]
    before=deepcopy(raw)
    assert schema(e).is_valid(raw) is valid
    if valid:
        parsed=parse_selection(e['bundle'],raw,binding=e['fact_binding_sha256'])
        for projected, original in zip(parsed['facts']['information'],raw['information']):
            assert {k:v for k,v in projected.items() if k!='source_ids'}=={k:v for k,v in original.items() if k!='source_ids'}
            assert projected['source_ids']==[parsed['reference_binding']['aliases'][k] for k in original['source_ids']]
    else:
        with pytest.raises(ValueError,match=code):parse_selection(e['bundle'],raw,binding=e['fact_binding_sha256'])
        assert code in {d['error_code'] for d in diagnose(e,raw)}
    assert raw==before


def test_opt_in_preserves_original_sources_wire_fields_and_a0(tmp_path):
    prior, e0, o0=old_setup();s,e,o=setup()
    # Same material, but independently created checkpoints; use one lineage.
    s=intake.configure_network_fact_contract(prior,CONTRACT)
    assert intake.prepare_request(s)==intake.prepare_request(prior) and s.candidate==prior.candidate
    assert dispatch.prepare_reader(s,'q1',query_review=o0['query_review'])['state']=='CHECK_BLOCKED'
    intake.save(s,tmp_path/'new.json');assert intake.restore(tmp_path/'new.json')==s
    b=old_request(e['bundle'],binding=e['fact_binding_sha256']);n=make_request(e['bundle'],binding=e['fact_binding_sha256'])
    old=json.loads(b['user']);new=json.loads(n['user'])
    assert {k:v for k,v in old.items() if k!='output_schema'}=={k:v for k,v in new.items() if k!='output_schema'}
    assert old['output_schema']['$defs']['Information']['required']==new['output_schema']['$defs']['Information']['required']
    assert old['output_schema']['$defs']['Information']['properties']['operator']==new['output_schema']['$defs']['Information']['properties']['operator']
    assert 'allOf' not in old['output_schema']['$defs']['Information']
    assert old_request(e['bundle'],binding=e['fact_binding_sha256'])==b


def test_generated_diagnostic_is_opt_in_and_does_not_send_candidate_values():
    s,e,o=setup();raw=o['candidate'];raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    before=deepcopy(raw);rows=diagnose(e,raw)
    assert {r['error_code'] for r in rows}=={'SIGNATURE_CELLS_WITH_OTHER_OPERATOR','EXACT_VALUE_WITH_NONEXACT_INFORMATION'}
    assert all(r['field_path']=='/information/0/signature_cells' for r in rows)
    old=dict(e,network_fact_contract='network-source-selections-roles-1')
    assert diagnose(old,raw)==[]
    assert raw['study']['nodes'][0] not in json.dumps(rows,ensure_ascii=False)
    sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path=rows[0]['field_path'],kind='WIRE_FORMAT_ERROR',doc='information'))
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['wire_format_constraints']==rows and public['previous_candidate']==before
    assert 'PRIVATE_REASON_NOT_SENT' not in r['request']['user']
    assert r['network_fact_contract']==CONTRACT and not r['backend_called']
    assert raw==before and not r['reading_revision_receipt']['scientific_approval']
    forged=feedback(sheet,path='/information/0/availability',kind='WIRE_FORMAT_ERROR',doc='information')
    assert prepare_recheck(s,'q1',**o,feedback=forged)['state']=='CHECK_BLOCKED'


def test_samples_remain_in_cited_materials_and_cannot_enter_math():
    s,e,o=setup();raw=o['candidate'];info=raw['information'][0]
    info.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    raw['bounded_model']['listed_means_are_complete_information']['value']=None
    assert schema(e).is_valid(raw)
    # This tests the field/dispatch contract only; the fixture source is not
    # scientifically approved as a newly authored sample business case.
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called'] and r['mathematical_claim'] is None
    assert r['facts']['information'][0]['availability']=='FINITE_SAMPLE'
    assert r['bundle']==e['bundle'] and info['source_ids']


@pytest.mark.parametrize('kind',['r1b','r2','partial'])
def test_existing_positive_routes_still_need_science_and_replay(kind):
    s,e,o=setup(kind);assert schema(e).is_valid(o['candidate'])
    assert dispatch.execute(s,'q1',**o,research_protocol_selected=True)['state']=='REVIEW_REQUIRED'
    p=dispatch.inspect_methods(s,'q1',**o);a=approval_records(p)
    row=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
    whole=business_case.execute_case(s,{'q1':row},case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert whole['state']=='ALL_QUERIES_IDENTIFIED'
    r=whole['results'][0]['result'];assert r['independent_replay']
    assert r['state']==('PARTIAL' if kind=='partial' else 'POINT')
    if kind=='partial':assert r['mathematical_claim']['sharp'] and r['mathematical_claim']['interval']==['3/7','4/7']
    assert not whole['production_admission'] and not whole['estimation_handoff_allowed']


@pytest.mark.parametrize('extra',[False,True])
def test_format_repair_cannot_hide_unknown_or_real_constraints(extra):
    kwargs=dict(extra=True) if extra else dict(missing_scope=True)
    s,e,o=setup(**kwargs);o['candidate']['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path='/information/0/signature_cells',kind='WIRE_FORMAT_ERROR',doc='information'))
    # Adversarial fixture: satisfies syntax while erasing a genuine condition.
    new=as_selection(to_wire(reference(r,**kwargs),r));new['additional_restrictions']=[]
    new['bounded_model']['no_additional_coupling_constraints']['value']=True
    opts=dict(query_review=o['query_review'],candidate=new,request_sha256=r['request_sha256'],reading_revision=r['reading_revision'])
    pending=dispatch.execute(s,'q1',**opts,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    sheet=pending['reading_change_worksheet'];rev=accept_changes(sheet)
    for k,v in sheet['changes'].items():
        if '/no_additional_coupling_constraints/value' in v['field_path']:rev['decisions'][k]['disposition']='REJECTED'
    result=dispatch.execute(s,'q1',**opts,change_review=rev,research_protocol_selected=True)
    assert result['state']=='READING_RECHECK_REQUIRED' and not result['backend_called']


def test_source_recheck_does_not_send_field_rules_without_explicit_format_selection():
    s,e,o=setup();o['candidate']['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path='/information',doc='information'))
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert set(public)=={'kind','previous_candidate','issues'}
