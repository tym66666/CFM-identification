"""Verified-first *routing* v0.2.

No live Identification Library is bundled. MockCorePort can demonstrate every path
but never upgrades a mocked theorem outcome to VERIFIED. Missing information and
verification failures MUST NOT silently turn into LLM fallbacks.
"""
from __future__ import annotations
from dataclasses import dataclass

from .audit import audit_draft, fingerprint_business_case
from .core_port import CoreIdentificationPort
from .orchestration_schemas import (
    ConfirmedProblemV02, CoreCapabilitiesV02, CoreDecisionV02, CoreReplayV02,
    HumanReviewV02, MATH_STATUSES, OrchestrationReportV02, canonical_sha256,
)
from .schemas import BusinessCase, FormulationReport
from .formulator import ProblemFormulator
from .providers.base import LLMProvider


class ConfirmationError(ValueError):
    """Mismatch or insufficiently resolved business specification."""


def confirm_formulation(case: BusinessCase, report: FormulationReport,
                        review: HumanReviewV02) -> ConfirmedProblemV02:
    """Re-check source quote grounding AND readiness, not merely a mutable status flag."""
    if report.case_id != case.case_id or report.input_sha256 != fingerprint_business_case(case):
        raise ConfirmationError("FormulationReport is not bound to this BusinessCase")
    # Re-audit even if an outside caller edited the report's status or removed its issues.
    verified_report = audit_draft(case, report.draft, provider=report.provider)
    if verified_report.review_status != "DRAFT_READY_FOR_HUMAN_REVIEW":
        raise ConfirmationError("The draft has unresolved blocking issues or HIGH-priority questions")
    draft_sha = canonical_sha256(report.draft)
    if review.draft_sha256 != draft_sha or review.input_sha256 != report.input_sha256:
        raise ConfirmationError("Human review is stale or bound to different source/draft contents")
    try:
        return ConfirmedProblemV02(
            case_id=case.case_id,
            input_sha256=report.input_sha256,
            draft_sha256=draft_sha,
            draft=report.draft,
            human_review=review,
        )
    except ValueError as exc:
        raise ConfirmationError(str(exc)) from exc


def _report(formulation: FormulationReport, *, status: str, explanation: str,
            next_steps: list[str], confirmed: ConfirmedProblemV02 | None = None,
            core_info: CoreCapabilitiesV02 | None = None, core_status: str | None = None,
            core_route: str | None = None, math_claim: str | None = None,
            expression: str | None = None, decision_sha: str | None = None,
            verifier_id: str | None = None, certificate: dict | None = None,
            verification: str = "NOT_PERFORMED",
            fallback: str = "NOT_EVALUATED") -> OrchestrationReportV02:
    return OrchestrationReportV02(
        case_id=formulation.case_id,
        input_sha256=formulation.input_sha256,
        draft_sha256=canonical_sha256(formulation.draft),
        confirmed_problem_sha256=confirmed.fingerprint() if confirmed else None,
        status=status,
        core=core_info,
        core_status=core_status,
        core_route=core_route,
        candidate_math_claim=math_claim,
        core_expression=expression,
        core_decision_sha256=decision_sha,
        core_verifier_id=verifier_id,
        core_certificate=certificate,
        verification_level=verification,
        fallback=fallback,
        explanation=explanation,
        next_steps=next_steps,
    )


