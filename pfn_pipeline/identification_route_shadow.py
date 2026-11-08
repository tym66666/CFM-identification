"""Opt-in A1/A4/A5/A6 network-family route assessment (v1.5 research integration).

This is NOT a theorem prover, IdentificationEngine replacement, estimator gate,
or a certificate of real-world truth. It does not change identify() or other APIs.
The only executable family below is the existing randomized-network arm theorem.
A fixed full-assignment policy is a *candidate route* without a registered solver.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from fractions import Fraction
from typing import Literal

from .contracts import TaskSpec
from ._internal.identification.schemas import IdentificationSpec
from ._internal.identification.randomized_network_arm import REQUIRED, _eligibility_error
from ._internal.identification.randomized_arm_family import AssignmentSpec
from .identification_a4_shadow import (
    A4SourceV1, _refs, _require_arm, _sha, assess_a4_shadow,
)

VERSION = 'network-route-shadow-v1.5'
ARM_FAMILY = 'randomized_network_design_standardized_arm_mean_v1'
FIXED_POLICY_CANDIDATE = 'randomized_full_assignment_policy_mean_candidate_v0'
TRUSTED = {'HUMAN_CONFIRMED', 'TRUSTED_FIXTURE'}
ADMITTED = {'CERTIFIED', 'ADMITTED'}


@dataclass(frozen=True)
class RouteFamilyContractV15:
    family_id: str
    executable_in_existing_engine: bool
    target_kinds: tuple[str, ...]
    information_requirement: str
    assumption_names: tuple[str, ...]
    validity_rule: str
    verification_authority: str
    scope_note: str


def family_catalog() -> tuple[RouteFamilyContractV15, ...]:
    return (
        RouteFamilyContractV15(
            family_id=ARM_FAMILY, executable_in_existing_engine=True,
            target_kinds=('DESIGN_CONDITIONED_NODE_ARM_MEAN',),
            information_requirement='E[Y_i^obs|W,T_i=a,S_i=s]',
            assumption_names=tuple(REQUIRED),
            validity_rule='verified exact pi_i(a,s|W)>0, defined exposure, bounded software domain',
            verification_authority='existing verify_randomized_network_arm',
            scope_note='Only currently supported D1/D2/D3 × E1/E2/E3; A4 shadow not authoritative.'
        ),
        RouteFamilyContractV15(
            family_id=FIXED_POLICY_CANDIDATE, executable_in_existing_engine=False,
            target_kinds=('FIXED_FULL_ASSIGNMENT_POLICY_MEAN',),
            information_requirement='E[Y_i^obs|W,T_vector=z] for every policy-weighted node',
            assumption_names=tuple(REQUIRED),
            validity_rule='q(z|W)>0 for this randomized full-vector change-of-measure candidate',
            verification_authority='NO_REGISTERED_GENERAL_POLICY_VERIFIER',
            scope_note='Research-only candidate, not the legacy specialized policy-value backends.'
        ),
    )


@dataclass(frozen=True)
class TargetSemanticsV15:
    kind: Literal['DESIGN_CONDITIONED_NODE_ARM_MEAN', 'FIXED_FULL_ASSIGNMENT_POLICY_MEAN']
    network_fingerprint: str
    node_order: tuple[str, ...]
    outcome: str
    context: str
    averaging_scope: str
    authority: str
    query_resolution: str
    assignment_law_fingerprint: str | None = None
    exposure_fingerprint: str | None = None
    node_id: str | None = None
    arm: tuple[int, int] | None = None
    policy_assignment: tuple[int, ...] | None = None
    unit_weights: tuple[str, ...] | None = None
    target_digest: str = ''

    def __post_init__(self):
        if not self.node_order or len(set(self.node_order)) != len(self.node_order):
            raise ValueError('Target requires ordered distinct network coordinates')
        if not self.context or not self.outcome or not self.network_fingerprint:
            raise ValueError('Target requires explicit W, outcome and network identity')
        if self.averaging_scope != 'population_conditional_mean_given_W':
            raise ValueError('Only fixed-W population conditional means are supported')
        if self.kind == 'DESIGN_CONDITIONED_NODE_ARM_MEAN':
            if (not self.assignment_law_fingerprint or not self.exposure_fingerprint
                or self.node_id not in self.node_order or self.arm is None
                or self.policy_assignment is not None or self.unit_weights is not None):
                raise ValueError('Invalid design-conditioned arm target')
            if len(self.arm) != 2 or type(self.arm[0]) is not int or self.arm[0] not in (0,1) or type(self.arm[1]) is not int:
                raise ValueError('Invalid arm coordinates')
        else:
            if (self.policy_assignment is None or len(self.policy_assignment) != len(self.node_order)
                or any(type(a) is not int or a not in (0, 1) for a in self.policy_assignment)
                or self.arm is not None or self.node_id is not None
                or self.exposure_fingerprint is not None
                or self.assignment_law_fingerprint is not None
                or self.unit_weights is None or len(self.unit_weights) != len(self.node_order)):
                raise ValueError('Fixed policy needs a full binary assignment and full node weight vector')
            weights = tuple(Fraction(w) for w in self.unit_weights)
            if any(w < 0 for w in weights) or sum(weights) != 1:
                raise ValueError('Policy aggregation weights must be nonnegative and sum to 1')
            object.__setattr__(self, 'unit_weights', tuple(str(w) for w in weights))
        if self.authority not in {'PROPOSED', 'HUMAN_CONFIRMED', 'TRUSTED_FIXTURE'}:
            raise ValueError('Unrecognized query authority')
        if self.query_resolution not in {'RESOLVED', 'UNRESOLVED', 'NEEDS_CONFIRMATION'}:
            raise ValueError('Unrecognized query resolution')
        fields = asdict(self)
        supplied = fields.pop('target_digest')
        # A1 scientific identity must not depend on approval or clarification
        # workflow status. Those belong to the route's provenance/authority gate.
        fields.pop('authority')
        fields.pop('query_resolution')
        expect = _sha({'v':'a1-target-v1.5', **fields})
        if supplied and supplied != expect:
            raise ValueError('Target digest is inconsistent with canonical semantics')
        object.__setattr__(self, 'target_digest', expect)


def arm_target_from_task(task: TaskSpec) -> TargetSemanticsV15:
    spec, _, _, query = _require_arm(task)
    refs = _refs(task)
    target = TargetSemanticsV15(
        kind='DESIGN_CONDITIONED_NODE_ARM_MEAN',
        network_fingerprint=refs['network'], node_order=refs['node_order'],
        outcome=query.outcome, context=refs['context'],
        averaging_scope='population_conditional_mean_given_W',
        authority=query.authority, query_resolution=query.resolution,
        assignment_law_fingerprint=refs['law'], exposure_fingerprint=refs['exposure'],
        node_id=query.target_node_id, arm=(query.own_treatment_value, query.exposure_value),
    )
    return target


def fixed_policy_target_from_study(task: TaskSpec, assignment: tuple[int, ...], *,
                                   authority: str, resolution: str = 'RESOLVED') -> TargetSemanticsV15:
    """Declare a NEW A1 Q; task serves only as an audited q/W/network study anchor.

    It never reuses the old *arm* query or arm fingerprint as the policy Q.
    In particular the policy Q identity is independent of original q and exposure g.
    """
    _, net, _, q = _require_arm(task)
    refs = _refs(task)
    return TargetSemanticsV15(
        kind='FIXED_FULL_ASSIGNMENT_POLICY_MEAN',
        network_fingerprint=refs['network'], node_order=refs['node_order'],
        outcome=q.outcome, context=refs['context'],
        averaging_scope='population_conditional_mean_given_W',
        authority=authority, query_resolution=resolution,
        policy_assignment=tuple(assignment),
        unit_weights=tuple(str(Fraction(1,len(net.node_ids))) for _ in net.node_ids),
    )


@dataclass(frozen=True)
class RequiredObservableV15:
    """The mathematical observable requested by a candidate theorem family.

    This is an A4 requirement, not an A1 intervention target or causal license.
    """
    operator: Literal['NODE_ARM_CONDITIONAL_MEAN', 'NODE_ASSIGNMENT_MEANS_FOR_POLICY']
    network_fingerprint: str
    node_order: tuple[str, ...]
    outcome: str
    context: str
    node_ids: tuple[str, ...]
    arm_cell: tuple[str, int, int] | None = None
    assignment_cell: tuple[int, ...] | None = None
    assignment_law_fingerprint: str | None = None
    exposure_fingerprint: str | None = None
    availability: str = 'SYMBOLIC_POPULATION_OPERATOR'


def required_observable_for(target: TargetSemanticsV15,
                            family_id: str) -> RequiredObservableV15:
    if family_id==ARM_FAMILY and target.kind=='DESIGN_CONDITIONED_NODE_ARM_MEAN':
        return RequiredObservableV15(
            operator='NODE_ARM_CONDITIONAL_MEAN',
            network_fingerprint=target.network_fingerprint,
            node_order=target.node_order, outcome=target.outcome,
            context=target.context, node_ids=(target.node_id,),
            arm_cell=(target.node_id,target.arm[0],target.arm[1]),
            assignment_law_fingerprint=target.assignment_law_fingerprint,
            exposure_fingerprint=target.exposure_fingerprint,
        )
    if family_id==FIXED_POLICY_CANDIDATE and target.kind=='FIXED_FULL_ASSIGNMENT_POLICY_MEAN':
        weighted=tuple(node for node,weight in zip(target.node_order,target.unit_weights)
                       if Fraction(weight)>0)
        return RequiredObservableV15(
            operator='NODE_ASSIGNMENT_MEANS_FOR_POLICY',
            network_fingerprint=target.network_fingerprint,
            node_order=target.node_order, outcome=target.outcome,
            context=target.context, node_ids=weighted,
            assignment_cell=target.policy_assignment,
        )
    raise ValueError('Required observable cannot be inferred for an unmatched family')


@dataclass(frozen=True)
class SourceAssessmentV15:
    source_id: str
    source_digest: str
    status: str
    reason: str | None
    rule_id: str | None
    receipt_digest: str | None = None


@dataclass(frozen=True)
class FamilyRouteAssessmentV15:
    version: str
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
    source_results: tuple[SourceAssessmentV15, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    current_legacy_status: str | None
    current_legacy_verification: str | None
    current_legacy_reason: str | None
    mathematical_identification_from_router: None
    digest: str


def _assessment(target, family, status, target_match, info, assumption, validity,
                sources, blockers, warnings=(), legacy_status=None, legacy_reason=None,
                legacy_verification=None):
    payload = dict(version=VERSION, target_digest=target.target_digest,
                   target_authority=target.authority,
                   target_resolution=target.query_resolution,
                   family_id=family.family_id, route_status=status,
                   target_match=target_match, information_status=info,
                   assumption_status=assumption, validity_status=validity,
                   backend_capability='REGISTERED' if family.executable_in_existing_engine else 'CANDIDATE_NOT_REGISTERED',
                   required_observable=(required_observable_for(target,family.family_id)
                                        if target.kind in family.target_kinds else None),
                   source_results=tuple(sources), blockers=tuple(blockers), warnings=tuple(warnings),
                   current_legacy_status=legacy_status,
                   current_legacy_verification=legacy_verification,
                   current_legacy_reason=legacy_reason,
                   mathematical_identification_from_router=None)
    hashable = {**payload, 'source_results': [asdict(x) for x in payload['source_results']],
                'required_observable': (asdict(payload['required_observable'])
                                        if payload['required_observable'] is not None else None)}
    return FamilyRouteAssessmentV15(**payload, digest=_sha(hashable))


def _assumptions(spec: IdentificationSpec):
    if spec.assumption_conflicts:
        return 'CONFLICT', tuple('ASSUMPTION_CONFLICT:' + x.code for x in spec.assumption_conflicts)
    records = {a.name:a for a in spec.assumptions}
    bad = tuple(sorted(name for name in REQUIRED
                       if name in records and records[name].status in ('NOT_ADMITTED','CONTRADICTED')))
    if bad:
        return 'REJECTED', tuple('NOT_ADMITTED:' + x for x in bad)
    missing = tuple(sorted(set(REQUIRED) - spec.confirmed_assumptions()))
    if missing:
        return 'NEEDS_INPUT', tuple('ASSUMPTION_UNRESOLVED:' + x for x in missing)
    return 'ADMITTED', ()


def _dedupe_sources(sources):
    by_id = {}
    for source in sources:
        if not isinstance(source, A4SourceV1):
            raise TypeError('Route assessment accepts reviewed A4SourceV1 only')
        if source.source_id in by_id and by_id[source.source_id] != source:
            return (), ('CONFLICTING_DECLARATIONS_FOR_SOURCE_ID:' + source.source_id,)
        by_id[source.source_id] = source
    return tuple(by_id[k] for k in sorted(by_id)), ()


def _source_binding(task, source):
    r = _refs(task)
    return (source.source_spec_fingerprint == r['spec']
            and source.network_fingerprint == r['network']
            and source.assignment_law_fingerprint == r['law']
            and source.node_order == r['node_order']
            and source.context == r['context'] and source.outcome == r['outcome']
            and source.outcome_averaging == 'population_conditional_mean_given_W'
            and set(source.outcome_nodes) <= set(r['node_order']))


def _fixed_policy_source(task, source, target, qmass):
    ssha=_sha(asdict(source))
    def report(status, reason=None, rule=None):
        return SourceAssessmentV15(source.source_id,ssha,status,reason,rule)
    if not _source_binding(task, source):
        return report('BLOCKED','SOURCE_SCOPE_OR_LAW_OR_NODE_ORDER_MISMATCH')
    if source.admission not in ADMITTED:
        return report('UNRESOLVED','SOURCE_NOT_ADMITTED')
    if source.availability=='FINITE_SAMPLE_ESTIMATE':
        return report('BLOCKED','FINITE_SAMPLE_NOT_POPULATION_INFORMATION')
    if qmass == 0:
        return report('BLOCKED','CONDITIONING_EVENT_OFF_SUPPORT')
    weighted_nodes=tuple(n for n,w in zip(target.node_order,target.unit_weights) if Fraction(w)>0)
    if not set(weighted_nodes) <= set(source.outcome_nodes):
        return report('BLOCKED','POLICY_NODE_OUTCOMES_NOT_COVERED')
    if source.operator=='ASSIGNMENT_NODE_MEANS':
        if target.policy_assignment not in source.assignment_cells:
            return report('BLOCKED','POLICY_ASSIGNMENT_MEAN_NOT_AVAILABLE')
        return report('SATISFIED',rule='A4_SELECT_ASSIGNMENT_NODE_MEANS_V1')
    if source.operator=='NODE_FULL_LAW':
        return report('SATISFIED',rule='A4_NODE_FULL_LAW_TO_ASSIGNMENT_MEAN_V1')
    if source.operator=='FULL_JOINT_LAW':
        if set(source.outcome_nodes) != set(target.node_order):
            return report('BLOCKED','FULL_JOINT_LAW_REQUIRES_ALL_OUTCOME_NODES')
        return report('SATISFIED',rule='A4_FULL_JOINT_TO_ASSIGNMENT_MEAN_V1')
    # No exposure sufficiency or other model restriction is inferred from arm means.
    return report('BLOCKED','ARM_OR_MARGINAL_INFO_NOT_ASSIGNMENT_MEAN')


def assess_family_route(task: TaskSpec, target: TargetSemanticsV15,
                        sources: tuple[A4SourceV1, ...], *, family_id: str) -> FamilyRouteAssessmentV15:
    """Non-authoritative preflight. Never turns a ready candidate into POINT.

    Does not combine separate sources or elevate observed associations to causal facts.
    Re-evaluates legacy identify only for the already implemented arm family.
    """
    catalog={family.family_id:family for family in family_catalog()}
    if family_id not in catalog:
        raise ValueError('Unregistered family candidate: declare a reviewed family contract first')
    family=catalog[family_id]
    spec, net, contract, query=_require_arm(task)
    refs=_refs(task)
    if (target.network_fingerprint != refs['network'] or target.node_order != refs['node_order']
        or target.outcome != refs['outcome'] or target.context != refs['context']):
        return _assessment(target,family,'SPECIFICATION_CONFLICT','CONFLICT','NOT_EVALUATED','NOT_EVALUATED','NOT_EVALUATED',(),('TARGET_STUDY_SCOPE_MISMATCH',))
    if target.kind not in family.target_kinds:
        return _assessment(target,family,'FAMILY_NOT_APPLICABLE','NOT_MATCHED','NOT_EVALUATED','NOT_EVALUATED','NOT_EVALUATED',(),('TARGET_CLASS_NOT_SUPPORTED_BY_THIS_FAMILY',))
    if (target.query_resolution != 'RESOLVED' or target.authority not in TRUSTED):
        return _assessment(target,family,'NEEDS_INPUT','UNCONFIRMED','NOT_EVALUATED','NOT_EVALUATED','NOT_EVALUATED',(),('TARGET_NOT_HUMAN_CONFIRMED',))
    if target.kind=='DESIGN_CONDITIONED_NODE_ARM_MEAN':
        expected=arm_target_from_task(task)
        if target != expected:
            return _assessment(target,family,'SPECIFICATION_CONFLICT','CONFLICT','NOT_EVALUATED','NOT_EVALUATED','NOT_EVALUATED',(),('ARM_TARGET_MISMATCH_WITH_V1_THEOREM_CONTRACT',))
    parsed, source_conflicts=_dedupe_sources(sources)
    if source_conflicts:
        return _assessment(target,family,'SOURCE_CONFLICT','MATCHED','NOT_EVALUATED','NOT_EVALUATED','NOT_EVALUATED',(),source_conflicts)
    ast, aissues=_assumptions(spec)
    if ast != 'ADMITTED':
        return _assessment(target,family,'ASSUMPTION_CONFLICT' if ast=='CONFLICT' else ('ASSUMPTIONS_NOT_ADMITTED' if ast=='REJECTED' else 'NEEDS_INPUT'),
                          'MATCHED','NOT_EVALUATED',ast,'NOT_EVALUATED',(),aissues)
    if target.kind=='DESIGN_CONDITIONED_NODE_ARM_MEAN':
        error=_eligibility_error(spec)
        if error not in (None, 'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED'):
            # Check validity independently of the typed information assessment.
            return _assessment(target,family,'THEOREM_REQUIREMENT_FAILED','MATCHED','NOT_EVALUATED','ADMITTED','FAILED',(),(error,))
        if not parsed:
            return _assessment(target,family,'NEEDS_INPUT','MATCHED','UNRESOLVED','ADMITTED','NOT_EVALUATED',(),('NO_REVIEWED_TYPED_INFORMATION_SOURCE',))
        rs=[]
        old_status=None; old_reason=None; old_verification=None
        for src in parsed:
            assessed=assess_a4_shadow(task,src)
            old_status=assessed.legacy_identification.status
            old_reason=assessed.legacy_identification.result.get('reason_code')
            old_verification=assessed.legacy_identification.verification_status
            old_verification=(old_verification.value if hasattr(old_verification,'value')
                              else str(old_verification))
            old_status=old_status.value if hasattr(old_status,'value') else str(old_status)
            receipt=assessed.receipt
            rs.append(SourceAssessmentV15(src.source_id,_sha(asdict(src)),
                      receipt.information_status,receipt.reason,receipt.rule_id,receipt.digest))
            if receipt.information_status == 'TARGET_UNDEFINED':
                return _assessment(target,family,'TARGET_UNDEFINED','MATCHED','TARGET_UNDEFINED','ADMITTED','UNDEFINED',rs,('ZERO_ARM_SUPPORT',),legacy_status=old_status,legacy_reason=old_reason,
                                   legacy_verification=old_verification)
        sat=next((x for x in rs if x.status=='SATISFIED'),None)
        warnings=tuple('UNRESOLVED_OTHER_SOURCE:' + x.source_id for x in rs if x.status=='UNRESOLVED')
        if sat:
            if old_status=='POINT' and old_reason is None:
                # Old result may have None reason while verification failed; only make a
                # routing claim (never a new mathematical claim).
                state='CANDIDATE_READY'
            elif old_reason=='CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED':
                state='LEGACY_GATE_DISAGREEMENT'
            else:
                state='CANDIDATE_READY'
            return _assessment(target,family,state,'MATCHED','SATISFIED','ADMITTED','VALID',rs,(),warnings,old_status,old_reason,old_verification)
        if any(x.status=='UNRESOLVED' for x in rs) and not any(x.status in ('BLOCKED','RULE_NOT_IMPLEMENTED') for x in rs):
            status='NEEDS_INPUT'; reason='INFORMATION_SOURCES_NOT_ADMITTED'
        elif any(x.status=='RULE_NOT_IMPLEMENTED' for x in rs):
            status='INFORMATION_RULE_NOT_IMPLEMENTED'; reason='OPERATOR_RULE_NOT_IMPLEMENTED'
        else:
            status='INFORMATION_BLOCKED'; reason='NO_ENTAILMENT_TO_REQUIRED_ARM_MEAN'
        return _assessment(target,family,status,'MATCHED',status,'ADMITTED','VALID',rs,(reason,),warnings,old_status,old_reason,old_verification)

    # Candidate: fixed full assignment policy value. This is not an executable
    # theorem route even when its required observational quantities exist.
    # Only use the arm TaskSpec as a study-context anchor. Do not inherit its
    # exposure-specific theorem validity, but insist on a legitimate fixed network.
    if (spec.structure.representation_type != 'fixed_network_interference'
        or not net.fixed_network):
        return _assessment(target,family,'THEOREM_REQUIREMENT_FAILED','MATCHED',
                           'NOT_EVALUATED','ADMITTED','FAILED',(),
                           ('FIXED_PRETREATMENT_NETWORK_REQUIRED',))
    qmass=AssignmentSpec(contract.design).full_assignment_probability(
        net,dict(zip(net.node_ids,target.policy_assignment)))
    if qmass == 0:
        return _assessment(target,family,'OFF_SUPPORT_ALTERNATE_THEOREM','MATCHED','CONDITIONAL_ASSIGNMENT_UNDEFINED',
                          'ADMITTED','OFF_SUPPORT',(),('Q_FIXED_POLICY_DEFINED_BUT_Q_ASSIGNED_ZERO_SUPPORT',
                                                     'ALTERNATE_ASSUMPTIONS_AND_THEOREM_REQUIRED'))
    if not parsed:
        return _assessment(target,family,'NEEDS_INPUT','MATCHED','UNRESOLVED','ADMITTED','VALID',(),('NO_REVIEWED_TYPED_INFORMATION_SOURCE',))
    rs=tuple(_fixed_policy_source(task,src,target,qmass) for src in parsed)
    yes=any(x.status=='SATISFIED' for x in rs)
    if yes:
        return _assessment(target,family,'THEOREM_BACKEND_UNAVAILABLE','MATCHED','SATISFIED','ADMITTED','VALID',
                           rs,('NO_REGISTERED_GENERAL_FIXED_POLICY_THEOREM_OR_VERIFIER',))
    if all(x.status=='UNRESOLVED' for x in rs):
        return _assessment(target,family,'NEEDS_INPUT','MATCHED','UNRESOLVED','ADMITTED','VALID',rs,('INFORMATION_SOURCES_NOT_ADMITTED',))
    return _assessment(target,family,'INFORMATION_BLOCKED','MATCHED','INSUFFICIENT','ADMITTED','VALID',rs,('NO_ENTAILMENT_TO_NODE_ASSIGNMENT_MEANS',))


def replay_family_route(task: TaskSpec, target: TargetSemanticsV15,
                        sources: tuple[A4SourceV1, ...], saved: FamilyRouteAssessmentV15) -> bool:
    """Same-environment deterministic replay of declared typed inputs, not source truth."""
    if not isinstance(saved, FamilyRouteAssessmentV15):
        raise ValueError('Invalid route assessment certificate')
    expected=assess_family_route(task,target,sources,family_id=saved.family_id)
    if expected != saved:
        raise ValueError('Route assessment is stale or was modified')
    fields=asdict(saved); saved_digest=fields.pop('digest')
    if saved_digest != _sha(fields):
        raise ValueError('Route digest mismatch')
    return True
