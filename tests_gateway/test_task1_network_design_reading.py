"""Task-1 design/exposure reading and review: recognition, gap-blocking, conversion.

This is the reading/review layer (cfm_id_llm + cfm_id adapter), NOT the native
math or certificate. It checks that:

  * the business reading recognises the new design/exposure kinds;
  * incomplete or contradictory declarations are blocked at review time
    (exact-normalized set probabilities, balance covariate scope, weights/mode/
    groups completeness) — a gap is blocked, never silently filled;
  * the adapter converts reviewed fields to the native wire contract;
  * existing D1-D6 / E1-E5 reading is unchanged (backward compatibility).

It does not import jsonschema and does not re-assert native support values
(those live in tests/test_task1_*).
"""
from fractions import Fraction

import pytest

from cfm_id_llm.network_policy_reading import Assignment, Exposure
from cfm_id_llm import network_design_reading as fields
from cfm_id import network_design_adapter as adapter
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

NODES = ["a", "b", "c", "d"]
EDGES = [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]
NET = NetworkExposureSpec(network_id="f", node_ids=NODES, undirected_edges=EDGES)
E1 = Exposure(kind="STRICT_MAJORITY_TIES_LOW", source_ids=["s"])


def unequal(**kw):
    base = dict(kind="UNEQUAL_PROBABILITY_FIXED_QUOTA", probabilities=None, fixed_count=2,
                treated_sets=[["a", "b"], ["a", "c"], ["c", "d"]],
                set_probabilities=["1/2", "1/4", "1/4"], source_ids=["s"])
    base.update(kw)
    return Assignment(**base)


def rerandomized(**kw):
    base = dict(kind="RERANDOMIZED_BALANCED", probabilities=None, fixed_count=2,
                unit_weights={"a": "1", "b": "1", "c": "1", "d": "1"},
                balance_covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1"}},
                balance_tolerance="1/2", source_ids=["s"])
    base.update(kw)
    return Assignment(**base)


# --- recognition -----------------------------------------------------------

def test_new_kinds_are_recognised():
    assert "UNEQUAL_PROBABILITY_FIXED_QUOTA" in fields.DESIGN_FIELDS
    assert "RERANDOMIZED_BALANCED" in fields.DESIGN_FIELDS
    assert fields.EXPOSURE_GROUPS["WEIGHTED_EXPOSURE"] == "weighted_exposure"
    assert fields.EXPOSURE_GROUPS["GROUPED_EXPOSURE"] == "grouped_exposure"


# --- gap blocking (缺项阻断) -----------------------------------------------

def test_valid_unequal_design_passes_review():
    fields.validate_components(unequal(), E1, NODES, EDGES)
    assert fields.missing_assignment(unequal(), NODES) == []


def test_non_normalized_set_probabilities_are_blocked():
    with pytest.raises(ValueError):
        fields.validate_components(unequal(set_probabilities=["1/2", "1/4", "1/8"]), E1, NODES, EDGES)


def test_incomplete_unit_weight_scope_is_reported():
    missing = fields.missing_assignment(
        unequal(treated_sets=None, set_probabilities=None, unit_weights={"a": "1", "b": "1"}), NODES)
    assert missing


