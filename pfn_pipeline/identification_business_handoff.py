"""No-numeric, read-only v2.7 business Identification -> Estimation/Policy audit.

Important: no registered adapter currently consumes the v2.1 typed business
routes automatically.  Successful *theorem* replay does not create an estimator.
This file deliberately does not modify EstimationRequest or the PFN pipeline.
"""
from __future__ import annotations

from .contracts import IdentificationResult
from .identification_assumption_inventory import requirements_for_route_v27
from .identification_observational_exposure_adjustment import (
    requirements_for_exposure_adjustment_v27p2,
)
from .identification_observational_nodewise_adjustment import (
    requirements_for_nodewise_adjustment_v28,
)
from .identification_business import VerifiedBusinessOutcomeV21, replay_verified_business_outcome
from ._internal.identification.schemas import TwoStageQuotaMixtureDesignV27

_POLICY_TYPES = {'FIXED_POLICY','FINITE_POLICY_MIXTURE','OBSERVATIONAL_POLICY'}


def _get_design_kind(result) -> str | None:
    # Inspect only replay-anchored source data, never assign a design by label.
    if isinstance(result, IdentificationResult):
        f = result.result.get('identified_functional') or {}
        if f.get('assignment_kind') == 'two_stage_quota_mixture':
            return 'two_stage_quota_mixture_binary_v2_7'
        return None
    study = getattr(result, 'study', None)
    if study is not None and hasattr(study, 'design'):
        design = study.design()
        if isinstance(design, TwoStageQuotaMixtureDesignV27):
            return design.kind
    if hasattr(result, 'components'):
        kinds = [_get_design_kind(component) for component in result.components]
        if kinds and all(k == 'two_stage_quota_mixture_binary_v2_7' for k in kinds):
            return kinds[0]
    if hasattr(result, 'source_batch'):
        # A verified bundle anchors the actual experiment in its source Batch.
        # Never infer it from a bundle title, array shape, or route name.
        batch = result.source_batch
        raw = batch.template.identification_spec.get('randomized_network_arm_theorem_contract') or {}
        design = raw.get('design') or {}
        if design.get('kind') == 'two_stage_quota_mixture_binary_v2_7':
            return design['kind']
    return None


def _fingerprints(result) -> list[str]:
    if isinstance(result, IdentificationResult):
        fp = (result.result.get('identified_functional') or {}).get('target_fingerprint')
        return [fp] if isinstance(fp,str) and len(fp)==64 else []
    if hasattr(result, 'results'):
        parts = result.results
    elif hasattr(result, 'proofs'):
        parts = result.proofs
    else:
        parts = (result,)
    return [f for r in parts if isinstance((f:=getattr(r,'target_fingerprint',None)),str) and len(f)==64]


def inspect_verified_business_handoff_v27(outcome: VerifiedBusinessOutcomeV21) -> dict:
    """Machine-readable release capability, not an EstimationRequest.

    Raises on tampered or unreplayable POINT wrappers (fail closed).
    Non-POINT classification is diagnostic, NOT a proof of mathematical non-ID.
    """
    if not isinstance(outcome, VerifiedBusinessOutcomeV21):
        raise TypeError('Typed VerifiedBusinessOutcomeV21 required')
    common = dict(contract='CFM-ID-BUSINESS-HANDOFF-v2.7-P0',
                  query_type=outcome.query_type, route=outcome.route,
                  source_status=outcome.status,
                  scientific_assumptions_verified_in_real_world=False,
                  finite_sample_estimate=None, policy_value_estimate=None)
    if outcome.status != 'POINT':
        return {**common, 'target_fingerprints': [], 'route_requirements': None,
                'theorem_replayed': False,
                'identification': {'status':outcome.status,'reason_code':outcome.reason_code},
                'estimation': {'status':'IDENTIFICATION_BLOCKED','adapter_id':None,'request':None},
                'policy': {'status':'IDENTIFICATION_BLOCKED'},
                'note':'Route/software refusal, NOT a mathematical non-identification certificate.'}
    if not replay_verified_business_outcome(outcome):
        raise ValueError('Independent theorem replay did not approve the business result')
    fingerprints = _fingerprints(outcome.result)
    if not fingerprints:
        raise ValueError('Replayed POINT result lacks a typed mathematical target fingerprint')
    requirements = (requirements_for_nodewise_adjustment_v28()
        if outcome.route == 'R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'
        else requirements_for_exposure_adjustment_v27p2()
        if outcome.route == 'R3_EXPOSURE_ADJUSTED_EFFECTS'
        else requirements_for_route_v27(outcome.route, design_kind=_get_design_kind(outcome.result)))
    return {**common,
        'target_fingerprints': fingerprints,
        'route_requirements': requirements,
        'theorem_replayed': True,
        'identification': {'status':'POINT','reason_code':None,
                           'interpretation':'population identification, not numerical estimation'},
        'estimation': {'status':'NO_ADAPTER', 'adapter_id':None, 'request':None,
                       'reason_code':'NO_CERTIFIED_ESTIMATOR_FOR_TYPED_BUSINESS_RESULT',
                       'note':'Legacy ER300 PFN adapter is not automatically compatible with this query.'},
        'policy': {'status':('IDENTIFIED_VALUE_FORMULA_ONLY' if outcome.query_type in _POLICY_TYPES
                             else 'NOT_A_FIXED_POLICY_VALUE'), 'numeric_policy_value':None},
        'note':'Theorem/provenance replay is not empirical evidence for causal assumptions.'}


__all__ = ['inspect_verified_business_handoff_v27']
