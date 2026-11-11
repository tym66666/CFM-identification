"""Exact compositional support: assignment count law + exposure grouping.

This is the *proposer* computation. The independent certificate verifier in
randomized_network_arm.py deliberately retains its own direct counting
formula, rather than calling this module or reusing its probability mass.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from ..schemas import NetworkExposureSpec
from .assignment import AssignmentSpec, NeighborCountLaw, neighbor_set
from .exposure import ExposureSpec
from .assignment_extensions import MAX_EXACT_ENUMERATION_N
from .exposure_extensions import GroupedExposureSpec, WeightedExposureSpec


@dataclass(frozen=True)
class ArmSupportEvidence:
    """Internal diagnostic object; does not replace versioned proof certificates."""
    own_probability: Fraction
    exposure_given_own_probability: Fraction
    joint_probability: Fraction


class SupportEngine:
    """Compute query-specific P(T_i=a,S_i=s|W) without enumerating 2**N."""

    @staticmethod
    def from_count_law(
        law: NeighborCountLaw, exposure: ExposureSpec, exposure_value: int,
    ) -> ArmSupportEvidence:
        if type(exposure_value) is not int or exposure_value not in exposure.states_for_degree(law.degree):
            raise ValueError("exposure_value is not in the declared grouping states")
        if not law.own_probability:
            return ArmSupportEvidence(Fraction(0), Fraction(0), Fraction(0))
        # The original D2/D3 implementations reject E2 isolates here, after
        # detecting a structurally impossible own-treatment arm.
        if exposure.grouping == "three_level_treated_neighbor_fraction" and law.degree == 0:
            raise ValueError("Three-level neighbor fraction is undefined for an isolate")
        conditional = sum(
            (mass for count, mass in enumerate(law.conditional_count_mass)
             if exposure.classify(count, law.degree) == exposure_value),
            Fraction(0),
        )
        return ArmSupportEvidence(law.own_probability, conditional, law.own_probability * conditional)

    @classmethod
    def evaluate(
        cls,
        *,
        network: NetworkExposureSpec,
        assignment: AssignmentSpec,
        exposure: ExposureSpec,
        node_id: str,
        own_treatment_value: int,
        exposure_value: int,
    ) -> ArmSupportEvidence:
        reference = exposure.reference_nodes(network, node_id)
        law = assignment.conditional_neighbor_count_law(
            network, node_id, own_treatment_value, reference_nodes=reference,
        )
        return cls.from_count_law(law, exposure, exposure_value)

    @staticmethod
    def conditional_exposure(*, joint_support, own_treatment_value):
        """P(S_i=s | T_i=a) from a full joint support table."""
        denominator = sum((p for (a, _), p in joint_support.items()
                           if a == own_treatment_value), Fraction(0))
        if denominator == 0:
            return {}
        return {state: p / denominator
                for (a, state), p in joint_support.items()
                if a == own_treatment_value and p}

    @classmethod
    def joint_support(cls, *, network, assignment, exposure, node_id):
        """Unified exact joint support table P(T_i=a, S_i=s).

        Uses the analytic neighbor-count law for typed D1-D6 designs with the
        E1-E5 groupings; otherwise falls back to exact 2**N enumeration for the
        task-1 unequal/rerandomized designs and weighted/grouped exposures.
        """
        if isinstance(exposure, ExposureSpec) and assignment.has_analytic_count_law:
            return cls._joint_support_analytic(network, assignment, exposure, node_id)
        return cls._joint_support_enumeration(network, assignment, exposure, node_id)

    @classmethod
    def _joint_support_analytic(cls, network, assignment, exposure, node_id):
        reference = exposure.reference_nodes(network, node_id)
        table: dict = {}
        for a in (0, 1):
            law = assignment.conditional_neighbor_count_law(
                network, node_id, a, reference_nodes=reference)
            if not law.own_probability:
                continue
            for count, mass in enumerate(law.conditional_count_mass):
                if not mass:
                    continue
                state = exposure.classify(count, law.degree)
                key = (a, state)
                table[key] = table.get(key, Fraction(0)) + law.own_probability * mass
        return table

    @classmethod
    def _joint_support_enumeration(cls, network, assignment, exposure, node_id):
        nodes = tuple(network.node_ids)
        if len(nodes) > MAX_EXACT_ENUMERATION_N:
            raise ValueError(
                f"exact enumeration is limited to N<={MAX_EXACT_ENUMERATION_N} "
                "for task-1 designs/exposures")
        if node_id not in nodes:
            raise ValueError("queried node must be in the network")
        neighbors = neighbor_set(network, node_id)
        table: dict = {}
        for bits in product((0, 1), repeat=len(nodes)):
            treatment = dict(zip(nodes, bits))
            mass = assignment.full_assignment_probability(network, treatment)
            if not mass:
                continue
            state = cls._enumerated_exposure_state(exposure, treatment, node_id, neighbors, network)
            key = (treatment[node_id], state)
            table[key] = table.get(key, Fraction(0)) + mass
        total = sum(table.values(), Fraction(0))
        if total != 1:
            raise ValueError(f"assignment law must sum to 1 (got {total})")
        return dict(sorted(table.items(), key=lambda kv: (kv[0][0], repr(kv[0][1]))))

    @staticmethod
    def _enumerated_exposure_state(exposure, treatment, node_id, neighbors, network):
        if isinstance(exposure, (WeightedExposureSpec, GroupedExposureSpec)):
            return exposure.statistic(treatment, node_id, neighbors)
        if isinstance(exposure, ExposureSpec):
            reference = exposure.reference_nodes(network, node_id)
            refs = set(reference) if reference is not None else set(neighbors)
            return exposure.classify(sum(treatment[j] for j in refs), len(refs))
        raise TypeError("unsupported exposure specification")
