"""Ordered local wire, exact source review and unchanged native proof boundary.

All candidates/reviews here are synthetic references, not LLM accuracy evidence.
"""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm import ordered_comparison_contract as ordered
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.evidence_refs import build_catalog
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_compact_short_refs import encode_fixture


def local_fixture(kind='DIRECT_EFFECT', reverse=False):
    from examples.network_effect_dispatch_reference import material
    case,data=material()
    qid='q1' if kind=='DIRECT_EFFECT' else 'q2'
    goal=data['questions'][qid]
    if kind=='LOCAL_TOTAL_EFFECT':
        replacement='自己启用且合作对象过半启用，与自己未启用且合作对象至多一半启用相比，本周顾客平均等待分钟数相差多少？前者减后者。'
        case=case.model_copy(update=dict(business_question=case.business_question.replace(goal,replacement)))
        goal=replacement
    if reverse:
        replacement=goal.replace('前者减后者','后者减前者')
        case=case.model_copy(update=dict(business_question=case.business_question.replace(goal,replacement)))
        goal=replacement
    catalog=build_catalog(case)
    def claim(value,doc):
        return dict(state='STATED',value=value,refs=[r['ref'] for r in catalog if r['source_id']==doc])
    common=dict(analysis_unit=claim(data['unit'],'study'),treatment=claim(data['treatment'],'study'),
        outcome=claim(data['outcome'],'study'),assignment_family='INDEPENDENT_BERNOULLI',
        assignment_law=claim(data['docs']['assignment'],'assignment'),unit_network=claim(data['docs']['network'],'network'),
        exposure_mapping=claim(data['docs']['exposure'],'exposure'),network_pretreatment_status=claim('网络在处理前固定','network'),
        available_information=claim(data['docs']['information'],'information'),covariates=[])
    first,second={'DIRECT_EFFECT':('自己启用','自己未启用'),
        'SPILLOVER_EFFECT':('自己未启用且合作对象过半启用','自己未启用且合作对象至多一半启用'),
        'LOCAL_TOTAL_EFFECT':('自己启用且合作对象过半启用','自己未启用且合作对象至多一半启用')}[kind]
    if reverse:first,second=second,first
    raw=dict(common=common,queries=[dict(kind=kind,goal=claim(goal,'business_question'),semantics=dict(
        target_population=claim(data['docs']['population'],'population'),aggregation=claim('评价名单内等权平均','population'),
        neighbor_exposure=claim('同伴过半启用' if kind=='DIRECT_EFFECT' else '同伴过半与至多一半的比较','business_question'),
        time_horizon=claim('同一周','context'),policy_assignment='NOT_APPLICABLE',
        standardization_distribution=claim(data['docs']['remaining'],'remaining')),
        comparison_expression=dict(form='ORDERED_DIFFERENCE',first=claim(first,'business_question'),
            second=claim(second,'business_question'),refs=claim(goal,'business_question')['refs']))])
    return case,data,raw


def received(case,raw,short=True):
    return receive(case,raw,short=short,profile=ordered.CONTRACT)


def execution(kind='DIRECT_EFFECT',reverse=False):
    from examples.network_effect_dispatch_reference import fact_reference
    case,data,raw=local_fixture(kind,reverse);s=received(case,raw)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['state']=='READY_TO_READ'
    facts=fact_reference(e,data)
    if kind=='SPILLOVER_EFFECT':
        facts['target'].update(kind=kind)
        facts['target']['first'].update(own=0,exposure=1)
        facts['target']['second'].update(own=0,exposure=0)
    if kind=='LOCAL_TOTAL_EFFECT':
        facts['target'].update(kind=kind)
        facts['target']['first'].update(own=1,exposure=1)
        facts['target']['second'].update(own=0,exposure=0)
    if reverse:facts['target']['first'],facts['target']['second']=facts['target']['second'],facts['target']['first']
    return s,e,dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'])


@pytest.mark.parametrize('kind',ordered.LOCAL_KINDS)
@pytest.mark.parametrize('reverse',[False,True])
def test_positions_survive_projection_review_and_native_replay(kind,reverse):
    from examples.network_effect_dispatch_reference import approval_records
    case,_,raw=local_fixture(kind,reverse);s=received(case,raw);before=deepcopy(s.candidate)
    schema=split_user(make_compact_request(case,a0_response_contract=ordered.CONTRACT)[1])[2]
    assert Draft202012Validator(schema).is_valid(raw)
    report=intake.inspect(s)['report']['draft']['queries'][0]['semantics']
    expression=raw['queries'][0]['comparison_expression']
    assert report['intervention']['value']==expression['first']['value']
    assert report['comparator']['value']==expression['second']['value']
    w=sheet(s)
    assert not any(p.endswith(('.semantics.intervention','.semantics.comparator','.comparison_order')) for p in w['fields'])
    for name in ordered.RULES:
        item=w['fields']['queries.q1.comparison_expression.'+name]
        assert item['actual_citations'] and item['definition']['wire_description']==ordered.description(ordered.RULES[name])
    assert s.candidate==before
    s,e,o=execution(kind,reverse);p=dispatch.inspect_methods(s,'q1',**o)
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']
    assert r['mathematical_claim']['target']['first']==[o['candidate']['target']['first'][k] for k in ('own','exposure')]


