"""Weighted/grouped exposure through the BATCH and COMPOSITION paths.

The single-arm certificate already carried W/G (see
``test_task1_weighted_grouped_certificate.py``). These tests cover the batch
tensor (per-node reachable state union, non-rectangular, unreachable cells are
UNSUPPORTED not POINT) and the R1A composition (string coordinate parsed back
to exact Fractions/tuples, checked against the independent oracle).
"""
import pytest

from pfn_pipeline import identification as ident
from pfn_pipeline.identification_batch import identify_randomized_network_batch
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_composition import (
    identify_verified_node_effect, CompositionUnavailable)

NODES = ["a", "b", "c", "d"]
EDGES = [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]
PROP = {n: "1/2" for n in NODES}


def _network():
    return dict(network_id="f", node_ids=NODES, undirected_edges=EDGES)


def _weighted_task(**kw):
    return ident.make_heterogeneous_bernoulli_arm_task(
        _network(), propensities=PROP, node_id="a", own_treatment_value=1,
        exposure_value="1", source="s", evidence="e",
        exposure_definition="weighted_exposure_sum", exposure_weights={"b": "1", "c": "2"},
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE", **kw)


def _grouped_task():
    return ident.make_heterogeneous_bernoulli_arm_task(
        _network(), propensities=PROP, node_id="a", own_treatment_value=1,
        exposure_value="[1, 0]", source="s", evidence="e",
        exposure_definition="grouped_exposure", exposure_groups={"g1": ("b",), "g2": ("c",)},
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE")


def _full_law_source(task, batch):
    return declare_a4_source(task, source_id="full law", operator="NODE_FULL_LAW",
        provenance="x", admission="ADMITTED", availability="SYMBOLIC_POPULATION_OPERATOR",
        outcome_nodes=batch.node_ids, node_order=batch.node_ids)


def test_weighted_batch_uses_canonical_reachable_states():
    batch = identify_randomized_network_batch(_weighted_task())
    # Reachable weighted sums for the whole graph, as canonical strings.
    assert batch.exposure_states == ("0", "1", "2", "3")
    # Every nonzero cell is POINT; every zero cell is explicitly UNSUPPORTED.
    for node in batch.node_ids:
        for a in (0, 1):
            for s in batch.exposure_states:
                cell = batch.cell(node, a, s)
                if cell["joint_support"] == "0":
                    assert cell["status"] == "UNSUPPORTED"
                else:
                    assert cell["status"] == "POINT"


def test_grouped_batch_uses_group_vectors():
    batch = identify_randomized_network_batch(_grouped_task())
    assert batch.exposure_states == ("[0, 0]", "[0, 1]", "[1, 0]", "[1, 1]")
    # A single 0/1 is never a grouped coordinate.
    with pytest.raises(ValueError):
        batch.cell("a", 1, "1")


def test_weighted_composition_reaches_point_with_independent_replay():
    task = _weighted_task()
    batch = identify_randomized_network_batch(task)
    result = identify_verified_node_effect(
        batch, _full_law_source(task, batch), node_id="a", kind="SPILLOVER",
        reference_exposure="0", comparison_exposure="1", spillover_own_treatment=1)
    assert result.status == "POINT" and result.verification_status == "VERIFIED"
    # Both arms are POINT, and the functional keeps the string coordinates.
    from fractions import Fraction
    assert all(Fraction(x) > 0 for x in result.population_arm_support)
    assert "S_a=1" in result.identified_functional


def test_grouped_composition_reaches_point():
    task = _grouped_task()
    batch = identify_randomized_network_batch(task)
    result = identify_verified_node_effect(
        batch, _full_law_source(task, batch), node_id="a", kind="SPILLOVER",
        reference_exposure="[0, 0]", comparison_exposure="[1, 0]", spillover_own_treatment=1)
    assert result.status == "POINT" and result.verification_status == "VERIFIED"
    assert "S_a=[1, 0]" in result.identified_functional


def test_unreachable_weighted_coordinate_is_not_silently_used():
    task = _weighted_task()
    batch = identify_randomized_network_batch(task)
    # Node a's neighbours carry weights 1 and 2, so sum 7 is impossible.
    with pytest.raises(CompositionUnavailable):
        identify_verified_node_effect(
            batch, _full_law_source(task, batch), node_id="a", kind="SPILLOVER",
            reference_exposure="0", comparison_exposure="7", spillover_own_treatment=1)
