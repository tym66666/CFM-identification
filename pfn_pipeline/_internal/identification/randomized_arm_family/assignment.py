"""Known assignment q(T|W) -> law of treated-neighbor count given T_i=a.

Supports D1 heterogeneous Bernoulli, D2 complete randomization, D3 two-group quotas,
D4 cluster Bernoulli, D5 multi-group quotas and D6 two-stage quota mixtures.
No assignment mechanism is inferred from data.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from collections.abc import Mapping
from math import comb

from ..schemas import (
    CompleteRandomizationDesignV1,
    HeterogeneousBernoulliDesignV1,
    NetworkExposureSpec,
    TwoGroupFixedQuotaDesignV1, ClusterBernoulliDesignV24, MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1, CovariateBalanceRuleV1,
)

from .assignment_extensions import (
    RerandomizedBalancedDesign, UnequalProbabilityFixedQuotaDesign, CovariateBalanceRule,
)

AssignmentDesign = (CompleteRandomizationDesignV1 | TwoGroupFixedQuotaDesignV1
                    | HeterogeneousBernoulliDesignV1 | ClusterBernoulliDesignV24 | MultiGroupFixedQuotaDesignV25 | TwoStageQuotaMixtureDesignV27
                    | UnequalProbabilityFixedQuotaDesign | RerandomizedBalancedDesign)


def as_design_dataclass(design):
    """Convert a serializable task-1 wire design to its exact dataclass twin.

    The wire types carry JSON-serializable treated sets / weights / balance
    covariates; the exact-support engine operates on the frozen dataclasses.
    Passing any other design returns it unchanged.
    """
    if isinstance(design, UnequalProbabilityFixedQuotaDesignV1):
        if design.unit_weights is not None:
            return UnequalProbabilityFixedQuotaDesign(
                nodes=design.nodes, m=design.m,
                unit_weights={n: Fraction(w) for n, w in design.unit_weights.items()})
        return UnequalProbabilityFixedQuotaDesign(
            nodes=design.nodes, m=design.m,
            assignment_probabilities={frozenset(s): Fraction(p)
                                      for s, p in zip(design.treated_sets, design.set_probabilities)})
    if isinstance(design, RerandomizedBalancedDesignV1):
        base = as_design_dataclass(design.base_design)
        rule = CovariateBalanceRule(
            covariates={name: {n: Fraction(v) for n, v in values.items()}
                        for name, values in design.balance_rule.covariates.items()},
            tolerance=Fraction(design.balance_rule.tolerance),
            metric=design.balance_rule.metric)
        return RerandomizedBalancedDesign(
            base_design=base, balance_rule=rule,
            balance_description=f"absolute pre-treatment covariate mean differences <= {design.balance_rule.tolerance}")
    return design


def _choose(n: int, k: int) -> int:
    return comb(n, k) if 0 <= k <= n else 0


def complete_conditional_count_distribution(n: int, m: int, degree: int, a: int) -> list[Fraction]:
    """P(K_i=k | T_i=a) for uniform fixed-m complete randomization.

    As in v0.5, an impossible own-treatment arm yields an all-zero list.
    """
    own_mass = Fraction(m if a else n - m, n)
    if not own_mass:
        return [Fraction(0)] * (degree + 1)
    remaining = m - a
    denominator = _choose(n - 1, remaining)
    assert denominator > 0
    return [
        Fraction(_choose(degree, k) * _choose(n - 1 - degree, remaining - k), denominator)
        for k in range(degree + 1)
    ]


def neighbor_set(network: NetworkExposureSpec, node_id: str) -> set[str]:
    result: set[str] = set()
    for left, right in network.undirected_edges:
        if left == node_id:
            result.add(right)
        elif right == node_id:
            result.add(left)
    return result


def group_neighbor_counts(
    network: NetworkExposureSpec, design: TwoGroupFixedQuotaDesignV1, node_id: str,
    reference_nodes: frozenset[str] | None = None,
) -> tuple[int, int]:
    neighbors = neighbor_set(network, node_id) if reference_nodes is None else reference_nodes
    return tuple(len(neighbors.intersection(members)) for members in design.groups)


def group_conditional_count_distribution(
    size: int, quota: int, neighbor_count: int, owns_node: bool, a: int,
) -> list[Fraction]:
    """Conditional hypergeometric law; the queried node consumes a quota."""
    others = size - int(owns_node)
    remaining_quota = quota - (a if owns_node else 0)
    denominator = comb(others, remaining_quota)
    return [
        Fraction(_choose(neighbor_count, k) *
                 _choose(others - neighbor_count, remaining_quota - k), denominator)
        for k in range(neighbor_count + 1)
    ]


def _convolve(left: tuple[Fraction, ...], right: list[Fraction]) -> tuple[Fraction, ...]:
    out = [Fraction(0)] * (len(left) + len(right) - 1)
    for j, mass_left in enumerate(left):
        if mass_left:
            for k, mass_right in enumerate(right):
                if mass_right:
                    out[j + k] += mass_left * mass_right
    return tuple(out)


def independent_bernoulli_neighbor_count_distribution(
    propensities: Mapping[str, str], neighbors: set[str],
) -> tuple[Fraction, ...]:
    """Exact Poisson-binomial law by sequential Bernoulli DP (proposer)."""
    masses = [Fraction(1)]
    for neighbor in sorted(neighbors):
        p = Fraction(propensities[neighbor])
        updated = [Fraction(0)] * (len(masses) + 1)
        for k, weight in enumerate(masses):
            updated[k] += weight * (1 - p)
            updated[k + 1] += weight * p
        masses = updated
    return tuple(masses)


@dataclass(frozen=True)
class NeighborCountLaw:
    """P(T_i=a) and P(K_i=k | T_i=a,W), *not* an observed outcome model.

    When P(T_i=a)=0 the conditional law is not defined; zero coefficients are
    carried solely to allow safe joint-support evaluation (joint mass is 0).
    """
    own_probability: Fraction
    conditional_count_mass: tuple[Fraction, ...]
    degree: int


def cluster_bernoulli_conditional_count_law(
    design: ClusterBernoulliDesignV24, node_id: str, a: int,
    reference_nodes: set[str],
) -> NeighborCountLaw:
    """Proposer: sequential DP over independent CLUSTER draws, not node draws.

    The cluster containing the queried node is conditioned on T_i=a and all
    reference neighbors in that cluster are deterministically set to a.
    """
    own_idx = next(j for j,c in enumerate(design.clusters) if node_id in c)
    p = Fraction(design.cluster_probabilities[own_idx])
    own = p if a else 1-p
    degree = len(reference_nodes)
    if not own:
        return NeighborCountLaw(Fraction(0), (Fraction(0),)*(degree+1), degree)
    shift = a * len(reference_nodes.intersection(design.clusters[own_idx]))
    masses = [Fraction(1)]
    for j,c in enumerate(design.clusters):
        if j == own_idx:
            continue
        count = len(reference_nodes.intersection(c))
        if count == 0:
            continue
        p_j = Fraction(design.cluster_probabilities[j])
        new = [Fraction(0)]*(len(masses)+count)
        for k,mass in enumerate(masses):
            new[k] += mass*(1-p_j)
            new[k+count] += mass*p_j
        masses = new
    out = [Fraction(0)]*(degree+1)
    for k,mass in enumerate(masses):
        out[k+shift] = mass
    return NeighborCountLaw(own, tuple(out), degree)


def multi_group_conditional_count_law(
    design: MultiGroupFixedQuotaDesignV25, node_id: str, a: int,
    reference_nodes: set[str],
) -> NeighborCountLaw:
    """Proposer: conditional hypergeometric laws convolved across independent strata.

    The own stratum uses m_h-a draws from n_h-1 after fixing T_i=a;
    all other strata retain original quotas. Probabilities are exact.
    """
    own_idx = next(j for j,g in enumerate(design.groups) if node_id in g)
    n_own = len(design.groups[own_idx]); m_own = design.treated_quotas[own_idx]
    own_mass = Fraction(m_own if a else n_own-m_own, n_own)
    degree = len(reference_nodes)
    if not own_mass:
        return NeighborCountLaw(Fraction(0),(Fraction(0),)*(degree+1),degree)
    masses: tuple[Fraction,...] = (Fraction(1),)
    for j,(group,quota) in enumerate(zip(design.groups,design.treated_quotas)):
        count = len(reference_nodes.intersection(group))
        law = group_conditional_count_distribution(
            len(group),quota,count,j==own_idx,a)
        masses = _convolve(masses,law)
    if len(masses) != degree+1 or sum(masses) != 1:
        raise ValueError('D5 invalid conditional count distribution')
    return NeighborCountLaw(own_mass,masses,degree)


def two_stage_conditional_count_law(
    design: TwoStageQuotaMixtureDesignV27, node_id: str, a: int,
    reference_nodes: set[str],
) -> NeighborCountLaw:
    """Production proposer: stage-1 weighted conditional hypergeometric convolution.

    The mixture is weighted by pi(u)*P(T_i=a|u), NOT pi(u). Never condition
    on an impossible own arm; that case returns zero JOINT support metadata.
    """
    own_idx = next(j for j,g in enumerate(design.groups) if node_id in g)
    degree=len(reference_nodes)
    joint=[Fraction(0)]*(degree+1)
    own_total=Fraction(0)
    for profile, raw in zip(design.quota_profiles,design.profile_probabilities):
        group=design.groups[own_idx]
        own=Fraction(profile[own_idx] if a else len(group)-profile[own_idx],len(group))
        if not own: continue
        weight=Fraction(raw)*own
        own_total+=weight
        part=(Fraction(1),)
        for j,(members,quota) in enumerate(zip(design.groups,profile)):
            local=group_conditional_count_distribution(
                len(members),quota,len(reference_nodes.intersection(members)),j==own_idx,a)
            part=_convolve(part,local)
        if len(part)!=degree+1 or sum(part)!=1:
            raise ValueError('D6 conditional count polynomial invalid')
        for k,p in enumerate(part):joint[k]+=weight*p
    if not own_total:
        return NeighborCountLaw(Fraction(0),tuple(Fraction(0) for _ in joint),degree)
    if sum(joint)!=own_total:
        raise ValueError('D6 joint count probability not normalized')
    return NeighborCountLaw(own_total,tuple(m/own_total for m in joint),degree)


@dataclass(frozen=True)
class AssignmentSpec:
    """Internal adapter over the existing v1 serializable assignment designs."""
    design: AssignmentDesign

    def __post_init__(self) -> None:
        if isinstance(self.design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
            object.__setattr__(self, "design", as_design_dataclass(self.design))
        if not isinstance(self.design, (CompleteRandomizationDesignV1, TwoGroupFixedQuotaDesignV1,
                                        HeterogeneousBernoulliDesignV1, ClusterBernoulliDesignV24,
                                        MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
                                        UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign)):
            raise TypeError("AssignmentSpec supports only typed D1-D6 and task-1 designs")

    @property
    def has_analytic_count_law(self) -> bool:
        """True when the design exposes an analytic neighbor-count law (typed D1-D6)."""
        return not isinstance(self.design, (UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign))

    def _validate_network(self, network: NetworkExposureSpec) -> None:
        """The internal adapter must not silently reinterpret a quota design."""
        if isinstance(self.design, (UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign)):
            nodes = (self.design.nodes if isinstance(self.design, UnequalProbabilityFixedQuotaDesign)
                     else self.design.base_design.nodes)
            if set(nodes) != set(network.node_ids):
                raise ValueError("task-1 assignment design nodes must match the network nodes exactly")
            return
        if isinstance(self.design, CompleteRandomizationDesignV1):
            if self.design.m > len(network.node_ids):
                raise ValueError("complete-randomization quota exceeds network size")
        elif isinstance(self.design, TwoGroupFixedQuotaDesignV1):
            members = self.design.groups[0] + self.design.groups[1]
            if len(members) != len(network.node_ids) or set(members) != set(network.node_ids):
                raise ValueError("two assignment groups must partition the network")
        elif isinstance(self.design, TwoStageQuotaMixtureDesignV27):
            members = tuple(n for group in self.design.groups for n in group)
            if set(members) != set(network.node_ids) or len(members) != len(network.node_ids):
                raise ValueError("D6 pretreatment groups must partition the network")
        elif isinstance(self.design, MultiGroupFixedQuotaDesignV25):
            members = tuple(n for group in self.design.groups for n in group)
            if set(members) != set(network.node_ids) or len(members) != len(network.node_ids):
                raise ValueError("D5 pretreatment strata must partition the network")
        elif isinstance(self.design, ClusterBernoulliDesignV24):
            members = tuple(n for c in self.design.clusters for n in c)
            if set(members) != set(network.node_ids) or len(members) != len(network.node_ids):
                raise ValueError("D4 pretreatment clusters must partition exactly the network nodes")
        elif set(self.design.propensities) != set(network.node_ids):
            raise ValueError("known Bernoulli propensities must cover precisely the network nodes")

    def full_assignment_probability(
        self, network: NetworkExposureSpec, treatments: Mapping[str, int],
    ) -> Fraction:
        """Known original q(t|W), including zero mass for forbidden allocations.

        Only a design-law evaluator: never infers a design from treatment data.
        Primarily useful for small-network audits and target-kernel checks.
        """
        self._validate_network(network)
        if set(treatments) != set(network.node_ids):
            raise ValueError("full treatment vector must contain exactly the network node ids")
        if any(type(value) is not int or value not in (0, 1) for value in treatments.values()):
            raise ValueError("full treatment vector must be binary integers")
        if isinstance(self.design, (UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign)):
            return self.design.assignment_probability(treatments)
        if isinstance(self.design, CompleteRandomizationDesignV1):
            if sum(treatments.values()) != self.design.m:
                return Fraction(0)
            return Fraction(1, comb(len(network.node_ids), self.design.m))
        if isinstance(self.design, TwoStageQuotaMixtureDesignV27):
            actual=tuple(sum(treatments[n] for n in g) for g in self.design.groups)
            denominator=1
            if actual not in self.design.quota_profiles:return Fraction(0)
            for group, m in zip(self.design.groups,actual):denominator*=comb(len(group),m)
            p=sum((Fraction(weight) for profile,weight in zip(
                self.design.quota_profiles,self.design.profile_probabilities) if profile==actual),Fraction(0))
            return p/denominator
        if isinstance(self.design, MultiGroupFixedQuotaDesignV25):
            if any(sum(treatments[n] for n in group) != quota
                   for group,quota in zip(self.design.groups,self.design.treated_quotas)):
                return Fraction(0)
            denominator = 1
            for group,quota in zip(self.design.groups,self.design.treated_quotas):
                denominator *= comb(len(group),quota)
            return Fraction(1,denominator)
        if isinstance(self.design, ClusterBernoulliDesignV24):
            weight = Fraction(1)
            for members, raw in zip(self.design.clusters, self.design.cluster_probabilities):
                values = {treatments[node] for node in members}
                if len(values) != 1:
                    return Fraction(0)
                p = Fraction(raw)
                weight *= p if next(iter(values)) else 1-p
            return weight
        if isinstance(self.design, HeterogeneousBernoulliDesignV1):
            weight = Fraction(1)
            for node in network.node_ids:
                p = Fraction(self.design.propensities[node])
                weight *= p if treatments[node] else 1-p
            return weight
        if any(sum(treatments[node] for node in members) != quota
               for members, quota in zip(self.design.groups, self.design.treated_quotas)):
            return Fraction(0)
        denominator = (comb(len(self.design.groups[0]), self.design.treated_quotas[0])
                       * comb(len(self.design.groups[1]), self.design.treated_quotas[1]))
        return Fraction(1, denominator)

    def conditional_neighbor_count_law(
        self, network: NetworkExposureSpec, node_id: str, own_treatment_value: int,
        reference_nodes: frozenset[str] | None = None,
    ) -> NeighborCountLaw:
        self._validate_network(network)
        if isinstance(self.design, (UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign)):
            raise NotImplementedError(
                "task-1 designs have no analytic neighbor-count law; "
                "use SupportEngine.joint_support (exact enumeration)")
        if node_id not in network.node_ids:
            raise ValueError("queried node must be in the network")
        if type(own_treatment_value) is not int or own_treatment_value not in (0, 1):
            raise ValueError("own treatment must be binary")
        if reference_nodes is not None and not reference_nodes <= neighbor_set(network, node_id):
            raise ValueError("reference_nodes must be actual pretreatment neighbors")
        design = self.design
        if isinstance(design, CompleteRandomizationDesignV1):
            n = len(network.node_ids)
            degree = (network.degree_map()[node_id] if reference_nodes is None
                      else len(reference_nodes))
            m = design.m
            own_mass = Fraction(m if own_treatment_value else n - m, n)
            distribution = complete_conditional_count_distribution(n, m, degree, own_treatment_value)
            return NeighborCountLaw(own_mass, tuple(distribution), degree)

        if isinstance(design, TwoStageQuotaMixtureDesignV27):
            refs=set(reference_nodes) if reference_nodes is not None else neighbor_set(network,node_id)
            return two_stage_conditional_count_law(design,node_id,own_treatment_value,refs)
        if isinstance(design, MultiGroupFixedQuotaDesignV25):
            refs = set(reference_nodes) if reference_nodes is not None else neighbor_set(network,node_id)
            return multi_group_conditional_count_law(design,node_id,own_treatment_value,refs)

        if isinstance(design, ClusterBernoulliDesignV24):
            refs = set(reference_nodes) if reference_nodes is not None else neighbor_set(network,node_id)
            return cluster_bernoulli_conditional_count_law(
                design,node_id,own_treatment_value,refs)

        if isinstance(design, HeterogeneousBernoulliDesignV1):
            neighbors = neighbor_set(network, node_id) if reference_nodes is None else reference_nodes
            degree = len(neighbors)
            own_p = Fraction(design.propensities[node_id])
            own_mass = own_p if own_treatment_value else 1 - own_p
            if not own_mass:
                return NeighborCountLaw(own_mass, (Fraction(0),) * (degree + 1), degree)
            # T_i is independent of T_-i under D1, even though p_j may differ.
            conditional = independent_bernoulli_neighbor_count_distribution(
                design.propensities, neighbors,
            )
            return NeighborCountLaw(own_mass, conditional, degree)

        own_group = 0 if node_id in design.groups[0] else 1
        own_size = len(design.groups[own_group])
        own_quota = design.treated_quotas[own_group]
        own_mass = Fraction(own_quota if own_treatment_value else own_size - own_quota, own_size)
        counts = group_neighbor_counts(network, design, node_id, reference_nodes)
        degree = sum(counts)
        if not own_mass:
            return NeighborCountLaw(own_mass, (Fraction(0),) * (degree + 1), degree)
        conditional_count_mass = (Fraction(1),)
        for r, members in enumerate(design.groups):
            law = group_conditional_count_distribution(
                len(members), design.treated_quotas[r], counts[r], r == own_group, own_treatment_value,
            )
            conditional_count_mass = _convolve(conditional_count_mass, law)
        return NeighborCountLaw(own_mass, conditional_count_mass, degree)