@pytest.mark.parametrize('bad',['missing_expression','missing_first','missing_second','missing_refs','empty_refs','duplicate_refs',
    'invented_refs','bad_form','legacy_order','legacy_intervention','legacy_comparator','extra_expression',
    'null_first','na_first','na_object','empty_claim_refs','mixed_missing','unknown_value','unknown_with_refs'])
def test_malformed_or_mixed_wire_is_blocked_with_actual_location(bad):
    from cfm_id.intake_reading_revision import prepare_recheck
    case,_,raw=local_fixture();q=raw['queries'][0];e=q['comparison_expression']
    if bad=='missing_expression':q.pop('comparison_expression')
    elif bad.startswith('missing_'):e.pop(bad.removeprefix('missing_'))
    elif bad=='empty_refs':e['refs']=[]
    elif bad=='duplicate_refs':e['refs']*=2
    elif bad=='invented_refs':e['refs']=['invented']
    elif bad=='bad_form':e['form']='NOT_APPLICABLE'
    elif bad=='legacy_order':q['comparison_order']=dict(operation='UNSPECIFIED',refs=e['refs'])
    elif bad.startswith('legacy_'):q['semantics'][bad.removeprefix('legacy_')]='UNKNOWN'
    elif bad=='extra_expression':e['secret_instruction']='DO_NOT_ECHO_THIS_VALUE'
    elif bad=='null_first':e['first']=None
    elif bad=='na_first':e['first']='NOT_APPLICABLE'
    elif bad=='na_object':e['first']=dict(state='NOT_APPLICABLE')
    elif bad=='empty_claim_refs':e['first']['refs']=[]
    elif bad=='mixed_missing':e['first'].update(state='MISSING',reason='未定')
    elif bad=='unknown_value':e['first']['state']='UNKNOWN'
    elif bad=='unknown_with_refs':e['first'].pop('value');e['first']['state']='UNKNOWN'
    before=deepcopy(raw);s=received(case,raw,False);r=intake.inspect(s)
    assert 'report' not in r and not r['core_called'] and s.candidate==before
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    issues=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet']['format_issues']
    assert issues and issues[0]['field_path'].startswith('/queries/0/')
    assert 'DO_NOT_ECHO_THIS_VALUE' not in json.dumps(issues)


@pytest.mark.parametrize('missing',['first','second','direction'])
@pytest.mark.parametrize('state',['UNKNOWN','MISSING'])
def test_missing_end_or_unknown_order_never_fills_or_executes(missing,state):
    case,_,raw=local_fixture();e=raw['queries'][0]['comparison_expression']
    if missing=='direction':e['form']='UNSPECIFIED'
    else:e[missing]='UNKNOWN' if state=='UNKNOWN' else dict(state='MISSING',reason='该端状态尚未决定',refs=e['refs'])
    s=received(case,raw);before=deepcopy(s.candidate);r=intake.inspect(s)
    assert 'report' in r and not r['core_called']
    assert dispatch.prepare_reader(s,'q1')['request'] is None
    if missing=='direction':
        assert any(x['code']=='COMPARISON_DIRECTION_UNRESOLVED' for x in r['wire_gate']['issues'])
        assert any(x['field']=='comparison_order' for x in r['wire_gate']['proposed_business_questions'])
    else:
        field='intervention' if missing=='first' else 'comparator'
        assert r['report']['draft']['queries'][0]['semantics'][field]['value'] is None
    assert s.candidate==before


