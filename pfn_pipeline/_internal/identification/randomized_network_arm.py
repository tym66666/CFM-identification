"""Production POINT identification for one design-standardized randomized-network arm.

One shared theorem backend for (D1) heterogeneous independent Bernoulli,
(D2) complete randomization, and (D3) two-group fixed-quota randomization,
with E1 strict-majority, E2 three-level neighbor-fraction, or E3
pre-treatment core-collaborator majority grouping.
The target is always standardized under the ORIGINAL full-vector design law.
No exposure-sufficiency assumption or PFN adapter for D1/D2/D3 is claimed.

The proposer uses a Poisson-binomial DP for D1 or conditional hypergeometric
laws for D2/D3. The verifier independently replays exact design support using
balanced polynomial multiplication (D1) or combinatorial counts (D2/D3).
Neither path enumerates all full assignments on a large network.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal
from math import comb
from collections.abc import Mapping
import hashlib
import json

REQUIRED = (
    "known_assignment_law",
    "full_vector_randomization",
    "consistency",
    "fixed_pretreatment_network",
    "finite_conditional_first_moments",
)

def _hash(payload) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def spec_fingerprint(spec) -> str:
    return _hash(spec.model_dump(mode="json", warnings="error"))
from .randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine, NeighborCountLaw
from .randomized_arm_family.assignment import (
    complete_conditional_count_distribution,
    neighbor_set, group_neighbor_counts, group_conditional_count_distribution,
    as_design_dataclass,
)
from .randomized_arm_family.exposure import GROUP_E1, GROUP_E2, GROUP_E3, GROUP_E4, GROUP_E5
from .randomized_arm_family.cluster_verifier import verify_cluster_joint_support
from .randomized_arm_family.two_stage_verifier import independent_joint_support as _verify_d6_joint_support
from .randomized_arm_family.two_stage_a5 import profile_exclusion_reason
from .randomized_arm_family.assignment_extensions import (
    MAX_EXACT_ENUMERATION_N, UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign,
)
from .randomized_arm_family.support_verifier import verify_joint_support as _verify_joint_support
from .randomized_arm_family.exposure_extensions import WeightedExposureSpec, GroupedExposureSpec
from .query_gate import TRUSTED_QUERY_AUTHORITIES, query_semantics_implementation_gaps
from .schemas import (
    Assumption, AssumptionStatus, CompleteRandomizationDesignV1,
    TwoGroupFixedQuotaDesignV1, MultiGroupFixedQuotaDesignV25, HeterogeneousBernoulliDesignV1, ClusterBernoulliDesignV24, TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1,
    IdentificationResult, IdentificationSpec, IdentificationStatus,
    InformationObject, InformationSignature, RandomizedArmObservableV21, InterferenceStructureReceipt,
    NetworkExposureSpec, QuerySpec, RandomizedNetworkArmMeanContractV1,
    RandomizedNetworkArmMeanProgram, StructureSpec, TraceStep, VariableDomain,
    VerificationStatus, interference_structure_semantic_fingerprint,
)


EXPOSURE_E1 = "strict_majority"
EXPOSURE_E2 = "three_level_treated_neighbor_fraction"
EXPOSURE_E3 = "pretreatment_core_collaborator_majority"
EXPOSURE_E4 = "exact_treated_neighbor_count"
EXPOSURE_E5 = "any_treated_neighbor"
PUBLIC_TO_GROUP = {EXPOSURE_E1: GROUP_E1, EXPOSURE_E2: GROUP_E2, EXPOSURE_E3: GROUP_E3,
                   EXPOSURE_E4: GROUP_E4, EXPOSURE_E5: GROUP_E5}
GROUP_TO_PUBLIC = {value: key for key, value in PUBLIC_TO_GROUP.items()}
GROUP_TO_PROGRAM = {
    GROUP_E1: "K_i>floor(degree_i/2);ties=0",
    GROUP_E2: "3K<d:low;d<=3K<2d:medium;3K>=2d:high;d>0",
    GROUP_E3: "K_i(C_i)>floor(|C_i|/2);ties=0;C_i fixed pretreatment",
    GROUP_E4: "S_i=K_i;exact treated one-hop neighbor count",
    GROUP_E5: "S_i=1{K_i>0};any treated one-hop neighbor",
}
GROUP_TO_REFERENCE = {
    GROUP_E1: "treated_neighbor_count_1hop",
    GROUP_E2: "treated_neighbor_fraction_three_level",
    GROUP_E3: "treated_core_collaborator_count_1hop",
    GROUP_E4: "treated_neighbor_count_1hop_exact",
    GROUP_E5: "any_treated_neighbor_1hop",
}
GROUP_TO_VARIABLE = {
    GROUP_E1: "majority_exposure",
    GROUP_E2: "three_level_exposure",
    GROUP_E3: "core_majority_exposure",
    GROUP_E4: "exact_count_exposure",
    GROUP_E5: "any_neighbor_exposure",
}

EXPOSURE_WEIGHTED_SUM = "weighted_exposure_sum"
EXPOSURE_WEIGHTED_PROPORTION = "weighted_exposure_proportion"
EXPOSURE_GROUPED = "grouped_exposure"
W_G_GROUPINGS = (EXPOSURE_WEIGHTED_SUM, EXPOSURE_WEIGHTED_PROPORTION, EXPOSURE_GROUPED)
W_G_TO_PROGRAM = {
    EXPOSURE_WEIGHTED_SUM: "S_i=sum_j w_ij T_j;fixed weighted sum",
    EXPOSURE_WEIGHTED_PROPORTION: "S_i=sum_j w_ij T_j/sum_j w_ij;fixed weighted proportion",
    EXPOSURE_GROUPED: "S_i=(K_i(G_1),...,K_i(G_K));fixed grouped counts",
}


def exposure_object(contract):
    """Build the internal exposure object implied by the contract's grouping."""
    if contract.grouping == EXPOSURE_WEIGHTED_SUM:
        return WeightedExposureSpec(weights=dict(contract.exposure_weights), mode="sum")
    if contract.grouping == EXPOSURE_WEIGHTED_PROPORTION:
        return WeightedExposureSpec(weights=dict(contract.exposure_weights), mode="proportion")
    if contract.grouping == EXPOSURE_GROUPED:
        return GroupedExposureSpec(groups={k: list(v) for k, v in contract.exposure_groups.items()})
    return ExposureSpec(contract.grouping, contract.core_collaborators)


def queried_exposure_state(exposure, raw):
    """Parse the serialized queried exposure state to its exact hashable value."""
    if isinstance(exposure, WeightedExposureSpec):
        return Fraction(raw)
    if isinstance(exposure, GroupedExposureSpec):
        import json
        value = json.loads(raw) if isinstance(raw, str) else raw
        return tuple(int(s) for s in value)
    return raw


def exposure_state_str(exposure, state):
    """Canonical serialized form of an exposure state for the wire query/program."""
    if isinstance(exposure, WeightedExposureSpec):
        return str(Fraction(state))
    if isinstance(exposure, GroupedExposureSpec):
        import json
        return json.dumps(list(state))
    return int(state)


GROUP_TO_VARIABLE.update({
    EXPOSURE_WEIGHTED_SUM: "weighted_exposure",
    EXPOSURE_WEIGHTED_PROPORTION: "weighted_exposure",
    EXPOSURE_GROUPED: "grouped_exposure",
})
GROUP_TO_REFERENCE.update({
    EXPOSURE_WEIGHTED_SUM: EXPOSURE_WEIGHTED_SUM,
    EXPOSURE_WEIGHTED_PROPORTION: EXPOSURE_WEIGHTED_PROPORTION,
    EXPOSURE_GROUPED: EXPOSURE_GROUPED,
})


def _canonical_core_collaborators(
    network: NetworkExposureSpec, grouping: str,
    core_collaborators: Mapping[str, object] | None,
) -> dict[str, tuple[str, ...]] | None:
    """Validate E3's entire pre-treatment map and canonically order each C_i.

    C_i is never inferred or fitted.  In this first E3 family all network nodes
    must have a nonempty, declared C_i subset of their *actual* neighbors.
    """
    if grouping != GROUP_E3:
        if core_collaborators is not None:
            raise ValueError("core_collaborators can only be supplied for E3")
        return None
    if not isinstance(core_collaborators, Mapping):
        raise ValueError("E3 requires a pre-treatment core collaborator map")
    ids = network.node_ids
    if set(core_collaborators) != set(ids):
        raise ValueError("E3 requires precisely one nonempty C_i for every network node")
    index = {node: i for i, node in enumerate(ids)}
    neighbors = {node: set() for node in ids}
    for left, right in network.undirected_edges:
        neighbors[left].add(right)
        neighbors[right].add(left)
    canonical = {}
    for node in ids:
        members = core_collaborators[node]
        if (not isinstance(members, (tuple, list)) or not members
            or any(not isinstance(member, str) for member in members)
            or len(members) != len(set(members))):
            raise ValueError("E3 requires a nonempty C_i with distinct string IDs")
        if not set(members) <= neighbors[node]:
            raise ValueError("E3 C_i must be a subset of pretreatment network neighbors")
        canonical[node] = tuple(sorted(members, key=index.__getitem__))
    return canonical


def _grouped_exposure(count: int, degree: int, grouping: str) -> int:
    """Compatibility wrapper; exposure semantics live in ExposureSpec."""
    return ExposureSpec(grouping).classify(count, degree)