def route_formulation(case: BusinessCase, formulation: FormulationReport, *,
                      human_review: HumanReviewV02 | None = None,
                      core: CoreIdentificationPort | None = None) -> OrchestrationReportV02:
    """No LLM answer or fixture can self-certify. All routing decisions are deterministic."""
    if formulation.case_id != case.case_id or formulation.input_sha256 != fingerprint_business_case(case):
        raise ConfirmationError("FormulationReport source/case binding mismatch")
    # Never trust a report's self-reported readiness field; independently re-audit it.
    fresh_review = audit_draft(case, formulation.draft, provider=formulation.provider)
    if fresh_review.review_status != "DRAFT_READY_FOR_HUMAN_REVIEW":
        return _report(formulation,
            status="NEEDS_CLARIFICATION", explanation="业务问题尚未澄清完整；不能进入正式识别，也不能让 LLM 猜测缺失条件。",
            next_steps=[q.question for q in fresh_review.suggested_questions[:5]],
            fallback="BLOCKED_NEEDS_INPUT")
    if human_review is None:
        return _report(formulation,
            status="AWAITING_HUMAN_REVIEW", explanation="草稿通过基本格式和证据检查，但还没有被研究者确认。",
            next_steps=["由研究者核对目标、总体信息与假设，并针对这一版草稿提交明确审核记录。"],
            fallback="NOT_EVALUATED")

    confirmed = confirm_formulation(case, formulation, human_review)
    if core is None:
        return _report(formulation, confirmed=confirmed,
            status="NO_CORE_CONNECTED", explanation="已完成显式人工审核，但尚未连接任何 Identification Library。",
            next_steps=["连接最新正式识别库适配器后再判断定理覆盖；当前不能推断该问题不可识别。"],
            fallback="BLOCKED_NO_CORE")

    info: CoreCapabilitiesV02 | None = None
    try:
        if core.mode not in ("MOCK", "PRODUCTION"):
            raise ValueError("Unsupported core trust mode")
        info = CoreCapabilitiesV02.model_validate(core.describe_capabilities())
        result = CoreDecisionV02.model_validate(core.identify(confirmed))
    except Exception as exc:
        return _report(formulation, confirmed=confirmed, core_info=info,
            status="CORE_ERROR", explanation=f"识别库适配器调用或响应校验失败：{type(exc).__name__}。不触发 LLM 推导替代。",
            next_steps=["检查适配器和正式库之间的数据合同；不要把软件故障解释为不可识别。"],
            fallback="BLOCKED_SAFETY_FAILURE")

    if result.problem_sha256 != confirmed.fingerprint():
        return _report(formulation, confirmed=confirmed, core_info=info, core_status=result.status,
            status="CORE_BINDING_FAILED", explanation="识别结果绑定的数学问题指纹不匹配，拒绝此结果。",
            next_steps=["检查是否复用了其他问题或已过期草稿的识别证书。"],
            verification="FAILED", fallback="BLOCKED_SAFETY_FAILURE")

    if result.status in MATH_STATUSES:
        if result.route_id not in info.available_routes:
            return _report(formulation, confirmed=confirmed, core_info=info,
                core_status=result.status, status="CORE_BINDING_FAILED",
                explanation="正式识别结论声明的 route 不在该适配器的能力清单中。",
                next_steps=["核对正式 theorem route 的身份和适配器能力描述。"],
                verification="FAILED", fallback="BLOCKED_SAFETY_FAILURE")
        try:
            receipt = CoreReplayV02.model_validate(core.replay_verify(confirmed, result))
            replay_ok = (receipt.accepted and receipt.problem_sha256 == confirmed.fingerprint()
                         and receipt.decision_sha256 == result.fingerprint()
                         and (core.mode == "MOCK" or not receipt.verifier_id.lower().startswith("mock")))
        except Exception:
            replay_ok = False
        if not replay_ok:
            return _report(formulation, confirmed=confirmed, core_info=info,
                core_status=result.status, core_route=result.route_id,
                status="CORE_VERIFICATION_FAILED", explanation="独立重放未通过或返回的证书绑定不一致，数学结论不予认证。",
                next_steps=["调查证书、定理条件及独立 verifier，不要用 LLM 覆盖失败结果。"],
                verification="FAILED", fallback="BLOCKED_SAFETY_FAILURE")
        if core.mode == "MOCK":
            return _report(formulation, confirmed=confirmed, core_info=info,
                core_status=result.status, core_route=result.route_id,
                math_claim=result.status, expression=result.identified_expression,
                decision_sha=result.fingerprint(), verifier_id=receipt.verifier_id,
                certificate=result.certificate,
                status="MOCK_CORE_RESULT", verification="MOCK_ONLY", fallback="MOCK_ONLY",
                explanation="模拟识别库给出了结果，并通过模拟重放；没有执行任何正式数学识别或认证。",
                next_steps=["以后连接真实定理和独立 verifier，才能把此类结果标为正式 VERIFIED。"])
        return _report(formulation, confirmed=confirmed, core_info=info,
            core_status=result.status, core_route=result.route_id,
            math_claim=result.status, expression=result.identified_expression,
            decision_sha=result.fingerprint(), verifier_id=receipt.verifier_id,
            certificate=result.certificate,
            status="CORE_VERIFIED", verification="CORE_REPLAY_VERIFIED", fallback="NOT_NEEDED",
            explanation="正式识别库返回数学结论，并且对应的独立重放与目标绑定均验证通过。",
            next_steps=["下一阶段仍需独立匹配 Estimation 模型能力；本版本不放行估计。"])

    # No identified mathematical conclusion is available. Do not invent one.
    if core.mode == "MOCK":
        more = ("模拟结果为不支持；真实库未接入，不能据此判断哪些数学路线真的缺失。"
                if result.status == "UNSUPPORTED" else "模拟结果仅用于测试分流规则。")
        return _report(formulation, confirmed=confirmed, core_info=info,
            core_status=result.status, status="MOCK_CORE_RESULT", verification="MOCK_ONLY",
            fallback="BLOCKED_NEEDS_INPUT" if result.status == "NEEDS_INPUT" else "MOCK_ONLY",
            explanation=more,
            next_steps=result.missing_requirements or ["完成真实 Library 适配后再复核。"])

    status_map = {
        "NEEDS_INPUT": ("CORE_NEEDS_INPUT", "BLOCKED_NEEDS_INPUT", "识别库需要进一步的正式信息或假设确认。"),
        "UNSUPPORTED": ("CORE_UNSUPPORTED", "ELIGIBLE_NOT_IMPLEMENTED", "当前严格识别库不覆盖这个已确认的问题；不表示数学上不可识别。"),
        "NO_ADAPTER": ("CORE_NO_ADAPTER", "BLOCKED_SAFETY_FAILURE", "缺少正式规格转换适配器，不能由此认定缺少数学定理。"),
        "INCOMPATIBLE": ("CORE_INCOMPATIBLE", "BLOCKED_SAFETY_FAILURE", "现有输入与模型/协议要求不相容，须先澄清或修正。"),
        "ERROR": ("CORE_ERROR", "BLOCKED_SAFETY_FAILURE", "识别库报告执行错误，不允许假装成功。"),
    }
    flow_status, fallback, explanation = status_map[result.status]
    next_steps = result.missing_requirements or [
        "待 v0.3 的 LLM Candidate Reasoner 接入；现阶段不生成候选因果结论。" if result.status == "UNSUPPORTED"
        else "检查模型规格或补充缺失信息后再尝试。"
    ]
    return _report(formulation, confirmed=confirmed, core_info=info,
        core_status=result.status, status=flow_status, fallback=fallback,
        explanation=explanation, next_steps=next_steps)


@dataclass(frozen=True)
class GatewayRunV02:
    formulation: FormulationReport
    routing: OrchestrationReportV02


class GatewayV02:
    """Optional end-to-end facade; independent of current/past CFM-ID core releases."""
    def __init__(self, provider: LLMProvider, core: CoreIdentificationPort | None = None):
        self.formulator = ProblemFormulator(provider)
        self.core = core

    def run(self, case: BusinessCase, *, human_review: HumanReviewV02 | None = None) -> GatewayRunV02:
        draft = self.formulator.formulate(case)
        return GatewayRunV02(formulation=draft,
                             routing=route_formulation(case, draft, human_review=human_review, core=self.core))
