"""v2.8 P0 opt-in, read-only cross-R3 target/A4 consistency audit.

It consumes *already verified* R3 business outcomes and reruns their original
verifiers. It never identifies a new target, changes a certificate, replaces
A0 human review, certifies observed data, or creates an EstimationRequest.

For small graphs (<=12 binary nodes) it independently expands finite laws,
node-independent laws, and mixtures of node-independent laws to the same exact
P_obs(T-vector|W) representation. Large independent laws are compared directly;
large mixtures remain UNRESOLVED rather than being treated as equal or unequal.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Literal

from .identification_a4_shadow import _sha
from .identification_business import (
    VerifiedBusinessOutcomeV21, replay_verified_business_outcome,
)
from .identification_observational_r3 import (
    ObservationalFinitePopulationV23, VerifiedObservationalPolicyV23,
)
from .identification_observational_effects import VerifiedObservationalEffectsV26
from .identification_observational_factorized_a4 import (
    ObservationalFactorizedArmPopulationV27P1, VerifiedObservationalFactorizedEffectsV27P1,
)
from .identification_observational_mixture_a4 import (
    ObservationalMixtureArmPopulationV28P1, VerifiedObservationalMixtureEffectsV28P1,
)
from .identification_observational_exposure_adjustment import (
    ObservationalStratifiedArmPopulationV27P2, VerifiedExposureAdjustedEffectsV27P2,
)
from .identification_observational_nodewise_adjustment import (
    NodewiseLocalArmPopulationV28, VerifiedNodewiseAdjustedEffectsV28,
)

CONTRACT = 'CFM-ID-R3-TARGET-A4-READONLY-v2.8-P0'
MAX_EXACT_ENUMERATION_NODES = 12
MAX_AUDITED_RESULTS = 16

_RESULT_TYPES = (
    VerifiedObservationalPolicyV23, VerifiedObservationalEffectsV26,
    VerifiedObservationalFactorizedEffectsV27P1, VerifiedObservationalMixtureEffectsV28P1,
    VerifiedExposureAdjustedEffectsV27P2, VerifiedNodewiseAdjustedEffectsV28,
)


@dataclass(frozen=True)
class R3TargetA4ReceiptV28P0:
    route: str
    query_type: str
    study_scope_digest: str
    protocol_digest: str
    node_order: tuple[str, ...]
    context: str
    signature_fingerprint: str | None
    target_class: str
    original_target_fingerprints: tuple[str, ...]
    cross_representation_fingerprints: tuple[str, ...] | None
    a4_source_id: str
    a4_provenance: str
    a4_operator: str
    a4_model_fingerprint: str
    marginal_law_fingerprint: str | None
    marginal_law_comparison: Literal['EXACT_FULL_LAW', 'LARGE_INDEPENDENT_LAW', 'NOT_EXPANDED']
    # No A4 observed-outcome *values* are supplied or checked by this audit.

    def summary(self) -> dict:
        return dict(vars(self))


@dataclass(frozen=True)
class R3PairAuditV28P0:
    relationship: str
    a4_consistency: str
    same_target_certified: bool
    can_merge_as_one_symbolic_target: bool
    reasons: tuple[str, ...]
    left: R3TargetA4ReceiptV28P0
    right: R3TargetA4ReceiptV28P0

    def summary(self) -> dict:
        return dict(contract=CONTRACT,relationship=self.relationship,
            a4_consistency=self.a4_consistency,
            same_target_certified=self.same_target_certified,
            can_merge_as_one_symbolic_target=self.can_merge_as_one_symbolic_target,
            reasons=list(self.reasons),left=self.left.summary(),right=self.right.summary(),
            estimation={'status':'NO_ADAPTER','request':None},
            causal_assumptions_proven_from_real_data=False,
            outcome_mean_operator_value_equivalence_proven=False)


def _mixture_rows(source):
    if isinstance(source, ObservationalFinitePopulationV23):
        return None
    if isinstance(source, ObservationalFactorizedArmPopulationV27P1):
        return ((Fraction(1), tuple(Fraction(x) for x in source.treatment_one_probabilities)),)
    if isinstance(source, ObservationalMixtureArmPopulationV28P1):
        return tuple((Fraction(weight), tuple(Fraction(x) for x in ps))
                     for weight,ps in source.components)
    if isinstance(source, ObservationalStratifiedArmPopulationV27P2):
        return tuple((Fraction(b.mass), tuple(Fraction(x) for x in b.treatment_one_probabilities))
                     for b in source.strata)
    if isinstance(source, NodewiseLocalArmPopulationV28):
        return tuple((Fraction(p.mass), tuple(Fraction(x) for x in p.treatment_one_probabilities))
                     for p in source.profiles)
    raise TypeError('Unknown R3 population-source type')


def _expanded_law(source):
    """Independent arithmetic oracle. Never calls a theorem's support engine."""
    n = len(source.node_order)
    if n > MAX_EXACT_ENUMERATION_NODES:
        return None
    if isinstance(source, ObservationalFinitePopulationV23):
        return tuple((t, str(Fraction(v))) for t,v in source.assignment_masses)
    rows = _mixture_rows(source)
    result=[]
    for allocation in product((0,1),repeat=n):
        total=Fraction(0)
        for mass,probs in rows:
            weight=mass
            for treated,p in zip(allocation,probs):
                weight *= p if treated else (1-p)
                if not weight:
                    break
            total += weight
        if total:
            result.append((allocation,str(total)))
    return tuple(result)


