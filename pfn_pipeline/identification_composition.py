"""R1a v1.8: verified *population* linear combinations of randomized network arms.

This is a new query/result type, NOT another randomized identification theorem.
The v1.0 Batch's independently checked source proof is revalidated with its
original anchor, source digest and new exact checks of each nonzero arm; an
explicit admitted A4 population-operator declaration must
cover every used arm. No finite-sample values, fixed-policy welfare, exposure
sufficiency, estimator request, or observational exchangeability are inferred.

The public original TaskSpec, identify(), Batch and Estimation/Policy interfaces
are unchanged. Float coefficients are forbidden: signatures use exact rationals.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from typing import Mapping, Literal

from .identification_batch import BatchIdentificationResult
from .identification_batch import _VERSION as _BATCH_VERSION, _digest as _batch_digest
from .identification_batch import _independent_count_masses, _support_comparison
from .identification_a4_shadow import A4SourceV1, _refs
from ._internal.identification.schemas import IdentificationSpec
from ._internal.identification.randomized_network_arm import (
    REQUIRED, arm_target_fingerprint, spec_fingerprint, GROUP_E3,
    exposure_object, queried_exposure_state, exposure_state_str, W_G_GROUPINGS,
)
from ._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine
from ._internal.identification.schemas import HeterogeneousBernoulliDesignV1
from ._internal.identification.schemas import UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1
from ._internal.identification.randomized_arm_family.assignment import as_design_dataclass
from ._internal.identification.randomized_arm_family.support_verifier import verify_joint_support as _verify_joint_support
from .identification import identify, replay_population_identification

__all__ = [
    'ArmLinearTerm', 'VerifiedCompositionV18', 'CompositionUnavailable',
    'identify_verified_linear_target', 'identify_verified_node_effect',
    'identify_verified_group_effect', 'replay_verified_composition',
]

_VERSION = 'randomized-network-verified-linear-composition-v1.8'
_EFFECTS = {'DIRECT', 'SPILLOVER', 'TOTAL'}
_TRUSTED_A4 = {'ADMITTED', 'CERTIFIED'}
_SUPPORTED_A4 = {'NODE_ARM_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW'}
_COHORT_AUTHORITY = {'STUDY_PROTOCOL', 'HUMAN_CONFIRMED_PRETREATMENT', 'TRUSTED_FIXTURE'}


class CompositionUnavailable(ValueError):
    """Fail-closed workflow error; it does NOT assert mathematical PARTIAL ID."""

    def __init__(self, code: str, detail: str = ''):
        self.reason_code = code
        super().__init__(code if not detail else f'{code}: {detail}')


def _fraction(value, *, field: str) -> Fraction:
    if type(value) is int or isinstance(value, Fraction):
        result = Fraction(value)
    elif type(value) is str:
        try:
            result = Fraction(value)
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            raise ValueError(f'{field} must be an exact finite rational') from exc
    else:
        raise TypeError(f'{field} must be an exact int/Fraction/string, not float or bool')
    return result


def _hash(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ArmLinearTerm:
    node_id: str
    own_treatment: int
    # int for E1-E5; canonical string coordinate for weighted/grouped exposure.
    exposure_state: int | str
    coefficient: Fraction | int | str

    def __post_init__(self):
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise ValueError('An explicit nonempty node ID is required')
        if type(self.own_treatment) is not int or self.own_treatment not in (0, 1):
            raise ValueError('own_treatment must be 0 or 1')
        if isinstance(self.exposure_state, bool) or not (
                (type(self.exposure_state) is int and self.exposure_state >= 0)
                or (isinstance(self.exposure_state, str) and self.exposure_state.strip())):
            raise ValueError('exposure_state must be a nonnegative integer or canonical exposure string')
        object.__setattr__(self, 'coefficient', _fraction(self.coefficient, field='coefficient'))

    @property
    def coordinates(self) -> tuple[str, int, int | str]:
        return self.node_id, self.own_treatment, self.exposure_state

    def json_payload(self) -> dict:
        return dict(node_id=self.node_id, own_treatment=self.own_treatment,
                    exposure_state=self.exposure_state, coefficient=str(self.coefficient))


@dataclass(frozen=True)
class _CompositionRecipe:
    """Immutable declared query; named effects are independently reconstructed."""
    kind: Literal['CUSTOM_LINEAR', 'DIRECT', 'SPILLOVER', 'TOTAL']
    node_weights: tuple[tuple[str, Fraction], ...] = ()
    reference_exposure: int | str | None = None
    comparison_exposure: int | str | None = None
    spillover_own_treatment: int = 1
    supplied_terms: tuple[ArmLinearTerm, ...] = ()
    cohort_authority: str | None = None
    cohort_evidence: str | None = None


@dataclass(frozen=True)
class VerifiedCompositionV18:
    """An independently replayable symbolic POINT result, never numerical effects.

    `target_fingerprint` identifies the *mathematical* linear combination; the
    receipt includes provenance, recipe, explicit A4 information and source Batch.
    Each term is one already-POINT node-arm mean under one q/g/W context.
    """
    source_batch: BatchIdentificationResult
    a4_source: A4SourceV1
    recipe: _CompositionRecipe
    terms: tuple[ArmLinearTerm, ...]
    population_arm_support: tuple[str, ...]
    constituent_target_fingerprints: tuple[str, ...]
    required_population_objects: tuple[str, ...]
    identified_functional: str
    a4_rule_id: str
    a4_operations: tuple[str, ...]
    target_fingerprint: str
    certificate_sha256: str
    contract_version: str = _VERSION
    status: str = 'POINT'
    verification_status: str = 'VERIFIED'
    assumptions_used: tuple[str, ...] = tuple(sorted(REQUIRED))
    validity_note: str = ('All nonzero constituent arms must have verified positive q-support; '
                          'all refer to the same W/q/g; a reviewed population observable must '
                          'supply every conditional arm mean.')
    estimation_request: None = None

    @property
    def term_count(self) -> int:
        return len(self.terms)

    @property
    def kind(self) -> str:
        return self.recipe.kind

    def summary(self) -> dict:
        """Safe JSON-friendly result: no fabricated causal numeric values."""
        return dict(status=self.status, verification_status=self.verification_status,
                    kind=self.kind, term_count=self.term_count,
                    identified_functional=self.identified_functional,
                    target_fingerprint=self.target_fingerprint,
                    source_batch_sha256=self.source_batch.batch_sha256,
                    a4_source_id=self.a4_source.source_id,
                    # Numeric information here is exact *assignment support*,
                    # not an estimated causal effect. Keep terms, coefficients
                    # and their independent support proofs visible to clients.
                    constituent_arms=[dict(**term.json_payload(),
                        joint_support=support, arm_target_fingerprint=target_fp)
                        for term, support, target_fp in zip(
                            self.terms, self.population_arm_support,
                            self.constituent_target_fingerprints)],
                    a4_rule_id=self.a4_rule_id, assumptions_used=self.assumptions_used,
                    validity_note=self.validity_note,
                    certificate_sha256=self.certificate_sha256,
                    estimation_request=None)


def _normalize_terms(batch: BatchIdentificationResult,
                     terms: tuple[ArmLinearTerm, ...]) -> tuple[ArmLinearTerm, ...]:
    if not terms:
        raise CompositionUnavailable('EMPTY_LINEAR_TARGET')
    order = {node: i for i, node in enumerate(batch.node_ids)}
    result: dict[tuple[str, int, int], Fraction] = {}
    for term in terms:
        if not isinstance(term, ArmLinearTerm):
            raise TypeError('Terms must be explicit ArmLinearTerm instances')
        if term.node_id not in order or term.exposure_state not in batch.exposure_states:
            raise CompositionUnavailable('ARM_COORDINATES_OUTSIDE_SOURCE_BATCH', str(term.coordinates))
        result[term.coordinates] = result.get(term.coordinates, Fraction(0)) + term.coefficient
    # A canceled term does not impose a positivity requirement; it is absent
    # from the mathematical target. Nonzero terms are checked without dropping.
    clean = [ArmLinearTerm(*key, coef) for key, coef in result.items() if coef]
    if not clean:
        raise CompositionUnavailable('ZERO_LINEAR_TARGET', 'All coefficients cancel')
    clean.sort(key=lambda t: (order[t.node_id], t.own_treatment, t.exposure_state))
    return tuple(clean)


def _check_batch_envelope(batch: BatchIdentificationResult) -> None:
    """Integrity + authoritative anchor replay, WITHOUT recomputing 1,200 arms.

    Every actually used arm is separately checked by _check_term_support below.
    This is stronger than trusting a Batch VERIFIED field, while preventing
    quadratic repeated full-Batch replays for every new business contrast.
    """
    if not isinstance(batch, BatchIdentificationResult) or batch.estimation_request is not None:
        raise CompositionUnavailable('SOURCE_POPULATION_BATCH_REQUIRED')
    if batch.contract_version != _BATCH_VERSION or batch.verification_status != 'VERIFIED':
        raise CompositionUnavailable('SOURCE_BATCH_CONTRACT_INVALID')
    if batch.anchor.task is not batch.template:
        raise CompositionUnavailable('SOURCE_BATCH_ANCHOR_BINDING_MISMATCH')
    spec = IdentificationSpec.model_validate(batch.template.identification_spec)
    net, contract = spec.network_exposure, spec.randomized_network_arm_theorem_contract
    if net is None or contract is None or tuple(net.node_ids) != batch.node_ids:
        raise CompositionUnavailable('SOURCE_BATCH_NETWORK_MISMATCH')
    if contract.grouping in W_G_GROUPINGS:
        # Weighted/grouped state axis is the union of reachable canonical states
        # across nodes (non-integer coordinates). Rebuild it from the independent
        # oracle, never from the batch's own declared axis.
        exposure = exposure_object(contract)
        engine = AssignmentSpec(contract.design)
        engine._validate_network(net)
        reachable = set()
        for node in net.node_ids:
            oracle = _verify_joint_support(network=net, design=engine,
                exposure=exposure, node_id=node, proposed={})["oracle"]
            reachable.update(exposure_state_str(exposure, s)
                             for (a, s), p in oracle.items() if p)
        expected_states = tuple(sorted(reachable, key=str))
    else:
        exposure_spec = ExposureSpec(contract.grouping, contract.core_collaborators)
        expected_states = (tuple(range(net.max_degree() + 1))
                           if contract.grouping == "exact_treated_neighbor_count"
                           else exposure_spec.states)
    if batch.exposure_states != expected_states:
        raise CompositionUnavailable('SOURCE_BATCH_EXPOSURE_STATES_MISMATCH')
    source_digest=spec_fingerprint(spec)
    if batch.source_spec_sha256 != source_digest:
        raise CompositionUnavailable('SOURCE_BATCH_SPEC_MISMATCH')
    content=dict(version=_BATCH_VERSION, source_spec_sha256=source_digest,
                 node_ids=batch.node_ids, exposure_states=batch.exposure_states,
                 joint_support=batch.population_joint_support,arm_status=batch.arm_status,
                 arm_reason=batch.arm_reason,target_fingerprints=batch.target_fingerprints)
    if batch.batch_sha256 != _batch_digest(content):
        raise CompositionUnavailable('SOURCE_BATCH_DIGEST_MISMATCH')
    if (len(batch.arm_status)!=len(batch.node_ids) or
        any(len(row)!=2 or any(len(arm)!=len(expected_states) for arm in row)
            for row in batch.arm_status)):
        raise CompositionUnavailable('SOURCE_BATCH_SHAPE_INVALID')
    actual_coverage=('ALL_POINT_IDENTIFIED' if all(
        status=='POINT' for node in batch.arm_status for arm in node for status in arm)
        else 'SOME_ARMS_UNSUPPORTED')
    if actual_coverage != batch.coverage_status:
        raise CompositionUnavailable('SOURCE_BATCH_COVERAGE_MISMATCH')
    replay_population_identification(batch.anchor)
    checked=identify(batch.template)
    if checked.status!='POINT' or checked.verification_status!='VERIFIED' or checked.result!=batch.anchor.result:
        raise CompositionUnavailable('SOURCE_BATCH_ANCHOR_REPLAY_FAILED')


def _check_term_support(batch: BatchIdentificationResult, term: ArmLinearTerm,
                        cell: dict) -> None:
    """Re-evaluate used cell with two independent exact probability methods.

    This does NOT infer q from observed T and does NOT inspect outcomes. The
    unused 1,200-arm matrix is protected by the source Batch digest; only
    mathematically relevant nonzero terms require fresh support proofs.
    """
    spec=IdentificationSpec.model_validate(batch.template.identification_spec)
    net, contract=spec.network_exposure,spec.randomized_network_arm_theorem_contract
    a,s,node=term.own_treatment,term.exposure_state,term.node_id
    engine=AssignmentSpec(contract.design)
    engine._validate_network(net)
    if contract.grouping in W_G_GROUPINGS:
        # Weighted/grouped exposures use a canonical string coordinate; parse it
        # back to the exact hashable state the support map is keyed by.
        exposure=exposure_object(contract)
        state=queried_exposure_state(exposure,s)
        joint=SupportEngine.joint_support(network=net, assignment=engine, exposure=exposure, node_id=node)
        produced=joint.get((a,state), Fraction(0))
        oracle=_verify_joint_support(network=net, design=engine,
            exposure=exposure, node_id=node, proposed={})["oracle"]
        independently=oracle.get((a,state), Fraction(0))
    else:
        grouping=ExposureSpec(contract.grouping,contract.core_collaborators)
        reference=(frozenset(contract.core_collaborators[node])
                   if contract.grouping==GROUP_E3 else None)
        if isinstance(contract.design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
            joint=SupportEngine.joint_support(network=net, assignment=engine, exposure=grouping, node_id=node)
            produced=joint.get((a,s), Fraction(0))
            oracle=_verify_joint_support(network=net, design=as_design_dataclass(contract.design),
                exposure=grouping, node_id=node, proposed={})["oracle"]
            independently=oracle.get((a,s), Fraction(0))
        else:
            law=engine.conditional_neighbor_count_law(net,node,a,reference_nodes=reference)
            produced=SupportEngine.from_count_law(law,grouping,s).joint_probability
            neighbor_counts=None
            if isinstance(contract.design,HeterogeneousBernoulliDesignV1):
                from ._internal.identification.randomized_arm_family.assignment import neighbor_set
                members=neighbor_set(net,node) if reference is None else set(reference)
                neighbor_counts=_independent_count_masses(contract.design,members)
            independently=_support_comparison(contract.design,net,node,a,(s,),
                                              contract.grouping,reference,neighbor_counts)[s]
    if produced!=independently or str(produced)!=cell['joint_support']:
        raise CompositionUnavailable('SOURCE_ARM_SUPPORT_INDEPENDENT_REPLAY_MISMATCH',str(term.coordinates))
    if cell['target_fingerprint'] != arm_target_fingerprint(net,contract,node,a,s):
        raise CompositionUnavailable('SOURCE_ARM_TARGET_FINGERPRINT_MISMATCH',str(term.coordinates))


def _validate_a4(batch: BatchIdentificationResult, source: A4SourceV1,
                 terms: tuple[ArmLinearTerm, ...]) -> tuple[str, tuple[str, ...]]:
    if not isinstance(source, A4SourceV1):
        raise CompositionUnavailable('TYPED_A4_SOURCE_REQUIRED')
    refs = _refs(batch.template)
    if (source.source_spec_fingerprint != batch.source_spec_sha256
        or source.source_spec_fingerprint != refs['spec']
        or source.network_fingerprint != refs['network']
        or source.assignment_law_fingerprint != refs['law']
        or source.node_order != batch.node_ids
        or source.context != refs['context']
        or source.outcome != refs['outcome']):
        raise CompositionUnavailable('A4_SOURCE_CONTEXT_OR_DESIGN_MISMATCH')
    if source.regime != 'experimental':
        raise CompositionUnavailable('A4_EXPERIMENTAL_OPERATOR_REQUIRED')
    if source.admission not in _TRUSTED_A4:
        raise CompositionUnavailable('A4_SOURCE_NOT_ADMITTED')
    if source.availability not in {'SYMBOLIC_POPULATION_OPERATOR', 'EXACT_POPULATION_VALUE'}:
        raise CompositionUnavailable('A4_POPULATION_OPERATOR_REQUIRED')
    if source.operator not in _SUPPORTED_A4:
        raise CompositionUnavailable('A4_OPERATOR_NOT_ENTAILED', source.operator)
    if any(t.node_id not in source.outcome_nodes for t in terms):
        raise CompositionUnavailable('A4_NODE_OUTCOME_MISSING')
    if not set(source.outcome_nodes) <= set(batch.node_ids):
        raise CompositionUnavailable('A4_INVALID_OUTCOME_NODES')
    if source.operator == 'NODE_ARM_MEANS':
        if source.exposure_fingerprint != refs['exposure']:
            raise CompositionUnavailable('A4_EXPOSURE_SIGNATURE_MISMATCH')
        missing = [t.coordinates for t in terms if t.coordinates not in source.arm_cells]
        if missing:
            raise CompositionUnavailable('A4_ARM_COVERAGE_INCOMPLETE', str(missing[:3]))
        return 'A4_DIRECT_NODE_ARM_V1', ('SELECT_NODE_ARM_MEANS', 'APPLY_EXACT_LINEAR_COEFFICIENTS')
    if source.operator == 'NODE_FULL_LAW':
        return 'A4_NODE_FULL_LAW_TO_ARM_V1', (
            'DERIVE_EXPOSURE_FROM_FULL_T', 'CONDITION_ON_ARM', 'TAKE_NODE_MEAN', 'LINEAR_COMBINATION')
    if set(source.outcome_nodes) != set(batch.node_ids):
        raise CompositionUnavailable('A4_FULL_JOINT_REQUIRES_ALL_NODES')
    return 'A4_FULL_JOINT_TO_ARM_V1', (
        'DERIVE_EXPOSURE_FROM_FULL_T', 'MARGINALIZE_OTHER_OUTCOMES',
        'CONDITION_ON_ARM', 'TAKE_NODE_MEAN', 'LINEAR_COMBINATION')


def _weights(weights: Mapping[str, Fraction | int | str]) -> tuple[tuple[str, Fraction], ...]:
    if not isinstance(weights, Mapping) or not weights:
        raise CompositionUnavailable('NODE_WEIGHTS_REQUIRED')
    values = []
    for key, raw in weights.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError('Node IDs must be explicit strings')
        weight = _fraction(raw, field='node_weight')
        if weight < 0:
            raise CompositionUnavailable('NEGATIVE_GROUP_WEIGHT')
        if weight:
            values.append((key, weight))
    total = sum((w for _, w in values), Fraction(0))
    if not total:
        raise CompositionUnavailable('ZERO_TOTAL_GROUP_WEIGHT')
    return tuple((node, w / total) for node, w in values)


def _terms_from_recipe(recipe: _CompositionRecipe) -> tuple[ArmLinearTerm, ...]:
    if recipe.kind == 'CUSTOM_LINEAR':
        if (recipe.node_weights or recipe.reference_exposure is not None
            or recipe.comparison_exposure is not None or recipe.cohort_authority is not None):
            raise ValueError('Custom target must only contain declared linear terms')
        return recipe.supplied_terms
    if recipe.kind not in _EFFECTS or recipe.supplied_terms:
        raise ValueError('Unknown or malformed named causal contrast')
    sr, sc = recipe.reference_exposure, recipe.comparison_exposure
    def _exposure_ok(value):
        return ((type(value) is int and value >= 0)
                or (isinstance(value, str) and value.strip()))
    if not _exposure_ok(sr) or not _exposure_ok(sc):
        raise ValueError('Explicit integer or canonical exposure reference and comparison are required')
    if recipe.kind == 'DIRECT' and sr != sc:
        raise CompositionUnavailable('DIRECT_EXPOSURE_LABEL_MISMATCH',
            'DIRECT holds exposure fixed; reference and comparison must be equal')
    if sr == sc and recipe.kind in ('SPILLOVER','TOTAL'):
        raise CompositionUnavailable('INVALID_EFFECT_CONTRAST', 'reference and comparison exposure must differ')
    a = recipe.spillover_own_treatment
    if type(a) is not int or a not in (0, 1):
        raise ValueError('spillover_own_treatment must be binary')
    if not recipe.node_weights:
        raise CompositionUnavailable('NODE_WEIGHTS_REQUIRED')
    if any(w <= 0 for _, w in recipe.node_weights):
        raise CompositionUnavailable('INVALID_NORMALIZED_WEIGHTS')
    if sum((w for _,w in recipe.node_weights), Fraction(0)) != 1:
        raise CompositionUnavailable('WEIGHTS_NOT_NORMALIZED')
    if len({node for node, _ in recipe.node_weights}) != len(recipe.node_weights):
        raise CompositionUnavailable('DUPLICATE_NODES')
    if len(recipe.node_weights)>1:
        if recipe.cohort_authority not in _COHORT_AUTHORITY or not recipe.cohort_evidence:
            raise CompositionUnavailable('PRETREATMENT_GROUP_EVIDENCE_REQUIRED')
    elif recipe.cohort_authority is not None and recipe.cohort_authority not in _COHORT_AUTHORITY:
        raise ValueError('Invalid group source status')
    out = []
    for node, w in recipe.node_weights:
        if recipe.kind == 'DIRECT':
            out.extend((ArmLinearTerm(node,1,sr,w), ArmLinearTerm(node,0,sr,-w)))
        elif recipe.kind == 'SPILLOVER':
            out.extend((ArmLinearTerm(node,a,sc,w), ArmLinearTerm(node,a,sr,-w)))
        else:
            out.extend((ArmLinearTerm(node,1,sc,w), ArmLinearTerm(node,0,sr,-w)))
    return tuple(out)


def _format_functional(terms: tuple[ArmLinearTerm, ...]) -> str:
    # Text is a *symbolic formula*, not a numerical prediction.
    pieces = []
    for term in terms:
        c = term.coefficient
        atom = (f'E[Y_{term.node_id}^obs | W, T_{term.node_id}={term.own_treatment}, '
                f'S_{term.node_id}={term.exposure_state}]')
        sign = '+' if c > 0 else '-'
        mag = abs(c)
        pieces.append((sign, ('' if mag == 1 else str(mag) + '*') + atom))
    first, *rest = pieces
    result = ('' if first[0] == '+' else '-') + first[1]
    for sign, piece in rest:
        result += f' {sign} {piece}'
    return result


def _recipe_payload(recipe: _CompositionRecipe) -> dict:
    return dict(kind=recipe.kind, node_weights=[(n, str(w)) for n,w in recipe.node_weights],
                reference_exposure=recipe.reference_exposure,
                comparison_exposure=recipe.comparison_exposure,
                spillover_own_treatment=recipe.spillover_own_treatment,
                supplied_terms=[t.json_payload() for t in recipe.supplied_terms],
                cohort_authority=recipe.cohort_authority, cohort_evidence=recipe.cohort_evidence)


def _certificate_payload(batch: BatchIdentificationResult, a4: A4SourceV1,
                         recipe: _CompositionRecipe, terms: tuple[ArmLinearTerm, ...],
                         supports: tuple[str, ...], fps: tuple[str, ...],
                         target_fp: str, a4_rule: str, operations: tuple[str, ...]) -> dict:
    return dict(version=_VERSION, batch_sha256=batch.batch_sha256,
                source_spec_sha256=batch.source_spec_sha256,
                a4_source_sha256=_hash(a4.__dict__),
                target_fingerprint=target_fp, recipe=_recipe_payload(recipe),
                terms=[t.json_payload() for t in terms],
                joint_arm_support=supports, source_arm_target_fingerprints=fps,
                a4_rule_id=a4_rule, a4_operations=operations,
                workflow='R1A_VERIFIED_POPULATION_LINEAR_COMPOSITION')


def _compute(batch: BatchIdentificationResult, a4: A4SourceV1,
             recipe: _CompositionRecipe) -> VerifiedCompositionV18:
    terms = _normalize_terms(batch, _terms_from_recipe(recipe))
    if recipe.cohort_authority == 'TRUSTED_FIXTURE':
        spec = IdentificationSpec.model_validate(batch.template.identification_spec)
        if spec.provenance.get('mode') != 'synthetic_source_contract':
            raise CompositionUnavailable('TRUSTED_FIXTURE_REQUIRES_SYNTHETIC_STUDY')
    # Nonzero weights only; no support-null term is ever silently omitted.
    if (recipe.kind != 'CUSTOM_LINEAR' and
        any(n not in batch.node_ids for n, _ in recipe.node_weights)):
        raise CompositionUnavailable('GROUP_NODE_OUTSIDE_SOURCE_NETWORK')
    supports, fps, obs = [], [], []
    for t in terms:
        cell = batch.cell(t.node_id, t.own_treatment, t.exposure_state)
        if cell['status'] != 'POINT' or cell['joint_support'] is None:
            raise CompositionUnavailable(cell['reason_code'] or 'ARM_NOT_POINT', str(t.coordinates))
        if Fraction(cell['joint_support']) <= 0:
            raise CompositionUnavailable('ZERO_ARM_SUPPORT', str(t.coordinates))
        _check_term_support(batch,t,cell)
        supports.append(cell['joint_support'])
        fps.append(cell['target_fingerprint'])
        obs.append(f'E[Y_{t.node_id}^obs | W,T_{t.node_id}={t.own_treatment},S_{t.node_id}={t.exposure_state}]')
    a4_rule, operations = _validate_a4(batch, a4, terms)
    # Kind and authority do not alter the *causal target*. The normalized
    # mathematical coefficients and source q/g/W identity do.
    spec = IdentificationSpec.model_validate(batch.template.identification_spec)
    target_fp = _hash(dict(
        version='network-linear-arm-mean-target-v1.8',
        # Mathematical identity uses the validated child target fingerprints,
        # outcome semantics and conditioning context, not seed query, A4 source,
        # reviewer confirmation or evidence. Those belong to the certificate.
        arm_target_fingerprints=fps,
        coefficients=[str(t.coefficient) for t in terms],
        outcome_variable=spec.query.outcome,
        outcome_kind=batch.template.outcome_kind,
        target_population=spec.query.target_population,
        context=spec.support_domain.get('context_symbol'),
        context_semantics=spec.support_domain.get('context_semantics'),
    ))
    certificate = _certificate_payload(batch, a4, recipe, terms, tuple(supports),
                                       tuple(fps), target_fp, a4_rule, operations)
    return VerifiedCompositionV18(
        source_batch=batch, a4_source=a4, recipe=recipe,
        terms=terms, population_arm_support=tuple(supports),
        constituent_target_fingerprints=tuple(fps),
        required_population_objects=tuple(obs),
        identified_functional=_format_functional(terms),
        a4_rule_id=a4_rule, a4_operations=operations,
        target_fingerprint=target_fp,
        certificate_sha256=_hash(certificate),
    )


def _identify(batch: BatchIdentificationResult, a4_source: A4SourceV1,
              recipe: _CompositionRecipe) -> VerifiedCompositionV18:
    if not isinstance(batch, BatchIdentificationResult):
        raise TypeError('A v1.0 randomized-network arm Batch is required')
    if batch.estimation_request is not None:
        raise CompositionUnavailable('ESTIMATION_REQUEST_NOT_A_POPULATION_CERTIFICATE')
    _check_batch_envelope(batch)  # replay anchor + source digest
    return _compute(batch, a4_source, recipe)  # independently recheck used arms


def identify_verified_linear_target(batch: BatchIdentificationResult, a4_source: A4SourceV1,
                                    terms: tuple[ArmLinearTerm, ...]) -> VerifiedCompositionV18:
    """Custom finite linear functional of POINT arm means, not true policy value."""
    if not isinstance(terms, tuple):
        raise TypeError('Explicit immutable tuple of terms is required')
    return _identify(batch, a4_source, _CompositionRecipe('CUSTOM_LINEAR', supplied_terms=terms))


def identify_verified_node_effect(batch: BatchIdentificationResult, a4_source: A4SourceV1,
                                  *, node_id: str, kind: str,
                                  reference_exposure: int | str, comparison_exposure: int | str,
                                  spillover_own_treatment: int = 1) -> VerifiedCompositionV18:
    """One node: DIRECT=(1,s0)-(0,s0); SPILLOVER=(a,s1)-(a,s0);
    TOTAL=(1,s1)-(0,s0). D2/D3 contrasts are *design-standardized*.
    """
    return _identify(batch, a4_source, _CompositionRecipe(
        kind=kind, node_weights=((node_id, Fraction(1)),),
        reference_exposure=reference_exposure, comparison_exposure=comparison_exposure,
        spillover_own_treatment=spillover_own_treatment,
    ))


def identify_verified_group_effect(batch: BatchIdentificationResult, a4_source: A4SourceV1,
                                   *, kind: str,
                                   node_weights: Mapping[str, Fraction | int | str],
                                   reference_exposure: int | str, comparison_exposure: int | str,
                                   cohort_authority: str, cohort_evidence: str,
                                   spillover_own_treatment: int = 1) -> VerifiedCompositionV18:
    """Pre-declared subgroup mean of design-standardized effects.

    Weights are nonnegative, exact and normalized before use; zero weights are
    omitted. Claimed pretreatment cohort provenance is recorded but cannot be
    externally authenticated by a digest. Outcome-based subgroup discovery is
    not certified by this contract.
    """
    weights = _weights(node_weights)
    if cohort_authority not in _COHORT_AUTHORITY or not isinstance(cohort_evidence,str) or not cohort_evidence.strip():
        raise CompositionUnavailable('PRETREATMENT_GROUP_EVIDENCE_REQUIRED')
    return _identify(batch, a4_source, _CompositionRecipe(
        kind=kind, node_weights=weights,
        reference_exposure=reference_exposure, comparison_exposure=comparison_exposure,
        spillover_own_treatment=spillover_own_treatment,
        cohort_authority=cohort_authority, cohort_evidence=cohort_evidence,
    ))


def replay_verified_composition(saved: VerifiedCompositionV18) -> VerifiedCompositionV18:
    """Re-derive every term, source A4 entitlement, support and certificate.

    A hash is an integrity check on the *declared inputs*, not evidence that an
    external study protocol or information source is genuinely trustworthy.
    """
    if not isinstance(saved, VerifiedCompositionV18):
        raise TypeError('Expected VerifiedCompositionV18')
    if saved.contract_version != _VERSION or saved.status != 'POINT' or saved.verification_status != 'VERIFIED' or saved.estimation_request is not None:
        raise CompositionUnavailable('INVALID_COMPOSITION_ENVELOPE')
    _check_batch_envelope(saved.source_batch)
    expected = _compute(saved.source_batch, saved.a4_source, saved.recipe)
    # Compare only public scalar/tuple semantics, not NumPy-bearing TaskSpec.
    _compare_composition(saved, expected)
    return expected


@dataclass(frozen=True)
class EffectQueryV18:
    """Explicit business query, used to certify many requests with ONE Batch replay.

    A single-node query has one node weight. Multi-node averages require an
    admitted pretreatment cohort authority/evidence; no implicit data selection.
    """
    kind: Literal['DIRECT', 'SPILLOVER', 'TOTAL']
    node_weights: tuple[tuple[str, Fraction | int | str], ...]
    reference_exposure: int | str
    comparison_exposure: int | str
    spillover_own_treatment: int = 1
    cohort_authority: str | None = None
    cohort_evidence: str | None = None

    def __post_init__(self):
        if not isinstance(self.node_weights, tuple) or not self.node_weights:
            raise ValueError('EffectQuery node_weights must be an explicit immutable tuple')
        if (any(not isinstance(item,tuple) or len(item)!=2 for item in self.node_weights)
            or len({item[0] for item in self.node_weights}) != len(self.node_weights)):
            raise ValueError('EffectQuery must have distinct node-weight pairs')
        # Normalize and canonicalize exact, positive weights immediately.
        weights = _weights(dict(self.node_weights))
        object.__setattr__(self,'node_weights',weights)
        if len(weights)>1 and (self.cohort_authority not in _COHORT_AUTHORITY
                               or not self.cohort_evidence):
            raise CompositionUnavailable('PRETREATMENT_GROUP_EVIDENCE_REQUIRED')

    def recipe(self) -> _CompositionRecipe:
        return _CompositionRecipe(kind=self.kind,node_weights=self.node_weights,
            reference_exposure=self.reference_exposure,
            comparison_exposure=self.comparison_exposure,
            spillover_own_treatment=self.spillover_own_treatment,
            cohort_authority=self.cohort_authority,cohort_evidence=self.cohort_evidence)


def compile_effect_query_terms(query: EffectQueryV18) -> tuple[ArmLinearTerm, ...]:
    """Shared exact contrast algebra for R1a and R3; NO identification license.

    This compiles A1 only. Every route must independently establish its own
    A4/A5/A6 before treating these terms as POINT-identified.
    """
    if not isinstance(query, EffectQueryV18):
        raise TypeError('Use a typed EffectQueryV18 for an effect target')
    return _terms_from_recipe(query.recipe())


@dataclass(frozen=True)
class VerifiedCompositionBundleV18:
    """Multi-query R1a result with exactly one verified source Batch per call."""
    source_batch: BatchIdentificationResult
    a4_source: A4SourceV1
    requests: tuple[EffectQueryV18, ...]
    results: tuple[VerifiedCompositionV18, ...]
    bundle_sha256: str
    contract_version: str = _VERSION
    verification_status: str = 'VERIFIED'
    estimation_request: None = None

    def summary(self) -> dict:
        return dict(verification_status=self.verification_status,
                    query_count=len(self.requests),source_batch_sha256=self.source_batch.batch_sha256,
                    bundle_sha256=self.bundle_sha256,
                    results=[x.summary() for x in self.results],estimation_request=None)


def _bundle_payload(batch: BatchIdentificationResult, source: A4SourceV1,
                    requests: tuple[EffectQueryV18, ...],
                    results: tuple[VerifiedCompositionV18, ...]) -> dict:
    return dict(version=_VERSION,batch_sha256=batch.batch_sha256,
                a4_source_sha256=_hash(source.__dict__),
                requests=[_recipe_payload(req.recipe()) for req in requests],
                result_certificates=[x.certificate_sha256 for x in results])


def identify_verified_effect_bundle(batch: BatchIdentificationResult,
                                   a4_source: A4SourceV1,
                                   requests: tuple[EffectQueryV18, ...]) -> VerifiedCompositionBundleV18:
    """Evaluate several effects under one independently checked source anchor.

    The Batch integrity and original theorem anchor are replayed once, then
    every nonzero used arm gets two independent exact support calculations.
    This avoids rechecking *unused* Batch cells on each business query.
    """
    if not isinstance(batch,BatchIdentificationResult) or not isinstance(requests,tuple) or not requests:
        raise ValueError('A verified Batch and a nonempty immutable request tuple are required')
    if any(not isinstance(req,EffectQueryV18) for req in requests):
        raise TypeError('Every request must be an EffectQueryV18')
    _check_batch_envelope(batch)
    results=tuple(_compute(batch,a4_source,req.recipe()) for req in requests)
    return VerifiedCompositionBundleV18(
        source_batch=batch,a4_source=a4_source,requests=requests,results=results,
        bundle_sha256=_hash(_bundle_payload(batch,a4_source,requests,results)))


def _compare_composition(saved: VerifiedCompositionV18,
                        expected: VerifiedCompositionV18) -> None:
    for field in ('terms','population_arm_support','constituent_target_fingerprints',
                  'required_population_objects','identified_functional',
                  'a4_rule_id','a4_operations','target_fingerprint','certificate_sha256',
                  'contract_version','status','verification_status','assumptions_used',
                  'validity_note','estimation_request'):
        if getattr(saved,field)!=getattr(expected,field):
            raise CompositionUnavailable('COMPOSITION_REPLAY_MISMATCH',field)


def replay_verified_effect_bundle(saved: VerifiedCompositionBundleV18) -> VerifiedCompositionBundleV18:
    """Recompute the original theorem, all requested compositions, then the bundle digest."""
    if not isinstance(saved, VerifiedCompositionBundleV18) or saved.contract_version!=_VERSION or saved.verification_status!='VERIFIED' or saved.estimation_request is not None:
        raise CompositionUnavailable('INVALID_COMPOSITION_BUNDLE')
    if len(saved.requests)!=len(saved.results) or not saved.requests:
        raise CompositionUnavailable('COMPOSITION_BUNDLE_LENGTH_MISMATCH')
    _check_batch_envelope(saved.source_batch)
    fresh=tuple(_compute(saved.source_batch,saved.a4_source,req.recipe()) for req in saved.requests)
    for result,exp in zip(saved.results,fresh):
        _compare_composition(result,exp)
    certificate=_hash(_bundle_payload(saved.source_batch,saved.a4_source,saved.requests,fresh))
    if certificate!=saved.bundle_sha256:
        raise CompositionUnavailable('COMPOSITION_BUNDLE_REPLAY_MISMATCH')
    return VerifiedCompositionBundleV18(saved.source_batch,saved.a4_source,saved.requests,
                                        fresh,certificate)


__all__ += ['EffectQueryV18','VerifiedCompositionBundleV18',
            'identify_verified_effect_bundle','replay_verified_effect_bundle']
