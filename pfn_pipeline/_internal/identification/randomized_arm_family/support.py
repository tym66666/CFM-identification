"""Exact compositional support: assignment count law + exposure grouping.

This is the *proposer* computation. The independent certificate verifier in
randomized_network_arm.py deliberately retains its own direct counting
formula, rather than calling this module or reusing its probability mass.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..schemas import NetworkExposureSpec
from .assignment import AssignmentSpec, NeighborCountLaw
from .exposure import ExposureSpec


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