def test_rejected_endpoint_cannot_hide_behind_top_level_approval_and_review_is_bound():
    case,_,raw=local_fixture();s=received(case,raw);w=sheet(s);r=record(w)
    r['decisions']['queries.q1.comparison_expression.first']['source_coverage']='REJECTED'
    assert submit(s,r)['state']=='CHECK_BLOCKED'
    q=submit(s,record(w))['query_review'];changed=deepcopy(s.candidate)
    changed['queries'][0]['comparison_expression']['first']['value']+='新的条件'
    newer=intake.receive_candidate(s,changed,request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(newer,'q1',query_review=q)['request'] is None
    assert all(d['source_coverage']=='PENDING' for d in sheet(newer)['decisions'].values())


def test_reread_exposes_new_raw_path_without_private_answer_and_requires_change_review():
    from cfm_id.intake_reading_revision import prepare_recheck
    from tests_gateway.test_reading_review_guards import feedback
    case,_,raw=local_fixture();s=received(case,raw)
    w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet'];f=feedback(w)
    path='/queries/0/comparison_expression/first';f['issues'][0]['field_path']=path
    newer=prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST');request=intake.prepare_request(newer)
    public=json.loads(request['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['field_role_constraints']==ordered.recheck_field_roles([path])
    assert 'PRIVATE_REASON_STAYS_LOCAL' not in request['user_prompt']
    raw['queries'][0]['comparison_expression']['first']['value']+='（重读）'
    fresh=intake.receive_candidate(newer,encode_fixture(newer,raw),request_sha256=newer.request_sha256)
    assert intake.inspect(fresh)['state']=='REVIEW_REQUIRED'
    assert dispatch.prepare_reader(fresh,'q1')['request'] is None
    with pytest.raises(intake.IntakeError):intake.receive_candidate(newer,s.candidate,request_sha256=s.request_sha256)


@pytest.mark.parametrize('negative,expected',[('sample','NEEDS_INPUT'),('pending','NEEDS_INPUT'),('refused','ADAPTER_NOT_CONNECTED'),('source','CHECK_BLOCKED')])
def test_ordered_wire_does_not_bypass_science_information_or_source_review(negative,expected):
    from examples.network_effect_dispatch_reference import approval_records
    s,e,o=execution()
    if negative=='sample':
        o['candidate']['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
    elif negative in ('pending','refused'):
        o['candidate']['scientific_statements']['consistency']['status']='UNDECIDED' if negative=='pending' else 'NOT_ADOPTED'
    p=dispatch.inspect_methods(s,'q1',**o)
    a=approval_records(p) if 'plan_worksheet' in p else dict(research_protocol_selected=True)
    if negative=='source':
        for review in a['native_reviews'].values():review['reading_review'].decisions['source_entailment']='REJECTED'
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==expected and not r['backend_called'] and not r['independent_replay']


@pytest.mark.parametrize('kind',['point','partial'])
def test_complete_policy_contrast_preserves_business_roles_and_replay(kind):
    from tests_gateway.test_compact_evidence_slots import contrast_raw
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    case,data,raw=contrast_raw(kind);raw.pop('missing_information');s=received(case,raw)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    o=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==kind.upper() and r['independent_replay']
    assert 'queries.q1.comparison_order' in sheet(s)['fields']
    mixed=deepcopy(raw);mixed['queries'][0]['comparison_expression']={}
    assert 'report' not in intake.inspect(received(case,mixed))


def test_dag_retains_original_wire_and_native_replay():
    from tests_gateway.test_business_intake_compact import scenario
    from examples.business_dispatch_reference import approvals
    case,raw,facts=scenario();s=received(case,wire(raw));s=intake.configure_fact_format(s,'source_hash')
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['reader_id']=='VARIABLE_DAG_FACTS'
    o=dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approvals(p))
    assert r['state']=='POINT' and r['independent_replay']


def test_mixed_queries_keep_distinct_raw_review_paths_and_source_context():
    case,_,raw=local_fixture();nonlocal_query=deepcopy(raw['queries'][0])
    nonlocal_query['kind']='FIXED_POLICY_VALUE'
    expression=nonlocal_query.pop('comparison_expression')
    nonlocal_query['comparison_order']=dict(operation='NOT_APPLICABLE',refs=expression['refs'])
    nonlocal_query['semantics'].update(intervention=expression['first'],comparator='NOT_APPLICABLE',policy_assignment=expression['first'])
    raw['queries'].append(nonlocal_query)
    s=received(case,raw)
    assert 'queries.q1.comparison_expression.first' in sheet(s,'q1')['fields']
    assert 'queries.q2.comparison_order' in sheet(s,'q2')['fields']
    assert not any('comparison_expression' in p for p in sheet(s,'q2')['fields'])
    changed=deepcopy(s.candidate);changed['reference_context']='c'+'0'*64
    rejected=intake.receive_candidate(s,changed,request_sha256=s.request_sha256)
    assert intake.inspect(rejected)['reason_code']=='A0_REFERENCE_CONTEXT_MISMATCH'


def test_nonlocal_schema_and_parser_operator_rules_remain_identical():
    from cfm_id_llm.schemas import TargetKind
    from cfm_id_llm.comparison_operator_contract import allowed_operations
    from tests_gateway.test_target_summary_contract import fixture
    case,base=fixture()
    schema=split_user(make_compact_request(case,a0_response_contract=ordered.CONTRACT)[1])[2]
    Draft202012Validator.check_schema(schema)
    for kind in TargetKind:
        if kind.value in ordered.LOCAL_KINDS:continue
        for operation in ('INTERVENTION_MINUS_COMPARATOR','COMPARATOR_MINUS_INTERVENTION','UNSPECIFIED','NOT_APPLICABLE'):
            raw=wire(base,operation);raw['queries'][0]['kind']=kind.value
            expected=operation in allowed_operations(kind.value)
            assert Draft202012Validator(schema).is_valid(raw)==expected,(kind,operation)
            assert ('report' in intake.inspect(received(case,raw)))==expected,(kind,operation)
