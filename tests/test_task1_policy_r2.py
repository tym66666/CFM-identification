"""R2 (mean-signature sufficiency) now reaches the new designs D7/D8.

The fixed-policy value route R1B was already wired to the Task-1 designs; this
covers the remaining R2 route for a single policy mean. R2 additionally assumes
mean-signature sufficiency (an explicit A5 claim) and conditions on an E1-E5
signature. Support is recomputed independently by full enumeration (N<=8).
"""
import pytest
from fractions import Fraction

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_policy_r2 import (
    R2PolicyUnavailable, declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source, identify_verified_signature_policy,
    replay_verified_signature_policy)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context)

NODES = ('a', 'b', 'c', 'd')
EDGES = tuple((NODES[i], NODES[j]) for i in range(4) for j in range(i + 1, 4))
NAMES = ('known_assignment_law', 'full_vector_randomization', 'consistency',
         'fixed_pretreatment_network', 'finite_conditional_first_moments')


def _task1_design(kind, nodes):
    base = dict(kind='unequal_probability_fixed_quota_binary_v1',
                nodes=list(nodes), m=2, unit_weights={n: '1' for n in nodes})
    if kind == 'D7':
        return base
    return dict(kind='rerandomized_balanced_binary_v1', base_design=base,
                balance_rule=dict(tolerance='1/2',
                                  covariates={'x': {n: '0' for n in nodes}}))


def _study(kind, nodes=NODES, edges=EDGES):
    return declare_network_study(network_id='r2-task1', node_order=nodes, undirected_edges=edges,
        treatment_variable='AI', outcome_variable='sales', outcome_kind='continuous',
        context_reference='W:test', observation_regime='experimental',
        assignment_design=_task1_design(kind, nodes),
        protocol_provenance='reviewed synthetic design',
        network_provenance='reviewed fixed network',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def _assumptions():
    return tuple(Assumption(name=n, source='demo_specification', confirmed=True,
                            status='ADMITTED', evidence=['reviewed DGP protocol']) for n in NAMES)


def _run(st, policy=(1, 1, 0, 0), grouping='strict_majority_ties_low'):
    sig = declare_policy_signature(st, grouping=grouping)
    claim = admit_mean_signature_sufficiency(st, sig,
        assumption=Assumption(name='mean_signature_sufficiency', source='human_confirmation',
            status='ADMITTED', confirmed=True,
            evidence=['domain expert reviewed all-assignment mean-response restriction']),
        covered_nodes=st.node_order)
    from pfn_pipeline._internal.identification.randomized_arm_family import ExposureSpec
    exposure = ExposureSpec(grouping)
    degree = st.network().degree_map()
    cells = tuple((n, a, s) for n in st.node_order for a in (0, 1)
                  for s in exposure.states_for_degree(degree[n]))
    src = declare_signature_population_source(st, sig, source_id='A4 reviewed',
        operator='NODE_SIGNATURE_MEANS', outcome_nodes=st.node_order, signature_cells=cells,
        admission='ADMITTED', availability='SYMBOLIC_POPULATION_OPERATOR',
        provenance='independently reviewed symbolic population object')
    target = fixed_policy_target_from_context(st, tuple(policy), authority='TRUSTED_FIXTURE')
    return identify_verified_signature_policy(st, target, sig, (src,),
        assumptions=_assumptions(), sufficiency=claim)


@pytest.mark.parametrize('kind', ['D7', 'D8'])
def test_r2_policy_mean_point_for_new_designs(kind):
    result = _run(_study(kind))
    assert result.status == 'POINT' and result.verification_status == 'VERIFIED'
    assert result.theorem_id == 'R2_RANDOMIZED_MEAN_SIGNATURE_SUFFICIENCY_POLICY_POINT_V1'
    assert replay_verified_signature_policy(result) is True
    # Four equal-weighted nodes, each mapped to one observed signature arm.
    assert len(result.policy_node_classes) == 4
    assert all(Fraction(support) > 0 for support in result.node_class_support)


@pytest.mark.parametrize('kind', ['D7', 'D8'])
def test_r2_accepts_zero_policy_probability(kind):
    # The chosen policy need not itself be a possible assignment under q; the
    # node-class arm means still have positive support.
    result = _run(_study(kind), policy=(1, 1, 0, 0))
    assert result.status == 'POINT' and result.verification_status == 'VERIFIED'
    replay_verified_signature_policy(result)


def test_r2_certificate_tamper_fails_replay():
    result = _run(_study('D7'))
    from dataclasses import replace
    with pytest.raises(R2PolicyUnavailable):
        replay_verified_signature_policy(replace(result, policy_assignment_probability='1/999'))


@pytest.mark.parametrize('kind', ['D7', 'D8'])
@pytest.mark.parametrize('grouping', ['exact_treated_neighbor_count',
                                      'any_treated_neighbor',
                                      'three_level_treated_neighbor_fraction'])
def test_r2_existing_signatures_reach_new_designs(kind, grouping):
    result = _run(_study(kind), grouping=grouping)
    assert result.status == 'POINT' and result.verification_status == 'VERIFIED'
    replay_verified_signature_policy(result)
