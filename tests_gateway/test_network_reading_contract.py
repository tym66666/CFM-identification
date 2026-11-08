"""The explanatory profile cannot change evidence, permission or mathematics."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id_llm.network_reading_contract import CONTRACT, make_request
from cfm_id_llm.network_statement_reading import make_information_request, parse_selection
from examples.network_dispatch_reference import setup as point_setup, candidate, approval_records
from examples.network_bounded_dispatch_reference import setup as box_setup, reference
from examples.business_dispatch_reference import approve
from tests_gateway.test_network_statement_reading import to_wire, as_selection
from tests_gateway.test_information_semantics import without_descriptions


def setup(kind='partial', **kwargs):
    opts = dict(design='D1', sufficiency=False) if kind == 'r1b' else {}
    old, _, _, _ = box_setup(**kwargs) if kind == 'partial' else point_setup(**opts)
    s = intake.configure_network_fact_contract(old, CONTRACT)
    q = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    raw = reference(e, **kwargs) if kind == 'partial' else candidate(e, **opts)
    wire = as_selection(to_wire(raw, e))
    return s, e, dict(query_review=q, candidate=wire, request_sha256=e['request_sha256'])


def test_only_explanations_change_not_sources_or_wire():
    _, e, _ = setup()
    old = make_information_request(e['bundle'], binding=e['fact_binding_sha256'])
    new = make_request(e['bundle'], binding=e['fact_binding_sha256'])
    assert without_descriptions(json.loads(old['user'])) == without_descriptions(json.loads(new['user']))
    assert old != new
    assert make_information_request(e['bundle'], binding=e['fact_binding_sha256']) == old


def test_configuration_preserves_a0_but_invalidates_old_reviews_and_requests(tmp_path):
    old, e0, o0, _ = box_setup()
    s = intake.configure_network_fact_contract(old, CONTRACT)
    assert intake.prepare_request(s) == intake.prepare_request(old)
    assert s.candidate == old.candidate
    assert dispatch.prepare_reader(s, 'q1', query_review=o0['query_review'])['state'] == 'CHECK_BLOCKED'
    intake.save(s, tmp_path/'saved.json')
    assert intake.restore(tmp_path/'saved.json') == s
    q = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    result = dispatch.inspect_methods(s, 'q1', query_review=q, candidate=o0['candidate'], request_sha256=e0['request_sha256'])
    assert result['reason_code'] == 'STALE_FACT_READING_REQUEST' and not result['backend_called']
    assert e['request_sha256'] != e0['request_sha256']


@pytest.mark.parametrize('kind', ['r1b', 'r2', 'partial'])
def test_whole_case_requires_fresh_reviews_and_replays_unchanged_math(kind):
    s, e, o = setup(kind)
    before = deepcopy(o['candidate'])
    pending = dispatch.execute(s, 'q1', **o, research_protocol_selected=True)
    assert pending['state'] == 'REVIEW_REQUIRED' and not pending['backend_called']
    p = dispatch.inspect_methods(s, 'q1', **o)
    a = approval_records(p)
    row = dict(o, **{k:v for k,v in a.items() if k != 'research_protocol_selected'})
    result = business_case.execute_case(s, {'q1':row},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']), research_protocol_selected=True)
    assert result['state'] == 'ALL_QUERIES_IDENTIFIED'
    r = result['results'][0]['result']
    assert r['independent_replay'] and r['state'] == ('PARTIAL' if kind == 'partial' else 'POINT')
    assert o['candidate'] == before
    assert not r['statement_reading_receipt']['scientific_approval']
    assert not result['production_admission'] and not result['estimation_handoff_allowed']
    if kind == 'partial':
        assert r['mathematical_claim']['interval'] == ['3/7','4/7']
        assert r['mathematical_claim']['sharp'] and not result['all_queries_point_identified']


@pytest.mark.parametrize('no_coupling', [False, True, None])
def test_real_extra_is_preserved_and_blocks_even_with_wrong_no_coupling_flag(no_coupling):
    s, e, o = setup(extra=True)
    o['candidate']['bounded_model']['no_additional_coupling_constraints']['value'] = no_coupling
    before = deepcopy(o['candidate'])
    parsed = parse_selection(e['bundle'], before, binding=e['fact_binding_sha256'])
    assert parsed['facts']['additional_restrictions']
    r = dispatch.execute(s, 'q1', **o, research_protocol_selected=True)
    assert r['state'] == 'ADAPTER_NOT_CONNECTED' and not r['backend_called']
    assert r['mathematical_claim'] is None and o['candidate'] == before
    assert r['facts']['bounded_model']['no_additional_coupling_constraints']['value'] is no_coupling


def test_unknown_model_completeness_is_not_approved_by_prompt():
    s, _, o = setup(missing_scope=True)
    r = dispatch.execute(s, 'q1', **o, research_protocol_selected=True)
    assert r['state'] == 'NEEDS_INPUT' and not r['backend_called']
    assert r['facts']['bounded_model']['no_additional_coupling_constraints']['value'] is None


def test_duplicate_information_note_is_not_silently_deleted():
    s, _, o = setup()
    o['candidate']['additional_restrictions'] = [dict(
        text='资料是精确总体均值，不是样本估计。', source_ids=o['candidate']['information'][0]['source_ids'])]
    before = deepcopy(o['candidate'])
    r = dispatch.execute(s, 'q1', **o, research_protocol_selected=True)
    assert r['state'] == 'ADAPTER_NOT_CONNECTED' and not r['backend_called']
    assert o['candidate'] == before and r['facts']['additional_restrictions']


def test_reread_keeps_profile_and_requires_change_review():
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_fact_reading_revision import feedback
    s, e, o = setup()
    w = prepare_recheck(s, 'q1', **o)['feedback_worksheet']
    new = prepare_recheck(s, 'q1', **o, feedback=feedback(w, path='/information', doc='information'))
    assert new['network_fact_contract'] == CONTRACT
    assert new['request']['system'].startswith(e['request']['system'] + '\n')
    assert new['request_sha256'] != e['request_sha256']
    fresh = as_selection(to_wire(reference(new), new))
    fresh['bounded_model']['no_additional_coupling_constraints']['value'] = None
    r = dispatch.inspect_methods(s, 'q1', query_review=o['query_review'], candidate=fresh,
        request_sha256=new['request_sha256'], reading_revision=new['reading_revision'])
    assert 'reading_change_worksheet' in r and not r['backend_called']
