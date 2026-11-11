"""Weighted/grouped exposures now reach the formal arm-mean certificate.

They are carried by the wire contract's grouping + exposure_weights /
exposure_groups fields and resolved by exact full-assignment enumeration.
"""
import pytest

from pfn_pipeline import identification as ident
from pfn_pipeline._internal.identification.schemas import (
    UnequalProbabilityFixedQuotaDesignV1, RandomizedNetworkArmMeanContractV1)

NODES = ["a", "b", "c", "d"]
EDGES = [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]


def network():
    return dict(network_id="f", node_ids=NODES, undirected_edges=EDGES)


def design():
    return UnequalProbabilityFixedQuotaDesignV1(
        nodes=tuple(NODES), m=2, unit_weights={"a": "2", "b": "1", "c": "1", "d": "1"})


def _identify(**kw):
    task = ident.make_unequal_probability_fixed_quota_arm_task(
        network(), design=design(), node_id="a", own_treatment_value=1,
        source="s", evidence="e", admitted=True, synthetic=True,
        query_authority="TRUSTED_FIXTURE", **kw)
    return ident.identify(task).result


def test_weighted_exposure_certificate():
    result = _identify(exposure_definition="weighted_exposure_sum", exposure_value="1",
                       exposure_weights={"b": "1", "c": "2"})
    assert result["status"] == "POINT"
    assert result["verification_status"] == "VERIFIED"
    assert result["certificate"]["joint_arm_support_probability"] == "2/9"


def test_grouped_exposure_certificate():
    result = _identify(exposure_definition="grouped_exposure", exposure_value="[1, 0]",
                       exposure_groups={"g1": ("b",), "g2": ("c",)})
    assert result["status"] == "POINT"
    assert result["verification_status"] == "VERIFIED"
    assert result["certificate"]["joint_arm_support_probability"] == "2/9"


def test_weighted_exposure_replay_verified():
    result = _identify(exposure_definition="weighted_exposure_sum", exposure_value="1",
                       exposure_weights={"b": "1", "c": "2"})
    assert result["verification_status"] == "VERIFIED"
    # The certificate carries the W/G declaration and the queried state.
    assert result["certificate"]["exposure_grouping"] == "weighted_exposure_sum"
    assert result["query"]["exposure_value"] == "1"


def test_contract_requires_wg_params():
    with pytest.raises(Exception):
        RandomizedNetworkArmMeanContractV1(
            design=design(), grouping="weighted_exposure_sum")  # missing exposure_weights
    with pytest.raises(Exception):
        RandomizedNetworkArmMeanContractV1(
            design=design(), grouping="strict_majority_ties_low",
            exposure_weights={"b": "1"})  # params only for W/G


def test_existing_design_weighted_exposure_certificate():
    # W/G works on the pre-existing D2 design too, not only D7/D8.
    task = ident.make_complete_randomization_arm_task(
        network(), m=2, node_id="a", own_treatment_value=1, exposure_value="1",
        source="s", evidence="e", exposure_definition="weighted_exposure_sum",
        exposure_weights={"b": "1", "c": "2"}, admitted=True, synthetic=True,
        query_authority="TRUSTED_FIXTURE")
    result = ident.identify(task).result
    assert result["status"] == "POINT"
    assert result["verification_status"] == "VERIFIED"
    assert result["certificate"]["joint_arm_support_probability"] == "1/6"


def test_existing_design_grouped_exposure_certificate():
    task = ident.make_heterogeneous_bernoulli_arm_task(
        network(), propensities={"a": "1/2", "b": "1/2", "c": "1/2", "d": "1/2"},
        node_id="a", own_treatment_value=1, exposure_value="[1, 0]",
        source="s", evidence="e", exposure_definition="grouped_exposure",
        exposure_groups={"g1": ("b",), "g2": ("c",)}, admitted=True, synthetic=True,
        query_authority="TRUSTED_FIXTURE")
    result = ident.identify(task).result
    assert result["status"] == "POINT"
    assert result["verification_status"] == "VERIFIED"
    assert result["certificate"]["joint_arm_support_probability"] == "1/8"

