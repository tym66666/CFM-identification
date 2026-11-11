"""Internal, non-serialized components of the randomized-network POINT family.

The *public* wire contracts remain TaskSpec / IdentificationSpec and
RandomizedNetworkArmMeanContractV1. This package does not change them or issue
causal certificates by itself; the theorem backend and independent verifier
remain authoritative.
"""
from .assignment import AssignmentSpec, NeighborCountLaw
from .exposure import ExposureSpec
from .support import ArmSupportEvidence, SupportEngine
from .assignment_extensions import (
    CovariateBalanceRule, RerandomizedBalancedDesign, UnequalProbabilityFixedQuotaDesign,
)
from .exposure_extensions import GroupedExposureSpec, WeightedExposureSpec

__all__ = [
    "AssignmentSpec", "NeighborCountLaw", "ExposureSpec", "ArmSupportEvidence", "SupportEngine",
    "UnequalProbabilityFixedQuotaDesign", "RerandomizedBalancedDesign", "CovariateBalanceRule",
    "WeightedExposureSpec", "GroupedExposureSpec",
]
