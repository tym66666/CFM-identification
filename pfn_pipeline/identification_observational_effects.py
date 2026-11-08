"""v2.6 R3 *observational-law-standardized* network effect identification.

This is a new R3 A1 Target route, not a new causal-identification Family.
Under admitted full-vector conditional exchangeability and consistency,
E[Y_i(t)|W=w] = E[Y_i^obs|T=t,W=w] for positive assignment cells.
For a positive p_obs arm cell, its p_obs-conditioned potential-outcome mixture
is therefore identified by E[Y_i^obs|T_i=a,g_i(T)=s,W=w].

- NO exposure sufficiency is required for these *standardized* arm targets.
- DIRECT/SPILLOVER/TOTAL are contrasts of those standardized arm means,
  NOT fixed-neighbor controlled effects or fixed-allocation policy values.
- The observational allocation law p_obs *determines the target mixture*.
- Reuses R3 existing A4/A5 admission, E1-E5 signature, and R1a contrast algebra.
- Small exact population laws <=12 nodes; no empirical estimator or PFN output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Literal

from .identification_a4_shadow import _sha
from .identification_composition import (
    ArmLinearTerm, EffectQueryV18, compile_effect_query_terms,
)
from .identification_observational_r3 import (
    R3Unavailable, ObservationalFinitePopulationV23,
    _validated_observational_basis, _validated_exposure_signature,
    _manual_exposure_classify_v26,
)
from .identification_policy_r2 import SignatureSpecV20
from .network_inquiry_shadow import NetworkStudyContextV17
from ._internal.identification.schemas import Assumption
from ._internal.identification.randomized_arm_family.assignment import neighbor_set

VERSION = 'r3-observational-standardized-effects-v2.6'
THEOREM = 'R3_OBSERVATIONAL_P_STANDARDIZED_ARM_CONTRAST_FIXED_W_POINT_V1'
TARGET_KIND = 'OBSERVATIONAL_P_STANDARDIZED_ARM_LINEAR_CONTRAST'

__all__ = [
    'VerifiedObservationalEffectsV26','identify_observational_effects_v26',
    'replay_observational_effects_v26',
]


@dataclass(frozen=True)
class ObservationalEffectProofV26:
    kind: Literal['DIRECT','SPILLOVER','TOTAL']
    terms: tuple[ArmLinearTerm, ...]
    arm_support: tuple[str, ...]
    identified_functional: str
    target_fingerprint: str

    def summary(self):
        return dict(kind=self.kind, status='POINT',
            target_fingerprint=self.target_fingerprint,
            identified_functional=self.identified_functional,
            arm_terms=[dict(**term.json_payload(), population_support=prob)
                       for term,prob in zip(self.terms,self.arm_support)])


@dataclass(frozen=True)
class VerifiedObservationalEffectsV26:
    study: NetworkStudyContextV17
    source: ObservationalFinitePopulationV23
    assumptions: tuple[Assumption,...]
    signature: SignatureSpecV20
    requests: tuple[EffectQueryV18,...]
    proofs: tuple[ObservationalEffectProofV26,...]
    observational_law_fingerprint: str
    certificate_sha256: str
    theorem_id: str = THEOREM
    route: Literal['R3_P_STANDARDIZED_EFFECTS']='R3_P_STANDARDIZED_EFFECTS'
    contract_version: str = VERSION
    status: Literal['POINT']='POINT'
    verification_status: Literal['VERIFIED']='VERIFIED'
    estimation_request: None = None

    def summary(self):
        return dict(route=self.route, status=self.status,
            verification_status=self.verification_status,
            theorem_id=self.theorem_id, query_count=len(self.requests),
            observational_law_fingerprint=self.observational_law_fingerprint,
            signature=self.signature.grouping,
            results=[proof.summary() for proof in self.proofs],
            certificate_sha256=self.certificate_sha256,
            assumptions_used=['full_vector_conditional_exchangeability','consistency',
                              'fixed_pretreatment_network','finite_conditional_first_moments'],
            exposure_sufficiency_required=False,
            estimator_capability='NO_ADAPTER', estimation_request=None,
            note='Conditional, observed-law-standardized causal contrasts; not '
                 'controlled-neighbor effects or fixed full-assignment policy values. '
                 'A5 exchangeability is assumed, not empirically confirmed; '
                 'A4 declares symbolic population operators, not sample estimates.')


def _law_digest(source):
    # p_obs is part of the causal target standardization, unlike source provenance.
    return _sha(dict(version='R3_P_STANDARDIZATION_LAW_V1',
             node_order=source.node_order, assignment_masses=source.assignment_masses))


def _canonical_terms(study, request):
    if not isinstance(request, EffectQueryV18):
        raise R3Unavailable('TYPED_OBSERVATIONAL_EFFECT_REQUEST_REQUIRED')
    try:
        canonical = EffectQueryV18(**asdict(request))
        terms = compile_effect_query_terms(canonical)
    except (ValueError, TypeError, AttributeError) as exc:
        raise R3Unavailable('INVALID_EFFECT_TARGET') from exc
    if canonical != request:
        raise R3Unavailable('NONCANONICAL_EFFECT_TARGET')
    pos = {node:i for i,node in enumerate(study.node_order)}
    collected = {}
    for t in terms:
        if t.node_id not in pos:
            raise R3Unavailable('TARGET_NODE_OUTSIDE_STUDY')
        key = (t.node_id,t.own_treatment,t.exposure_state)
        collected[key] = collected.get(key,Fraction(0)) + t.coefficient
    clean = tuple(ArmLinearTerm(*key, coeff) for key,coeff in sorted(
        collected.items(),key=lambda pair: (pos[pair[0][0]],pair[0][1],pair[0][2])) if coeff)
    if not clean:
        raise R3Unavailable('ZERO_LINEAR_TARGET')
    return clean


def _compute(study,source,signature,assumptions,requests):
    st,src = _validated_observational_basis(study,source,assumptions)
    if not isinstance(requests,tuple) or not requests:
        raise R3Unavailable('EXPLICIT_EFFECT_QUERIES_REQUIRED')
    canonical_requests=[]
    terms_by_query=[]
    for request in requests:
        terms_by_query.append(_canonical_terms(st,request))
        canonical_requests.append(request)
    nodes = {t.node_id for terms in terms_by_query for t in terms}
    if not nodes<=set(src.outcome_nodes):
        raise R3Unavailable('A4_WEIGHTED_OUTCOME_NODES_MISSING')
    exposure = _validated_exposure_signature(st,signature,nodes)
    adjacency = {n:neighbor_set(st.network(),n) for n in nodes}
    if signature.grouping=='pretreatment_core_collaborator_majority':
        core=dict(signature.core_collaborators)
        adjacency={n:frozenset(core[n]) for n in nodes}
    positions={n:i for i,n in enumerate(st.node_order)}
    # Each cell is evaluated under the SAME observational joint treatment law.
    law=[(t,Fraction(p)) for t,p in src.assignment_masses]
    used_arms={t.coordinates for terms in terms_by_query for t in terms}
    support={}
    for node,a,s in used_arms:
        refs=adjacency[node]
        if s not in exposure.states_for_degree(len(refs)):
            raise R3Unavailable('INVALID_TARGET_EXPOSURE_STATE',f'{node}: {s}')
        pi=sum((p for t,p in law
                if t[positions[node]]==a and
                exposure.classify(sum(t[positions[u]] for u in refs),len(refs))==s),
               Fraction(0))
        if pi<=0:
            raise R3Unavailable('ZERO_OBSERVATIONAL_ARM_SUPPORT',f'{node}, {a}, {s}')
        support[(node,a,s)]=str(pi)
    law_fingerprint=_law_digest(src)
    proofs=[]
    for request,terms in zip(canonical_requests,terms_by_query):
        objects=[]
        for term in terms:
            objects.append((term.coefficient,
                f'E[Y_{term.node_id}^obs | T_{term.node_id}={term.own_treatment}, '
                f'S_{term.node_id}^g={term.exposure_state}, W={st.context_reference}]'))
        functional=' + '.join(f'({weight}) * {atom}' for weight,atom in objects)
        fp=_sha(dict(version='R3_P_STANDARDIZED_ARM_TARGET_V1',
            study_scope=st.shared_scope_digest,
            exposure_signature=signature.signature_fingerprint,
            observational_law=law_fingerprint,
            terms=[term.json_payload() for term in terms]))
        proofs.append(ObservationalEffectProofV26(request.kind,terms,
            tuple(support[t.coordinates] for t in terms),functional,fp))
    result=VerifiedObservationalEffectsV26(
        st,src,assumptions,signature,tuple(canonical_requests),tuple(proofs),law_fingerprint,'')
    return replace(result,certificate_sha256=_sha(_certificate_payload(result)))


def _certificate_payload(result):
    data=asdict(result);data.pop('certificate_sha256')
    return data


def _independent_support_check(value):
    """Independent graph construction/predicate; no primary ExposureSpec or solver cache."""
    positions={node:i for i,node in enumerate(value.study.node_order)}
    adj={n:set() for n in value.study.node_order}
    for left,right in value.study.undirected_edges:
        adj[left].add(right);adj[right].add(left)
    core=dict(value.signature.core_collaborators)
    rows=value.source.assignment_masses
    for proof in value.proofs:
        for term,claimed in zip(proof.terms,proof.arm_support):
            refs=core[term.node_id] if value.signature.grouping=='pretreatment_core_collaborator_majority' else adj[term.node_id]
            den=Fraction(0)
            for assignment,p in rows:
                if assignment[positions[term.node_id]]!=term.own_treatment:
                    continue
                k=sum(assignment[positions[u]] for u in refs)
                s=_manual_exposure_classify_v26(k,len(refs),value.signature.grouping)
                if s==term.exposure_state:
                    den+=Fraction(p)
            if den<=0 or den!=Fraction(claimed):
                raise R3Unavailable('R3_INDEPENDENT_ARM_SUPPORT_MISMATCH',str(term.coordinates))


def identify_observational_effects_v26(
        study: NetworkStudyContextV17, source: ObservationalFinitePopulationV23,
        signature: SignatureSpecV20, *, assumptions:tuple[Assumption,...],
        requests:tuple[EffectQueryV18,...])->VerifiedObservationalEffectsV26:
    value=_compute(study,source,signature,assumptions,requests)
    replay_observational_effects_v26(value)
    return value


def replay_observational_effects_v26(value:VerifiedObservationalEffectsV26)->bool:
    if not isinstance(value,VerifiedObservationalEffectsV26):
        raise R3Unavailable('R3_EFFECT_RESULT_REQUIRED')
    if (value.contract_version!=VERSION or value.theorem_id!=THEOREM or
        value.route!='R3_P_STANDARDIZED_EFFECTS' or value.status!='POINT' or
        value.verification_status!='VERIFIED' or value.estimation_request is not None):
        raise R3Unavailable('R3_EFFECT_INVALID_RESULT_ENVELOPE')
    if _sha(_certificate_payload(value))!=value.certificate_sha256:
        raise R3Unavailable('R3_EFFECT_CERTIFICATE_DIGEST_MISMATCH')
    fresh=_compute(value.study,value.source,value.signature,value.assumptions,value.requests)
    if fresh!=value:
        raise R3Unavailable('R3_EFFECT_CERTIFICATE_REPLAY_MISMATCH')
    _independent_support_check(value)
    return True
