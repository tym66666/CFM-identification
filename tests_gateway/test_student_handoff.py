"""Public entry, packaged configuration and complete offline teaching examples."""
from copy import deepcopy
import json
import pytest
from cfm_id import project, business_intake, fact_reading_revision
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import fact_reading_contracts as registry
from cfm_id_llm.fact_wire_models import model_for
from examples import student_handoff


def test_recommended_entry_uses_one_config_without_changing_legacy_defaults(monkeypatch):
    monkeypatch.setattr(business_intake, 'uuid4', lambda:'handoff-fixed-session')
    case = student_handoff.material('point')
    config = project.reading_config()
    assert config.a0_response_contract == 'target-first-skill-1'
    assert config.network_fact_contract == 'network-shared-definitions-1'
    assert ReadingConfig().a0_response_contract is None
    current = project.start(case)
    explicit = business_intake.start_configured(case, config)
    assert business_intake.prepare_request(current) == business_intake.prepare_request(explicit)
    assert current.candidate is None


def test_all_five_reader_families_have_one_component_owner():
    # Keep the historical test node ID used by the acceptance manifest.
    # The supported set now includes three additional reader families.
    rows = registry.registrations()
    assert {r.reader_id for r in rows} == {
        'NETWORK_FIXED_POLICY_FACTS', 'NETWORK_POLICY_CONTRAST_FACTS',
        'NETWORK_RANDOMIZED_EFFECT_FACTS', 'NETWORK_OBSERVATIONAL_POLICY_FACTS',
        'VARIABLE_DAG_FACTS', 'NETWORK_RANDOMIZED_ARM_FACTS',
        'NETWORK_FINITE_POLICY_FACTS', 'NETWORK_OBSERVATIONAL_EFFECT_FACTS'}
    from cfm_id.capability_registry import business_bindings
    assert {r.reader_id for r in rows} == {b.reader_id for b in business_bindings()}
    assert len({(r.reader_id, r.profile) for r in rows}) == len(rows)
    for row in rows:
        entry = dict(reader_id=row.reader_id, reference_format=row.reference_format, **row.entry_metadata())
        selected = registry.contract_for_entry(entry)
        assert (selected.reader_id, selected.profile, selected.wire_version) == (row.reader_id, row.profile, row.wire_version)
        assert selected.model is row.model
        assert model_for(entry) is row.model
        with pytest.raises(registry.ReadingContractError):
            registry.contract_for_entry(dict(entry, **{row.profile_field or row.version_field:'unregistered-profile'}))


def test_registered_dag_parser_and_sources_preserve_native_projection():
    from examples.business_case_reference import scenario, submission
    session, native = scenario()
    row, entry, plan = submission(session, native, 'q1', [0])
    before = deepcopy(row['candidate'])
    contract = registry.contract_for_entry(entry)
    projection = contract.parse_candidate(entry, row['candidate'])
    assert projection['native_candidate'] == native == plan['native_candidate']
    assert row['candidate'] == before
    assert contract.reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256']) == fact_reading_revision._references(entry)
    assert registry.contract_for_entry(dict(entry, reference_format='source_hash')) is None


def test_registered_scoped_effect_keeps_reviewed_roles_and_constraints(monkeypatch):
    from tests_gateway.test_scoped_effect_reading import setup
    from cfm_id_llm import scoped_effect_reading
    session, entry, options = setup(monkeypatch)
    contract = registry.contract_for_entry(entry)
    raw = deepcopy(options['candidate'])
    expected = scoped_effect_reading.parse(entry['bundle'], raw,
        binding=entry['fact_binding_sha256'], reviewed_query=entry['reviewed_local_request']['raw_query'])
    assert contract.parse_candidate(entry, raw) == expected
    assert options['candidate'] == raw
    assert contract.public_constraints(entry, ['target']) == fact_reading_revision._public_constraints(entry, ['target'])
    with pytest.raises((ValueError, KeyError)):
        contract.parse_candidate(dict(entry, reviewed_local_request={}), raw)


def test_teaching_examples_require_explicit_synthetic_review_opt_in(tmp_path):
    with pytest.raises(ValueError, match='EXPLICIT_SYNTHETIC_REVIEW_OPT_IN_REQUIRED'):
        student_handoff.run(tmp_path/'refused')
    assert not (tmp_path/'refused').exists()


def test_three_examples_keep_real_proof_and_missing_condition_boundary(tmp_path):
    folder = tmp_path/'examples'
    report = student_handoff.run(folder, allow_synthetic_reviews=True)
    assert report['api_calls'] == 0
    assert [r['state'] for r in report['examples']] == ['POINT','PARTIAL','NEEDS_INPUT']
    assert report['reading_config'] == project.reading_config().model_dump(mode='json')
    for row in report['examples']:
        result = json.loads((folder/row['example']/'result.json').read_text('utf8'))
        assert result['independent_replay'] == (row['state'] != 'NEEDS_INPUT')
        if row['state'] == 'NEEDS_INPUT':
            assert not result['backend_called'] and result['certificate'] is None
        else:
            assert result['certificate'] is not None
        if row['state'] == 'PARTIAL':
            assert result['mathematical_claim']['sharp']
            assert result['mathematical_claim']['interval'] == ['3/7','4/7']