def test_balance_covariate_scope_is_blocked():
    # extra study-external node
    with pytest.raises(ValueError):
        fields.validate_components(
            rerandomized(balance_covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1", "e": "0"}}),
            E1, NODES, EDGES)
    # missing study node
    with pytest.raises(ValueError):
        fields.validate_components(
            rerandomized(balance_covariates={"x": {"a": "0", "b": "0", "c": "1"}}),
            E1, NODES, EDGES)
    # covariates disagree on node set
    with pytest.raises(ValueError):
        fields.validate_components(
            rerandomized(balance_covariates={
                "x": {"a": "0", "b": "0", "c": "1", "d": "1"},
                "y": {"a": "0", "b": "0", "c": "1"}}),
            E1, NODES, EDGES)


def test_weighted_exposure_requires_weights_and_mode():
    w_ok = Exposure(kind="WEIGHTED_EXPOSURE", weights={"b": "1", "c": "2"}, mode="sum", source_ids=["s"])
    fields.validate_components(unequal(), w_ok, NODES, EDGES)
    assert fields.missing_exposure(w_ok, NODES) == []

    w_missing_mode = Exposure(kind="WEIGHTED_EXPOSURE", weights={"b": "1"}, source_ids=["s"])
    assert "exposure.mode" in fields.missing_exposure(w_missing_mode, NODES)
    with pytest.raises(ValueError):
        fields.validate_components(unequal(), w_missing_mode, NODES, EDGES)


def test_grouped_exposure_requires_groups():
    g_ok = Exposure(kind="GROUPED_EXPOSURE", groups={"friend": ["b"], "colleague": ["c"]}, source_ids=["s"])
    fields.validate_components(unequal(), g_ok, NODES, EDGES)
    assert fields.missing_exposure(g_ok, NODES) == []

    g_missing = Exposure(kind="GROUPED_EXPOSURE", source_ids=["s"])
    assert "exposure.groups" in fields.missing_exposure(g_missing, NODES)


def test_weighted_coordinate_bounds():
    # Node a has neighbours b, c; declared weights sum to 1 + 2 = 3.
    w_sum = Exposure(kind="WEIGHTED_EXPOSURE", weights={"b": "1", "c": "2"}, mode="sum", source_ids=["s"])
    fields.validate_exposure_coordinate(w_sum, "a", "3", EDGES)
    for bad in ("4", "-1"):
        with pytest.raises(ValueError):
            fields.validate_exposure_coordinate(w_sum, "a", bad, EDGES)
    w_prop = Exposure(kind="WEIGHTED_EXPOSURE", weights={"b": "1", "c": "2"}, mode="proportion", source_ids=["s"])
    fields.validate_exposure_coordinate(w_prop, "a", "1/3", EDGES)
    with pytest.raises(ValueError):
        fields.validate_exposure_coordinate(w_prop, "a", "4/3", EDGES)


def test_grouped_coordinate_must_be_a_group_vector():
    # Coordinates are one treated-count per group, never a single 0/1.
    g = Exposure(kind="GROUPED_EXPOSURE", groups={"friend": ["b"], "colleague": ["c"]}, source_ids=["s"])
    fields.validate_exposure_coordinate(g, "a", "[1, 0]", EDGES)
    for bad in ("1", "0", "[1]", "[2, 0]", "[0, 1, 0]"):
        with pytest.raises(ValueError):
            fields.validate_exposure_coordinate(g, "a", bad, EDGES)


# --- adapter conversion ----------------------------------------------------

def test_adapter_converts_reviewed_fields_to_native_contract():
    d = adapter.task1_design(unequal(), NET)
    assert d.kind == "unequal_probability_fixed_quota_binary_v1"
    assert d.m == 2

    d2 = adapter.task1_design(rerandomized(), NET)
    assert d2.kind == "rerandomized_balanced_binary_v1"
    assert set(d2.balance_rule.covariates["x"]) == set(NODES)


def test_design_payload_matches_native_types():
    payload = adapter.design_payload(unequal(), nodes=tuple(NODES))
    assert payload["kind"] == "unequal_probability_fixed_quota_binary_v1"
    assert payload["nodes"] == tuple(NODES)
    rr = adapter.design_payload(rerandomized(), nodes=tuple(NODES))
    assert rr["kind"] == "rerandomized_balanced_binary_v1"
    assert rr["base_design"]["kind"] == "unequal_probability_fixed_quota_binary_v1"


# --- backward compatibility (旧能力兼容) -----------------------------------

def test_existing_design_reading_unchanged():
    d2 = Assignment(kind="UNIFORM_FIXED_QUOTA", probabilities=None, fixed_count=2, source_ids=["s"])
    fields.validate_components(d2, E1, NODES, EDGES)
    assert fields.missing_assignment(d2, NODES) == []
    assert adapter.design_payload(d2)["kind"] == "complete_randomization_binary_v1"
    assert adapter.exposure_payload(E1)["grouping"] == "strict_majority_ties_low"
