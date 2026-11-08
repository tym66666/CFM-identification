"""Reading/dispatch boundaries. Fixtures are not model accuracy measurements."""
from copy import deepcopy
import json
import pytest
from test_live_demo import reading_fixture, fixture_review
from demo.backend import automatic_review as audit, recovery
from cfm_id_llm.assumption_choices import AssumptionChoice, applicability


def choice(run, status, scope='CURRENT_STUDY'):
    return dict(condition='MEAN_EXPOSURE_SUFFICIENCY',status=status,scope=scope,
        source_ids=run.submission['candidate']['scientific_statements']['consistency']['source_ids'])


def ready(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    return engine,run


@pytest.mark.parametrize('status',['NOT_ADOPTED','UNDECIDED'])
def test_optional_choice_retained_without_question_but_still_needs_science(tmp_path,monkeypatch,status):
    engine,run=ready(tmp_path,monkeypatch)
    run.submission['candidate']['assumption_choices']=[choice(run,status)]
    before=deepcopy(run.submission['candidate']);engine._plan(run)
    assert any('assumption_choices' in p for p in run.review_sheets['source']['fields'])
    request,fields,sources=audit.request(run);body=json.loads(request['user_prompt'])
    assert body['method_requirements']['optional_condition_required'] is False
    engine._review(run,fixture_review(run))
    assert run.review_kind=='science' and run.result is None and not run.plan['clarification_questions']
    assert run.plan['assumption_choices_review']['retained']==[
        dict(condition='MEAN_EXPOSURE_SUFFICIENCY',status=status,required=False)]
    engine._review(run,fixture_review(run))
    assert run.result['state']=='POINT' and run.result['independent_replay']
    assert run.submission['candidate']==before
    assert run.result['assumption_choices_review']['retained'][0]['status']==status


@pytest.mark.parametrize('status',['ADOPTED','PROPOSED','ASSERTED_FALSE','CONFLICTING'])
def test_actual_model_assertions_are_not_discarded(tmp_path,monkeypatch,status):
    engine,run=ready(tmp_path,monkeypatch)
    run.submission['candidate']['assumption_choices']=[choice(run,status)]
    engine._plan(run);engine._review(run,fixture_review(run))
    assert run.result['state']=='ADAPTER_NOT_CONNECTED' and not run.result['backend_called']
    assert run.submission['candidate']['assumption_choices'][0]['status']==status


@pytest.mark.parametrize('status,expected',[('NOT_ADOPTED','ADAPTER_NOT_CONNECTED'),('UNDECIDED','NEEDS_INPUT')])
def test_required_condition_refused_or_undecided_still_blocks(tmp_path,monkeypatch,status,expected):
    engine,run=ready(tmp_path,monkeypatch)
    run.submission['candidate']['assumption_choices']=[choice(run,'NOT_ADOPTED')]
    run.submission['candidate']['scientific_statements']['consistency']['status']=status
    run.submission['candidate']['unresolved']=[]
    engine._plan(run);engine._review(run,fixture_review(run))
    assert run.result['state']==expected and not run.result['backend_called']
    assert run.submission['candidate']['scientific_statements']['consistency']['status']==status
    if status=='UNDECIDED':assert len(run.result['clarification_questions'])==1

def test_reader_and_auditor_share_residual_unknown_ownership(tmp_path,monkeypatch):
    from cfm_id_llm.network_effect_reading import RESIDUAL_ROLES
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    _,run=ready(tmp_path,monkeypatch)
    description=contract_for_entry(run.entry).model.model_json_schema()['properties']['unresolved']['description']
    request,_,_=audit.request(run);body=json.loads(request['user_prompt'])
    assert description==RESIDUAL_ROLES['unresolved']==body['field_definitions']['root']['unresolved']


def test_optional_nonadoption_never_cancels_a_genuine_extra_constraint(tmp_path,monkeypatch):
    engine,run=ready(tmp_path,monkeypatch)
    item=choice(run,'NOT_ADOPTED');run.submission['candidate']['assumption_choices']=[item]
    run.submission['candidate']['additional_restrictions']=[dict(
        text='另外要求所有门店的总体均值相等。',source_ids=item['source_ids'])]
    engine._plan(run);engine._review(run,fixture_review(run))
    assert run.result['reason_code']=='ADDITIONAL_EFFECT_MODEL_REQUIRES_SEPARATE_ADAPTER'
    assert '所有门店' in run.result['processing_explanation'] and not run.result['backend_called']


def test_choice_source_and_scope_are_not_guessed(tmp_path,monkeypatch):
    engine,run=ready(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='SOURCES'):AssumptionChoice.model_validate({**choice(run,'NOT_ADOPTED'),'source_ids':[]})
    run.submission['candidate']['assumption_choices']=[choice(run,'NOT_ADOPTED','UNKNOWN')]
    engine._plan(run);engine._review(run,fixture_review(run))
    assert run.result['state']=='NEEDS_INPUT' and not run.result['backend_called']
    assert any('是否适用于本次研究' in q for q in run.result['clarification_questions'])


def test_matching_compares_actual_requirements_not_the_assumption_name():
    c=AssumptionChoice(condition='MEAN_EXPOSURE_SUFFICIENCY',status='NOT_ADOPTED',scope='CURRENT_STUDY',source_ids=['s1'])
    assert not applicability([c],required_conditions=set())['blocked']
    assert applicability([c],required_conditions={c.condition})['blocked']
    assert applicability([c,c],required_conditions=set())['blocked']==['CONFLICTING_ASSUMPTION_CHOICES']


def test_automatic_recovery_is_not_recorded_as_human_review(tmp_path,monkeypatch):
    engine,run=ready(tmp_path,monkeypatch);run.automatic_review=True
    run.submission['candidate']['additional_restrictions']=[dict(text='不额外采用同伴均值充分性。',
        source_ids=choice(run,'NOT_ADOPTED')['source_ids'])]
    engine._plan(run)
    feedback=recovery.prepare(run,allow_busy=True)['feedback']
    assert feedback['reviewer']=='Background reading recovery' and '并非用户逐条审核' in feedback['evidence']


def test_change_auditor_sees_unchanged_stance_in_both_candidates(tmp_path,monkeypatch):
    engine,run=ready(tmp_path,monkeypatch)
    old=deepcopy(run.submission['candidate'])
    run.artifacts['facts_before_recheck_1']={'candidate':old}
    run.review_kind='changes'
    request,_,_=audit.request(run);body=json.loads(request['user_prompt'])
    assert 'scientific_statements' in body['change_context']['unchanged_top_level_fields']
    versions=body['change_context']['declarations']['scientific_statements']
    assert versions['before']==versions['after']==old['scientific_statements']


def test_model_reading_error_is_not_a_question_for_the_user(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch);run.automatic_review=True
    def reply(run,request,stage):
        payload=json.loads(request['user_prompt'])
        if stage=='focused_audit':
            return dict(scientific_approval=False,assessments=[dict(field=field,
                comparison='模型误把明确的研究对象解释成其他对象',matches_source=False,
                question=None,source_ids=[next(iter(payload['source_catalog']))]) for field in payload['fields']])
        return dict(scientific_approval=False,findings=[dict(kind='READING_ERROR',
            field=next(iter(payload['fields'])),reason='模型误把明确的研究对象解释成其他对象',
            question=None,source_ids=[next(iter(payload['source_catalog']))])])
    monkeypatch.setattr(engine,'call',reply);engine._continue_automatically(run)
    assert run.user_question is None and run.error['code']=='READING_REVIEW_DISAGREEMENT'
    assert run.submission is None and run.result is None


def test_nonadoption_also_preserves_external_demo_admission_and_replay(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch)
    run.synthetic=False;engine._select(run,'q1')
    engine._review(run,fixture_review(run))
    run.submission['candidate']['assumption_choices']=[choice(run,'NOT_ADOPTED')]
    engine._plan(run);engine._review(run,fixture_review(run))
    assert run.review_kind=='science'
    engine._review(run,fixture_review(run))
    assert run.result['state']=='POINT' and run.result['independent_replay']
