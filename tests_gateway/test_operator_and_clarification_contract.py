"""Protocol consistency and clarification lifecycle; not model accuracy tests."""
from copy import deepcopy
import pytest
from jsonschema import Draft202012Validator

from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.compact_unified_contract import OPERATOR_CONTRACT as PROFILE
from cfm_id_llm.compact_evidence_contract import project
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.schemas import TargetKind
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_compact_evidence_slots import contrast_raw
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_intake_stop_review import uncertain, reviewed

EFFECTS = {'DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT', 'TOTAL_EFFECT', 'ATE', 'CATE'}
LEVELS = {'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN', 'FIXED_POLICY_VALUE',
          'STOCHASTIC_POLICY_VALUE', 'POLICY_OPTIMIZATION', 'INTERVENTIONAL_DISTRIBUTION'}
OPS = ('INTERVENTION_MINUS_COMPARATOR', 'COMPARATOR_MINUS_INTERVENTION',
       'UNSPECIFIED', 'NOT_APPLICABLE')


@pytest.mark.parametrize('kind',[v.value for v in TargetKind])
@pytest.mark.parametrize('operation',OPS)
def test_schema_and_runtime_accept_exact_same_target_operator_combinations(kind, operation):
    b, raw = fixture(); raw = wire(raw, operation)
    raw['queries'][0]['kind'] = kind
    schema = split_user(make_compact_request(b, a0_response_contract=PROFILE)[1])[2]
    valid = (operation != 'NOT_APPLICABLE' if kind in EFFECTS else
             operation == 'NOT_APPLICABLE' if kind in LEVELS else
             operation in ('UNSPECIFIED','NOT_APPLICABLE'))
    assert Draft202012Validator(schema).is_valid(raw) is valid
    from cfm_id_llm.evidence_refs import build_catalog
    old_wire = dict(raw, missing_information=[])
    if valid:
        project(old_wire, build_catalog(b))
    else:
        with pytest.raises(A0QualityValidationError) as exc:
            project(old_wire, build_catalog(b))
        assert exc.value.diagnostics['issues'][0]['path'] == ['queries',0,'comparison_order','operation']


def test_policy_conflict_keeps_precise_location_through_intake_and_reread():
    from cfm_id.intake_reading_revision import prepare_recheck
    b, raw = fixture(); raw = wire(raw, 'UNSPECIFIED'); raw['queries'][0]['kind'] = 'POLICY_OPTIMIZATION'
    s = receive(b, raw, profile=PROFILE); before=deepcopy(s.candidate)
    result = intake.inspect(s)
    assert result['state'] == 'READING_RECHECK_REQUIRED' and not result['core_called']
    assert result['reason_code'] == 'A0_INLINE_EVIDENCE_REJECTED'
    issue = result['diagnostics']['issues'][0]
    assert issue == dict(code='TARGET_OPERATOR_CONFLICT',
        path=['queries',0,'comparison_order','operation'],allowed_values=['NOT_APPLICABLE'])
    feedback = prepare_recheck(s, authority='SYNTHETIC_TEST')['feedback_worksheet']
    assert feedback['format_issues'][0]['field_path'] == '/queries/0/comparison_order/operation'
    assert 'NOT_APPLICABLE' in feedback['format_issues'][0]['allowed_literals']
    assert s.candidate == before and dispatch.prepare_reader(s,'q1')['request'] is None


def test_policy_choice_does_not_require_the_solution_list_as_an_input():
    b, raw = fixture(); raw = wire(raw)
    raw['queries'][0]['kind'] = 'POLICY_OPTIMIZATION'
    raw['queries'][0]['semantics']['intervention'] = 'UNKNOWN'
    new = intake.inspect(receive(b, raw, profile=PROFILE))
    old = intake.inspect(receive(b, raw, profile='inline-unified-contract-6'))
    assert not any(q['field']=='intervention' for q in new['wire_gate']['proposed_business_questions'])
    assert any(q['field']=='intervention' for q in old['wire_gate']['proposed_business_questions'])
    assert not new['core_called'] and not new['production_admission']
    assert new['report']['draft']['queries'][0]['semantics']['intervention']['value'] is None


