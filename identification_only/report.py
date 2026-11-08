"""Small, immutable-by-convention, JSON-safe presentation contract for Identification.

No new inference rules are encoded here. All POINT evidence is obtained from a
fresh, real, typed Core call plus its original independent theorem replay.

This module intentionally does not turn UNSUPPORTED into NON_IDENTIFIED. It
cannot authenticate reviewer identities or prove substantive real-world A5.
"""
from __future__ import annotations

from enum import Enum
from hashlib import sha256
import json
from typing import Any

from pfn_pipeline.identification_business import (
    VerifiedBusinessOutcomeV21, replay_verified_business_outcome,
)

SCHEMA_VERSION = 'cfm-id-identification-only-report-v1'
CORE_POINT = 'POINT'
SAFE_OTHER = frozenset({'NEEDS_INPUT', 'UNSUPPORTED'})


def _clean(value: Any) -> Any:
    if isinstance(value, Enum):
        return _clean(value.value)
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_clean(v) for v in value]
    if value is None or isinstance(value, (int, float, bool, str)):
        return value
    raise TypeError(f'Core report contains non-JSON value: {type(value).__name__}')


def _digest(value: Any) -> str:
    payload = json.dumps(_clean(value), ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False)
    return sha256(payload.encode('utf-8')).hexdigest()


def _formula(identification: dict) -> str | None:
    function = identification.get('identified_functional')
    if isinstance(function, str):
        return function
    if isinstance(function, dict):
        return function.get('functional') or function.get('formula')
    results = identification.get('results')
    if isinstance(results, list) and results:
        expressions = [x.get('identified_functional') for x in results
                       if isinstance(x, dict) and isinstance(x.get('identified_functional'), str)]
        if expressions:
            return '\n'.join(expressions)
    return None


def _support(identification: dict) -> Any:
    certificate = identification.get('certificate')
    if isinstance(certificate, dict):
        for name in ('joint_arm_support_probability', 'assignment_probability'):
            if name in certificate:
                return certificate[name]
    for name in ('assignment_probability', 'support_by_term', 'joint_arm_support_probability'):
        if name in identification:
            return identification[name]
    results = identification.get('results')
    if isinstance(results, list):
        supported = [x.get('support_by_term') for x in results
                     if isinstance(x, dict) and 'support_by_term' in x]
        return supported or None
    return None


def _next_input(status: str, reason: str | None) -> str:
    if status == 'POINT':
        return '当前为符号总体 POINT；有限样本数值估计不属于本模块。'
    r = (reason or '').upper()
    if 'A4' in r or 'INFORMATION' in r or 'POPULATION' in r:
        return '请提供并独立审核目标所需的 typed 总体信息算子；仅样本统计不够。'
    if 'A5' in r or 'ASSUMPTION' in r or 'EXCHANGEABILITY' in r or 'EXCLUSION' in r:
        return '请审阅并明确接受所需因果假设；不得由模型自动批准。'
    if 'SUPPORT' in r:
        return '检查目标 arm / 完整分配 / 局部签名的精确支持；必要时重新设计未来实验或调整合法目标。'
    return '当前路由未能完成认证；检查定理适用域、A4/A5/A6 或寻求独立数学研究。'