def _verifier_matches_exposure(count: int, degree: int, s: int, grouping: str) -> bool:
    """Independent bin definition for verifier, not a call to the proposer."""
    if grouping == GROUP_E1:
        return (count <= degree // 2 and s == 0) or (count > degree // 2 and s == 1)
    if grouping == GROUP_E2:
        return degree > 0 and (
            (s == 0 and 3*count < degree)
            or (s == 1 and degree <= 3*count < 2*degree)
            or (s == 2 and 3*count >= 2*degree)
        )
    if grouping == GROUP_E3:
        return degree > 0 and (
            (s == 0 and count <= degree // 2)
            or (s == 1 and count > degree // 2)
        )
    if grouping == GROUP_E4:
        return s == count and 0 <= count <= degree
    if grouping == GROUP_E5:
        return (s == 0 and count == 0) or (s == 1 and count > 0)
    raise ValueError("Unsupported exposure grouping")

BACKEND = "randomized_network_arm_mean_v1"
RULE_ID = "RANDOMIZED_NETWORK_ARM_MEAN_COMPLETE_V1"  # existing D2 proof id
TWO_GROUP_RULE_ID = "RANDOMIZED_NETWORK_ARM_MEAN_TWO_GROUP_V1"
HETEROGENEOUS_RULE_ID = "RANDOMIZED_NETWORK_ARM_MEAN_HETEROGENEOUS_BERNOULLI_V1"
CLUSTER_RULE_ID = "RANDOMIZED_NETWORK_ARM_MEAN_CLUSTER_BERNOULLI_V24"
MULTI_GROUP_RULE_ID = "RANDOMIZED_NETWORK_ARM_MULTI_GROUP_QUOTAS_V25"
TWO_STAGE_RULE_ID = "RANDOMIZED_NETWORK_ARM_TWO_STAGE_QUOTA_MIXTURE_V27"
UNEQUAL_RULE_ID = "RANDOMIZED_NETWORK_ARM_MEAN_UNEQUAL_FIXED_QUOTA_V1"
RERANDOMIZED_RULE_ID = "RANDOMIZED_NETWORK_ARM_MEAN_RERANDOMIZED_BALANCED_V1"
D6_EXCLUSION = "first_stage_profile_no_direct_outcome_effect"
MAX_D6_CONVOLUTION_CELLS = 2_000_000
MAX_N = 4096
# D2 is linear in queried degree; D3 uses a bounded two-group count
# convolution. Both operate with exact rationals and avoid 2**N enumeration.
MAX_DEGREE = 4096
MAX_TWO_GROUP_CONVOLUTION_CELLS = 500_000
MAX_BERNOULLI_DP_CELLS = 500_000
EXPECTED_SUPPORT_DOMAIN = {
    "analysis_unit": ["node"],
    "context_symbol": "W",
    "context_semantics": "full_pretreatment_network_context",
    "target_context_distribution": "conditional_not_transport",
}


def arm_target_fingerprint(
    network: NetworkExposureSpec,
    contract: RandomizedNetworkArmMeanContractV1,
    node_id: str,
    own_treatment_value: int,
    exposure_value: int | str,
) -> str:
    """Fingerprint of q, g, queried unit and arm, not merely its support."""
    return _hash({
        "version": "randomized-network-arm-mean-target-v1",
        "network": network.model_dump(mode="json", warnings="error"),
        "theorem_contract": contract.model_dump(mode="json", warnings="error"),
        "node_id": node_id,
        "own_treatment_value": own_treatment_value,
        "exposure_value": exposure_value,
    })


def make_complete_randomization_arm_spec(
    network: NetworkExposureSpec,
    *,
    m: int,
    node_id: str,
    own_treatment_value: int,
    exposure_value: int | str,
    source: str,
    evidence: str,
    exposure_definition: Literal["strict_majority", "three_level_treated_neighbor_fraction", "pretreatment_core_collaborator_majority"] = EXPOSURE_E1,
    core_collaborators: Mapping[str, object] | None = None,
    exposure_weights: Mapping[str, object] | None = None,
    exposure_groups: Mapping[str, object] | None = None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> IdentificationSpec:
    """Legacy D2 constructor; unchanged study and theorem semantics."""
    design = CompleteRandomizationDesignV1(m=m)
    return _make_randomized_arm_spec(
        network, design=design, node_id=node_id,
        own_treatment_value=own_treatment_value, exposure_value=exposure_value,
        source=source, evidence=evidence, admitted=admitted,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,
        exposure_weights=exposure_weights, exposure_groups=exposure_groups,
        query_authority=query_authority, synthetic=synthetic,
        outcome_kind=outcome_kind,
    )


def make_two_group_quota_arm_spec(
    network: NetworkExposureSpec,
    *,
    groups: tuple[tuple[str, ...], tuple[str, ...]],
    treated_quotas: tuple[int, int],
    node_id: str,
    own_treatment_value: int,
    exposure_value: int | str,
    source: str,
    evidence: str,
    exposure_definition: Literal["strict_majority", "three_level_treated_neighbor_fraction", "pretreatment_core_collaborator_majority"] = EXPOSURE_E1,
    core_collaborators: Mapping[str, object] | None = None,
    exposure_weights: Mapping[str, object] | None = None,
    exposure_groups: Mapping[str, object] | None = None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> IdentificationSpec:
    """D3: two disjoint known pretreatment groups, independent uniform quotas.

    Group membership changes the full assignment law; it is not an exposure
    partition. Edges may cross the assignment groups. The input group ordering
    is retained for explicit provenance and target fingerprinting.
    """
    design = TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=treated_quotas)
    if (len(design.groups[0]) + len(design.groups[1]) != len(network.node_ids)
        or set(design.groups[0] + design.groups[1]) != set(network.node_ids)):
        raise ValueError("two pretreatment groups must partition the complete network node set")
    return _make_randomized_arm_spec(
        network, design=design, node_id=node_id,
        own_treatment_value=own_treatment_value, exposure_value=exposure_value,
        source=source, evidence=evidence, admitted=admitted,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,
        exposure_weights=exposure_weights, exposure_groups=exposure_groups,
        query_authority=query_authority, synthetic=synthetic,
        outcome_kind=outcome_kind,
    )


def make_heterogeneous_bernoulli_arm_spec(
    network: NetworkExposureSpec,
    *,
    propensities: dict[str, str],
    node_id: str,
    own_treatment_value: int,
    exposure_value: int | str,
    source: str,
    evidence: str,
    exposure_definition: Literal["strict_majority", "three_level_treated_neighbor_fraction", "pretreatment_core_collaborator_majority"] = EXPOSURE_E1,
    core_collaborators: Mapping[str, object] | None = None,
    exposure_weights: Mapping[str, object] | None = None,
    exposure_groups: Mapping[str, object] | None = None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> IdentificationSpec:
    """D1: explicit per-node independent Bernoulli law, no fitted propensities."""
    design = HeterogeneousBernoulliDesignV1(propensities=propensities)
    if set(design.propensities) != set(network.node_ids):
        raise ValueError("known Bernoulli propensities must cover precisely the fixed network nodes")
    return _make_randomized_arm_spec(
        network, design=design, node_id=node_id,
        own_treatment_value=own_treatment_value, exposure_value=exposure_value,
        source=source, evidence=evidence, admitted=admitted,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,
        exposure_weights=exposure_weights, exposure_groups=exposure_groups,
        query_authority=query_authority, synthetic=synthetic,
        outcome_kind=outcome_kind,
    )


def make_cluster_bernoulli_arm_spec(
    network: NetworkExposureSpec, *, clusters: tuple[tuple[str, ...], ...],
    cluster_probabilities: tuple[str, ...], node_id: str,
    own_treatment_value: int, exposure_value: int | str,
    source: str, evidence: str, exposure_definition: str = EXPOSURE_E1,
    core_collaborators: Mapping[str,object] | None = None,
    exposure_weights: Mapping[str,object] | None = None,
    exposure_groups: Mapping[str,object] | None = None,
    admitted: bool = False, query_authority: str = 'PROPOSED',
    synthetic: bool = False, outcome_kind: str = 'continuous',
) -> IdentificationSpec:
    """D4 cluster-level independent Bernoulli, entire cluster receives one draw."""
    design = ClusterBernoulliDesignV24(
        clusters=clusters, cluster_probabilities=cluster_probabilities)
    AssignmentSpec(design)._validate_network(network)
    return _make_randomized_arm_spec(network, design=design, node_id=node_id,
        own_treatment_value=own_treatment_value, exposure_value=exposure_value,
        source=source, evidence=evidence, admitted=admitted,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators, exposure_weights=exposure_weights,
        exposure_groups=exposure_groups, query_authority=query_authority,
        synthetic=synthetic, outcome_kind=outcome_kind)


def make_multi_group_quota_arm_spec(
    network: NetworkExposureSpec, *, groups: tuple[tuple[str,...],...],
    treated_quotas: tuple[int,...],node_id: str,own_treatment_value:int,
    exposure_value:int | str,source:str,evidence:str,exposure_definition:str=EXPOSURE_E1,
    core_collaborators:Mapping[str,object]|None=None,
    exposure_weights:Mapping[str,object]|None=None,exposure_groups:Mapping[str,object]|None=None,
    admitted:bool=False,
    query_authority:str='PROPOSED',synthetic:bool=False,
    outcome_kind:str='continuous',
)->IdentificationSpec:
    """D5: independent uniform fixed quotas in >=3 pretreatment strata."""
    design=MultiGroupFixedQuotaDesignV25(groups=groups,treated_quotas=treated_quotas)
    AssignmentSpec(design)._validate_network(network)
    return _make_randomized_arm_spec(network,design=design,node_id=node_id,
        own_treatment_value=own_treatment_value,exposure_value=exposure_value,
        source=source,evidence=evidence,admitted=admitted,
        exposure_definition=exposure_definition,core_collaborators=core_collaborators,
        exposure_weights=exposure_weights,exposure_groups=exposure_groups,
        query_authority=query_authority,synthetic=synthetic,outcome_kind=outcome_kind)


def make_two_stage_quota_arm_spec(
    network: NetworkExposureSpec, *, groups: tuple[tuple[str,...],...],
    quota_profiles: tuple[tuple[int,...],...], profile_probabilities: tuple[str,...],
    node_id:str, own_treatment_value:int, exposure_value:int | str, source:str,
    evidence:str, exposure_definition:str=EXPOSURE_E1, core_collaborators=None,
    exposure_weights=None, exposure_groups=None,
    admitted:bool=False, profile_exclusion_admitted:bool=False,
    query_authority:str='PROPOSED', synthetic:bool=False,
    outcome_kind:str='continuous',
)->IdentificationSpec:
    """D6: known first-stage profile lottery, uniform independent second stage.

    The exclusion of direct profile effects is separately admitted by the
    investigator; admitted=True for randomization does NOT turn it on.
    """
    design=TwoStageQuotaMixtureDesignV27(groups=groups,quota_profiles=quota_profiles,
                                         profile_probabilities=profile_probabilities)
    AssignmentSpec(design)._validate_network(network)
    spec=_make_randomized_arm_spec(network,design=design,node_id=node_id,
        own_treatment_value=own_treatment_value,exposure_value=exposure_value,
        source=source,evidence=evidence,admitted=admitted,
        exposure_definition=exposure_definition,core_collaborators=core_collaborators,
        exposure_weights=exposure_weights,exposure_groups=exposure_groups,
        query_authority=query_authority,synthetic=synthetic,outcome_kind=outcome_kind)
    extra=Assumption(name=D6_EXCLUSION,
        source='demo_specification' if synthetic else 'human_confirmation',
        status=(AssumptionStatus.CERTIFIED if synthetic else AssumptionStatus.ADMITTED)
                  if profile_exclusion_admitted else AssumptionStatus.UNRESOLVED,
        evidence=[evidence],
        details=('Scientifically accepted exclusion: given final treatment vector, '
                 'the publicly assigned stage-one quota profile has no independent '
                 'effect on outcomes; no profile-dependent versions of treatment. '
                 'Software does not verify this scientific premise. '+source))
    return spec.model_copy(update={'assumptions':spec.assumptions+[extra]})


def make_unequal_probability_fixed_quota_arm_spec(
    network: NetworkExposureSpec,
    *,
    design: UnequalProbabilityFixedQuotaDesignV1,
    node_id: str,
    own_treatment_value: int,
    exposure_value: int | str,
    source: str,
    evidence: str,
    exposure_definition: Literal["strict_majority", "three_level_treated_neighbor_fraction", "pretreatment_core_collaborator_majority"] = EXPOSURE_E1,
    core_collaborators: Mapping[str, object] | None = None,
    exposure_weights: Mapping[str, object] | None = None,
    exposure_groups: Mapping[str, object] | None = None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> IdentificationSpec:
    """Task-1 unequal fixed quota: an arbitrary declared size-m treated-set law.

    Exact support is computed by full-assignment enumeration (N<=8), so there
    is no analytic neighbor-count law. The target remains standardized under
    the ORIGINAL declared law conditioned on own treatment and exposure.
    """
    AssignmentSpec(design)._validate_network(network)
    return _make_randomized_arm_spec(
        network, design=design, node_id=node_id,
        own_treatment_value=own_treatment_value, exposure_value=exposure_value,
        source=source, evidence=evidence, admitted=admitted,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,
        exposure_weights=exposure_weights, exposure_groups=exposure_groups,
        query_authority=query_authority, synthetic=synthetic,
        outcome_kind=outcome_kind,
    )


def make_rerandomized_balanced_arm_spec(
    network: NetworkExposureSpec,
    *,
    design: RerandomizedBalancedDesignV1,
    node_id: str,
    own_treatment_value: int,
    exposure_value: int | str,
    source: str,
    evidence: str,
    exposure_definition: Literal["strict_majority", "three_level_treated_neighbor_fraction", "pretreatment_core_collaborator_majority"] = EXPOSURE_E1,
    core_collaborators: Mapping[str, object] | None = None,
    exposure_weights: Mapping[str, object] | None = None,
    exposure_groups: Mapping[str, object] | None = None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> IdentificationSpec:
    """Task-1 rerandomized balance: base fixed-quota law conditioned on balance B(A).

    Rejective sampling q_B(A)=q(A)1{B(A)}/P_q(B) (Hajek 1964); exact support
    via full-assignment enumeration (N<=8). The balance event is a
    pre-treatment absolute covariate mean-difference rule.
    """
    AssignmentSpec(design)._validate_network(network)
    return _make_randomized_arm_spec(
        network, design=design, node_id=node_id,
        own_treatment_value=own_treatment_value, exposure_value=exposure_value,
        source=source, evidence=evidence, admitted=admitted,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,
        exposure_weights=exposure_weights, exposure_groups=exposure_groups,
        query_authority=query_authority, synthetic=synthetic,
        outcome_kind=outcome_kind,
    )


def _make_randomized_arm_spec(
    network: NetworkExposureSpec,
    *,
    design: CompleteRandomizationDesignV1 | TwoGroupFixedQuotaDesignV1 | HeterogeneousBernoulliDesignV1 | ClusterBernoulliDesignV24 | MultiGroupFixedQuotaDesignV25 | TwoStageQuotaMixtureDesignV27 | UnequalProbabilityFixedQuotaDesignV1 | RerandomizedBalancedDesignV1,
    node_id: str,
    own_treatment_value: int,
    exposure_value: int | str,
    source: str,
    evidence: str,
    admitted: bool,
    exposure_definition: str,
    core_collaborators: Mapping[str, object] | None,
    exposure_weights: Mapping[str, object] | None = None,
    exposure_groups: Mapping[str, object] | None = None,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> IdentificationSpec:
    """Shared spec/assumption/query construction, never inferring assumptions.

    ``admitted=True`` records the analyst's substantive acceptance, not a
    data-derived proof. TRUSTED_FIXTURE is only valid for synthetic examples.
    """
    if not source.strip() or not evidence.strip():
        raise ValueError("Nonempty protocol source and evidence are required")
    if query_authority == "TRUSTED_FIXTURE" and not synthetic:
        raise ValueError("TRUSTED_FIXTURE is reserved for documented synthetic fixtures")
    if type(own_treatment_value) is not int or own_treatment_value not in (0, 1):
        raise ValueError("own_treatment_value must be 0 or 1")
    contract_extra = {}
    if exposure_definition in W_G_GROUPINGS:
        grouping = exposure_definition
        core = None
        if exposure_definition == EXPOSURE_GROUPED:
            if not exposure_groups:
                raise ValueError("grouped exposure requires exposure_groups")
            exposure_obj = GroupedExposureSpec(groups={k: list(v) for k, v in exposure_groups.items()})
            contract_extra = dict(exposure_groups={k: tuple(v) for k, v in exposure_groups.items()})
        else:
            if not exposure_weights:
                raise ValueError("weighted exposure requires exposure_weights")
            mode = "sum" if exposure_definition == EXPOSURE_WEIGHTED_SUM else "proportion"
            exposure_obj = WeightedExposureSpec(weights=dict(exposure_weights), mode=mode)
            contract_extra = dict(exposure_weights={k: str(v) for k, v in exposure_weights.items()})
        try:
            _state = queried_exposure_state(exposure_obj, exposure_value)
        except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
            raise ValueError("exposure_value is not a valid weighted/grouped state") from exc
        wire_state = exposure_state_str(exposure_obj, _state)
    else:
        if exposure_definition not in PUBLIC_TO_GROUP:
            raise ValueError("unsupported exposure_definition for randomized-network arm")
        grouping = PUBLIC_TO_GROUP[exposure_definition]
        core = _canonical_core_collaborators(network, grouping, core_collaborators)
        allowed_states = ExposureSpec(grouping,core).states_for_degree(
            len(core[node_id]) if core is not None and node_id in core else network.degree_map().get(node_id,0))
        if type(exposure_value) is not int or exposure_value not in allowed_states:
            raise ValueError(f"exposure_value must be in {allowed_states}")
        wire_state = exposure_value
    if node_id not in network.node_ids:
        raise ValueError("node_id must be a node in the declared network")
    if outcome_kind not in ("continuous", "binary"):
        raise ValueError("outcome_kind must be continuous or binary")
    contract = RandomizedNetworkArmMeanContractV1(
        design=design, grouping=grouping, core_collaborators=core, **contract_extra,
    )
    if isinstance(design, CompleteRandomizationDesignV1):
        design_note = "complete randomization"
        assignment_detail = (
            f"Known uniform complete randomization of exactly m={design.m} treated "
            f"units out of N={len(network.node_ids)}; conditional quotas apply when T_i is fixed."
        )
    elif isinstance(design, TwoGroupFixedQuotaDesignV1):
        design_note = "independent two-group uniform fixed quotas"
        assignment_detail = (
            "Known independent uniform treatment assignment within two disjoint "
            f"pretreatment groups, sizes=({len(design.groups[0])},{len(design.groups[1])}), "
            f"treated quotas={design.treated_quotas}; cross-group network edges allowed; "
            "conditional quotas apply when T_i is fixed."
        )
    elif isinstance(design, TwoStageQuotaMixtureDesignV27):
        design_note='two-stage pretreatment quota-profile mixture'
        assignment_detail=(
            f'Known exact first-stage lottery among {len(design.quota_profiles)} quota profiles; '
            f'given profile, independent uniform fixed quotas in {len(design.groups)} groups; '
            'marginal assignment law mixes group quotas. Direct first-stage outcome effects '
            'are separately excluded by an explicit A5 scientific admission.'
        )
    elif isinstance(design, MultiGroupFixedQuotaDesignV25):
        design_note = 'independent multi-stratum uniform fixed quotas'
        assignment_detail = (
            f'Known independent uniform fixed quotas in {len(design.groups)} '
            f'pretreatment strata with sizes={tuple(map(len,design.groups))} '
            f'and treated quotas={design.treated_quotas}; edges may cross strata; '
            'conditioning on own treatment consumes the own-stratum quota.'
        )
    elif isinstance(design, ClusterBernoulliDesignV24):
        design_note = "independent Bernoulli draws at the pretreatment cluster level"
        assignment_detail = (
            "Known fixed, disjoint cluster partition; one Bernoulli draw per cluster "
            "and all cluster members receive exactly the same treatment. "
            "Different clusters are independent conditional on W."
        )
    elif isinstance(design, UnequalProbabilityFixedQuotaDesignV1):
        design_note = "unequal-probability fixed quota"
        assignment_detail = (
            f"Known arbitrary size-m={design.m} treated-set law over N={len(network.node_ids)} nodes; "
            "q(A) equals the declared probability of each size-m treated set and 0 otherwise; "
            "conditioning on T_i=a restricts to treated sets containing/not containing node i."
        )
    elif isinstance(design, RerandomizedBalancedDesignV1):
        design_note = "rerandomized balanced (rejective sampling)"
        assignment_detail = (
            "Known base size-m treated-set law conditioned on a pre-treatment balance event B(A): "
            "q_B(A)=q(A)1{B(A)}/P_q(B); the balance event is an absolute covariate mean-difference rule; "
            "conditioning on T_i=a restricts to balanced treated sets containing/not containing node i."
        )
    else:
        design_note = "heterogeneous independent Bernoulli"
        assignment_detail = (
            "Known pretreatment, node-specific independent Bernoulli probabilities "
            "p_i=P(T_i=1|W), fixed for every node; conditioning on T_i=a "
            "does not change the neighbors' assignment law."
        )
    query = QuerySpec(
        type="NETWORK_RANDOMIZED_ARM_MEAN",
        treatment="treatment", outcome="outcome",
        target_population="fixed_network_conditional_context",
        reference_exposure_definition=GROUP_TO_REFERENCE[grouping],
        target_exposure_semantics="design_averaged_randomized_arm_mean",
        target_node_id=node_id,
        own_treatment_value=own_treatment_value,
        exposure_value=wire_state,
        response_target_fingerprint=arm_target_fingerprint(
            network, contract, node_id, own_treatment_value, wire_state
        ),
        authority=query_authority,
        evidence=[evidence],
        interpretation_notes=(
            f"Single node/arm design-standardized mean under the original {design_note} "
            + ("law conditioned on own treatment and strict-majority grouping. "
             if grouping == GROUP_E1 else
             "law conditioned on own treatment and three-level treated-neighbor fraction grouping. "
             if grouping == GROUP_E2 else
             "law conditioned on own treatment and majority within the fixed pre-treatment C_i. "
             if grouping == GROUP_E3 else
             "law conditioned on own treatment and exact treated-neighbor count. "
             if grouping == GROUP_E4 else
             "law conditioned on own treatment and fixed weighted neighbour exposure. "
             if grouping in (EXPOSURE_WEIGHTED_SUM, EXPOSURE_WEIGHTED_PROPORTION) else
             "law conditioned on own treatment and grouped treated-neighbour counts. "
             if grouping == EXPOSURE_GROUPED else
             "law conditioned on own treatment and any-treated-neighbor state. ")
            + "No exposure sufficiency or fixed-allocation policy welfare is asserted."
        ),
    )
    receipt = InterferenceStructureReceipt(
        provider_id=("declared_fixed_network_core_collaborators_v1" if grouping == GROUP_E3
                     else "declared_fixed_network_grouping_v1"),
        source_status="SYNTHETIC_GROUND_TRUTH" if synthetic else "EXPERT_PROVIDED",
        analysis_status="ACCEPTED_AS_ASSUMPTION" if admitted else "UNRESOLVED",
        semantic_fingerprint=interference_structure_semantic_fingerprint(network, None, "UNSPECIFIED"),
        provenance={"source": source}, qualification_evidence=[evidence],
    )
    details = {
        "known_assignment_law": assignment_detail,
        "full_vector_randomization": "The complete assignment vector is randomized independently of the full potential-outcome schedule conditional on W.",
        "consistency": "The observed outcome equals Y_i(T) at the realized full assignment; no exposure-sufficiency condition.",
        "fixed_pretreatment_network": (
            "The fixed network and strict-majority grouping were defined before treatment."
            if grouping == GROUP_E1 else
            "The fixed network and three-level treated-neighbor fraction grouping were defined before treatment."
            if grouping == GROUP_E2 else
            "The fixed network and nonempty core collaborator sets C_i were defined before treatment."
            if grouping == GROUP_E3 else
            "The fixed network and one-hop neighbor-count signature were defined before treatment."
            if grouping == GROUP_E4 else
            "The fixed network and fixed weighted neighbour exposure were defined before treatment."
            if grouping in (EXPOSURE_WEIGHTED_SUM, EXPOSURE_WEIGHTED_PROPORTION) else
            "The fixed network and fixed grouped neighbour sets were defined before treatment."
            if grouping == EXPOSURE_GROUPED else
            "The fixed network and any-treated-neighbor signature were defined before treatment."
        ),
        "finite_conditional_first_moments": "Relevant potential-outcome absolute first moments are finite conditional on W.",
    }
    assumptions = [
        Assumption(
            name=name,
            source=("deterministic_derivation" if synthetic and name == "finite_conditional_first_moments"
                    else "study_protocol" if synthetic and name in {
                        "known_assignment_law", "full_vector_randomization", "fixed_pretreatment_network"}
                    else "demo_specification" if synthetic else "domain_knowledge"),
            status=(AssumptionStatus.UNRESOLVED if not admitted else
                    AssumptionStatus.DERIVED if synthetic and name == "finite_conditional_first_moments" else
                    AssumptionStatus.CERTIFIED if synthetic else AssumptionStatus.ADMITTED),
            evidence=[evidence], details=details[name] + " Source: " + source,
        ) for name in REQUIRED
    ]
    return IdentificationSpec(
        structure=StructureSpec(
            representation_type="fixed_network_interference",
            variables=["treatment", GROUP_TO_VARIABLE[grouping], "outcome", "context"],
            source="human_specified",
            notes="Unit-level fixed network; no variable-level causal DAG required.",
        ),
        network_exposure=network,
        exposure_mapping_claim="UNSPECIFIED",
        interference_structure_receipt=receipt,
        randomized_network_arm_theorem_contract=contract,
        variable_domains={
            "treatment": VariableDomain(kind="binary", values=[0, 1]),
            "outcome": VariableDomain(
                kind=outcome_kind,
                **({"values": [0, 1]} if outcome_kind == "binary" else {}),
            ),
        },
        assumptions=assumptions,
        information_signature=InformationSignature(objects=[InformationObject(
            name="P_exp(Y_i,T_i,S_i|W,G)", regime="experimental",
            variables=["treatment", GROUP_TO_VARIABLE[grouping], "outcome", "context"],
            description=(
                "Explicitly declared complete node/arm POPULATION conditional means; "
                "not actual finite-sample measurements or a fitted estimator."
            ),
            randomized_arm_observable=RandomizedArmObservableV21(
                operator="NODE_ARM_MEANS", source_id="official_randomized_arm_task_constructor_v21",
                provenance=f"{source}: {evidence}",
                admission="CERTIFIED" if synthetic and admitted else "ADMITTED" if admitted else "UNRESOLVED",
                availability="SYMBOLIC_POPULATION_OPERATOR",
                node_order=tuple(network.node_ids), outcome_nodes=tuple(network.node_ids),
                treatment=query.treatment, outcome=query.outcome,
                context_symbol="W", network_fingerprint=network.semantic_fingerprint(),
                assignment_law_fingerprint=_hash(contract.design.model_dump(mode="json")),
                exposure_fingerprint=_hash({
                    "network": network.semantic_fingerprint(), "grouping": contract.grouping,
                    "core_collaborators": contract.core_collaborators,
                }),
                arm_coverage="ALL_NODE_ARMS",
            ),
        )]),
        query=query,
        support_domain=dict(EXPECTED_SUPPORT_DOMAIN),
        provenance={
            "mode": "synthetic_source_contract" if synthetic else "expert_assumption_contract",
            "source": source,
            "population_values": "not_supplied",
            "finite_sample_status": "not_used_to_confirm_causal_assumptions",
        },
    )


def arm_a4_information_reason(spec: IdentificationSpec, *, node_id: str,
                              a: int, s: int) -> str | None:
    """A4 operator entailment (not an A5 causal license). Strict typed-only gate.

    NODE_ARM_MEANS must cover the exact queried cell; node full laws and full
    joint law may derive it when q/g/support conditions are checked separately.
    The constructor's all-arm claim remains a reviewer/synthetic-population
    *declaration*, never an inference from finite rows or variable names.
    """
    contract, net, query = (spec.randomized_network_arm_theorem_contract,
                            spec.network_exposure, spec.query)
    if contract is None or net is None:
        return "RANDOMIZED_NETWORK_ARM_CONTRACT_REQUIRED"
    expected_network = net.semantic_fingerprint()
    expected_design = _hash(contract.design.model_dump(mode="json"))
    expected_exposure = _hash({"network": expected_network,
                               "grouping": contract.grouping,
                               "core_collaborators": contract.core_collaborators})
    # Reused source_id with incompatible operator semantics is a contradictory
    # information contract even when one of those declarations could match.
    seen_sources = {}
    for obj in spec.information_signature.objects:
        claim = obj.randomized_arm_observable
        if claim is None:
            continue
        payload = claim.model_dump(mode="json")
        if claim.source_id in seen_sources and seen_sources[claim.source_id] != payload:
            return "CONFLICTING_A4_SOURCE_ID"
        seen_sources[claim.source_id] = payload
    for obj in spec.information_signature.objects:
        op = obj.randomized_arm_observable
        if op is None or obj.regime != "experimental":
            continue
        # Old coarse metadata must not contradict a new typed operator claim.
        if obj.joint_scope == "node_local_marginals_only":
            continue
        if (obj.outcome_representation == "full_joint_law" and op.operator != "FULL_JOINT_LAW"
            or obj.whole_network_assignment_law_available is False and op.operator != "NODE_ARM_MEANS"
            or obj.joint_scope == "whole_network_assignment" and op.operator == "NODE_ARM_MEANS"):
            continue
        if (op.admission not in {"ADMITTED", "CERTIFIED"}
            or op.availability not in {"SYMBOLIC_POPULATION_OPERATOR", "EXACT_POPULATION_VALUE"}
            or op.node_order != tuple(net.node_ids)
            or op.network_fingerprint != expected_network
            or op.assignment_law_fingerprint != expected_design
            or op.context_symbol != spec.support_domain.get("context_symbol")
            or op.outcome != query.outcome or op.treatment != query.treatment
            or node_id not in op.outcome_nodes):
            continue
        needed_vars = {query.treatment, query.outcome, "context"}
        if op.operator == "NODE_ARM_MEANS":
            if (op.exposure_fingerprint == expected_exposure
                and needed_vars | {GROUP_TO_VARIABLE[contract.grouping]} <= set(obj.variables)
                and (op.arm_coverage == "ALL_NODE_ARMS" or (node_id, a, s) in op.arm_cells)):
                return None
        elif op.operator in {"NODE_FULL_LAW", "FULL_JOINT_LAW"}:
            if needed_vars <= set(obj.variables):
                return None
    return "CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED"


def _eligibility_error(spec: IdentificationSpec) -> str | None:
    q, net, contract = spec.query, spec.network_exposure, spec.randomized_network_arm_theorem_contract
    if q.type != "NETWORK_RANDOMIZED_ARM_MEAN" or contract is None:
        return "RANDOMIZED_NETWORK_ARM_CONTRACT_REQUIRED"
    if q.resolution != "RESOLVED" or q.authority not in TRUSTED_QUERY_AUTHORITIES:
        return "QUERY_NOT_CONFIRMED"
    if query_semantics_implementation_gaps(q):
        return "RANDOMIZED_NETWORK_ARM_QUERY_MISMATCH"
    if spec.structure.representation_type != "fixed_network_interference" or spec.structure.directed_edges or spec.structure.bidirected_edges:
        return "FIXED_NETWORK_SEMANTICS_REQUIRED"
    if not isinstance(net, NetworkExposureSpec) or not net.fixed_network:
        return "KNOWN_FIXED_NETWORK_REQUIRED"
    if spec.exposure_uncertainty is not None:
        return "EXPOSURE_UNCERTAINTY_NOT_PART_OF_DESIGN_AVERAGED_TARGET"
    if (spec.majority_response_theorem_contract is not None
        or spec.network_policy_mixture_theorem_contract is not None
        or spec.network_policy_mixture_population_facts is not None
        or spec.network_policy_mixture_assignment_design is not None
        or spec.network_policy_mixture_information_contract is not None
        or spec.deterministic_policy_oracle is not None
        or spec.reference_exposure_propensity_upper_bound_fact is not None):
        return "MIXED_THEOREM_CONTRACTS_NOT_SUPPORTED"
    if spec.assumption_conflicts:
        return "UNRESOLVED_ASSUMPTION_CONFLICT"
    if isinstance(contract.design, TwoStageQuotaMixtureDesignV27):
        reason = profile_exclusion_reason(spec.assumptions)
        if reason is not None:
            return reason
    if not set(REQUIRED) <= spec.confirmed_assumptions():
        return "REQUIRED_ASSUMPTIONS_NOT_ADMITTED"
    receipt = spec.interference_structure_receipt
    if (receipt is None or not receipt.executable()
        or receipt.analysis_status != "ACCEPTED_AS_ASSUMPTION"):
        return "I1_STRUCTURE_NOT_ADMITTED"
    if receipt.semantic_fingerprint != interference_structure_semantic_fingerprint(net, None, spec.exposure_mapping_claim or "UNSPECIFIED"):
        return "I1_FINGERPRINT_MISMATCH"
    if q.target_node_id not in net.node_ids:
        return "QUERY_NODE_NOT_IN_NETWORK"
    if type(q.own_treatment_value) is not int or q.own_treatment_value not in (0, 1):
        return "INVALID_OWN_TREATMENT_STATE"
    grouping = contract.grouping
    if grouping in W_G_GROUPINGS:
        try:
            exposure_obj = exposure_object(contract)
            state = queried_exposure_state(exposure_obj, q.exposure_value)
        except (ValueError, TypeError, KeyError, ZeroDivisionError):
            return "INVALID_EXPOSURE_STATE"
        if q.reference_exposure_definition != grouping:
            return "EXPOSURE_QUERY_CONTRACT_MISMATCH"
        if q.response_target_fingerprint != arm_target_fingerprint(
            net, contract, q.target_node_id, q.own_treatment_value,
            exposure_state_str(exposure_obj, state),
        ):
            return "DESIGN_DEPENDENT_TARGET_FINGERPRINT_MISMATCH"
    else:
        if grouping not in GROUP_TO_PUBLIC:
            return "UNSUPPORTED_EXPOSURE_GROUPING"
        reference_degree = (len(contract.core_collaborators[q.target_node_id])
                            if grouping == GROUP_E3 and contract.core_collaborators
                            else net.degree_map()[q.target_node_id])
        if type(q.exposure_value) is not int or q.exposure_value not in ExposureSpec(grouping, contract.core_collaborators).states_for_degree(reference_degree):
            return "INVALID_EXPOSURE_STATE"
        try:
            normalized_core = _canonical_core_collaborators(net, grouping, contract.core_collaborators)
        except (ValueError, TypeError, KeyError) as exc:
            return "CORE_COLLABORATOR_MAPPING_INVALID"
        if normalized_core != contract.core_collaborators:
            return "NONCANONICAL_CORE_COLLABORATOR_MAPPING"
        if q.reference_exposure_definition != GROUP_TO_REFERENCE[grouping]:
            return "EXPOSURE_QUERY_CONTRACT_MISMATCH"
        if grouping == GROUP_E2 and net.degree_map()[q.target_node_id] == 0:
            return "EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE"
        if q.response_target_fingerprint != arm_target_fingerprint(
            net, contract, q.target_node_id, q.own_treatment_value, q.exposure_value
        ):
            return "DESIGN_DEPENDENT_TARGET_FINGERPRINT_MISMATCH"
    domain = spec.domain(q.treatment)
    if domain is None or domain.kind != "binary" or set(domain.values or ()) != {0, 1}:
        return "BINARY_TREATMENT_REQUIRED"
    domain = spec.domain(q.outcome)
    if domain is None or domain.kind not in {"continuous", "binary"}:
        return "INTEGRABLE_NUMERIC_OUTCOME_REQUIRED"
    a4_error = arm_a4_information_reason(
        spec, node_id=q.target_node_id,
        a=q.own_treatment_value, s=q.exposure_value)
    if a4_error is not None:
        return a4_error
    if spec.support_domain != EXPECTED_SUPPORT_DOMAIN:
        return "CONTEXT_DOMAIN_NOT_SUPPORTED"
    if len(net.node_ids) > MAX_N or net.max_degree() > MAX_DEGREE:
        return "RANDOMIZED_NETWORK_RESOURCE_LIMIT"
    design = contract.design
    try:
        AssignmentSpec(design)._validate_network(net)
    except (ValueError, TypeError, KeyError):
        return "ASSIGNMENT_DESIGN_NETWORK_MISMATCH"
    if isinstance(design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
        if len(net.node_ids) > MAX_EXACT_ENUMERATION_N:
            return "RANDOMIZED_NETWORK_RESOURCE_LIMIT"
    if isinstance(design,TwoStageQuotaMixtureDesignV27):
        degree=net.degree_map()[q.target_node_id]
        if len(design.quota_profiles)*degree*(degree+1)//2>MAX_D6_CONVOLUTION_CELLS:
            return 'RANDOMIZED_NETWORK_RESOURCE_LIMIT'
    if isinstance(design, MultiGroupFixedQuotaDesignV25):
        # Limit the worst-case exact-Fraction convolution cost per queried node.
        # Refuse rather than silently approximate zero support.
        degree = net.degree_map()[q.target_node_id]
        if degree*(degree+1)//2 > MAX_TWO_GROUP_CONVOLUTION_CELLS:
            return 'RANDOMIZED_NETWORK_RESOURCE_LIMIT'
    if isinstance(design, TwoGroupFixedQuotaDesignV1):
        c0, c1 = _group_neighbor_counts(net, design, q.target_node_id)
        if (c0 + 1) * (c1 + 1) > MAX_TWO_GROUP_CONVOLUTION_CELLS:
            return "RANDOMIZED_NETWORK_RESOURCE_LIMIT"
    if isinstance(design, (HeterogeneousBernoulliDesignV1, ClusterBernoulliDesignV24)):
        degree = net.degree_map()[q.target_node_id]
        if degree * (degree + 1) // 2 > MAX_BERNOULLI_DP_CELLS:
            return "RANDOMIZED_NETWORK_RESOURCE_LIMIT"
    return None


def _choose(n: int, k: int) -> int:
    return comb(n, k) if 0 <= k <= n else 0


def conditional_count_distribution(n: int, m: int, degree: int, a: int) -> list[Fraction]:
    """Legacy internal entry point: D2 conditional count law."""
    return complete_conditional_count_distribution(n, m, degree, a)


def joint_support(
    n: int, m: int, degree: int, a: int, s: int,
    grouping: str = GROUP_E1,
) -> Fraction:
    """Compatibility wrapper: exact D2 arm support from reusable components."""
    if grouping == GROUP_E2 and degree == 0:
        raise ValueError("Three-level neighbor fraction is undefined for an isolate")
    prior = Fraction(m if a else n - m, n)
    law = NeighborCountLaw(
        own_probability=prior,
        conditional_count_mass=tuple(complete_conditional_count_distribution(n, m, degree, a)),
        degree=degree,
    )
    return SupportEngine.from_count_law(law, ExposureSpec(grouping), s).joint_probability


def _neighbors(network: NetworkExposureSpec, node_id: str) -> set[str]:
    """Compatibility wrapper for the common network-neighbor primitive."""
    return neighbor_set(network, node_id)


def _group_neighbor_counts(
    network: NetworkExposureSpec, design: TwoGroupFixedQuotaDesignV1, node_id: str
) -> tuple[int, int]:
    return group_neighbor_counts(network, design, node_id)


def _group_conditional_count_distribution(
    size: int, quota: int, neighbor_count: int, owns_node: bool, a: int
) -> list[Fraction]:
    return group_conditional_count_distribution(size, quota, neighbor_count, owns_node, a)


def joint_support_two_group(
    network: NetworkExposureSpec, design: TwoGroupFixedQuotaDesignV1,
    node_id: str, a: int, s: int, grouping: str = GROUP_E1,
) -> Fraction:
    """Compatibility wrapper: exact D3 arm support from reusable components."""
    return SupportEngine.evaluate(
        network=network, assignment=AssignmentSpec(design), exposure=ExposureSpec(grouping),
        node_id=node_id, own_treatment_value=a, exposure_value=s,
    ).joint_probability


def _program(spec: IdentificationSpec) -> RandomizedNetworkArmMeanProgram:
    q = spec.query
    assert q.target_node_id is not None
    assert type(q.own_treatment_value) is int and (
        type(q.exposure_value) is int or isinstance(q.exposure_value, str))
    design = spec.randomized_network_arm_theorem_contract.design
    if isinstance(design, CompleteRandomizationDesignV1):
        assignment_fields = {"assignment_kind": "complete_randomization", "treated_quota": design.m}
    elif isinstance(design, TwoGroupFixedQuotaDesignV1):
        assignment_fields = {"assignment_kind": "two_group_fixed_quotas",
                             "group_node_ids": design.groups,
                             "group_treated_quotas": design.treated_quotas}
    elif isinstance(design, TwoStageQuotaMixtureDesignV27):
        assignment_fields={'assignment_kind':'two_stage_quota_mixture',
            'two_stage_group_node_ids':design.groups,
            'two_stage_quota_profiles':design.quota_profiles,
            'two_stage_profile_probabilities':design.profile_probabilities}
    elif isinstance(design, MultiGroupFixedQuotaDesignV25):
        assignment_fields = {'assignment_kind':'multi_group_fixed_quotas',
                             'multi_group_node_ids':design.groups,
                             'multi_group_treated_quotas':design.treated_quotas}
    elif isinstance(design, ClusterBernoulliDesignV24):
        assignment_fields = {"assignment_kind": "cluster_bernoulli",
                             "cluster_node_ids": design.clusters,
                             "cluster_probabilities": design.cluster_probabilities}
    elif isinstance(design, UnequalProbabilityFixedQuotaDesignV1):
        assignment_fields = {"assignment_kind": "unequal_probability_fixed_quota",
                             "extended_design": design}
    elif isinstance(design, RerandomizedBalancedDesignV1):
        assignment_fields = {"assignment_kind": "rerandomized_balanced",
                             "extended_design": design}
    else:
        assignment_fields = {"assignment_kind": "heterogeneous_bernoulli",
                             "propensities": dict(design.propensities)}
    contract = spec.randomized_network_arm_theorem_contract
    exposure_fields = {}
    if contract.grouping in W_G_GROUPINGS:
        program_grouping = W_G_TO_PROGRAM[contract.grouping]
        if contract.exposure_weights is not None:
            exposure_fields["exposure_weights"] = dict(contract.exposure_weights)
        if contract.exposure_groups is not None:
            exposure_fields["exposure_groups"] = dict(contract.exposure_groups)
    else:
        program_grouping = GROUP_TO_PROGRAM[contract.grouping]
    return RandomizedNetworkArmMeanProgram(
        node_id=q.target_node_id,
        own_treatment_value=q.own_treatment_value,
        exposure_value=q.exposure_value,
        treatment=q.treatment,
        outcome=q.outcome,
        network_fingerprint=spec.network_exposure.semantic_fingerprint(),
        target_fingerprint=q.response_target_fingerprint,
        grouping=program_grouping,
        core_neighbor_ids=(contract.core_collaborators[q.target_node_id]
                           if contract.grouping == GROUP_E3 else None),
        **assignment_fields,
        **exposure_fields,
    )


def _expected_result_fields(spec: IdentificationSpec, support: Fraction) -> dict:
    q, net = spec.query, spec.network_exposure
    n = len(net.node_ids)
    design = spec.randomized_network_arm_theorem_contract.design
    d = net.degree_map()[q.target_node_id]
    program = _program(spec)
    grouping = spec.randomized_network_arm_theorem_contract.grouping
    if isinstance(design, CompleteRandomizationDesignV1):
        design_objects = [
            f"uniform_complete_randomization(N={n},m={design.m})",
            "q(u|W)=1/C(N,m) for legal allocations and 0 otherwise",
        ]
        certificate_details = {
            "rule_id": RULE_ID,
            "version": "randomized-network-arm-complete-v1",
            "treated_quota": design.m,
            "support_method": "conditional_hypergeometric_count",
        }
    elif isinstance(design, TwoGroupFixedQuotaDesignV1):
        sizes = (len(design.groups[0]), len(design.groups[1]))
        design_objects = [
            f"independent_uniform_two_group_fixed_quotas(n={sizes},m={design.treated_quotas})",
            "q(u|W)=1/[C(n1,m1)C(n2,m2)] for allocations respecting both group quotas; otherwise 0",
            "conditioning T_i=a consumes a quota in i's own pretreatment group",
        ]
        certificate_details = {
            "rule_id": TWO_GROUP_RULE_ID,
            "version": "randomized-network-arm-two-group-v1",
            "group_node_ids": [list(g) for g in design.groups],
            "group_treated_quotas": list(design.treated_quotas),
            "support_method": "conditional_two_group_hypergeometric_convolution",
        }
    elif isinstance(design, TwoStageQuotaMixtureDesignV27):
        design_objects=[
            f'known_two_stage_quota_profile_mixture(H={len(design.groups)}, profiles={len(design.quota_profiles)})',
            'q(t|W)=sum_u pi(u|W) prod_h 1{quota_h(t)=m_h(u)}/C(n_h,m_h(u))',
            'profile is marginalized; direct effect of profile excluded by separate A5 license',
        ]
        certificate_details={
            'rule_id':TWO_STAGE_RULE_ID,'version':'randomized-network-arm-two-stage-v2.7',
            'group_node_ids':[list(g) for g in design.groups],
            'quota_profiles':[list(q) for q in design.quota_profiles],
            'profile_probabilities':list(design.profile_probabilities),
            'support_method':'stage_one_posterior_weighted_conditional_hypergeometric_convolution',
        }
    elif isinstance(design, MultiGroupFixedQuotaDesignV25):
        design_objects = [
            f'independent_uniform_multi_group_fixed_quotas(H={len(design.groups)})',
            'q(t|W)=1/prod_h C(n_h,m_h) for allocations respecting every stratum quota; otherwise 0',
            'conditioning T_i=a consumes one treatment in the own stratum',
        ]
        certificate_details = {
            'rule_id':MULTI_GROUP_RULE_ID,
            'version':'randomized-network-arm-multi-group-v2.5',
            'group_node_ids':[list(g) for g in design.groups],
            'group_treated_quotas':list(design.treated_quotas),
            'support_method':'conditional_multi_group_hypergeometric_convolution',
        }
    elif isinstance(design, ClusterBernoulliDesignV24):
        design_objects = [
            "known_cluster_bernoulli_design(C_j,p_j|W)",
            "one independent Bernoulli draw per fixed cluster; all nodes in a cluster share treatment",
            "conditioning T_i=a fixes the entire own cluster to a",
        ]
        certificate_details = {
            "rule_id": CLUSTER_RULE_ID,
            "version": "randomized-network-arm-cluster-v2.4",
            "cluster_node_ids": [list(c) for c in design.clusters],
            "cluster_probabilities": list(design.cluster_probabilities),
            "support_method": "cluster_conditional_weighted_count_dp",
        }
    elif isinstance(design, UnequalProbabilityFixedQuotaDesignV1):
        design_objects = [
            f"known_unequal_probability_fixed_quota(N={n},m={design.m})",
            "q(A)=p_A for declared size-m treated sets (or unit weights w_i); 0 for other sets; sum_A p_A=1",
            "conditioning T_i=a restricts to treated sets containing/not containing i",
        ]
        certificate_details = {
            "rule_id": UNEQUAL_RULE_ID,
            "version": "randomized-network-arm-unequal-fixed-quota-v1",
            "treated_sets": [list(s) for s in design.treated_sets] if design.treated_sets is not None else None,
            "set_probabilities": list(design.set_probabilities) if design.set_probabilities is not None else None,
            "unit_weights": dict(design.unit_weights) if design.unit_weights else None,
            "support_method": "exact_full_assignment_enumeration",
        }
    elif isinstance(design, RerandomizedBalancedDesignV1):
        design_objects = [
            f"known_rerandomized_balanced_design(base_m={design.base_design.m})",
            "q_B(A)=q(A)1{B(A)}/P_q(B); B = absolute covariate mean differences <= tolerance",
            "conditioning T_i=a restricts to balanced treated sets containing/not containing i",
        ]
        certificate_details = {
            "rule_id": RERANDOMIZED_RULE_ID,
            "version": "randomized-network-arm-rerandomized-balanced-v1",
            "base_design": design.base_design.model_dump(mode="json"),
            "balance_rule": design.balance_rule.model_dump(mode="json"),
            "support_method": "exact_full_assignment_enumeration_rejective_sampling",
        }
    else:
        design_objects = [
            "known_independent_heterogeneous_bernoulli_design(p_i|W)",
            "q(u|W)=prod_j p_j^{u_j}(1-p_j)^{1-u_j}, with every p_j fixed in the theorem contract",
            "conditioning T_i=a does not change neighbors' Bernoulli probabilities",
        ]
        certificate_details = {
            "rule_id": HETEROGENEOUS_RULE_ID,
            "version": "randomized-network-arm-heterogeneous-bernoulli-v1",
            "propensities": dict(design.propensities),
            "support_method": "conditional_poisson_binomial_dp",
        }
    if grouping == GROUP_E1:
        grouping_object = "S_i(u)=1{treated_neighbors_i(u)>floor(degree_i/2)}"
    elif grouping == GROUP_E2:
        grouping_object = "d_i>0; S_i(u)=0 if 3*K_i<d_i, 1 if d_i<=3*K_i<2*d_i, 2 if 3*K_i>=2*d_i"
    elif grouping == GROUP_E4:
        grouping_object = "S_i(u)=sum_{j in N(i)}u_j;exact one-hop treated-neighbor count"
    elif grouping == GROUP_E5:
        grouping_object = "S_i(u)=1{sum_{j in N(i)}u_j>0};isolates have S_i=0"
    elif grouping in W_G_GROUPINGS:
        grouping_object = W_G_TO_PROGRAM[grouping]
    else:
        grouping_object = (
            "Fixed pretreatment C_i subset N(i), |C_i|>0; "
            "S_i(u)=1{sum_{j in C_i}u_j>floor(|C_i|/2)};ties=0"
        )
    if grouping == GROUP_E2:
        certificate_details = {
            **certificate_details,
            "exposure_grouping": grouping,
            "exposure_states": [0, 1, 2],
        }
    elif grouping in {GROUP_E4, GROUP_E5}:
        certificate_details = {**certificate_details, "exposure_grouping": grouping,
                               "exposure_states": list(range(d+1)) if grouping==GROUP_E4 else [0,1]}
    elif grouping == GROUP_E3:
        core = spec.randomized_network_arm_theorem_contract.core_collaborators[q.target_node_id]
        certificate_details = {
            **certificate_details,
            "exposure_grouping": grouping,
            "exposure_states": [0, 1],
            "core_neighbor_ids": list(core),
            "core_reference_size": len(core),
        }
    elif grouping in W_G_GROUPINGS:
        contract = spec.randomized_network_arm_theorem_contract
        certificate_details = {
            **certificate_details,
            "exposure_grouping": grouping,
            "exposure_weights": (dict(contract.exposure_weights)
                                 if contract.exposure_weights is not None else None),
            "exposure_groups": ({k: list(v) for k, v in contract.exposure_groups.items()}
                                if contract.exposure_groups is not None else None),
        }
    return dict(
        status=IdentificationStatus.POINT,
        query=q, backend=BACKEND,
        identified_functional=program,
        network_exposure=net,
        required_population_objects=[
            f"E_exp[{q.outcome}_i^obs | W,G,{q.treatment}_i={q.own_treatment_value},S_i={q.exposure_value}], i={q.target_node_id}"
        ],
        known_design_objects=design_objects + [
            grouping_object,
            "kappa_i,a,s(u|W)=q(u|W)1{u_i=a,S_i(u)=s}/pi_i(a,s|W)",
        ],
        assumptions_used=list(REQUIRED) + ([D6_EXCLUSION] if isinstance(design,TwoStageQuotaMixtureDesignV27) else []),
        guarantee="point_identified",
        validity_domain={
            "network_fingerprint": net.semantic_fingerprint(),
            "target_fingerprint": program.target_fingerprint,
            "context": "full_pretreatment_network_context",
            "population_information_basis": "node_conditional_arm_mean_of_experimental_law",
            "target_semantics": program.semantics,
            "query_arm_support": str(support),
            "finite_sample_estimator_verified": False,
            "executable_estimation_adapter": False,
            "deterministic_policy_value_identified": False,
        },
        certificate={
            **certificate_details,
            "source_spec_sha256": spec_fingerprint(spec),
            "node_degree": d,
            "network_size": n,
            "query_node_id": q.target_node_id,
            "query_arm": [q.own_treatment_value, q.exposure_value],
            "joint_arm_support_probability": str(support),
        },
    )


def _failure(spec: IdentificationSpec, reason: str, *, explanation: str | None = None) -> IdentificationResult:
    return IdentificationResult(
        status=IdentificationStatus.UNSUPPORTED,
        query=spec.query, backend=BACKEND,
        reason_code=reason,
        message=explanation or reason,
        verification_status=VerificationStatus.UNSUPPORTED,
        verification_message="No POINT certificate was issued.",
    )


@dataclass
class RandomizedNetworkArmBackend:
    name: str = BACKEND
    priority: int = 125
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        return spec.query.type == "NETWORK_RANDOMIZED_ARM_MEAN"

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        error = _eligibility_error(spec)
        if error:
            return _failure(spec, error)
        q, net = spec.query, spec.network_exposure
        contract = spec.randomized_network_arm_theorem_contract
        design = contract.design
        exposure_obj = exposure_object(contract)
        assignment = AssignmentSpec(design)
        # Analytic count law for (D1-D6 x E1-E5); exact enumeration for the
        # task-1 designs and for weighted/grouped exposures.
        if isinstance(exposure_obj, ExposureSpec) and assignment.has_analytic_count_law:
            pi = SupportEngine.evaluate(
                network=net,
                assignment=assignment,
                exposure=exposure_obj,
                node_id=q.target_node_id,
                own_treatment_value=q.own_treatment_value,
                exposure_value=q.exposure_value,
            ).joint_probability
        else:
            joint = SupportEngine.joint_support(
                network=net, assignment=assignment, exposure=exposure_obj,
                node_id=q.target_node_id)
            state = queried_exposure_state(exposure_obj, q.exposure_value)
            pi = joint.get((q.own_treatment_value, state), Fraction(0))
        if pi == 0:
            zero_support_detail = (
                "The queried design-standardized conditional arm mean is undefined: "
                "the original declared fixed-quota design assigns zero probability "
                "to this (node, own-treatment, exposure) event. This is not a PARTIAL bound."
            ) if not isinstance(design, HeterogeneousBernoulliDesignV1) else (
                "The queried design-standardized conditional arm mean is undefined: "
                "the original independent Bernoulli design assigns zero probability "
                "to this arm event. This is not a PARTIAL bound."
            )
            return _failure(spec, "ZERO_ARM_SUPPORT", explanation=zero_support_detail)
        return IdentificationResult(
            **_expected_result_fields(spec, pi),
            message=(
                "The single queried randomized-network arm mean is POINT identified "
                "from the experimental population conditional law. This result "
                "does not certify estimation precision or deterministic rollout welfare."
            ),
            trace=[
                TraceStep(step="target_semantics", outcome="PASS",
                          detail=("Condition on own treatment AND exposure under the original independent Bernoulli assignment law."
                                  if isinstance(design, HeterogeneousBernoulliDesignV1) else
                                  "Condition on own treatment AND exposure under the original cluster-correlated Bernoulli law."
                                  if isinstance(design, ClusterBernoulliDesignV24) else
                                  "Condition on own treatment AND exposure under the original joint fixed-quota assignment law.")),
                TraceStep(step="support", outcome="PASS",
                          detail=f"Exact joint arm support pi_i(a,s|W)={pi} is positive."),
                TraceStep(step="randomization_identification", outcome="PASS",
                          detail="Full-vector randomization + consistency identify E[Y_i^obs|W,T_i=a,S_i=s] without exposure sufficiency."),
            ],
        )


def _verify_joint_support_independently(
    n: int, m: int, degree: int, a: int, s: int,
    grouping: str = GROUP_E1,
) -> Fraction:
    """Verifier path: count LEGAL full assignments in each arm / C(N,m).

    Unlike the proposing code, this does not condition on own treatment,
    does not use hypergeometric conditional weights, and does not call the
    proposer support function. Each numerator term counts how many uniform
    size-m allocations select k of the degree neighbors and m-a-k others.
    """
    denominator = comb(n, m)
    numerator = 0
    for k in range(degree + 1):
        if not _verifier_matches_exposure(k, degree, s, grouping):
            continue
        numerator += _choose(degree, k) * _choose(n - 1 - degree, m - a - k)
    return Fraction(numerator, denominator)


def _verify_two_group_joint_support_independently(
    network: NetworkExposureSpec, design: TwoGroupFixedQuotaDesignV1,
    node_id: str, a: int, s: int, grouping: str = GROUP_E1,
    reference_nodes: frozenset[str] | None = None,
) -> Fraction:
    """Verifier: count original legal full assignments, without conditioning.

    For each group we count the selections for each neighbor count, fixing the
    query node to a only in its group, then divide by the PRODUCT of original
    (unconditional) group allocation counts. Unlike the proposer this function
    does not calculate P(T_i=a) or any conditional hypergeometric probability.
    """
    if reference_nodes is None:
        counts = _group_neighbor_counts(network, design, node_id)
    else:
        # Independent verifier counts the declared core against original
        # group membership directly, without using the proposer count law.
        counts = tuple(sum(node in reference_nodes for node in members)
                       for members in design.groups)
    degree = sum(counts)
    group_counts: list[list[int]] = []
    denominator = 1
    for r, members in enumerate(design.groups):
        size, quota, c = len(members), design.treated_quotas[r], counts[r]
        in_group = node_id in members
        denominator *= comb(size, quota)
        rest = size - int(in_group) - c
        remaining = quota - (a if in_group else 0)
        group_counts.append([
            _choose(c, k) * _choose(rest, remaining - k)
            for k in range(c + 1)
        ])
    numerator = 0
    for k0, ways0 in enumerate(group_counts[0]):
        for k1, ways1 in enumerate(group_counts[1]):
            if _verifier_matches_exposure(k0 + k1, degree, s, grouping):
                numerator += ways0 * ways1
    return Fraction(numerator, denominator)


def _verify_multi_group_joint_support_independently(
    network:NetworkExposureSpec, design:MultiGroupFixedQuotaDesignV25,
    node_id:str,a:int,s:int,grouping:str=GROUP_E1,
    reference_nodes:frozenset[str]|None=None,
)->Fraction:
    """Independent original-law enumeration by INTEGER generating polynomials.

    In each stratum, the count of quota-compatible full assignments with k
    treated reference neighbors is C(c,k)C(rest,m-a_own-k). Multiply these
    integer generating polynomials across ALL strata, and divide by the
    product of original assignment counts. No conditional hypergeometric law
    or proposer SupportEngine is used.
    """
    refs=_neighbors(network,node_id) if reference_nodes is None else reference_nodes
    degree=len(refs)
    counts=[1]
    denominator=1
    for group,quota in zip(design.groups,design.treated_quotas):
        own=int(node_id in group)
        c=len(refs.intersection(group))
        rest=len(group)-own-c
        ways=[_choose(c,k)*_choose(rest,quota-a*own-k) for k in range(c+1)]
        updated=[0]*(len(counts)+len(ways)-1)
        for x,u in enumerate(counts):
            for y,v in enumerate(ways):
                updated[x+y]+=u*v
        counts=updated
        denominator*=comb(len(group),quota)
    if len(counts)!=degree+1:
        raise ValueError('D5 verifier polynomial degree mismatch')
    return Fraction(sum(ways for k,ways in enumerate(counts)
                        if _verifier_matches_exposure(k,degree,s,grouping)),denominator)


def _verify_heterogeneous_joint_support_independently(
    network: NetworkExposureSpec,
    design: HeterogeneousBernoulliDesignV1,
    node_id: str,
    a: int,
    s: int,
    grouping: str = GROUP_E1,
    reference_nodes: frozenset[str] | None = None,
) -> Fraction:
    """Independent verifier: coefficients of a balanced generating-product.

    Does not call AssignmentSpec, the proposer Poisson-binomial DP, or
    SupportEngine. Small-N tests separately enumerate all 2**N allocations.
    """
    own_p = Fraction(design.propensities[node_id])
    own_mass = own_p if a else 1 - own_p
    if own_mass == 0:
        return Fraction(0)
    neighbors = _neighbors(network, node_id) if reference_nodes is None else reference_nodes
    polys = [
        (1 - Fraction(design.propensities[j]), Fraction(design.propensities[j]))
        for j in sorted(neighbors)
    ]
    if not polys:
        polys = [(Fraction(1),)]
    while len(polys) > 1:
        merged = []
        for offset in range(0, len(polys), 2):
            if offset + 1 == len(polys):
                merged.append(polys[offset])
                continue
            left, right = polys[offset], polys[offset + 1]
            product = [Fraction(0)] * (len(left) + len(right) - 1)
            for k, left_mass in enumerate(left):
                for l, right_mass in enumerate(right):
                    product[k+l] += left_mass * right_mass
            merged.append(tuple(product))
        polys = merged
    degree = len(neighbors)
    selected_mass = sum(
        (mass for k, mass in enumerate(polys[0])
         if _verifier_matches_exposure(k, degree, s, grouping)),
        Fraction(0),
    )
    return own_mass * selected_mass


def verify_randomized_network_arm(
    spec: IdentificationSpec, result: IdentificationResult
) -> IdentificationResult:
    """Replay typed spec, exact combinatorial support, program and certificate."""
    checked = result.model_copy(deep=True)
    try:
        normalized = IdentificationSpec.model_validate(spec.model_dump(mode="python", warnings="error"))
        if normalized.model_dump(mode="json", warnings="error") != spec.model_dump(mode="json", warnings="error"):
            raise ValueError("Non-canonical mutated specification")
        error = _eligibility_error(normalized)
        if error:
            raise ValueError(error)
        net, q, contract = normalized.network_exposure, normalized.query, normalized.randomized_network_arm_theorem_contract
        design = contract.design
        reference_nodes = (frozenset(contract.core_collaborators[q.target_node_id])
                           if contract.grouping == GROUP_E3 else None)
        if contract.grouping in W_G_GROUPINGS:
            exposure_obj = exposure_object(contract)
            state = queried_exposure_state(exposure_obj, q.exposure_value)
            report = _verify_joint_support(
                network=net, design=AssignmentSpec(design), exposure=exposure_obj,
                node_id=q.target_node_id, proposed={})
            expected_support = report["oracle"].get((q.own_treatment_value, state), Fraction(0))
        elif isinstance(design, CompleteRandomizationDesignV1):
            expected_support = _verify_joint_support_independently(
                len(net.node_ids), design.m,
                len(reference_nodes) if reference_nodes is not None else net.degree_map()[q.target_node_id],
                q.own_treatment_value, q.exposure_value,
                grouping=contract.grouping,
            )
        elif isinstance(design, TwoGroupFixedQuotaDesignV1):
            expected_support = _verify_two_group_joint_support_independently(
                net, design, q.target_node_id,
                q.own_treatment_value, q.exposure_value,
                grouping=contract.grouping,
                reference_nodes=reference_nodes,
            )
        elif isinstance(design, TwoStageQuotaMixtureDesignV27):
            expected_support=_verify_d6_joint_support(net,design,q.target_node_id,
                q.own_treatment_value,q.exposure_value,contract.grouping,
                _verifier_matches_exposure,reference_nodes=reference_nodes)
        elif isinstance(design, MultiGroupFixedQuotaDesignV25):
            expected_support = _verify_multi_group_joint_support_independently(
                net,design,q.target_node_id,q.own_treatment_value,
                q.exposure_value,grouping=contract.grouping,reference_nodes=reference_nodes)
        elif isinstance(design, ClusterBernoulliDesignV24):
            expected_support = verify_cluster_joint_support(
                net, design, q.target_node_id, q.own_treatment_value,
                q.exposure_value, contract.grouping, _verifier_matches_exposure,
                reference_nodes=reference_nodes)
        elif isinstance(design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
            report = _verify_joint_support(
                network=net, design=as_design_dataclass(design),
                exposure=ExposureSpec(contract.grouping, contract.core_collaborators),
                node_id=q.target_node_id, proposed={},
            )
            expected_support = report["oracle"].get(
                (q.own_treatment_value, q.exposure_value), Fraction(0))
        else:
            expected_support = _verify_heterogeneous_joint_support_independently(
                net, design, q.target_node_id,
                q.own_treatment_value, q.exposure_value,
                grouping=contract.grouping,
                reference_nodes=reference_nodes,
            )
        if expected_support <= 0:
            raise ValueError("ZERO_ARM_SUPPORT")
        expected = IdentificationResult(**_expected_result_fields(normalized, expected_support))
        ignored = {"trace", "message", "verification_status", "verification_message"}
        if checked.model_dump(mode="json", exclude=ignored, warnings="error") != expected.model_dump(
            mode="json", exclude=ignored, warnings="error"
        ):
            raise ValueError("Target, functional, support or proof certificate differs from the independent replay")
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError) as exc:
        checked.verification_status = VerificationStatus.REJECTED
        checked.verification_message = str(exc)
        return checked
    checked.verification_status = VerificationStatus.VERIFIED
    if isinstance(design, HeterogeneousBernoulliDesignV1):
        checked.verification_message = (
            "Verified exact independent Bernoulli arm support by balanced generating-polynomial multiplication; "
            "confirmed theorem contract and E[Y_i^obs|W,T_i=a,S_i=s]. "
            "This does not validate study assumptions or downstream estimator accuracy."
        )
    elif isinstance(design, TwoStageQuotaMixtureDesignV27):
        checked.verification_message=(
            'D6 verified by independent original-assignment integer polynomial counting; '
            'the first-stage no-direct-effect assumption is externally admitted, not tested.')
    elif isinstance(design, MultiGroupFixedQuotaDesignV25):
        checked.verification_message = (
            'Verified exact multi-stratum quotas by independent integer generating polynomial counts; '
            'the theorem identifies the design-standardized population arm mean. '
            'No estimator accuracy or empirical assumptions are verified.'
        )
    elif isinstance(design, ClusterBernoulliDesignV24):
        checked.verification_message = (
            "Verified exact cluster-correlated Bernoulli support by independent balanced cluster-polynomial counting; "
            "confirmed theorem contract and E[Y_i^obs|W,T_i=a,S_i=s]. "
            "This does not validate study assumptions or downstream estimator accuracy."
        )
    elif isinstance(design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
        checked.verification_message = (
            "Verified exact task-1 design support by independent full-assignment enumeration; "
            "confirmed theorem contract and E[Y_i^obs|W,T_i=a,S_i=s]. "
            "This does not validate study assumptions or downstream estimator accuracy."
        )
    else:
        checked.verification_message = (
            "Verified exact joint design support by independent combinatorial allocation counting; "
            "confirmed theorem contract and E[Y_i^obs|W,T_i=a,S_i=s]. "
            "This does not validate study assumptions or downstream estimator accuracy."
        )
    return checked