@pytest.mark.parametrize('bad', ['missing', 'stale', 'wrong_type'])
def test_reference_binding_failure_is_located_but_never_filled(bad):
    from tests_gateway.test_compact_short_refs import setup, receive as receive_short
    from cfm_id.intake_reading_revision import prepare_recheck
    s, _ = setup(); raw = deepcopy(s.candidate)
    if bad == 'missing':
        raw.pop('reference_context')
    else:
        raw['reference_context'] = 'previous-request' if bad == 'stale' else 42
    s = receive_short(s, raw)
    report = intake.inspect(s)
    assert report['reason_code'] == 'A0_REFERENCE_CONTEXT_MISMATCH'
    assert report['state'] == 'READING_RECHECK_REQUIRED' and not report['core_called']
    assert report['diagnostics']['issues'][0]['path'] == ['reference_context']
    worksheet = prepare_recheck(s, authority='SYNTHETIC_TEST')['feedback_worksheet']
    assert worksheet['format_issues'] == [dict(field_path='/reference_context',
        error_code='missing' if bad == 'missing' else 'REFERENCE_CONTEXT_MISMATCH')]
    assert s.candidate == raw and dispatch.prepare_reader(s, 'q1')['request'] is None


@pytest.mark.parametrize('kind,phrase',[('DIRECT_EFFECT','按某个规则平均'),('SPILLOVER_EFFECT','本对象是否使用')])
def test_focused_target_questions_preserve_unknowns_and_require_source_check(kind, phrase):
    b, raw = fixture(); raw = wire(raw, 'UNSPECIFIED')
    raw['queries'][0]['kind'] = kind
    raw['queries'][0]['semantics']['neighbor_exposure'] = 'UNKNOWN'
    raw['queries'][0]['semantics']['comparator'] = 'UNKNOWN'
    raw['common']['exposure_mapping'] = 'UNKNOWN'
    s = receive(b, raw, profile=PROFILE); result=intake.inspect(s)
    q = next(x for x in result['wire_gate']['proposed_business_questions'] if x['field']=='neighbor_exposure')
    assert phrase in q['question'] and q['status']=='VERIFY_MISSING_IN_SOURCE_BEFORE_ASKING'
    assert not result['core_called'] and s.candidate['queries'][0]['semantics']['neighbor_exposure']=='UNKNOWN'


def two_gap_case():
    s=uncertain('三家门店都启用工具，只评价甲店，结果如何汇总和评价哪个时期尚未决定。')
    raw=deepcopy(s.candidate);raw['queries'][0]['semantics']['time_horizon']='UNKNOWN'
    return intake.receive_candidate(s,raw,request_sha256=s.request_sha256)


def test_batch_answers_use_reviewed_current_plan_and_clear_all_prior_admission(tmp_path):
    s=reviewed(two_gap_case());plan=intake.clarification_plan(s)
    assert len(plan['questions'])==2
    before=s.model_dump(mode='json')
    answers={q['clarification_id']: '这项还没有决定。' for q in plan['questions']}
    new=intake.append_replies(s,plan,answers)
    assert s.model_dump(mode='json')==before and new.revision==s.revision+1
    assert new.case.business_question==s.case.business_question
    assert new.candidate is new.reading_stop_review is new.reading_change_review is None
    assert new.history[-1]['previous_stop_review']==s.reading_stop_review
    assert len(new.clarifications)==2 and len(new.case.sources)==len(s.case.sources)+2
    assert all(d.text=='这项还没有决定。' for d in new.case.sources[-2:])
    assert all(c.kind=='ASSISTANT_CONTEXT_NOT_EVIDENCE' for c in new.clarifications)
    assert intake.inspect(new)['state']=='READING_REQUIRED' and not intake.inspect(new)['core_called']
    with pytest.raises(ValueError,match='STALE_INTAKE_RESPONSE'):
        intake.receive_candidate(new,s.candidate,request_sha256=s.request_sha256)
    with pytest.raises(ValueError,match='STALE_OR_CHANGED'):
        intake.append_replies(new,plan,answers)
    intake.save(new,tmp_path/'new.json');assert intake.restore(tmp_path/'new.json')==new


@pytest.mark.parametrize('bad',['unreviewed','unknown_id','blank','empty','changed_plan'])
def test_invalid_batch_never_appends_partial_replies(bad):
    s=two_gap_case() if bad=='unreviewed' else reviewed(two_gap_case())
    plan=intake.clarification_plan(s);answers={q['clarification_id']:'仍未确定。' for q in plan['questions']}
    before=s.model_dump(mode='json')
    if bad=='unknown_id':answers['invented']='仍未确定。'
    elif bad=='blank':answers[next(iter(answers))]=' '
    elif bad=='empty':answers={}
    elif bad=='changed_plan':plan['questions'][0]['question']='Assume everything needed.'
    with pytest.raises(ValueError):intake.append_replies(s,plan,answers)
    assert s.model_dump(mode='json')==before and not intake.inspect(s)['core_called']


