"""v2.8: explicitly scoped R3 node-specific local-covariate exposure adjustment.

Fixed pre-treatment undirected G; one binary pre-treatment feature X_j per node.
For each i, C_i = (X_i, sum_{j in N(i)} X_j), where N(i) means ALL
undirected graph neighbors (even if exposure E3 uses core collaborators).
A4: finite exact P(X-vector|W), conditional nodewise-factorized P(T|X,W),
and typed population E[Yobs_i|Ti=a,Si=s,Ci=c,W] *operators*.
A5: individual Y_i(t)=Y_i(t_i,g_i(t,G)), plus exposure-potential-outcome
mean exchangeability conditional on C_i, separately scientifically admitted.
The target E[Y_i(a,s)|W] does not depend on P(T|X,W).

This is NOT full generalized propensity-score adjustment, not Network Auto-G,
not a fitted regression, and not an empirical verification of ignorability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Literal

from ._internal.identification.schemas import Assumption
from .identification_a4_shadow import _sha
from .identification_composition import ArmLinearTerm, EffectQueryV18
from .identification_observational_effects import _canonical_terms
from .identification_observational_exposure_adjustment import (
    BASIC_A5, _require_assumption,
)
from .identification_observational_factorized_a4 import (
    MAX_NODE_COUNT, MAX_REFERENCE_DEGREE, _exact, _primary_support,
)
from .identification_observational_r3 import (
    R3Unavailable, _validated_exposure_signature, _manual_exposure_classify_v26,
)
from .identification_policy_r2 import SignatureSpecV20
from .network_inquiry_shadow import NetworkStudyContextV17

VERSION='r3-nodewise-neighbor-covariate-adjustment-v2.8'
ROUTE='R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'
THEOREM='R3_LOCAL_COVARIATE_EXPOSURE_G_FORMULA_POINT_V1'
A4_OP='OBSERVATIONAL_NODE_LOCAL_COVARIATE_ARM_POPULATION_MEANS'
A4_LAW='OBSERVATIONAL_FINITE_X_PROFILE_CONDITIONAL_NODEWISE_FACTORIZATION'
ADJUSTMENT='OWN_BINARY_X_PLUS_UNDIRECTED_NEIGHBOR_POSITIVE_X_COUNT'
MAX_PROFILES=24
MAX_COVERED_CELLS=20000
# Optional correlated observational A4: finite mixtures of Bernoulli laws
# conditional on each complete pretreatment X profile. This is NOT A5.
CONDITIONAL_MIXTURE_LAW='OBSERVATIONAL_FINITE_X_PROFILE_CONDITIONAL_BERNOULLI_MIXTURE'
CONDITIONAL_MIXTURE_OPERATOR='OBSERVATIONAL_NODE_LOCAL_COVARIATE_MIXTURE_ARM_POPULATION_MEANS'
MAX_CONDITIONAL_COMPONENTS=16


def _fraction_str(x, *, probability=True, positive=False):
    v=_exact(x,probability=probability)
    if positive and v<=0:
        raise ValueError('STRICT_POSITIVE_PROFILE_MASS_REQUIRED')
    return str(v)


def _schema(st, signature, feature_name):
    return _sha(dict(version='NODEWISE_LOCAL_COVARIATE_SCHEMA_V1',
        scope=st.shared_scope_digest,signature=signature.signature_fingerprint,
        feature_name=feature_name,network_edges=st.undirected_edges,
        node_order=st.node_order,aggregation=ADJUSTMENT))


def _neighbors(st):
    neighbors={n:set() for n in st.node_order}
    for a,b in st.undirected_edges:
        neighbors[a].add(b);neighbors[b].add(a)
    return neighbors


def _exposure_refs(st,signature):
    if signature.grouping=='pretreatment_core_collaborator_majority':
        return {n:set(vals) for n,vals in signature.core_collaborators}
    return _neighbors(st)


@dataclass(frozen=True)
class NodewisePretreatmentProfileV28:
    label:str
    mass:str
    node_binary_features:tuple[int,...]
    treatment_one_probabilities:tuple[str,...]

    def __post_init__(self):
        if not isinstance(self.label,str) or not self.label.strip():
            raise ValueError('NODEWISE_PROFILE_LABEL_REQUIRED')
        if type(self.mass) is not str or self.mass!=_fraction_str(self.mass,positive=True):
            raise ValueError('NODEWISE_PROFILE_POSITIVE_CANONICAL_MASS_REQUIRED')
        if (not isinstance(self.node_binary_features,tuple) or not self.node_binary_features
            or not all(type(x) is int and x in (0,1) for x in self.node_binary_features)):
            raise ValueError('NODEWISE_PROFILE_BINARY_PRETREATMENT_FEATURES_REQUIRED')
        if (not isinstance(self.treatment_one_probabilities,tuple)
            or len(self.treatment_one_probabilities)!=len(self.node_binary_features)
            or any(type(p) is not str or p!=_fraction_str(p)
                   for p in self.treatment_one_probabilities)):
            raise ValueError('NODEWISE_PROFILE_EXACT_CONDITIONAL_PROPENSITIES_REQUIRED')


@dataclass(frozen=True)
class ConditionalBernoulliComponentV28P2:
    weight:str
    treatment_one_probabilities:tuple[str,...]

    def __post_init__(self):
        if type(self.weight) is not str or self.weight!=_fraction_str(self.weight,positive=True):
            raise ValueError('NODEWISE_MIXTURE_EXACT_POSITIVE_COMPONENT_WEIGHT_REQUIRED')
        if (not isinstance(self.treatment_one_probabilities,tuple)
            or not self.treatment_one_probabilities
            or any(type(p) is not str or p!=_fraction_str(p)
                   for p in self.treatment_one_probabilities)):
            raise ValueError('NODEWISE_MIXTURE_EXACT_COMPONENT_PROPENSITIES_REQUIRED')


@dataclass(frozen=True)
class NodewiseMixturePretreatmentProfileV28P2:
    label:str
    mass:str
    node_binary_features:tuple[int,...]
    components:tuple[ConditionalBernoulliComponentV28P2,...]

    def __post_init__(self):
        if not isinstance(self.label,str) or not self.label.strip():
            raise ValueError('NODEWISE_MIXTURE_PROFILE_LABEL_REQUIRED')
        if type(self.mass) is not str or self.mass!=_fraction_str(self.mass,positive=True):
            raise ValueError('NODEWISE_MIXTURE_PROFILE_EXACT_MASS_REQUIRED')
        if (not isinstance(self.node_binary_features,tuple) or not self.node_binary_features
            or any(type(x) is not int or x not in (0,1) for x in self.node_binary_features)):
            raise ValueError('NODEWISE_MIXTURE_PRETREATMENT_BINARY_FEATURES_REQUIRED')
        if (not isinstance(self.components,tuple) or not 1<=len(self.components)<=MAX_CONDITIONAL_COMPONENTS
            or any(not isinstance(c,ConditionalBernoulliComponentV28P2)
                   or len(c.treatment_one_probabilities)!=len(self.node_binary_features)
                   for c in self.components)
            or sum((Fraction(c.weight) for c in self.components),Fraction(0))!=1):
            raise ValueError('NODEWISE_MIXTURE_COMPONENT_MASS_OR_DIMENSION_INVALID')
        # Canonical order avoids ambiguous representations; distinct components
        # are not a claim of unique statistical mixture identifiability.
        ps=tuple(c.treatment_one_probabilities for c in self.components)
        if ps!=tuple(sorted(set(ps))):
            raise ValueError('NODEWISE_MIXTURE_COMPONENTS_NOT_UNIQUE_SORTED')


@dataclass(frozen=True)
class NodewiseLocalArmPopulationV28:
    source_id:str
    provenance:str
    admission:Literal['ADMITTED','CERTIFIED','PROPOSED','UNRESOLVED']
    availability:Literal['SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE_ESTIMATE']
    study_scope_digest:str
    protocol_digest:str
    node_order:tuple[str,...]
    outcome:str
    context:str
    feature_name:str
    signature_fingerprint:str
    covariate_schema_fingerprint:str
    profiles:tuple[NodewisePretreatmentProfileV28 | NodewiseMixturePretreatmentProfileV28P2,...]
    # (node, own-pre-X, number-of-neighbors-pre-X=1, own-treatment, exposure)
    covered_cells:tuple[tuple[str,int,int,int,int],...]
    covariate_timing:Literal['DECLARED_PRETREATMENT']='DECLARED_PRETREATMENT'
    adjustment_kind:str=ADJUSTMENT
    factorization_kind:str=A4_LAW
    operator:str=A4_OP

    def __post_init__(self):
        if any(not isinstance(getattr(self,key),str) or not getattr(self,key).strip()
               for key in ('source_id','provenance','study_scope_digest','protocol_digest',
                           'outcome','context','feature_name','signature_fingerprint',
                           'covariate_schema_fingerprint')):
            raise ValueError('NODEWISE_A4_COORDINATES_AND_PROVENANCE_REQUIRED')
        if (not isinstance(self.node_order,tuple) or not 0<len(self.node_order)<=MAX_NODE_COUNT
            or len(set(self.node_order))!=len(self.node_order)):
            raise ValueError('NODEWISE_A4_NODE_RESOURCE_GUARD')
        if not isinstance(self.profiles,tuple) or not 0<len(self.profiles)<=MAX_PROFILES:
            raise ValueError('NODEWISE_A4_PROFILE_RESOURCE_GUARD')
        if self.factorization_kind==A4_LAW and self.operator==A4_OP:
            profile_type=NodewisePretreatmentProfileV28
        elif (self.factorization_kind==CONDITIONAL_MIXTURE_LAW
              and self.operator==CONDITIONAL_MIXTURE_OPERATOR):
            profile_type=NodewiseMixturePretreatmentProfileV28P2
        else:
            raise ValueError('NODEWISE_A4_UNKNOWN_OPERATOR_OR_FACTORIZATION')
        if any(type(p) is not profile_type for p in self.profiles):
            raise ValueError('NODEWISE_A4_PROFILE_TYPE_DOES_NOT_MATCH_LAW')
        if any(len(p.node_binary_features)!=len(self.node_order) for p in self.profiles):
            raise ValueError('NODEWISE_A4_PROFILE_NODE_COVERAGE_REQUIRED')
        if (tuple(p.label for p in self.profiles)!=tuple(sorted(set(p.label for p in self.profiles)))
            or len(set(p.node_binary_features for p in self.profiles))!=len(self.profiles)):
            raise ValueError('NODEWISE_A4_PROFILE_UNIQUE_SORTED_REQUIRED')
        if sum((Fraction(p.mass) for p in self.profiles),Fraction(0))!=1:
            raise ValueError('NODEWISE_A4_PROFILE_MASSES_NOT_NORMALIZED')
        if (self.covariate_timing!='DECLARED_PRETREATMENT' or self.adjustment_kind!=ADJUSTMENT
            or self.factorization_kind not in (A4_LAW,CONDITIONAL_MIXTURE_LAW)
            or self.operator not in (A4_OP,CONDITIONAL_MIXTURE_OPERATOR)):
            raise ValueError('NODEWISE_A4_UNKNOWN_OPERATOR_OR_POSTTREATMENT_COVARIATE')
        if not isinstance(self.covered_cells,tuple) or len(self.covered_cells)>MAX_COVERED_CELLS:
            raise ValueError('NODEWISE_A4_IMMUTABLE_CELL_COVERAGE_OR_RESOURCE_GUARD')
        pos={n:i for i,n in enumerate(self.node_order)}
        prev=None
        for cell in self.covered_cells:
            if (not isinstance(cell,tuple) or len(cell)!=5 or cell[0] not in pos
                or any(type(v) is not int for v in cell[1:])
                or cell[1] not in (0,1) or cell[2]<0 or cell[3] not in (0,1)
                or cell[4]<0):
                raise ValueError('NODEWISE_A4_INVALID_CELL_COORDINATES')
            key=(pos[cell[0]],*cell[1:])
            if prev is not None and key<=prev:
                raise ValueError('NODEWISE_A4_CELLS_NOT_UNIQUE_SORTED')
            prev=key

    @property
    def observational_law_fingerprint(self):
        return _sha(dict(version=('NODEWISE_OBSERVATIONAL_X_AND_T_LAW_V1'
                                  if self.factorization_kind==A4_LAW
                                  else 'NODEWISE_OBSERVATIONAL_X_AND_T_MIXTURE_LAW_V1'),
            scope=self.study_scope_digest,protocol=self.protocol_digest,
            schema=self.covariate_schema_fingerprint,
            profiles=[asdict(p) for p in self.profiles]))

    @property
    def target_population_fingerprint(self):
        # Target identity depends on pretreatment X law, NOT observational propensities.
        return _sha(dict(version='NODEWISE_TARGET_X_POPULATION_V1',
            scope=self.study_scope_digest,protocol=self.protocol_digest,
            schema=self.covariate_schema_fingerprint,
            profiles=[(p.label,p.mass,p.node_binary_features) for p in self.profiles]))


def declare_nodewise_local_arm_population_v28(study,signature,*,source_id,provenance,
        feature_name,profiles,covered_cells,admission='ADMITTED',
        availability='SYMBOLIC_POPULATION_OPERATOR'):
    if not isinstance(study,NetworkStudyContextV17) or study.observation_regime!='observational' or study.design() is not None:
        raise ValueError('NODEWISE_A4_OBSERVATIONAL_STUDY_REQUIRED')
    if not isinstance(signature,SignatureSpecV20) or signature.study_scope_digest!=study.shared_scope_digest:
        raise ValueError('NODEWISE_A4_SIGNATURE_MISMATCH')
    if not isinstance(feature_name,str) or not feature_name.strip():
        raise ValueError('NODEWISE_A4_FEATURE_NAME_REQUIRED')
    rows=[]
    for label,mass,feature_vec,propensities in profiles:
        if isinstance(feature_vec,dict):
            if set(feature_vec)!=set(study.node_order):
                raise ValueError('NODEWISE_A4_COMPLETE_X_VECTOR_REQUIRED')
            feature_vec=tuple(feature_vec[n] for n in study.node_order)
        if isinstance(propensities,dict):
            if set(propensities)!=set(study.node_order):
                raise ValueError('NODEWISE_A4_COMPLETE_PROPENSITY_VECTOR_REQUIRED')
            propensities=tuple(propensities[n] for n in study.node_order)
        rows.append(NodewisePretreatmentProfileV28(label,_fraction_str(mass,positive=True),
            tuple(feature_vec),tuple(_fraction_str(p) for p in propensities)))
    rows.sort(key=lambda p:p.label)
    nodes={n:i for i,n in enumerate(study.node_order)}
    cells=tuple(sorted((tuple(c) for c in covered_cells),key=lambda c:(nodes[c[0]],*c[1:])))
    return NodewiseLocalArmPopulationV28(source_id,provenance,admission,availability,
        study.shared_scope_digest,study.protocol_digest,study.node_order,
        study.outcome_variable,study.context_reference,feature_name,
        signature.signature_fingerprint,_schema(study,signature,feature_name),
        tuple(rows),cells)


@dataclass(frozen=True)
class ScopedNodewiseAdjustmentA5V28:
    study_scope_digest:str
    signature_fingerprint:str
    covariate_schema_fingerprint:str
    covered_nodes:tuple[str,...]
    potential_outcome_exposure_sufficiency:Assumption
    local_covariate_exposure_mean_exchangeability:Assumption

    def __post_init__(self):
        if (not isinstance(self.study_scope_digest,str) or not self.study_scope_digest
            or not isinstance(self.signature_fingerprint,str) or not self.signature_fingerprint
            or not isinstance(self.covariate_schema_fingerprint,str) or not self.covariate_schema_fingerprint
            or not isinstance(self.covered_nodes,tuple) or not self.covered_nodes
            or len(set(self.covered_nodes))!=len(self.covered_nodes)):
            raise ValueError('NODEWISE_SCOPED_A5_INVALID')


def admit_nodewise_adjustment_a5_v28(study,signature,*,feature_name,covered_nodes,
        potential_outcome_exposure_sufficiency,local_covariate_exposure_mean_exchangeability):
    return ScopedNodewiseAdjustmentA5V28(study.shared_scope_digest,
        signature.signature_fingerprint,_schema(study,signature,feature_name),
        tuple(covered_nodes),potential_outcome_exposure_sufficiency,
        local_covariate_exposure_mean_exchangeability)


@dataclass(frozen=True)
class NodewiseAdjustedProofV28:
    kind:Literal['DIRECT','SPILLOVER','TOTAL']
    terms:tuple[ArmLinearTerm,...]
    # Each row: (node,own-treatment,exposure,((own-X,neighbor-X-count,P(C_i),P(arm|C_i)),...))
    support_by_term:tuple[tuple[str,int,int,tuple[tuple[int,int,str,str],...]],...]
    identified_functional:str
    target_fingerprint:str

    def summary(self):
        return dict(kind=self.kind,arm_terms=[t.json_payload() for t in self.terms],
            support_by_term=[dict(node=n,own_treatment=a,exposure=s,
                local_strata=[dict(own_pretreatment_covariate=x,neighbor_covariate_count=k,
                                   population_mass=m,arm_support=p) for x,k,m,p in strata])
                for n,a,s,strata in self.support_by_term],
            identified_functional=self.identified_functional,
            target_fingerprint=self.target_fingerprint)


@dataclass(frozen=True)
class VerifiedNodewiseAdjustedEffectsV28:
    study:NetworkStudyContextV17
    source:NodewiseLocalArmPopulationV28
    signature:SignatureSpecV20
    assumptions:tuple[Assumption,...]
    license:ScopedNodewiseAdjustmentA5V28
    requests:tuple[EffectQueryV18,...]
    proofs:tuple[NodewiseAdjustedProofV28,...]
    certificate_sha256:str
    route:Literal['R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS']=ROUTE
    theorem_id:str=THEOREM
    contract_version:str=VERSION
    status:Literal['POINT']='POINT'
    verification_status:Literal['VERIFIED']='VERIFIED'
    estimation_request:None=None

    def summary(self):
        answer=dict(route=self.route,theorem_id=self.theorem_id,
            contract_version=self.contract_version,status=self.status,
            verification_status=self.verification_status,
            source_id=self.source.source_id,A4_operator=self.source.operator,
            observational_law_fingerprint=self.source.observational_law_fingerprint,
            target_semantics='NODEWISE_LOCAL_COVARIATE_ADJUSTED_EXPOSURE_POTENTIAL_OUTCOME',
            adjustment_schema=dict(own_pretreatment_feature=self.source.feature_name,
                neighbor_summary='count of undirected neighbors with pre-treatment X=1'),
            full_vector_exchangeability_required=False,
            exposure_sufficiency_required=True,
            assumptions_used=list(BASIC_A5)+['potential_outcome_exposure_sufficiency',
                'local_covariate_exposure_mean_exchangeability'],
            results=[p.summary() for p in self.proofs],
            certificate_sha256=self.certificate_sha256,
            estimator_capability='NO_ADAPTER',estimation_request=None,
            scientific_assumptions_verified_in_real_world=False,
            note='Exact population nodewise local-covariate G-formula; NOT p-standardized, '
                 'NOT a fixed policy value; no empirical estimator or general Network Auto-G.')
        if self.source.factorization_kind==CONDITIONAL_MIXTURE_LAW:
            answer['conditional_assignment_law']=self.source.factorization_kind
        return answer


def _validate(study,source,signature,assumptions,license):
    try:
        st=NetworkStudyContextV17(**asdict(study))
        profile_rows=[]
        for p in source.profiles:
            if isinstance(p,NodewiseMixturePretreatmentProfileV28P2):
                row=asdict(p)
                row['components']=tuple(ConditionalBernoulliComponentV28P2(**asdict(c))
                                        for c in p.components)
                profile_rows.append(NodewiseMixturePretreatmentProfileV28P2(**row))
            else:
                profile_rows.append(NodewisePretreatmentProfileV28(**asdict(p)))
        src=NodewiseLocalArmPopulationV28(**{**asdict(source),
            'profiles':tuple(profile_rows)})
        sig=SignatureSpecV20(**asdict(signature))
        lic=ScopedNodewiseAdjustmentA5V28(license.study_scope_digest,
            license.signature_fingerprint,license.covariate_schema_fingerprint,
            tuple(license.covered_nodes),license.potential_outcome_exposure_sufficiency,
            license.local_covariate_exposure_mean_exchangeability)
    except (ValueError,TypeError,AttributeError) as exc:
        raise R3Unavailable('NODEWISE_NONCANONICAL_TYPED_INPUT') from exc
    if (st!=study or src!=source or sig!=signature or lic!=license):
        raise R3Unavailable('NODEWISE_NONCANONICAL_TYPED_INPUT')
    if st.observation_regime!='observational' or st.design() is not None:
        raise R3Unavailable('NODEWISE_OBSERVATIONAL_STUDY_REQUIRED')
    if st.graph_timing_claim!='DECLARED_PRETREATMENT_FIXED':
        raise R3Unavailable('NETWORK_PRETREATMENT_STATUS_UNRESOLVED')
    if (src.study_scope_digest!=st.shared_scope_digest or src.protocol_digest!=st.protocol_digest
        or src.node_order!=st.node_order or src.outcome!=st.outcome_variable
        or src.context!=st.context_reference or src.signature_fingerprint!=sig.signature_fingerprint
        or src.covariate_schema_fingerprint!=_schema(st,sig,src.feature_name)
        or lic.study_scope_digest!=st.shared_scope_digest or lic.signature_fingerprint!=sig.signature_fingerprint
        or lic.covariate_schema_fingerprint!=src.covariate_schema_fingerprint):
        raise R3Unavailable('NODEWISE_STUDY_SIGNATURE_COVARIATE_OR_A4_MISMATCH')
    if src.admission not in ('ADMITTED','CERTIFIED'):
        raise R3Unavailable('A4_NODEWISE_SOURCE_NOT_ADMITTED')
    if src.availability!='SYMBOLIC_POPULATION_OPERATOR':
        raise R3Unavailable('A4_NODEWISE_POPULATION_OPERATOR_REQUIRED')
    if not isinstance(assumptions,tuple):
        raise R3Unavailable('NODEWISE_TYPED_ASSUMPTIONS_REQUIRED')
    seen={}
    for a in assumptions:
        if not isinstance(a,Assumption) or a.name in seen:
            raise R3Unavailable('NODEWISE_DUPLICATE_OR_INVALID_ASSUMPTIONS')
        seen[a.name]=a
    if any(k in seen for k in ('known_assignment_law','full_vector_randomization')):
        raise R3Unavailable('RANDOMIZATION_IS_NOT_OBSERVATIONAL_IGNORABILITY')
    for name in BASIC_A5:
        _require_assumption(seen.get(name),name)
    _require_assumption(lic.potential_outcome_exposure_sufficiency,'potential_outcome_exposure_sufficiency')
    _require_assumption(lic.local_covariate_exposure_mean_exchangeability,
                        'local_covariate_exposure_mean_exchangeability')
    return st,src,sig,lic


def _profile_local(st,profile,neighbors,positions,node):
    return (profile.node_binary_features[positions[node]],
            sum(profile.node_binary_features[positions[j]] for j in neighbors[node]))


def _local_masses(st,src,neighbors,positions,used_nodes):
    masses={}
    for node in used_nodes:
        cells={}
        for p in src.profiles:
            c=_profile_local(st,p,neighbors,positions,node)
            cells[c]=cells.get(c,Fraction(0))+Fraction(p.mass)
        masses[node]=cells
    return masses


def _profile_treatment_components(profile):
    if isinstance(profile,NodewiseMixturePretreatmentProfileV28P2):
        return tuple((Fraction(c.weight),tuple(map(Fraction,c.treatment_one_probabilities)))
                     for c in profile.components)
    return ((Fraction(1),tuple(map(Fraction,profile.treatment_one_probabilities))),)


def _solve(study,source,signature,assumptions,license,requests):
    st,src,sig,lic=_validate(study,source,signature,assumptions,license)
    if not isinstance(requests,tuple) or not requests:
        raise R3Unavailable('NODEWISE_EFFECT_QUERIES_REQUIRED')
    terms_by_query=tuple(_canonical_terms(st,q) for q in requests)
    required={t.node_id for terms in terms_by_query for t in terms}
    if not required <= set(lic.covered_nodes) or not set(lic.covered_nodes)<=set(st.node_order):
        raise R3Unavailable('NODEWISE_A5_NODE_COVERAGE_MISSING')
    exp=_validated_exposure_signature(st,sig,required)
    neighbors=_neighbors(st)
    erefs=_exposure_refs(st,sig)
    positions={n:i for i,n in enumerate(st.node_order)}
    for n in required:
        if len(erefs[n])>MAX_REFERENCE_DEGREE:
            raise R3Unavailable('NODEWISE_EXPOSURE_SUPPORT_RESOURCE_GUARD',n)
        if len(neighbors[n])>MAX_REFERENCE_DEGREE:
            raise R3Unavailable('NODEWISE_LOCAL_COVARIATE_RESOURCE_GUARD',n)
    used={t.coordinates for terms in terms_by_query for t in terms}
    all_masses=_local_masses(st,src,neighbors,positions,
        {t[0] for t in used}|{c[0] for c in src.covered_cells})
    # A4 may include unused cells, but no claimed conditional operator may
    # condition on an impossible local stratum or an undefined exposure state.
    for n,x,k,a,s in src.covered_cells:
        if k>len(neighbors[n]) or s not in exp.states_for_degree(len(erefs[n])) or (
            sig.grouping=='three_level_treated_neighbor_fraction' and len(erefs[n])==0):
            raise R3Unavailable('A4_NODEWISE_UNDEFINED_COVARIATE_OR_EXPOSURE_CELL',str((n,x,k,a,s)))
        if (x,k) not in all_masses[n]:
            raise R3Unavailable('A4_NODEWISE_NONPOPULATION_COVARIATE_CELL',str((n,x,k)))
    masses={n:all_masses[n] for n in {t[0] for t in used}}
    needed={(n,x,k,a,s) for n,a,s in used for x,k in masses[n]}
    if not needed<=set(src.covered_cells):
        raise R3Unavailable('A4_NODEWISE_CONDITIONAL_MEANS_MISSING',str(sorted(needed-set(src.covered_cells))[:3]))
    all_support={}
    for n,a,s in sorted(used,key=lambda item:(positions[item[0]],item[1],item[2])):
        if s not in exp.states_for_degree(len(erefs[n])):
            raise R3Unavailable('NODEWISE_INVALID_TARGET_EXPOSURE',str((n,a,s)))
        joint={c:Fraction(0) for c in masses[n]}
        for profile in src.profiles:
            c=_profile_local(st,profile,neighbors,positions,n)
            for component_mass,probs in _profile_treatment_components(profile):
                dist=_primary_support(probs,probs[positions[n]],a,
                    tuple(positions[j] for j in erefs[n]),exp)
                joint[c]+=Fraction(profile.mass)*component_mass*dist.get(s,Fraction(0))
        rows=[]
        for (x,k),m in sorted(masses[n].items()):
            if joint[(x,k)]<=0:
                raise R3Unavailable('ZERO_NODEWISE_COVARIATE_STRATUM_SUPPORT',f'{n}:{x},{k},{a},{s}')
            rows.append((x,k,str(m),str(joint[(x,k)]/m)))
        all_support[(n,a,s)]=tuple(rows)
    proofs=[]
    for req,terms in zip(requests,terms_by_query):
        out=[]
        for term in terms:
            inner=' + '.join(f'({mass}) * E[Y_{term.node_id}^obs | '
                f'T_{term.node_id}={term.own_treatment},S_{term.node_id}^g={term.exposure_state},'
                f'{src.feature_name}_{term.node_id}={x},'
                f'neighbor_positive_{src.feature_name}_count={k},{st.context_reference}]'
                for x,k,mass,_ in all_support[term.coordinates])
            out.append(f'({term.coefficient}) * ({inner})')
        # No P(T|X,W) in a causal target identity.
        fp=_sha(dict(version='R3_NODEWISE_EXPOSURE_POTENTIAL_OUTCOME_TARGET_V1',
            scope=st.shared_scope_digest,signature=sig.signature_fingerprint,
            covariate_schema=src.covariate_schema_fingerprint,
            target_population=src.target_population_fingerprint,
            terms=[term.json_payload() for term in terms]))
        proofs.append(NodewiseAdjustedProofV28(req.kind,terms,tuple(
            (n,a,s,all_support[(n,a,s)]) for n,a,s in (t.coordinates for t in terms)),
            ' + '.join(out),fp))
    result=VerifiedNodewiseAdjustedEffectsV28(st,src,sig,assumptions,lic,requests,tuple(proofs),'')
    return replace(result,certificate_sha256=_sha(_payload(result)))


def _payload(value):
    payload=asdict(value);payload.pop('certificate_sha256',None)
    return payload


def _independent_local_support_verifier(result):
    # Reverse-convolution oracle never calls primary support engine/ExposureSpec.
    neighbors={node:set() for node in result.study.node_order}
    for a,b in result.study.undirected_edges:
        neighbors[a].add(b);neighbors[b].add(a)
    refs=({n:set(c) for n,c in result.signature.core_collaborators}
          if result.signature.grouping=='pretreatment_core_collaborator_majority'
          else neighbors)
    positions={node:i for i,node in enumerate(result.study.node_order)}
    for proof in result.proofs:
        for n,a,s,rows in proof.support_by_term:
            local={}
            totals={}
            for profile in result.source.profiles:
                features=profile.node_binary_features
                key=(features[positions[n]],sum(features[positions[j]] for j in neighbors[n]))
                mass=Fraction(profile.mass)
                totals[key]=totals.get(key,Fraction(0))+mass
                if isinstance(profile,NodewiseMixturePretreatmentProfileV28P2):
                    component_rows=((Fraction(c.weight),c.treatment_one_probabilities)
                                    for c in profile.components)
                else:
                    component_rows=((Fraction(1),profile.treatment_one_probabilities),)
                for mix_weight,probability_row in component_rows:
                    probs={node:Fraction(p) for node,p in zip(result.study.node_order,
                                      probability_row)}
                    counts={0:Fraction(1)}
                    for j in sorted(refs[n],reverse=True):
                        next_counts={}
                        for k,v in counts.items():
                            next_counts[k]=next_counts.get(k,Fraction(0))+v*(1-probs[j])
                            next_counts[k+1]=next_counts.get(k+1,Fraction(0))+v*probs[j]
                        counts=next_counts
                    own=probs[n] if a else 1-probs[n]
                    conditional=own*sum((v for k,v in counts.items()
                        if _manual_exposure_classify_v26(k,len(refs[n]),result.signature.grouping)==s),Fraction(0))
                    local[key]=local.get(key,Fraction(0))+mass*mix_weight*conditional
            expected=tuple((x,k,str(totals[(x,k)]),str(local[(x,k)]/totals[(x,k)]))
                for x,k in sorted(totals))
            if rows!=expected or any(Fraction(row[3])<=0 for row in rows):
                raise R3Unavailable('NODEWISE_INDEPENDENT_LOCAL_SUPPORT_MISMATCH',f'{n},{a},{s}')


def identify_observational_nodewise_effects_v28(study,source,signature,*,assumptions,license,requests):
    result=_solve(study,source,signature,assumptions,license,requests)
    replay_observational_nodewise_effects_v28(result)
    return result


def replay_observational_nodewise_effects_v28(result):
    if not isinstance(result,VerifiedNodewiseAdjustedEffectsV28):
        raise R3Unavailable('NODEWISE_TYPED_VERIFIED_RESULT_REQUIRED')
    if (result.route!=ROUTE or result.theorem_id!=THEOREM or result.contract_version!=VERSION
        or result.status!='POINT' or result.verification_status!='VERIFIED'
        or result.estimation_request is not None):
        raise R3Unavailable('NODEWISE_RESULT_ENVELOPE_INVALID')
    if result.certificate_sha256!=_sha(_payload(result)):
        raise R3Unavailable('NODEWISE_CERTIFICATE_DIGEST_MISMATCH')
    if result!=_solve(result.study,result.source,result.signature,result.assumptions,
                      result.license,result.requests):
        raise R3Unavailable('NODEWISE_CERTIFICATE_REPLAY_MISMATCH')
    _independent_local_support_verifier(result)
    return True


def requirements_for_nodewise_adjustment_v28():
    return dict(route=ROUTE, target_semantics='E[Y_i(a,s)|W] nodewise X_i,neighbor-X-count adjusted',
        required_names=list(BASIC_A5)+['potential_outcome_exposure_sufficiency',
                                      'local_covariate_exposure_mean_exchangeability'],
        A4_required='exact P(X-vector|W), factorized P(T|X,W), typed E[Yobs|Ti,Si,Ci,W]',
        A6_required='positive arm support at each positive-mass node-specific C_i',
        no_assumption_discovery=True,scientific_validity_certified_by_software=False,
        estimator_capability='NO_ADAPTER')


def implemented_assumption_catalog_v28():
    """Opt-in v2.8 extension; preserve both v2.7 P0 and P2 public catalogs."""
    from .identification_observational_exposure_adjustment import implemented_assumption_catalog_v27p2
    old=implemented_assumption_catalog_v27p2()
    new=dict(name='local_covariate_exposure_mean_exchangeability',layer='A5_OBSERVATIONAL',
        description='E[Y_i(a,s)|Ti=a,Si=s,C_i,W]=E[Y_i(a,s)|C_i,W] '
                    'where C_i=(X_i, neighbor positive X count).',
        scientific_scope='R3 v2.8 node-specific local covariate adjustment only.',
        machine_verifiability='Scoped license checked; scientific truth not proven.')
    return {**old,
        'contract':'CFM-ID-IMPLEMENTED-ASSUMPTIONS-v2.8-NODEWISE',
        'assumptions':old['assumptions']+[new],
        'route_ids':old['route_ids']+[ROUTE],
        'legacy_catalog_unchanged':True}


__all__=[
    'NodewisePretreatmentProfileV28','NodewiseLocalArmPopulationV28',
    'ConditionalBernoulliComponentV28P2','NodewiseMixturePretreatmentProfileV28P2',
    'CONDITIONAL_MIXTURE_LAW','CONDITIONAL_MIXTURE_OPERATOR',
    'ScopedNodewiseAdjustmentA5V28','NodewiseAdjustedProofV28','VerifiedNodewiseAdjustedEffectsV28',
    'declare_nodewise_local_arm_population_v28','admit_nodewise_adjustment_a5_v28',
    'identify_observational_nodewise_effects_v28','replay_observational_nodewise_effects_v28',
    'requirements_for_nodewise_adjustment_v28',
    'implemented_assumption_catalog_v28',
]
