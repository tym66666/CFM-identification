from fractions import Fraction
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, CompleteRandomizationDesignV1, HeterogeneousBernoulliDesignV1)
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec
from pfn_pipeline._internal.identification.randomized_arm_family.exposure_extensions import (
    WeightedExposureSpec, GroupedExposureSpec)
from pfn_pipeline._internal.identification.randomized_arm_family.support import SupportEngine
from pfn_pipeline._internal.identification.randomized_arm_family.support_verifier import verify_joint_support


def network():
    return NetworkExposureSpec(
        network_id="triangle", node_ids=["a", "b", "c"],
        undirected_edges=[("a", "b"), ("a", "c"), ("b", "c")])


def test_weighted_sum_is_fixed_and_exact():
    spec = WeightedExposureSpec(weights={"b": 2, "c": 1}, mode="sum")
    design = AssignmentSpec(CompleteRandomizationDesignV1(m=2))
    joint = SupportEngine.joint_support(network=network(), assignment=design, exposure=spec, node_id="a")
    assert sum(joint.values()) == 1
    assert joint[(1, Fraction(2))] == Fraction(1, 3)
    assert joint[(1, Fraction(1))] == Fraction(1, 3)
    assert joint[(0, Fraction(3))] == Fraction(1, 3)


def test_weighted_proportion_and_conditioning():
    spec = WeightedExposureSpec(weights={"b": 2, "c": 1}, mode="proportion")
    design = AssignmentSpec(CompleteRandomizationDesignV1(m=2))
    joint = SupportEngine.joint_support(network=network(), assignment=design, exposure=spec, node_id="a")
    cond = SupportEngine.conditional_exposure(joint_support=joint, own_treatment_value=1)
    assert cond[Fraction(2, 3)] == Fraction(1, 2)
    assert cond[Fraction(1, 3)] == Fraction(1, 2)


def test_grouped_exposure_preserves_coordinates():
    spec = GroupedExposureSpec(groups={"friends": ["b"], "colleagues": ["c"]})
    design = AssignmentSpec(CompleteRandomizationDesignV1(m=2))
    joint = SupportEngine.joint_support(network=network(), assignment=design, exposure=spec, node_id="a")
    assert (0, (1, 1)) in joint and (1, (1, 0)) in joint and (1, (0, 1)) in joint
    assert sum(joint.values()) == 1


def test_independent_verifier_matches_d1_and_d2():
    spec = GroupedExposureSpec(groups={"all": ["b", "c"]})
    designs = (
        AssignmentSpec(CompleteRandomizationDesignV1(m=2)),
        AssignmentSpec(HeterogeneousBernoulliDesignV1(
            propensities={"a": "1/2", "b": "1/3", "c": "1/4"})),
    )
    for design in designs:
        joint = SupportEngine.joint_support(network=network(), assignment=design,
                                            exposure=spec, node_id="a")
        report = verify_joint_support(network=network(), design=design,
                                      exposure=spec, node_id="a", proposed=joint)
        assert report["ok"], report["mismatch"]
