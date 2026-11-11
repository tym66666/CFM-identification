"""Task-1 new designs through the native certificate backend and business adapter.

The unequal fixed-quota and rerandomized-balanced designs are wired into the
frozen randomized-network arm theorem backend (exact full-assignment
enumeration, N<=8). Hand-checked support values act as an independent oracle.
"""
from fractions import Fraction

from pfn_pipeline import identification as ident
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, UnequalProbabilityFixedQuotaDesignV1,
    RerandomizedBalancedDesignV1, CovariateBalanceRuleV1)
from cfm_id import network_design_adapter as adapter
from cfm_id_llm.network_policy_reading import Assignment, Exposure
from cfm_id_llm import network_design_reading as reading

NODES = ["a", "b", "c", "d"]
EDGES = [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]


def network():
    return NetworkExposureSpec(network_id="fixture", node_ids=list(NODES), undirected_edges=list(EDGES))


def unequal_treated_sets():
    return UnequalProbabilityFixedQuotaDesignV1(
        nodes=tuple(NODES), m=2,
        treated_sets=(("a", "b"), ("a", "c"), ("c", "d")),
        set_probabilities=("1/2", "1/4", "1/4"))


def unequal_unit_weights():
    return UnequalProbabilityFixedQuotaDesignV1(
        nodes=tuple(NODES), m=2,
        unit_weights={"a": "2", "b": "1", "c": "1", "d": "1"})


def rerandomized():
    base = UnequalProbabilityFixedQuotaDesignV1(
        nodes=tuple(NODES), m=2,
        treated_sets=(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d"), ("b", "c")),
        set_probabilities=("1/6", "1/6", "1/6", "1/6", "1/6", "1/6"))
    rule = CovariateBalanceRuleV1(
        tolerance="1/2", covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1"}})
    return RerandomizedBalancedDesignV1(base_design=base, balance_rule=rule)


def _identify(task):
    result = ident.identify(task)
    assert result.result["status"] == "POINT", result.result.get("reason_code")
    assert result.result["verification_status"] == "VERIFIED"
    return result.result


def test_unequal_treated_sets_law_point():
    task = ident.make_unequal_probability_fixed_quota_arm_task(
        network(), design=unequal_treated_sets(), node_id="a",
        own_treatment_value=1, exposure_value=0,
        source="s", evidence="e", exposure_definition="strict_majority",
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE")
    result = _identify(task)
    # a's neighbors are b and c (degree 2). For own=1: treated sets {a,b} and
    # {a,c} each leave exactly one neighbor treated -> S=0. So support = 3/4.
    assert Fraction(result["certificate"]["joint_arm_support_probability"]) == Fraction(3, 4)


def test_unequal_unit_weights_law_point():
    task = ident.make_unequal_probability_fixed_quota_arm_task(
        network(), design=unequal_unit_weights(), node_id="a",
        own_treatment_value=1, exposure_value=0,
        source="s", evidence="e", exposure_definition="strict_majority",
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE")
    result = _identify(task)
    # q({a,b})=q({a,c})=q({a,d})=2/9; all leave <=1 neighbor treated -> S=0.
    assert Fraction(result["certificate"]["joint_arm_support_probability"]) == Fraction(2, 3)


def test_rerandomized_balanced_point():
    task = ident.make_rerandomized_balanced_arm_task(
        network(), design=rerandomized(), node_id="a",
        own_treatment_value=0, exposure_value=1,
        source="s", evidence="e", exposure_definition="strict_majority",
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE")
    result = _identify(task)
    # Balanced size-2 sets are {a,c},{a,d},{b,c},{b,d}, each weight 1/4. For
    # own=0 only {b,c} gives a both treated neighbors -> S=1. Support = 1/4.
    assert Fraction(result["certificate"]["joint_arm_support_probability"]) == Fraction(1, 4)


def test_zero_support_arm_rejected_consistently():
    task = ident.make_unequal_probability_fixed_quota_arm_task(
        network(), design=unequal_treated_sets(), node_id="a",
        own_treatment_value=0, exposure_value=1,
        source="s", evidence="e", exposure_definition="strict_majority",
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE")
    result = ident.identify(task).result
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "ZERO_ARM_SUPPORT"


def test_adapter_task1_design_builds_native_design():
    business = Assignment(kind="UNEQUAL_PROBABILITY_FIXED_QUOTA", probabilities=None,
                          fixed_count=2, treated_sets=[["a", "b"], ["a", "c"], ["c", "d"]],
                          set_probabilities=["1/2", "1/4", "1/4"], source_ids=["s"])
    design = adapter.task1_design(business, network())
    assert isinstance(design, UnequalProbabilityFixedQuotaDesignV1)
    assert design.m == 2
    assert design.treated_sets == (("a", "b"), ("a", "c"), ("c", "d"))


def test_adapter_task1_design_rerandomized():
    business = Assignment(kind="RERANDOMIZED_BALANCED", probabilities=None, fixed_count=2,
                          unit_weights={"a": "2", "b": "1", "c": "1", "d": "1"},
                          balance_covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1"}},
                          balance_tolerance="1/2", source_ids=["s"])
    design = adapter.task1_design(business, network())
    assert isinstance(design, RerandomizedBalancedDesignV1)
    assert design.base_design.unit_weights == {"a": "2", "b": "1", "c": "1", "d": "1"}


def test_reading_layer_validate_new_designs():
    ok = Assignment(kind="RERANDOMIZED_BALANCED", probabilities=None, fixed_count=2,
                    treated_sets=[["a", "b"], ["a", "c"], ["c", "d"]],
                    set_probabilities=["1/2", "1/4", "1/4"],
                    balance_covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1"}},
                    balance_tolerance="1/2", source_ids=["s"])
    exposure = Exposure(kind="STRICT_MAJORITY_TIES_LOW", source_ids=["s"])
    reading.validate_components(ok, exposure, NODES, EDGES)
    assert reading.missing_assignment(ok, NODES) == []


def test_reading_layer_rejects_bad_new_design():
    import pytest
    exposure = Exposure(kind="STRICT_MAJORITY_TIES_LOW", source_ids=["s"])
    with pytest.raises(ValueError):
        reading.validate_components(
            Assignment(kind="UNEQUAL_PROBABILITY_FIXED_QUOTA", probabilities=None, fixed_count=2,
                       treated_sets=[["a", "b"], ["a", "c"]], set_probabilities=["1/2", "1/4"],
                       source_ids=["s"]),
            exposure, NODES, EDGES)