def _law_identity(source):
    """Only exact equality/inequality of whole observational treatment laws is claimed."""
    expanded=_expanded_law(source)
    if expanded is not None:
        return (_sha(dict(kind='EXACT_FULL_BINARY_TREATMENT_LAW_V1',
                          node_order=source.node_order, masses=expanded)), 'EXACT_FULL_LAW')
    if isinstance(source, ObservationalFactorizedArmPopulationV27P1):
        return (_sha(dict(kind='LARGE_INDEPENDENT_BINARY_TREATMENT_LAW_V1',
                          node_order=source.node_order,
                          propensities=source.treatment_one_probabilities)),
                'LARGE_INDEPENDENT_LAW')
    # A large mixture might have multiple representations of the same marginal.
    # Its model digest cannot establish an inequality of observational laws.
    return None, 'NOT_EXPANDED'


def _source_model_fingerprint(source):
    """Within-operator source declaration (ignores coverage and provenance)."""
    if isinstance(source, ObservationalFinitePopulationV23):
        description=('FULL_ASSIGNMENT',source.assignment_masses)
    elif isinstance(source, ObservationalFactorizedArmPopulationV27P1):
        description=('FACTORIZED',source.treatment_one_probabilities)
    elif isinstance(source, ObservationalMixtureArmPopulationV28P1):
        description=('FINITE_MIXTURE_FACTORIZED',source.components)
    elif isinstance(source, ObservationalStratifiedArmPopulationV27P2):
        description=('SHARED_STRATA',source.adjustment_variable,
                     tuple((s.label,s.mass,s.treatment_one_probabilities) for s in source.strata))
    elif isinstance(source, NodewiseLocalArmPopulationV28):
        description=('NODEWISE_PROFILES',source.covariate_schema_fingerprint,
                     tuple((p.label,p.mass,p.node_binary_features,p.treatment_one_probabilities)
                           for p in source.profiles))
    else:
        raise TypeError('Unsupported R3 source')
    return _sha(dict(version='R3_A4_SOURCE_MODEL_V1',node_order=source.node_order,
                     declared_law=description))


