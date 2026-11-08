"""v2.3 opt-in R3 observational-network POINT policy identification.

Math (conditional on a FIXED pre-treatment network and W=w):
  - full-vector conditional exchangeability for every Y_i(t), consistency;
  - finite first moments, a declared exact observational population operator;
  - full-assignment positivity identifies V(z|w) without exposure sufficiency;
  - alternatively, admitted mean-signature sufficiency and positive observational
    signature-cell support identify V(z|w) even if P_obs(T=z|w)=0.

This initial backend requires an explicitly enumerated *population* distribution
P_obs(T=t|W=w), for <=12 nodes, plus the SAME source's symbolic node-conditional
outcome mean operators. It never interprets sample frequencies as population law,
never treats observed propensities as randomized treatment, does not check the
truth of ignorability/sufficiency and does not output business effect estimates.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from fractions import Fraction
from typing import Literal

from ._internal.identification.schemas import Assumption, AssumptionStatus
from ._internal.identification.randomized_arm_family import ExposureSpec
from ._internal.identification.randomized_arm_family.assignment import neighbor_set
from .identification_a4_shadow import _sha
from .identification_route_shadow import TargetSemanticsV15
from .identification_policy_r2 import SignatureSpecV20, MeanSignatureSufficiencyV20
from .network_inquiry_shadow import NetworkStudyContextV17

VERSION='r3-observational-finite-population-point-v2.3'
FULL_THEOREM='R3_OBSERVATIONAL_FULL_VECTOR_ADJUSTMENT_FIXED_W_POINT_V1'
SIGNATURE_THEOREM='R3_OBSERVATIONAL_MEAN_SIGNATURE_ADJUSTMENT_FIXED_W_POINT_V1'
MAX_FINITE_NODES=12
MAX_POPULATION_ASSIGNMENTS=4096
REQUIRED_A5=(
    'full_vector_conditional_exchangeability',
    'consistency',
    'fixed_pretreatment_network',
    'finite_conditional_first_moments',
)
APPROVED={AssumptionStatus.CERTIFIED,AssumptionStatus.ADMITTED,AssumptionStatus.DERIVED}

__all__=[
    'R3Unavailable','ObservationalFinitePopulationV23','VerifiedObservationalPolicyV23',
    'declare_observational_population_v23','identify_observational_policy_v23',
    'replay_observational_policy_v23','MAX_FINITE_NODES',
]


class R3Unavailable(ValueError):
    """Route rejection is not a mathematical proof of non-identifiability."""
    def __init__(self,reason_code:str,detail:str=''):
        self.reason_code=reason_code
        super().__init__(reason_code+(': '+detail if detail else ''))


def _require_fraction(value,*, positive=False):
    if not isinstance(value,str) or not value.strip():
        raise ValueError('Exact rational must be a nonempty string')
    result=Fraction(value)
    if positive and result<=0:
        raise ValueError('Population assignment probabilities must be strictly positive')
    return result


@dataclass(frozen=True)
class ObservationalFinitePopulationV23:
    """A4 population operator: joint assignment distribution and symbolic
    E[Y_i^obs | T=t,W=w] for *every positive* t and each declared outcome node.

    The exact allocation law is observational P(T|W), NOT an experiment q;
    a finite sample histogram is never allowed as a substitute.
    """
    source_id:str
    provenance:str
    admission:Literal['ADMITTED','CERTIFIED','PROPOSED','UNRESOLVED']
    availability:Literal['SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE_ESTIMATE']
    study_scope_digest:str
    protocol_digest:str
    node_order:tuple[str,...]
    outcome:str
    context:str
    outcome_nodes:tuple[str,...]
    assignment_masses:tuple[tuple[tuple[int,...],str],...]
    operator:Literal['OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS']='OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS'

    def __post_init__(self):
        if any(not isinstance(v,str) or not v.strip() for v in
               (self.source_id,self.provenance,self.study_scope_digest,
                self.protocol_digest,self.outcome,self.context)):
            raise ValueError('Explicit A4 source, provenance and scientific coordinates required')
        if not isinstance(self.node_order,tuple) or not self.node_order or len(set(self.node_order))!=len(self.node_order):
            raise ValueError('Explicit unique ordered nodes required')
        if not isinstance(self.outcome_nodes,tuple) or len(set(self.outcome_nodes))!=len(self.outcome_nodes) or not set(self.outcome_nodes)<=set(self.node_order):
            raise ValueError('Valid explicitly covered outcome nodes required')
        if len(self.node_order)>MAX_FINITE_NODES:
            raise ValueError('FINITE_OBSERVATIONAL_SUPPORT_ENUMERATION_LIMIT')
        if not isinstance(self.assignment_masses,tuple) or not 0<len(self.assignment_masses)<=MAX_POPULATION_ASSIGNMENTS:
            raise ValueError('Nonempty finite population distribution required')
        seen=set(); total=Fraction(0); previous=None
        for item in self.assignment_masses:
            if not isinstance(item,tuple) or len(item)!=2 or not isinstance(item[0],tuple):
                raise ValueError('Expected (complete assignment tuple, exact probability string)')
            t,p=item
            if len(t)!=len(self.node_order) or any(type(a) is not int or a not in (0,1) for a in t):
                raise ValueError('Full binary assignment and exact node coordinates required')
            if t in seen or (previous is not None and t<=previous):
                raise ValueError('Assignments must be unique and lexicographically ordered')
            seen.add(t);previous=t
            total+=_require_fraction(p,positive=True)
            if p!=str(Fraction(p)):
                raise ValueError('Use canonical exact rational probability strings')
        if total!=1:
            raise ValueError('Population observational assignment law must sum exactly to one')
        if self.operator!='OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS':
            raise ValueError('Unsupported observational A4 operator')


def declare_observational_population_v23(study:NetworkStudyContextV17,*,
        source_id:str,provenance:str,assignment_masses,
        outcome_nodes:tuple[str,...]|None=None,admission:str='ADMITTED',
        availability:str='SYMBOLIC_POPULATION_OPERATOR')->ObservationalFinitePopulationV23:
    if not isinstance(study,NetworkStudyContextV17):
        raise TypeError('Typed observational study required')
    if study.observation_regime!='observational' or study.design() is not None:
        raise ValueError('Observational population operator requires nonrandomized study context')
    cells=[]
    for assignment,p in assignment_masses:
        cells.append((tuple(assignment),str(Fraction(p))))
    cells.sort(key=lambda x:x[0])
    return ObservationalFinitePopulationV23(source_id,provenance,admission,availability,
        study.shared_scope_digest,study.protocol_digest,study.node_order,
        study.outcome_variable,study.context_reference,
        tuple(outcome_nodes) if outcome_nodes is not None else study.node_order,tuple(cells))


@dataclass(frozen=True)
class VerifiedObservationalPolicyV23:
    study:NetworkStudyContextV17
    target:TargetSemanticsV15
    source:ObservationalFinitePopulationV23
    assumptions:tuple[Assumption,...]
    signature:SignatureSpecV20|None
    sufficiency:MeanSignatureSufficiencyV20|None
    route:Literal['R3_FULL_ASSIGNMENT','R3_MEAN_SIGNATURE']
    theorem_id:str
    target_observational_probability:str
    weighted_node_classes:tuple[tuple[str,int,int|None],...]
    node_support:tuple[str,...]
    node_weights:tuple[str,...]
    identified_functional:str
    required_observables:tuple[str,...]
    target_fingerprint:str
    certificate_sha256:str
    version:str=VERSION
    status:Literal['POINT']='POINT'
    verification_status:Literal['VERIFIED']='VERIFIED'
    estimation_request:None=None

    def summary(self)->dict:
        return dict(route=self.route,theorem_id=self.theorem_id,status=self.status,
            verification_status=self.verification_status,study_digest=self.study.study_digest,
            target_fingerprint=self.target_fingerprint,
            target_observational_probability=self.target_observational_probability,
            source_id=self.source.source_id,source_operator=self.source.operator,
            signature=None if self.signature is None else self.signature.grouping,
            classes=[dict(node=n,treatment=a,signature=s,support=pi,weight=w)
                for (n,a,s),pi,w in zip(self.weighted_node_classes,self.node_support,self.node_weights)],
            identified_functional=self.identified_functional,
            required_observables=list(self.required_observables),
            assumptions_used=list(REQUIRED_A5)+(['mean_signature_sufficiency'] if self.sufficiency else []),
            certificate_sha256=self.certificate_sha256,estimation_request=None,
            warning='Observational conditional POINT depends on untestable exchangeability '
                    'and possibly mean-signature sufficiency; population symbolic source, '
                    'NOT sample estimates or empirically verified assumptions')


def _validated_assumptions(assumptions):
    if not isinstance(assumptions,tuple):
        raise R3Unavailable('TYPED_ASSUMPTIONS_REQUIRED')
    by_name={}
    for record in assumptions:
        if not isinstance(record,Assumption):
            raise R3Unavailable('INVALID_ASSUMPTION_RECORD')
        try:
            validated=Assumption.model_validate(record.model_dump(mode='json'))
        except (TypeError,ValueError) as exc:
            raise R3Unavailable('INVALID_ASSUMPTION_RECORD') from exc
        if validated.model_dump(mode='json')!=record.model_dump(mode='json'):
            raise R3Unavailable('INVALID_ASSUMPTION_RECORD')
        if validated.name in by_name:
            raise R3Unavailable('DUPLICATE_ASSUMPTION_RECORD',validated.name)
        by_name[validated.name]=validated
    if 'full_vector_randomization' in by_name or 'known_assignment_law' in by_name:
        raise R3Unavailable('RANDOMIZATION_IS_NOT_OBSERVATIONAL_IGNORABILITY')
    for name in REQUIRED_A5:
        record=by_name.get(name)
        if record is None or record.status not in APPROVED or not record.confirmed:
            raise R3Unavailable('NEEDS_INPUT','Missing admitted A5: '+name)
        if not record.evidence or not any(isinstance(e,str) and e.strip() for e in record.evidence):
            raise R3Unavailable('NEEDS_INPUT','A5 evidence missing for '+name)
        if name=='full_vector_conditional_exchangeability':
            if record.status not in {AssumptionStatus.ADMITTED,AssumptionStatus.CERTIFIED} or record.source not in {
                    'human_confirmation','domain_knowledge','demo_specification'}:
                raise R3Unavailable('NEEDS_INPUT','Observational exchangeability must be expressly admitted')
    return by_name


def _check_structural_claim(study,signature,sufficiency,needed_nodes):
    if not isinstance(signature,SignatureSpecV20) or not isinstance(sufficiency,MeanSignatureSufficiencyV20):
        raise R3Unavailable('TYPED_SIGNATURE_AND_A5_CLAIM_REQUIRED')
    if (signature.study_scope_digest!=study.shared_scope_digest
        or signature.network_fingerprint!=study.network_fingerprint
        or signature.treatment_variable!=study.treatment_variable
        or sufficiency.study_scope_digest!=study.shared_scope_digest
        or sufficiency.signature_fingerprint!=signature.signature_fingerprint):
        raise R3Unavailable('SIGNATURE_SUFFICIENCY_STUDY_MISMATCH')
    if not needed_nodes<=set(sufficiency.covered_nodes) or not set(sufficiency.covered_nodes)<=set(study.node_order):
        raise R3Unavailable('SUFFICIENCY_NODE_COVERAGE_INCOMPLETE')
    claim=sufficiency.assumption
    if not isinstance(claim,Assumption) or claim.name!='mean_signature_sufficiency':
        raise R3Unavailable('MEAN_SIGNATURE_SUFFICIENCY_NOT_ADMITTED')
    try:
        checked=Assumption.model_validate(claim.model_dump(mode='json'))
    except (ValueError,TypeError) as exc:
        raise R3Unavailable('MEAN_SIGNATURE_SUFFICIENCY_NOT_ADMITTED') from exc
    if (checked.model_dump(mode='json')!=claim.model_dump(mode='json')
        or claim.status not in {AssumptionStatus.ADMITTED,AssumptionStatus.CERTIFIED}
        or not claim.confirmed or claim.source not in {'human_confirmation','domain_knowledge','demo_specification'}
        or not claim.evidence or not any(isinstance(e,str) and e.strip() for e in claim.evidence)):
        raise R3Unavailable('MEAN_SIGNATURE_SUFFICIENCY_NOT_ADMITTED')
    return _validated_exposure_signature(study, signature, needed_nodes)


def _validated_observational_basis(study, source, assumptions):
    """Shared R3 A2/A3/A4/A5 admission gate, independent of Target class.

    Observational Policy and observational standardized-arm effects use the
    same source/protocol, exchangeability and population-operator check. No
    dummy fixed-policy target is fabricated for a non-policy inquiry.
    """
    try:
        st = NetworkStudyContextV17(**asdict(study))
        src = ObservationalFinitePopulationV23(**asdict(source))
    except (TypeError, ValueError, AttributeError) as exc:
        raise R3Unavailable('NONCANONICAL_TYPED_INPUT') from exc
    if st != study or src != source:
        raise R3Unavailable('NONCANONICAL_TYPED_INPUT')
    if st.observation_regime != 'observational' or st.design() is not None:
        raise R3Unavailable('OBSERVATIONAL_STUDY_REQUIRED')
    if st.graph_timing_claim != 'DECLARED_PRETREATMENT_FIXED':
        raise R3Unavailable('NETWORK_PRETREATMENT_STATUS_UNRESOLVED')
    if (src.study_scope_digest != st.shared_scope_digest
        or src.protocol_digest != st.protocol_digest
        or src.node_order != st.node_order or src.outcome != st.outcome_variable
        or src.context != st.context_reference):
        raise R3Unavailable('A4_STUDY_OR_PROTOCOL_MISMATCH')
    if src.admission not in {'ADMITTED', 'CERTIFIED'}:
        raise R3Unavailable('A4_SOURCE_NOT_ADMITTED')
    if src.availability != 'SYMBOLIC_POPULATION_OPERATOR':
        raise R3Unavailable('A4_POPULATION_OPERATOR_REQUIRED')
    _validated_assumptions(assumptions)
    return st, src


def _validated_exposure_signature(study, signature, needed_nodes):
    """Exposure definition only (A1/A3), NOT mean-sufficiency admission (A5)."""
    if not isinstance(signature, SignatureSpecV20):
        raise R3Unavailable('TYPED_SIGNATURE_REQUIRED')
    try:
        sig = SignatureSpecV20(**asdict(signature))
    except (TypeError, ValueError, AttributeError) as exc:
        raise R3Unavailable('INVALID_SIGNATURE') from exc
    if sig != signature or (sig.study_scope_digest != study.shared_scope_digest
        or sig.network_fingerprint != study.network_fingerprint
        or sig.treatment_variable != study.treatment_variable):
        raise R3Unavailable('SIGNATURE_STUDY_MISMATCH')
    if signature.grouping == 'pretreatment_core_collaborator_majority':
        if tuple(n for n,_ in signature.core_collaborators) != study.node_order:
            raise R3Unavailable('E3_CORE_COORDINATES_MISMATCH')
        exposure = ExposureSpec(signature.grouping,dict(signature.core_collaborators))
        try:
            for node in study.node_order:
                exposure.reference_nodes(study.network(), node)
        except (ValueError, TypeError) as exc:
            raise R3Unavailable('INVALID_PRETREATMENT_CORE_MAP') from exc
    else:
        exposure = ExposureSpec(signature.grouping)
    if signature.grouping == 'three_level_treated_neighbor_fraction':
        if any(study.network().degree_map()[n] == 0 for n in needed_nodes):
            raise R3Unavailable('UNDEFINED_EXPOSURE_FOR_POLICY_NODE')
    return exposure


def _normalized(study,target,source,assumptions,signature,sufficiency):
    st, src = _validated_observational_basis(study, source, assumptions)
    try:
        tg = TargetSemanticsV15(**asdict(target))
        sig = None if signature is None else SignatureSpecV20(**asdict(signature))
        suf = None if sufficiency is None else MeanSignatureSufficiencyV20(**asdict(sufficiency))
    except (TypeError,ValueError,AttributeError) as exc:
        raise R3Unavailable('NONCANONICAL_TYPED_INPUT') from exc
    if (tg != target or sig != signature or suf != sufficiency):
        raise R3Unavailable('NONCANONICAL_TYPED_INPUT')
    if (tg.kind!='FIXED_FULL_ASSIGNMENT_POLICY_MEAN'
        or tg.network_fingerprint!=st.network_fingerprint
        or tg.node_order!=st.node_order or tg.outcome!=st.outcome_variable
        or tg.context!=st.context_reference):
        raise R3Unavailable('TARGET_STUDY_SCOPE_MISMATCH')
    if tg.authority not in {'HUMAN_CONFIRMED','TRUSTED_FIXTURE'} or tg.query_resolution!='RESOLVED':
        raise R3Unavailable('NEEDS_INPUT','Target not resolved')
    weighted_nodes={n for n,w in zip(st.node_order,tg.unit_weights) if Fraction(w)>0}
    if not weighted_nodes:
        raise R3Unavailable('EMPTY_POLICY')
    if any(Fraction(w)<0 for w in tg.unit_weights):
        raise R3Unavailable('NEGATIVE_POLICY_WEIGHTS')
    if not weighted_nodes<=set(src.outcome_nodes):
        raise R3Unavailable('A4_WEIGHTED_OUTCOME_NODES_MISSING')
    if (signature is None)!=(sufficiency is None):
        raise R3Unavailable('SIGNATURE_AND_SUFFICIENCY_MUST_BE_PAIRED')
    return st,tg,src,sig,suf


def _solve(study,target,source,*,assumptions,signature=None,sufficiency=None):
    study,target,source,signature,sufficiency=_normalized(study,target,source,assumptions,signature,sufficiency)
    policy=target.policy_assignment
    law={t:Fraction(p) for t,p in source.assignment_masses}
    q_z=law.get(tuple(policy),Fraction(0))
    used=[]; probs=[]; weights=[]; objects=[]
    if q_z>0:
        route='R3_FULL_ASSIGNMENT'; theorem=FULL_THEOREM
        # Extraneous unneeded A5 signature is not used as identification license.
        signature=None;sufficiency=None
        for node,w in zip(study.node_order,target.unit_weights):
            fw=Fraction(w)
            if fw==0:continue
            used.append((node,policy[study.node_order.index(node)],None))
            probs.append(str(q_z));weights.append(str(fw))
            objects.append(f'E[Y_{{{node}}}^obs | T={tuple(policy)}, W={study.context_reference}]')
    else:
        if signature is None or sufficiency is None:
            raise R3Unavailable('ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT')
        route='R3_MEAN_SIGNATURE'; theorem=SIGNATURE_THEOREM
        exposure=_check_structural_claim(study,signature,sufficiency,
                      {n for n,w in zip(study.node_order,target.unit_weights) if Fraction(w)>0})
        network=study.network()
        core=dict(signature.core_collaborators) if signature.core_collaborators else None
        for node,a,w in zip(study.node_order,policy,target.unit_weights):
            fw=Fraction(w)
            if fw==0:continue
            refs=frozenset(core[node]) if core is not None else frozenset(neighbor_set(network,node))
            try:
                s_target=exposure.classify(sum(policy[study.node_order.index(j)] for j in refs),len(refs))
            except ValueError as exc:
                raise R3Unavailable('UNDEFINED_POLICY_SIGNATURE',node) from exc
            support=Fraction(0)
            for t,p in law.items():
                if t[study.node_order.index(node)]!=a:continue
                s=exposure.classify(sum(t[study.node_order.index(j)] for j in refs),len(refs))
                if s==s_target:support+=p
            if support<=0:
                raise R3Unavailable('ZERO_OBSERVATIONAL_SIGNATURE_SUPPORT',node)
            used.append((node,a,s_target));probs.append(str(support));weights.append(str(fw))
            objects.append(f'E[Y_{{{node}}}^obs | T_{{{node}}}={a}, S_{{{node}}}^g={s_target}, W={study.context_reference}]')
    if not used:
        raise R3Unavailable('EMPTY_WEIGHTED_POLICY')
    # Target identity is unchanged between R3 full / R3 signature and other routes.
    identity=_sha({'version':'r1b-target-semantics-v1.9',
                   'canonical_target':target.target_digest,
                   'intervention_variable':study.treatment_variable})
    result=VerifiedObservationalPolicyV23(
        study,target,source,assumptions,signature,sufficiency,route,theorem,str(q_z),
        tuple(used),tuple(probs),tuple(weights),
        ' + '.join(f'{w} * {m}' for w,m in zip(weights,objects)),tuple(objects),identity,'')
    return replace(result,certificate_sha256=_sha(_payload(result)))


def _payload(result):
    obj=asdict(result);obj.pop('certificate_sha256');return obj


def identify_observational_policy_v23(study:NetworkStudyContextV17,
        target:TargetSemanticsV15,source:ObservationalFinitePopulationV23,*,
        assumptions:tuple[Assumption,...],signature:SignatureSpecV20|None=None,
        sufficiency:MeanSignatureSufficiencyV20|None=None)->VerifiedObservationalPolicyV23:
    value=_solve(study,target,source,assumptions=assumptions,signature=signature,sufficiency=sufficiency)
    replay_observational_policy_v23(value)
    return value



def _manual_exposure_classify_v26(k, d, grouping):
    """Independent arithmetic A6 predicate, deliberately not ExposureSpec.classify.

    Shared by policy and contrast replay to avoid two *independent* auditors
    diverging as E4/E5 are introduced. The primary solvers use ExposureSpec.
    """
    if grouping in ('strict_majority_ties_low', 'pretreatment_core_collaborator_majority'):
        if grouping == 'pretreatment_core_collaborator_majority' and d == 0:
            raise R3Unavailable('R3_INDEPENDENT_UNDEFINED_E3')
        return int(2*k > d)
    if grouping == 'three_level_treated_neighbor_fraction':
        if d == 0:
            raise R3Unavailable('R3_INDEPENDENT_UNDEFINED_E2')
        return 0 if 3*k < d else (1 if 3*k < 2*d else 2)
    if grouping == 'exact_treated_neighbor_count':
        return k
    if grouping == 'any_treated_neighbor':
        return int(k > 0)
    raise R3Unavailable('R3_INDEPENDENT_UNKNOWN_SIGNATURE')

def _independent_observational_support_audit(value:VerifiedObservationalPolicyV23)->None:
    """Second support implementation: direct assignment-cell summation with
    hand-coded exposure predicates, not ExposureSpec or the solver's loop.
    This certifies exact A6 support *conditional on the declared A4 law*.
    """
    rows=[(tuple(t),Fraction(prob)) for t,prob in value.source.assignment_masses]
    nodes=value.study.node_order
    positions={n:i for i,n in enumerate(nodes)}
    original=sum((p for t,p in rows if t==value.target.policy_assignment),Fraction(0))
    if original!=Fraction(value.target_observational_probability):
        raise R3Unavailable('R3_INDEPENDENT_FULL_SUPPORT_MISMATCH')
    adjacency={n:set() for n in nodes}
    for a,b in value.study.undirected_edges:
        adjacency[a].add(b);adjacency[b].add(a)


    for (node,a,s),claimed in zip(value.weighted_node_classes,value.node_support):
        if value.route=='R3_FULL_ASSIGNMENT':
            independent=original
        else:
            if value.signature is None or s is None:
                raise R3Unavailable('R3_INDEPENDENT_MISSING_SIGNATURE')
            group=value.signature.grouping
            ref=(set(dict(value.signature.core_collaborators)[node])
                 if group=='pretreatment_core_collaborator_majority' else adjacency[node])
            correct=_manual_exposure_classify_v26(sum(value.target.policy_assignment[positions[u]] for u in ref),len(ref),group)
            if correct!=s:
                raise R3Unavailable('R3_INDEPENDENT_POLICY_SIGNATURE_MISMATCH')
            independent=sum((p for t,p in rows
                if t[positions[node]]==a
                and _manual_exposure_classify_v26(sum(t[positions[u]] for u in ref),len(ref),group)==s),Fraction(0))
        if independent<=0 or independent!=Fraction(claimed):
            raise R3Unavailable('R3_INDEPENDENT_OBSERVATIONAL_SUPPORT_MISMATCH',node)


def replay_observational_policy_v23(value:VerifiedObservationalPolicyV23)->bool:
    if not isinstance(value,VerifiedObservationalPolicyV23):
        raise R3Unavailable('R3_RESULT_REQUIRED')
    if _sha(_payload(value))!=value.certificate_sha256:
        raise R3Unavailable('R3_CERTIFICATE_DIGEST_MISMATCH')
    try:
        expected=_solve(value.study,value.target,value.source,assumptions=value.assumptions,
                        signature=value.signature,sufficiency=value.sufficiency)
    except R3Unavailable:
        raise
    except (ValueError,TypeError,AttributeError) as exc:
        raise R3Unavailable('R3_REPLAY_INPUT_INVALID') from exc
    if expected!=value:
        raise R3Unavailable('R3_CERTIFICATE_REPLAY_MISMATCH')
    _independent_observational_support_audit(value)
    return True
