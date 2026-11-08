"""Non-authoritative, opt-in A4 shadow for the verified randomized-network arm family.

This module does NOT change identify(), the published v1.0 contracts, theorem
admission, batch certificates, estimation requests, or policy. A4 receipts
attest only whether an *explicitly declared* population observable entails the
node-arm conditional mean required by the family; they do not attest that the
source declaration is true, establish randomization, or prove a causal effect.

Support is computed with the existing family SupportEngine and independently
verified with its separate exact counting backends. No full assignment space
is enumerated, including for the official ER300 network.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from hashlib import sha256
import json

from .contracts import TaskSpec, IdentificationResult
from .identification import identify
from ._internal.identification.schemas import (
    IdentificationSpec, CompleteRandomizationDesignV1,
    TwoGroupFixedQuotaDesignV1, HeterogeneousBernoulliDesignV1,
)
from ._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine
from ._internal.identification.randomized_network_arm import (
    GROUP_E2, GROUP_E3, GROUP_TO_REFERENCE, arm_target_fingerprint,
    spec_fingerprint, _verify_joint_support_independently,
    _verify_two_group_joint_support_independently,
    _verify_heterogeneous_joint_support_independently,
    _canonical_core_collaborators, _eligibility_error,
)

__all__ = [
    'A4SourceV1', 'VerifiedArmSupportV1', 'A4ShadowReceiptV1',
    'A4ShadowAssessmentV1', 'VerifiedSupportAdapter', 'declare_a4_source',
    'verified_arm_support', 'replay_verified_arm_support',
    'assess_a4_shadow', 'replay_a4_shadow',
]

_VERSION = 'a4-randomized-network-arm-shadow-v1'
_SUPPORTED_OPERATORS = frozenset((
    'NODE_ARM_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW',
    'ASSIGNMENT_NODE_MEANS', 'PAIRWISE_MARGINALS',
))
_APPROVED = {'CERTIFIED', 'ADMITTED'}
_AVAILABILITY = {'SYMBOLIC_POPULATION_OPERATOR', 'EXACT_POPULATION_VALUE', 'FINITE_SAMPLE_ESTIMATE'}


def _canonical(obj):
    if isinstance(obj, Fraction):
        return str(obj)
    if hasattr(obj, 'model_dump'):
        return _canonical(obj.model_dump(mode='json'))
    if isinstance(obj, dict):
        return {str(k): _canonical(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_canonical(x) for x in obj]
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    raise TypeError(f'Noncanonical digest input: {type(obj)!r}')


def _sha(obj) -> str:
    return sha256(json.dumps(_canonical(obj), sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _require_arm(task: TaskSpec):
    if not isinstance(task, TaskSpec) or task.estimand != 'NETWORK_RANDOMIZED_ARM_MEAN':
        raise ValueError('A4 shadow only supports a v1.0 randomized-network arm TaskSpec')
    replace(task)  # check dataclass mutable nested payloads at API boundary
    if task.identification_spec is None:
        raise ValueError('Typed identification_spec required')
    spec = IdentificationSpec.model_validate(task.identification_spec)
    contract, net, q = spec.randomized_network_arm_theorem_contract, spec.network_exposure, spec.query
    if contract is None or net is None or q.type != 'NETWORK_RANDOMIZED_ARM_MEAN':
        raise ValueError('An exact randomized-network arm theorem contract is required')
    if tuple(net.node_ids) != task.node_ids:
        raise ValueError('Network node coordinate order differs from original TaskSpec')
    if q.target_node_id not in net.node_ids:
        raise ValueError('Query node is outside the network')
    if q.response_target_fingerprint != arm_target_fingerprint(
        net, contract, q.target_node_id, q.own_treatment_value, q.exposure_value
    ):
        raise ValueError('Query target fingerprint is inconsistent with q/g')
    return spec, net, contract, q


def _refs(task: TaskSpec):
    spec, net, contract, q = _require_arm(task)
    return {
        'spec': spec_fingerprint(spec),
        'network': net.semantic_fingerprint(),
        'law': _sha(contract.design.model_dump(mode='json')),
        'exposure': _sha({'network': net.semantic_fingerprint(),
                          'grouping': contract.grouping,
                          'core_collaborators': contract.core_collaborators}),
        'target': q.response_target_fingerprint,
        'node_order': tuple(net.node_ids),
        'outcome': q.outcome,
        'context': spec.support_domain.get('context_symbol'),
    }


@dataclass(frozen=True)
class A4SourceV1:
    """Explicit admitted source; not inferred from legacy variables or sample columns."""
    source_id: str
    operator: str
    provenance: str
    admission: str
    availability: str
    regime: str
    source_spec_fingerprint: str
    network_fingerprint: str
    assignment_law_fingerprint: str
    node_order: tuple[str, ...]
    context: str
    outcome: str
    outcome_averaging: str
    outcome_nodes: tuple[str, ...]
    exposure_fingerprint: str | None = None
    arm_cells: tuple[tuple[str, int, int], ...] = ()
    assignment_cells: tuple[tuple[int, ...], ...] = ()

    def __post_init__(self):
        if not self.source_id or not self.provenance or not self.context or not self.outcome:
            raise ValueError('Explicit source identification/context/provenance required')
        if self.operator not in _SUPPORTED_OPERATORS or self.admission not in (
            'CERTIFIED', 'ADMITTED', 'PROPOSED', 'UNRESOLVED', 'NOT_ADMITTED', 'CONTRADICTED'
        ) or self.availability not in _AVAILABILITY:
            raise ValueError('Invalid information operator, admission or availability')
        if self.regime not in ('experimental', 'observational'):
            raise ValueError('Invalid information regime')
        if not self.node_order or len(set(self.node_order)) != len(self.node_order):
            raise ValueError('Full treatment vector requires distinct ordered node coordinates')
        if not self.outcome_nodes or len(set(self.outcome_nodes)) != len(self.outcome_nodes):
            raise ValueError('Explicit nonempty outcome node coverage required')
        if self.outcome_averaging != 'population_conditional_mean_given_W':
            raise ValueError('Only a declared W-conditional population outcome mean is supported')
        if self.operator == 'NODE_ARM_MEANS':
            if not self.exposure_fingerprint or not self.arm_cells or self.assignment_cells:
                raise ValueError('NODE_ARM_MEANS requires q/g-bound exact cells')
            if (len(set(self.arm_cells)) != len(self.arm_cells)
                or any(not isinstance(c, tuple) or len(c) != 3
                       or c[0] not in self.outcome_nodes
                       or type(c[1]) is not int or c[1] not in (0, 1)
                       or type(c[2]) is not int or c[2] < 0
                       for c in self.arm_cells)):
                raise ValueError('Invalid or duplicate arm cells')
        elif self.operator == 'ASSIGNMENT_NODE_MEANS':
            if self.exposure_fingerprint is not None or not self.assignment_cells or self.arm_cells:
                raise ValueError('ASSIGNMENT_NODE_MEANS requires declared assignment coverage')
            if (len(set(self.assignment_cells)) != len(self.assignment_cells)
                or any(len(z) != len(self.node_order)
                       or any(type(a) is not int or a not in (0,1) for a in z)
                       for z in self.assignment_cells)):
                raise ValueError('Invalid or duplicate assignment cells')
        elif self.exposure_fingerprint is not None or self.arm_cells or self.assignment_cells:
            raise ValueError('Full-law/marginal sources cannot impersonate arm or assignment cells')


def declare_a4_source(task: TaskSpec, *, source_id: str, operator: str,
                      provenance: str, admission: str, availability: str,
                      outcome_nodes: tuple[str, ...], node_order: tuple[str, ...],
                      arm_cells: tuple[tuple[str, int, int], ...] = (),
                      assignment_cells: tuple[tuple[int, ...], ...] = (),
                      regime: str = 'experimental') -> A4SourceV1:
    """Versioned *explicit declaration* from a reviewed source, not a truth detector.

    The caller must actively assert operator semantics, coordinate order and
    provenance. This cannot upgrade legacy InformationObject.variables to a
    full joint law and does not inspect finite samples.
    """
    r = _refs(task)
    return A4SourceV1(
        source_id=source_id, operator=operator, provenance=provenance,
        admission=admission, availability=availability, regime=regime,
        source_spec_fingerprint=r['spec'], network_fingerprint=r['network'],
        assignment_law_fingerprint=r['law'], node_order=tuple(node_order),
        context=r['context'], outcome=r['outcome'],
        outcome_averaging='population_conditional_mean_given_W',
        outcome_nodes=tuple(outcome_nodes),
        exposure_fingerprint=r['exposure'] if operator == 'NODE_ARM_MEANS' else None,
        arm_cells=tuple(arm_cells), assignment_cells=tuple(assignment_cells),
    )


@dataclass(frozen=True)
class VerifiedArmSupportV1:
    source_spec_fingerprint: str
    network_fingerprint: str
    assignment_law_fingerprint: str
    exposure_fingerprint: str
    target_fingerprint: str
    node_order: tuple[str, ...]
    query_node_id: str
    own_treatment: int
    exposure_state: int
    support: str
    independent_verifier_rule: str
    digest: str


def verified_arm_support(task: TaskSpec) -> VerifiedArmSupportV1:
    """Two independent EXACT support calculations, never enumerating all T vectors.

    Only certifies the event under the design; it does NOT certify assumptions
    or information availability. Unsupported/out-of-domain query inputs are
    conservatively rejected, rather than normalized into a different target.
    """
    spec, net, contract, q = _require_arm(task)
    # Reuse the official v1.0 mathematical requirements except the outdated
    # variable-name-only A4 gate. No change to the production implementation.
    error = _eligibility_error(spec)
    if error not in (None, 'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED'):
        raise ValueError('Support adapter cannot ignore non-A4 theorem constraints: ' + error)
    design, grouping = contract.design, contract.grouping
    assignment = AssignmentSpec(design)
    exposure = ExposureSpec(grouping, contract.core_collaborators)
    assignment._validate_network(net)
    core = (_canonical_core_collaborators(net, grouping, contract.core_collaborators)
            if grouping == GROUP_E3 else None)
    ref_nodes = frozenset(core[q.target_node_id]) if core is not None else None
    a, s, node = q.own_treatment_value, q.exposure_value, q.target_node_id
    proposer = SupportEngine.evaluate(
        network=net, assignment=assignment, exposure=exposure,
        node_id=node, own_treatment_value=a, exposure_value=s,
    ).joint_probability
    if isinstance(design, CompleteRandomizationDesignV1):
        degree = len(ref_nodes) if ref_nodes is not None else net.degree_map()[node]
        independent = _verify_joint_support_independently(len(net.node_ids), design.m, degree, a, s, grouping)
        rule = 'INDEPENDENT_COMPLETE_COMBINATORIAL'
    elif isinstance(design, TwoGroupFixedQuotaDesignV1):
        independent = _verify_two_group_joint_support_independently(
            net, design, node, a, s, grouping, reference_nodes=ref_nodes,
        )
        rule = 'INDEPENDENT_TWO_GROUP_COMBINATORIAL'
    elif isinstance(design, HeterogeneousBernoulliDesignV1):
        independent = _verify_heterogeneous_joint_support_independently(
            net, design, node, a, s, grouping, reference_nodes=ref_nodes,
        )
        rule = 'INDEPENDENT_BERNOULLI_GENERATING_POLYNOMIAL'
    else:
        raise ValueError('Unknown exact design backend')
    if proposer != independent:
        raise ValueError('PROPOSER_INDEPENDENT_VERIFIER_SUPPORT_DISAGREEMENT')
    if independent < 0 or independent > 1:
        raise ValueError('Invalid population probability')
    r = _refs(task)
    payload = dict(source_spec_fingerprint=r['spec'], network_fingerprint=r['network'],
                   assignment_law_fingerprint=r['law'], exposure_fingerprint=r['exposure'],
                   target_fingerprint=r['target'], node_order=r['node_order'],
                   query_node_id=node, own_treatment=a, exposure_state=s,
                   support=str(independent), independent_verifier_rule=rule)
    return VerifiedArmSupportV1(**payload, digest=_sha(payload))


class VerifiedSupportAdapter:
    """Non-enumerative bridge to the *existing* support proposer and verifier.

    For an already identified task it additionally replays the old theorem
    certificate and matches its joint-arm probability against both independent
    support computations. For a task stopped solely by the old A4 variable gate,
    only the mathematical support is verified; this does not create a theorem
    certificate or change the saved legacy result.
    """

    @staticmethod
    def from_task(task: TaskSpec) -> VerifiedArmSupportV1:
        return verified_arm_support(task)

    @staticmethod
    def from_legacy_verified(legacy: IdentificationResult) -> VerifiedArmSupportV1:
        from .identification import replay_population_identification
        if not isinstance(legacy, IdentificationResult) or legacy.status != 'POINT' or legacy.verification_status != 'VERIFIED':
            raise ValueError('Verified POINT IdentificationResult required as theorem anchor')
        checked = replay_population_identification(legacy)
        if checked.backend != 'randomized_network_arm_mean_v1':
            raise ValueError('Theorem anchor is not from the randomized-network arm family')
        proof = verified_arm_support(legacy.task)
        certificate = checked.certificate
        if (certificate.get('source_spec_sha256') != proof.source_spec_fingerprint
            or certificate.get('query_node_id') != proof.query_node_id
            or tuple(certificate.get('query_arm', ())) != (proof.own_treatment, proof.exposure_state)
            or Fraction(certificate['joint_arm_support_probability']) != Fraction(proof.support)):
            raise ValueError('Verified theorem support differs from independent support adapter')
        return proof


def replay_verified_arm_support(task: TaskSpec, proof: VerifiedArmSupportV1) -> bool:
    if not isinstance(proof, VerifiedArmSupportV1) or verified_arm_support(task) != proof:
        raise ValueError('VerifiedArmSupport tampered or not bound to this task')
    return True


@dataclass(frozen=True)
class A4ShadowReceiptV1:
    version: str
    source_digest: str
    source_id: str
    source_spec_fingerprint: str
    required_target_fingerprint: str
    required_observable: str
    support_digest: str
    support: str
    rule_id: str | None
    operations: tuple[str, ...]
    information_status: str
    reason: str | None
    digest: str


@dataclass(frozen=True)
class A4ShadowAssessmentV1:
    legacy_identification: IdentificationResult
    support: VerifiedArmSupportV1
    receipt: A4ShadowReceiptV1
    difference: str
    mathematical_status_of_shadow: None = None


def _assess_from_proof(task: TaskSpec, source: A4SourceV1, proof: VerifiedArmSupportV1) -> A4ShadowReceiptV1:
    r = _refs(task)
    def outcome(status, reason=None, rule=None, ops=()):
        p = dict(version=_VERSION, source_digest=_sha(source.__dict__), source_id=source.source_id,
                 source_spec_fingerprint=r['spec'], required_target_fingerprint=r['target'],
                 required_observable='E[Y_i^obs | W, T_i=a, S_i=s]',
                 support_digest=proof.digest, support=proof.support, rule_id=rule,
                 operations=tuple(ops), information_status=status, reason=reason)
        return A4ShadowReceiptV1(**p, digest=_sha(p))

    # Must verify binding before any operator rule, including direct arm means.
    if (source.source_spec_fingerprint != r['spec'] or source.network_fingerprint != r['network']
        or source.assignment_law_fingerprint != r['law'] or source.node_order != r['node_order']
        or source.context != r['context'] or source.outcome != r['outcome']):
        return outcome('BLOCKED', 'SOURCE_SCOPE_OR_LAW_OR_NODE_ORDER_MISMATCH')
    if source.admission not in _APPROVED:
        return outcome('UNRESOLVED', 'SOURCE_NOT_ADMITTED')
    if source.availability == 'FINITE_SAMPLE_ESTIMATE':
        return outcome('BLOCKED', 'FINITE_SAMPLE_IS_NOT_POPULATION_OPERATOR')
    if source.outcome_averaging != 'population_conditional_mean_given_W':
        return outcome('BLOCKED', 'OUTCOME_AVERAGING_MISMATCH')
    if not set(source.outcome_nodes) <= set(r['node_order']):
        return outcome('BLOCKED', 'INVALID_OUTCOME_NODE_SCOPE')
    if proof.support == '0':
        return outcome('TARGET_UNDEFINED', 'ZERO_ARM_SUPPORT')
    node = proof.query_node_id
    if node not in source.outcome_nodes:
        return outcome('BLOCKED', 'NODE_OUTCOME_NOT_AVAILABLE')
    if source.operator == 'NODE_ARM_MEANS':
        if source.exposure_fingerprint != r['exposure']:
            return outcome('BLOCKED', 'SOURCE_EXPOSURE_MISMATCH')
        cell = (node, proof.own_treatment, proof.exposure_state)
        if cell not in source.arm_cells:
            return outcome('BLOCKED', 'ARM_COVERAGE_INCOMPLETE')
        return outcome('SATISFIED', rule='A4_DIRECT_NODE_ARM_V1', ops=('SELECT_NODE_ARM_MEAN',))
    if source.operator == 'NODE_FULL_LAW':
        return outcome('SATISFIED', rule='A4_NODE_FULL_LAW_TO_ARM_V1',
                       ops=('COMPUTE_EXPOSURE_FROM_T_VECTOR', 'CONDITION_ON_ARM_EVENT',
                            'TAKE_NODE_CONDITIONAL_MEAN'))
    if source.operator == 'FULL_JOINT_LAW':
        if set(source.outcome_nodes) != set(r['node_order']):
            return outcome('BLOCKED', 'FULL_JOINT_REQUIRES_ALL_NODE_OUTCOMES')
        return outcome('SATISFIED', rule='A4_FULL_JOINT_TO_ARM_V1',
                       ops=('COMPUTE_EXPOSURE_FROM_T_VECTOR', 'MARGINALIZE_OTHER_OUTCOMES',
                            'CONDITION_ON_ARM_EVENT', 'TAKE_NODE_CONDITIONAL_MEAN'))
    if source.operator == 'ASSIGNMENT_NODE_MEANS':
        return outcome('RULE_NOT_IMPLEMENTED', 'COMPLETE_CONDITIONAL_Q_WEIGHTS_NOT_CERTIFIED')
    return outcome('BLOCKED', 'OPERATOR_NOT_ENTAILED')


def _difference(legacy: IdentificationResult, receipt: A4ShadowReceiptV1) -> str:
    # Only flag false +/- for the A4 decision, not for other theorem gates.
    legacy_ok = legacy.status == 'POINT' and legacy.verification_status == 'VERIFIED'
    legacy_issue = legacy.result.get('reason_code')
    if legacy_ok and receipt.information_status == 'SATISFIED':
        return 'AGREE_A4_READY'
    if legacy_ok and receipt.information_status == 'BLOCKED':
        return 'LEGACY_A4_TOO_PERMISSIVE'
    if (not legacy_ok and legacy_issue == 'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED'
        and receipt.information_status == 'SATISFIED'):
        return 'LEGACY_A4_TOO_RESTRICTIVE'
    return 'NO_A4_GATE_CONCLUSION'


def assess_a4_shadow(task: TaskSpec, source: A4SourceV1) -> A4ShadowAssessmentV1:
    """Run the REAL legacy identification in parallel with trusted typed A4 preflight.

    No production status is overwritten. A4 READY never means POINT.
    """
    legacy = identify(task)
    proof = (VerifiedSupportAdapter.from_legacy_verified(legacy)
             if legacy.status == 'POINT' and legacy.verification_status == 'VERIFIED'
             else VerifiedSupportAdapter.from_task(task))
    receipt = _assess_from_proof(task, source, proof)
    return A4ShadowAssessmentV1(legacy, proof, receipt, _difference(legacy, receipt))


def replay_a4_shadow(task: TaskSpec, source: A4SourceV1,
                     saved: A4ShadowAssessmentV1) -> bool:
    if not isinstance(saved, A4ShadowAssessmentV1):
        raise ValueError('Invalid A4ShadowAssessment')
    if saved.legacy_identification.task is not task:
        raise ValueError('Shadow assessment must remain bound to its original TaskSpec')
    expected = assess_a4_shadow(task, source)
    # Legacy result embeds a TaskSpec containing numpy arrays; compare only
    # its original source identity and serializable typed theorem results.
    if (saved.receipt != expected.receipt or saved.support != expected.support
        or saved.difference != expected.difference or
        saved.legacy_identification.result != expected.legacy_identification.result or
        saved.legacy_identification.verification_status != expected.legacy_identification.verification_status
        or saved.legacy_identification.diagnostics != expected.legacy_identification.diagnostics):
        raise ValueError('A4 shadow certificate differs from trusted-source replay')
    if saved.receipt.digest != _sha({
        'version': saved.receipt.version, 'source_digest': saved.receipt.source_digest,
        'source_id': saved.receipt.source_id,
        'source_spec_fingerprint': saved.receipt.source_spec_fingerprint,
        'required_target_fingerprint': saved.receipt.required_target_fingerprint,
        'required_observable': saved.receipt.required_observable,
        'support_digest': saved.receipt.support_digest, 'support': saved.receipt.support,
        'rule_id': saved.receipt.rule_id, 'operations': saved.receipt.operations,
        'information_status': saved.receipt.information_status,
        'reason': saved.receipt.reason,
    }):
        raise ValueError('A4 receipt digest does not match contents')
    return True
