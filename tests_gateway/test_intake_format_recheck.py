"""A0 format rereads keep source, whole-change and scientific review barriers."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.intake_reading_revision import prepare_recheck, review_changes
from cfm_id_llm.compact_reference_contract import request_context
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_reading_review_guards import feedback
from tests_gateway.test_fact_reading_revision import accept_changes


def test_nonlocal_recheck_uses_its_own_schema_not_local_effect_instructions(tmp_path):
    from cfm_id_llm.compact_reference_contract import split_user
    from tests_gateway.test_inline_evidence_slots import receive
    for profile in ('local-role-ownership-1', 'local-role-ownership-3', 'query-conditioning-1'):
        case, raw = fixture(); raw = wire(raw)
        raw['queries'][0]['kind'] = 'TOTAL_EFFECT'
        raw['queries'][0]['comparison_order']['operation'] = 'INTERVENTION_MINUS_COMPARATOR'
        if profile == 'query-conditioning-1':
            raw['queries'][0]['semantics']['conditioning_context'] = 'UNKNOWN'
        original = receive(case, raw, profile=profile)
        schema = split_user(intake.prepare_request(original)['user_prompt'])[2]
        w = prepare_recheck(original, authority='SYNTHETIC_TEST')['feedback_worksheet']
        f = feedback(w)
        names = ('policy_assignment', 'intervention', 'comparator', 'target_population')
        f['issues'] = [dict(f['issues'][0], field_path='/queries/0/semantics/'+name) for name in names]
        newer = prepare_recheck(original, feedback=f, authority='SYNTHETIC_TEST')
        request = intake.prepare_request(newer)
        public = json.loads(request['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
        expected = [dict(field_path=i['field_path'], field_role=schema['$defs']['CompactSemantics']['properties'][name]['description'])
                    for i, name in zip(f['issues'], names)]
        assert public['field_role_constraints'] == expected
        assert public['previous_candidate'] == original.candidate
        assert newer.candidate is None and newer.case == original.case
        assert 'PRIVATE_REASON_STAYS_LOCAL' not in request['user_prompt']
        assert dispatch.prepare_reader(newer, 'q1')['request'] is None
        path = tmp_path/(profile+'.json')
        intake.save(newer, path)
        assert intake.prepare_request(intake.restore(path)) == request


def test_schema_role_selection_is_per_query_and_does_not_guess_invalid_kinds():
    from cfm_id_llm.compact_reference_contract import split_user
    from cfm_id_llm.compact_response_contract import scope_recheck_roles
    case, raw = fixture(); raw = wire(raw)
    s = receive(case, raw, profile='local-role-ownership-1')
    user = intake.prepare_request(s)['user_prompt']; schema = split_user(user)[2]
    candidate = dict(queries=[dict(kind='DIRECT_EFFECT'), dict(kind='TOTAL_EFFECT'), dict(kind='INVALID')])
    paths = ['/queries/0/semantics/aggregation', '/queries/1/semantics/policy_assignment/refs/0',
             '/queries/2/semantics/policy_assignment', '/queries/20/semantics/policy_assignment',
             '/queries/1/semantics/invented', '/common/outcome']
    rows = [dict(field_path=p, field_role='existing public help') for p in paths]
    result = scope_recheck_roles(rows, contract=s.a0_response_contract, user_prompt=user, candidate=candidate)
    assert result[1]['field_role'] == schema['$defs']['CompactSemantics']['properties']['policy_assignment']['description']
    assert [r for i, r in enumerate(result) if i != 1] == [r for i, r in enumerate(rows) if i != 1]
    assert all(r['field_role']=='existing public help' for r in rows)


def test_recheck_scope_version_preserves_legacy_history_and_all_review_gates(tmp_path):
    from cfm_id_llm.compact_reference_contract import request_context
    from cfm_id_llm.compact_response_contract import evidence_contract
    from tests_gateway.test_business_field_review import sheet, record, submit
    case, raw = fixture(); raw = wire(raw)
    original = receive(case, raw, profile='local-role-ownership-1')
    path = '/queries/0/semantics/policy_assignment'
    w = prepare_recheck(original, authority='SYNTHETIC_TEST')['feedback_worksheet']; f = feedback(w)
    f['issues'][0]['field_path'] = path
    newer = prepare_recheck(original, feedback=f, authority='SYNTHETIC_TEST')
    legacy_history = deepcopy(newer.reading_revision)
    legacy_history['steps'][0].pop('field_role_contract')
    legacy = newer.model_copy(update=dict(reading_revision=legacy_history))
    legacy = intake._checked(legacy.model_copy(update=dict(request_sha256=intake._request_sha(legacy))))
    old_request = intake.prepare_request(legacy)
    old_public = json.loads(old_request['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert old_public['field_role_constraints'] == evidence_contract(original.a0_response_contract).recheck_field_roles([path])
    assert old_request != intake.prepare_request(newer)
    intake.save(legacy, tmp_path/'legacy.json')
    assert intake.prepare_request(intake.restore(tmp_path/'legacy.json')) == old_request
    with pytest.raises(intake.IntakeError):
        intake.receive_candidate(newer, original.candidate, request_sha256=legacy.request_sha256)
    for pending in (legacy, newer):
        candidate = deepcopy(original.candidate)
        candidate['queries'][0]['goal']['value'] += '（复查表达）'
        candidate['reference_context'] = request_context(intake.prepare_request(pending)['user_prompt'])
        received = intake.receive_candidate(pending, candidate, request_sha256=pending.request_sha256)
        report = intake.inspect(received)
        assert report['state']=='REVIEW_REQUIRED' and not report['core_called']
        checked = review_changes(received, accept_changes(report['reading_change_worksheet']))
        assert intake.inspect(checked)['state']=='SEMANTIC_REVIEW_REQUIRED'
        review = record(sheet(checked))
        review['decisions']['queries.q1.semantics.policy_assignment']['field_role']='REJECTED'
        rejected = submit(checked, review)
        assert rejected['state']=='CHECK_BLOCKED'
        assert dispatch.prepare_reader(checked, 'q1', query_review=rejected['query_review'])['request'] is None
        if pending is legacy:
            w2=prepare_recheck(received, authority='SYNTHETIC_TEST')['feedback_worksheet']; f2=feedback(w2)
            f2['issues'][0]['field_path']=path
            mixed=prepare_recheck(received, feedback=f2, authority='SYNTHETIC_TEST')
            assert 'field_role_contract' not in mixed.reading_revision['steps'][0]
            assert mixed.reading_revision['steps'][1]['field_role_contract']=='query-schema-1'
            intake.save(mixed, tmp_path/'mixed.json')
            assert intake.prepare_request(intake.restore(tmp_path/'mixed.json'))==intake.prepare_request(mixed)

PATH = '/common/assignment_family'


def setup(profile='inline-unified-contract-1', short=True):
    case, raw = fixture()
    if profile is not None:
        raw = wire(raw)
    s = receive(case, raw, short, profile=profile)
    bad = deepcopy(s.candidate)
    bad['common']['assignment_family'] = dict(state='STATED', value='UNTRUSTED_VALUE', refs=[])
    return s, intake.receive_candidate(s, bad, request_sha256=s.request_sha256)


def format_feedback(sheet, path=PATH):
    f = feedback(sheet)
    f['issues'][0].update(field_path=path, kind='WIRE_FORMAT_ERROR')
    return f


def reread(s, path=PATH):
    sheet = prepare_recheck(s, authority='SYNTHETIC_TEST')['feedback_worksheet']
    return prepare_recheck(s, feedback=format_feedback(sheet, path), authority='SYNTHETIC_TEST')


@pytest.mark.parametrize('profile',[None,'inline-evidence-1','inline-output-guide-1','inline-unified-contract-1'])
@pytest.mark.parametrize('short',[False,True])
def test_same_type_diagnostic_across_a0_presentations_without_candidate_repair(profile,short):
    good, bad = setup(profile, short)
    raw = deepcopy(bad.candidate)
    sheet = prepare_recheck(bad,authority='SYNTHETIC_TEST')['feedback_worksheet']
    error = next(d for d in sheet['format_issues'] if d['field_path']==PATH)
    assert error['error_code']=='enum' and 'OBSERVATIONAL' in error['allowed_literals']
    assert 'UNTRUSTED_VALUE' not in json.dumps(sheet['format_issues'])
    next_s = reread(bad)
    request = intake.prepare_request(next_s)
    public = json.loads(request['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['wire_format_constraints']==[error] and public['previous_candidate']==raw
    assert bad.candidate==raw and next_s.case==bad.case and next_s.candidate is None
    assert not intake.inspect(bad)['core_called']
    assert 'PRIVATE_REASON_STAYS_LOCAL' not in request['user_prompt']
    assert 'PRIVATE_EVIDENCE_STAYS_LOCAL' not in request['user_prompt']
    assert request!=intake.prepare_request(good)


@pytest.mark.parametrize('shape',['string','object'])
def test_field_forbidden_state_has_explicit_recheck_location_without_relaxation(shape):
    good,_=setup();raw=deepcopy(good.candidate)
    invalid='NOT_APPLICABLE' if shape=='string' else dict(state='NOT_APPLICABLE')
    raw['queries'][0]['semantics']['neighbor_exposure']=invalid
    raw['common']['outcome']=invalid
    bad=intake.receive_candidate(good,raw,request_sha256=good.request_sha256)
    w=prepare_recheck(bad,authority='SYNTHETIC_TEST')['feedback_worksheet']
    paths={d['field_path'] for d in w['format_issues'] if d['error_code']=='INVALID_NOT_APPLICABLE'}
    assert paths=={'/common/outcome','/queries/0/semantics/neighbor_exposure'}
    assert intake.inspect(bad)['state']=='READING_RECHECK_REQUIRED'
    new=reread(bad,'/queries/0/semantics/neighbor_exposure')
    public=json.loads(intake.prepare_request(new)['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['wire_format_constraints']==[dict(field_path='/queries/0/semantics/neighbor_exposure',error_code='INVALID_NOT_APPLICABLE')]
    assert bad.candidate==raw and new.candidate is None and new.case==bad.case
    assert dispatch.prepare_reader(bad,'q1')['request'] is None


def test_field_state_diagnostic_preserves_legal_empty_slots_and_list_coordinates():
    good,_=setup();raw=deepcopy(good.candidate)
    raw['queries'][0]['semantics'].update(comparator='NOT_APPLICABLE',policy_assignment='NOT_APPLICABLE',neighbor_exposure='UNKNOWN')
    raw['common']['covariates']=[dict(state='NOT_APPLICABLE')]
    candidate=intake.receive_candidate(good,raw,request_sha256=good.request_sha256)
    ds=prepare_recheck(candidate,authority='SYNTHETIC_TEST')['feedback_worksheet']['format_issues']
    assert ds==[dict(field_path='/common/covariates/0',error_code='INVALID_NOT_APPLICABLE')]
    # Legal field states do not approve the comparison's semantic applicability.
    assert dispatch.prepare_reader(candidate,'q1')['request'] is None


@pytest.mark.parametrize('path,mutation',[
    ('/common',lambda d:d.pop('common')),
    ('/queries/0/semantics',lambda d:d['queries'][0].pop('semantics')),
    ('/queries/0/goal',lambda d:d['queries'][0].pop('goal')),
    ('/common/assignment_family',lambda d:d['common'].__setitem__('assignment_family',None)),
])
def test_missing_regions_or_invalid_fields_can_be_located_without_filling(path,mutation):
    good,_=setup();raw=deepcopy(good.candidate);mutation(raw)
    bad=intake.receive_candidate(good,raw,request_sha256=good.request_sha256)
    assert path in {d['field_path'] for d in prepare_recheck(bad)['feedback_worksheet']['format_issues']}
    next_s=reread(bad,path)
    assert next_s.reading_revision['steps'][0]['candidate']==raw and next_s.candidate is None


@pytest.mark.parametrize('invalid',['good_path','invented','replacement','valid_candidate'])
def test_format_feedback_must_match_actual_current_type_error(invalid):
    good,bad=setup();s=good if invalid=='valid_candidate' else bad
    sheet=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet'];f=format_feedback(sheet)
    if invalid=='good_path':f['issues'][0]['field_path']='/queries/0/goal'
    if invalid=='invented':f['issues'][0]['field_path']='/arbitrary'
    if invalid=='replacement':f['issues'][0]['allowed_literals']='OBSERVATIONAL'
    with pytest.raises(ValueError):prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST')


def test_unrecognized_schema_errors_do_not_become_clearance_or_guessed_format_hints():
    good,_=setup();raw=deepcopy(good.candidate)
    raw['queries'][0]['semantics']['comparator']=dict(state='MISSING',reason='未定',value='FORGED',refs=[])
    bad=intake.receive_candidate(good,raw,request_sha256=good.request_sha256)
    sheet=prepare_recheck(bad,authority='SYNTHETIC_TEST')['feedback_worksheet']
    assert sheet['format_issues']==[] and 'report' not in intake.inspect(bad)
    assert dispatch.prepare_reader(bad,'q1')['request'] is None
    next_s=prepare_recheck(bad,feedback=feedback(sheet),authority='SYNTHETIC_TEST')
    assert 'wire_format_constraints' not in intake.prepare_request(next_s)['user_prompt']


def test_raw_extra_field_names_and_validator_messages_are_not_public_diagnostics():
    good,_=setup();raw=deepcopy(good.candidate);raw['common']['UNTRUSTED_EXTRA_KEY']='PRIVATE_DATA'
    bad=intake.receive_candidate(good,raw,request_sha256=good.request_sha256)
    ds=prepare_recheck(bad)['feedback_worksheet']['format_issues'];assert ds
    assert all(d['field_path']=='/common' for d in ds)
    assert 'UNTRUSTED' not in json.dumps(ds) and 'PRIVATE_DATA' not in json.dumps(ds)


def test_plain_source_recheck_and_saved_requests_keep_old_public_contract(tmp_path):
    good,bad=setup();sheet=prepare_recheck(bad,authority='SYNTHETIC_TEST')['feedback_worksheet']
    next_s=prepare_recheck(bad,feedback=feedback(sheet),authority='SYNTHETIC_TEST')
    r=intake.prepare_request(next_s)
    public=json.loads(r['user_prompt'].split('独立复查定位（不是新增事实）：\n')[1])
    assert set(public)=={'kind','previous_candidate','issues'}
    assert 'wire_format_constraints' not in r['system_prompt']
    p=tmp_path/'state.json';intake.save(next_s,p);assert intake.prepare_request(intake.restore(p))==r


def test_format_reply_needs_all_change_and_field_reviews_and_cannot_reuse_old_binding():
    good,bad=setup();next_s=reread(bad);new=deepcopy(good.candidate)
    with pytest.raises(ValueError):intake.receive_candidate(next_s,new,request_sha256=bad.request_sha256)
    new['reference_context']=request_context(intake.prepare_request(next_s)['user_prompt'])
    received=intake.receive_candidate(next_s,new,request_sha256=next_s.request_sha256)
    pending=intake.inspect(received)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['core_called']
    assert dispatch.prepare_reader(received,'q1')['request'] is None
    sheet=pending['reading_change_worksheet']
    checked=review_changes(received,accept_changes(sheet))
    assert intake.inspect(checked)['state']=='SEMANTIC_REVIEW_REQUIRED'
    assert dispatch.prepare_reader(checked,'q1')['request'] is None
    assert not intake.inspect(checked)['core_called']
    raw=next_s.model_dump(mode='json');raw['reading_revision']['steps'][0]['candidate']['common']['assignment_family']='OBSERVATIONAL'
    with pytest.raises(ValueError):intake._checked(raw)


def test_corrected_format_does_not_hide_unrequested_semantic_changes():
    good,bad=setup();next_s=reread(bad);new=deepcopy(good.candidate)
    new['reference_context']=request_context(intake.prepare_request(next_s)['user_prompt'])
    new['queries'][0]['semantics']['time_horizon']=dict(state='STATED',value='未经原文提供的十年后',refs=new['queries'][0]['goal']['refs'])
    received=intake.receive_candidate(next_s,new,request_sha256=next_s.request_sha256)
    w=intake.inspect(received)['reading_change_worksheet'];review=accept_changes(w)
    ids=[k for k,v in w['changes'].items() if '/time_horizon' in v['field_path']];assert ids
    for k in ids:review['decisions'][k]['disposition']='REJECTED'
    blocked=review_changes(received,review)
    assert intake.inspect(blocked)['state']=='READING_RECHECK_REQUIRED'
    assert dispatch.prepare_reader(blocked,'q1')['request'] is None
    assert blocked.candidate==new and not intake.inspect(blocked)['core_called']
