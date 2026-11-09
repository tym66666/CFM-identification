"""Original-query evidence and source-bound admission, with no online calls.

Frozen synthetic reviews below are prepared from the reference BEFORE a
candidate is mutated. A passing offline fixture is not an LLM accuracy claim.
"""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from unittest.mock import patch

import pytest

from cfm_id_bridge.scientific_binding import sha
from cfm_id.dag_id_contract import as_problem
from cfm_id.dag_id_solver import identify_or_report
from cfm_id.dag_id_verify import check_failure, check_hedge, replay
from cfm_id.dag_id_route import GeneralIdProblem, prepare, submit
from cfm_id_llm.dag_id_reading import make_request, parse, to_problem
from examples.dag_id_route_reference import make_problem, synthetic_review
from examples.dag_id_llm_reading import _run, _respond_to, _reread_trigger, review_for


def fixture():
    case = dict(question='对本期会员，强制设定发券X后，是否复购Y的分布是什么？',
                documents={'brief': '本期会员为研究对象。X表示是否发券，Y表示是否复购，均为已观测二元变量。'
                           '采用单期无反馈结构模型，对象之间无干扰。直接因果关系只有X到Y；'
                           '没有未列出的共同原因，外生噪声独立。干预只替换X的机制，其余机制不变。'
                           '本合成研究给定严格正的X、Y联合总体分布，不是把样本频数当总体。'},
                expected='POINT')
    bundle = dict(case_id='frozen', question=case['question'], documents=case['documents'])
    catalog = json.loads(make_request(bundle)['user'])['source_catalog']
    sid = next(iter(catalog))
    claim = dict(value=True, source_ids=[sid])
    wire = dict(version='dag-id-reading-1',
                variables=[dict(name=n, observation='OBSERVED', domain='BINARY', source_ids=[sid])
                           for n in ['X', 'Y']],
                relations=[dict(cause='X', effect='Y', kind='DIRECT_CAUSE', source_ids=[sid])],
                common_causes=[], target=dict(kind='INTERVENTIONAL_DISTRIBUTION', treatment='X',
                    outcome='Y', context='本期会员', source_ids=[sid]),
                scope={k: deepcopy(claim) for k in ('static_acyclic', 'graph_complete',
                    'latent_causes_accounted', 'independent_errors', 'perfect_intervention',
                    'no_between_unit_interference')},
                information=dict(kind='FULL_JOINT_POPULATION_LAW', variables=['X', 'Y'],
                                 source_ids=[sid], positivity=deepcopy(claim)),
                adjustment=None, adjustment_source_ids=[], unresolved=[], additional_restrictions=[])
    p = GeneralIdProblem(**to_problem(parse(bundle, wire),
        graph_source='researcher-confirmed reading of the material in this example',
        materials_sha256=sha(bundle), researcher_confirmed=True))
    # Approval is separate, frozen to this reference, never generated from the
    # candidate supplied to FakeProvider below.
    case['approved_graph'] = dict(nodes=['X', 'Y'], directed=[['X', 'Y']], bidirected=[])
    case['review'] = synthetic_review(p).model_dump()
    return case, bundle, wire, p


class FakeProvider:
    name = 'offline-reference'
    model = 'none'
    base_url = 'no-network'
    last_diagnostics = {}

    def __init__(self, wire):
        self.wire = wire

    def generate_json(self, **kwargs):
        return deepcopy(self.wire)


def run_fixture(case, wire):
    record = {}
    with redirect_stdout(io.StringIO()):
        state = _run(FakeProvider(wire), 'frozen', case, record)
    return state, record


def test_complete_reading_uses_only_frozen_approval_and_replays():
    case, bundle, wire, p = fixture()
    state, record = run_fixture(case, wire)
    assert state == 'POINT'
    assert record['independent_replay'] is True
    assert record['problem']['reading_declarations']['candidate'] == parse(bundle, wire).model_dump()
    assert prepare(p)['worksheet']['reading_declarations']['positivity']['value'] is True


@pytest.mark.parametrize('change,reason', [
    ('graph_unknown', 'SCOPE_DECLARATION_MISSING:graph_complete'),
    ('domain_other', 'FINITE_DISCRETE_DOMAIN_NOT_DECLARED'),
    ('positivity_unknown', 'POSITIVITY_NOT_DECLARED'),
    ('positivity_false', 'DECLARED_POSITIVITY_NOT_SATISFIED'),
    ('information_coverage', 'POPULATION_LAW_VARIABLE_COVERAGE_MISMATCH'),
    ('interference', 'DECLARED_SCOPE_NOT_SATISFIED:no_between_unit_interference'),
    ('sample', 'INFORMATION_IS_NOT_A_POPULATION_LAW'),
])
def test_read_correctly_but_inadmissible_never_calls_solver(change, reason):
    case, _, wire, _ = fixture()
    if change == 'graph_unknown': wire['scope']['graph_complete']['value'] = None
    elif change == 'domain_other': wire['variables'][1]['domain'] = 'OTHER'
    elif change == 'positivity_unknown': wire['information']['positivity']['value'] = None
    elif change == 'positivity_false': wire['information']['positivity']['value'] = False
    elif change == 'information_coverage': wire['information']['variables'] = ['X']
    elif change == 'interference': wire['scope']['no_between_unit_interference']['value'] = False
    elif change == 'sample': wire['information']['kind'] = 'FINITE_SAMPLE'
    with patch('cfm_id.dag_id_route.solve', side_effect=AssertionError('must not solve')):
        state, record = run_fixture(case, wire)
    assert state in ('NEEDS_INPUT', 'UNSUPPORTED')
    assert record['reason_code'] == reason
    assert 'certificate' not in record


