"""R1b v1.9: verified population mean of a FIXED full-vector policy.

This is a real identification theorem route, separate from the v1.7 *shadow*
preflight. For a fixed pretreatment network, q-known randomized experiment,
consistency and full-vector randomization, and q(z)>0,

 V(z|W)=sum_i weight_i E[Y_i^obs | T_vector=z,W].

A4 must explicitly supply assignment-resolved population means or a stronger
observable law; node arm means are NOT sufficient. The result contains no
estimated outcomes or PFN promises. This route does not rely on any exposure
mapping/sufficiency and does not extend to policies outside q's full support.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from fractions import Fraction
from itertools import combinations
from math import comb
from typing import Literal

from ._internal.identification.schemas import (
    Assumption, CompleteRandomizationDesignV1, TwoGroupFixedQuotaDesignV1,
    HeterogeneousBernoulliDesignV1, ClusterBernoulliDesignV24, MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1,
)
from ._internal.identification.randomized_arm_family import AssignmentSpec
from ._internal.identification.randomized_arm_family.two_stage_verifier import original_assignment_mass
from ._internal.identification.randomized_arm_family.two_stage_a5 import profile_exclusion_reason
from .identification_a4_shadow import _sha
from .identification_route_shadow import TargetSemanticsV15, FIXED_POLICY_CANDIDATE
from .network_inquiry_shadow import (
    NetworkStudyContextV17, NetworkA4SourceV17, NonArmRouteAssessmentV17,
    assess_nonarm_network_inquiry, replay_nonarm_network_inquiry,
)

__all__ = [
    'R1bPolicyUnavailable', 'VerifiedFixedPolicyV19',
    'identify_verified_fixed_policy', 'replay_verified_fixed_policy',
]

VERSION = 'randomized-network-fixed-full-assignment-policy-point-v1.9'
THEOREM_ID = 'R1B_RANDOMIZED_FULL_ASSIGNMENT_POLICY_POINT_V1'
VALID_A4_RULES = {
    'A4_SELECT_NODE_ASSIGNMENT_MEAN_V17',
    'A4_NODE_FULL_LAW_TO_ASSIGNMENT_MEAN_V17',
    'A4_FULL_JOINT_TO_ASSIGNMENT_MEAN_V17',
}


class R1bPolicyUnavailable(ValueError):
    """Workflow or route failure, NEVER a mathematical PARTIAL determination."""

    def __init__(self, reason_code: str, message: str = ''):
        self.reason_code = reason_code
        super().__init__(f'{reason_code}: {message}' if message else reason_code)


def _independent_unequal_q(design, treated, nodes) -> Fraction:
    """Independent q(A) from declared unequal-fixed-quota fields."""
    treated = frozenset(treated)
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
    for members, prob in zip(design.treated_sets, design.set_probabilities):
        if frozenset(members) == treated:
            return Fraction(prob)
    return Fraction(0)


def _balance_ok(rule, treated, nodes) -> bool:
    """Independent absolute-mean-difference balance event from raw covariate values."""
    treated = set(treated)
    untreated = set(nodes) - treated
    if not treated or not untreated:
        return False
    for values in rule.covariates.values():
        if set(values) != set(nodes):
            raise R1bPolicyUnavailable('BALANCE_COVARIATE_SCOPE_MISMATCH')
        tm = sum((Fraction(values[n]) for n in treated), Fraction(0)) / len(treated)
        um = sum((Fraction(values[n]) for n in untreated), Fraction(0)) / len(untreated)
        if abs(tm - um) > Fraction(rule.tolerance):
            return False
    return True


def _independent_rerandomized_q(design, treated, nodes) -> Fraction:
    """Independent q_B(A)=q(A)1{B(A)}/P_q(B) from declared base law and balance rule."""
    base = design.base_design
    treated = frozenset(treated)
    if len(treated) != base.m or not _balance_ok(design.balance_rule, treated, nodes):
        return Fraction(0)
    normalizer = Fraction(0)
    for combo in combinations(nodes, base.m):
        combo_set = frozenset(combo)
        if _balance_ok(design.balance_rule, combo_set, nodes):
            normalizer += _independent_unequal_q(base, combo_set, nodes)
    if normalizer == 0:
        return Fraction(0)
    return _independent_unequal_q(base, treated, nodes) / normalizer


def _independent_q(study: NetworkStudyContextV17, z: tuple[int, ...]) -> Fraction:
    """Independent full-vector design check (not an invocation of AssignmentSpec)."""
    design = study.design()
    if design is None or len(z) != len(study.node_order):
        raise R1bPolicyUnavailable('EXPERIMENTAL_ASSIGNMENT_LAW_UNRESOLVED')
    if isinstance(design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
        treated = frozenset(n for n, t in zip(study.node_order, z) if t)
        if isinstance(design, UnequalProbabilityFixedQuotaDesignV1):
            return _independent_unequal_q(design, treated, study.node_order)
        return _independent_rerandomized_q(design, treated, study.node_order)
    if isinstance(design, ClusterBernoulliDesignV24):
        assignments=dict(zip(study.node_order,z))
        mass=Fraction(1)
        for cluster,p_string in zip(design.clusters,design.cluster_probabilities):
            vals={assignments[node] for node in cluster}
            if len(vals)!=1:
                return Fraction(0)
            p=Fraction(p_string)
            mass *= p if next(iter(vals)) else 1-p
        return mass
    if isinstance(design, HeterogeneousBernoulliDesignV1):
        mass = Fraction(1)
        for node, treatment in zip(study.node_order, z):
            p = Fraction(design.propensities[node])
            mass *= p if treatment else 1-p
        return mass
    if isinstance(design, CompleteRandomizationDesignV1):
        return Fraction(1, comb(len(z),design.m)) if sum(z)==design.m else Fraction(0)
    if isinstance(design, TwoStageQuotaMixtureDesignV27):
        return original_assignment_mass(study.node_order,design,z)
    if isinstance(design, MultiGroupFixedQuotaDesignV25):
        tr=dict(zip(study.node_order,z))
        if any(sum(tr[node] for node in group)!=quota
               for group,quota in zip(design.groups,design.treated_quotas)):
            return Fraction(0)
        denominator=1
        for group,quota in zip(design.groups,design.treated_quotas):
            denominator*=comb(len(group),quota)
        return Fraction(1,denominator)
    if isinstance(design, TwoGroupFixedQuotaDesignV1):
        tr = dict(zip(study.node_order,z))
        if any(sum(tr[node] for node in group)!=m for group,m in zip(
                design.groups,design.treated_quotas)):
            return Fraction(0)
        return Fraction(1, comb(len(design.groups[0]),design.treated_quotas[0])
                        * comb(len(design.groups[1]),design.treated_quotas[1]))
    raise R1bPolicyUnavailable('UNSUPPORTED_ASSIGNMENT_DESIGN')


def _policy_formula(target: TargetSemanticsV15, nodes: tuple[str, ...]) -> str:
    """A symbolic observable formula, never a numerically estimated outcome."""
    terms = []
    z = '(' + ','.join(map(str,target.policy_assignment)) + ')'
    for node,weight in zip(nodes,target.unit_weights):
        w = Fraction(weight)
        if w:
            terms.append(f'{w} * E[Y_{{{node}}}^obs | W={target.context}, T_vector={z}]')
    return ' + '.join(terms)


@dataclass(frozen=True)
class VerifiedFixedPolicyV19:
    """Replayable theorem result; signed digests attest consistency, not external truth."""
    study: NetworkStudyContextV17
    target: TargetSemanticsV15
    sources: tuple[NetworkA4SourceV17, ...]
    assumptions: tuple[Assumption, ...]
    route_receipt: NonArmRouteAssessmentV17
    selected_a4_source_id: str
    selected_a4_source_digest: str
    a4_rule_id: str
    assignment_probability: str
    weighted_nodes: tuple[str, ...]
    node_weights: tuple[str, ...]
    required_observables: tuple[str, ...]
    identified_functional: str
    target_fingerprint: str
    theorem_id: str
    certificate_sha256: str
    version: str = VERSION
    status: Literal['POINT'] = 'POINT'
    verification_status: Literal['VERIFIED'] = 'VERIFIED'
    estimation_request: None = None

    def summary(self) -> dict:
        return {
            'route': self.theorem_id,
            'status': self.status,
            'verification_status': self.verification_status,
            'target_kind': self.target.kind,
            'target_fingerprint': self.target_fingerprint,
            'study_digest': self.study.study_digest,
            'protocol_digest': self.study.protocol_digest,
            'fixed_policy_treatment': list(self.target.policy_assignment),
            'assignment_probability': self.assignment_probability,
            'nonzero_node_weights': dict(zip(self.weighted_nodes,self.node_weights)),
            'required_observables': list(self.required_observables),
            'a4_source_id': self.selected_a4_source_id,
            'a4_rule_id': self.a4_rule_id,
            'assumptions_used': sorted(set(a.name for a in self.assumptions if a.confirmed)),
            'identified_functional': self.identified_functional,
            'certificate_sha256': self.certificate_sha256,
            'estimation_request': None,
            'warning': 'POINT is a population identification result, not a finite-sample policy value estimate',
        }


def _result_payload(result: VerifiedFixedPolicyV19) -> dict:
    payload = asdict(result)
    payload.pop('certificate_sha256')
    return payload


def _solve(study: NetworkStudyContextV17, target: TargetSemanticsV15,
           sources: tuple[NetworkA4SourceV17, ...],
           assumptions: tuple[Assumption, ...]) -> VerifiedFixedPolicyV19:
    if not isinstance(study, NetworkStudyContextV17):
        raise TypeError('Use a typed NetworkStudyContextV17')
    if not isinstance(target, TargetSemanticsV15):
        raise TypeError('Use a reviewed typed TargetSemanticsV15')
    if not isinstance(sources, tuple) or not isinstance(assumptions, tuple):
        raise TypeError('Sources and assumptions must be immutable tuples')
    if isinstance(study.design(), TwoStageQuotaMixtureDesignV27):
        reason = profile_exclusion_reason(assumptions)
        if reason is not None:
            raise R1bPolicyUnavailable(reason)
    if study.graph_timing_claim != 'DECLARED_PRETREATMENT_FIXED':
        raise R1bPolicyUnavailable('NETWORK_PRETREATMENT_STATUS_UNRESOLVED')
    # Pydantic model_copy(update=...) can bypass validators. Revalidate the
    # *serialized* assumption records and reject any inconsistent status/flag
    # before their claims can authorize a population causal theorem.
    for a in assumptions:
        if not isinstance(a,Assumption):
            raise TypeError('Expected reviewed typed Assumption records')
        try:
            revalidated=Assumption.model_validate(a.model_dump(mode='json'))
        except (ValueError,TypeError) as exc:
            raise R1bPolicyUnavailable('INVALID_ASSUMPTION_RECORD') from exc
        if revalidated.model_dump(mode='json')!=a.model_dump(mode='json'):
            raise R1bPolicyUnavailable('ASSUMPTION_STATUS_INCONSISTENT')

    route = assess_nonarm_network_inquiry(
        study,target,sources,family_id=FIXED_POLICY_CANDIDATE,
        assumptions=assumptions)
    # Reconstruct the v1.7 route receipt from the original supplied source &
    # assumption declarations; this does NOT upgrade a shadow receipt to proof.
    replay_nonarm_network_inquiry(study,target,sources,route,assumptions=assumptions)
    if (route.route_status != 'THEOREM_BACKEND_UNAVAILABLE'
            or route.target_match!='MATCHED'
            or route.information_status!='SATISFIED'
            or route.assumption_status!='ADMITTED'
            or route.validity_status!='POSITIVE_UNDER_DECLARED_Q'):
        raise R1bPolicyUnavailable(route.route_status, ','.join(route.blockers))
    if not route.required_observable or route.required_observable.operator != 'NODE_ASSIGNMENT_MEANS_FOR_POLICY':
        raise R1bPolicyUnavailable('REQUIRED_OBSERVABLE_CONTRACT_INVALID')
    if study.observation_regime!='experimental' or study.design() is None:
        raise R1bPolicyUnavailable('EXPERIMENTAL_RANDOMIZED_STUDY_REQUIRED')

    independent = _independent_q(study,target.policy_assignment)
    assignment = dict(zip(study.node_order,target.policy_assignment))
    q = AssignmentSpec(study.design()).full_assignment_probability(study.network(),assignment)
    if q != independent or str(q)!=route.policy_assignment_probability:
        raise R1bPolicyUnavailable('INDEPENDENT_ASSIGNMENT_SUPPORT_MISMATCH')
    if not q:
        raise R1bPolicyUnavailable('OFF_SUPPORT_ALTERNATE_THEOREM')

    accepted_sources = []
    by_id={s.source_id:s for s in sources}
    for checked in route.source_results:
        if (checked.information_status=='SATISFIED'
            and checked.rule_id in VALID_A4_RULES
            and checked.source_id in by_id
            and checked.source_digest==_sha(asdict(by_id[checked.source_id]))):
            accepted_sources.append((checked.source_id,checked.source_digest,checked.rule_id))
    if not accepted_sources:
        raise R1bPolicyUnavailable('NO_VERIFIED_ASSIGNMENT_LEVEL_OBSERVABLE')
    chosen=sorted(accepted_sources)[0]  # deterministic evidence selection
    nodes=tuple(node for node,w in zip(study.node_order,target.unit_weights) if Fraction(w)>0)
    weights=tuple(str(Fraction(w)) for w in target.unit_weights if Fraction(w)>0)
    z='(' + ','.join(map(str,target.policy_assignment)) + ')'
    observables=tuple(f'E[Y_{{{node}}}^obs | W={target.context}, T_vector={z}]'
                      for node in nodes)
    result=VerifiedFixedPolicyV19(
        study=study,target=target,sources=sources,assumptions=assumptions,
        route_receipt=route,selected_a4_source_id=chosen[0],
        selected_a4_source_digest=chosen[1],a4_rule_id=chosen[2],
        assignment_probability=str(q),weighted_nodes=nodes,node_weights=weights,
        required_observables=observables,identified_functional=_policy_formula(target,study.node_order),
        target_fingerprint=_sha({'version':'r1b-target-semantics-v1.9',
            'canonical_target':target.target_digest,
            'intervention_variable':study.treatment_variable}),theorem_id=THEOREM_ID,
        certificate_sha256='',
    )
    return VerifiedFixedPolicyV19(**{**result.__dict__,
        'certificate_sha256':_sha(_result_payload(result))})


def identify_verified_fixed_policy(study: NetworkStudyContextV17,
                                   target: TargetSemanticsV15,
                                   sources: tuple[NetworkA4SourceV17, ...], *,
                                   assumptions: tuple[Assumption, ...]) -> VerifiedFixedPolicyV19:
    """POINT only after independent q check and A4/A5/A6 reviewed gates."""
    result=_solve(study,target,sources,assumptions)
    replay_verified_fixed_policy(result)
    return result


def replay_verified_fixed_policy(saved: VerifiedFixedPolicyV19) -> bool:
    """Independently reconstruct from typed inputs and re-check all stored fields."""
    if not isinstance(saved, VerifiedFixedPolicyV19):
        raise TypeError('A verified R1b result is required')
    if _sha(_result_payload(saved))!=saved.certificate_sha256:
        raise R1bPolicyUnavailable('POLICY_CERTIFICATE_DIGEST_MISMATCH')
    fresh=_solve(saved.study,saved.target,saved.sources,saved.assumptions)
    if fresh != saved:
        raise R1bPolicyUnavailable('POLICY_CERTIFICATE_REPLAY_MISMATCH')
    return True


# A finite-support randomized policy is a *composition* of supported fixed
# policies. This is not a general kernel engine and is not an R2 extrapolation.
# In particular, each constituent z must have its own verified assignment cell.

@dataclass(frozen=True)
class VerifiedFinitePolicyMixtureV19:
    """A finite stochastic intervention r=sum_k alpha_k delta_(z_k), alpha>0."""
    components: tuple[VerifiedFixedPolicyV19, ...]
    policy_probabilities: tuple[str, ...]
    target_fingerprint: str
    identified_functional: str
    certificate_sha256: str
    theorem_id: str = 'R1B_FINITE_SUPPORT_STOCHASTIC_POLICY_POINT_V1'
    version: str = VERSION
    status: Literal['POINT'] = 'POINT'
    verification_status: Literal['VERIFIED'] = 'VERIFIED'
    estimation_request: None = None

    def summary(self) -> dict:
        return {
            'theorem_id': self.theorem_id,
            'status': self.status,
            'verification_status': self.verification_status,
            'target_fingerprint': self.target_fingerprint,
            'policy_support': [
                {'assignment':list(c.target.policy_assignment),
                 'policy_probability':p,
                 'experimental_assignment_probability':c.assignment_probability,
                 'fixed_policy_certificate':c.certificate_sha256}
                for c,p in zip(self.components,self.policy_probabilities)],
            'identified_functional':self.identified_functional,
            'certificate_sha256':self.certificate_sha256,
            'estimation_request':None,
            'warning':'Finite mixture of full-assignment population means; no PFN value is estimated',
        }


def _mixture_payload(result: VerifiedFinitePolicyMixtureV19) -> dict:
    payload=asdict(result)
    payload.pop('certificate_sha256')
    return payload


def _build_finite_mixture(
    components: tuple[VerifiedFixedPolicyV19, ...],
    weights: tuple[int | Fraction | str, ...],
) -> VerifiedFinitePolicyMixtureV19:
    if not isinstance(components,tuple) or not components or len(components)>64:
        raise R1bPolicyUnavailable('FINITE_POLICY_ATOM_COUNT_INVALID')
    if not isinstance(weights,tuple) or len(weights)!=len(components):
        raise R1bPolicyUnavailable('FINITE_POLICY_WEIGHT_SHAPE_INVALID')
    prob=[]
    for value in weights:
        if type(value) not in (str,int,Fraction):
            raise R1bPolicyUnavailable('POLICY_PROBABILITIES_MUST_BE_EXACT')
        try:
            p=Fraction(value)
        except (ValueError,ZeroDivisionError,TypeError,OverflowError) as exc:
            raise R1bPolicyUnavailable('INVALID_POLICY_PROBABILITY') from exc
        if p<=0:
            raise R1bPolicyUnavailable('POLICY_PROBABILITY_MUST_BE_POSITIVE')
        prob.append(p)
    if sum(prob)!=1:
        raise R1bPolicyUnavailable('POLICY_PROBABILITIES_NOT_NORMALIZED')

    first=components[0]
    if not isinstance(first,VerifiedFixedPolicyV19):
        raise TypeError('Use fully verified fixed policy components')
    coords=set()
    pieces=[]
    for c,p in zip(components,prob):
        if not isinstance(c,VerifiedFixedPolicyV19):
            raise TypeError('Use fully verified fixed policy components')
        replay_verified_fixed_policy(c)
        if (c.study!=first.study or c.study.protocol_digest!=first.study.protocol_digest
            or c.target.unit_weights!=first.target.unit_weights
            or c.target.averaging_scope!=first.target.averaging_scope):
            raise R1bPolicyUnavailable('POLICY_COMPONENT_STUDY_OR_TARGET_MISMATCH')
        if c.target.policy_assignment in coords:
            raise R1bPolicyUnavailable('DUPLICATE_FULL_POLICY_ATOM')
        coords.add(c.target.policy_assignment)
        pieces.append((c.target.policy_assignment,c,p))
    pieces.sort(key=lambda item:item[0])
    ordered=tuple(c for _,c,_ in pieces)
    probabilities=tuple(str(p) for _,_,p in pieces)
    scientific={
        'version':'r1b-finite-policy-target-v1.9',
        'scope':first.study.shared_scope_digest,
        'treatment_variable':first.study.treatment_variable,
        'outcome':first.study.outcome_variable,
        'W':first.study.context_reference,
        'node_weights':first.target.unit_weights,
        'policy_atoms':[(list(z),str(p)) for z,_,p in pieces],
    }
    # An observable linear combination of independently verified fixed-policy
    # formulas. It retains the exact policy probabilities as rational numbers.
    formula=' + '.join(f'{p} * ({c.identified_functional})' for _,c,p in pieces)
    result=VerifiedFinitePolicyMixtureV19(
        components=ordered,policy_probabilities=probabilities,
        target_fingerprint=_sha(scientific),identified_functional=formula,
        certificate_sha256='',
    )
    return VerifiedFinitePolicyMixtureV19(**{
        **result.__dict__,'certificate_sha256':_sha(_mixture_payload(result))})


def identify_verified_finite_policy_mixture(
    components: tuple[VerifiedFixedPolicyV19, ...],
    *, policy_probabilities: tuple[int | Fraction | str, ...],
) -> VerifiedFinitePolicyMixtureV19:
    """Verify a finite *stochastic* policy by composing R1b fixed POINT results.

    No enumeration of all q-supported assignments; only explicitly listed
    policy atoms are used. Each must have q(z)>0 and assignment-level A4 info.
    """
    result=_build_finite_mixture(components,policy_probabilities)
    replay_verified_finite_policy_mixture(result)
    return result


def replay_verified_finite_policy_mixture(saved: VerifiedFinitePolicyMixtureV19) -> bool:
    if not isinstance(saved,VerifiedFinitePolicyMixtureV19):
        raise TypeError('Expected an R1b finite-policy result')
    if saved.certificate_sha256!=_sha(_mixture_payload(saved)):
        raise R1bPolicyUnavailable('FINITE_POLICY_CERTIFICATE_DIGEST_MISMATCH')
    fresh=_build_finite_mixture(saved.components,saved.policy_probabilities)
    if saved!=fresh:
        raise R1bPolicyUnavailable('FINITE_POLICY_CERTIFICATE_REPLAY_MISMATCH')
    return True


__all__.extend([
    'VerifiedFinitePolicyMixtureV19',
    'identify_verified_finite_policy_mixture',
    'replay_verified_finite_policy_mixture',
])
