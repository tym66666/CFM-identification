"""R2 v2.0: reviewed MEAN signature-sufficiency -> fixed-network policy POINT.

For each policy-weighted node, assume explicitly (not deduce from the exposure
rule!) that E[Y_i(z)|W]=h_i(z_i,g_i(z),W) for ALL binary full assignments z.
Under a known fully randomized assignment q, consistency, finite first moments,
positive support for each policy node's (z_i,g_i(z)) class, and adequate A4
population arm means, V(z) is identified as a weighted sum of observed
node/signature conditional means. q(z) may be zero. This is not a partial-ID
solver, finite-sample policy evaluator, or causal assumption discovery tool.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from fractions import Fraction
from math import comb
from typing import Literal

from ._internal.identification.schemas import (
    Assumption, AssumptionStatus, CompleteRandomizationDesignV1,
    TwoGroupFixedQuotaDesignV1, MultiGroupFixedQuotaDesignV25, HeterogeneousBernoulliDesignV1, ClusterBernoulliDesignV24, TwoStageQuotaMixtureDesignV27,
)
from ._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine
from ._internal.identification.randomized_arm_family.two_stage_verifier import independent_joint_support as _verify_d6_joint_support
from ._internal.identification.randomized_arm_family.two_stage_a5 import profile_exclusion_reason
from ._internal.identification.randomized_arm_family.assignment import neighbor_set
from ._internal.identification.randomized_network_arm import (
    REQUIRED, MAX_N, MAX_DEGREE, MAX_TWO_GROUP_CONVOLUTION_CELLS, MAX_BERNOULLI_DP_CELLS,
    _verify_joint_support_independently, _verify_two_group_joint_support_independently,
    _verify_heterogeneous_joint_support_independently, _verify_multi_group_joint_support_independently, _verifier_matches_exposure,
)
from ._internal.identification.randomized_arm_family.cluster_verifier import verify_cluster_joint_support
from .identification_a4_shadow import _sha
from .identification_route_shadow import TargetSemanticsV15
from .network_inquiry_shadow import NetworkStudyContextV17

VERSION = 'r2-mean-signature-sufficient-fixed-policy-point-v2.0'
THEOREM_ID = 'R2_RANDOMIZED_MEAN_SIGNATURE_SUFFICIENCY_POLICY_POINT_V1'
APPROVED = {AssumptionStatus.CERTIFIED, AssumptionStatus.ADMITTED, AssumptionStatus.DERIVED}
SUPPORTED_SOURCE_OPS = {'NODE_SIGNATURE_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW'}

__all__ = [
    'R2PolicyUnavailable','SignatureSpecV20','MeanSignatureSufficiencyV20',
    'SignaturePopulationSourceV20','VerifiedSignaturePolicyV20',
    'declare_policy_signature','admit_mean_signature_sufficiency',
    'declare_signature_population_source','identify_verified_signature_policy',
    'replay_verified_signature_policy',
]


class R2PolicyUnavailable(ValueError):
    """A route/capability problem; does not assert mathematical non-identification."""
    def __init__(self, reason_code: str, detail: str = ''):
        self.reason_code = reason_code
        super().__init__(reason_code + (': '+detail if detail else ''))


def _valid_model(record: Assumption) -> Assumption:
    if not isinstance(record, Assumption):
        raise R2PolicyUnavailable('INVALID_ASSUMPTION_RECORD')
    try:
        copy = Assumption.model_validate(record.model_dump(mode='json'))
    except (ValueError, TypeError) as exc:
        raise R2PolicyUnavailable('INVALID_ASSUMPTION_RECORD') from exc
    if copy.model_dump(mode='json') != record.model_dump(mode='json'):
        raise R2PolicyUnavailable('INVALID_ASSUMPTION_RECORD')
    return copy


def _validate_randomization(assumptions: tuple[Assumption, ...]) -> None:
    if not isinstance(assumptions, tuple):
        raise R2PolicyUnavailable('TYPED_ASSUMPTION_TUPLE_REQUIRED')
    by_name = {}
    for item in assumptions:
        item = _valid_model(item)
        if item.name == 'mean_signature_sufficiency':
            raise R2PolicyUnavailable('SUFFICIENCY_MUST_USE_SCOPED_A5_CLAIM')
        if item.name in by_name and item.model_dump(mode='json') != by_name[item.name].model_dump(mode='json'):
            raise R2PolicyUnavailable('CONFLICTING_ASSUMPTIONS',item.name)
        by_name[item.name] = item
    rejected = [name for name in REQUIRED if name in by_name and
                by_name[name].status in {AssumptionStatus.NOT_ADMITTED, AssumptionStatus.CONTRADICTED}]
    if rejected:
        raise R2PolicyUnavailable('ASSUMPTIONS_NOT_ADMITTED',','.join(rejected))
    missing = [name for name in REQUIRED if name not in by_name or by_name[name].status not in APPROVED]
    if missing:
        raise R2PolicyUnavailable('NEEDS_INPUT',','.join(missing))


def _nonblank(s: str) -> bool:
    return isinstance(s,str) and bool(s.strip())


@dataclass(frozen=True)
class SignatureSpecV20:
    """A known grouping g, not by itself a sufficient causal exposure model."""
    study_scope_digest: str
    network_fingerprint: str
    treatment_variable: str
    grouping: Literal[
        'strict_majority_ties_low','three_level_treated_neighbor_fraction',
        'pretreatment_core_collaborator_majority',
        'exact_treated_neighbor_count', 'any_treated_neighbor',
    ]
    core_collaborators: tuple[tuple[str,tuple[str,...]], ...] = ()
    signature_fingerprint: str = ''

    def __post_init__(self):
        if not all(_nonblank(x) for x in (self.study_scope_digest,self.network_fingerprint,self.treatment_variable)):
            raise ValueError('Signature must bind a reviewed network study and treatment')
        if self.grouping not in ('strict_majority_ties_low','three_level_treated_neighbor_fraction',
                                 'pretreatment_core_collaborator_majority',
                                 'exact_treated_neighbor_count','any_treated_neighbor'):
            raise ValueError('Unknown E1/E2/E3/E4/E5 signature')
        if self.grouping == 'pretreatment_core_collaborator_majority':
            if not self.core_collaborators or any(not isinstance(x,tuple) or len(x)!=2
                       or not isinstance(x[1],tuple) for x in self.core_collaborators):
                raise ValueError('E3 needs complete typed pretreatment core map')
        elif self.core_collaborators:
            raise ValueError('Only E3 may specify core collaborators')
        expected = _sha({'version':'network-signature-v2.0','study_scope':self.study_scope_digest,
                         'network':self.network_fingerprint,'treatment':self.treatment_variable,
                         'grouping':self.grouping,'core':self.core_collaborators})
        if self.signature_fingerprint and self.signature_fingerprint != expected:
            raise ValueError('Signature digest mismatch')
        object.__setattr__(self,'signature_fingerprint',expected)


def declare_policy_signature(study: NetworkStudyContextV17, *, grouping: str,
                             core_collaborators: dict[str,tuple[str,...]] | None = None) -> SignatureSpecV20:
    if not isinstance(study,NetworkStudyContextV17):
        raise TypeError('Reviewed NetworkStudyContextV17 required')
    net=study.network()
    if grouping=='pretreatment_core_collaborator_majority':
        if not isinstance(core_collaborators,dict) or set(core_collaborators)!=set(study.node_order):
            raise ValueError('E3 needs a core subset for EVERY study node')
        neighbors={node:neighbor_set(net,node) for node in study.node_order}
        for node,members in core_collaborators.items():
            if not isinstance(members,(tuple,list)) or not members or len(set(members))!=len(members):
                raise ValueError('Each E3 core must be nonempty and unique')
            if not set(members)<=neighbors[node]:
                raise ValueError('E3 cores must consist of actual neighbors')
        canonical=tuple((node,tuple(sorted(core_collaborators[node]))) for node in study.node_order)
    else:
        if core_collaborators is not None:
            raise ValueError('Only E3 may have core collaborators')
        canonical=()
    return SignatureSpecV20(study.shared_scope_digest,study.network_fingerprint,
                            study.treatment_variable,grouping,canonical)


@dataclass(frozen=True)
class MeanSignatureSufficiencyV20:
    """EXPLICIT additional A5 claim: mean-equivalence across ALL assignments."""
    study_scope_digest: str
    signature_fingerprint: str
    covered_nodes: tuple[str,...]
    assumption: Assumption

    def __post_init__(self):
        if (not self.covered_nodes or len(set(self.covered_nodes))!=len(self.covered_nodes)
                or not all(_nonblank(n) for n in self.covered_nodes)):
            raise ValueError('An explicit list of covered nodes is required')
        if not _nonblank(self.study_scope_digest) or not _nonblank(self.signature_fingerprint):
            raise ValueError('A5 scope and signature identity required')
        if not isinstance(self.assumption,Assumption) or self.assumption.name!='mean_signature_sufficiency':
            raise ValueError('The explicitly named mean-signature sufficiency assumption is required')


def admit_mean_signature_sufficiency(study: NetworkStudyContextV17,
                                     signature: SignatureSpecV20, *,
                                     assumption: Assumption,
                                     covered_nodes: tuple[str,...]) -> MeanSignatureSufficiencyV20:
    """Do not infer sufficiency from existence of an exposure grouping!"""
    return MeanSignatureSufficiencyV20(study.shared_scope_digest,signature.signature_fingerprint,
                                      tuple(covered_nodes),assumption)


@dataclass(frozen=True)
class SignaturePopulationSourceV20:
    """Explicit A4 observable; NODE_SIGNATURE_MEANS lists exact covered cells."""
    source_id: str
    operator: Literal['NODE_SIGNATURE_MEANS','NODE_FULL_LAW','FULL_JOINT_LAW']
    provenance: str
    admission: str
    availability: str
    study_scope_digest: str
    protocol_digest: str
    node_order: tuple[str,...]
    outcome: str
    context: str
    outcome_nodes: tuple[str,...]
    signature_fingerprint: str | None = None
    signature_cells: tuple[tuple[str,int,int], ...] = ()

    def __post_init__(self):
        if not all(_nonblank(x) for x in (self.source_id,self.provenance,self.study_scope_digest,
                                          self.protocol_digest,self.outcome,self.context)):
            raise ValueError('Explicit source identity and context required')
        if self.operator not in SUPPORTED_SOURCE_OPS:
            raise ValueError('Unsupported A4 operator')
        if (not isinstance(self.node_order,tuple) or not isinstance(self.outcome_nodes,tuple)
            or len(set(self.node_order))!=len(self.node_order)
            or not self.node_order or len(set(self.outcome_nodes))!=len(self.outcome_nodes)
            or not self.outcome_nodes or not set(self.outcome_nodes)<=set(self.node_order)):
            raise ValueError('Invalid ordered A4 node coordinates')
        if self.admission not in {'ADMITTED','CERTIFIED','PROPOSED','UNRESOLVED','CONTRADICTED','NOT_ADMITTED'}:
            raise ValueError('Unknown provenance status')
        if self.availability not in {'SYMBOLIC_POPULATION_OPERATOR','EXACT_POPULATION_VALUE','FINITE_SAMPLE_ESTIMATE'}:
            raise ValueError('Unknown population information availability')
        if self.operator=='NODE_SIGNATURE_MEANS':
            if (not _nonblank(self.signature_fingerprint) or not self.signature_cells
                or len(set(self.signature_cells))!=len(self.signature_cells)
                or any(not isinstance(c,tuple) or len(c)!=3 or c[0] not in self.outcome_nodes
                       or type(c[1]) is not int or c[1] not in (0,1)
                       or type(c[2]) is not int or c[2]<0 for c in self.signature_cells)):
                raise ValueError('Exact signature arm coordinates and digest are required')
        elif self.signature_fingerprint is not None or self.signature_cells:
            raise ValueError('Full law sources do not rely on a particular signature')


def declare_signature_population_source(study: NetworkStudyContextV17,
                                        signature: SignatureSpecV20, *, source_id: str,
                                        operator: str, outcome_nodes: tuple[str,...],
                                        admission: str, availability: str,
                                        provenance: str, signature_cells=()) -> SignaturePopulationSourceV20:
    return SignaturePopulationSourceV20(
        source_id=source_id, operator=operator, provenance=provenance,
        admission=admission, availability=availability,
        study_scope_digest=study.shared_scope_digest,protocol_digest=study.protocol_digest,
        node_order=study.node_order, outcome=study.outcome_variable,
        context=study.context_reference,outcome_nodes=tuple(outcome_nodes),
        signature_fingerprint=signature.signature_fingerprint if operator=='NODE_SIGNATURE_MEANS' else None,
        signature_cells=tuple(tuple(c) for c in signature_cells))


@dataclass(frozen=True)
class VerifiedSignaturePolicyV20:
    study: NetworkStudyContextV17
    target: TargetSemanticsV15
    signature: SignatureSpecV20
    sufficiency: MeanSignatureSufficiencyV20
    sources: tuple[SignaturePopulationSourceV20,...]
    assumptions: tuple[Assumption,...]
    a4_selected_id: str
    a4_selected_digest: str
    a4_rule_id: str
    policy_assignment_probability: str
    policy_node_classes: tuple[tuple[str,int,int], ...]
    node_class_support: tuple[str,...]
    node_weights: tuple[str,...]
    identified_functional: str
    required_observables: tuple[str,...]
    target_fingerprint: str
    theorem_id: str
    certificate_sha256: str
    version: str = VERSION
    status: Literal['POINT'] = 'POINT'
    verification_status: Literal['VERIFIED'] = 'VERIFIED'
    estimation_request: None = None

    def summary(self) -> dict:
        return {
            'route':'R2','theorem_id':self.theorem_id,'status':self.status,
            'verification_status':self.verification_status,
            'target_fingerprint':self.target_fingerprint,
            'study_digest':self.study.study_digest,
            'signature':self.signature.grouping,
            'signature_fingerprint':self.signature.signature_fingerprint,
            'full_assignment_probability':self.policy_assignment_probability,
            'policy_assignment':list(self.target.policy_assignment),
            'node_classes':[{'node':n,'treatment':a,'signature':s,
                             'joint_support':pi,'weight':w}
                            for (n,a,s),pi,w in zip(self.policy_node_classes,
                                                    self.node_class_support,self.node_weights)],
            'required_observables':list(self.required_observables),
            'identified_functional':self.identified_functional,
            'a4_source_id':self.a4_selected_id,'a4_rule_id':self.a4_rule_id,
            'assumptions_used':sorted(set([a.name for a in self.assumptions if a.confirmed]
                                           + ['mean_signature_sufficiency'])),
            'certificate_sha256':self.certificate_sha256,'estimation_request':None,
            'warning':'Population POINT conditional on reviewed mean-signature sufficiency; not numeric policy welfare',
        }


def _payload(result: VerifiedSignaturePolicyV20) -> dict:
    obj=asdict(result)
    obj.pop('certificate_sha256')
    return obj


def _normalized_inputs(study, target, signature, sufficiency, sources, assumptions):
    # Rebuild all typed declarations to detect invalid state introduced by
    # object.__setattr__ or other mutation outside ordinary constructors.
    if not isinstance(study,NetworkStudyContextV17) or not isinstance(target,TargetSemanticsV15):
        raise R2PolicyUnavailable('TYPED_STUDY_AND_TARGET_REQUIRED')
    if not isinstance(signature,SignatureSpecV20) or not isinstance(sufficiency,MeanSignatureSufficiencyV20):
        raise R2PolicyUnavailable('TYPED_SIGNATURE_AND_A5_CLAIM_REQUIRED')
    if not isinstance(sources,tuple) or any(not isinstance(src,SignaturePopulationSourceV20) for src in sources):
        raise R2PolicyUnavailable('TYPED_A4_SOURCES_REQUIRED')
    if not isinstance(assumptions,tuple):
        raise R2PolicyUnavailable('TYPED_ASSUMPTIONS_REQUIRED')
    try:
        st=NetworkStudyContextV17(**asdict(study))
        tgt=TargetSemanticsV15(**asdict(target))
        sig=SignatureSpecV20(**asdict(signature))
        suf=MeanSignatureSufficiencyV20(**asdict(sufficiency))
        srcs=tuple(SignaturePopulationSourceV20(**asdict(src)) for src in sources)
    except (ValueError,TypeError,KeyError) as exc:
        raise R2PolicyUnavailable('NONCANONICAL_TYPED_INPUT') from exc
    if (st!=study or tgt!=target or sig!=signature or suf!=sufficiency or srcs!=sources):
        raise R2PolicyUnavailable('NONCANONICAL_TYPED_INPUT')
    _validate_randomization(assumptions)
    if isinstance(st.design(), TwoStageQuotaMixtureDesignV27):
        reason = profile_exclusion_reason(assumptions)
        if reason is not None:
            raise R2PolicyUnavailable(reason)
    return st,tgt,sig,suf,srcs


def _validate_study_target(study, target, signature, sufficiency):
    if study.observation_regime!='experimental' or study.design() is None:
        raise R2PolicyUnavailable('RANDOMIZED_EXPERIMENT_REQUIRED')
    if study.graph_timing_claim!='DECLARED_PRETREATMENT_FIXED':
        raise R2PolicyUnavailable('NETWORK_PRETREATMENT_STATUS_UNRESOLVED')
    if (target.kind!='FIXED_FULL_ASSIGNMENT_POLICY_MEAN'
        or target.network_fingerprint!=study.network_fingerprint
        or target.node_order!=study.node_order or target.outcome!=study.outcome_variable
        or target.context!=study.context_reference):
        raise R2PolicyUnavailable('TARGET_STUDY_SCOPE_MISMATCH')
    if target.authority not in {'HUMAN_CONFIRMED','TRUSTED_FIXTURE'} or target.query_resolution!='RESOLVED':
        raise R2PolicyUnavailable('NEEDS_INPUT','Target authority unresolved')
    if (signature.study_scope_digest!=study.shared_scope_digest
        or signature.network_fingerprint!=study.network_fingerprint
        or signature.treatment_variable!=study.treatment_variable):
        raise R2PolicyUnavailable('SIGNATURE_STUDY_MISMATCH')
    if (sufficiency.study_scope_digest!=study.shared_scope_digest
        or sufficiency.signature_fingerprint!=signature.signature_fingerprint):
        raise R2PolicyUnavailable('SUFFICIENCY_SIGNATURE_MISMATCH')
    claim=_valid_model(sufficiency.assumption)
    # Mean sufficiency is a substantive, generally untestable restriction.
    # It cannot be DERIVED from the randomized design or exposure definition.
    if (claim.status not in {AssumptionStatus.CERTIFIED, AssumptionStatus.ADMITTED}
        or not claim.confirmed
        or claim.source not in {'human_confirmation','domain_knowledge','demo_specification'}
        or not any(isinstance(e,str) and e.strip() for e in claim.evidence)):
        if claim.status in {AssumptionStatus.NOT_ADMITTED,AssumptionStatus.CONTRADICTED}:
            raise R2PolicyUnavailable('MEAN_SIGNATURE_SUFFICIENCY_NOT_ADMITTED')
        raise R2PolicyUnavailable('NEEDS_INPUT','Mean-signature sufficiency not confirmed')
    nodes={n for n,w in zip(study.node_order,target.unit_weights) if Fraction(w)>0}
    if not nodes <= set(sufficiency.covered_nodes) or not set(sufficiency.covered_nodes)<=set(study.node_order):
        raise R2PolicyUnavailable('SUFFICIENCY_NODE_COVERAGE_INCOMPLETE')
    if len(study.node_order)>MAX_N or max(study.network().degree_map().values())>MAX_DEGREE:
        raise R2PolicyUnavailable('NETWORK_OUTSIDE_CERTIFIED_SOFTWARE_DOMAIN')
    net=study.network()
    if signature.grouping=='pretreatment_core_collaborator_majority':
        if tuple(node for node,_ in signature.core_collaborators)!=study.node_order:
            raise R2PolicyUnavailable('E3_CORE_COORDINATES_MISMATCH')
        core=dict(signature.core_collaborators)
        try:
            exposure=ExposureSpec(signature.grouping,core)
            for node in study.node_order:
                exposure.reference_nodes(net,node)
        except (ValueError,TypeError,KeyError) as exc:
            raise R2PolicyUnavailable('INVALID_PRETREATMENT_CORE_MAP') from exc
    elif signature.grouping=='three_level_treated_neighbor_fraction':
        if any(net.degree_map()[n]==0 for n in nodes):
            raise R2PolicyUnavailable('UNDEFINED_EXPOSURE_FOR_POLICY_NODE')


def _independent_support(net, design, signature, node, a, s, reference):
    if isinstance(design,CompleteRandomizationDesignV1):
        degree=len(reference) if reference is not None else net.degree_map()[node]
        return _verify_joint_support_independently(len(net.node_ids),design.m,degree,a,s,
                                                    grouping=signature.grouping)
    if isinstance(design,TwoGroupFixedQuotaDesignV1):
        return _verify_two_group_joint_support_independently(net,design,node,a,s,
                            grouping=signature.grouping,reference_nodes=reference)
    if isinstance(design,TwoStageQuotaMixtureDesignV27):
        return _verify_d6_joint_support(net,design,node,a,s,signature.grouping,
            _verifier_matches_exposure,reference_nodes=reference)
    if isinstance(design,MultiGroupFixedQuotaDesignV25):
        return _verify_multi_group_joint_support_independently(
            net,design,node,a,s,grouping=signature.grouping,reference_nodes=reference)
    if isinstance(design,ClusterBernoulliDesignV24):
        return verify_cluster_joint_support(net,design,node,a,s,signature.grouping,
                        _verifier_matches_exposure,reference_nodes=reference)
    if isinstance(design,HeterogeneousBernoulliDesignV1):
        return _verify_heterogeneous_joint_support_independently(net,design,node,a,s,
                            grouping=signature.grouping,reference_nodes=reference)
    raise R2PolicyUnavailable('UNSUPPORTED_ASSIGNMENT_DESIGN')


def _validate_source(study, signature, source, cells):
    if (source.study_scope_digest!=study.shared_scope_digest
        or source.protocol_digest!=study.protocol_digest
        or source.node_order!=study.node_order
        or source.outcome!=study.outcome_variable or source.context!=study.context_reference):
        return None,'A4_STUDY_OR_PROTOCOL_MISMATCH'
    if source.admission not in {'ADMITTED','CERTIFIED'}:
        return None,'A4_SOURCE_NOT_ADMITTED'
    if source.availability not in {'SYMBOLIC_POPULATION_OPERATOR','EXACT_POPULATION_VALUE'}:
        return None,'A4_POPULATION_OPERATOR_REQUIRED'
    if any(node not in source.outcome_nodes for node,_,_ in cells):
        return None,'A4_WEIGHTED_OUTCOME_NODES_MISSING'
    if source.operator=='NODE_SIGNATURE_MEANS':
        degree_map=(dict((n,len(ref)) for n,ref in signature.core_collaborators)
                    if signature.grouping=='pretreatment_core_collaborator_majority'
                    else study.network().degree_map())
        if any(cell[2] not in ExposureSpec(signature.grouping, dict(signature.core_collaborators)
                                            if signature.core_collaborators else None).states_for_degree(degree_map[cell[0]])
               for cell in source.signature_cells):
            return None,'A4_INVALID_SIGNATURE_STATE'
        if source.signature_fingerprint!=signature.signature_fingerprint:
            return None,'A4_SIGNATURE_MISMATCH'
        if not set(cells)<=set(source.signature_cells):
            return None,'A4_NODE_CLASS_COVERAGE_INCOMPLETE'
        return 'A4_SELECT_EXACT_SIGNATURE_MEANS_V20',None
    if source.operator=='NODE_FULL_LAW':
        return 'A4_DERIVE_SIGNATURE_FROM_FULL_T_CONDITION_V20',None
    if source.operator=='FULL_JOINT_LAW':
        if set(source.outcome_nodes)!=set(study.node_order):
            return None,'A4_FULL_JOINT_REQUIRES_ALL_NODES'
        return 'A4_FULL_JOINT_MARGINALIZE_AND_CONDITION_V20',None
    return None,'A4_OPERATOR_NOT_SUPPORTED'


def _solve(study: NetworkStudyContextV17, target: TargetSemanticsV15,
           signature: SignatureSpecV20, sources: tuple[SignaturePopulationSourceV20,...],
           *, assumptions: tuple[Assumption,...],
           sufficiency: MeanSignatureSufficiencyV20) -> VerifiedSignaturePolicyV20:
    study,target,signature,sufficiency,sources = _normalized_inputs(
        study,target,signature,sufficiency,sources,assumptions)
    _validate_study_target(study,target,signature,sufficiency)
    net=study.network(); design=study.design(); assignment=AssignmentSpec(design)
    assignment._validate_network(net)
    core_map=dict(signature.core_collaborators) if signature.core_collaborators else None
    exposure=ExposureSpec(signature.grouping,core_map)
    policy=dict(zip(study.node_order,target.policy_assignment))
    q_full=assignment.full_assignment_probability(net,policy)
    node_classes=[]; masses=[]; weights=[]
    # With homogeneous independent Bernoulli p, every (a,g) arm has a
    # Binomial(degree,p) count law regardless of which neighbors are listed.
    # Certify each distinct (a,s,degree) by BOTH previous exact algorithms
    # plus a third closed-form binomial identity, then reuse that mathematical
    # equality for nodes with the same degree. This never applies to D1 with
    # heterogeneous p_i, D2, or D3.
    iid_p=(Fraction(next(iter(design.propensities.values())))
           if isinstance(design,HeterogeneousBernoulliDesignV1)
              and len(set(design.propensities.values()))==1 else None)
    iid_verified_cache={}
    for node,a,w in zip(study.node_order,target.policy_assignment,target.unit_weights):
        if not Fraction(w):
            continue
        reference=(frozenset(core_map[node]) if core_map is not None else None)
        degree=len(reference) if reference is not None else net.degree_map()[node]
        count=sum(policy[n] for n in (reference if reference is not None else neighbor_set(net,node)))
        try:
            s=exposure.classify(count,degree)
        except ValueError as exc:
            raise R2PolicyUnavailable('UNDEFINED_POLICY_SIGNATURE',node) from exc
        # Performance/software-domain budget: exact support polynomial, never 2^N.
        if isinstance(design,(HeterogeneousBernoulliDesignV1,ClusterBernoulliDesignV24)) and degree*(degree+1)//2>MAX_BERNOULLI_DP_CELLS:
            raise R2PolicyUnavailable('EXACT_SUPPORT_COMPUTE_BUDGET_EXCEEDED')
        if isinstance(design,TwoStageQuotaMixtureDesignV27):
            if len(design.quota_profiles)*degree*(degree+1)//2>2_000_000:
                raise R2PolicyUnavailable('EXACT_SUPPORT_COMPUTE_BUDGET_EXCEEDED')
        if isinstance(design,MultiGroupFixedQuotaDesignV25):
            if degree*(degree+1)//2>MAX_TWO_GROUP_CONVOLUTION_CELLS:
                raise R2PolicyUnavailable('EXACT_SUPPORT_COMPUTE_BUDGET_EXCEEDED')
        if isinstance(design,TwoGroupFixedQuotaDesignV1):
            counts=tuple(sum(u in (reference if reference is not None else neighbor_set(net,node))
                             for u in group) for group in design.groups)
            if (counts[0]+1)*(counts[1]+1)>MAX_TWO_GROUP_CONVOLUTION_CELLS:
                raise R2PolicyUnavailable('EXACT_SUPPORT_COMPUTE_BUDGET_EXCEEDED')
        key=(a,s,degree) if iid_p is not None else None
        if key is not None and key in iid_verified_cache:
            q_arm=iid_verified_cache[key]
        else:
            q_arm=SupportEngine.evaluate(network=net,assignment=assignment,exposure=exposure,
                    node_id=node,own_treatment_value=a,exposure_value=s).joint_probability
            q_independent=_independent_support(net,design,signature,node,a,s,reference)
            if q_arm!=q_independent:
                raise R2PolicyUnavailable('INDEPENDENT_SIGNATURE_SUPPORT_MISMATCH',node)
            if key is not None:
                own=iid_p if a else 1-iid_p
                direct=own*sum((Fraction(comb(degree,k))*iid_p**k*(1-iid_p)**(degree-k)
                      for k in range(degree+1) if exposure.classify(k,degree)==s),Fraction(0))
                if q_arm!=direct:
                    raise R2PolicyUnavailable('BINOMIAL_IID_SUPPORT_INCONSISTENT',node)
                iid_verified_cache[key]=q_arm
        if q_arm<=0:
            raise R2PolicyUnavailable('ZERO_POLICY_SIGNATURE_SUPPORT',f'{node} ({a},{s})')
        node_classes.append((node,a,s));masses.append(str(q_arm));weights.append(str(Fraction(w)))
    if not node_classes:
        raise R2PolicyUnavailable('EMPTY_WEIGHTED_POLICY')
    used=tuple(node_classes)
    accepted=[]; reasons=[]
    by_id={}
    for source in sources:
        if source.source_id in by_id and by_id[source.source_id]!=source:
            raise R2PolicyUnavailable('CONFLICTING_A4_SOURCE_ID',source.source_id)
        by_id[source.source_id]=source
    for source in sorted(by_id.values(),key=lambda s:s.source_id):
        rule,error=_validate_source(study,signature,source,used)
        if rule:
            accepted.append((source.source_id,_sha(asdict(source)),rule))
        else:
            reasons.append(error)
    if not accepted:
        raise R2PolicyUnavailable('A4_SIGNATURE_INFORMATION_INSUFFICIENT',','.join(sorted(set(reasons))))
    chosen=sorted(accepted)[0]
    objects=tuple(f'E[Y_{{{node}}}^obs | W={target.context}, T_{{{node}}}={a}, '
                  f'S_{{{node}}}^g={s}]' for node,a,s in used)
    formula=' + '.join(f'{w} * {term}' for w,term in zip(weights,objects))
    # Keep the exact R1b scientific identity for the SAME Q across two routes.
    identity=_sha({'version':'r1b-target-semantics-v1.9',
                   'canonical_target':target.target_digest,
                   'intervention_variable':study.treatment_variable})
    result=VerifiedSignaturePolicyV20(
        study=study,target=target,signature=signature,sufficiency=sufficiency,
        sources=sources,assumptions=assumptions,
        a4_selected_id=chosen[0],a4_selected_digest=chosen[1],a4_rule_id=chosen[2],
        policy_assignment_probability=str(q_full),policy_node_classes=used,
        node_class_support=tuple(masses),node_weights=tuple(weights),
        identified_functional=formula,required_observables=objects,
        target_fingerprint=identity,theorem_id=THEOREM_ID,certificate_sha256='')
    return replace(result,certificate_sha256=_sha(_payload(result)))


def identify_verified_signature_policy(study: NetworkStudyContextV17,
        target: TargetSemanticsV15, signature: SignatureSpecV20,
        sources: tuple[SignaturePopulationSourceV20,...], *,
        assumptions: tuple[Assumption,...],
        sufficiency: MeanSignatureSufficiencyV20) -> VerifiedSignaturePolicyV20:
    result=_solve(study,target,signature,sources,assumptions=assumptions,sufficiency=sufficiency)
    replay_verified_signature_policy(result)
    return result


def replay_verified_signature_policy(result: VerifiedSignaturePolicyV20) -> bool:
    if not isinstance(result,VerifiedSignaturePolicyV20):
        raise R2PolicyUnavailable('R2_RESULT_REQUIRED')
    if _sha(_payload(result))!=result.certificate_sha256:
        raise R2PolicyUnavailable('R2_CERTIFICATE_DIGEST_MISMATCH')
    fresh=_solve(result.study,result.target,result.signature,result.sources,
                 assumptions=result.assumptions,sufficiency=result.sufficiency)
    if fresh!=result:
        raise R2PolicyUnavailable('R2_CERTIFICATE_REPLAY_MISMATCH')
    return True