def inspect_r3_target_a4_v28p0(outcome: VerifiedBusinessOutcomeV21) -> R3TargetA4ReceiptV28P0:
    """Fail closed on non-POINT, tampering, and unsupported/non-R3 results."""
    if not isinstance(outcome, VerifiedBusinessOutcomeV21) or outcome.status != 'POINT':
        raise ValueError('R3_AUDIT_REQUIRES_VERIFIED_POINT_BUSINESS_RESULT')
    if not isinstance(outcome.result, _RESULT_TYPES):
        raise ValueError('R3_AUDIT_SUPPORTS_ONLY_EXISTING_R3_ROUTES')
    if not replay_verified_business_outcome(outcome):
        raise ValueError('R3_AUDIT_THEOREM_REPLAY_FAILED')
    result=outcome.result
    st=result.study
    source=result.source
    sig=getattr(result,'signature',None)
    signature_fp=None if sig is None else sig.signature_fingerprint
    marginal_fp,comparison=_law_identity(source)
    proofs=getattr(result,'proofs',None)
    original=(tuple(p.target_fingerprint for p in proofs) if proofs is not None
              else (result.target_fingerprint,))
    if isinstance(result,(VerifiedObservationalEffectsV26,VerifiedObservationalFactorizedEffectsV27P1,
                          VerifiedObservationalMixtureEffectsV28P1)):
        target_class='OBSERVATIONAL_P_STANDARDIZED_CONTRAST'
        # A large observational mixture has no tractable unique marginal-law
        # fingerprint. Never substitute its representation digest for proof of
        # cross-representation equality; retain only the theorem's own target
        # fingerprint and let the comparison fail closed unless models coincide.
        common=(None if marginal_fp is None else tuple(_sha(dict(
                   version='CROSS_R3_P_STANDARDIZED_LINEAR_TARGET_V1',
                   scope=st.shared_scope_digest,signature=signature_fp,
                   law=marginal_fp,terms=[term.json_payload() for term in p.terms]))
                   for p in result.proofs))
    elif isinstance(result,VerifiedObservationalPolicyV23):
        target_class='OBSERVATIONAL_FIXED_POLICY_VALUE'
        common=None
    elif isinstance(result,VerifiedExposureAdjustedEffectsV27P2):
        target_class='SHARED_PRETREATMENT_STRATUM_EXPOSURE_TARGET'
        common=None
    else:
        target_class='NODEWISE_PRETREATMENT_COVARIATE_EXPOSURE_TARGET'
        common=None
    return R3TargetA4ReceiptV28P0(
        route=outcome.route,query_type=outcome.query_type,
        study_scope_digest=st.shared_scope_digest,protocol_digest=st.protocol_digest,
        node_order=st.node_order,context=st.context_reference,
        signature_fingerprint=signature_fp,target_class=target_class,
        original_target_fingerprints=original,cross_representation_fingerprints=common,
        a4_source_id=source.source_id,a4_provenance=source.provenance,
        a4_operator=source.operator,a4_model_fingerprint=_source_model_fingerprint(source),
        marginal_law_fingerprint=marginal_fp,marginal_law_comparison=comparison,
    )


def _compare_receipts(left, right):
    same_scope=(left.study_scope_digest==right.study_scope_digest
                and left.protocol_digest==right.protocol_digest
                and left.node_order==right.node_order)
    reasons=[]
    if not same_scope:
        return R3PairAuditV28P0('DIFFERENT_STUDY_OR_PROTOCOL','NOT_COMPARABLE',False,False,
            ('DIFFERENT_STUDY_OR_PROTOCOL',),left,right)
    same_source=left.a4_source_id==right.a4_source_id
    conflicting_source=(same_source and left.a4_provenance!=right.a4_provenance)
    if conflicting_source:
        reasons.append('A4_SAME_SOURCE_ID_DIFFERENT_PROVENANCE')
    if (same_source and left.a4_operator==right.a4_operator
        and left.a4_model_fingerprint!=right.a4_model_fingerprint):
        reasons.append('A4_SAME_SOURCE_ID_DIFFERENT_MODEL')
    if (left.marginal_law_fingerprint is not None
        and right.marginal_law_fingerprint is not None
        and left.marginal_law_comparison==right.marginal_law_comparison):
        if left.marginal_law_fingerprint==right.marginal_law_fingerprint:
            a4='EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT'
        else:
            a4='CONFLICTING_MARGINAL_TREATMENT_LAWS'
            reasons.append('A4_SAME_STUDY_MARGINAL_LAW_CONFLICT')
    elif (left.marginal_law_fingerprint is None or right.marginal_law_fingerprint is None):
        # Full equality can still be certified if the identical declared model
        # is reused under the identical type of A4 operator.
        if (left.a4_operator==right.a4_operator
            and left.a4_model_fingerprint==right.a4_model_fingerprint):
            a4='IDENTICAL_DECLARED_MODEL_NONENUMERATED'
        else:
            a4='MARGINAL_LAW_EQUIVALENCE_UNRESOLVED'
            if same_source:
                reasons.append('A4_SOURCE_ID_REUSED_WITH_UNRESOLVED_LAW')
    else:
        a4='MARGINAL_LAW_EQUIVALENCE_UNRESOLVED'
    if reasons:
        relationship='CONFLICTING_OR_UNRESOLVED_A4_SOURCE'
        return R3PairAuditV28P0(relationship,a4,False,False,tuple(reasons),left,right)
    if left.target_class != right.target_class:
        relation='CROSS_TARGET_SEMANTICS_NOT_CERTIFIED_EQUIVALENT'
        same=False
    elif left.target_class=='OBSERVATIONAL_P_STANDARDIZED_CONTRAST':
        if left.cross_representation_fingerprints is None or right.cross_representation_fingerprints is None:
            # Unknown equality of large mixtures is NOT same target merely
            # because both common fingerprints are None.
            same=(a4=='IDENTICAL_DECLARED_MODEL_NONENUMERATED'
                  and left.a4_operator==right.a4_operator
                  and left.original_target_fingerprints==right.original_target_fingerprints)
            relation='SAME_TARGET' if same else 'TARGET_EQUIVALENCE_NOT_CERTIFIED'
        else:
            same=(left.cross_representation_fingerprints==right.cross_representation_fingerprints)
            relation='SAME_TARGET' if same else 'DISTINCT_DECLARED_TARGET'
    else:
        same=(left.original_target_fingerprints==right.original_target_fingerprints)
        relation='SAME_TARGET' if same else 'TARGET_EQUIVALENCE_NOT_CERTIFIED'
    certified_a4=a4 in ('EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT',
                        'IDENTICAL_DECLARED_MODEL_NONENUMERATED')
    return R3PairAuditV28P0(relation,a4,same,bool(same and certified_a4),
        () if same and certified_a4 else ('NO_AUTHORIZED_TARGET_MERGE',),left,right)


