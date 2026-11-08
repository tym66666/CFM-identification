"""Required response sections must not become invented facts or approvals."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id.intake_reading_revision import prepare_recheck, review_changes
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_response_contract import CONTRACT
from cfm_id_llm.compact_reference_contract import CONTRACT as SHORT, split_user
from cfm_id_llm.evidence_refs import build_catalog
from tests_gateway.test_compact_short_refs import encode_fixture
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_reading_review_guards import feedback, accept_changes
from examples.business_dispatch_reference import approve


def setup(short=False):
    b, raw = fixture()
    s = intake.start(b, a0_response_contract=CONTRACT,
                     a0_reference_contract=SHORT if short else None)
    return s, encode_fixture(s, raw) if short else raw


def receive(s, raw):
    return intake.receive_candidate(s, raw, request_sha256=s.request_sha256)


def valid(s, raw):
    schema = split_user(intake.prepare_request(s)['user_prompt'])[2]
    return Draft202012Validator(schema).is_valid(raw)


def test_legacy_default_is_unchanged_and_sections_are_orthogonal_to_sources():
    b, raw = fixture(); base = make_compact_request(b)
    new = make_compact_request(b, a0_response_contract=CONTRACT)
    _, p, a, _ = split_user(base[1]); _, q, z, _ = split_user(new[1])
    assert base == make_compact_request(b, a0_response_contract=None)
    assert p == q and base[2] == new[2] and new[0].startswith(base[0])
    z['required'].remove('common'); z['$defs']['CompactQuery']['required'].remove('semantics')
    assert a == z
    old = intake.start(b)
    assert 'a0_response_contract' not in old.model_dump(mode='json')
    incomplete = deepcopy(raw); incomplete.pop('common')
    assert valid(old, incomplete)  # Do not silently rewrite the legacy contract.
    assert intake.inspect(receive(old, incomplete))['state'] == 'READING_RECHECK_REQUIRED'


@pytest.mark.parametrize('short', [False, True])
@pytest.mark.parametrize('missing', ['common', 'semantics', 'second_query_semantics', 'both'])
def test_missing_section_is_rejected_before_defaults_and_no_downstream_request(short, missing):
    s, raw = setup(short)
    if missing in ('common', 'both'): raw.pop('common')
    if missing in ('semantics', 'both'): raw['queries'][0].pop('semantics')
    if missing == 'second_query_semantics':
        raw['queries'].append(deepcopy(raw['queries'][0])); raw['queries'][1].pop('semantics')
    original = deepcopy(raw); assert not valid(s, raw)
    s = receive(s, raw); r = intake.inspect(s)
    assert r['reason_code'] == 'A0_RESPONSE_SECTION_MISSING' and not r['core_called']
    assert r['state'] == 'READING_RECHECK_REQUIRED' and s.candidate == original
    assert dispatch.prepare_reader(s, 'q1')['request'] is None
    assert not business_case.execute_case(s, {}, research_protocol_selected=True)['backend_called']
    if missing == 'second_query_semantics':
        assert r['diagnostics']['issues'] == [{'code':'missing','path':['queries',1,'semantics']}]


@pytest.mark.parametrize('field,value', [('common', None), ('common', []), ('common', 'UNKNOWN'),
                                       ('semantics', None), ('semantics', []), ('semantics', 'UNKNOWN')])
def test_wrong_section_types_still_use_existing_schema_rejection(field, value):
    s, raw = setup()
    (raw if field == 'common' else raw['queries'][0])[field] = value
    assert not valid(s, raw)
    r = intake.inspect(receive(s, raw))
    assert r['reason_code'] == 'COMPACT_SCHEMA_REJECTED' and not r['core_called']


@pytest.mark.parametrize('empty', ['common', 'semantics', 'unknown_summary'])
def test_explicit_empty_or_unknown_cannot_masquerade_as_complete_business(empty):
    s, raw = setup(True)
    if empty == 'common': raw['common'] = {}
    elif empty == 'semantics': raw['queries'][0]['semantics'] = {}
    else: raw['queries'][0]['semantics']['aggregation'] = 'UNKNOWN'
    assert valid(s, raw)  # Structure permits ignorance, never forces a value.
    s = receive(s, raw); r = intake.inspect(s)
    assert r['state'] in ('READING_RECHECK_REQUIRED', 'BUSINESS_CLARIFICATION_REQUIRED')
    assert s.candidate == raw and not r['core_called']
    assert dispatch.prepare_reader(s, 'q1')['request'] is None


@pytest.mark.parametrize('short', [False, True])
def test_complete_response_retains_unknown_facts_and_requires_independent_review(short):
    s, raw = setup(short); assert valid(s, raw)
    s = receive(s, raw); r = intake.inspect(s)
    b, oldraw = fixture(); old = intake.inspect(receive(intake.start(b), oldraw))
    assert r['report']['draft'] == old['report']['draft']
    assert r['report']['prompt_version'] == intake.prepare_request(s)['prompt_version']
    assert r['state'] == 'SEMANTIC_REVIEW_REQUIRED' and r['scientific_review_required']
    pending = dispatch.prepare_reader(s, 'q1')
    assert pending['state'] == 'REVIEW_REQUIRED' and pending['request'] is None
    rejected = approve(pending['query_worksheet']).model_dump(mode='json')
    rejected['decisions']['source_entailment'] = 'REJECTED'
    assert dispatch.prepare_reader(s, 'q1', query_review=rejected)['state'] == 'CHECK_BLOCKED'


def test_contract_change_invalidates_request_and_review_without_mutating_saved_state(tmp_path):
    b, raw = fixture(); old = receive(intake.start(b), raw)
    review = approve(dispatch.prepare_reader(old, 'q1')['query_worksheet'])
    modified = old.model_dump(mode='json'); modified['a0_response_contract'] = CONTRACT
    with pytest.raises(ValueError, match='PROMPT_CHANGED'): intake._checked(modified)
    s, raw = setup()
    with pytest.raises(ValueError, match='STALE'): intake.receive_candidate(s, raw, request_sha256=old.request_sha256)
    s = receive(s, raw)
    assert dispatch.prepare_reader(s, 'q1', query_review=review)['state'] == 'CHECK_BLOCKED'
    intake.save(s, tmp_path/'state.json'); assert intake.restore(tmp_path/'state.json') == s
    with pytest.raises(ValueError): intake.start(b, a0_response_contract='invented')
    with pytest.raises(ValueError, match='REQUIRES_COMPACT'):
        intake.start(b, reading_format='canonical', a0_response_contract=CONTRACT)


def test_short_context_also_binds_the_response_structure_contract():
    b, raw = fixture(); old = intake.start(b, a0_reference_contract=SHORT)
    oldraw = encode_fixture(old, raw)
    modified = old.model_copy(update={'a0_response_contract':CONTRACT})
    s = intake._checked(modified.model_copy(update={'request_sha256':intake._request_sha(modified)}))
    assert intake.inspect(receive(s, oldraw))['reason_code'] == 'A0_REFERENCE_CONTEXT_MISMATCH'


def test_explicit_reread_preserves_contract_history_and_change_review():
    s, raw = setup(True); bad = deepcopy(raw); bad['queries'][0]['semantics']['aggregation'] = 'UNKNOWN'
    s = receive(s, bad)
    sheet = prepare_recheck(s, authority='SYNTHETIC_TEST')['feedback_worksheet']
    fresh = prepare_recheck(s, feedback=feedback(sheet), authority='SYNTHETIC_TEST')
    assert fresh.a0_response_contract == CONTRACT
    assert fresh.reading_revision['steps'][0]['candidate'] == bad
    b, correct = fixture(); fresh = receive(fresh, encode_fixture(fresh, correct))
    pending = intake.inspect(fresh)
    assert pending['state'] == 'REVIEW_REQUIRED' and dispatch.prepare_reader(fresh, 'q1')['request'] is None
    reviewed = review_changes(fresh, accept_changes(pending['reading_change_worksheet']))
    assert intake.inspect(reviewed)['state'] == 'SEMANTIC_REVIEW_REQUIRED'
    assert dispatch.prepare_reader(reviewed, 'q1')['request'] is None


def test_complete_sections_do_not_skip_science_or_point_certificate_replay():
    from examples.network_dispatch_reference import case, candidate, approval_records
    b, _, _ = case(); cat = build_catalog(b)
    def c(text, doc): return dict(state='STATED', value=text, refs=[r['ref'] for r in cat if r['source_id']==doc])
    goal = c(b.business_question, 'business_question')
    raw = dict(common={k:c(b.source_map()[d],d) for k,d in [('analysis_unit','study'),('treatment','study'),('outcome','study'),('unit_network','network')]},
               queries=[dict(goal=goal,kind='FIXED_POLICY_VALUE',semantics=dict(target_population=goal,intervention=goal,policy_assignment=goal,aggregation=goal,time_horizon=c('本周','study'),comparator='NOT_APPLICABLE'))])
    s = intake.start(b, a0_response_contract=CONTRACT, a0_reference_contract=SHORT)
    s = receive(s, encode_fixture(s, raw))
    qr = approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    e = dispatch.prepare_reader(s,'q1',query_review=qr)
    opts = dict(query_review=qr,candidate=candidate(e),request_sha256=e['request_sha256'])
    inspection = dispatch.inspect_methods(s,'q1',**opts)
    blocked = dispatch.execute(s,'q1',**opts,research_protocol_selected=True)
    assert not blocked['backend_called'] and blocked['mathematical_claim'] is None
    result = dispatch.execute(s,'q1',**opts,**approval_records(inspection))
    assert result['state']=='POINT' and result['independent_replay']


def test_cli_can_select_sections_independently_of_reference_format(tmp_path):
    from cfm_id.business_intake_cli import main
    b, _ = fixture(); p = tmp_path/'case.json'; p.write_text(b.model_dump_json(), encoding='utf8')
    dest = tmp_path/'state.json'
    assert main(['new','--case-json',str(p),'--a0-response-contract',CONTRACT,'--output',str(dest)])==0
    s = intake.restore(dest)
    assert s.a0_response_contract == CONTRACT and s.a0_reference_contract is None
