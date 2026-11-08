"""v2.7 post-release P1: R3 p-standardized effects with factorized A4, not R3 policy.

Formal subdomain, conditional on fixed W=w and a known pre-treatment network:
  p_obs(T=t|W=w) = product_i r_i**t_i (1-r_i)**(1-t_i).
The factorization is an explicitly *admitted observational population law*, NOT
randomization, NOT proved by samples, and NOT exchangeability. Full-vector
conditional exchangeability, consistency, stable graph, finite moments must
still be separately admitted by R3's original A5 gate. A typed node-arm mean
operator must cover EVERY nonzero term. No exposure-sufficiency assumption.

Unlike v2.3/v2.6 finite enumeration, this source stores O(n) exact rational
probabilities and computes support by polynomial convolution. The verifier
reconstructs arithmetic support independently with a separate algorithm and
manual E1-E5 predicates. This verifies conditional mathematical consequences
of the declared A4 law; not its truth in the real world. No finite-sample
estimates, fixed-policy value, or estimator adapter are produced.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Literal

from .identification_a4_shadow import _sha
from .identification_composition import EffectQueryV18
from .identification_observational_effects import (
    THEOREM, ObservationalEffectProofV26, _canonical_terms,
)
from .identification_observational_r3 import (
    R3Unavailable, _validated_assumptions, _validated_exposure_signature,
    _manual_exposure_classify_v26,
)
from .identification_policy_r2 import SignatureSpecV20
from .network_inquiry_shadow import NetworkStudyContextV17
from ._internal.identification.schemas import Assumption
from ._internal.identification.randomized_arm_family.exposure import ExposureSpec

VERSION = 'r3-factorized-observational-a4-postrelease-p1'
OPERATOR = 'OBSERVATIONAL_NODE_ARM_POPULATION_CONDITIONAL_MEANS'
LAW_KIND = 'OBSERVATIONAL_CONDITIONAL_NODEWISE_BERNOULLI_FACTORIZATION'
ROUTE = 'R3_P_STANDARDIZED_EFFECTS'
MAX_NODE_COUNT = 2000  # engineering guard only; NOT a mathematical limit
MAX_REFERENCE_DEGREE = 600  # O(degree^2) exact arithmetic; never silently approximate


def _exact(value, *, probability: bool = False) -> Fraction:
    if type(value) is bool or isinstance(value, float) or not isinstance(value, (str, int, Fraction)):
        raise ValueError('EXACT_RATIONAL_NOT_FLOAT_REQUIRED')
    try:
        v = Fraction(value)
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError('INVALID_EXACT_RATIONAL') from exc
    if probability and not (0 <= v <= 1):
        raise ValueError('OBSERVATIONAL_NODE_PROBABILITY_OUTSIDE_UNIT_INTERVAL')
    return v


@dataclass(frozen=True)
class ObservationalFactorizedArmPopulationV27P1:
    """Typed A4: one admitted *observational* law and arm-mean operators.

    Each (node,a,s) in covered_arms declares availability of the symbolic
    population conditional mean under the one signature and one observed law.
    It does not claim a numerical conditional outcome or an empirical estimate.
    Node-wise treatment independence given W is an explicit *A4 scientific
    model claim*. R3's A5 exchangeability remains separately indispensable.
    """
    source_id: str
    provenance: str
    admission: Literal['ADMITTED','CERTIFIED','PROPOSED','UNRESOLVED']
    availability: Literal['SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE_ESTIMATE']
    study_scope_digest: str
    protocol_digest: str
    node_order: tuple[str,...]
    outcome: str
    context: str
    signature_fingerprint: str
    treatment_one_probabilities: tuple[str,...]
    covered_arms: tuple[tuple[str,int,int],...]
    factorization_kind: str = LAW_KIND
    operator: str = OPERATOR

    def __post_init__(self):
        if any(not isinstance(x,str) or not x.strip() for x in (
            self.source_id,self.provenance,self.study_scope_digest,self.protocol_digest,
            self.outcome,self.context,self.signature_fingerprint)):
            raise ValueError('A4_FACTOR_SOURCE_PROVENANCE_AND_COORDINATES_REQUIRED')
        if not isinstance(self.node_order,tuple) or not self.node_order or len(self.node_order)>MAX_NODE_COUNT or len(set(self.node_order))!=len(self.node_order) or any(type(n) is not str or not n.strip() for n in self.node_order):
            raise ValueError('A4_FACTOR_INVALID_NODE_COORDINATES_OR_RESOURCE_LIMIT')
        if (not isinstance(self.treatment_one_probabilities,tuple)
            or len(self.treatment_one_probabilities)!=len(self.node_order)):
            raise ValueError('A4_FACTOR_COMPLETE_NODE_PROBABILITIES_REQUIRED')
        for p in self.treatment_one_probabilities:
            if not isinstance(p,str) or p!=str(_exact(p,probability=True)):
                raise ValueError('A4_FACTOR_CANONICAL_EXACT_NODE_PROBABILITY_REQUIRED')
        if self.factorization_kind != LAW_KIND or self.operator != OPERATOR:
            raise ValueError('A4_FACTOR_OPERATOR_OR_LAW_KIND_INVALID')
        if self.admission not in ('ADMITTED','CERTIFIED','PROPOSED','UNRESOLVED'):
            raise ValueError('A4_FACTOR_INVALID_ADMISSION')
        if self.availability not in ('SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE_ESTIMATE'):
            raise ValueError('A4_FACTOR_INVALID_AVAILABILITY')
        if not isinstance(self.covered_arms,tuple):
            raise ValueError('A4_FACTOR_IMMUTABLE_ARM_COVERAGE_REQUIRED')
        pos={n:k for k,n in enumerate(self.node_order)}
        prev=None
        for arm in self.covered_arms:
            if (not isinstance(arm,tuple) or len(arm)!=3 or arm[0] not in pos
                or type(arm[1]) is not int or arm[1] not in (0,1)
                or type(arm[2]) is not int or arm[2]<0):
                raise ValueError('A4_FACTOR_INVALID_ARM_COORDINATES')
            key=(pos[arm[0]],arm[1],arm[2])
            if prev is not None and key<=prev:
                raise ValueError('A4_FACTOR_ARMS_MUST_BE_UNIQUE_IN_NODE_ORDER')
            prev=key

    @property
    def observational_law_fingerprint(self) -> str:
        return _sha(dict(version='R3_OBSERVATIONAL_FACTORIZED_LAW_V1',
            scope=self.study_scope_digest,protocol=self.protocol_digest,
            node_order=self.node_order,p1=self.treatment_one_probabilities))


def declare_observational_factorized_arm_population_v27p1(
        study:NetworkStudyContextV17,signature:SignatureSpecV20,*,
        source_id:str,provenance:str,treatment_one_probabilities,
        covered_arms,admission:str='ADMITTED',
        availability:str='SYMBOLIC_POPULATION_OPERATOR') -> ObservationalFactorizedArmPopulationV27P1:
    """Construct typed symbolic population information, NEVER estimate it from data."""
    if not isinstance(study,NetworkStudyContextV17) or study.observation_regime!='observational' or study.design() is not None:
        raise ValueError('OBSERVATIONAL_STUDY_REQUIRED')
    if not isinstance(signature,SignatureSpecV20) or signature.study_scope_digest!=study.shared_scope_digest:
        raise ValueError('A4_FACTOR_SIGNATURE_STUDY_MISMATCH')
    if isinstance(treatment_one_probabilities,dict):
        if set(treatment_one_probabilities)!=set(study.node_order):
            raise ValueError('A4_FACTOR_ALL_NODES_REQUIRED')
        ps=[treatment_one_probabilities[n] for n in study.node_order]
    else:
        ps=list(treatment_one_probabilities)
    canon=tuple(str(_exact(v,probability=True)) for v in ps)
    positions={n:i for i,n in enumerate(study.node_order)}
    cells=tuple(sorted((tuple(c) for c in covered_arms),
                       key=lambda a:(positions[a[0]],a[1],a[2])))
    return ObservationalFactorizedArmPopulationV27P1(
        source_id,provenance,admission,availability,
        study.shared_scope_digest,study.protocol_digest,study.node_order,
        study.outcome_variable,study.context_reference,signature.signature_fingerprint,
        canon,cells)


@dataclass(frozen=True)
class VerifiedObservationalFactorizedEffectsV27P1:
    study: NetworkStudyContextV17
    source: ObservationalFactorizedArmPopulationV27P1
    assumptions: tuple[Assumption,...]
    signature: SignatureSpecV20
    requests: tuple[EffectQueryV18,...]
    proofs: tuple[ObservationalEffectProofV26,...]
    observational_law_fingerprint: str
    certificate_sha256: str
    theorem_id: str = THEOREM
    route: Literal['R3_P_STANDARDIZED_EFFECTS'] = ROUTE
    contract_version: str = VERSION
    status: Literal['POINT'] = 'POINT'
    verification_status: Literal['VERIFIED'] = 'VERIFIED'
    estimation_request: None = None

    def summary(self) -> dict:
        return dict(route=self.route,status=self.status,
            verification_status=self.verification_status,theorem_id=self.theorem_id,
            A4_operator=self.source.operator,A4_law_kind=self.source.factorization_kind,
            A4_source_id=self.source.source_id,query_count=len(self.requests),
            node_count=len(self.study.node_order),
            observational_law_fingerprint=self.observational_law_fingerprint,
            signature=self.signature.grouping,results=[r.summary() for r in self.proofs],
            certificate_sha256=self.certificate_sha256,
            assumptions_used=['full_vector_conditional_exchangeability','consistency',
                              'fixed_pretreatment_network','finite_conditional_first_moments'],
            exposure_sufficiency_required=False,
            scientific_factorization_validated_in_real_world=False,
            scientific_exchangeability_validated_in_real_world=False,
            estimator_capability='NO_ADAPTER',estimation_request=None,
            note='POINT relative to admitted observational factorizaton, A5 and population arm means. '
                 'No finite-sample estimation; no general observational law, no fixed-policy value.')


def _validate(study,source,signature,assumptions):
    try:
        st=NetworkStudyContextV17(**asdict(study))
        src=ObservationalFactorizedArmPopulationV27P1(**asdict(source))
        sig=SignatureSpecV20(**asdict(signature))
    except (TypeError, ValueError, AttributeError) as exc:
        raise R3Unavailable('A4_FACTOR_NONCANONICAL_TYPED_INPUT') from exc
    if st!=study or src!=source or sig!=signature:
        raise R3Unavailable('A4_FACTOR_NONCANONICAL_TYPED_INPUT')
    if st.observation_regime!='observational' or st.design() is not None:
        raise R3Unavailable('OBSERVATIONAL_STUDY_REQUIRED')
    if st.graph_timing_claim!='DECLARED_PRETREATMENT_FIXED':
        raise R3Unavailable('NETWORK_PRETREATMENT_STATUS_UNRESOLVED')
    if (src.study_scope_digest!=st.shared_scope_digest
        or src.protocol_digest!=st.protocol_digest
        or src.node_order!=st.node_order
        or src.outcome!=st.outcome_variable
        or src.context!=st.context_reference
        or src.signature_fingerprint!=sig.signature_fingerprint):
        raise R3Unavailable('A4_STUDY_OR_PROTOCOL_MISMATCH')
    if src.admission not in {'ADMITTED','CERTIFIED'}:
        raise R3Unavailable('A4_SOURCE_NOT_ADMITTED')
    if src.availability!='SYMBOLIC_POPULATION_OPERATOR':
        raise R3Unavailable('A4_POPULATION_OPERATOR_REQUIRED')
    _validated_assumptions(assumptions)
    return st,src,sig


def _primary_support(probs,own_p,own_a,ref_indices,exposure):
    """Primary exact count-generating polynomial; closed form for E5."""
    grouping=exposure.grouping
    own=(own_p if own_a==1 else (1-own_p))
    if own==0:
        return {}
    neighbors=[probs[i] for i in ref_indices]
    if grouping=='any_treated_neighbor':
        p0=Fraction(1)
        for p in neighbors:
            p0*=1-p
        return {0:own*p0,1:own*(1-p0)}
    coeff=[Fraction(1)]
    for p in neighbors:
        nxt=[Fraction(0)]*(len(coeff)+1)
        for k,v in enumerate(coeff):
            nxt[k]+=v*(1-p)
            nxt[k+1]+=v*p
        coeff=nxt
    result={}
    for k,w in enumerate(coeff):
        if w:
            s=exposure.classify(k,len(neighbors))
            result[s]=result.get(s,Fraction(0))+own*w
    return result


def _solve(study,source,signature,assumptions,requests):
    st,src,sig=_validate(study,source,signature,assumptions)
    if not isinstance(requests,tuple) or not requests:
        raise R3Unavailable('EXPLICIT_EFFECT_QUERIES_REQUIRED')
    terms_by_query=tuple(_canonical_terms(st,q) for q in requests)
    targets={t.node_id for terms in terms_by_query for t in terms}
    exp=_validated_exposure_signature(st,sig,targets)
    positions={n:i for i,n in enumerate(st.node_order)}
    adjacency={n:set() for n in targets}
    for a,b in st.undirected_edges:
        if a in adjacency:adjacency[a].add(b)
        if b in adjacency:adjacency[b].add(a)
    cores=dict(sig.core_collaborators)
    # Declared A4 cells must themselves have a well-defined exposure label,
    # even when the particular business inquiry does not use every cell.
    all_neighbors={n:set() for n in st.node_order}
    for u,v in st.undirected_edges:
        all_neighbors[u].add(v)
        all_neighbors[v].add(u)
    for node,a,s in src.covered_arms:
        refs=cores[node] if sig.grouping=='pretreatment_core_collaborator_majority' else all_neighbors[node]
        if s not in exp.states_for_degree(len(refs)) or (sig.grouping=='three_level_treated_neighbor_fraction' and not refs):
            raise R3Unavailable('A4_FACTOR_UNDEFINED_DECLARED_ARM_CELL',f'{node}:{a}:{s}')
    probabilities=tuple(Fraction(p) for p in src.treatment_one_probabilities)
    requested={t.coordinates for terms in terms_by_query for t in terms}
    supports={}
    for node,a,s in requested:
        refs=cores[node] if sig.grouping=='pretreatment_core_collaborator_majority' else adjacency[node]
        if s not in exp.states_for_degree(len(refs)):
            raise R3Unavailable('INVALID_TARGET_EXPOSURE_STATE',f'{node}:{s}')
        if len(refs)>MAX_REFERENCE_DEGREE:
            raise R3Unavailable('FACTORIZED_SUPPORT_RESOURCE_GUARD',f'{node}:{len(refs)}')
        distribution=_primary_support(probabilities,probabilities[positions[node]],a,
                                     tuple(positions[j] for j in refs),exp)
        pi=distribution.get(s,Fraction(0))
        if pi<=0:
            raise R3Unavailable('ZERO_OBSERVATIONAL_ARM_SUPPORT',f'{node}:{a}:{s}')
        supports[(node,a,s)]=str(pi)
    if not requested<=set(src.covered_arms):
        raise R3Unavailable('A4_WEIGHTED_ARM_POPULATION_MEANS_MISSING',str(sorted(requested-set(src.covered_arms))))
    law_fp=src.observational_law_fingerprint
    proofs=[]
    for request,terms in zip(requests,terms_by_query):
        functional=' + '.join(
            f'({t.coefficient}) * E[Y_{t.node_id}^obs | T_{t.node_id}={t.own_treatment}, '
            f'S_{t.node_id}^g={t.exposure_state}, W={st.context_reference}]'
            for t in terms)
        fp=_sha(dict(version='R3_P_STANDARDIZED_ARM_TARGET_FACTORIZED_LAW_V1',
            study_scope=st.shared_scope_digest,signature=sig.signature_fingerprint,
            observational_law=law_fp,terms=[t.json_payload() for t in terms]))
        proofs.append(ObservationalEffectProofV26(request.kind,terms,
                        tuple(supports[t.coordinates] for t in terms),functional,fp))
    value=VerifiedObservationalFactorizedEffectsV27P1(
        st,src,assumptions,sig,requests,tuple(proofs),law_fp,'')
    return replace(value,certificate_sha256=_sha(_payload(value)))


def _payload(value):
    d=asdict(value)
    d.pop('certificate_sha256',None)
    return d


def _independent_support_audit(value):
    """Different verifier: reverse recursion + MANUAL E predicates.

    It checks support conditional on the declared factorized p; it cannot
    independently establish that observational treatment decisions factorize.
    """
    probs={node:Fraction(p) for node,p in zip(
        value.source.node_order,value.source.treatment_one_probabilities)}
    adjacent={node:set() for node in value.study.node_order}
    for a,b in value.study.undirected_edges:
        adjacent[a].add(b);adjacent[b].add(a)
    core=dict(value.signature.core_collaborators)
    for proof in value.proofs:
        for term,claim in zip(proof.terms,proof.arm_support):
            refs=(core[term.node_id] if value.signature.grouping=='pretreatment_core_collaborator_majority'
                  else adjacent[term.node_id])
            # Recursive generating polynomial constructed from the last neighbor
            # backward, independent of _primary_support / ExposureSpec.
            count={0:Fraction(1)}
            for neighbor in sorted(refs,reverse=True):
                q=probs[neighbor]
                new={}
                for k,v in count.items():
                    new[k]=new.get(k,Fraction(0))+v*(1-q)
                    new[k+1]=new.get(k+1,Fraction(0))+v*q
                count=new
            own=probs[term.node_id] if term.own_treatment==1 else 1-probs[term.node_id]
            independently=own*sum((v for k,v in count.items()
                if _manual_exposure_classify_v26(k,len(refs),value.signature.grouping)
                   ==term.exposure_state),Fraction(0))
            if independently<=0 or independently!=Fraction(claim):
                raise R3Unavailable('R3_FACTORIZED_INDEPENDENT_SUPPORT_MISMATCH',str(term.coordinates))


def identify_observational_factorized_effects_v27p1(
        study:NetworkStudyContextV17,source:ObservationalFactorizedArmPopulationV27P1,
        signature:SignatureSpecV20,*,assumptions:tuple[Assumption,...],
        requests:tuple[EffectQueryV18,...]) -> VerifiedObservationalFactorizedEffectsV27P1:
    value=_solve(study,source,signature,assumptions,requests)
    replay_observational_factorized_effects_v27p1(value)
    return value


def replay_observational_factorized_effects_v27p1(
        value:VerifiedObservationalFactorizedEffectsV27P1) -> bool:
    if not isinstance(value,VerifiedObservationalFactorizedEffectsV27P1):
        raise R3Unavailable('R3_FACTORIZED_RESULT_REQUIRED')
    if (value.contract_version!=VERSION or value.theorem_id!=THEOREM
        or value.route!=ROUTE or value.status!='POINT'
        or value.verification_status!='VERIFIED' or value.estimation_request is not None):
        raise R3Unavailable('R3_FACTORIZED_INVALID_RESULT_ENVELOPE')
    if _sha(_payload(value))!=value.certificate_sha256:
        raise R3Unavailable('R3_FACTORIZED_CERTIFICATE_DIGEST_MISMATCH')
    fresh=_solve(value.study,value.source,value.signature,value.assumptions,value.requests)
    if fresh!=value:
        raise R3Unavailable('R3_FACTORIZED_CERTIFICATE_REPLAY_MISMATCH')
    _independent_support_audit(value)
    return True


__all__=[
    'ObservationalFactorizedArmPopulationV27P1',
    'VerifiedObservationalFactorizedEffectsV27P1',
    'declare_observational_factorized_arm_population_v27p1',
    'identify_observational_factorized_effects_v27p1',
    'replay_observational_factorized_effects_v27p1',
]
