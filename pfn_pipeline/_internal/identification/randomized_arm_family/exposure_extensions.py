"""Task 1 exposure extensions: fixed weights and grouped coordinates.

Weights and groups are pre-treatment inputs; never inferred from treatment
or outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from collections.abc import Mapping
from typing import Literal


def _fraction(value):
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("boolean is not a numeric weight")
    try:
        return Fraction(str(value))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise TypeError(f"value {value!r} cannot be represented exactly") from exc


@dataclass(frozen=True)
class WeightedExposureSpec:
    """Fixed nonnegative neighbor weights and an exact exposure statistic.

    mode='sum' returns sum_j w_ij T_j.
    mode='proportion' returns sum_j w_ij T_j / sum_j w_ij.
    """
    weights: Mapping
    mode: Literal["sum", "proportion"] = "sum"

    def __post_init__(self):
        if self.mode not in ("sum", "proportion"):
            raise ValueError("mode must be 'sum' or 'proportion'")
        normalized = {}
        for node, raw in self.weights.items():
            if isinstance(raw, Mapping):
                normalized[str(node)] = {str(n): _fraction(v) for n, v in raw.items()}
                if any(v < 0 for v in normalized[str(node)].values()):
                    raise ValueError("weights must be nonnegative")
            else:
                value = _fraction(raw)
                if value < 0:
                    raise ValueError("weights must be nonnegative")
                normalized[str(node)] = value
        object.__setattr__(self, "weights", normalized)

    def _weight(self, node, neighbour):
        raw = self.weights.get(node, Fraction(0))
        if isinstance(raw, Mapping):
            return _fraction(raw.get(neighbour, Fraction(0)))
        candidate = self.weights.get(neighbour, Fraction(0))
        return _fraction(candidate) if not isinstance(candidate, Mapping) else Fraction(0)

    def statistic(self, assignment, node_id, neighbours):
        treated = assignment if isinstance(assignment, Mapping) else set(assignment)
        nbrs = tuple(neighbours)
        weighted_sum = sum((self._weight(node_id, j) * int(treated.get(j, j in treated))
                            for j in nbrs), Fraction(0))
        if self.mode == "sum":
            return weighted_sum
        denominator = sum((self._weight(node_id, j) for j in nbrs), Fraction(0))
        if denominator == 0:
            raise ValueError(
                f"weighted proportion undefined for zero-weight node {node_id!r}")
        return weighted_sum / denominator

    def values(self, assignment, node_id, neighbours):
        return self.statistic(assignment, node_id, neighbours)


@dataclass(frozen=True)
class GroupedExposureSpec:
    """Pre-treatment group coordinates of treated-neighbor counts.

    Returns a tuple (count_group_1, ..., count_group_K) in stable label order.
    """
    groups: Mapping

    def __post_init__(self):
        if not self.groups:
            raise ValueError("at least one exposure group is required")
        normalized = {}
        seen = set()
        for label, members in self.groups.items():
            if not str(label):
                raise ValueError("group labels must be nonempty")
            member_set = frozenset(str(m) for m in members)
            if seen.intersection(member_set):
                raise ValueError("group members must be disjoint")
            seen.update(member_set)
            normalized[str(label)] = member_set
        object.__setattr__(self, "groups", normalized)

    @property
    def labels(self):
        return tuple(sorted(self.groups))

    def statistic(self, assignment, node_id, neighbours):
        treated = assignment if isinstance(assignment, Mapping) else set(assignment)
        nbrs = set(neighbours)
        return tuple(sum(int(treated.get(j, j in treated))
                         for j in nbrs.intersection(self.groups[label]))
                     for label in self.labels)

    def values(self, assignment, node_id, neighbours):
        return self.statistic(assignment, node_id, neighbours)