def test_no_independent_approval_is_a_review_stop_even_for_correct_reading():
    case, _, wire, p = fixture()
    case.pop('review')
    state, _ = run_fixture(case, wire)
    assert state == 'REVIEW_REQUIRED'
    case.pop('approved_graph')
    assert run_fixture(case, wire)[0] == 'REVIEW_REQUIRED'
    assert set(review_for(p).decisions.values()) == {'PENDING'}


@pytest.mark.parametrize('text', [
    '结果取值域尚未确定，可能连续，研究者尚未作决定。',
    '结果Y没有测量记录，Y的总体分布是否可用尚未确定。',
    '只有样本观测记录，尚未提供联合分布。',
])
def test_keywords_never_resolve_scientific_uncertainty(text):
    assert _respond_to(text).decision == 'UNRESOLVED'
    _, _, _, p = fixture()
    p = p.model_copy(update={'unresolved': [text]})
    # The preserved reading and the business problem must agree, including notes.
    assert prepare(p)['reason_code'] == 'READING_PROBLEM_MISMATCH'


def test_real_missing_population_information_does_not_trigger_pressure_to_reread():
    assert _reread_trigger('NEEDS_INPUT', {
        'reason_code': 'INFORMATION_IS_NOT_A_POPULATION_LAW',
        'reading_audit': {'information': 'FINITE_SAMPLE'}}) is None


def test_old_approval_cannot_survive_a_changed_reading_source():
    case, bundle, wire, p = fixture()
    other = deepcopy(wire)
    other['target']['source_ids'] = [list(json.loads(make_request(bundle)['user'])['source_catalog'])[-1]]
    changed = GeneralIdProblem(**to_problem(parse(bundle, other),
        graph_source=p.graph_source, materials_sha256=p.materials_sha256, researcher_confirmed=True))
    assert submit(changed, synthetic_review(p))['reason_code'] == 'STALE_GENERAL_ID_REVIEW'


def test_other_intervention_witness_is_rejected_even_after_rebinding_hash():
    asked = as_problem(['X', 'A', 'Y'], [('A', 'Y')], [('A', 'Y')], 'X', ['Y'])
    other = as_problem(['A', 'Y'], [('A', 'Y')], [('A', 'Y')], 'A', ['Y'])
    wrong = identify_or_report(other)
    assert identify_or_report(asked)['status'] == 'POINT'
    assert not check_failure(wrong['witness'], asked)['passed']
    wrong['witness'].update(problem_sha256=sha(asked), original_target={
        'treatment': asked.treatment, 'outcome': asked.outcome, 'context': asked.context})
    assert not check_failure(wrong['witness'], asked)['passed']
    p = make_problem().model_copy(update=dict(nodes=asked.nodes, directed=asked.directed,
        bidirected=asked.bidirected, treatment='X', outcome=['Y']))
    wrong['witness'].update(problem_sha256=sha(as_problem(p.nodes, p.directed, p.bidirected,
        p.treatment, p.outcome, p.context)), original_target={
            'treatment': p.treatment, 'outcome': p.outcome, 'context': p.context})
    with patch('cfm_id.dag_id_route.solve', return_value=wrong):
        result = submit(p, synthetic_review(p))
    assert result['nonidentification_proved'] is False
    assert result['native_state'] == 'NO_FORMULA_YET'


def test_multichar_treatment_and_original_graph_membership():
    p = as_problem(['Treatment', 'Outcome'], [('Treatment', 'Outcome')],
                   [('Treatment', 'Outcome')], 'Treatment', ['Outcome'])
    w = identify_or_report(p)['witness']
    assert check_failure(w, p)['passed']
    assert not check_failure(w)['passed']
    hedge = deepcopy(w['hedge'])
    hedge['grown_forest']['directed'].append(['foreign', 'Outcome'])
    assert not check_hedge(hedge, p)['passed']
    hedge = deepcopy(w['hedge'])
    hedge['grown_forest']['bidirected'] = []
    assert not check_hedge(hedge, p)['passed']


def test_first_derivation_step_cannot_change_original_edges():
    p = as_problem(['X', 'Y'], [('X', 'Y')], [], 'X', ['Y'])
    cert = identify_or_report(p)
    cert['derivation'][0]['graph']['bidirected'] = [['X', 'Y']]
    cert['certificate_sha256'] = sha({k: v for k, v in cert.items() if k != 'certificate_sha256'})
    assert not replay(cert, p)['passed']
