"""Guide presentation must not relax parsing, source review or native replay."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm import compact_output_guide as guide, compact_inline_evidence_contract as inline
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user, request_context
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_compact_evidence_slots import contrast_raw
from tests_gateway.test_business_field_review import sheet, record, submit


def read(b, raw, short=True):
    return receive(b, raw, short, profile=guide.CONTRACT)


@pytest.mark.parametrize('short', [False, True])
def test_guide_keeps_sources_field_meanings_enums_and_exact_parser(short):
    b, _ = fixture()
    opts = dict(a0_reference_contract='compact-source-selectors-1' if short else None)
    a = make_compact_request(b, a0_response_contract=inline.CONTRACT, **opts)
    z = make_compact_request(b, a0_response_contract=guide.CONTRACT, **opts)
    _, ap, schema, _ = split_user(a[1]); _, zp, text, _ = split_user(z[1])
    if short:
        assert ap.pop('reference_context') != zp.pop('reference_context')
        assert text['reference_context'] == request_context(z[1])
    assert ap == zp and a[2] == z[2]
    assert set(text['common字段']) == set(schema['$defs']['CompactCommon']['properties'])
    assert set(text['semantics字段']) == set(schema['$defs']['CompactSemantics']['properties'])
    for field in ('assignment_family', 'kind'):
        name = 'AssignmentFamily' if field == 'assignment_family' else 'TargetKind'
        assert text[field+'可选值'] == schema['$defs'][name]['enum']
    assert '$defs' not in text and 'properties' not in text
    assert len(z[1]) < len(a[1])
    assert guide.project is inline.project and guide.review_items is inline.review_items
    assert guide.apply_gate is inline.apply_gate


@pytest.mark.parametrize('error', ['bare_claim', 'enum_object', 'missing_context', 'wrong_context', 'bad_ref', 'missing_with_value', 'missing_goal', 'extra_field'])
def test_malformed_answers_are_rejected_without_repair(error):
    b, raw = fixture(); s = read(b, wire(raw)); bad = deepcopy(s.candidate)
    if error == 'bare_claim': bad['queries'][0]['goal'] = '这个业务问题'
    elif error == 'enum_object': bad['common']['assignment_family'] = {'enum': ['UNRESOLVED']}
    elif error == 'missing_context': bad.pop('reference_context')
    elif error == 'wrong_context': bad['reference_context'] = 'old-request'
    elif error == 'bad_ref': bad['queries'][0]['goal']['refs'] = ['s9999']
    elif error == 'missing_with_value': bad['queries'][0]['semantics']['comparator'] = dict(state='MISSING', reason='未定', value='随意填', refs=bad['queries'][0]['goal']['refs'])
    elif error == 'missing_goal': bad['queries'][0]['goal'] = dict(state='MISSING', reason='未定', refs=bad['queries'][0]['goal']['refs'])
    else: bad['scientific_approval'] = True
    r = intake.receive_candidate(s, bad, request_sha256=s.request_sha256)
    assert r.candidate == bad and not intake.inspect(r)['core_called']
    assert intake.inspect(r)['reason_code'] is not None
    assert dispatch.prepare_reader(r, 'q1')['request'] is None


def test_missing_baseline_stays_unknown_and_review_does_not_call_core():
    b, _, raw = contrast_raw(operation='COMPARATOR_MINUS_INTERVENTION'); raw.pop('missing_information')
    raw['queries'][0]['semantics']['comparator'] = dict(state='MISSING', reason='比较基准未定', refs=raw['queries'][0]['goal']['refs'])
    s = read(b, raw)
    assert intake.inspect(s)['report']['draft']['queries'][0]['semantics']['comparator']['value'] is None
    assert submit(s, record(sheet(s)))['state'] == 'NEEDS_INPUT'
    assert not intake.inspect(s)['core_called']


def test_old_context_review_and_checkpoint_cannot_be_reused(tmp_path):
    b, raw = fixture(); raw = wire(raw); a = receive(b, raw); z = read(b, raw)
    wrong = intake.receive_candidate(z, a.candidate, request_sha256=z.request_sha256)
    assert intake.inspect(wrong)['reason_code'] == 'A0_REFERENCE_CONTEXT_MISMATCH'
    old_review = submit(a, record(sheet(a)))['query_review']
    assert dispatch.prepare_reader(z, 'q1', query_review=old_review)['request'] is None
    p = tmp_path/'saved.json'; intake.save(z, p); assert intake.restore(p) == z
    with pytest.raises(ValueError, match='PROMPT_CHANGED'):
        intake._checked(dict(a.model_dump(mode='json'), a0_response_contract=guide.CONTRACT))


def test_reread_rebinds_guide_and_retains_original_sources():
    from cfm_id import intake_reading_revision as revision
    b, raw = fixture(); s = read(b, wire(raw))
    old = intake.prepare_request(s); worksheet = revision.prepare_recheck(s, authority='SYNTHETIC_TEST')['feedback_worksheet']
    feedback = dict(version='intake-reading-feedback-1', binding_sha256=worksheet['binding_sha256'], authority='SYNTHETIC_TEST', reviewer='test reviewer', evidence='Synthetic binding regression; not a source accuracy approval.', issues=[])
    # Use a source-located independent request; it does not supply a replacement.
    feedback['issues'] = [dict(field_path='/common/analysis_unit', kind='OMITTED_OR_MISREAD', reason='Recheck the analysis unit against the cited original material.', source_ids=[next(iter(worksheet['source_catalog']))])]
    z = revision.prepare_recheck(s, feedback=feedback, authority='SYNTHETIC_TEST')
    new = intake.prepare_request(z)
    _, p, g, suffix = split_user(new['user_prompt'])
    assert p['reference_context'] == g['reference_context'] != request_context(old['user_prompt'])
    assert p['sources'] == split_user(old['user_prompt'])[1]['sources']
    assert 'A0_RECHECK_CONTEXT_NOT_EVIDENCE' in suffix
    assert intake.inspect(intake.receive_candidate(z, s.candidate, request_sha256=z.request_sha256))['reason_code'] == 'A0_REFERENCE_CONTEXT_MISMATCH'


@pytest.mark.parametrize('kind,expected', [('point','POINT'), ('partial','PARTIAL')])
def test_native_results_still_require_science_and_independent_replay(kind, expected):
    from examples.network_contrast_dispatch_reference import fact_reference, approval_records
    b, data, raw = contrast_raw(kind); raw.pop('missing_information'); s = read(b, raw)
    q = submit(s, record(sheet(s)))['query_review']; e = dispatch.prepare_reader(s, 'q1', query_review=q)
    opts = dict(query_review=q, candidate=fact_reference(e,data), request_sha256=e['request_sha256'])
    p = dispatch.inspect_methods(s, 'q1', **opts)
    assert not dispatch.execute(s, 'q1', **opts, research_protocol_selected=True)['backend_called']
    result = dispatch.execute(s, 'q1', **opts, **approval_records(p))
    assert result['state'] == expected and result['independent_replay']


def test_dag_reader_and_replay_are_preserved():
    from tests_gateway.test_business_intake_compact import scenario
    from examples.business_dispatch_reference import approvals
    b, raw, facts = scenario(); s = intake.configure_fact_format(read(b, wire(raw)), 'source_hash')
    q = submit(s, record(sheet(s)))['query_review']; e = dispatch.prepare_reader(s, 'q1', query_review=q)
    assert e['reader_id'] == 'VARIABLE_DAG_FACTS'
    opts = dict(query_review=q, candidate=facts, request_sha256=e['request_sha256'])
    p = dispatch.inspect_methods(s, 'q1', **opts)
    r = dispatch.execute(s, 'q1', **opts, **approvals(p))
    assert r['state'] == 'POINT' and r['independent_replay']
