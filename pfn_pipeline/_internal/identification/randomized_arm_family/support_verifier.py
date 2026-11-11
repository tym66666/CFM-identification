"""Independent small-network verifier for extended-design joint support.

This is the *verifier* oracle. It recomputes the assignment mass q(t) and the
exposure state S_i(t) directly from the DECLARED design/exposure fields with
its own code, so a defect in the proposer's ``assignment_probability`` /
``statistic`` / ``classify`` cannot silently pass verification:

- unequal fixed quota: recompute q(A)=prod w_i / sum_{|B|=m} prod w_j from the
  raw ``unit_weights`` (not the precomputed law); a declared-list law is read
  as the declared data itself.
- rerandomized balance: recompute the conditioning normalizer
  sum_{A': B(A')} base_q(A') from the declared ``balance_rule``.
- weighted exposure: recompute the weighted sum / proportion from the raw
  ``weights``; grouped exposure: recompute per-group treated counts directly
  from ``groups``; E1-E5: verifier-owned ``classify``.

It never calls ``SupportEngine``. Base D1-D6 assignment laws fall back to the
declared full law only as a test cross-check; their production independence is
provided by the dedicated combinatorial verifiers in ``randomized_network_arm``.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations, product
from collections.abc import Mapping
from math import comb

from .assignment import AssignmentSpec
from .assignment_extensions import (
    UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign, CovariateBalanceRule)
from .exposure import ExposureSpec
from .exposure_extensions import GroupedExposureSpec, WeightedExposureSpec
from ..schemas import (
    HeterogeneousBernoulliDesignV1, CompleteRandomizationDesignV1,
    TwoGroupFixedQuotaDesignV1)


def _network_parts(network):
    nodes = tuple(network.node_ids)
    edges = list(network.undirected_edges)
    if not nodes or len(set(nodes)) != len(nodes):
        raise ValueError("network node_ids must be nonempty and unique")
    return nodes, edges


def _neighbors(nodes, edges):
    out = {n: set() for n in nodes}
    index = set(nodes)
    for edge in edges:
        left, right = edge
        if left not in index or right not in index:
            raise ValueError("edge endpoint is absent from node_ids")
        out[left].add(right)
        out[right].add(left)
    return {n: frozenset(v) for n, v in out.items()}


def _independent_classify(grouping, count, degree):
    """Verifier-owned count -> exposure state map (does not call ExposureSpec)."""
    if grouping == "exact_treated_neighbor_count":
        return count
    if grouping == "any_treated_neighbor":
        return int(count > 0)
    if grouping in ("strict_majority_ties_low", "pretreatment_core_collaborator_majority"):
        return int(count > degree // 2)
    if grouping == "three_level_treated_neighbor_fraction":
        if degree == 0:
            raise ValueError("Three-level neighbor fraction is undefined for an isolate")
        if 3 * count < degree:
            return 0
        if 3 * count < 2 * degree:
            return 1
        return 2
    raise ValueError(f"unsupported exposure grouping {grouping!r}")


def _independent_unequal_mass(design, treated, nodes):
    """Recompute q(A) from the declared unequal-fixed-quota fields."""
    if len(treated) != design.m:
        return Fraction(0)
    if design.unit_weights is not None:
        weights = {n: Fraction(design.unit_weights[n]) for n in nodes}
        normalizer = Fraction(0)
        for combo in combinations(nodes, design.m):
            term = Fraction(1)
            for node in combo:
                term *= weights[node]
            normalizer += term
        if normalizer == 0:
            return Fraction(0)
        numerator = Fraction(1)
        for node in treated:
            numerator *= weights[node]
        return numerator / normalizer
    # Declared-list law: the declared probabilities ARE the rule.
    return design.assignment_probabilities.get(treated, Fraction(0))


def _independent_balance_ok(rule, treated, nodes):
    """Recompute the absolute-mean-difference balance event from the raw values.

    Does not call ``rule(treated)``: a defect in the proposer's balance formula
    cannot pass verification. Each covariate must cover exactly the network
    nodes; extra or missing nodes are rejected, not silently ignored.
    """
    treated = set(treated)
    untreated = set(nodes) - treated
    if not treated or not untreated:
        return False
    for values in rule.covariates.values():
        if set(values) != set(nodes):
            raise ValueError("balance covariate does not cover exactly the network nodes")
        tm = sum((Fraction(values[n]) for n in treated), Fraction(0)) / len(treated)
        um = sum((Fraction(values[n]) for n in untreated), Fraction(0)) / len(untreated)
        if abs(tm - um) > rule.tolerance:
            return False
    return True


def _independent_rerandomized_mass(design, treated, nodes):
    """Recompute q_B(A)=q(A)1{B(A)}/P_q(B) from the declared base and balance rule."""
    base = design.base_design
    if len(treated) != base.m:
        return Fraction(0)
    rule = design.balance_rule

    def balanced(combo):
        if isinstance(rule, CovariateBalanceRule):
            return _independent_balance_ok(rule, combo, nodes)
        return bool(rule(combo))  # arbitrary callable: cannot recompute

    if not balanced(treated):
        return Fraction(0)
    normalizer = Fraction(0)
    for combo in combinations(nodes, base.m):
        combo_set = frozenset(combo)
        if balanced(combo_set):
            normalizer += _independent_unequal_mass(base, combo_set, nodes)
    if normalizer == 0:
        return Fraction(0)
    return _independent_unequal_mass(base, treated, nodes) / normalizer


def _assignment_mass(design, treatment, nodes, network):
    """q(t) recomputed from declared fields; independent for task-1 and D1-D3."""
    inner = design.design if isinstance(design, AssignmentSpec) else design
    if isinstance(inner, (UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign)):
        treated = frozenset(n for n in nodes if treatment[n])
        if isinstance(inner, UnequalProbabilityFixedQuotaDesign):
            return _independent_unequal_mass(inner, treated, nodes)
        return _independent_rerandomized_mass(inner, treated, nodes)
    if isinstance(inner, Mapping):
        return Fraction(inner.get(frozenset(n for n in nodes if treatment[n]), Fraction(0)))
    # Base D1-D3: recompute the declared law from its primitive fields, never by
    # calling the proposer's assignment_probability. D4-D6 fall back to the
    # declared full law (test cross-check only, see the module note).
    if isinstance(inner, HeterogeneousBernoulliDesignV1):
        if set(inner.propensities) != set(nodes):
            raise ValueError("Bernoulli design must declare one propensity per fixed node")
        mass = Fraction(1)
        for node in nodes:
            p = Fraction(inner.propensities[node])
            mass *= p if treatment[node] else (1 - p)
        return mass
    if isinstance(inner, CompleteRandomizationDesignV1):
        if sum(treatment[n] for n in nodes) != inner.m:
            return Fraction(0)
        return Fraction(1, comb(len(nodes), inner.m))
    if isinstance(inner, TwoGroupFixedQuotaDesignV1):
        g0, g1 = inner.groups
        flat = tuple(g0) + tuple(g1)
        if len(flat) != len(nodes) or set(flat) != set(nodes):
            raise ValueError("Two-group design must partition the fixed network")
        m0, m1 = inner.treated_quotas
        c0 = sum(1 for n in g0 if treatment[n])
        c1 = sum(1 for n in g1 if treatment[n])
        if c0 != m0 or c1 != m1:
            return Fraction(0)
        return Fraction(1, comb(len(g0), m0) * comb(len(g1), m1))
    # Base D4-D6: mirror the declared full law (test cross-check only).
    if isinstance(design, AssignmentSpec):
        return design.full_assignment_probability(network, treatment)
    if hasattr(design, "full_assignment_probability"):
        return design.full_assignment_probability(network, treatment)
    if hasattr(design, "assignment_probability"):
        return design.assignment_probability(treatment)
    raise TypeError("design must expose complete assignment probabilities")


def _exposure_state(exposure, treatment, node_id, nbrs):
    """S_i(t) recomputed from the declared exposure fields (own code)."""
    if isinstance(exposure, GroupedExposureSpec):
        return tuple(
            sum(1 for j in nbrs if treatment[j] and j in exposure.groups[label])
            for label in sorted(exposure.groups))
    if isinstance(exposure, WeightedExposureSpec):
        def weight(j):
            raw = exposure.weights.get(node_id, Fraction(0))
            if isinstance(raw, Mapping):
                return Fraction(raw.get(j, Fraction(0)))
            candidate = exposure.weights.get(j, Fraction(0))
            return Fraction(candidate) if not isinstance(candidate, Mapping) else Fraction(0)
        weighted = sum((weight(j) * int(treatment[j]) for j in nbrs), Fraction(0))
        if exposure.mode == "sum":
            return weighted
        denominator = sum((weight(j) for j in nbrs), Fraction(0))
        if denominator == 0:
            raise ValueError(f"weighted proportion undefined for node {node_id!r}")
        return weighted / denominator
    if isinstance(exposure, ExposureSpec):
        if exposure.grouping == "pretreatment_core_collaborator_majority":
            refs = set(exposure.core_collaborators[node_id])
        else:
            refs = set(nbrs)
        return _independent_classify(exposure.grouping,
                                     sum(treatment[j] for j in refs), len(refs))
    raise TypeError("unsupported exposure specification")


def verify_joint_support(*, network, design, exposure, node_id, proposed):
    nodes, edges = _network_parts(network)
    if len(nodes) > 8:
        raise ValueError("independent verification is limited to N<=8")
    if node_id not in nodes:
        raise ValueError(f"unknown node {node_id!r}")
    nbrs = _neighbors(nodes, edges)[node_id]
    oracle = {}
    total = Fraction(0)
    for bits in product((0, 1), repeat=len(nodes)):
        treatment = dict(zip(nodes, bits))
        p = _assignment_mass(design, treatment, nodes, network)
        p = p if isinstance(p, Fraction) else Fraction(str(p))
        total += p
        state = _exposure_state(exposure, treatment, node_id, nbrs)
        key = (treatment[node_id], state)
        oracle[key] = oracle.get(key, Fraction(0)) + p
    keys = set(proposed) | set(oracle)
    mismatch = {k: (proposed.get(k, Fraction(0)), oracle.get(k, Fraction(0)))
                for k in keys
                if proposed.get(k, Fraction(0)) != oracle.get(k, Fraction(0))}
    return {"ok": total == 1 and not mismatch,
            "normalization": total,
            "oracle": oracle,
            "proposed": dict(proposed),
            "mismatch": mismatch}
