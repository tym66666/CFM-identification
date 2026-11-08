"""v2.8 postrelease P1: finite mixture of observational Bernoulli assignment laws.

A4: p_obs(T=t|W=w) = sum_{h=1}^H pi_h prod_i r_{h,i}^t_i (1-r_{h,i})^(1-t_i),
with exact population weights and treatment probabilities. The latent mixture
component is NOT treated as a covariate or as a randomized experimental arm.
This is a declaration of an observational population law, NOT proof of its truth
or of causal exchangeability. The original R3 full-vector A5 gate and typed
population node-arm means remain required. Outputs remain symbolic; no adapter.
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
from .identification_observational_factorized_a4 import (
    MAX_NODE_COUNT, MAX_REFERENCE_DEGREE, _exact,
)
from .identification_observational_r3 import (
    R3Unavailable, _validated_assumptions, _validated_exposure_signature,
    _manual_exposure_classify_v26,
)
from .identification_policy_r2 import SignatureSpecV20
from .network_inquiry_shadow import NetworkStudyContextV17
from ._internal.identification.schemas import Assumption

VERSION = 'r3-observational-finite-mixture-a4-v2.8-postrelease-p1'
LAW_KIND = 'OBSERVATIONAL_FINITE_MIXTURE_NODEWISE_BERNOULLI'
OPERATOR = 'OBSERVATIONAL_NODE_ARM_POPULATION_CONDITIONAL_MEANS'
ROUTE = 'R3_P_STANDARDIZED_EFFECTS'
MAX_COMPONENTS = 16


def _canonical_components(components):
    """Canonical, deduplicated mixture; float probabilities are prohibited."""
    if not isinstance(components, (tuple, list)) or not 1 <= len(components) <= MAX_COMPONENTS:
        raise ValueError('A4_MIXTURE_COMPONENT_LIMIT')
    accumulated = {}
    width = None
    for item in components:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError('A4_MIXTURE_COMPONENT_PAIR_REQUIRED')
        mass = _exact(item[0], probability=True)
        probs = item[1]
        if not isinstance(probs, (tuple, list)) or not probs:
            raise ValueError('A4_MIXTURE_COMPLETE_NODE_PROBABILITIES_REQUIRED')
        row = tuple(_exact(p, probability=True) for p in probs)
        if width is None:
            width = len(row)
        if len(row) != width:
            raise ValueError('A4_MIXTURE_INCONSISTENT_NODE_DIMENSION')
        if mass == 0:
            raise ValueError('A4_MIXTURE_ZERO_COMPONENT_WEIGHT')
        accumulated[row] = accumulated.get(row, Fraction(0)) + mass
    if sum(accumulated.values(), Fraction(0)) != 1:
        raise ValueError('A4_MIXTURE_WEIGHTS_NOT_NORMALIZED')
    # Sort by vector of node propensities, not by arbitrary component labels.
    return tuple((str(accumulated[row]), tuple(map(str, row)))
                 for row in sorted(accumulated))


@dataclass(frozen=True)
class ObservationalMixtureArmPopulationV28P1:
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
    components: tuple[tuple[str, tuple[str,...]], ...]
    covered_arms: tuple[tuple[str,int,int], ...]
    factorization_kind: str = LAW_KIND
    operator: str = OPERATOR

    def __post_init__(self):
        for s in (self.source_id,self.provenance,self.study_scope_digest,self.protocol_digest,
                  self.outcome,self.context,self.signature_fingerprint):
            if type(s) is not str or not s.strip():
                raise ValueError('A4_MIXTURE_SOURCE_PROVENANCE_OR_COORDINATES_REQUIRED')
        if (not isinstance(self.node_order,tuple) or not 1<=len(self.node_order)<=MAX_NODE_COUNT
            or len(set(self.node_order)) != len(self.node_order)
            or any(type(s) is not str or not s.strip() for s in self.node_order)):
            raise ValueError('A4_MIXTURE_INVALID_NODE_COORDINATES')
        if not isinstance(self.components,tuple) or any(
                not isinstance(x,tuple) or len(x)!=2 or not isinstance(x[1],tuple)
                for x in self.components):
            raise ValueError('A4_MIXTURE_IMMUTABLE_COMPONENTS_REQUIRED')
        canonical = _canonical_components(self.components)
        if canonical != self.components or any(len(p) != len(self.node_order) for _,p in self.components):
            raise ValueError('A4_MIXTURE_CANONICAL_COMPLETE_LAW_REQUIRED')
        if self.factorization_kind != LAW_KIND or self.operator != OPERATOR:
            raise ValueError('A4_MIXTURE_LAW_KIND_OR_OPERATOR_INVALID')
        if self.admission not in ('ADMITTED','CERTIFIED','PROPOSED','UNRESOLVED'):
            raise ValueError('A4_MIXTURE_ADMISSION_INVALID')
        if self.availability not in ('SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE_ESTIMATE'):
            raise ValueError('A4_MIXTURE_AVAILABILITY_INVALID')
        if not isinstance(self.covered_arms,tuple):
            raise ValueError('A4_MIXTURE_COVERAGE_TUPLE_REQUIRED')
        order={n:k for k,n in enumerate(self.node_order)}
        previous=None
        for arm in self.covered_arms:
            if (not isinstance(arm,tuple) or len(arm)!=3 or arm[0] not in order
                or type(arm[1]) is not int or arm[1] not in (0,1)
                or type(arm[2]) is not int or arm[2]<0):
                raise ValueError('A4_MIXTURE_INVALID_ARM_CELL')
            key=(order[arm[0]],arm[1],arm[2])
            if previous is not None and key<=previous:
                raise ValueError('A4_MIXTURE_ARMS_NOT_SORTED_UNIQUE')
            previous=key

    @property
    def observational_law_fingerprint(self):
        return _sha(dict(version='R3_OBSERVATIONAL_MIXTURE_LAW_V1',
                         scope=self.study_scope_digest,protocol=self.protocol_digest,
                         node_order=self.node_order,components=self.components))


def declare_observational_mixture_arm_population_v28p1(
        study:NetworkStudyContextV17,signature:SignatureSpecV20,*,
        source_id:str,provenance:str,components,covered_arms,
        admission:str='ADMITTED',availability:str='SYMBOLIC_POPULATION_OPERATOR'):
    if not isinstance(study,NetworkStudyContextV17) or study.observation_regime!='observational' or study.design() is not None:
        raise ValueError('OBSERVATIONAL_STUDY_REQUIRED')
    if not isinstance(signature,SignatureSpecV20) or signature.study_scope_digest!=study.shared_scope_digest:
        raise ValueError('A4_MIXTURE_SIGNATURE_STUDY_MISMATCH')
    canon = _canonical_components(components)
    order = {n:k for k,n in enumerate(study.node_order)}
    arms=tuple(sorted((tuple(c) for c in covered_arms),key=lambda t:(order[t[0]],t[1],t[2])))
    return ObservationalMixtureArmPopulationV28P1(
        source_id,provenance,admission,availability,study.shared_scope_digest,
        study.protocol_digest,study.node_order,study.outcome_variable,
        study.context_reference,signature.signature_fingerprint,canon,arms)


@dataclass(frozen=True)
class VerifiedObservationalMixtureEffectsV28P1:
    study:NetworkStudyContextV17
    source:ObservationalMixtureArmPopulationV28P1
    assumptions:tuple[Assumption,...]
    signature:SignatureSpecV20
    requests:tuple[EffectQueryV18,...]
    proofs:tuple[ObservationalEffectProofV26,...]
    observational_law_fingerprint:str
    certificate_sha256:str
    theorem_id:str=THEOREM
    route:Literal['R3_P_STANDARDIZED_EFFECTS']=ROUTE
    contract_version:str=VERSION
    status:Literal['POINT']='POINT'
    verification_status:Literal['VERIFIED']='VERIFIED'
    estimation_request:None=None

    def summary(self):
        return dict(route=self.route,status=self.status,verification_status=self.verification_status,
            theorem_id=self.theorem_id,A4_operator=self.source.operator,
            A4_law_kind=self.source.factorization_kind,A4_source_id=self.source.source_id,
            query_count=len(self.requests),node_count=len(self.study.node_order),
            component_count=len(self.source.components),
            observational_law_fingerprint=self.observational_law_fingerprint,
            results=[p.summary() for p in self.proofs],certificate_sha256=self.certificate_sha256,
            assumptions_used=['full_vector_conditional_exchangeability','consistency',
                'fixed_pretreatment_network','finite_conditional_first_moments'],
            exposure_sufficiency_required=False,
            observational_independence_assumed=False,
            empirical_factorization_or_exchangeability_verified=False,
            estimator_capability='NO_ADAPTER',estimation_request=None,
            note='Conditional on an ADMITTED observational finite-mixture law and separate R3 A5. '
                 'No intervention on mixture label; not a randomized study or numeric estimator.')


def _validate(study,source,signature,assumptions):
    try:
        st=NetworkStudyContextV17(**asdict(study))
        src=ObservationalMixtureArmPopulationV28P1(**asdict(source))
        sig=SignatureSpecV20(**asdict(signature))
    except (TypeError,ValueError,AttributeError) as exc:
        raise R3Unavailable('A4_MIXTURE_NONCANONICAL_TYPED_INPUT') from exc
    if st!=study or src!=source or sig!=signature:
        raise R3Unavailable('A4_MIXTURE_NONCANONICAL_TYPED_INPUT')
    if st.observation_regime!='observational' or st.design() is not None:
        raise R3Unavailable('OBSERVATIONAL_STUDY_REQUIRED')
    if st.graph_timing_claim!='DECLARED_PRETREATMENT_FIXED':
        raise R3Unavailable('NETWORK_PRETREATMENT_STATUS_UNRESOLVED')
    if (src.study_scope_digest!=st.shared_scope_digest or src.protocol_digest!=st.protocol_digest
        or src.node_order!=st.node_order or src.outcome!=st.outcome_variable
        or src.context!=st.context_reference or src.signature_fingerprint!=sig.signature_fingerprint):
        raise R3Unavailable('A4_STUDY_OR_PROTOCOL_MISMATCH')
    if src.admission not in ('ADMITTED','CERTIFIED'):
        raise R3Unavailable('A4_SOURCE_NOT_ADMITTED')
    if src.availability!='SYMBOLIC_POPULATION_OPERATOR':
        raise R3Unavailable('A4_POPULATION_OPERATOR_REQUIRED')
    _validated_assumptions(assumptions)
    return st,src,sig


def _support_primary(components,own_i,own_a,reference,exposure):
    """Outer mixture of exact Poisson-binomial generating polynomials."""
    total={}
    for weight,ps in components:
        probs=tuple(map(Fraction,ps))
        own=probs[own_i] if own_a==1 else 1-probs[own_i]
        if not own:
            continue
        coeff=[Fraction(1)]
        for j in reference:
            p=probs[j]
            next_coeff=[Fraction(0)]*(len(coeff)+1)
            for k,v in enumerate(coeff):
                next_coeff[k]+=v*(1-p)
                next_coeff[k+1]+=v*p
            coeff=next_coeff
        for k,v in enumerate(coeff):
            if v:
                label=exposure.classify(k,len(reference))
                total[label]=total.get(label,Fraction(0))+Fraction(weight)*own*v
    return total


def _solve(study,source,signature,assumptions,requests):
    st,src,sig=_validate(study,source,signature,assumptions)
    if not isinstance(requests,tuple) or not requests:
        raise R3Unavailable('EXPLICIT_EFFECT_QUERIES_REQUIRED')
    terms_by_query=tuple(_canonical_terms(st,q) for q in requests)
    targets={t.node_id for terms in terms_by_query for t in terms}
    exp=_validated_exposure_signature(st,sig,targets)
    positions={n:i for i,n in enumerate(st.node_order)}
    adj={n:set() for n in st.node_order}
    for u,v in st.undirected_edges:
        adj[u].add(v);adj[v].add(u)
    cores=dict(sig.core_collaborators)
    # Reject even unused A4 cells when exposure semantics are undefined.
    for node,a,s in src.covered_arms:
        refs=cores[node] if sig.grouping=='pretreatment_core_collaborator_majority' else adj[node]
        if s not in exp.states_for_degree(len(refs)) or (sig.grouping=='three_level_treated_neighbor_fraction' and not refs):
            raise R3Unavailable('A4_MIXTURE_UNDEFINED_DECLARED_ARM_CELL',f'{node}:{a}:{s}')
    requested={t.coordinates for terms in terms_by_query for t in terms}
    supports={}
    for node,a,s in requested:
        refs=cores[node] if sig.grouping=='pretreatment_core_collaborator_majority' else adj[node]
        if s not in exp.states_for_degree(len(refs)):
            raise R3Unavailable('INVALID_TARGET_EXPOSURE_STATE',f'{node}:{s}')
        if len(refs)>MAX_REFERENCE_DEGREE:
            raise R3Unavailable('MIXTURE_SUPPORT_RESOURCE_GUARD',f'{node}:{len(refs)}')
        pi=_support_primary(src.components,positions[node],a,
                            tuple(positions[j] for j in sorted(refs)),exp).get(s,Fraction(0))
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
        fp=_sha(dict(version='R3_P_STANDARDIZED_MIXTURE_TARGET_V1',scope=st.shared_scope_digest,
                     signature=sig.signature_fingerprint,observational_law=law_fp,
                     terms=[t.json_payload() for t in terms]))
        proofs.append(ObservationalEffectProofV26(request.kind,terms,
            tuple(supports[t.coordinates] for t in terms),functional,fp))
    value=VerifiedObservationalMixtureEffectsV28P1(
        st,src,assumptions,sig,requests,tuple(proofs),law_fp,'')
    return replace(value,certificate_sha256=_sha(_payload(value)))


def _payload(value):
    d=asdict(value)
    d.pop('certificate_sha256',None)
    return d


def _independent_support_audit(value):
    """Verifier uses reversed-neighbor sparse recursion and explicit E predicates.

    It never invokes _support_primary or ExposureSpec.classify; even then it
    verifies mathematics conditional on declared A4, not real-world correctness.
    """
    pos={n:i for i,n in enumerate(value.study.node_order)}
    adj={n:set() for n in value.study.node_order}
    for u,v in value.study.undirected_edges:
        adj[u].add(v);adj[v].add(u)
    cores=dict(value.signature.core_collaborators)
    for proof in value.proofs:
        for term,claim in zip(proof.terms,proof.arm_support):
            refs=cores[term.node_id] if value.signature.grouping=='pretreatment_core_collaborator_majority' else adj[term.node_id]
            total=Fraction(0)
            for weight, ps in value.source.components:
                r={n:Fraction(p) for n,p in zip(value.study.node_order,ps)}
                count={0:Fraction(1)}
                for n in sorted(refs,reverse=True):
                    p=r[n]
                    nxt={}
                    for k,mass in count.items():
                        nxt[k]=nxt.get(k,Fraction(0))+mass*(1-p)
                        nxt[k+1]=nxt.get(k+1,Fraction(0))+mass*p
                    count=nxt
                own=r[term.node_id] if term.own_treatment else 1-r[term.node_id]
                label_mass=sum((v for k,v in count.items()
                    if _manual_exposure_classify_v26(k,len(refs),value.signature.grouping)==term.exposure_state),
                    Fraction(0))
                total+=Fraction(weight)*own*label_mass
            if total<=0 or total!=Fraction(claim):
                raise R3Unavailable('R3_MIXTURE_INDEPENDENT_SUPPORT_MISMATCH',str(term.coordinates))


def identify_observational_mixture_effects_v28p1(
        study:NetworkStudyContextV17,source:ObservationalMixtureArmPopulationV28P1,
        signature:SignatureSpecV20,*,assumptions:tuple[Assumption,...],
        requests:tuple[EffectQueryV18,...])->VerifiedObservationalMixtureEffectsV28P1:
    value=_solve(study,source,signature,assumptions,requests)
    replay_observational_mixture_effects_v28p1(value)
    return value


def replay_observational_mixture_effects_v28p1(value:VerifiedObservationalMixtureEffectsV28P1)->bool:
    if not isinstance(value,VerifiedObservationalMixtureEffectsV28P1):
        raise R3Unavailable('R3_MIXTURE_RESULT_REQUIRED')
    if (value.contract_version!=VERSION or value.theorem_id!=THEOREM or value.route!=ROUTE
        or value.status!='POINT' or value.verification_status!='VERIFIED'
        or value.estimation_request is not None):
        raise R3Unavailable('R3_MIXTURE_INVALID_RESULT_ENVELOPE')
    if _sha(_payload(value))!=value.certificate_sha256:
        raise R3Unavailable('R3_MIXTURE_CERTIFICATE_DIGEST_MISMATCH')
    fresh=_solve(value.study,value.source,value.signature,value.assumptions,value.requests)
    if fresh!=value:
        raise R3Unavailable('R3_MIXTURE_CERTIFICATE_REPLAY_MISMATCH')
    _independent_support_audit(value)
    return True


__all__=['ObservationalMixtureArmPopulationV28P1','VerifiedObservationalMixtureEffectsV28P1',
         'declare_observational_mixture_arm_population_v28p1',
         'identify_observational_mixture_effects_v28p1',
         'replay_observational_mixture_effects_v28p1']
