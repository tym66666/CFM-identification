"""v2.1 opt-in verified business query dispatcher for the network-first POINT routes.

No assumption discovery, no synthesis of an estimator/causal proof, no scalar
business effect values. Every POINT is delegated to its original theorem,
verifier and replay API. No changes to existing identify/Estimation/Policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import TaskSpec, IdentificationResult
from .identification import identify, replay_population_identification
from .identification_batch import BatchIdentificationResult
from .identification_composition import (
    EffectQueryV18, VerifiedCompositionBundleV18,
    identify_verified_effect_bundle, replay_verified_effect_bundle,
)
from .identification_a4_shadow import A4SourceV1
from .identification_policy_r1b import (
    R1bPolicyUnavailable, VerifiedFixedPolicyV19, VerifiedFinitePolicyMixtureV19,
    identify_verified_fixed_policy, identify_verified_finite_policy_mixture,
    replay_verified_fixed_policy, replay_verified_finite_policy_mixture,
)
from .identification_policy_r2 import (
    R2PolicyUnavailable, MeanSignatureSufficiencyV20, SignatureSpecV20,
    SignaturePopulationSourceV20, VerifiedSignaturePolicyV20,
    identify_verified_signature_policy, replay_verified_signature_policy,
)
from .identification_observational_effects import (
    VerifiedObservationalEffectsV26, identify_observational_effects_v26,
    replay_observational_effects_v26,
)
from .identification_observational_factorized_a4 import (
    ObservationalFactorizedArmPopulationV27P1, VerifiedObservationalFactorizedEffectsV27P1,
    identify_observational_factorized_effects_v27p1,
    replay_observational_factorized_effects_v27p1,
)
from .identification_observational_mixture_a4 import (
    ObservationalMixtureArmPopulationV28P1, VerifiedObservationalMixtureEffectsV28P1,
    identify_observational_mixture_effects_v28p1,
    replay_observational_mixture_effects_v28p1,
)
from .identification_observational_exposure_adjustment import (
    ObservationalStratifiedArmPopulationV27P2, ScopedExposureAdjustmentA5V27P2,
    VerifiedExposureAdjustedEffectsV27P2,
    identify_observational_exposure_adjusted_effects_v27p2,
    replay_observational_exposure_adjusted_effects_v27p2,
)
from .identification_observational_nodewise_adjustment import (
    NodewiseLocalArmPopulationV28, ScopedNodewiseAdjustmentA5V28,
    VerifiedNodewiseAdjustedEffectsV28,
    identify_observational_nodewise_effects_v28,
    replay_observational_nodewise_effects_v28,
)
from .network_inquiry_shadow import NetworkStudyContextV17, NetworkA4SourceV17
from .identification_route_shadow import TargetSemanticsV15
from .identification_observational_r3 import (
    ObservationalFinitePopulationV23, VerifiedObservationalPolicyV23,
    R3Unavailable, identify_observational_policy_v23, replay_observational_policy_v23,
)
from ._internal.identification.schemas import Assumption


@dataclass(frozen=True)
class ArmInquiryV21:
    task: TaskSpec


@dataclass(frozen=True)
class EffectsInquiryV21:
    batch: BatchIdentificationResult
    a4_source: A4SourceV1
    requests: tuple[EffectQueryV18, ...]


@dataclass(frozen=True)
class FixedPolicyInquiryV21:
    study: NetworkStudyContextV17
    target: TargetSemanticsV15
    assumptions: tuple[Assumption, ...]
    r1b_sources: tuple[NetworkA4SourceV17, ...] = ()
    r2_signature: SignatureSpecV20 | None = None
    r2_sufficiency: MeanSignatureSufficiencyV20 | None = None
    r2_sources: tuple[SignaturePopulationSourceV20, ...] = ()


@dataclass(frozen=True)
class FinitePolicyInquiryV21:
    # Only previously verified R1b components; this cannot bypass q(z)>0.
    components: tuple[VerifiedFixedPolicyV19, ...]
    policy_probabilities: tuple[str, ...]


@dataclass(frozen=True)
class ObservationalPolicyInquiryV23:
    study: NetworkStudyContextV17
    target: TargetSemanticsV15
    source: ObservationalFinitePopulationV23
    assumptions: tuple[Assumption, ...]
    signature: SignatureSpecV20 | None = None
    sufficiency: MeanSignatureSufficiencyV20 | None = None


@dataclass(frozen=True)
class ObservationalEffectsInquiryV26:
    """R3 arm/effect A1 query; reuses R1a EffectQuery algebra, not its A5 q."""
    study: NetworkStudyContextV17
    source: ObservationalFinitePopulationV23 | ObservationalFactorizedArmPopulationV27P1 | ObservationalMixtureArmPopulationV28P1
    assumptions: tuple[Assumption, ...]
    signature: SignatureSpecV20
    requests: tuple[EffectQueryV18, ...]


@dataclass(frozen=True)
class ObservationalExposureAdjustedEffectsInquiryV27P2:
    """New R3 exposure-outcome target; NOT a p-standardized arm query."""
    study: NetworkStudyContextV17
    source: ObservationalStratifiedArmPopulationV27P2
    assumptions: tuple[Assumption,...]
    signature: SignatureSpecV20
    license: ScopedExposureAdjustmentA5V27P2
    requests: tuple[EffectQueryV18,...]


@dataclass(frozen=True)
class ObservationalNodewiseAdjustedEffectsInquiryV28:
    """Opt-in R3 nodewise (X_i, neighbor positive X count) adjusted exposure target.

    Its target is neither the old p-standardized arm nor the shared-B adjusted
    exposure result.  The licenses and A4 must be supplied explicitly.
    """
    study: NetworkStudyContextV17
    source: NodewiseLocalArmPopulationV28
    assumptions: tuple[Assumption, ...]
    signature: SignatureSpecV20
    license: ScopedNodewiseAdjustmentA5V28
    requests: tuple[EffectQueryV18, ...]


@dataclass(frozen=True)
class VerifiedBusinessOutcomeV21:
    query_type: str
    status: str
    route: str | None
    reason_code: str | None
    result: (IdentificationResult | VerifiedCompositionBundleV18 |
             VerifiedFixedPolicyV19 | VerifiedFinitePolicyMixtureV19 |
             VerifiedSignaturePolicyV20 | VerifiedObservationalPolicyV23 |
             VerifiedObservationalEffectsV26 | VerifiedObservationalFactorizedEffectsV27P1 | VerifiedObservationalMixtureEffectsV28P1 | VerifiedExposureAdjustedEffectsV27P2 | VerifiedNodewiseAdjustedEffectsV28 | None)
    attempted_routes: tuple[tuple[str, str], ...] = ()

    def summary(self) -> dict:
        if self.result is None:
            data = None
        elif isinstance(self.result, IdentificationResult):
            data = {
                'status': self.result.status,
                'verification_status': self.result.verification_status,
                'identified_functional': self.result.result.get('identified_functional'),
                'reason_code': self.result.result.get('reason_code'),
                'certificate': self.result.result.get('certificate'),
                'estimation_request': None if self.result.estimation_request is None
                                       else 'LEGACY_CAPABILITY_BOUND',
            }
        else:
            data = self.result.summary()
        return dict(query_type=self.query_type, status=self.status,
                    route=self.route, reason_code=self.reason_code,
                    attempted_routes=[dict(route=r, result=status) for r,status in self.attempted_routes],
                    identification=data,
                    note='Mathematical POINT / verification only; no numeric business effect estimated')


def _kind_to_status(code: str) -> str:
    if (code.startswith('A4_') or code in {'INFORMATION_BLOCKED', 'NEEDS_INPUT', 'ASSUMPTIONS_NOT_ADMITTED',
                                           'NETWORK_PRETREATMENT_STATUS_UNRESOLVED',
                                           'EXPERIMENTAL_RANDOMIZED_STUDY_REQUIRED', 'TYPED_SIGNATURE_REQUIRED',
                                           'D6_FIRST_STAGE_PROFILE_EXCLUSION_NOT_ADMITTED'}):
        return 'NEEDS_INPUT'
    return 'UNSUPPORTED'


def identify_network_business_query(
        query: ArmInquiryV21 | EffectsInquiryV21 | FixedPolicyInquiryV21 | FinitePolicyInquiryV21 | ObservationalPolicyInquiryV23 | ObservationalEffectsInquiryV26 | ObservationalExposureAdjustedEffectsInquiryV27P2 | ObservationalNodewiseAdjustedEffectsInquiryV28
        ) -> VerifiedBusinessOutcomeV21:
    """Explicit typed queries, no free-text causal license or route label guessing.

    R1b takes precedence if complete-assignment support and information exist.
    R2 is considered only with a separate explicit, admitted mean-signature
    sufficiency record; it never follows automatically from an exposure label.
    """
    if isinstance(query, ObservationalNodewiseAdjustedEffectsInquiryV28):
        try:
            result=identify_observational_nodewise_effects_v28(
                query.study,query.source,query.signature,
                assumptions=query.assumptions,license=query.license,requests=query.requests)
        except (R3Unavailable,ValueError,TypeError) as exc:
            reason=getattr(exc,'reason_code',None) or 'R3_NODEWISE_REQUIREMENTS_UNSATISFIED'
            return VerifiedBusinessOutcomeV21('OBSERVATIONAL_NODEWISE_ADJUSTED_EFFECTS',
                _kind_to_status(reason),None,reason,None,(('R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS',reason),))
        return VerifiedBusinessOutcomeV21('OBSERVATIONAL_NODEWISE_ADJUSTED_EFFECTS',
            'POINT','R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS',None,result)

    if isinstance(query, ObservationalExposureAdjustedEffectsInquiryV27P2):
        try:
            result=identify_observational_exposure_adjusted_effects_v27p2(
                query.study,query.source,query.signature,
                assumptions=query.assumptions,license=query.license,requests=query.requests)
        except (R3Unavailable,ValueError,TypeError) as exc:
            reason=getattr(exc,'reason_code',None) or 'R3_ADJUSTMENT_REQUIREMENTS_UNSATISFIED'
            return VerifiedBusinessOutcomeV21('OBSERVATIONAL_ADJUSTED_EFFECTS',
                _kind_to_status(reason),None,reason,None,(("R3_EXPOSURE_ADJUSTED_EFFECTS",reason),))
        return VerifiedBusinessOutcomeV21('OBSERVATIONAL_ADJUSTED_EFFECTS','POINT',
            'R3_EXPOSURE_ADJUSTED_EFFECTS',None,result)

    if isinstance(query, ObservationalEffectsInquiryV26):
        try:
            if isinstance(query.source, ObservationalFactorizedArmPopulationV27P1):
                result = identify_observational_factorized_effects_v27p1(
                    query.study, query.source, query.signature,
                    assumptions=query.assumptions, requests=query.requests)
            elif isinstance(query.source, ObservationalMixtureArmPopulationV28P1):
                result = identify_observational_mixture_effects_v28p1(
                    query.study, query.source, query.signature,
                    assumptions=query.assumptions, requests=query.requests)
            elif isinstance(query.source, ObservationalFinitePopulationV23):
                result = identify_observational_effects_v26(
                    query.study, query.source, query.signature,
                    assumptions=query.assumptions, requests=query.requests)
            else:
                raise R3Unavailable('R3_UNSUPPORTED_A4_OPERATOR')
        except (R3Unavailable, ValueError, TypeError) as exc:
            reason = getattr(exc, 'reason_code', None) or 'R3_EFFECT_REQUIREMENTS_UNSATISFIED'
            return VerifiedBusinessOutcomeV21('OBSERVATIONAL_EFFECTS', _kind_to_status(reason),
                    None, reason, None, (('R3_P_STANDARDIZED_EFFECTS', reason),))
        return VerifiedBusinessOutcomeV21('OBSERVATIONAL_EFFECTS', 'POINT',
                                          'R3_P_STANDARDIZED_EFFECTS', None, result)

    if isinstance(query, ObservationalPolicyInquiryV23):
        try:
            result = identify_observational_policy_v23(
                query.study, query.target, query.source,
                assumptions=query.assumptions, signature=query.signature,
                sufficiency=query.sufficiency)
            # identify_observational_policy_v23 has already replayed the certificate.
        except (R3Unavailable, ValueError, TypeError) as exc:
            reason = getattr(exc, 'reason_code', None) or 'R3_REQUIREMENTS_UNSATISFIED'
            return VerifiedBusinessOutcomeV21('OBSERVATIONAL_POLICY', _kind_to_status(reason),
                        None, reason, None, (('R3_OBSERVATIONAL', reason),))
        return VerifiedBusinessOutcomeV21('OBSERVATIONAL_POLICY','POINT',result.route,None,result)

    if isinstance(query, ArmInquiryV21):
        result = identify(query.task)
        if result.status == 'POINT' and result.verification_status == 'VERIFIED':
            replay_population_identification(result)
            return VerifiedBusinessOutcomeV21('ARM', 'POINT', 'R1A_RANDOMIZED_ARM', None, result)
        reason = result.result.get('reason_code') or 'NO_VERIFIED_ARM_ROUTE'
        return VerifiedBusinessOutcomeV21('ARM',
            'NEEDS_INPUT' if result.diagnostics.get('workflow_status') == 'NEEDS_INPUT'
            or reason == 'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED' else 'UNSUPPORTED',
            None, reason, None, (('R1A_RANDOMIZED_ARM', reason),))

    if isinstance(query, EffectsInquiryV21):
        try:
            result = identify_verified_effect_bundle(query.batch, query.a4_source, query.requests)
            replay_verified_effect_bundle(result)
        except (ValueError, TypeError) as exc:
            reason = getattr(exc, 'reason_code', None) or 'R1A_COMPOSITION_REQUIREMENTS_UNSATISFIED'
            return VerifiedBusinessOutcomeV21('EFFECT_BUNDLE', _kind_to_status(reason), None,
                                              reason, None, (('R1A_COMPOSITION', reason),))
        return VerifiedBusinessOutcomeV21('EFFECT_BUNDLE', 'POINT', 'R1A_COMPOSITION', None, result)

    if isinstance(query, FinitePolicyInquiryV21):
        try:
            result = identify_verified_finite_policy_mixture(
                query.components, policy_probabilities=query.policy_probabilities)
            replay_verified_finite_policy_mixture(result)
        except (ValueError, TypeError) as exc:
            reason = getattr(exc, 'reason_code', None) or 'R1B_FINITE_POLICY_INVALID'
            return VerifiedBusinessOutcomeV21('FINITE_POLICY_MIXTURE', _kind_to_status(reason),
                                              None, reason, None, (('R1B_FINITE_POLICY', reason),))
        return VerifiedBusinessOutcomeV21('FINITE_POLICY_MIXTURE', 'POINT', 'R1B_FINITE_POLICY', None, result)

    if isinstance(query, FixedPolicyInquiryV21):
        attempted = []
        if query.r1b_sources:
            try:
                result = identify_verified_fixed_policy(query.study, query.target,
                            query.r1b_sources, assumptions=query.assumptions)
                replay_verified_fixed_policy(result)
                return VerifiedBusinessOutcomeV21('FIXED_POLICY', 'POINT', 'R1B_FULL_ASSIGNMENT',
                                                  None, result)
            except (R1bPolicyUnavailable, ValueError, TypeError) as exc:
                code = getattr(exc, 'reason_code', None) or 'R1B_REQUIREMENTS_UNSATISFIED'
                attempted.append(('R1B_FULL_ASSIGNMENT', code))
        if (query.r2_signature is not None and query.r2_sufficiency is not None
            and query.r2_sources):
            try:
                result = identify_verified_signature_policy(
                    query.study, query.target, query.r2_signature,
                    query.r2_sources, assumptions=query.assumptions,
                    sufficiency=query.r2_sufficiency)
                # identify_verified_signature_policy() already independently
                # replays its theorem result. Do not perform an expensive third
                # ER300 replay at this wrapper boundary; callers may explicitly
                # call replay_verified_business_outcome later.
                return VerifiedBusinessOutcomeV21('FIXED_POLICY', 'POINT',
                       'R2_MEAN_SIGNATURE', None, result, tuple(attempted))
            except (R2PolicyUnavailable, ValueError, TypeError) as exc:
                code = getattr(exc, 'reason_code', None) or 'R2_REQUIREMENTS_UNSATISFIED'
                attempted.append(('R2_MEAN_SIGNATURE', code))
        if not attempted:
            attempted.append(('R1B_FULL_ASSIGNMENT', 'A4_ASSIGNMENT_INFORMATION_REQUIRED'))
            if query.r2_signature is None or query.r2_sufficiency is None:
                attempted.append(('R2_MEAN_SIGNATURE', 'A5_SIGNATURE_SUFFICIENCY_NOT_ADMITTED'))
        # An unimplemented route is NOT a proof of non-identification.
        code = attempted[-1][1]
        if code == 'A5_SIGNATURE_SUFFICIENCY_NOT_ADMITTED' and len(attempted)>1:
            code = attempted[0][1]
        return VerifiedBusinessOutcomeV21('FIXED_POLICY', _kind_to_status(code),
                                          None, code, None, tuple(attempted))

    raise TypeError('Use an explicitly typed v2.1 Network Business Inquiry')


def replay_verified_business_outcome(value: VerifiedBusinessOutcomeV21) -> bool:
    """Recheck original theorem/verifier, rather than trusting the wrapper label."""
    if not isinstance(value, VerifiedBusinessOutcomeV21) or value.status != 'POINT' or value.result is None:
        raise ValueError('Only a verified POINT business outcome can be replayed')
    # The theorem certificate authenticates its own causal target.  The outer
    # business envelope is *not* part of that certificate, so independently
    # reject type/route mismatches before any downstream handoff.  This is a
    # compatibility-only hardening, not a new identification theorem.
    route_types = {
        'R1A_RANDOMIZED_ARM': 'ARM',
        'R1A_COMPOSITION': 'EFFECT_BUNDLE',
        'R1B_FULL_ASSIGNMENT': 'FIXED_POLICY',
        'R1B_FINITE_POLICY': 'FINITE_POLICY_MIXTURE',
        'R2_MEAN_SIGNATURE': 'FIXED_POLICY',
        'R3_FULL_ASSIGNMENT': 'OBSERVATIONAL_POLICY',
        'R3_MEAN_SIGNATURE': 'OBSERVATIONAL_POLICY',
        'R3_P_STANDARDIZED_EFFECTS': 'OBSERVATIONAL_EFFECTS',
        'R3_EXPOSURE_ADJUSTED_EFFECTS': 'OBSERVATIONAL_ADJUSTED_EFFECTS',
        'R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS': 'OBSERVATIONAL_NODEWISE_ADJUSTED_EFFECTS',
    }
    if route_types.get(value.route) != value.query_type:
        raise ValueError('Business query_type/route mismatch (route/result mismatch)')
    if isinstance(value.result, IdentificationResult):
        replay_population_identification(value.result)
        if value.route != 'R1A_RANDOMIZED_ARM':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedCompositionBundleV18):
        replay_verified_effect_bundle(value.result)
        if value.route != 'R1A_COMPOSITION':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedFixedPolicyV19):
        replay_verified_fixed_policy(value.result)
        if value.route != 'R1B_FULL_ASSIGNMENT':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedSignaturePolicyV20):
        replay_verified_signature_policy(value.result)
        if value.route != 'R2_MEAN_SIGNATURE':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedNodewiseAdjustedEffectsV28):
        replay_observational_nodewise_effects_v28(value.result)
        if value.route != 'R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedExposureAdjustedEffectsV27P2):
        replay_observational_exposure_adjusted_effects_v27p2(value.result)
        if value.route != 'R3_EXPOSURE_ADJUSTED_EFFECTS':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedObservationalMixtureEffectsV28P1):
        replay_observational_mixture_effects_v28p1(value.result)
        if value.route != 'R3_P_STANDARDIZED_EFFECTS' or value.query_type != 'OBSERVATIONAL_EFFECTS':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedObservationalFactorizedEffectsV27P1):
        replay_observational_factorized_effects_v27p1(value.result)
        if value.route != 'R3_P_STANDARDIZED_EFFECTS' or value.query_type != 'OBSERVATIONAL_EFFECTS':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedObservationalEffectsV26):
        replay_observational_effects_v26(value.result)
        if value.route != 'R3_P_STANDARDIZED_EFFECTS' or value.query_type != 'OBSERVATIONAL_EFFECTS':
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedObservationalPolicyV23):
        replay_observational_policy_v23(value.result)
        if value.route != value.result.route:
            raise ValueError('Business route/result mismatch')
    elif isinstance(value.result, VerifiedFinitePolicyMixtureV19):
        replay_verified_finite_policy_mixture(value.result)
        if value.route != 'R1B_FINITE_POLICY':
            raise ValueError('Business route/result mismatch')
    else:
        raise ValueError('Unknown theorem result type')
    return True


__all__ = [
    'ArmInquiryV21','EffectsInquiryV21','FixedPolicyInquiryV21','FinitePolicyInquiryV21',
    'ObservationalPolicyInquiryV23','ObservationalEffectsInquiryV26',
    'ObservationalExposureAdjustedEffectsInquiryV27P2',
    'ObservationalNodewiseAdjustedEffectsInquiryV28','VerifiedBusinessOutcomeV21',
    'identify_network_business_query','replay_verified_business_outcome',
]
