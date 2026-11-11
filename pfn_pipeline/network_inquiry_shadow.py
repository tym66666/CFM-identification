"""Opt-in non-arm Network Inquiry Shadow (v1.7).

Only one new path is added: fixed-full-assignment mean *candidate* inquiries
without first constructing a randomized arm TaskSpec. Existing TaskSpec,
identify(), A4 arm Shadow, Batch, Estimation and Policy stay authoritative.
This module describes A1/A4/A5/A6 preflight conditions, NEVER identifies Q.

Supported study scopes: finite, undirected, simple fixed networks; binary T,
one outcome variable and symbolic fixed-W conditional means. A known q may use
only the existing D1/D2/D3 exact design objects. Neither q nor information
availability establishes causal randomization. Observational policy inquiries
are expressible but have NO registered theorem backend here.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from fractions import Fraction
import json
from typing import Literal

from .contracts import TaskSpec
from ._internal.identification.schemas import (
    Assumption, AssumptionStatus, NetworkExposureSpec,
    CompleteRandomizationDesignV1, TwoGroupFixedQuotaDesignV1,
    HeterogeneousBernoulliDesignV1, ClusterBernoulliDesignV24, MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1,
)
from ._internal.identification.randomized_arm_family import AssignmentSpec
from ._internal.identification.randomized_network_arm import REQUIRED
from .identification_a4_shadow import _require_arm, _sha
from .identification_route_shadow import (
    TargetSemanticsV15, RequiredObservableV15, FIXED_POLICY_CANDIDATE,
    required_observable_for,
)

VERSION = 'non-arm-network-inquiry-shadow-v1.7'
OBSERVATIONAL_CANDIDATE = 'observational_network_fixed_policy_research_candidate_v0'
_DESIGNS = {
    'heterogeneous_bernoulli_binary_v1': HeterogeneousBernoulliDesignV1,
    'complete_randomization_binary_v1': CompleteRandomizationDesignV1,
    'two_group_fixed_quota_binary_v1': TwoGroupFixedQuotaDesignV1,
    'cluster_bernoulli_binary_v2_4': ClusterBernoulliDesignV24,
    'multi_group_fixed_quota_binary_v2_5': MultiGroupFixedQuotaDesignV25,
    'two_stage_quota_mixture_binary_v2_7': TwoStageQuotaMixtureDesignV27,
    'unequal_probability_fixed_quota_binary_v1': UnequalProbabilityFixedQuotaDesignV1,
    'rerandomized_balanced_binary_v1': RerandomizedBalancedDesignV1,
}
_OPERATORS = {'ASSIGNMENT_NODE_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW',
              'NODE_ARM_MEANS', 'PAIRWISE_MARGINALS'}
_ADMISSIONS = {'CERTIFIED', 'ADMITTED', 'PROPOSED', 'UNRESOLVED',
               'NOT_ADMITTED', 'CONTRADICTED'}
_AVAILABILITY = {'SYMBOLIC_POPULATION_OPERATOR', 'EXACT_POPULATION_VALUE',
                 'FINITE_SAMPLE_ESTIMATE'}
_TRUSTED_QUERY = {'HUMAN_CONFIRMED', 'TRUSTED_FIXTURE'}
_ADMITTED_ASSUMPTION = {AssumptionStatus.CERTIFIED, AssumptionStatus.ADMITTED,
                       AssumptionStatus.DERIVED}


def _nonblank(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} requires a nonempty string')


def _make_design(value):
    if value is None:
        return None
    if not isinstance(value, dict) or value.get('kind') not in _DESIGNS:
        raise ValueError('Only an explicit D1/D2/D3/D4/D5/D6 assignment design is accepted')
    return _DESIGNS[value['kind']].model_validate(value)


@dataclass(frozen=True)
class NetworkStudyContextV17:
    """A2/A3 scientific scope and A4 protocol facts, but NO Q, exposure or A5.

    assignment_design_json is canonical validated *declared* design data, or
    None when q is not supplied. No q is inferred from observational records.
    The scope and protocol digests distinguish identity, not source truth.
    """
    network_id: str
    node_order: tuple[str, ...]
    undirected_edges: tuple[tuple[str, str], ...]
    treatment_variable: str
    outcome_variable: str
    outcome_kind: Literal['continuous', 'binary']
    context_reference: str
    observation_regime: Literal['experimental', 'observational', 'unknown']
    assignment_design_json: str | None
    protocol_provenance: str
    network_provenance: str
    graph_timing_claim: Literal['DECLARED_PRETREATMENT_FIXED', 'UNRESOLVED'] = 'UNRESOLVED'

    def __post_init__(self):
        for field in ('network_id', 'treatment_variable', 'outcome_variable',
                      'context_reference', 'protocol_provenance', 'network_provenance'):
            _nonblank(getattr(self, field), field)
        if self.observation_regime not in ('experimental', 'observational', 'unknown'):
            raise ValueError('Unknown study observation regime')
        if self.outcome_kind not in ('continuous', 'binary'):
            raise ValueError('This entry only supports continuous/binary outcomes')
        if self.graph_timing_claim not in ('DECLARED_PRETREATMENT_FIXED', 'UNRESOLVED'):
            raise ValueError('Graph timing claim is not recognized')
        if not isinstance(self.node_order, tuple) or not self.node_order or any(
                not isinstance(x, str) or not x.strip() for x in self.node_order):
            raise ValueError('Explicit nonempty ordered node IDs required')
        if not isinstance(self.undirected_edges, tuple):
            raise ValueError('Undirected edges must be immutable coordinate tuples')
        net = self.network()
        if tuple(net.node_ids) != self.node_order:
            raise ValueError('Network coordinates must be preserved')
        canonical_edges = tuple(tuple(edge) for edge in net.undirected_edges)
        object.__setattr__(self, 'undirected_edges', canonical_edges)
        if self.observation_regime != 'experimental' and self.assignment_design_json is not None:
            raise ValueError('Known experimental assignment law cannot be asserted in observational/unknown mode')
        if self.assignment_design_json is not None:
            if not isinstance(self.assignment_design_json, str):
                raise ValueError('Assignment design is an immutable canonical JSON string')
            try:
                raw = json.loads(self.assignment_design_json)
                design = _make_design(raw)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError('Malformed typed assignment design') from exc
            AssignmentSpec(design)._validate_network(net)
            object.__setattr__(self, 'assignment_design_json', json.dumps(
                design.model_dump(mode='json'), sort_keys=True, separators=(',', ':'),
                ensure_ascii=False, allow_nan=False))

    def network(self) -> NetworkExposureSpec:
        # The v1 NetworkExposureSpec has a historical 'treated_neighbor_count'
        # field. Here it is used ONLY to reproduce its graph fingerprint;
        # it DOES NOT impose exposure sufficiency or an exposure-based query.
        return NetworkExposureSpec(
            network_id=self.network_id, node_ids=list(self.node_order),
            undirected_edges=list(self.undirected_edges))

    def design(self):
        return None if self.assignment_design_json is None else _make_design(
            json.loads(self.assignment_design_json))

    @property
    def network_fingerprint(self) -> str:
        return self.network().semantic_fingerprint()

    @property
    def shared_scope_digest(self) -> str:
        return _sha(dict(version='network-scope-v1.7', network_fingerprint=self.network_fingerprint,
                         nodes=self.node_order, treatment=self.treatment_variable,
                         outcome=self.outcome_variable, outcome_kind=self.outcome_kind,
                         context=self.context_reference))

    @property
    def protocol_digest(self) -> str:
        return _sha(dict(version='network-protocol-v1.7',
                         regime=self.observation_regime,
                         assignment_design=json.loads(self.assignment_design_json)
                         if self.assignment_design_json is not None else None))

    @property
    def study_digest(self) -> str:
        return _sha({'scope':self.shared_scope_digest, 'protocol':self.protocol_digest})


def declare_network_study(*, network_id: str, node_order: tuple[str, ...],
                          undirected_edges: tuple[tuple[str, str], ...],
                          treatment_variable: str, outcome_variable: str,
                          outcome_kind: str, context_reference: str,
                          observation_regime: str, assignment_design: dict | None,
                          protocol_provenance: str, network_provenance: str,
                          graph_timing_claim: str = 'UNRESOLVED') -> NetworkStudyContextV17:
    """Explicit independent entry: no arm/TaskSpec or exposure dummy is required."""
    design = _make_design(assignment_design)
    return NetworkStudyContextV17(
        network_id=network_id, node_order=tuple(node_order),
        undirected_edges=tuple(tuple(e) for e in undirected_edges),
        treatment_variable=treatment_variable, outcome_variable=outcome_variable,
        outcome_kind=outcome_kind, context_reference=context_reference,
        observation_regime=observation_regime,
        assignment_design_json=(json.dumps(design.model_dump(mode='json'),
                                            sort_keys=True, separators=(',', ':'),
                                            ensure_ascii=False) if design is not None else None),
        protocol_provenance=protocol_provenance, network_provenance=network_provenance,
        graph_timing_claim=graph_timing_claim)


def study_from_legacy_arm(task: TaskSpec) -> NetworkStudyContextV17:
    """One-way, non-authoritative study projection from an audited arm task."""
    spec, net, contract, query = _require_arm(task)
    W = spec.support_domain.get('context_symbol')
    if not W:
        raise ValueError('Legacy arm task has no explicit W context')
    result = declare_network_study(
        network_id=net.network_id, node_order=tuple(net.node_ids),
        undirected_edges=tuple(tuple(e) for e in net.undirected_edges),
        treatment_variable=query.treatment, outcome_variable=query.outcome,
        outcome_kind=task.outcome_kind, context_reference=W,
        observation_regime='experimental',
        assignment_design=contract.design.model_dump(mode='json'),
        protocol_provenance='PROJECTED_FROM_AUDITED_LEGACY_ARM_TASK',
        network_provenance='PROJECTED_FROM_AUDITED_LEGACY_ARM_TASK',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    if result.network_fingerprint != net.semantic_fingerprint():
        raise ValueError('Legacy network identity was not preserved')
    return result


def fixed_policy_target_from_context(study: NetworkStudyContextV17,
                                     assignment: tuple[int, ...], *,
                                     authority: str, resolution: str = 'RESOLVED',
                                     unit_weights: tuple[str, ...] | None = None) -> TargetSemanticsV15:
    """New A1 fixed allocation target with no dependence on q, g or arm task."""
    if unit_weights is None:
        unit_weights = tuple(str(Fraction(1, len(study.node_order))) for _ in study.node_order)
    return TargetSemanticsV15(
        kind='FIXED_FULL_ASSIGNMENT_POLICY_MEAN',
        network_fingerprint=study.network_fingerprint,
        node_order=study.node_order, outcome=study.outcome_variable,
        context=study.context_reference,
        averaging_scope='population_conditional_mean_given_W',
        authority=authority, query_resolution=resolution,
        policy_assignment=tuple(assignment), unit_weights=tuple(unit_weights))


@dataclass(frozen=True)
class NetworkA4SourceV17:
    """Reviewer-declared A4 population operator, bound to scope + protocol.

    This is NOT an authentication of external data and NOT a causal license.
    Exposing original arm summaries does not make them sufficient for policy Q.
    """
    source_id: str
    operator: Literal['ASSIGNMENT_NODE_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW',
                      'NODE_ARM_MEANS', 'PAIRWISE_MARGINALS']
    provenance: str
    admission: str
    availability: str
    regime: str
    shared_scope_digest: str
    protocol_digest: str
    node_order: tuple[str, ...]
    outcome: str
    context: str
    outcome_nodes: tuple[str, ...]
    assignment_cells: tuple[tuple[int, ...], ...] = ()
    exposure_fingerprint: str | None = None

    def __post_init__(self):
        for f in ('source_id', 'provenance', 'shared_scope_digest', 'protocol_digest',
                  'outcome', 'context'):
            _nonblank(getattr(self,f), f)
        if self.operator not in _OPERATORS or self.admission not in _ADMISSIONS or self.availability not in _AVAILABILITY:
            raise ValueError('Unrecognized A4 operator, status or availability')
        if self.regime not in ('experimental', 'observational', 'unknown'):
            raise ValueError('Unknown source observation regime')
        if (not isinstance(self.node_order, tuple) or not isinstance(self.outcome_nodes, tuple)
            or not isinstance(self.assignment_cells, tuple)
            or not self.node_order or len(set(self.node_order)) != len(self.node_order)
            or not self.outcome_nodes or len(set(self.outcome_nodes)) != len(self.outcome_nodes)
            or not set(self.outcome_nodes).issubset(self.node_order)):
            raise ValueError('Invalid A4 outcome-node coordinates')
        if self.operator == 'ASSIGNMENT_NODE_MEANS':
            if (any(not isinstance(z, tuple) for z in self.assignment_cells)
                or not self.assignment_cells or self.exposure_fingerprint is not None
                or len(set(self.assignment_cells)) != len(self.assignment_cells)
                or any(len(z) != len(self.node_order) or any(type(a) is not int or a not in (0,1) for a in z)
                       for z in self.assignment_cells)):
                raise ValueError('Exact assignment mean cells required')
        elif self.assignment_cells:
            raise ValueError('Assignment cells cannot be attached to another operator')
        if self.operator == 'NODE_ARM_MEANS' and not self.exposure_fingerprint:
            raise ValueError('Arm summary must identify its exposure definition')
        if self.operator != 'NODE_ARM_MEANS' and self.exposure_fingerprint is not None:
            raise ValueError('Only arm summaries have an exposure fingerprint')


def declare_network_a4_source(study: NetworkStudyContextV17, *,
                              source_id: str, operator: str, provenance: str,
                              admission: str, availability: str,
                              outcome_nodes: tuple[str, ...],
                              assignment_cells: tuple[tuple[int, ...], ...] = (),
                              exposure_fingerprint: str | None = None) -> NetworkA4SourceV17:
    return NetworkA4SourceV17(
        source_id=source_id, operator=operator, provenance=provenance,
        admission=admission, availability=availability,
        regime=study.observation_regime,
        shared_scope_digest=study.shared_scope_digest,
        protocol_digest=study.protocol_digest,
        node_order=study.node_order, outcome=study.outcome_variable,
        context=study.context_reference, outcome_nodes=tuple(outcome_nodes),
        assignment_cells=tuple(tuple(z) for z in assignment_cells),
        exposure_fingerprint=exposure_fingerprint)


@dataclass(frozen=True)
class NonArmSourceAssessmentV17:
    source_id: str
    source_digest: str
    information_status: str
    reason: str | None
    rule_id: str | None


@dataclass(frozen=True)
class NonArmRouteAssessmentV17:
    version: str
    study_digest: str
    study_declaration_digest: str
    assumption_evidence_digest: str
    policy_assignment_probability: str | None
    target_digest: str
    target_authority: str
    target_resolution: str
    family_id: str
    route_status: str
    target_match: str
    information_status: str
    assumption_status: str
    validity_status: str
    backend_capability: str
    required_observable: RequiredObservableV15 | None
    source_results: tuple[NonArmSourceAssessmentV17, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    mathematical_identification_from_router: None
    digest: str


def _record(payload):
    hashed = {**payload, 'required_observable':
              asdict(payload['required_observable']) if payload['required_observable'] else None,
              'source_results':tuple(asdict(x) for x in payload['source_results'])}
    return NonArmRouteAssessmentV17(**payload, digest=_sha(hashed))


def _source_assessment(study, target, src, qmass):
    ss = _sha(asdict(src))
    def result(status, reason=None, rule=None):
        return NonArmSourceAssessmentV17(src.source_id,ss,status,reason,rule)
    if (src.shared_scope_digest != study.shared_scope_digest
        or src.protocol_digest != study.protocol_digest
        or src.node_order != study.node_order
        or src.outcome != study.outcome_variable or src.context != study.context_reference
        or src.regime != study.observation_regime):
        return result('BLOCKED','SOURCE_STUDY_SCOPE_OR_PROTOCOL_MISMATCH')
    if src.admission == 'CONTRADICTED':
        return result('BLOCKED','SOURCE_CONTRADICTED')
    if src.admission not in {'CERTIFIED','ADMITTED'}:
        return result('UNRESOLVED','SOURCE_NOT_ADMITTED')
    if src.availability == 'FINITE_SAMPLE_ESTIMATE':
        return result('BLOCKED','FINITE_SAMPLE_NOT_EXACT_POPULATION_OPERATOR')
    weighted=tuple(n for n,w in zip(target.node_order,target.unit_weights) if Fraction(w)>0)
    if not set(weighted).issubset(src.outcome_nodes):
        return result('BLOCKED','WEIGHTED_OUTCOME_NODES_NOT_COVERED')
    if qmass is not None and qmass == 0:
        return result('BLOCKED','CONDITIONING_EVENT_OFF_SUPPORT')
    if src.operator == 'ASSIGNMENT_NODE_MEANS':
        if target.policy_assignment not in src.assignment_cells:
            return result('BLOCKED','POLICY_ASSIGNMENT_CELL_NOT_COVERED')
        return result('SATISFIED',rule='A4_SELECT_NODE_ASSIGNMENT_MEAN_V17')
    if src.operator == 'NODE_FULL_LAW':
        if qmass is None:
            return result('UNRESOLVED','JOINT_LAW_CONDITIONING_SUPPORT_UNRESOLVED')
        return result('SATISFIED',rule='A4_NODE_FULL_LAW_TO_ASSIGNMENT_MEAN_V17')
    if src.operator == 'FULL_JOINT_LAW':
        if set(src.outcome_nodes) != set(study.node_order):
            return result('BLOCKED','FULL_JOINT_NEEDS_ALL_NODES')
        if qmass is None:
            return result('UNRESOLVED','FULL_JOINT_CONDITIONING_SUPPORT_UNRESOLVED')
        return result('SATISFIED',rule='A4_FULL_JOINT_TO_ASSIGNMENT_MEAN_V17')
    return result('BLOCKED','ARM_OR_MARGINAL_INFORMATION_DOES_NOT_ENTAIL_POLICY_CELL')


def _assumption_assessment(assumptions: tuple[Assumption, ...], family_id: str):
    names = {}
    for a in assumptions:
        if not isinstance(a, Assumption):
            raise TypeError('Assumptions must be verified typed Assumption records')
        if a.name in names and a.model_dump(mode='json') != names[a.name].model_dump(mode='json'):
            return 'CONFLICT', ('CONFLICTING_ASSUMPTIONS:' + a.name,)
        names[a.name] = a
    if family_id == OBSERVATIONAL_CANDIDATE:
        return 'NO_REGISTERED_OBSERVATIONAL_THEOREM', ('NO_OBSERVATIONAL_CAUSAL_LICENSE_EVALUATED',)
    rejected = tuple(sorted(name for name in REQUIRED if name in names
                            and names[name].status in (AssumptionStatus.CONTRADICTED,
                                                      AssumptionStatus.NOT_ADMITTED)))
    if rejected:
        return 'REJECTED',tuple('NOT_ADMITTED:' + x for x in rejected)
    missing=tuple(sorted(set(REQUIRED)-set(name for name,rec in names.items()
                                           if rec.status in _ADMITTED_ASSUMPTION)))
    if missing:
        return 'NEEDS_INPUT',tuple('ASSUMPTION_UNRESOLVED:' + x for x in missing)
    return 'ADMITTED', ()


def assess_nonarm_network_inquiry(study: NetworkStudyContextV17,
                                  target: TargetSemanticsV15,
                                  sources: tuple[NetworkA4SourceV17, ...], *,
                                  family_id: str,
                                  assumptions: tuple[Assumption, ...] = ()) -> NonArmRouteAssessmentV17:
    """Return explanation ONLY. Never call legacy identify(), never claim POINT."""
    if not isinstance(study, NetworkStudyContextV17) or not isinstance(target, TargetSemanticsV15):
        raise TypeError('Expected explicit typed study and A1 target')
    if not isinstance(sources, tuple) or not isinstance(assumptions, tuple):
        raise TypeError('Sources and assumptions must be tuples of typed records')
    if family_id not in {FIXED_POLICY_CANDIDATE, OBSERVATIONAL_CANDIDATE}:
        raise ValueError('Only declared policy inquiry candidates supported')
    if any(not isinstance(s,NetworkA4SourceV17) for s in sources):
        raise TypeError('Typed NetworkA4SourceV17 required')
    if any(not isinstance(a,Assumption) for a in assumptions):
        raise TypeError('Typed existing Assumption records required')

    base=dict(version=VERSION, study_digest=study.study_digest,
              study_declaration_digest=_sha(asdict(study)),
              assumption_evidence_digest=_sha([a.model_dump(mode='json') for a in assumptions]),
              policy_assignment_probability=None,
              target_digest=target.target_digest, target_authority=target.authority,
              target_resolution=target.query_resolution, family_id=family_id,
              backend_capability='CANDIDATE_NOT_REGISTERED',
              required_observable=None, source_results=(), blockers=(), warnings=(),
              mathematical_identification_from_router=None)
    def out(status, target_match='MATCHED', information='NOT_EVALUATED',
            assumption='NOT_EVALUATED', validity='NOT_EVALUATED', sources_out=(),
            blockers=(), warnings=(), requirement=None, qmass_literal=None):
        return _record(dict(base, route_status=status, target_match=target_match,
                            information_status=information, assumption_status=assumption,
                            validity_status=validity, source_results=tuple(sources_out),
                            blockers=tuple(blockers), warnings=tuple(warnings),
                            required_observable=requirement,
                            policy_assignment_probability=qmass_literal))
    if (target.network_fingerprint != study.network_fingerprint
        or target.node_order != study.node_order or target.outcome != study.outcome_variable
        or target.context != study.context_reference):
        return out('SPECIFICATION_CONFLICT','CONFLICT',blockers=('TARGET_STUDY_SCOPE_MISMATCH',))
    if target.kind != 'FIXED_FULL_ASSIGNMENT_POLICY_MEAN':
        return out('FAMILY_NOT_APPLICABLE','NOT_MATCHED',blockers=('NOT_A_FIXED_POLICY_QUERY',))
    if (study.observation_regime == 'observational' and family_id != OBSERVATIONAL_CANDIDATE
        or study.observation_regime == 'experimental' and family_id != FIXED_POLICY_CANDIDATE
        or study.observation_regime == 'unknown'):
        return out('FAMILY_NOT_APPLICABLE','NOT_MATCHED',blockers=('FAMILY_AND_STUDY_REGIME_MISMATCH',))
    req=required_observable_for(target,FIXED_POLICY_CANDIDATE)
    if target.query_resolution != 'RESOLVED' or target.authority not in _TRUSTED_QUERY:
        return out('NEEDS_INPUT','UNCONFIRMED',blockers=('TARGET_UNCONFIRMED',),requirement=req)

    dedup={}
    for s in sources:
        if s.source_id in dedup and dedup[s.source_id]!=s:
            return out('SOURCE_CONFLICT',blockers=('CONFLICTING_SOURCE_ID:' + s.source_id,),requirement=req)
        dedup[s.source_id]=s
    unique=tuple(dedup[k] for k in sorted(dedup))

    qmass = None
    if study.observation_regime == 'experimental' and study.design() is not None:
        qmass=AssignmentSpec(study.design()).full_assignment_probability(
            study.network(),dict(zip(study.node_order,target.policy_assignment)))
    results=tuple(_source_assessment(study,target,s,qmass) for s in unique)
    if any(r.information_status=='SATISFIED' for r in results):
        info='SATISFIED'
    elif any(r.information_status=='UNRESOLVED' for r in results) or not results:
        info='UNRESOLVED'
    else:
        info='INSUFFICIENT'
    if qmass == 0:
        validity='OFF_SUPPORT'
    elif qmass is None:
        validity='UNRESOLVED'
    else:
        validity='POSITIVE_UNDER_DECLARED_Q'
    ass, a_issues=_assumption_assessment(assumptions,family_id)
    blockers=list(a_issues)
    if not results:
        blockers.append('NO_TYPED_POPULATION_INFORMATION_DECLARED')
    elif info=='INSUFFICIENT':
        blockers.append('NO_ENTAILMENT_TO_REQUIRED_POLICY_ASSIGNMENT_MEANS')
    elif info=='UNRESOLVED':
        blockers.append('SOURCE_STATUS_OR_CONDITIONING_SUPPORT_UNRESOLVED')
    if ass=='CONFLICT':
        status='ASSUMPTION_CONFLICT'
    elif study.observation_regime=='observational':
        blockers.append('NO_REGISTERED_OBSERVATIONAL_POLICY_THEOREM')
        status='INFORMATION_BLOCKED' if info=='INSUFFICIENT' else 'THEOREM_BACKEND_UNAVAILABLE'
    elif ass=='REJECTED':
        status='ASSUMPTIONS_NOT_ADMITTED'
    elif qmass == 0:
        blockers.extend(('POLICY_Q_DEFINED_BUT_EXPERIMENT_Q_ZERO',
                         'ALTERNATE_ASSUMPTIONS_AND_THEOREM_REQUIRED'))
        status='OFF_SUPPORT_ALTERNATE_THEOREM'
    elif ass!='ADMITTED' or study.design() is None:
        if study.design() is None:
            blockers.append('EXPERIMENTAL_ASSIGNMENT_LAW_UNRESOLVED')
        status='NEEDS_INPUT'
    elif info=='INSUFFICIENT':
        status='INFORMATION_BLOCKED'
    elif info!='SATISFIED':
        status='NEEDS_INPUT'
    else:
        blockers.append('NO_REGISTERED_GENERAL_FIXED_POLICY_THEOREM_OR_VERIFIER')
        status='THEOREM_BACKEND_UNAVAILABLE'
    warnings=('A4_SATISFIED_DOES_NOT_AUTHORIZE_CAUSAL_IDENTIFICATION',)
    return out(status,information=info,assumption=ass,validity=validity,
               sources_out=results,blockers=tuple(blockers),warnings=warnings,
               requirement=req, qmass_literal=str(qmass) if qmass is not None else None)


def replay_nonarm_network_inquiry(study: NetworkStudyContextV17,
                                  target: TargetSemanticsV15,
                                  sources: tuple[NetworkA4SourceV17, ...],
                                  saved: NonArmRouteAssessmentV17, *,
                                  assumptions: tuple[Assumption, ...] = ()) -> bool:
    """Deterministic comparison against reviewed typed inputs, not source-truth proof."""
    if not isinstance(saved, NonArmRouteAssessmentV17):
        raise ValueError('Invalid non-arm route receipt')
    expected=assess_nonarm_network_inquiry(study,target,sources,family_id=saved.family_id,
                                          assumptions=assumptions)
    if expected != saved:
        raise ValueError('Non-arm route receipt stale or altered')
    payload=asdict(saved); saved_digest=payload.pop('digest')
    if _sha(payload)!=saved_digest:
        raise ValueError('Non-arm route receipt digest mismatch')
    return True
