"""Source-absence notes and signed target proposals never bypass review."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id import business_field_review as review
from cfm_id_llm.compact_evidence_contract import CONTRACT
from cfm_id_llm.compact_reference_contract import CONTRACT as SHORT, split_user
from cfm_id_llm.compact_formulator import make_compact_request
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_compact_short_refs import encode_fixture
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_reading_review_guards import feedback
from examples.business_dispatch_reference import approve


def extended(raw, operation='NOT_APPLICABLE'):
    raw = deepcopy(raw)
    raw['missing_information'] = []
    for q in raw['queries']:
        q['comparison_order'] = dict(operation=operation, refs=deepcopy(q['goal']['refs']))
    return raw


def received(b, raw, short=True):
    s = intake.start(b, a0_response_contract=CONTRACT, a0_reference_contract=SHORT if short else None,
                     target_summary_contract='target-summary-3')
    return intake.receive_candidate(s, encode_fixture(s, raw) if short else raw, request_sha256=s.request_sha256)


def missing_fixture():
    b, raw = fixture(); raw = extended(raw)
    # Deliberately unsupported absence claim: only the external reviewer can tell.
    raw['missing_information'] = [dict(field_path='common.network_pretreatment_status',
        reason='材料没有说明关系建立时间', refs=deepcopy(raw['common']['analysis_unit']['refs']))]
    return b, raw


def test_public_schema_keeps_sources_and_adds_only_explicit_slots():
    b, _ = fixture()
    old = make_compact_request(b, a0_response_contract='explicit-field-roles-1')
    new = make_compact_request(b, a0_response_contract=CONTRACT)
    assert old[2] == new[2] and split_user(old[1])[1] == split_user(new[1])[1]
    schema = split_user(new[1])[2]
    assert 'missing_information' in schema['required']
    assert 'comparison_order' in schema['$defs']['CompactQuery']['required']
    assert schema['$defs']['MissingInformation']['properties']['refs']['$ref'].endswith('/refs')


@pytest.mark.parametrize('short', [False, True])
def test_absence_reason_remains_unknown_and_is_visible_to_review(short):
    b, raw = missing_fixture(); s = received(b, raw, short); before = deepcopy(s.candidate)
    result = intake.inspect(s)
    assert 'report' in result and not result['core_called']
    claim = result['report']['draft']['shared_draft']['structure']['network_pretreatment_status']
    assert claim['value'] is None and claim['basis'] == 'UNRESOLVED' and claim['evidence'] == []
    item = sheet(s)['fields']['common.missing_information[0]']
    assert item['state'] == 'SOURCE_ABSENCE_PROPOSAL'
    assert item['candidate'] == s.candidate['missing_information'][0] and item['actual_citations']
    assert s.candidate == before
    r = record(sheet(s)); r['decisions']['common.missing_information[0]']['source_coverage'] = 'REJECTED'
    assert submit(s, r)['state'] == 'CHECK_BLOCKED'


@pytest.mark.parametrize('bad', ['missing_notes', 'missing_operator', 'unknown_path', 'wrong_query',
    'duplicate_note', 'known_slot', 'empty_reason', 'bad_reference', 'duplicate_reference',
    'empty_operator_reference', 'bad_operator', 'level_with_difference', 'unknown_extra'])
def test_malformed_or_conflicting_slots_are_not_repaired(bad):
    b, raw = missing_fixture()
    if bad == 'missing_notes': raw.pop('missing_information')
    elif bad == 'missing_operator': raw['queries'][0].pop('comparison_order')
    elif bad == 'unknown_path': raw['missing_information'][0]['field_path'] = 'common.invented'
    elif bad == 'wrong_query': raw['missing_information'][0]['field_path'] = 'queries.q9.semantics.time_horizon'
    elif bad == 'duplicate_note': raw['missing_information'] *= 2
    elif bad == 'known_slot': raw['missing_information'][0]['field_path'] = 'common.analysis_unit'
    elif bad == 'empty_reason': raw['missing_information'][0]['reason'] = ' '
    elif bad == 'bad_reference': raw['missing_information'][0]['refs'] = ['unknown']
    elif bad == 'duplicate_reference': raw['missing_information'][0]['refs'] *= 2
    elif bad == 'empty_operator_reference': raw['queries'][0]['comparison_order']['refs'] = []
    elif bad == 'bad_operator': raw['queries'][0]['comparison_order']['operation'] = 'DIFFERENCE'
    elif bad == 'level_with_difference': raw['queries'][0]['comparison_order']['operation'] = 'INTERVENTION_MINUS_COMPARATOR'
    else: raw['missing_information'][0]['approve'] = True
    s = received(b, raw, False)
    assert intake.inspect(s)['reason_code'] == 'A0_EVIDENCE_SLOTS_REJECTED'
    assert s.candidate == raw and dispatch.prepare_reader(s, 'q1')['request'] is None


def contrast_raw(kind='point', operation='INTERVENTION_MINUS_COMPARATOR'):
    from examples.network_contrast_dispatch_reference import material, a0_reference
    b, data = material(kind); raw = extended(a0_reference(b), operation)
    # Direction is carried by the declared operator; retain the underlying mean.
    raw['queries'][0]['semantics']['aggregation']['value'] = '四个对象等权的结果均值'
    return b, data, raw


@pytest.mark.parametrize('operation, phrase', [('INTERVENTION_MINUS_COMPARATOR', '主方案减基准方案'),
                                              ('COMPARATOR_MINUS_INTERVENTION', '基准方案减主方案')])
def test_signed_projection_preserves_roles_raw_answer_and_operator_citations(operation, phrase):
    b, _, raw = contrast_raw(operation=operation); s = received(b, raw)
    r = intake.inspect(s); semantics = r['report']['draft']['queries'][0]['semantics']
    assert semantics['aggregation']['value'].endswith('比较运算：' + phrase)
    assert semantics['intervention']['value'] == raw['queries'][0]['semantics']['intervention']['value']
    assert semantics['comparator']['value'] == raw['queries'][0]['semantics']['comparator']['value']
    w = sheet(s); assert w['fields']['queries.q1.comparison_order']['actual_citations']
    assert s.candidate['queries'][0]['semantics']['aggregation']['value'] == '四个对象等权的结果均值'
    # A syntactically valid but wrong direction must be explicitly rejected.
    review_record = record(w)
    review_record['decisions']['queries.q1.comparison_order']['source_coverage'] = 'REJECTED'
    assert submit(s, review_record)['state'] == 'CHECK_BLOCKED'


def test_unspecified_direction_does_not_guess_sign_or_bypass_by_coarse_review():
    b, _, raw = contrast_raw(operation='UNSPECIFIED'); s = received(b, raw)
    r = intake.inspect(s)
    assert any(i['code'] == 'COMPARISON_DIRECTION_UNRESOLVED' for i in r['wire_gate']['issues'])
    assert dispatch.prepare_reader(s, 'q1')['state'] == 'READING_RECHECK_REQUIRED'
    assert not r['core_called']


def test_new_protocol_requires_all_extra_fields_reviewed_and_prevents_stripping():
    b, raw = fixture(); s = received(b, extended(raw))
    coarse = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    assert dispatch.prepare_reader(s, 'q1', query_review=coarse)['reason_code'] == 'EXPLICIT_EVIDENCE_FIELD_REVIEW_REQUIRED'
    w = sheet(s); pending = record(w); pending['decisions']['queries.q1.comparison_order']['field_role'] = 'PENDING'
    assert submit(s, pending)['state'] == 'REVIEW_REQUIRED'
    good = submit(s, record(w))['query_review']
    assert dispatch.prepare_reader(s, 'q1', query_review=good)['state'] == 'READY_TO_READ'
    good.pop('field_review')
    assert dispatch.prepare_reader(s, 'q1', query_review=good)['request'] is None
    incomplete = record(w); incomplete['decisions'].pop('queries.q1.comparison_order')
    with pytest.raises(ValueError): submit(s, incomplete)


def test_changed_note_or_operator_invalidates_review_and_save_restore(tmp_path):
    b, raw = missing_fixture(); s = received(b, raw)
    approval = submit(s, record(sheet(s)))['query_review']
    path = tmp_path / 'intake.json'; intake.save(s, path); assert intake.restore(path) == s
    changed = deepcopy(s.candidate); changed['missing_information'][0]['reason'] += '，待确认'
    newer = intake.receive_candidate(s, changed, request_sha256=s.request_sha256)
    assert dispatch.prepare_reader(newer, 'q1', query_review=approval)['request'] is None


def test_legacy_protocol_cannot_silently_drop_new_fields_or_reuse_context():
    b, raw = fixture(); s = intake.start(b, a0_response_contract='explicit-field-roles-1')
    s = intake.receive_candidate(s, extended(raw), request_sha256=s.request_sha256)
    assert intake.inspect(s)['reason_code'] == 'COMPACT_SCHEMA_REJECTED'
    old = intake.start(b, a0_response_contract='explicit-field-roles-1', a0_reference_contract=SHORT)
    newer = received(b, extended(raw))
    wrong = intake.receive_candidate(newer, encode_fixture(old, extended(raw)), request_sha256=newer.request_sha256)
    assert intake.inspect(wrong)['reason_code'] == 'A0_REFERENCE_CONTEXT_MISMATCH'


def test_new_protocol_reread_requires_change_review():
    from cfm_id.intake_reading_revision import prepare_recheck
    b, raw = missing_fixture(); s = received(b, raw)
    w = prepare_recheck(s, authority='SYNTHETIC_TEST')['feedback_worksheet']
    newer = prepare_recheck(s, feedback=feedback(w), authority='SYNTHETIC_TEST')
    raw['missing_information'] = []
    newer = intake.receive_candidate(newer, encode_fixture(newer, raw), request_sha256=newer.request_sha256)
    assert newer.a0_response_contract == CONTRACT and intake.inspect(newer)['state'] == 'REVIEW_REQUIRED'
    assert dispatch.prepare_reader(newer, 'q1')['request'] is None


def test_query_specific_notes_do_not_leak_into_another_query_review():
    b, raw = fixture(); raw = extended(raw)
    raw['queries'].append(deepcopy(raw['queries'][0]))
    # Separate unapproved candidates: this tests review scope, not entailment.
    raw['queries'][1]['goal']['value'] += '；另一个待来源审核的子问题'
    raw['queries'][1]['semantics']['standardization_distribution'] = 'UNKNOWN'
    raw['missing_information'] = [dict(field_path='queries.q2.semantics.standardization_distribution',
        reason='第二问没有提供平均分布', refs=raw['queries'][1]['goal']['refs'])]
    s = received(b, raw)
    assert 'queries.q2.missing_information[0]' not in sheet(s, 'q1')['fields']
    assert 'queries.q2.missing_information[0]' in sheet(s, 'q2')['fields']
    assert 'queries.q2.comparison_order' in sheet(s, 'q2')['fields']


def test_absence_notes_cannot_fill_an_unknown_target_coordinate():
    b, raw = fixture(); raw = extended(raw)
    raw['queries'][0]['semantics']['aggregation'] = 'UNKNOWN'
    raw['missing_information'] = [dict(field_path='queries.q1.semantics.aggregation',
        reason='汇总方式尚未决定', refs=raw['queries'][0]['goal']['refs'])]
    s = received(b, raw); result = dispatch.prepare_reader(s, 'q1')
    assert result['state'] == 'NEEDS_INPUT' and result['request'] is None
    assert intake.inspect(s)['report']['draft']['queries'][0]['semantics']['aggregation']['value'] is None


@pytest.mark.parametrize('kind, expected', [('point', 'POINT'), ('partial', 'PARTIAL')])
def test_native_comparison_still_requires_science_and_independent_replay(kind, expected):
    from examples.network_contrast_dispatch_reference import fact_reference, approval_records
    b, data, raw = contrast_raw(kind); s = received(b, raw)
    q = submit(s, record(sheet(s)))['query_review']
    e = dispatch.prepare_reader(s, 'q1', query_review=q); assert e['state'] == 'READY_TO_READ'
    options = dict(query_review=q, candidate=fact_reference(e, data), request_sha256=e['request_sha256'])
    p = dispatch.inspect_methods(s, 'q1', **options)
    assert not dispatch.execute(s, 'q1', **options, research_protocol_selected=True)['backend_called']
    result = dispatch.execute(s, 'q1', **options, **approval_records(p))
    assert result['state'] == expected and result['independent_replay']


def test_cli_exposes_optional_contract_without_route_or_scientific_defaults(tmp_path):
    from cfm_id.business_intake_cli import main
    b, _ = fixture(); p = tmp_path / 'case.json'; p.write_text(b.model_dump_json(), encoding='utf8')
    dest = tmp_path / 'intake.json'
    assert main(['new', '--case-json', str(p), '--a0-response-contract', CONTRACT, '--output', str(dest)]) == 0
    assert intake.restore(dest).a0_response_contract == CONTRACT


@pytest.mark.parametrize('operation', ['INTERVENTION_MINUS_COMPARATOR', 'COMPARATOR_MINUS_INTERVENTION'])
def test_specialist_arithmetic_positions_are_not_main_baseline_aliases(operation):
    from cfm_id_llm.compact_evidence_contract import clarify_fact_order
    from cfm_id_llm.network_contrast_reading import make_request
    b, _, raw = contrast_raw(operation=operation); s = received(b, raw)
    q = submit(s, record(sheet(s)))['query_review']
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    system = e['request']['system']
    assert 'first/second不是主方案/基准' in system and '此时first放基准、second放主方案' in system
    base = make_request(e['bundle'], binding=e['fact_binding_sha256'])
    snapshot = deepcopy(base); clarified = clarify_fact_order(base)
    assert base == snapshot and clarified['user'] == base['user']
    assert 'first是所问相对变化的方案' in base['system']
    with pytest.raises(ValueError, match='INSTRUCTION_CHANGED'):
        clarify_fact_order(clarified)
