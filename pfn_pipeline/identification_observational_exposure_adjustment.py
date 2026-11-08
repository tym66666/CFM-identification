"""v2.7 post-release P2 (research P1): finite-stratum observational exposure G-formula.

This is a *new R3 subroute/target*, not the old p-standardized R3 arm.
For fixed pretreatment G and W=w, B is a PRETREATMENT, finite categorical
cohort-wide adjustment regime with admitted masses P(B=b | W=w).  Assumptions:
  (i) individual potential-outcome exposure sufficiency: for every allocation z,
      Y_i(z)=Y_i(z_i,g_i(z,G)) for licensed nodes;
  (ii) mean conditional exchangeability for each exposure potential outcome:
      E[Y_i(a,s) | T_i=a,S_i=s,B=b,W=w] = E[Y_i(a,s)|B=b,W=w];
  (iii) consistency, fixed pretreatment network, finite conditional first moments;
  (iv) every target signature (i,a,s) occurs with positive probability at EACH
       positive-mass B=b, with a typed population conditional-mean operator.
Then μ_i(a,s|W=w)=Σ_b P(B=b|W=w)E[Y_i^obs|T_i=a,S_i=s,B=b,W=w].

To validate support without full assignment enumeration, current A4 additionally
requires EXACT, admitted p_obs(T|B=b,W)=product_j Bernoulli(r_{bj}), per b.
This A4 factorization is NOT ignorability and it is NOT randomization. It is a
narrow tractable subdomain, not general node-specific GPS/Auto-G. No estimator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Literal

from ._internal.identification.schemas import Assumption, AssumptionStatus
from ._internal.identification.randomized_arm_family.exposure import ExposureSpec
from .identification_a4_shadow import _sha
from .identification_composition import ArmLinearTerm, EffectQueryV18
from .identification_observational_effects import _canonical_terms
from .identification_observational_factorized_a4 import (
    MAX_NODE_COUNT, MAX_REFERENCE_DEGREE, _exact, _primary_support,
)
from .identification_observational_r3 import (
    R3Unavailable, _validated_exposure_signature, _manual_exposure_classify_v26,
)
from .identification_policy_r2 import SignatureSpecV20
from .network_inquiry_shadow import NetworkStudyContextV17

VERSION='r3-exposure-adjustment-finite-strata-postrelease-p2'
ROUTE='R3_EXPOSURE_ADJUSTED_EFFECTS'
THEOREM='R3_EXPOSURE_OUTCOME_CONDITIONAL_G_FORMULA_POINT_V1'
A4_OP='OBSERVATIONAL_STRATUM_NODE_ARM_CONDITIONAL_POPULATION_MEANS'
A4_LAW='OBSERVATIONAL_PRETREATMENT_STRATIFIED_NODEWISE_FACTORIZATION'
MAX_STRATA=16
BASIC_A5=('consistency','fixed_pretreatment_network','finite_conditional_first_moments')
SCIENCE_SOURCES={'human_confirmation','domain_knowledge','demo_specification'}
ACCEPTED={AssumptionStatus.ADMITTED,AssumptionStatus.CERTIFIED}


def _canon_fraction(value, *, positive=False, probability=False):
    v=_exact(value,probability=probability)
    if positive and v<=0:
        raise ValueError('STRICT_POSITIVE_EXACT_FRACTION_REQUIRED')
    return str(v)


@dataclass(frozen=True)
class PretreatmentStratumV27P2:
    label:str
    mass:str
    treatment_one_probabilities:tuple[str,...]
    def __post_init__(self):
        if not isinstance(self.label,str) or not self.label.strip():
            raise ValueError('NONEMPTY_PRETREATMENT_STRATUM_LABEL_REQUIRED')
        if not isinstance(self.mass,str) or self.mass!=_canon_fraction(self.mass,positive=True,probability=True):
            raise ValueError('CANONICAL_POSITIVE_STRATUM_MASS_REQUIRED')
        if not isinstance(self.treatment_one_probabilities,tuple) or not self.treatment_one_probabilities:
            raise ValueError('COMPLETE_STRATUM_PROPENSITY_VECTOR_REQUIRED')
        for p in self.treatment_one_probabilities:
            if not isinstance(p,str) or p!=_canon_fraction(p,probability=True):
                raise ValueError('CANONICAL_STRATUM_PROPENSITY_REQUIRED')


@dataclass(frozen=True)
class ObservationalStratifiedArmPopulationV27P2:
    source_id:str
    provenance:str
    admission:Literal['ADMITTED','CERTIFIED','PROPOSED','UNRESOLVED']
    availability:Literal['SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE_ESTIMATE']
    study_scope_digest:str
    protocol_digest:str
    node_order:tuple[str,...]
    outcome:str
    context:str
    adjustment_variable:str
    signature_fingerprint:str
    strata:tuple[PretreatmentStratumV27P2,...]
    covered_cells:tuple[tuple[str,str,int,int],...]
    adjustment_timing:Literal['DECLARED_PRETREATMENT']='DECLARED_PRETREATMENT'
    factorization_kind:str=A4_LAW
    operator:str=A4_OP

    def __post_init__(self):
        for name in ('source_id','provenance','study_scope_digest','protocol_digest',
                     'outcome','context','adjustment_variable','signature_fingerprint'):
            if not isinstance(getattr(self,name),str) or not getattr(self,name).strip():
                raise ValueError('A4_STRATIFIED_PROVENANCE_AND_COORDINATES_REQUIRED')
        if not isinstance(self.node_order,tuple) or not 0<len(self.node_order)<=MAX_NODE_COUNT or len(set(self.node_order))!=len(self.node_order):
            raise ValueError('A4_STRATIFIED_INVALID_NODES_OR_RESOURCE_LIMIT')
        if not isinstance(self.strata,tuple) or not 0<len(self.strata)<=MAX_STRATA:
            raise ValueError('A4_STRATIFIED_STRATA_RESOURCE_LIMIT')
        if tuple(s.label for s in self.strata)!=tuple(sorted(set(s.label for s in self.strata))):
            raise ValueError('A4_STRATIFIED_STRATA_UNIQUE_SORTED_REQUIRED')
        if sum((Fraction(s.mass) for s in self.strata),Fraction(0))!=1:
            raise ValueError('A4_STRATIFIED_MASSES_MUST_SUM_TO_ONE')
        if any(len(s.treatment_one_probabilities)!=len(self.node_order) for s in self.strata):
            raise ValueError('A4_STRATIFIED_COMPLETE_NODE_PROPENSITIES_REQUIRED')
        if self.adjustment_timing!='DECLARED_PRETREATMENT':
            raise ValueError('A4_STRATIFIED_ADJUSTMENT_MUST_BE_PRETREATMENT')
        if self.operator!=A4_OP or self.factorization_kind!=A4_LAW:
            raise ValueError('A4_STRATIFIED_OPERATOR_NOT_SUPPORTED')
        if not isinstance(self.covered_cells,tuple):
            raise ValueError('A4_STRATIFIED_IMMUTABLE_CELLS_REQUIRED')
        nodes={n:i for i,n in enumerate(self.node_order)}
        labels={s.label:i for i,s in enumerate(self.strata)}
        previous=None
        for cell in self.covered_cells:
            if (not isinstance(cell,tuple) or len(cell)!=4 or cell[0] not in labels
                or cell[1] not in nodes or type(cell[2]) is not int or cell[2] not in (0,1)
                or type(cell[3]) is not int or cell[3]<0):
                raise ValueError('A4_STRATIFIED_CELL_COORDINATES_INVALID')
            key=(labels[cell[0]],nodes[cell[1]],cell[2],cell[3])
            if previous is not None and key<=previous:
                raise ValueError('A4_STRATIFIED_CELLS_NOT_UNIQUE_SORTED')
            previous=key

    @property
    def assignment_law_fingerprint(self):
        return _sha(dict(version='R3_STRATIFIED_OBS_LAW_V1',scope=self.study_scope_digest,
            protocol=self.protocol_digest,node_order=self.node_order,
            adjustment_variable=self.adjustment_variable,
            strata=[asdict(s) for s in self.strata]))


def declare_stratified_observational_arm_population_v27p2(study,signature,*,
        source_id,provenance,adjustment_variable,strata,covered_cells,
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR'):
    if not isinstance(study,NetworkStudyContextV17) or study.observation_regime!='observational' or study.design() is not None:
        raise ValueError('OBSERVATIONAL_STUDY_REQUIRED')
    if not isinstance(signature,SignatureSpecV20) or signature.study_scope_digest!=study.shared_scope_digest:
        raise ValueError('A4_STRATIFIED_SIGNATURE_STUDY_MISMATCH')
    rows=[]
    for label,mass,ps in strata:
        if isinstance(ps,dict):
            if set(ps)!=set(study.node_order):
                raise ValueError('COMPLETE_STRATUM_PROPENSITIES_REQUIRED')
            ps=tuple(ps[n] for n in study.node_order)
        rows.append(PretreatmentStratumV27P2(label,_canon_fraction(mass,positive=True,probability=True),
                                             tuple(_canon_fraction(p,probability=True) for p in ps)))
    rows.sort(key=lambda s:s.label)
    labels={s.label:i for i,s in enumerate(rows)}
    nodes={n:i for i,n in enumerate(study.node_order)}
    cells=tuple(sorted((tuple(c) for c in covered_cells),key=lambda c:(labels[c[0]],nodes[c[1]],c[2],c[3])))
    return ObservationalStratifiedArmPopulationV27P2(source_id,provenance,admission,availability,
        study.shared_scope_digest,study.protocol_digest,study.node_order,study.outcome_variable,
        study.context_reference,adjustment_variable,signature.signature_fingerprint,tuple(rows),cells)


@dataclass(frozen=True)
class ScopedExposureAdjustmentA5V27P2:
    study_scope_digest:str
    signature_fingerprint:str
    covered_nodes:tuple[str,...]
    potential_outcome_exposure_sufficiency:Assumption
    exposure_level_conditional_exchangeability:Assumption
    def __post_init__(self):
        if (not isinstance(self.study_scope_digest,str) or not self.study_scope_digest
            or not isinstance(self.signature_fingerprint,str) or not self.signature_fingerprint
            or not isinstance(self.covered_nodes,tuple) or not self.covered_nodes
            or len(set(self.covered_nodes))!=len(self.covered_nodes)):
            raise ValueError('SCOPED_EXPOSURE_ADJUSTMENT_LICENSE_REQUIRED')


def admit_exposure_adjustment_a5_v27p2(study,signature,*,covered_nodes,
        potential_outcome_exposure_sufficiency,exposure_level_conditional_exchangeability):
    return ScopedExposureAdjustmentA5V27P2(
        study.shared_scope_digest,signature.signature_fingerprint,tuple(covered_nodes),
        potential_outcome_exposure_sufficiency,exposure_level_conditional_exchangeability)


@dataclass(frozen=True)
class AdjustedExposureProofV27P2:
    kind:Literal['DIRECT','SPILLOVER','TOTAL']
    terms:tuple[ArmLinearTerm,...]
    support_by_stratum:tuple[tuple[str,tuple[str,...]],...]
    identified_functional:str
    target_fingerprint:str
    def summary(self):
        return dict(kind=self.kind,target_fingerprint=self.target_fingerprint,
            arm_terms=[t.json_payload() for t in self.terms],
            support_by_stratum=[dict(stratum=b,nonzero_term_support=list(s)) for b,s in self.support_by_stratum],
            identified_functional=self.identified_functional)


@dataclass(frozen=True)
class VerifiedExposureAdjustedEffectsV27P2:
    study:NetworkStudyContextV17
    source:ObservationalStratifiedArmPopulationV27P2
    assumptions:tuple[Assumption,...]
    license:ScopedExposureAdjustmentA5V27P2
    signature:SignatureSpecV20
    requests:tuple[EffectQueryV18,...]
    proofs:tuple[AdjustedExposureProofV27P2,...]
    certificate_sha256:str
    route:Literal['R3_EXPOSURE_ADJUSTED_EFFECTS']=ROUTE
    theorem_id:str=THEOREM
    contract_version:str=VERSION
    status:Literal['POINT']='POINT'
    verification_status:Literal['VERIFIED']='VERIFIED'
    estimation_request:None=None
    def summary(self):
        return dict(route=self.route,theorem_id=self.theorem_id,
            contract_version=self.contract_version,status=self.status,
            verification_status=self.verification_status,
            source_id=self.source.source_id,A4_operator=self.source.operator,
            adjustment_variable=self.source.adjustment_variable,
            strata=[dict(label=b.label,mass=b.mass) for b in self.source.strata],
            target_semantics='EXPOSURE_POTENTIAL_OUTCOME_ADJUSTED_MEAN',
            exposure_sufficiency_required=True,
            full_vector_exchangeability_required=False,
            assumptions_used=list(BASIC_A5)+[
                'potential_outcome_exposure_sufficiency',
                'exposure_level_conditional_exchangeability'],
            results=[p.summary() for p in self.proofs],
            certificate_sha256=self.certificate_sha256,
            estimator_capability='NO_ADAPTER',estimation_request=None,
            scientific_assumptions_verified_in_real_world=False,
            note='Population conditional G-formula, NOT p-standardized effect, fixed policy value, '
                 'Auto-G, sample estimate, or verified real-world adjustment.')


def _require_assumption(record,expected):
    if not isinstance(record,Assumption) or record.name!=expected:
        raise R3Unavailable('R3_ADJUSTMENT_A5_TYPE_MISSING',expected)
    try:
        canonical=Assumption.model_validate(record.model_dump(mode='json'))
    except (TypeError,ValueError) as exc:
        raise R3Unavailable('R3_ADJUSTMENT_A5_INVALID') from exc
    if canonical.model_dump(mode='json')!=record.model_dump(mode='json'):
        raise R3Unavailable('R3_ADJUSTMENT_A5_INVALID')
    if (record.status not in ACCEPTED or not record.confirmed or record.source not in SCIENCE_SOURCES
        or not record.evidence or not any(isinstance(e,str) and e.strip() for e in record.evidence)):
        raise R3Unavailable('NEEDS_INPUT','A5 not scientifically admitted: '+expected)


def _validate(study,source,signature,assumptions,license):
    try:
        st=NetworkStudyContextV17(**asdict(study))
        src=ObservationalStratifiedArmPopulationV27P2(**{**asdict(source),
            "strata":tuple(PretreatmentStratumV27P2(**asdict(b)) for b in source.strata)})
        sig=SignatureSpecV20(**asdict(signature))
        lic=ScopedExposureAdjustmentA5V27P2(
            license.study_scope_digest, license.signature_fingerprint,
            tuple(license.covered_nodes), license.potential_outcome_exposure_sufficiency,
            license.exposure_level_conditional_exchangeability)
    except (ValueError,TypeError,AttributeError) as exc:
        raise R3Unavailable('R3_ADJUSTMENT_NONCANONICAL_TYPED_INPUT') from exc
    if (st!=study or src!=source or sig!=signature or lic!=license):
        raise R3Unavailable('R3_ADJUSTMENT_NONCANONICAL_TYPED_INPUT')
    if st.observation_regime!='observational' or st.design() is not None:
        raise R3Unavailable('OBSERVATIONAL_STUDY_REQUIRED')
    if st.graph_timing_claim!='DECLARED_PRETREATMENT_FIXED':
        raise R3Unavailable('NETWORK_PRETREATMENT_STATUS_UNRESOLVED')
    if (src.study_scope_digest!=st.shared_scope_digest or src.protocol_digest!=st.protocol_digest
        or src.node_order!=st.node_order or src.outcome!=st.outcome_variable
        or src.context!=st.context_reference or src.signature_fingerprint!=sig.signature_fingerprint
        or lic.study_scope_digest!=st.shared_scope_digest
        or lic.signature_fingerprint!=sig.signature_fingerprint):
        raise R3Unavailable('R3_ADJUSTMENT_STUDY_SIGNATURE_OR_A4_MISMATCH')
    if src.admission not in {'ADMITTED','CERTIFIED'}:
        raise R3Unavailable('A4_STRATIFIED_SOURCE_NOT_ADMITTED')
    if src.availability!='SYMBOLIC_POPULATION_OPERATOR':
        raise R3Unavailable('A4_STRATIFIED_POPULATION_OPERATOR_REQUIRED')
    _require_assumption(lic.potential_outcome_exposure_sufficiency,'potential_outcome_exposure_sufficiency')
    _require_assumption(lic.exposure_level_conditional_exchangeability,'exposure_level_conditional_exchangeability')
    if not isinstance(assumptions,tuple):
        raise R3Unavailable('TYPED_ASSUMPTIONS_REQUIRED')
    seen={}
    for a in assumptions:
        if not isinstance(a,Assumption) or a.name in seen:
            raise R3Unavailable('DUPLICATE_OR_INVALID_ASSUMPTION')
        seen[a.name]=a
    if any(name in seen for name in ('known_assignment_law','full_vector_randomization')):
        raise R3Unavailable('RANDOMIZATION_IS_NOT_OBSERVATIONAL_IGNORABILITY')
    for name in BASIC_A5:
        _require_assumption(seen.get(name),name)
    return st,src,sig,lic


def _refs(st,signature):
    adj={n:set() for n in st.node_order}
    for a,b in st.undirected_edges:
        adj[a].add(b);adj[b].add(a)
    if signature.grouping=='pretreatment_core_collaborator_majority':
        return {n:set(v) for n,v in signature.core_collaborators}
    return adj


def _solve(study,source,signature,assumptions,license,requests):
    st,src,sig,lic=_validate(study,source,signature,assumptions,license)
    if not isinstance(requests,tuple) or not requests:
        raise R3Unavailable('R3_ADJUSTMENT_EFFECT_QUERIES_REQUIRED')
    canonical_terms=tuple(_canonical_terms(st,q) for q in requests)
    required_nodes={t.node_id for terms in canonical_terms for t in terms}
    if not required_nodes<=set(lic.covered_nodes) or not set(lic.covered_nodes)<=set(st.node_order):
        raise R3Unavailable('R3_ADJUSTMENT_A5_NODE_COVERAGE_MISSING')
    exp=_validated_exposure_signature(st,sig,required_nodes)
    refs=_refs(st,sig)
    positions={n:i for i,n in enumerate(st.node_order)}
    for b,n,a,s in src.covered_cells:
        if s not in exp.states_for_degree(len(refs[n])) or (sig.grouping=='three_level_treated_neighbor_fraction' and len(refs[n])==0):
            raise R3Unavailable('A4_STRATIFIED_UNDEFINED_EXPOSURE_CELL',f'{b},{n},{a},{s}')
    used={term.coordinates for terms in canonical_terms for term in terms}
    needed={(b.label,*arm) for b in src.strata for arm in used}
    if not needed<=set(src.covered_cells):
        raise R3Unavailable('A4_STRATIFIED_CONDITIONAL_MEANS_MISSING',str(sorted(needed-set(src.covered_cells))[:3]))
    support={}
    for stratum in src.strata:
        probs=tuple(Fraction(x) for x in stratum.treatment_one_probabilities)
        for n,a,s in sorted(used,key=lambda t:(positions[t[0]],t[1],t[2])):
            if s not in exp.states_for_degree(len(refs[n])):
                raise R3Unavailable('INVALID_TARGET_EXPOSURE_STATE',str((n,a,s)))
            if len(refs[n])>MAX_REFERENCE_DEGREE:
                raise R3Unavailable('STRATIFIED_SUPPORT_RESOURCE_GUARD',n)
            dist=_primary_support(probs,probs[positions[n]],a,tuple(positions[j] for j in refs[n]),exp)
            p=dist.get(s,Fraction(0))
            if p<=0:
                raise R3Unavailable('ZERO_STRATUM_EXPOSURE_SUPPORT',f'{stratum.label}:{n},{a},{s}')
            support[(stratum.label,n,a,s)]=str(p)
    # This target does NOT depend on the observational treatment propensities.
    target_distribution=tuple((s.label,s.mass) for s in src.strata)
    proofs=[]
    for q,terms in zip(requests,canonical_terms):
        terms_str=[]
        for term in terms:
            inner=' + '.join(
                f'({s.mass}) * E[Y_{term.node_id}^obs | T_{term.node_id}={term.own_treatment}, '
                f'S_{term.node_id}^g={term.exposure_state}, '
                f'{src.adjustment_variable}={s.label}, W={st.context_reference}]'
                for s in src.strata)
            terms_str.append(f'({term.coefficient}) * ({inner})')
        fp=_sha(dict(version='R3_ADJUSTED_EXPOSURE_POTENTIAL_OUTCOME_TARGET_V1',
            scope=st.shared_scope_digest,signature=sig.signature_fingerprint,
            adjustment_variable=src.adjustment_variable,stratum_distribution=target_distribution,
            terms=[term.json_payload() for term in terms]))
        stratum_support=tuple((b.label,tuple(support[(b.label,*term.coordinates)] for term in terms))
                              for b in src.strata)
        proofs.append(AdjustedExposureProofV27P2(q.kind,terms,stratum_support,
                                                 ' + '.join(terms_str),fp))
    result=VerifiedExposureAdjustedEffectsV27P2(st,src,assumptions,lic,sig,requests,tuple(proofs),'')
    return replace(result,certificate_sha256=_sha(_payload(result)))


def _payload(value):
    d=asdict(value);d.pop('certificate_sha256',None)
    return d


def _independent_support_verifier(value):
    # Independent reverse polynomial recursion and explicit E1-E5 predicates;
    # no use of primary _primary_support, ExposureSpec, or solver cache.
    # Reconstruct network adjacency independently of the primary _refs helper.
    refs={n:set() for n in value.study.node_order}
    for u,v in value.study.undirected_edges:
        refs[u].add(v);refs[v].add(u)
    if value.signature.grouping=='pretreatment_core_collaborator_majority':
        refs={n:set(v) for n,v in value.signature.core_collaborators}
    for proof in value.proofs:
        for b,claims in proof.support_by_stratum:
            probs={n:Fraction(p) for n,p in zip(value.study.node_order,
                next(s for s in value.source.strata if s.label==b).treatment_one_probabilities)}
            for term,claim in zip(proof.terms,claims):
                counts={0:Fraction(1)}
                for j in sorted(refs[term.node_id],reverse=True):
                    nxt={}
                    for k,m in counts.items():
                        nxt[k]=nxt.get(k,Fraction(0))+m*(1-probs[j])
                        nxt[k+1]=nxt.get(k+1,Fraction(0))+m*probs[j]
                    counts=nxt
                own=probs[term.node_id] if term.own_treatment else 1-probs[term.node_id]
                actual=own*sum((mass for k,mass in counts.items()
                    if _manual_exposure_classify_v26(k,len(refs[term.node_id]),value.signature.grouping)
                       ==term.exposure_state),Fraction(0))
                if actual<=0 or actual!=Fraction(claim):
                    raise R3Unavailable('R3_ADJUSTMENT_INDEPENDENT_SUPPORT_MISMATCH',
                        f'{b}:{term.coordinates}')


def identify_observational_exposure_adjusted_effects_v27p2(study,source,signature,*,
        assumptions,license,requests):
    result=_solve(study,source,signature,assumptions,license,requests)
    replay_observational_exposure_adjusted_effects_v27p2(result)
    return result


def replay_observational_exposure_adjusted_effects_v27p2(result):
    if not isinstance(result,VerifiedExposureAdjustedEffectsV27P2):
        raise R3Unavailable('R3_ADJUSTMENT_TYPED_RESULT_REQUIRED')
    if (result.route!=ROUTE or result.theorem_id!=THEOREM or result.contract_version!=VERSION
        or result.status!='POINT' or result.verification_status!='VERIFIED'
        or result.estimation_request is not None):
        raise R3Unavailable('R3_ADJUSTMENT_INVALID_RESULT_ENVELOPE')
    if result.certificate_sha256!=_sha(_payload(result)):
        raise R3Unavailable('R3_ADJUSTMENT_CERTIFICATE_DIGEST_MISMATCH')
    if result!=_solve(result.study,result.source,result.signature,result.assumptions,
                      result.license,result.requests):
        raise R3Unavailable('R3_ADJUSTMENT_CERTIFICATE_REPLAY_MISMATCH')
    _independent_support_verifier(result)
    return True


def requirements_for_exposure_adjustment_v27p2():
    """Postrelease P2 addition; keeps the published v2.7 P0 catalog unchanged."""
    return dict(route=ROUTE,
        target_semantics='finite_pretreatment_strata_adjusted_exposure_potential_outcome_contrasts',
        required_names=list(BASIC_A5)+['potential_outcome_exposure_sufficiency',
                                      'exposure_level_conditional_exchangeability'],
        conditionally_required_if_D6=None,
        A4_required='exact admitted P(B|W), factorized p_obs(T|B,W), typed symbolic E[Yobs|T_i,S_i,B,W]',
        A6_required='positive signature support in every positive-mass B stratum',
        requires_mean_signature_sufficiency=False,
        requires_individual_exposure_sufficiency=True,
        exposure_mapping_does_not_certify_sufficiency=True,
        premises_checked_by='NATIVE_R3_EXPOSURE_ADJUSTMENT_THEOREM_AND_REPLAY',
        scientific_validity_certified_by_software=False,
        no_assumption_discovery=True)


def implemented_assumption_catalog_v27p2():
    """Opt-in extended discovery; preserve v2.7 P0 public counts for old callers."""
    from .identification_assumption_inventory import implemented_assumption_catalog_v27
    old=implemented_assumption_catalog_v27()
    extra=[dict(name='potential_outcome_exposure_sufficiency',layer='A5_STRUCTURAL',
        description='Y_i(t) equals Y_i(t_i,g_i(t,G)) for all complete assignments, licensed nodes.',
        scientific_scope='R3 exposure-adjustment subroute only; stronger than R2 mean sufficiency.',
        machine_verifiability='Scoped admitted license checked; scientific truth not proven.'),
           dict(name='exposure_level_conditional_exchangeability',layer='A5_OBSERVATIONAL',
        description='Conditional mean ignorability of exposure potential outcomes given B,W.',
        scientific_scope='R3 exposure-adjustment subroute only; not full-vector ignorability.',
        machine_verifiability='Scoped admitted license checked; observational data alone cannot prove it.')]
    return {**old,'contract':'CFM-ID-IMPLEMENTED-ASSUMPTIONS-v2.7-POSTRELEASE-P2',
        'assumptions':old['assumptions']+extra,'route_ids':old['route_ids']+[ROUTE],
        'legacy_catalog_unchanged':True}


__all__=['PretreatmentStratumV27P2','ObservationalStratifiedArmPopulationV27P2',
    'ScopedExposureAdjustmentA5V27P2','AdjustedExposureProofV27P2',
    'VerifiedExposureAdjustedEffectsV27P2',
    'declare_stratified_observational_arm_population_v27p2',
    'admit_exposure_adjustment_a5_v27p2',
    'identify_observational_exposure_adjusted_effects_v27p2',
    'replay_observational_exposure_adjusted_effects_v27p2',
    'requirements_for_exposure_adjustment_v27p2',
    'implemented_assumption_catalog_v27p2']
