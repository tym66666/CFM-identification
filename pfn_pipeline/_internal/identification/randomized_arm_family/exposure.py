"""Pure treated-reference count -> exposure-state grouping (E1/E2/E3).

This is a target-standardization grouping, not an exposure-sufficiency claim.
The unit's network degree and the treated-neighbor count are supplied by the
fixed pretreatment network and the assignment component, respectively.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..schemas import NetworkExposureSpec

GROUP_E1 = "strict_majority_ties_low"
GROUP_E2 = "three_level_treated_neighbor_fraction"
GROUP_E3 = "pretreatment_core_collaborator_majority"
GROUP_E4 = "exact_treated_neighbor_count"
GROUP_E5 = "any_treated_neighbor"
ExposureGrouping = Literal[
    "strict_majority_ties_low", "three_level_treated_neighbor_fraction",
    "pretreatment_core_collaborator_majority",
    "exact_treated_neighbor_count", "any_treated_neighbor",
]


@dataclass(frozen=True)
class ExposureSpec:
    """Internal adapter over the grouping field in the existing theorem contract."""
    grouping: ExposureGrouping
    core_collaborators: dict[str, tuple[str, ...]] | None = None

    def __post_init__(self) -> None:
        if self.grouping not in (GROUP_E1, GROUP_E2, GROUP_E3, GROUP_E4, GROUP_E5):
            raise ValueError("Unsupported exposure grouping")
        if self.grouping == GROUP_E3 and not self.core_collaborators:
            raise ValueError("E3 requires a pre-treatment core collaborator map")
        if self.grouping != GROUP_E3 and self.core_collaborators is not None:
            raise ValueError("Only E3 can declare core collaborators")

    def reference_nodes(self, network: NetworkExposureSpec, node_id: str) -> frozenset[str] | None:
        """E1/E2 use all N(i); E3 uses the pre-treatment C_i instead."""
        if self.grouping != GROUP_E3:
            return None
        if set(self.core_collaborators) != set(network.node_ids):
            raise ValueError("E3 requires one declared C_i for every fixed-network node")
        neighbors = {node: set() for node in network.node_ids}
        for left, right in network.undirected_edges:
            neighbors[left].add(right)
            neighbors[right].add(left)
        for node, members in self.core_collaborators.items():
            if not members or len(set(members)) != len(members):
                raise ValueError("E3 C_i must be nonempty with no duplicates")
            if not set(members) <= neighbors[node]:
                raise ValueError("E3 C_i must be a subset of the true pretreatment neighbors")
        return frozenset(self.core_collaborators[node_id])

    @property
    def states(self) -> tuple[int, ...]:
        return (0, 1, 2) if self.grouping == GROUP_E2 else (0, 1)

    def states_for_degree(self, degree: int) -> tuple[int, ...]:
        if degree < 0:
            raise ValueError("Network degree cannot be negative")
        return tuple(range(degree + 1)) if self.grouping == GROUP_E4 else self.states

    def classify(self, treated_neighbors: int, degree: int) -> int:
        """Exact count / binary grouping. A zero-degree E5 node is low (0)."""
        if (type(treated_neighbors) is not int or type(degree) is not int
                or not 0 <= treated_neighbors <= degree):
            raise ValueError("Treated-neighbor count must be between 0 and degree")
        if self.grouping == GROUP_E4:
            return treated_neighbors
        if self.grouping == GROUP_E5:
            return int(treated_neighbors > 0)
        if self.grouping in (GROUP_E1, GROUP_E3):
            if self.grouping == GROUP_E3 and degree == 0:
                raise ValueError("E3 requires a nonempty core collaborator set")
            return int(treated_neighbors > degree // 2)
        if degree == 0:
            raise ValueError("Three-level neighbor fraction is undefined for an isolate")
        if 3 * treated_neighbors < degree:
            return 0
        if 3 * treated_neighbors < 2 * degree:
            return 1
        return 2