def compare_r3_target_a4_v28p0(left: VerifiedBusinessOutcomeV21,
                                  right: VerifiedBusinessOutcomeV21) -> R3PairAuditV28P0:
    """Explain target/A4 relationships; never call a numeric estimator."""
    return _compare_receipts(inspect_r3_target_a4_v28p0(left),
                             inspect_r3_target_a4_v28p0(right))


def inspect_r3_joint_handoff_v28p0(outcomes: tuple[VerifiedBusinessOutcomeV21,...],
                                     *, require_single_target: bool = True) -> dict:
    """Audited symbolic grouping only. Reject unsafe or unknown target merging.

    With require_single_target=False, distinct targets are listed, not merged.
    A4 conflicts and unresolved same-source reuse are always rejected.
    """
    if (not isinstance(outcomes,tuple) or not 2<=len(outcomes)<=MAX_AUDITED_RESULTS
        or type(require_single_target) is not bool):
        raise ValueError('R3_AUDIT_TYPED_BOUNDED_OUTCOME_BATCH_REQUIRED')
    receipts=tuple(inspect_r3_target_a4_v28p0(v) for v in outcomes)
    pairs=tuple(_compare_receipts(receipts[i],receipts[j])
                for i in range(len(receipts)) for j in range(i+1,len(receipts)))
    for p in pairs:
        if p.relationship=='CONFLICTING_OR_UNRESOLVED_A4_SOURCE':
            raise ValueError('R3_AUDIT_A4_SOURCE_CONFLICT_OR_UNRESOLVED_REUSE')
    all_same=all(p.can_merge_as_one_symbolic_target for p in pairs)
    if require_single_target and not all_same:
        raise ValueError('R3_AUDIT_TARGET_EQUIVALENCE_NOT_CERTIFIED')
    return dict(contract=CONTRACT,receipt_count=len(receipts),pair_count=len(pairs),
        target_merge_certified=all_same,
        # Even if the mathematical target coincides, independent symbolic
        # conditional-outcome operators are not empirically reconciled.
        conditional_mean_values_reconciled=False,
        route_theorem_replays_completed=True,
        receipts=[r.summary() for r in receipts],
        pair_relations=[p.summary() for p in pairs],
        estimation={'status':'NO_ADAPTER','adapter_id':None,'request':None,
                    'numeric_estimate':None},
        policy={'numeric_policy_value':None},
        scientific_assumptions_verified_in_real_world=False,
        note='Read-only identification audit; no population values, estimator or policy value computed.')


__all__=['R3TargetA4ReceiptV28P0','R3PairAuditV28P0',
         'inspect_r3_target_a4_v28p0','compare_r3_target_a4_v28p0',
         'inspect_r3_joint_handoff_v28p0']
