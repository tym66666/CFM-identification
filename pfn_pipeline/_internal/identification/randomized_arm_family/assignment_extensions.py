"""Task 1 assignment extensions: unequal fixed quota and rerandomization.

All inputs are pre-treatment.  Nothing is inferred from treatment or outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from collections.abc import Mapping, Callable

MAX_EXACT_ENUMERATION_N = 8


def _as_fraction(value):
    return value if isinstance(value, Fraction) else Fraction(str(value))


def _canonical_treated(nodes, assignment):
    """Normalize a treated set / 0-1 vector / bit string / mapping to a frozenset."""
    if isinstance(assignment, (str, bytes)):
        bits = assignment.decode() if isinstance(assignment, bytes) else assignment
        if len(bits) != len(nodes) or any(c not in "01" for c in bits):
            raise ValueError("assignment bit string must have one 0/1 per node")
        return frozenset(n for n, bit in zip(nodes, bits) if bit == "1")
    if isinstance(assignment, Mapping):
        if set(assignment) != set(nodes):
            raise ValueError("assignment mapping must contain exactly all nodes")
        if any(type(v) is not int or v not in (0, 1) for v in assignment.values()):
            raise ValueError("assignment values must be binary integers")
        return frozenset(n for n in nodes if assignment[n])
    values = tuple(assignment)
    if len(values) == len(nodes) and all(type(v) is int and v in (0, 1) for v in values):
        return frozenset(n for n, bit in zip(nodes, values) if bit)
    treated = frozenset(values)
    if not treated <= set(nodes):
        raise ValueError("treated set contains an unknown node")
    return treated


@dataclass(frozen=True)
class UnequalProbabilityFixedQuotaDesign:
    """Exactly ``m`` treated nodes, with arbitrary legal-list probabilities.

    Provide either the complete-list law ``assignment_probabilities`` or
    non-negative ``unit_weights``; with weights the law is

        q(A) = prod(i in A, w_i) / sum(|B|=m) prod(j in B, w_j).
    """
    nodes: tuple[str, ...]
    m: int
    assignment_probabilities: Mapping | None = None
    unit_weights: Mapping | None = None

    def __post_init__(self):
        nodes = tuple(self.nodes)
        if len(set(nodes)) != len(nodes) or any(not isinstance(n, str) or not n for n in nodes):
            raise ValueError("nodes must be a non-empty sequence of unique strings")
        if not isinstance(self.m, int) or not 0 <= self.m <= len(nodes):
            raise ValueError("m must satisfy 0 <= m <= number of nodes")
        if (self.assignment_probabilities is None) == (self.unit_weights is None):
            raise ValueError("provide exactly one of assignment_probabilities or unit_weights")

        canonical = {}
        if self.unit_weights is not None:
            if len(nodes) > MAX_EXACT_ENUMERATION_N:
                raise ValueError(
                    "unit-weight full-list materialization is limited to N<=8")
            if set(self.unit_weights) != set(nodes):
                raise ValueError("unit_weights must cover precisely all nodes")
            weights = {n: _as_fraction(w) for n, w in self.unit_weights.items()}
            if any(w < 0 for w in weights.values()):
                raise ValueError("unit weights must be non-negative")
            normalizer = Fraction(0)
            for combo in combinations(nodes, self.m):
                mass = Fraction(1)
                for node in combo:
                    mass *= weights[node]
                normalizer += mass
            if normalizer <= 0:
                raise ValueError("unit weights give zero probability to every quota assignment")
            for combo in combinations(nodes, self.m):
                mass = Fraction(1)
                for node in combo:
                    mass *= weights[node]
                canonical[frozenset(combo)] = mass / normalizer
        else:
            for key, raw in self.assignment_probabilities.items():
                treated = _canonical_treated(nodes, key)
                if len(treated) != self.m:
                    raise ValueError("every assignment must contain exactly m treated nodes")
                p = _as_fraction(raw)
                if p < 0:
                    raise ValueError("assignment probabilities must be non-negative")
                if treated in canonical:
                    raise ValueError("duplicate assignment keys after canonicalization")
                canonical[treated] = p

        if sum(canonical.values(), Fraction(0)) != 1:
            raise ValueError("assignment probabilities must sum exactly to 1")

        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "assignment_probabilities", canonical)
        if self.unit_weights is not None:
            object.__setattr__(self, "unit_weights",
                               {n: _as_fraction(w) for n, w in self.unit_weights.items()})

    def enumerate_assignments(self):
        if len(self.nodes) > MAX_EXACT_ENUMERATION_N:
            raise ValueError(
                f"complete assignment enumeration is limited to N<={MAX_EXACT_ENUMERATION_N}")
        return tuple(frozenset(c) for c in combinations(self.nodes, self.m))

    def assignment_probability(self, assignment):
        treated = _canonical_treated(self.nodes, assignment)
        if len(treated) != self.m:
            return Fraction(0)
        return self.assignment_probabilities.get(treated, Fraction(0))

    full_assignment_probability = assignment_probability

    def probability_table(self):
        return {a: self.assignment_probability(a) for a in self.enumerate_assignments()}

    assignment_probability_table = probability_table

    def validate(self):
        if sum(self.probability_table().values(), Fraction(0)) != 1:
            raise ValueError("assignment law is not normalized")


@dataclass(frozen=True)
class CovariateBalanceRule:
    """Pre-treatment balance rule: each covariate's treated-vs-untreated mean
    difference is at most ``tolerance`` in absolute value."""
    covariates: Mapping
    tolerance: object
    metric: str = "absolute_mean_difference"

    def __post_init__(self):
        if self.metric != "absolute_mean_difference":
            raise ValueError("only absolute_mean_difference balance is supported")
        if not self.covariates:
            raise ValueError("at least one pre-treatment covariate is required")
        tol = _as_fraction(self.tolerance)
        if tol < 0:
            raise ValueError("balance tolerance must be non-negative")
        normalized = {}
        for name, values in self.covariates.items():
            if not str(name).strip() or not values:
                raise ValueError("balance covariates must have nonempty names and values")
            normalized[str(name)] = {str(n): _as_fraction(v) for n, v in values.items()}
        node_sets = {frozenset(values) for values in normalized.values()}
        if len(node_sets) != 1:
            raise ValueError("every balance covariate must cover precisely the same node set")
        object.__setattr__(self, "covariates", normalized)
        object.__setattr__(self, "tolerance", tol)

    def __call__(self, treated):
        nodes = set(next(iter(self.covariates.values())))
        if not treated <= nodes or not treated or treated == nodes:
            return False
        untreated = nodes - set(treated)
        for values in self.covariates.values():
            if set(values) != nodes:
                raise ValueError("every balance covariate must cover precisely all nodes")
            tm = sum((values[n] for n in treated), Fraction(0)) / len(treated)
            um = sum((values[n] for n in untreated), Fraction(0)) / len(untreated)
            if abs(tm - um) > self.tolerance:
                return False
        return True

    @property
    def description(self):
        return f"absolute pre-treatment covariate mean differences <= {self.tolerance}"


@dataclass(frozen=True)
class RerandomizedBalancedDesign:
    """Fixed-quota law conditioned on a pre-treatment balance event B(A)."""
    base_design: UnequalProbabilityFixedQuotaDesign
    balance_rule: Callable
    balance_description: str = "pre-treatment balance rule"

    def __post_init__(self):
        if not callable(self.balance_rule):
            raise TypeError("balance_rule must be callable")
        if isinstance(self.balance_rule, CovariateBalanceRule):
            rule_nodes = set(next(iter(self.balance_rule.covariates.values())))
            base_nodes = set(self.base_design.nodes)
            if rule_nodes != base_nodes:
                raise ValueError(
                    "balance covariates must match the study nodes exactly; "
                    f"extra={sorted(rule_nodes - base_nodes)!r}, "
                    f"missing={sorted(base_nodes - rule_nodes)!r}")
        accepted = [a for a in self.base_design.enumerate_assignments()
                    if self.is_balanced(a)]
        normalizer = sum((self.base_design.assignment_probability(a)
                          for a in accepted), Fraction(0))
        if normalizer <= 0:
            raise ValueError("balance event has zero probability under the base design")
        object.__setattr__(self, "_balanced_assignments", tuple(accepted))
        object.__setattr__(self, "_balance_probability", normalizer)

    def is_balanced(self, assignment):
        treated = _canonical_treated(self.base_design.nodes, assignment)
        return bool(self.balance_rule(treated))

    def enumerate_assignments(self):
        return self.base_design.enumerate_assignments()

    @property
    def balance_probability(self):
        return self._balance_probability

    def assignment_probability(self, assignment):
        treated = _canonical_treated(self.base_design.nodes, assignment)
        if len(treated) != self.base_design.m or not self.is_balanced(treated):
            return Fraction(0)
        return self.base_design.assignment_probability(treated) / self.balance_probability

    full_assignment_probability = assignment_probability

    def probability_table(self):
        return {a: self.assignment_probability(a) for a in self.enumerate_assignments()}

    assignment_probability_table = probability_table

    def validate(self):
        if sum(self.probability_table().values(), Fraction(0)) != 1:
            raise ValueError("rerandomized assignment law is not normalized")
