"""Exact compatibility is not semantic repair; audited intent has one owner."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as d,fact_reading_revision as revision
from cfm_id_llm import policy_action_compat as compat,policy_action_contract as strict
from cfm_id_llm.compact_wire_diagnostics import diagnose
from cfm_id_llm.compact_reference_contract import split_user
from jsonschema import Draft202012Validator
from tests_gateway.test_policy_interface_contracts import a0_case
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet,record,submit
from tests_gateway.test_reading_material_handoff import reviewed
from tests_gateway.test_fact_reading_revision import feedback,accept_changes
from examples.network_design_exposure_reference import material,fact_reference
from examples.network_dispatch_reference import approval_records


@pytest.mark.parametrize('family',['policy','contrast'])
def test_missing_direct_claim_is_located_without_repair_or_scientific_adoption(family):
    from cfm_id_llm.wire_type_diagnostics import diagnose as fact_diagnose
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    s,e,o=setup(family);raw=o['candidate']
    raw['mean_sufficiency'].update(status='NOT_STATED',source_ids=[],scope='UNKNOWN',covered_nodes=[],definition_refs=['study'])
    before=deepcopy(raw)
    rows=fact_diagnose(e,raw)
    assert rows[0]['field_path']=='/mean_sufficiency' and rows[0]['error_code']=='DIRECT_CLAIM_SOURCE_REQUIRED'
    with pytest.raises(ValueError,match='DIRECT_CLAIM_SOURCE_REQUIRED'):
        contract_for_entry(e).parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
    w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=revision.prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/mean_sufficiency',kind='WIRE_FORMAT_ERROR',doc='study'))
    assert r['state']=='READY_TO_READ' and not r['backend_called']
    assert r['reading_revision']['steps'][0]['candidate']==before==raw
    assert not r['reading_revision_receipt']['scientific_approval']
    assert 'DIRECT_CLAIM_SOURCE_REQUIRED' in r['request']['user']


def test_diagnostic_accepts_absence_and_sourced_dependency_without_supplying_evidence():
    from cfm_id_llm.wire_type_diagnostics import diagnose as fact_diagnose
    s,e,o=setup();raw=o['candidate']
    assert fact_diagnose(e,raw)==[]
    raw['mean_sufficiency'].update(status='NOT_STATED',source_ids=[],scope='UNKNOWN',covered_nodes=[],definition_refs=[])
    assert fact_diagnose(e,raw)==[]


def setup(family='policy',*,alias=True,reverse=False):
    case,raw=a0_case(family)
    if alias:raw['queries'][0]['semantics']['policy_assignment']=deepcopy(raw['queries'][0]['semantics']['intervention'])
    if reverse:raw['queries'][0]['comparison_order']['operation']='COMPARATOR_MINUS_INTERVENTION'
    s=receive(case,raw,profile=compat.CONTRACT)
    s=intake.configure_network_fact_contract(s,'network-policy-scopes-1')
    s=intake.configure_material_handoff(s)
    q=submit(s,record(sheet(s)))['query_review'];e=d.prepare_reader(s,'q1',query_review=q)
    assert e['state']=='READY_TO_READ',e
    _,data=material('D1','E5',family)
    if reverse:data['first'],data['second']=data['second'],data['first']
    c=fact_reference(e,data);c['assignment']['definition_refs']=['study']
    c['mean_sufficiency']['definition_refs']=['study']
    for endpoint in ([c['target']] if family=='policy' else [c['target']['first'],c['target']['second']]):endpoint['definition_refs']=['study']
    for row in c['information']:row.update(definition_refs=['study'],scope_status='DECLARED',scope_source_ids=list(row['source_ids']))
    return s,e,dict(query_review=q,candidate=c,request_sha256=e['request_sha256'])


@pytest.mark.parametrize('alias',[False,True])
def test_only_exact_alias_is_compatible_without_modifying_raw_or_old_protocol(alias):
    case,raw=a0_case();sem=raw['queries'][0]['semantics']
    if alias:sem['policy_assignment']=deepcopy(sem['intervention'])
    s=receive(case,raw,profile=compat.CONTRACT);before=deepcopy(s.candidate);r=intake.inspect(s)
    assert 'report' in r and s.candidate==before
    receipt=r['wire_gate']['policy_action_projection']
    assert receipt['contract']==compat.CONTRACT and bool(receipt['compatible_aliases'])==alias
    assert not receipt['raw_candidate_modified']
    Draft202012Validator(split_user(intake.prepare_request(s)['user_prompt'])[2]).validate(s.candidate)
    assert 'queries.q1.semantics.policy_assignment' not in sheet(s)['fields']
    old=receive(case,raw,profile=strict.CONTRACT)
    assert ('report' in intake.inspect(old))== (not alias)
    assert intake.prepare_request(old)['system_prompt']==intake.prepare_request(s)['system_prompt']


@pytest.mark.parametrize('defect',['paraphrase','opposite','status','citations','duplicate_refs','missing_owner'])
def test_conflicts_and_unsupported_equivalence_do_not_gain_precedence(defect):
    case,raw=a0_case('contrast');sem=raw['queries'][0]['semantics'];sem['policy_assignment']=deepcopy(sem['intervention'])
    other=sem['policy_assignment']
    if defect=='paraphrase':other['value']+='。'
    elif defect=='opposite':sem['policy_assignment']=deepcopy(sem['comparator'])
    elif defect=='status':other['state']='INTERPRETED'
    elif defect=='citations':other['refs']=deepcopy(raw['common']['analysis_unit']['refs'])
    elif defect=='duplicate_refs':other['refs']*=2
    else:sem.pop('intervention')
    s=receive(case,raw,profile=compat.CONTRACT);before=deepcopy(s.candidate)
    assert 'report' not in intake.inspect(s) and d.prepare_reader(s,'q1')['request'] is None and s.candidate==before
    # Diagnostics use canonical refs here; neither source borrowing nor text repair.
    rows=diagnose(case,raw,response_contract=compat.CONTRACT)
    assert any(x['error_code']=='POLICY_ALIAS_CONFLICT' for x in rows),rows


@pytest.mark.parametrize('family,reverse',[('policy',False),('contrast',False),('contrast',True)])
def test_one_reviewed_intent_survives_fact_stage_and_native_replay(family,reverse):
    s,e,o=setup(family,reverse=reverse);raw=deepcopy(o['candidate'])
    text=e['request']['user'].split('本次只读取下面选定子问题。')[1]
    focus=json.JSONDecoder().raw_decode(text[text.index('{'):])[0]['focus']
    target=focus['reviewed_policy_target'];assert 'semantics' not in focus and 'requested_comparison_or_policy' not in focus
    assert 'policy_assignment' not in json.dumps(focus) and not target['is_citable_source'] and not target['scientific_approval']
    if family=='contrast':
        owner='comparator' if reverse else 'intervention'
        assert target['first']['value']==s.candidate['queries'][0]['semantics'][owner]['value']
        assert target['operation']=='FIRST_MINUS_SECOND'
    o['source_review']=reviewed(e,raw,omitted=False);p=d.inspect_methods(s,'q1',**o)
    assert not d.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=d.execute(s,'q1',**o,**approval_records(p));assert r['state']=='POINT' and r['independent_replay'] and raw==o['candidate']


@pytest.mark.parametrize('defect',['pending_science','no_population','wrong_citation','alias_review_changed'])
def test_compatibility_and_intent_context_never_bypass_admission(defect):
    s,e,o=setup('contrast')
    if defect=='pending_science':o['candidate']['scientific_statements']['consistency']['status']='UNDECIDED'
    elif defect=='no_population':o['candidate']['information']=[]
    if defect=='alias_review_changed':
        value=s.model_dump(mode='json');value['candidate']['queries'][0]['semantics']['policy_assignment']['value']+='。'
        assert d.execute(value,'q1',**o)['backend_called'] is False;return
    review=reviewed(e,o['candidate'],omitted=False)
    if defect=='wrong_citation':review['decisions']['/target/first']['source_coverage']='REJECTED'
    r=d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)
    assert not r['backend_called'] and not r['independent_replay']


def test_recheck_rebuilds_same_intent_without_reusing_old_approvals(tmp_path):
    s,e,o=setup('contrast',reverse=True);o['source_review']=reviewed(e,o['candidate'],omitted=False)
    p=d.inspect_methods(s,'q1',**o);a=approval_records(p)
    args={k:v for k,v in o.items() if k!='source_review'}
    w=revision.prepare_recheck(s,'q1',**args)['feedback_worksheet']
    fresh=revision.prepare_recheck(s,'q1',**args,feedback=feedback(w,path='/target',doc='population'))
    assert fresh['reviewed_policy_request']==e['reviewed_policy_request']
    assert 'reviewed_policy_target' in fresh['request']['user']
    assert '原材料交接清单' in fresh['request']['user']
    assert not d.execute(s,'q1',**dict(o,request_sha256=fresh['request_sha256'],reading_revision=fresh['reading_revision']),**a)['backend_called']
    path=tmp_path/'intake.json';intake.save(s,path);assert intake.restore(path)==s


def guided_observational(*, profile=None, **kwargs):
    from tests_gateway.test_query_conditioning_contract import draft
    from examples.network_observational_policy_reference import fact_reference
    from cfm_id_llm.guided_policy_reading import CONTRACT
    case,data,raw=draft(**kwargs)
    raw['queries'][0]['semantics']['intervention']=raw['queries'][0]['semantics'].pop('policy_assignment')
    s=receive(case,raw,profile=profile or CONTRACT)
    q=submit(s,record(sheet(s)))['query_review'];e=d.prepare_reader(s,'q1',query_review=q)
    assert e['state']=='READY_TO_READ',e
    return s,e,dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])


@pytest.mark.parametrize('kwargs,expected',[
    ({},'POINT'),({'exchangeability':None},'NEEDS_INPUT'),
    ({'exchangeability':False},'ADAPTER_NOT_CONNECTED'),({'sample_only':True},'NEEDS_INPUT')])
def test_guided_owner_reaches_r3_without_granting_science(kwargs,expected):
    s,e,o=guided_observational(**kwargs);original=deepcopy(s.candidate)
    focus=json.JSONDecoder().raw_decode(e['request']['user'].split('本次只读取下面选定子问题。')[1].split('\n',1)[1])[0]['focus']
    assert 'reviewed_policy_target' in focus and 'semantics' not in focus
    assert 'policy_assignment' not in json.dumps(focus)
    assert not focus['reviewed_policy_target']['scientific_approval']
    assert e['reviewed_target_context']['conditioning_context']==original['queries'][0]['semantics']['conditioning_context']
    from cfm_id import fact_source_review as source
    from tests_gateway.test_fact_source_review import record as source_record
    o['source_review']=source_record(source.prepare(e,o['candidate']))
    plan=d.inspect_methods(s,'q1',**o)
    a=approval_records(plan) if plan.get('methods') else dict(research_protocol_selected=True)
    result=d.execute(s,'q1',**o,**a)
    assert result['state']==expected and result['independent_replay']==(expected=='POINT')
    assert s.candidate==original


def test_guided_r3_recheck_retains_owner_and_rejects_previous_sources():
    s,e,o=guided_observational()
    w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    fresh=revision.prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/target',doc='study'))
    assert fresh['reviewed_policy_request']==e['reviewed_policy_request']
    assert 'reviewed_policy_target' in fresh['request']['user']
    assert fresh['fact_binding_sha256']!=e['fact_binding_sha256']
    assert not d.execute(s,'q1',**dict(o,request_sha256=fresh['request_sha256'],reading_revision=fresh['reading_revision']),research_protocol_selected=True)['backend_called']


def test_guided_wire_keeps_existing_alias_and_schema_rules():
    from cfm_id_llm.guided_policy_reading import CONTRACT
    from cfm_id_llm.compact_formulator import make_compact_request
    case,raw=a0_case()
    a=make_compact_request(case,a0_response_contract=compat.CONTRACT)
    b=make_compact_request(case,a0_response_contract=CONTRACT)
    old_schema=split_user(a[1])[2];new_schema=deepcopy(split_user(b[1])[2])
    new_schema['$defs'].pop('GuidedConditioningClaim')
    for name in ('CompactSemantics','OrderedLocalSemantics','PolicyActionSemantics'):
        new_schema['$defs'][name]['properties']['conditioning_context']=deepcopy(
            old_schema['$defs'][name]['properties']['conditioning_context'])
    assert old_schema==new_schema
    assert a[0]!=b[0]
    s=receive(case,raw,profile=CONTRACT)
    assert 'report' in intake.inspect(s)
    bad=deepcopy(raw);bad['queries'][0]['semantics'].pop('intervention')
    missing=receive(case,bad,profile=CONTRACT)
    assert 'report' not in intake.inspect(missing)
    with pytest.raises(intake.IntakeError):
        intake.prepare_request(s.model_copy(update={'a0_response_contract':compat.CONTRACT}))


@pytest.mark.parametrize('kind,valid',[
    ('unknown_string',True),('unknown_empty',True),('unknown_refs',False),
    ('unknown_value',False),('implicit_unknown_refs',False),
    ('known',True),('known_no_refs',False),('known_blank',False),('duplicate_refs',False)])
def test_guided_conditioning_schema_and_parser_agree_without_answer_repair(kind,valid):
    from cfm_id_llm.guided_policy_reading import CONTRACT
    case,raw=a0_case();ref=raw['queries'][0]['semantics']['intervention']['refs'][0]
    values={
        'unknown_string':'UNKNOWN','unknown_empty':dict(state='UNKNOWN',value=None,refs=[]),
        'unknown_refs':dict(state='UNKNOWN',value=None,refs=[ref]),
        'unknown_value':dict(state='UNKNOWN',value='未指定背景',refs=[]),
        'implicit_unknown_refs':dict(refs=[ref]),
        'known':dict(state='STATED',value='原文指定背景',refs=[ref]),
        'known_no_refs':dict(state='STATED',value='原文指定背景',refs=[]),
        'known_blank':dict(state='STATED',value='   ',refs=[ref]),
        'duplicate_refs':dict(state='STATED',value='原文指定背景',refs=[ref,ref]),
    }
    raw['queries'][0]['semantics']['conditioning_context']=values[kind]
    s=receive(case,raw,profile=CONTRACT);before=deepcopy(s.candidate)
    schema=split_user(intake.prepare_request(s)['user_prompt'])[2]
    assert Draft202012Validator(schema).is_valid(s.candidate)==valid
    assert ('report' in intake.inspect(s))==valid
    assert s.candidate==before


def test_model_policy_output_separates_generated_view_from_old_client_alias(tmp_path):
    from cfm_id_llm import model_policy_output as model
    from cfm_id import intake_reading_revision as a0_revision
    from tests_gateway.test_reading_review_guards import feedback as a0_feedback
    for family in ('policy','contrast'):
        case,raw=a0_case(family);s=receive(case,raw,profile=model.CONTRACT)
        before=deepcopy(s.candidate);request=intake.prepare_request(s)
        schema=split_user(request['user_prompt'])[2];Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(before)
        assert 'policy_assignment' not in schema['$defs']['PolicyActionSemantics']['properties']
        assert 'CompactQuery' not in schema['$defs']  # unused legacy output branch
        # This field remains meaningful for other policy goal types.
        assert 'policy_assignment' in schema['$defs']['CompactSemantics']['properties']
        report=intake.inspect(s);projection=report['wire_gate']['policy_action_projection']
        assert projection['compatibility_view_generated'] and not projection['alias_accepted_from_model']
        sem=report['report']['draft']['queries'][0]['semantics']
        assert sem['intervention']==sem['policy_assignment']
        w=sheet(s);assert 'queries.q1.semantics.policy_assignment' not in w['fields']
        assert w['fields']['queries.q1.semantics.intervention']['actual_citations']
        q=submit(s,record(w))['query_review']
        fw=a0_revision.prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']
        f=a0_feedback(fw);f['issues'][0]['field_path']='/queries/0/semantics/intervention'
        reread=a0_revision.prepare_recheck(s,authority='SYNTHETIC_TEST',feedback=f)
        assert d.prepare_reader(reread,'q1',query_review=q)['state']!='READY_TO_READ'
        assert 'policy_assignment' not in split_user(intake.prepare_request(reread)['user_prompt'])[2]['$defs']['PolicyActionSemantics']['properties']
        alias=deepcopy(raw);alias['queries'][0]['semantics']['policy_assignment']=deepcopy(alias['queries'][0]['semantics']['intervention'])
        new=receive(case,alias,profile=model.CONTRACT)
        assert 'report' not in intake.inspect(new)
        assert not Draft202012Validator(schema).is_valid(new.candidate)
        assert 'report' in intake.inspect(receive(case,alias,profile=compat.CONTRACT))
        assert any(x['error_code']=='POLICY_DUPLICATE_OWNER_FORBIDDEN' for x in diagnose(case,alias,response_contract=model.CONTRACT))
        path=tmp_path/f'{family}.json';intake.save(s,path);assert intake.restore(path)==s
        assert before==s.candidate


def test_model_policy_output_preserves_unknown_refusal_and_source_review():
    from cfm_id_llm.model_policy_output import CONTRACT
    case,raw=a0_case();unknown=deepcopy(raw)
    unknown['queries'][0]['semantics']['intervention']='UNKNOWN'
    s=receive(case,unknown,profile=CONTRACT);r=intake.inspect(s)
    sem=r['report']['draft']['queries'][0]['semantics']
    assert sem['policy_assignment']['value'] is None and sem['intervention']['value'] is None
    assert not any(x['field']=='policy_assignment' for x in r['wire_gate']['proposed_business_questions'])
    for defect in ('missing','foreign_source'):
        bad=deepcopy(raw)
        if defect=='missing':bad['queries'][0]['semantics'].pop('intervention')
        else:bad['queries'][0]['semantics']['intervention']['refs']=['foreign']
        s=receive(case,bad,profile=CONTRACT,short=False)
        assert 'report' not in intake.inspect(s) and d.prepare_reader(s,'q1')['request'] is None
    s=receive(case,raw,profile=CONTRACT);w=sheet(s)
    for axis in ('field_role','value_state','source_coverage'):
        review=record(w);review['decisions']['queries.q1.semantics.intervention'][axis]='REJECTED'
        assert submit(s,review)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('kind',['point','partial'])
def test_model_policy_output_keeps_joint_difference_math_and_replay(kind):
    from cfm_id_llm.model_policy_output import CONTRACT
    from examples import network_contrast_dispatch_reference as contrast
    from tests_gateway.test_inline_evidence_slots import wire
    from cfm_id import fact_source_review as source
    from tests_gateway.test_fact_source_review import record as source_record
    case,data=contrast.material(kind)
    raw=wire(contrast.a0_reference(case),operation='INTERVENTION_MINUS_COMPARATOR')
    sem=raw['queries'][0]['semantics'];sem['intervention']=sem.pop('policy_assignment');sem['conditioning_context']='UNKNOWN'
    s=receive(case,raw,profile=CONTRACT)
    s=intake.configure_network_fact_contract(s,'network-source-selections-mean-orders-1')
    q=submit(s,record(sheet(s)))['query_review'];e=d.prepare_reader(s,'q1',query_review=q)
    facts=contrast.fact_reference(e,data);before=deepcopy(facts)
    o=dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'],source_review=source_record(source.prepare(e,facts)))
    p=d.inspect_methods(s,'q1',**o);result=d.execute(s,'q1',**o,**approval_records(p))
    assert result['state']==kind.upper() and result['independent_replay'] and facts==before
    if kind=='partial':assert result['mathematical_claim']['sharp']
    rejected=deepcopy(o);rejected['candidate']['scientific_statements']['consistency']['status']='UNDECIDED'
    assert not d.execute(s,'q1',**rejected,research_protocol_selected=True)['backend_called']


def test_model_policy_output_r3_positive_missing_and_refused_conditions():
    from cfm_id_llm.model_policy_output import CONTRACT
    from cfm_id import fact_source_review as source
    from tests_gateway.test_fact_source_review import record as source_record
    for kwargs,expected in [({},'POINT'),({'exchangeability':None},'NEEDS_INPUT'),
                            ({'exchangeability':False},'ADAPTER_NOT_CONNECTED'),({'sample_only':True},'NEEDS_INPUT')]:
        s,e,o=guided_observational(profile=CONTRACT,**kwargs)
        o['source_review']=source_record(source.prepare(e,o['candidate']))
        plan=d.inspect_methods(s,'q1',**o)
        args=approval_records(plan) if plan.get('methods') else dict(research_protocol_selected=True)
        result=d.execute(s,'q1',**o,**args)
        assert result['state']==expected and result['independent_replay']==(expected=='POINT')
