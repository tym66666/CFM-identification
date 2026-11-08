"""Policy wire ownership, information scope and diagnostic/native boundaries."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator, ValidationError as SchemaError
from pydantic import ValidationError
from cfm_id import business_intake as intake, business_dispatch as dispatch, fact_source_review as source
from cfm_id import intake_reading_revision as a0_revision, fact_reading_revision as revision
from cfm_id_llm import policy_action_contract as action, policy_scope_reading as scope
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.compact_wire_diagnostics import diagnose as a0_diagnose
from cfm_id_llm.wire_type_diagnostics import diagnose
from examples.network_design_exposure_reference import material, a0_reference
from examples.network_dispatch_reference import approval_records
from tests_gateway.test_inline_evidence_slots import wire, receive
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_policy_definition_refs import setup
from tests_gateway.test_fact_source_review import record as source_record
from tests_gateway.test_fact_reading_revision import feedback, accept_changes


def a0_case(family='policy'):
    case,data=material('D1','E5',family);raw=wire(a0_reference(case,data),
        operation='NOT_APPLICABLE' if family=='policy' else 'INTERVENTION_MINUS_COMPARATOR')
    sem=raw['queries'][0]['semantics'];sem['conditioning_context']='UNKNOWN'
    refs=raw['queries'][0]['goal']['refs']
    def claim(z):return dict(state='STATED',value='；'.join(n+('启用' if t else '不启用') for n,t in zip(data['nodes'],z)),refs=refs)
    sem['intervention']=claim(data['first']);sem.pop('policy_assignment')
    if family=='contrast':sem['comparator']=claim(data['second'])
    return case,raw


@pytest.mark.parametrize('family',['policy','contrast'])
def test_one_primary_owner_drives_review_compatibility_view_and_recheck(family,tmp_path):
    case,raw=a0_case(family);s=receive(case,raw,profile=action.CONTRACT)
    before=deepcopy(s.candidate);report=intake.inspect(s);assert 'report' in report
    request=intake.prepare_request(s);schema=split_user(request['user_prompt'])[2]
    assert '完整政策的主方案放policy_assignment' not in request['system_prompt']
    assert request['system_prompt'].count('semantics.intervention是唯一主安排')==1
    Draft202012Validator(schema).validate(s.candidate)
    assert 'policy_assignment' not in schema['$defs']['PolicyActionSemantics']['properties']
    sem=report['report']['draft']['queries'][0]['semantics']
    assert sem['intervention']==sem['policy_assignment']
    w=sheet(s);assert 'queries.q1.semantics.policy_assignment' not in w['fields']
    assert w['fields']['queries.q1.semantics.intervention']['definition']['wire_description']==action.ACTION
    q=submit(s,record(w))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['state']=='READY_TO_READ'
    path=tmp_path/'saved.json';intake.save(s,path);assert intake.restore(path)==s
    fs=a0_revision.prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
    from tests_gateway.test_reading_review_guards import feedback as a0_feedback
    f=a0_feedback(fs);f['issues'][0]['field_path']='/queries/0/semantics/intervention'
    reread=a0_revision.prepare_recheck(s,authority='SYNTHETIC_TEST',feedback=f)
    assert action.ACTION in intake.prepare_request(reread)['user_prompt']
    assert dispatch.prepare_reader(reread,'q1',query_review=q)['state']!='READY_TO_READ'
    assert s.candidate==before


@pytest.mark.parametrize('defect',['duplicate','missing','foreign_source'])
def test_no_alias_precedence_or_hidden_completion(defect):
    case,raw=a0_case('contrast');sem=raw['queries'][0]['semantics']
    if defect=='duplicate':sem['policy_assignment']=deepcopy(sem['comparator'])
    elif defect=='missing':sem.pop('intervention')
    else:sem['intervention']['refs']=['foreign']
    before=deepcopy(raw);s=receive(case,raw,short=False,profile=action.CONTRACT)
    assert 'report' not in intake.inspect(s) and raw==before
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    if defect!='foreign_source':assert a0_diagnose(case,raw,response_contract=action.CONTRACT)


def test_unknown_primary_action_remains_unknown_and_asks_once():
    case,raw=a0_case();raw['queries'][0]['semantics']['intervention']='UNKNOWN'
    s=receive(case,raw,profile=action.CONTRACT);r=intake.inspect(s)
    sem=r['report']['draft']['queries'][0]['semantics']
    assert sem['intervention']['value'] is None and sem['policy_assignment']['value'] is None
    questions=r['wire_gate']['proposed_business_questions']
    assert any(q['field']=='intervention' for q in questions)
    assert not any(q['field']=='policy_assignment' for q in questions)


@pytest.mark.parametrize('axis',['field_role','value_state','source_coverage'])
def test_primary_source_review_still_blocks_each_dimension(axis):
    case,raw=a0_case();s=receive(case,raw,profile=action.CONTRACT);w=sheet(s);r=record(w)
    r['decisions']['queries.q1.semantics.intervention'][axis]='REJECTED'
    assert submit(s,r)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('family',['mean','contrast'])
@pytest.mark.parametrize('kind',['point','partial'])
def test_scope_wire_preserves_point_joint_partial_and_certificates(family,kind):
    s,e,o=setup(family,kind,scope.CONTRACT);before=deepcopy(o['candidate'])
    schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(before)
    o['source_review']=source_record(source.prepare(e,before));p=dispatch.inspect_methods(s,'q1',**o)
    assert p['evidence_dependencies']['information_scopes']
    result=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert result['state']==kind.upper() and result['independent_replay'] and o['candidate']==before
    if kind=='partial':assert result['mathematical_claim']['sharp']


def test_unspecified_sample_coverage_stays_empty_without_losing_known_population_law():
    s,e,o=setup('mean','point',scope.CONTRACT);raw=o['candidate']
    sample=deepcopy(raw['information'][0]);sample.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',
        scope_status='UNSPECIFIED',outcome_nodes=[],assignment_cells=[],signature_cells=[],scope_source_ids=[],definition_refs=[])
    raw['information'].append(sample);before=deepcopy(raw)
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay'] and raw==before
    assert p['evidence_dependencies']['information_scopes'][1]['outcome_nodes']==[]
    raw['information']=[sample]
    stopped=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert stopped['state']=='NEEDS_INPUT' and not stopped['backend_called']


@pytest.mark.parametrize('defect',['undeclared_names','scope_without_source','scope_is_roster','refused_science'])
def test_scope_and_scientific_negatives_remain_blocked(defect):
    s,e,o=setup('contrast','partial',scope.CONTRACT);raw=o['candidate'];info=raw['information'][0]
    if defect=='undeclared_names':info.update(scope_status='UNSPECIFIED',scope_source_ids=[])
    elif defect=='scope_without_source':info['scope_source_ids']=[]
    elif defect=='scope_is_roster':info['scope_source_ids']=raw['study']['source_ids']
    else:raw['scientific_statements']['consistency']['status']='NOT_ADOPTED'
    before=deepcopy(raw)
    if defect=='scope_is_roster':
        r=source_record(source.prepare(e,raw));r['decisions']['/information/0']['source_coverage']='REJECTED';o['source_review']=r
    stopped=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not stopped['backend_called'] and raw==before
    if defect in ('undeclared_names','scope_without_source'):
        schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
        assert list(Draft202012Validator(schema).iter_errors(raw)) and diagnose(e,raw)


@pytest.mark.parametrize('path,status,sources,code',[
 ('first_stage_exclusion','NOT_STATED',True,'FIRST_STAGE_EXCLUSION_SOURCE_STATE_REQUIRED'),
 ('first_stage_exclusion','UNDECIDED',False,'FIRST_STAGE_EXCLUSION_SOURCE_STATE_REQUIRED'),
 ('scientific_statements','NOT_STATED',True,'ABSENT_STATEMENT_HAS_NO_SOURCE_SELECTION'),
 ('scientific_statements','ADOPTED',False,'EXPLICIT_STATEMENT_REQUIRES_SOURCE_SELECTION'),
])
def test_state_source_pairing_has_same_schema_parser_and_public_diagnostic(path,status,sources,code):
    s,e,o=setup('contrast','point',scope.CONTRACT);raw=o['candidate']
    item=dict(status=status,source_ids=list(raw['study']['source_ids']) if sources else [])
    if path=='first_stage_exclusion':raw[path]=item;pointer='/'+path
    else:raw[path]['consistency']=item;pointer='/'+path+'/consistency'
    before=deepcopy(raw);schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    with pytest.raises(SchemaError):Draft202012Validator(schema).validate(raw)
    from cfm_id_llm.fact_wire_models import model_for
    with pytest.raises(ValidationError):model_for(e).model_validate(raw)
    rows=diagnose(e,raw);assert any(r['field_path']==pointer and r['error_code']==code and scope.STATE_RULE==r['description'] for r in rows)
    w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    f=feedback(w,path=pointer,doc='science').model_dump(mode='json');f['issues'][0]['kind']='WIRE_FORMAT_ERROR'
    next_entry=revision.prepare_recheck(s,'q1',**o,feedback=f)
    public=json.loads(next_entry['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert any(r['error_code']==code for r in public['wire_format_constraints'])
    assert raw==before


def test_scope_change_invalidates_source_and_math_reviews_and_unknown_errors_are_not_echoed():
    s,e,o=setup('mean','point',scope.CONTRACT);review=source_record(source.prepare(e,o['candidate']))
    o['source_review']=review;p=dispatch.inspect_methods(s,'q1',**o);approvals=approval_records(p)
    o['candidate']['information'][0]['scope_source_ids']=o['candidate']['study']['source_ids']
    assert not dispatch.execute(s,'q1',**o,**approvals)['backend_called']
    assert scope.validation_diagnostic({'ctx':{'error':ValueError('UNTRUSTED_PRIVATE_VALUE')}})=={}
