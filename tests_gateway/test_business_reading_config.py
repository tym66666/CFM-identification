"""Developer configuration compatibility and current native review boundaries."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
from pydantic import TypeAdapter
import pytest

from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.business_reading_config import ReadingConfig
from cfm_id.business_intake_cli import main
from cfm_id_llm.network_fact_protocols import (
    NetworkFactProfile, network_fact_profiles, network_fact_protocol,
)
from tests_gateway.test_business_intake_compact import scenario
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_network_statement_reading import to_wire, as_selection
from examples.network_bounded_dispatch_reference import setup as old_setup, reference
from examples.network_dispatch_reference import approval_records
from examples.business_dispatch_reference import approve, approvals


PROFILES = network_fact_profiles()


def start(case, config):
    # Deterministic identity isolates actual request/checkpoint compatibility.
    with patch.object(intake, 'uuid4', return_value='fixed-config-test'):
        return intake.start_configured(case, config)


@pytest.mark.parametrize('options', [
    {}, dict(reading_format='canonical', fact_format='source_hash'),
    dict(assignment_semantics='joint-assignment-law-1'),
    dict(target_summary_contract='target-summary-1'),
    dict(target_summary_contract='target-summary-2'),
    dict(a0_reference_contract='compact-source-selectors-1'),
    dict(a0_response_contract='explicit-sections-1'),
    dict(assignment_semantics='joint-assignment-law-1', target_summary_contract='target-summary-2',
         a0_reference_contract='compact-source-selectors-1', a0_response_contract='explicit-sections-1'),
    *[dict(network_fact_contract=p) for p in PROFILES if p is not None],
])
def test_config_roundtrip_preserves_legacy_request_and_checkpoint(options, tmp_path):
    case, _, _ = scenario()
    cfg = ReadingConfig(**options)
    with patch.object(intake, 'uuid4', return_value='fixed-config-test'):
        old = intake.start(case, **options)
    s = start(case, cfg)
    assert s.model_dump(mode='json') == old.model_dump(mode='json')
    assert intake.prepare_request(s) == intake.prepare_request(old)
    assert start(case, json.loads(cfg.model_dump_json())) == s
    intake.save(s, tmp_path/'intake.json')
    assert intake.restore(tmp_path/'intake.json') == s
    assert 'version' not in cfg.intake_options()
    assert s.version == 'business-intake-1'


@pytest.mark.parametrize('options', [
    dict(version='unknown'), dict(reading_format='unknown'), dict(fact_format='unknown'),
    dict(assignment_semantics=True), dict(target_summary_contract='auto'),
    dict(network_fact_contract='my.plugin'), dict(a0_response_contract='auto'),
    dict(reading_format='canonical', a0_reference_contract='compact-source-selectors-1'),
    dict(reading_format='canonical', assignment_semantics='joint-assignment-law-1'),
    dict(reading_format='canonical', target_summary_contract='target-summary-2'),
    dict(reading_format='canonical', a0_response_contract='explicit-sections-1'),
    dict(fact_format='source_hash', network_fact_contract='network-source-statements-1'),
    dict(lane='DAG_CLASSICAL_BACKDOOR'), dict(scientific_approval=True),
    dict(api_key='not-a-real-key'), dict(provider='arbitrary'), dict(force_point=True),
])
def test_invalid_or_authority_settings_are_rejected_before_start(options):
    case, _, _ = scenario()
    with patch.object(intake, 'start', side_effect=AssertionError('must validate first')):
        with pytest.raises(ValueError):
            intake.start_configured(case, options)


def test_unvalidated_pydantic_copy_cannot_bypass_config_guard():
    cfg = ReadingConfig().model_copy(update={'reading_format': 'canonical',
        'a0_response_contract': 'explicit-sections-1'})
    case, _, _ = scenario()
    with pytest.raises(ValueError):
        intake.start_configured(case, cfg)
    with pytest.raises(ValueError):
        cfg.intake_options()


def test_profile_type_and_closed_pairs_cover_exactly_the_same_choices():
    schema = TypeAdapter(NetworkFactProfile).json_schema()
    values = {None, *next(s['enum'] for s in schema['anyOf'] if 'enum' in s)}
    assert set(PROFILES) == values
    assert intake.BusinessIntake.model_fields['network_fact_contract'].annotation == NetworkFactProfile
    for value in values:
        assert ReadingConfig(network_fact_contract=value).network_fact_contract == value
        p = network_fact_protocol(value)
        assert callable(p.make_request) and callable(p.parse)


@pytest.mark.parametrize('profile', ['missing', 'cfm_id.solver', {}, False])
def test_unknown_protocol_never_falls_back_to_default(profile):
    with pytest.raises(ValueError, match='UNKNOWN_NETWORK_FACT_CONTRACT'):
        network_fact_protocol(profile)


@pytest.mark.parametrize('reader,fmt,reason', [
    ('typo', 'short_refs', 'UNKNOWN_FACT_READER'),
    ('VARIABLE_DAG_FACTS', 'typo', 'UNKNOWN_FACT_REFERENCE_FORMAT'),
])
def test_unknown_reader_or_format_never_falls_back_to_dag(reader, fmt, reason):
    with pytest.raises(ValueError, match=reason):
        dispatch._fact_request({}, 'binding', reader, fmt, {}, [])


def test_broken_registration_is_not_disguised_as_unknown_reader(monkeypatch):
    def broken(*args):
        raise dispatch.capabilities.RegistryError('MISSING_BUSINESS_HANDLER')
    monkeypatch.setattr(dispatch.capabilities,'business_binding',broken)
    with pytest.raises(dispatch.capabilities.RegistryError,match='MISSING_BUSINESS_HANDLER'):
        dispatch._fact_request({},'binding','NETWORK_FIXED_POLICY_FACTS','short_refs',{},[])


def network_setup(profile, **kwargs):
    old, _, _, _ = old_setup(**kwargs)
    s = intake.start_configured(old.case, ReadingConfig(reading_format='canonical',
        network_fact_contract=profile))
    s = intake.receive_candidate(s, old.candidate, request_sha256=s.request_sha256)
    pending = dispatch.prepare_reader(s, 'q1')
    assert pending['state'] == 'REVIEW_REQUIRED' and pending['request'] is None
    q = approve(pending['query_worksheet'])
    entry = dispatch.prepare_reader(s, 'q1', query_review=q)
    raw = reference(entry, **kwargs)
    if profile is not None:
        raw = to_wire(raw, entry)
        if profile != 'network-source-statements-1':
            raw = as_selection(raw)
    if profile in ('network-policy-definition-refs-1', 'network-policy-record-definitions-1', 'network-policy-scopes-1', 'network-policy-scopes-2'):
        raw['version']=profile
        raw['assignment']['definition_refs']=['study'] if raw['assignment']['probabilities'] else []
        raw['target']['definition_refs']=['study']
        for info in raw['information']:info['definition_refs']=['study']
        if profile in ('network-policy-record-definitions-1','network-policy-scopes-1','network-policy-scopes-2'):
            raw['mean_sufficiency']['definition_refs']=['study'] if raw['mean_sufficiency']['covered_nodes'] else []
    if profile in ('network-policy-scopes-1','network-policy-scopes-2'):
        for info in raw['information']:
            info.update(scope_status='DECLARED' if info['outcome_nodes'] else 'UNSPECIFIED',
                        scope_source_ids=list(info['source_ids']) if info['outcome_nodes'] else [])
    return s, entry, dict(query_review=q, candidate=raw, request_sha256=entry['request_sha256'])


@pytest.mark.parametrize('profile', PROFILES)
def test_paired_protocol_requires_science_then_replays_sharp_partial(profile):
    s, e, opts = network_setup(profile)
    original = deepcopy(opts['candidate'])
    parsed = network_fact_protocol(profile).parse(e['bundle'], original, binding=e['fact_binding_sha256'])
    assert parsed['facts']['target']['kind'] == 'FIXED_POLICY_MEAN'
    r = dispatch.execute(s, 'q1', **opts, research_protocol_selected=True)
    assert r['state'] == 'REVIEW_REQUIRED' and not r['backend_called']
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    result = dispatch.execute(s, 'q1', **opts, **approval_records(plan))
    assert result['state'] == 'PARTIAL' and result['independent_replay']
    assert result['mathematical_claim']['interval'] == ['3/7', '4/7']
    assert result['mathematical_claim']['sharp']
    assert opts['candidate'] == original
    assert not result['production_admission'] and not result['estimation_handoff_allowed']


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('condition', ['unknown', 'extra'])
def test_config_cannot_remove_unknown_scope_or_extra_restrictions(profile, condition):
    kwargs = dict(missing_scope=True) if condition == 'unknown' else dict(extra=True)
    s, _, opts = network_setup(profile, **kwargs)
    original = deepcopy(opts['candidate'])
    result = dispatch.execute(s, 'q1', **opts, research_protocol_selected=True)
    assert result['state'] == ('NEEDS_INPUT' if condition == 'unknown' else 'ADAPTER_NOT_CONNECTED')
    assert not result['backend_called'] and result['mathematical_claim'] is None
    assert opts['candidate'] == original


def test_configuration_does_not_resolve_unknown_business_target():
    case, raw = fixture()
    raw['queries'][0]['semantics']['aggregation'] = 'UNKNOWN'
    s = intake.start_configured(case, ReadingConfig(target_summary_contract='target-summary-2'))
    s = intake.receive_candidate(s, raw, request_sha256=s.request_sha256)
    r = dispatch.prepare_reader(s, 'q1')
    assert r['state'] == 'NEEDS_INPUT' and r['request'] is None
    assert not r['backend_called']


def test_dag_remains_selected_by_reviewed_meaning_not_network_protocol_option():
    case, raw, facts = scenario()
    s = intake.start_configured(case, ReadingConfig(network_fact_contract='network-source-selections-information-1'))
    s = intake.receive_candidate(s, raw, request_sha256=s.request_sha256)
    q = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    assert e['reader_id'] == 'VARIABLE_DAG_FACTS'
    # Use the retained source-hash facts for the full native proof path.
    s = intake.configure_fact_format(s, 'source_hash')
    q = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    opts = dict(query_review=q, candidate=facts, request_sha256=e['request_sha256'])
    p = dispatch.inspect_methods(s, 'q1', **opts)
    assert not p['backend_called']
    r = dispatch.execute(s, 'q1', **opts, **approvals(p))
    assert r['state'] == 'POINT' and r['independent_replay']


def test_fact_config_change_preserves_a0_but_invalidates_review_and_response():
    s, e, opts = network_setup(None)
    request = intake.prepare_request(s)
    updated = intake.configure_network_fact_contract(s, 'network-source-statements-1')
    assert intake.prepare_request(updated) == request and updated.candidate == s.candidate
    assert dispatch.prepare_reader(updated, 'q1', query_review=opts['query_review'])['state'] == 'CHECK_BLOCKED'
    q = approve(dispatch.prepare_reader(updated, 'q1')['query_worksheet'])
    r = dispatch.inspect_methods(updated, 'q1', query_review=q, candidate=opts['candidate'],
                                 request_sha256=e['request_sha256'])
    assert r['reason_code'] == 'STALE_FACT_READING_REQUEST' and not r['backend_called']


def test_a0_config_change_rejects_prior_response_and_historical_defaults_stay_separate():
    case, raw, _ = scenario()
    s = start(case, {})
    other = start(case, dict(a0_response_contract='explicit-sections-1'))
    assert s.request_sha256 != other.request_sha256
    with pytest.raises(ValueError, match='STALE_INTAKE_RESPONSE'):
        intake.receive_candidate(other, raw, request_sha256=s.request_sha256)
    assert ReadingConfig().reading_format == 'compact'
    assert intake.BusinessIntake.model_fields['reading_format'].default == 'canonical'
    assert intake.BusinessIntake.model_fields['fact_format'].default == 'source_hash'


def test_cli_config_is_offline_and_cannot_mix_flags_or_write_on_failure(tmp_path, capsys):
    question = tmp_path/'question.txt'
    question.write_text('希望知道实施培训对本店和相邻门店营业额的影响。', encoding='utf8')
    config = tmp_path/'config.json'
    config.write_text(ReadingConfig(a0_response_contract='explicit-sections-1').model_dump_json(), encoding='utf8')
    output = tmp_path/'new.json'
    args = ['new', '--question-file', str(question), '--reading-config', str(config), '--output', str(output)]
    assert main(args) == 0
    assert intake.restore(output).a0_response_contract == 'explicit-sections-1'
    assert json.loads(capsys.readouterr().out)['api_calls'] == 0
    bad = tmp_path/'bad.json'
    args[-1] = str(bad)
    assert main([*args, '--a0-reference-contract', 'compact-source-selectors-1']) == 2
    assert 'CANNOT_MIX' in capsys.readouterr().out and not bad.exists()
    config.write_text('{"fact_format":"short_refs","fact_format":"source_hash"}', encoding='utf8')
    assert main(args) == 2
    assert 'DUPLICATE_JSON_KEY' in capsys.readouterr().out and not bad.exists()
    config.write_text('{"scientific_approval":true}', encoding='utf8')
    assert main(args) == 2 and not bad.exists()


def test_shipped_config_matches_current_defaults():
    path = Path(__file__).resolve().parents[1]/'examples/legacy/configs/compatibility_default.json'
    assert ReadingConfig.model_validate(intake.read_json(path)) == ReadingConfig()