def test_partly_known_fields_can_be_source_reviewed_without_becoming_unknown():
    from cfm_id.intake_stop_review import prepare_review,review_stop
    from tests_gateway.test_intake_stop_review import record as stop_record
    b,raw=fixture();raw=wire(raw);raw['queries'][0]['kind']='POLICY_OPTIMIZATION'
    s=receive(b,raw,profile=PROFILE);before=deepcopy(s.candidate)
    scope={'q1':['policy_assignment','aggregation']}
    w=prepare_review(s,authority='SYNTHETIC_TEST',target_fields=scope)['stop_worksheet']
    r=stop_record(w);r['target_fields']=scope
    checked=review_stop(s,r,authority='SYNTHETIC_TEST')
    assert checked.candidate==before and not intake.inspect(checked)['core_called']
    plan=intake.clarification_plan(checked)
    assert {q['field_path'] for q in plan['questions']} == {
        'queries.q1.semantics.policy_assignment','queries.q1.semantics.aggregation'}
    answers={q['clarification_id']:'还没有定好。' for q in plan['questions']}
    assert intake.append_replies(checked,plan,answers).candidate is None
    bad=deepcopy(r);bad['target_fields']={'q1':['policy_assignment']}
    with pytest.raises(ValueError,match='STALE'):
        review_stop(s,bad,authority='SYNTHETIC_TEST')


def test_unknown_direction_may_be_confirmed_as_gap_but_invalid_operator_cannot():
    from cfm_id.intake_stop_review import prepare_review,review_stop
    from tests_gateway.test_intake_stop_review import record as stop_record
    b,raw=fixture();raw=wire(raw,'UNSPECIFIED');raw['queries'][0]['kind']='DIRECT_EFFECT'
    raw['queries'][0]['semantics']['comparator']='UNKNOWN'
    raw['queries'][0]['semantics']['policy_assignment']='NOT_APPLICABLE'
    s=receive(b,raw,profile=PROFILE)
    w=prepare_review(s,authority='SYNTHETIC_TEST')['stop_worksheet']
    checked=review_stop(s,stop_record(w),authority='SYNTHETIC_TEST')
    plan=intake.clarification_plan(checked)
    assert any(q['field_path']=='queries.q1.comparison_order' for q in plan['questions'])
    assert intake.inspect(checked)['state']=='BUSINESS_CLARIFICATION_REQUIRED'
    assert not intake.inspect(checked)['core_called']
    raw['queries'][0]['comparison_order']['operation']='NOT_APPLICABLE'
    with pytest.raises(ValueError,match='VALID_COMPACT_REPORT'):
        prepare_review(receive(b,raw,profile=PROFILE),authority='SYNTHETIC_TEST')


def test_unknown_policy_constraints_are_a_review_task_not_an_asserted_missing_solution():
    b,raw=fixture();raw=wire(raw);raw['queries'][0]['kind']='POLICY_OPTIMIZATION'
    raw['queries'][0]['semantics']['policy_assignment']='UNKNOWN'
    s=receive(b,raw,profile=PROFILE);r=intake.inspect(s)
    actions=r['report']['query_quality'][0]['actions']
    assert any(a['code']=='POLICY_CHOICE_CONSTRAINTS_OPEN' for a in actions)
    assert not any(a['code']=='POLICY_ASSIGNMENT_SEMANTICS_OPEN' for a in actions)
    assert any(q['field']=='policy_assignment' for q in r['wire_gate']['proposed_business_questions'])
    assert not r['core_called'] and not r['production_admission']


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('partial','PARTIAL')])
def test_new_protocol_keeps_scientific_gate_and_independent_network_replay(kind,expected):
    from examples.network_contrast_dispatch_reference import fact_reference,approval_records
    b,data,raw=contrast_raw(kind);raw.pop('missing_information');s=receive(b,raw,profile=PROFILE)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    opts=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    r=dispatch.execute(s,'q1',**opts,**approval_records(p))
    assert r['state']==expected and r['independent_replay']
