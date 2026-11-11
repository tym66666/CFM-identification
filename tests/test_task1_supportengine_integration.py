"""Unified SupportEngine integration checks for task-1 designs and exposures.

The independent brute-force oracle ``verify_joint_support`` never calls
SupportEngine.  We also cross-check the analytic neighbor-count path against
exact enumeration for the existing typed D1-D6 designs.
"""
from fractions import Fraction

from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, CompleteRandomizationDesignV1, HeterogeneousBernoulliDesignV1)
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family.support import SupportEngine
from pfn_pipeline._internal.identification.randomized_arm_family.assignment_extensions import (
    UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign)
from pfn_pipeline._internal.identification.randomized_arm_family.exposure_extensions import (
    WeightedExposureSpec, GroupedExposureSpec)
from pfn_pipeline._internal.identification.randomized_arm_family.support_verifier import verify_joint_support


NODES = ("a", "b", "c", "d")
EDGES = (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"))

E1 = ExposureSpec("strict_majority_ties_low")
E4 = ExposureSpec("exact_treated_neighbor_count")
WEIGHTED_SUM = WeightedExposureSpec(weights={"b": 1, "c": 2}, mode="sum")
WEIGHTED_PROP = WeightedExposureSpec(weights={"b": 1, "c": 2}, mode="proportion")
GROUPED = GroupedExposureSpec(groups={"friend": ("b",), "colleague": ("c",)})


def network():
    return NetworkExposureSpec(network_id="fixture", node_ids=list(NODES), undirected_edges=list(EDGES))


def unequal():
    return UnequalProbabilityFixedQuotaDesign(
        nodes=NODES, m=2,
        assignment_probabilities={
            frozenset(("a", "b")): Fraction(1, 2),
            frozenset(("a", "c")): Fraction(1, 4),
            frozenset(("c", "d")): Fraction(1, 4),
        })


def rerandomized():
    return RerandomizedBalancedDesign(unequal(), lambda t: "a" in t)


def existing_designs():
    return (
        AssignmentSpec(CompleteRandomizationDesignV1(m=2)),
        AssignmentSpec(HeterogeneousBernoulliDesignV1(propensities={n: "1/2" for n in NODES})),
    )


def assert_matches_oracle(design, exposure):
    assignment = design if isinstance(design, AssignmentSpec) else AssignmentSpec(design)
    joint = SupportEngine.joint_support(network=network(), assignment=assignment,
                                        exposure=exposure, node_id="a")
    report = verify_joint_support(network=network(), design=assignment,
                                  exposure=exposure, node_id="a", proposed=joint)
    assert report["ok"], report["mismatch"]


def test_new_designs_with_old_exposures_match_oracle():
    for design in (unequal(), rerandomized()):
        for exposure in (E1, E4):
            assert_matches_oracle(design, exposure)


def test_new_designs_with_new_exposures_match_oracle():
    for design in (unequal(), rerandomized()):
        for exposure in (WEIGHTED_SUM, WEIGHTED_PROP, GROUPED):
            assert_matches_oracle(design, exposure)


def test_existing_designs_with_new_exposures_match_oracle():
    for design in existing_designs():
        for exposure in (WEIGHTED_SUM, WEIGHTED_PROP, GROUPED):
            assert_matches_oracle(design, exposure)


def test_existing_designs_old_exposures_analytic_matches_enumeration():
    for design in existing_designs():
        for exposure in (E1, E4):
            analytic = SupportEngine._joint_support_analytic(network(), design, exposure, "a")
            enumerated = SupportEngine._joint_support_enumeration(network(), design, exposure, "a")
            assert analytic == enumerated


def test_existing_designs_old_exposures_match_oracle():
    for design in existing_designs():
        for exposure in (E1, E4):
            assert_matches_oracle(design, exposure)
