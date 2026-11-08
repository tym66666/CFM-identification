"""Protocol diagnostics cannot supply facts or bypass full-change review."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_dispatch as dispatch, business_case
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm.wire_type_diagnostics import diagnose
from tests_gateway.test_network_reading_contract import setup
from tests_gateway.test_fact_reading_revision import feedback, accept_changes
from tests_gateway.test_network_statement_reading import as_selection, to_wire
from examples.network_bounded_dispatch_reference import reference
from examples.network_dispatch_reference import approval_records
from examples.business_dispatch_reference import approve

PATH = '/bounded_model/bounds_scope'


def malformed(**kwargs):
    s, e, o = setup(**kwargs)
    o['candidate']['bounded_model']['bounds_scope'] = 'INVALID_ENUM_INPUT_NOT_A_FACT'
    return s, e, o


def reread(s, e, o):
    sheet = prepare_recheck(s, 'q1', **o)['feedback_worksheet']
    f = feedback(sheet, path=PATH, kind='WIRE_FORMAT_ERROR', doc='bounds')
    r = prepare_recheck(s, 'q1', **o, feedback=f)
    assert r['state'] == 'READY_TO_READ'
    return r


def test_type_diagnostic_does_not_repair_input_or_expose_raw_validator_message():
    s, e, o = malformed()
    before = deepcopy(o['candidate'])
    rows = diagnose(e, before)
    d = next(d for d in rows if d['field_path'] == PATH)
    assert d['error_code'] == 'literal_error' and 'CONDITIONAL_ON' in d['allowed_literals']
    assert 'INVALID_ENUM_INPUT_NOT_A_FACT' not in json.dumps(rows)
    r = reread(s, e, o)
    public = json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['wire_format_constraints'] == rows
    assert public['previous_candidate'] == before == o['candidate']
    assert 'PRIVATE_REASON_NOT_SENT' not in r['request']['user']
    assert not r['reading_revision_receipt']['scientific_approval'] and not r['backend_called']


@pytest.mark.parametrize('bad', ['valid_field', 'invented_path', 'replacement', 'valid_candidate'])
def test_forged_or_unnecessary_format_feedback_is_rejected(bad):
    s, e, o = setup() if bad == 'valid_candidate' else malformed()
    sheet = prepare_recheck(s, 'q1', **o)['feedback_worksheet']
    f = feedback(sheet, path=PATH, kind='WIRE_FORMAT_ERROR', doc='bounds').model_dump(mode='json')
    if bad == 'valid_field': f['issues'][0]['field_path'] = '/target'
    if bad == 'invented_path': f['issues'][0]['field_path'] = '/invented'
    if bad == 'replacement': f['issues'][0]['allowed_literals'] = 'POINT'
    r = prepare_recheck(s, 'q1', **o, feedback=f)
    assert r['state'] == 'CHECK_BLOCKED' and r['request'] is None and not r['backend_called']


def test_missing_required_field_can_be_rechecked_without_a_replacement():
    s, e, o = setup()
    del o['candidate']['assignment']
    sheet = prepare_recheck(s, 'q1', **o)['feedback_worksheet']
    assert '/assignment' not in sheet['field_paths']
    assert dict(field_path='/assignment', error_code='missing') in sheet['format_issues']
    r = prepare_recheck(s, 'q1', **o, feedback=feedback(sheet, path='/assignment', kind='WIRE_FORMAT_ERROR'))
    assert r['state'] == 'READY_TO_READ'
    assert 'assignment' not in r['reading_revision']['steps'][0]['candidate']


def test_dag_uses_its_own_type_contract_and_keeps_other_queries():
    from examples.business_case_reference import scenario, submission
    s, native = scenario()
    row, e, _ = submission(s, native, 'q1', [0])
    o = {k:deepcopy(row[k]) for k in ('query_review', 'candidate', 'request_sha256')}
    o['candidate']['version'] = 'INVALID_DAG_VERSION'
    sheet = prepare_recheck(s, 'q1', **o)['feedback_worksheet']
    d = next(d for d in sheet['format_issues'] if d['field_path'] == '/version')
    assert 'dag-query-reading-1' in d['allowed_literals']
    doc = next(iter(sheet['source_catalog'].values()))['doc_id']
    r = prepare_recheck(s, 'q1', **o, feedback=feedback(sheet, path='/version', kind='WIRE_FORMAT_ERROR', doc=doc))
    assert r['state'] == 'READY_TO_READ' and r['remaining_query_ids'] == ['q2']
    assert not r['backend_called']


def test_semantic_feedback_does_not_send_new_type_diagnostics():
    s, e, o = malformed()
    sheet = prepare_recheck(s, 'q1', **o)['feedback_worksheet']
    r = prepare_recheck(s, 'q1', **o, feedback=feedback(sheet, path=PATH, doc='bounds'))
    public = json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert set(public) == {'kind', 'previous_candidate', 'issues'}
    assert 'wire_format_constraints' not in r['request']['system']


def test_a0_does_not_accept_specialist_type_diagnostics():
    from cfm_id.intake_reading_revision import prepare_recheck as a0_recheck
    from tests_gateway.test_business_intake_compact import scenario, receive
    from tests_gateway.test_reading_review_guards import feedback as a0_feedback
    case, raw, _ = scenario()
    s = receive(case, raw)
    sheet = a0_recheck(s, authority='SYNTHETIC_TEST')['feedback_worksheet']
    f = a0_feedback(sheet)
    f['issues'][0]['kind'] = 'WIRE_FORMAT_ERROR'
    with pytest.raises(ValueError, match='INVALID_READING_ISSUE'):
        a0_recheck(s, feedback=f, authority='SYNTHETIC_TEST')
    assert a0_recheck(s, feedback=a0_feedback(sheet), authority='SYNTHETIC_TEST').candidate is None


def test_unwrapped_validator_arithmetic_error_does_not_disable_source_recheck():
    s, e, o = setup()
    o['candidate']['information'][0]['signature_cells'][0]['value'] = '1/0'
    # Existing fraction validation can raise ArithmeticError before Pydantic wraps it.
    from cfm_id_llm.network_statement_reading import SelectionReading
    with pytest.raises(ZeroDivisionError):
        SelectionReading.model_validate(o['candidate'])
    assert diagnose(e, o['candidate']) == []
    sheet = prepare_recheck(s, 'q1', **o)['feedback_worksheet']
    r = prepare_recheck(s, 'q1', **o, feedback=feedback(sheet, path='/information', doc='information'))
    assert r['state'] == 'READY_TO_READ' and not r['backend_called']


@pytest.mark.parametrize('source_change', [False, True])
def test_format_reread_binding_rejects_changed_history(source_change):
    s, e, o = malformed()
    r = reread(s, e, o)
    rev = deepcopy(r['reading_revision'])
    if source_change:
        from cfm_id import business_intake
        case = s.case.model_dump(mode='json')
        case['sources'][0]['text'] += ' Original material changed.'
        s = business_intake.revise_materials(s, case, reason='Source text corrected by author')
    else:
        rev['steps'][0]['candidate']['bounded_model']['bounds_scope'] = 'DIFFERENT_BAD_ENUM'
    blocked = dispatch.prepare_reader(s, 'q1', query_review=o['query_review'], reading_revision=rev)
    assert blocked['state'] != 'READY_TO_READ' and blocked.get('request') is None


@pytest.mark.parametrize('extra', [False, True])
def test_format_correction_cannot_hide_a_semantic_change(extra):
    kwargs = dict(extra=True) if extra else dict(missing_scope=True)
    s, e, o = malformed(**kwargs)
    r = reread(s, e, o)
    new = as_selection(to_wire(reference(r, **kwargs), r))
    # Adversarial new reply: format fixed, but genuine restriction/gap erased.
    new['bounded_model']['no_additional_coupling_constraints']['value'] = True
    new['additional_restrictions'] = []
    opts = dict(query_review=o['query_review'], candidate=new, request_sha256=r['request_sha256'], reading_revision=r['reading_revision'])
    pending = dispatch.execute(s, 'q1', **opts, research_protocol_selected=True)
    assert pending['state'] == 'REVIEW_REQUIRED' and not pending['backend_called']
    sheet = pending['reading_change_worksheet']
    review = accept_changes(sheet)
    bad = [k for k,v in sheet['changes'].items() if '/no_additional_coupling_constraints/value' in v['field_path']]
    assert bad
    for k in bad: review['decisions'][k]['disposition'] = 'REJECTED'
    stopped = dispatch.execute(s, 'q1', **opts, change_review=review, research_protocol_selected=True)
    assert stopped['state'] == 'READING_RECHECK_REQUIRED' and not stopped['backend_called'] and not stopped['answers']
    assert stopped['reading_candidate'] == new


def test_corrected_fixture_needs_fresh_science_and_whole_case_replays():
    s, e, o = malformed()
    r = reread(s, e, o)
    new = as_selection(to_wire(reference(r), r))
    opts = dict(query_review=o['query_review'], candidate=new, request_sha256=r['request_sha256'], reading_revision=r['reading_revision'])
    pending = dispatch.inspect_methods(s, 'q1', **opts)
    opts['change_review'] = accept_changes(pending['reading_change_worksheet'])
    pending = dispatch.execute(s, 'q1', **opts, research_protocol_selected=True)
    assert pending['state'] == 'REVIEW_REQUIRED' and not pending['backend_called']
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    approvals = approval_records(plan)
    row = dict(opts, **{k:v for k,v in approvals.items() if k != 'research_protocol_selected'})
    result = business_case.execute_case(s, {'q1':row}, case_review=approve(business_case.prepare_case(s)['case_worksheet']), research_protocol_selected=True)
    assert result['state'] == 'ALL_QUERIES_IDENTIFIED'
    claim = result['results'][0]['result']
    assert claim['state'] == 'PARTIAL' and claim['independent_replay']
    assert claim['mathematical_claim']['interval'] == ['3/7', '4/7'] and claim['mathematical_claim']['sharp']
    assert not result['production_admission'] and not result['estimation_handoff_allowed']
