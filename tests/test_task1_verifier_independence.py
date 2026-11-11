"""The extended-design verifier recomputes independently from declared rules.

A defect injected into the proposer's shared ``assignment_probability`` /
``statistic`` must NOT change the verifier's oracle and must be reported as a
mismatch. This is the "solver and verifier do not share the computation
function" guarantee.
"""
from fractions import Fraction
import pytest

from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec
from pfn_pipeline._internal.identification.randomized_arm_family.support import SupportEngine
from pfn_pipeline._internal.identification.randomized_arm_family.support_verifier import verify_joint_support
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family.assignment_extensions import (
    UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign, CovariateBalanceRule)
from pfn_pipeline._internal.identification.randomized_arm_family.exposure_extensions import (
    WeightedExposureSpec, GroupedExposureSpec)

NODES = ("a", "b", "c", "d")
EDGES = (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"))
E1 = ExposureSpec("strict_majority_ties_low")


def network():
    return NetworkExposureSpec(network_id="f", node_ids=list(NODES), undirected_edges=list(EDGES))


def unequal():
    return UnequalProbabilityFixedQuotaDesign(
        nodes=NODES, m=2,
        assignment_probabilities={frozenset(("a", "b")): Fraction(1, 2),
                                  frozenset(("a", "c")): Fraction(1, 4),
                                  frozenset(("c", "d")): Fraction(1, 4)})


def test_verifier_ignores_buggy_assignment_probability(monkeypatch):
    design = unequal()
    expected = verify_joint_support(network=network(), design=design, exposure=E1,
                                    node_id="a", proposed={})["oracle"]

    def buggy(self, assignment):
        treated = (frozenset(n for n, v in assignment.items() if v)
                   if isinstance(assignment, dict) else frozenset())
        return Fraction(1, 6) if len(treated) == 2 else Fraction(0)

    monkeypatch.setattr(UnequalProbabilityFixedQuotaDesign, "assignment_probability", buggy)
    # Proposer follows the injected (normalized-but-wrong) law.
    bad = SupportEngine.joint_support(network=network(), assignment=AssignmentSpec(design),
                                      exposure=E1, node_id="a")
    assert bad != expected
    # Verifier recomputes from declared fields: oracle unchanged, mismatch reported.
    report = verify_joint_support(network=network(), design=design, exposure=E1,
                                  node_id="a", proposed=bad)
    assert report["oracle"] == expected
    assert report["ok"] is False
    assert report["mismatch"]


def test_verifier_ignores_buggy_weighted_statistic(monkeypatch):
    exp = WeightedExposureSpec(weights={"b": "1", "c": "2"}, mode="sum")
    expected = verify_joint_support(network=network(), design=unequal(), exposure=exp,
                                    node_id="a", proposed={})["oracle"]
    monkeypatch.setattr(WeightedExposureSpec, "statistic",
                        lambda self, a, n, g: Fraction(999))
    report = verify_joint_support(network=network(), design=unequal(), exposure=exp,
                                  node_id="a", proposed={})
    assert report["oracle"] == expected


def test_verifier_ignores_buggy_grouped_statistic(monkeypatch):
    exp = GroupedExposureSpec(groups={"g1": ("b",), "g2": ("c",)})
    expected = verify_joint_support(network=network(), design=unequal(), exposure=exp,
                                    node_id="a", proposed={})["oracle"]
    monkeypatch.setattr(GroupedExposureSpec, "statistic",
                        lambda self, a, n, g: ("BUG",))
    report = verify_joint_support(network=network(), design=unequal(), exposure=exp,
                                  node_id="a", proposed={})
    assert report["oracle"] == expected


def test_verifier_rerandomized_independent_of_base_method(monkeypatch):
    rr = RerandomizedBalancedDesign(
        base_design=UnequalProbabilityFixedQuotaDesign(
            nodes=NODES, m=2, unit_weights={"a": "2", "b": "1", "c": "1", "d": "1"}),
        balance_rule=CovariateBalanceRule(
            covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1"}}, tolerance="1/2"))
    expected = verify_joint_support(network=network(), design=rr, exposure=E1,
                                    node_id="a", proposed={})["oracle"]
    # Corrupting the base law must not move the verifier's rerandomized oracle.
    monkeypatch.setattr(UnequalProbabilityFixedQuotaDesign, "assignment_probability",
                        lambda self, assignment: Fraction(0))
    report = verify_joint_support(network=network(), design=rr, exposure=E1,
                                  node_id="a", proposed={})
    assert report["oracle"] == expected


def test_verifier_ignores_buggy_balance_formula(monkeypatch):
    rr = RerandomizedBalancedDesign(
        base_design=UnequalProbabilityFixedQuotaDesign(
            nodes=NODES, m=2, unit_weights=dict.fromkeys(NODES, "1")),
        balance_rule=CovariateBalanceRule(
            covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1"}}, tolerance="1/2"))
    expected = verify_joint_support(network=network(), design=rr, exposure=E1,
                                    node_id="a", proposed={})["oracle"]
    # A defective balance formula in the proposer must not move the verifier.
    monkeypatch.setattr(CovariateBalanceRule, "__call__", lambda self, treated: True)
    report = verify_joint_support(network=network(), design=rr, exposure=E1,
                                  node_id="a", proposed={})
    assert report["oracle"] == expected


def test_balance_covariate_scope_is_rejected():
    import pytest
    base = UnequalProbabilityFixedQuotaDesign(
        nodes=NODES, m=2, unit_weights=dict.fromkeys(NODES, "1"))
    bad_covariates = (
        {"x": {"a": "0", "b": "0", "c": "1", "d": "1", "e": "0"}},  # extra study-external node
        {"x": {"a": "0", "b": "0", "c": "1"}},                       # missing study node
        {"x": {"a": "0", "b": "0", "c": "1", "d": "1"},
         "y": {"a": "0", "b": "0", "c": "1"}},                       # covariates disagree
    )
    for covariates in bad_covariates:
        with pytest.raises(ValueError):
            RerandomizedBalancedDesign(
                base_design=base,
                balance_rule=CovariateBalanceRule(covariates=covariates, tolerance="1/2"))


@pytest.mark.parametrize('design', ['D4', 'D5', 'D6'])
@pytest.mark.parametrize('exposure', ['weighted', 'grouped'])
def test_partition_designs_replay_and_reject_shared_law_defect(monkeypatch, design, exposure):
    """Corrupt the producer into IID draws: the independent replay must reject it."""
    from pfn_pipeline import identification as ident
    nodes = tuple('ab' if design == 'D4' else 'abcdef' if design == 'D5' else 'abcd')
    net = dict(network_id='partition-proof', node_ids=list(nodes), undirected_edges=[('a', 'b')])
    common = dict(node_id='a', own_treatment_value=1, source='fixed synthetic law',
                  evidence='Declared partition and exact probabilities in this test.',
                  admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE')
    if exposure == 'weighted':
        common.update(exposure_definition='weighted_exposure_sum', exposure_weights={'b':'1'})
    else:
        common.update(exposure_definition='grouped_exposure', exposure_groups={'g':('b',)})
    if design == 'D4':
        build = ident.make_cluster_bernoulli_arm_task
        common.update(clusters=[nodes], cluster_probabilities=['1/2'])
        supported, probability = 1, Fraction(1, 2)
    elif design == 'D5':
        build = ident.make_multi_group_quota_arm_task
        common.update(groups=[('a','b'),('c','d'),('e','f')], treated_quotas=[1,1,1])
        supported, probability = 0, Fraction(1, 2)
    else:
        build = ident.make_two_stage_quota_arm_task
        common.update(groups=[('a','b'),('c','d')], quota_profiles=[(1,1),(0,2)],
                      profile_probabilities=['1/3','2/3'], profile_exclusion_admitted=True)
        supported, probability = 0, Fraction(1, 6)
    def task(level):
        value = str(level) if exposure == 'weighted' else f'[{level}]'
        return build(net, exposure_value=value, **common)
    good = ident.identify(task(supported))
    assert good.result['status'] == 'POINT'
    assert Fraction(good.result['certificate']['joint_arm_support_probability']) == probability
    assert ident.replay_population_identification(good).verification_status == 'VERIFIED'
    unsupported = task(1-supported)
    assert ident.identify(unsupported).result['status'] == 'UNSUPPORTED'
    monkeypatch.setattr(AssignmentSpec, 'full_assignment_probability',
                        lambda self, network, treatment: Fraction(1, 2**len(nodes)))
    corrupted = ident.identify(unsupported)
    assert corrupted.result['verification_status'] != 'VERIFIED'
    with pytest.raises(ValueError):
        ident.replay_population_identification(corrupted)

