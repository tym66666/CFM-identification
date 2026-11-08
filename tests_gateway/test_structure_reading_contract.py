"""Structure-reading clarification cannot change evidence or mathematical gates."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import compact_unified_contract as unified
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.schemas import SourceDocument
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id.business_field_review import DIMENSIONS
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_unified_reading_contract import no_descriptions
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_compact_evidence_slots import contrast_raw
from tests_gateway.test_business_field_review import sheet, record, submit


PROFILE = unified.STRUCTURE_CONTRACT


def read(b, raw, short=True):
    return receive(b, raw, short, profile=PROFILE)


@pytest.mark.parametrize('short', [False, True])
@pytest.mark.parametrize('assignment', [None, 'joint-assignment-law-1'])
def test_new_instructions_preserve_public_sources_schema_and_review(short, assignment):
    b, raw = fixture()
    options = dict(a0_reference_contract='compact-source-selectors-1' if short else None,
                   assignment_semantics=assignment, target_summary_contract='target-summary-3')
    old = make_compact_request(b, a0_response_contract=unified.CONTRACT, **options)
    new = make_compact_request(b, a0_response_contract=PROFILE, **options)
    _, op, oschema, _ = split_user(old[1])
    _, np, nschema, _ = split_user(new[1])
    if short:
        assert op.pop('reference_context') != np.pop('reference_context')
        oschema['properties'].pop('reference_context')
        nschema['properties'].pop('reference_context')
    assert op == np and old[2] == new[2]
    assert no_descriptions(oschema) == no_descriptions(nschema)
    a = receive(b, wire(raw), short, profile=unified.CONTRACT)
    z = read(b, wire(raw), short)
    wa, wz = sheet(a), sheet(z)
    assert set(wa['fields']) == set(wz['fields'])
    assert wa['original_materials'] == wz['original_materials']
    assert all(all(d[k] == 'PENDING' for k in DIMENSIONS) for d in wz['decisions'].values())
    assert not intake.inspect(z)['core_called']


@pytest.mark.parametrize('target', ['target-summary-1', 'target-summary-2'])
def test_incompatible_target_settings_are_rejected(target):
    with pytest.raises(ValueError, match='CURRENT_TARGET_SEMANTICS'):
        ReadingConfig(a0_response_contract=PROFILE, target_summary_contract=target)
    b, _ = fixture()
    with pytest.raises(ValueError, match='CURRENT_TARGET_SEMANTICS'):
        make_compact_request(b, a0_response_contract=PROFILE, target_summary_contract=target)


@pytest.mark.parametrize('family', ['UNRESOLVED', 'OBSERVATIONAL', 'COMPLETE_RANDOMIZATION'])
def test_assignment_label_is_not_reclassified_or_scientifically_approved(family):
    b, raw = fixture()
    raw = wire(raw)
    raw['common']['assignment_family'] = family
    # Deliberately unsupported classification: a real citation exists but does
    # not grant semantic truth. The independent review below must block it.
    if family != 'UNRESOLVED':
        raw['common']['assignment_law'] = dict(state='STATED', value='负责人选择名单',
            refs=raw['queries'][0]['goal']['refs'])
    s = read(b, raw)
    before = deepcopy(s.candidate)
    assert s.candidate['common']['assignment_family'] == family
    audit = record(sheet(s))
    audit['decisions']['common.assignment_family']['field_role'] = 'REJECTED'
    r = submit(s, audit)
    assert r['state'] == 'CHECK_BLOCKED' and not r['scientific_approval']
    assert dispatch.prepare_reader(s, 'q1', query_review=r['query_review'])['request'] is None
    assert s.candidate == before and not intake.inspect(s)['core_called']


@pytest.mark.parametrize('error', ['enum_object', 'invalid_ref', 'missing_with_value'])
def test_clarified_prompt_does_not_repair_invalid_model_output(error):
    b, raw = fixture()
    s = read(b, wire(raw))
    bad = deepcopy(s.candidate)
    q = bad['queries'][0]
    if error == 'enum_object':
        bad['common']['assignment_family'] = dict(state='STATED', value='OBSERVATIONAL', refs=q['goal']['refs'])
    elif error == 'invalid_ref':
        q['goal']['refs'] = ['s9999']
    else:
        q['semantics']['comparator'] = dict(state='MISSING', reason='未定', value='补填', refs=q['goal']['refs'])
    z = intake.receive_candidate(s, bad, request_sha256=s.request_sha256)
    assert 'report' not in intake.inspect(z) and z.candidate == bad
    assert dispatch.prepare_reader(z, 'q1')['request'] is None


def test_real_missing_baseline_and_rejected_review_remain_distinct_stops():
    b, _, raw = contrast_raw()
    raw.pop('missing_information')
    raw['queries'][0]['semantics']['comparator'] = dict(
        state='MISSING', reason='基准安排尚未决定', refs=raw['queries'][0]['goal']['refs'])
    s = read(b, raw)
    accepted = submit(s, record(sheet(s)))
    assert accepted['state'] in ('NEEDS_INPUT', 'READING_RECHECK_REQUIRED')
    rejected = record(sheet(s))
    rejected['decisions']['common.assignment_family']['field_role'] = 'REJECTED'
    r = submit(s, rejected)
    e = dispatch.prepare_reader(s, 'q1', query_review=r['query_review'])
    assert e['state'] == 'CHECK_BLOCKED' and not e['backend_called']
    assert e['reason_code'] == 'DISPATCH_REVIEW_REJECTED'


@pytest.mark.parametrize('kind, expected', [('point', 'POINT'), ('partial', 'PARTIAL')])
def test_network_identification_retains_scientific_review_and_independent_replay(kind, expected):
    from examples.network_contrast_dispatch_reference import fact_reference, approval_records
    b, data, raw = contrast_raw(kind)
    raw.pop('missing_information')
    s = read(b, raw)
    q = submit(s, record(sheet(s)))['query_review']
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    opts = dict(query_review=q, candidate=fact_reference(e, data), request_sha256=e['request_sha256'])
    p = dispatch.inspect_methods(s, 'q1', **opts)
    assert not dispatch.execute(s, 'q1', **opts, research_protocol_selected=True)['backend_called']
    r = dispatch.execute(s, 'q1', **opts, **approval_records(p))
    assert r['state'] == expected and r['independent_replay']
    assert not r['production_admission']


@pytest.mark.parametrize('combined', [False, True])
def test_variable_graph_is_preserved_and_combined_structure_is_not_silently_dropped(combined):
    from tests_gateway.test_business_intake_compact import scenario
    from examples.business_dispatch_reference import approvals
    b, raw, facts = scenario()
    if combined:
        old_catalog = build_catalog(b)
        text = '这些对象也有处理前固定的双向协作关系，甲与乙相连，乙与丙相连。'
        b = b.model_copy(update={'sources': [*b.sources, SourceDocument(source_id='network', text=text)]})
        new_catalog = build_catalog(b)
        refs = {r['ref']: next(n['ref'] for n in new_catalog if
            (n['source_id'], n['start'], n['end']) == (r['source_id'], r['start'], r['end'])) for r in old_catalog}
        def rebind_fixture(value):
            if isinstance(value, dict):
                return {k: [refs[r] for r in v] if k == 'refs' else rebind_fixture(v) for k, v in value.items()}
            if isinstance(value, list):
                return [rebind_fixture(v) for v in value]
            return value
        raw = rebind_fixture(raw)  # New synthetic fixture, never a live reply.
        raw['common']['unit_network'] = dict(state='STATED', value=text,
            refs=[r['ref'] for r in new_catalog if r['source_id'] == 'network'])
    s = intake.configure_fact_format(read(b, wire(raw)), 'source_hash')
    q = submit(s, record(sheet(s)))['query_review']
    e = dispatch.prepare_reader(s, 'q1', query_review=q)
    if combined:
        assert e['state'] == 'ADAPTER_NOT_CONNECTED'
        assert e['reason_code'] == 'COMBINED_OR_AMBIGUOUS_GRAPH_REPRESENTATIONS'
        assert e['request'] is None and not e['backend_called']
    else:
        assert e['reader_id'] == 'VARIABLE_DAG_FACTS'
        opts = dict(query_review=q, candidate=facts, request_sha256=e['request_sha256'])
        p = dispatch.inspect_methods(s, 'q1', **opts)
        r = dispatch.execute(s, 'q1', **opts, **approvals(p))
        assert r['state'] == 'POINT' and r['independent_replay']


def test_old_candidate_and_old_review_cannot_be_rebound_by_changing_profile(tmp_path):
    b, raw = fixture()
    old = receive(b, wire(raw), profile=unified.CONTRACT)
    new = read(b, wire(raw))
    bad = intake.receive_candidate(new, old.candidate, request_sha256=new.request_sha256)
    assert intake.inspect(bad)['reason_code'] == 'A0_REFERENCE_CONTEXT_MISMATCH'
    with pytest.raises(intake.IntakeError, match='INVALID_OR_STALE_FIELD_REVIEW'):
        submit(new, record(sheet(old)))
    path = tmp_path / 'intake.json'
    intake.save(new, path)
    assert intake.restore(path) == new
    with pytest.raises(ValueError, match='PROMPT_CHANGED'):
        intake._checked(dict(old.model_dump(mode='json'), a0_response_contract=PROFILE))