def from_verified_core(outcome: VerifiedBusinessOutcomeV21, *, case_id: str,
                       business_question: str, setting: str,
                       design: str | None = None, exposure: str | None = None,
                       assumptions_description: str,
                       information_description: str,
                       input_provenance: str = 'SYNTHETIC_APPROVED_FIXTURE') -> dict:
    """Fail closed. A POINT report is IMPOSSIBLE without current Core replay.

    Caller controls only presentational prose. No user supplied status, proof,
    certificate or target can bypass the Core-owned outcome and replay.
    """
    if not isinstance(outcome, VerifiedBusinessOutcomeV21):
        raise TypeError('An actual typed Core business outcome is required')
    if input_provenance != 'SYNTHETIC_APPROVED_FIXTURE':
        raise ValueError('This demo-only adapter cannot certify real business semantics; use reviewed v2.9 bridge')
    if not case_id or not business_question or not assumptions_description or not information_description:
        raise ValueError('Explicit case, business, A4 and A5 descriptions are required')
    if outcome.status not in SAFE_OTHER | {CORE_POINT}:
        raise ValueError('Unexpected Core status; do not invent an identification classification')
    summary = _clean(outcome.summary())
    status = outcome.status
    replay = False
    if status == CORE_POINT:
        if not replay_verified_business_outcome(outcome):
            raise ValueError('Core independent replay failed: no POINT report may be emitted')
        if not summary.get('route') or not isinstance(summary.get('identification'), dict):
            raise ValueError('POINT without a Core route and verified identification body')
        replay = True
    identification = summary.get('identification') or {}
    formula = _formula(identification) if replay else None
    target = identification.get('identified_functional') if replay else None
    if replay and target is None:
        target = identification.get('target_semantics') or identification.get('results') or identification.get('target')
    certificate = identification.get('certificate')
    certificate_digest = identification.get('certificate_sha256')
    if replay and not certificate_digest and isinstance(certificate, dict):
        certificate_digest = _digest(certificate)
    return dict(
        schema_version=SCHEMA_VERSION, case_id=case_id,
        business_question=business_question, setting=setting,
        inputs=dict(design=design, exposure=exposure, a4=information_description,
                    a5=assumptions_description, provenance=input_provenance),
        identification=dict(status=status, theorem_route=outcome.route if replay else None,
                            formula=formula, target=target,
                            support=_support(identification) if replay else None,
                            reason_code=outcome.reason_code,
                            attempted_routes=summary['attempted_routes']),
        proof=dict(level='CORE_REPLAY_VERIFIED' if replay else 'NOT_CERTIFIED',
                   replay_verified=replay,
                   certificate_sha256=certificate_digest if replay else None),
        category='FORMAL_POINT' if replay else status,
        next_step=_next_input(status, outcome.reason_code),
        numeric_effect_estimate=None, is_real_business_evidence=False,
        business_semantics_independently_certified=False,
        nonidentification_proven=False,
        warning=('合成科学条件下的符号总体识别；不表示现实假设已得到证明。'
                 if replay else '软件未认证 POINT；不等于已证明不可识别。'),
    )


def import_unverified_candidate(*, business_question: str, candidate: str,
                                origin: str = 'UNREVIEWED_LLM_OR_USER') -> dict:
    """Display-only LLM fallback. Cannot produce a theorem status or proof."""
    if not business_question.strip():
        raise ValueError('Original business question required')
    return dict(schema_version=SCHEMA_VERSION,
        case_id='UNVERIFIED_IMPORT', business_question=business_question,
        setting='UNREVIEWED_BUSINESS_INPUT',
        inputs=dict(origin=origin),
        identification=dict(status='NOT_EVALUATED', theorem_route=None,
                            formula=None, target=None, support=None, reason_code=None,
                            attempted_routes=[]),
        proof=dict(level='NOT_CERTIFIED', replay_verified=False,
                   certificate_sha256=None),
        category='UNVERIFIED_LLM_CANDIDATE', candidate_text=candidate,
        numeric_effect_estimate=None, is_real_business_evidence=False,
        business_semantics_independently_certified=False,
        nonidentification_proven=False,
        warning='LLM/人工候选，仅供进一步审核；不是 POINT/PARTIAL/NON-ID 的数学结论。',
        next_step='先完成独立业务目标审核与 A4/A5 输入，再运行 Core 及 replay。')


def research_partial_card(raw: dict) -> dict:
    """Exposes the existing Star7 research bounds without production promotion."""
    if raw.get('schema_version') != 'RESEARCH_PARTIAL_NOT_FORMAL_BACKEND' or raw.get('formally_certified_partial') is not False:
        raise ValueError('Only the isolated, explicitly UNVERIFIED research artifact may be displayed')
    return dict(schema_version=SCHEMA_VERSION, case_id='STAR7_RESEARCH_ONLY',
        setting='D2_STAR7_RESEARCH', business_question=raw['business_question'],
        category='PARTIAL_RESEARCH_ONLY',
        identification=dict(status='RESEARCH_ONLY', theorem_route=None,
                            formula=f"[{raw['symbolic_lower']}, {raw['symbolic_upper']}]",
                            support=raw['exact_signature_support'],
                            illustrative_interval=raw['illustrative_interval'],
                            sharp_width=raw['sharp_width'], reason_code='ZERO_TARGET_SIGNATURE_SUPPORT'),
        proof=dict(level='RESEARCH_WITNESSES_ONLY', replay_verified=False,
                   certificate_sha256=None),
        inputs=dict(a5=raw['assumptions'], provenance='SYNTHETIC_BOUND_RESEARCH'),
        numeric_effect_estimate=None, is_real_business_evidence=False,
        business_semantics_independently_certified=False,
        nonidentification_proven=False,
        warning='隔离 PARTIAL 研究演示：已核对界限与反例，但没有正式 PARTIAL 生产证书或 verifier。',
        next_step='要成为正式 PARTIAL，仍需独立数学合同、一般验证器和证书。')
