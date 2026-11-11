"""Hand-computed checks for the four task-1 target families.

These are verification-helper checks, not formal identification: the helper
recomputes target values from a supplied potential-response table. The formal
identification route is the certificate path (``identify`` + backend).
"""
from fractions import Fraction

from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, CompleteRandomizationDesignV1)
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family.assignment_extensions import (
    UnequalProbabilityFixedQuotaDesign)
from tests.task1_target_helpers import (
    local_direct_mean, peer_spillover_mean, policy_mean, policy_contrast)

NODES = ("a", "b", "c", "d")
EDGES = (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"))
E1 = ExposureSpec("strict_majority_ties_low")
ASSUMPTIONS = {"consistency": True, "random_assignment": True, "exposure_sufficiency": True}


def network():
    return NetworkExposureSpec(network_id="fixture", node_ids=list(NODES), undirected_edges=list(EDGES))


def d2(m):
    return AssignmentSpec(CompleteRandomizationDesignV1(m=m))


def arm_outcomes():
    """Y_i(a,s): own=1 -> 5, own=0 -> 1, with spillover bump to 7 at (0,1)."""
    outcomes = {}
    for node in NODES:
        outcomes[(node, 1, 0)] = Fraction(5)
        outcomes[(node, 1, 1)] = Fraction(9)
        outcomes[(node, 0, 0)] = Fraction(1)
        outcomes[(node, 0, 1)] = Fraction(7)
    return outcomes


def unequal():
    return UnequalProbabilityFixedQuotaDesign(
        nodes=NODES, m=2,
        assignment_probabilities={
            frozenset(("a", "b")): Fraction(1, 2),
            frozenset(("a", "c")): Fraction(1, 4),
            frozenset(("c", "d")): Fraction(1, 4),
        })


def test_local_direct_mean_point():
    result = local_direct_mean(network=network(), design=d2(2), exposure=E1,
                               outcomes=arm_outcomes(), exposure_state=0,
                               assumptions=ASSUMPTIONS)
    assert result.status == "POINT"
    assert result.value == Fraction(4)  # 5 - 1 uniformly


def test_local_direct_mean_unsupported_zero_support():
    result = local_direct_mean(network=network(), design=d2(2), exposure=E1,
                               outcomes=arm_outcomes(), exposure_state=1,
                               assumptions=ASSUMPTIONS)
    assert result.status == "UNSUPPORTED"


def test_peer_spillover_mean_point():
    result = peer_spillover_mean(network=network(), design=d2(2), exposure=E1,
                                 outcomes=arm_outcomes(), own_treatment_value=0,
                                 exposed_state=1, reference_state=0,
                                 assumptions=ASSUMPTIONS)
    assert result.status == "POINT"
    assert result.value == Fraction(6)  # 7 - 1 uniformly


def test_peer_spillover_mean_unsupported():
    result = peer_spillover_mean(network=network(), design=d2(2), exposure=E1,
                                 outcomes=arm_outcomes(), own_treatment_value=1,
                                 exposed_state=1, reference_state=0,
                                 assumptions=ASSUMPTIONS)
    assert result.status == "UNSUPPORTED"


def test_policy_mean_expectation():
    result = policy_mean(network=network(), design=d2(2),
                         outcomes=lambda treated: 2 * len(treated),
                         assumptions=ASSUMPTIONS)
    assert result.status == "POINT"
    assert result.value == Fraction(4)  # E[2|A|] = 2*m = 4


def test_policy_contrast_difference():
    result = policy_contrast(network=network(), design_a=d2(2), design_b=d2(1),
                             outcomes=lambda treated: 2 * len(treated),
                             assumptions=ASSUMPTIONS)
    assert result.status == "POINT"
    assert result.value == Fraction(2)  # 4 - 2


def test_new_design_target_uses_unified_support():
    result = local_direct_mean(network=network(), design=unequal(), exposure=E1,
                               outcomes=arm_outcomes(), exposure_state=0,
                               assumptions=ASSUMPTIONS)
    assert result.status == "POINT"
    assert result.value == Fraction(4)


def test_missing_assumptions_gate():
    result = local_direct_mean(network=network(), design=d2(2), exposure=E1,
                               outcomes=arm_outcomes(), exposure_state=0,
                               assumptions=None)
    assert result.status == "UNSUPPORTED"
    assert "not explicitly confirmed" in result.reason


def test_design_standardized_does_not_require_exposure_sufficiency():
    # Design-standardized contrast needs only consistency + random_assignment.
    result = local_direct_mean(network=network(), design=d2(2), exposure=E1,
                               outcomes=arm_outcomes(), exposure_state=0,
                               assumptions={"consistency": True, "random_assignment": True})
    assert result.status == "POINT"
    assert result.interpretation == "design_standardized_contrast"
    assert result.exposure_sufficiency_adopted is None


def test_exposure_sufficiency_is_a_separate_interpretation():
    result = local_direct_mean(network=network(), design=d2(2), exposure=E1,
                               outcomes=arm_outcomes(), exposure_state=0,
                               assumptions={"consistency": True, "random_assignment": True,
                                            "exposure_sufficiency": True})
    assert result.status == "POINT"
    assert result.value == Fraction(4)  # numeric value unchanged by the extra interpretation
    assert result.interpretation == "causal_effect_under_exposure_sufficiency"
    assert result.exposure_sufficiency_adopted is True


def test_rejecting_exposure_sufficiency_keeps_design_standardized_effect():
    result = local_direct_mean(network=network(), design=d2(2), exposure=E1,
                               outcomes=arm_outcomes(), exposure_state=0,
                               assumptions={"consistency": True, "random_assignment": True,
                                            "exposure_sufficiency": False})
    assert result.status == "POINT"
    assert result.interpretation == "design_standardized_contrast"
    assert result.exposure_sufficiency_adopted is False
