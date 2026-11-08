"""Information representation is neither source truth nor scientific approval."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch, network_effect_dispatch as effects
from cfm_id.fact_reading_revision import prepare_recheck, ReadingFeedback
from cfm_id_llm import network_effect_reading as reading
from cfm_id_llm.wire_type_diagnostics import diagnose
from examples.network_effect_dispatch_reference import approval_records
from evaluation.network_effect_information_cases import CASES, EXPECTED, setup
from tests_gateway.test_fact_reading_revision import accept_changes


@pytest.mark.parametrize('operator', ['NODE_ARM_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW', 'FINITE_SAMPLE', 'OTHER', 'UNKNOWN'])
@pytest.mark.parametrize('availability', ['SYMBOLIC_POPULATION_OPERATOR', 'FINITE_SAMPLE', 'EXACT_POPULATION_VALUE', 'UNKNOWN'])
@pytest.mark.parametrize('has_cells', [False, True])
def test_schema_parser_and_public_diagnostics_agree_without_repair(operator, availability, has_cells):
    _, entry, _, raw = setup('bakery_population')
    source = raw['information'][0]
    source.update(operator=operator, availability=availability,
                  arm_cells=source['arm_cells'][:1] if has_cells else [])
    before = deepcopy(raw)
    valid = ((operator == 'FINITE_SAMPLE') == (availability == 'FINITE_SAMPLE')
             and (not has_cells or operator == 'NODE_ARM_MEANS'))
    schema = json.JSONDecoder().raw_decode(entry['request']['user'])[0]['output_schema']
    assert Draft202012Validator(schema).is_valid(raw) == valid
    assert bool(diagnose(entry, raw)) == (not valid)
    if valid:
        reading.parse(entry['bundle'], raw, binding=entry['fact_binding_sha256'])
    else:
        with pytest.raises(ValueError):
            reading.parse(entry['bundle'], raw, binding=entry['fact_binding_sha256'])
    assert raw == before


@pytest.mark.parametrize('name', CASES)
def test_complete_prose_population_sample_mixture_and_missing_arm(name):
    state, entry, data, raw = setup(name)
    before = deepcopy(raw)
    opts = dict(query_review=entry['query_review'], candidate=raw, request_sha256=entry['request_sha256'])
    plan = dispatch.inspect_methods(state, 'q1', **opts)
    if EXPECTED[name] == 'POINT':
        pending = dispatch.execute(state, 'q1', **opts, research_protocol_selected=True)
        assert pending['state'] == 'REVIEW_REQUIRED' and not pending['backend_called']
        approvals = approval_records(plan)
    else:
        approvals = dict(research_protocol_selected=True)
    result = dispatch.execute(state, 'q1', **opts, **approvals)
    assert result['state'] == EXPECTED[name]
    assert result['independent_replay'] == (EXPECTED[name] == 'POINT')
    assert result['backend_called'] == (EXPECTED[name] == 'POINT')
    if EXPECTED[name] != 'POINT':
        assert result['mathematical_claim'] is None
    assert raw == before
    if data['variant'] in ('mixed', 'missing'):
        assert len(plan['facts']['information']) == 2
        assert plan['facts']['information'][1]['operator'] == 'FINITE_SAMPLE'


def test_contradictory_sample_rejects_before_backend_and_gives_no_replacement_answer(monkeypatch):
    state, entry, _, raw = setup('laundry_sample')
    raw['information'][0]['operator'] = 'NODE_ARM_MEANS'
    before = deepcopy(raw)
    monkeypatch.setattr(effects, '_compile', lambda *a, **kw: pytest.fail('Contradiction reached math'))
    opts = dict(query_review=entry['query_review'], candidate=raw, request_sha256=entry['request_sha256'])
    result = dispatch.execute(state, 'q1', **opts, research_protocol_selected=True)
    assert result['state'] == 'CHECK_BLOCKED' and not result['backend_called']
    sheet = prepare_recheck(state, 'q1', **opts)['feedback_worksheet']
    assert sheet['format_issues'] == diagnose(entry, raw)
    assert sheet['format_issues'][0]['field_path'] == '/information/0'
    assert 'replacement' not in json.dumps(sheet['format_issues'])
    assert raw == before


def test_format_recheck_uses_public_contract_and_keeps_all_reviews_fresh():
    state, entry, _, raw = setup('bakery_mixed')
    original_plan = dispatch.inspect_methods(state, 'q1', query_review=entry['query_review'],
        candidate=raw, request_sha256=entry['request_sha256'])
    old_approvals = approval_records(original_plan)
    bad = deepcopy(raw)
    bad['information'][1]['operator'] = 'NODE_ARM_MEANS'
    opts = dict(query_review=entry['query_review'], candidate=bad, request_sha256=entry['request_sha256'])
    sheet = prepare_recheck(state, 'q1', **opts)['feedback_worksheet']
    feedback = ReadingFeedback(binding_sha256=sheet['binding_sha256'], authority='SYNTHETIC_TEST',
        reviewer='PRIVATE_REVIEWER_NAME', evidence='PRIVATE_EVIDENCE_STRING: synthetic source audit.',
        issues=[dict(field_path='/information/1', kind='WIRE_FORMAT_ERROR',
            source_ids=[k for k, v in sheet['source_catalog'].items() if v['doc_id'] == 'sample_records'],
            reason='PRIVATE_REASON_STRING: compare original sample source and public type rules.')])
    revised = prepare_recheck(state, 'q1', **opts, feedback=feedback)
    assert revised['state'] == 'READY_TO_READ'
    assert revised['request_sha256'] != entry['request_sha256']
    public = json.loads(revised['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['previous_candidate'] == bad
    assert public['wire_format_constraints'] == sheet['format_issues']
    assert not any(x in json.dumps(revised['request']) for x in ('PRIVATE_REVIEWER_NAME', 'PRIVATE_EVIDENCE_STRING', 'PRIVATE_REASON_STRING'))
    assert json.JSONDecoder().raw_decode(revised['request']['user'])[0]['source_catalog'] == json.JSONDecoder().raw_decode(entry['request']['user'])[0]['source_catalog']
    # Test-authored new reply, not an edit to any model output.
    fresh = deepcopy(raw)
    fresh['reference_context'] = reading.reference_catalog(revised['bundle'], binding=revised['fact_binding_sha256'])['context']
    new = dict(query_review=entry['query_review'], candidate=fresh, request_sha256=revised['request_sha256'],
               reading_revision=revised['reading_revision'])
    changes = dispatch.inspect_methods(state, 'q1', **new)
    assert changes['state'] == 'REVIEW_REQUIRED' and changes['reading_change_worksheet']
    new['change_review'] = accept_changes(changes['reading_change_worksheet'])
    assert dispatch.execute(state, 'q1', **new, **old_approvals)['state'] == 'CHECK_BLOCKED'
    plan = dispatch.inspect_methods(state, 'q1', **new)
    result = dispatch.execute(state, 'q1', **new, **approval_records(plan))
    assert result['state'] == 'POINT' and result['independent_replay']
    assert result['reading_revision']['steps'][0]['candidate'] == bad
    assert not result['reading_revision_receipt']['candidate_modified']
