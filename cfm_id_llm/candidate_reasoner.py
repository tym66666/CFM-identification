"""v0.3 LLM fallback: tightly gated, review-bound, always unverified.

The only default fallback entrance is a *trusted production core* returning
UNSUPPORTED. An explicit MOCK_PREVIEW is useful for offline demonstration but
NEVER means that the real library lacks a theorem or that a proof was checked.
"""
from __future__ import annotations
from dataclasses import dataclass

from pydantic import ValidationError

from .audit import fingerprint_business_case
from .candidate_prompts import CANDIDATE_SYSTEM_PROMPT, PROMPT_VERSION_V03, make_candidate_user_prompt
from .candidate_schemas import (
    CandidateDraftV03, CandidateReportV03, CandidateAuditIssueV03,
)
from .core_port import CoreIdentificationPort
from .orchestration_schemas import HumanReviewV02, OrchestrationReportV02, ConfirmedProblemV02, canonical_sha256
from .orchestrator import ConfirmationError, confirm_formulation, route_formulation
from .formulator import ProblemFormulator
from .providers.base import LLMProvider
from .schemas import BusinessCase, FormulationReport, PopulationInformationLevel


class CandidateNotAllowed(ValueError):
    """Fallback gating failed before any LLM call."""


def _check_eligible(problem: ConfirmedProblemV02, routing: OrchestrationReportV02,
                    allow_mock_preview: bool) -> str:
    if (routing.case_id != problem.case_id or routing.input_sha256 != problem.input_sha256
            or routing.draft_sha256 != problem.draft_sha256
            or routing.confirmed_problem_sha256 != problem.fingerprint()):
        raise CandidateNotAllowed("Routing and human-reviewed problem bindings disagree")
    if (routing.core_status != "UNSUPPORTED" or routing.core is None
            or routing.candidate_math_claim is not None or routing.core_expression is not None
            or routing.core_certificate is not None):
        raise CandidateNotAllowed("LLM fallback requires an unproved library UNSUPPORTED response")
    if (routing.status == "CORE_UNSUPPORTED" and routing.fallback == "ELIGIBLE_NOT_IMPLEMENTED"
            and routing.verification_level == "NOT_PERFORMED"
            and routing.core.library_version != "NOT_CONNECTED"
            and not routing.core.adapter_id.lower().startswith("mock")):
        return "CORE_UNSUPPORTED"
    if (allow_mock_preview and routing.status == "MOCK_CORE_RESULT"
            and routing.fallback == "MOCK_ONLY" and routing.verification_level == "MOCK_ONLY"
            and routing.core.library_version == "NOT_CONNECTED"
            and routing.core.adapter_id.lower().startswith("mock")):
        return "MOCK_PREVIEW"
    raise CandidateNotAllowed("Only trusted-core UNSUPPORTED or explicit mock preview may call the reasoner")


def audit_candidate(draft: CandidateDraftV03, problem: ConfirmedProblemV02) -> list[CandidateAuditIssueV03]:
    """Check identity, admitted-A5 vocabulary and A4 bindings, NOT proof validity."""
    issues: list[CandidateAuditIssueV03] = []

    def issue(code: str, detail: str) -> None:
        issues.append(CandidateAuditIssueV03(code=code, detail=detail))

    if draft.target_kind != problem.draft.target.kind:
        issue("TARGET_KIND_CHANGED", "LLM changed the causal query type; the original target is immutable")
    if draft.target_description != problem.draft.target.description.value:
        issue("TARGET_DESCRIPTION_CHANGED", "LLM rewrote the human-reviewed causal target")

    allowed = set(problem.human_review.admitted_assumptions)
    if unadmitted := sorted(set(draft.admitted_assumptions_used) - allowed):
        issue("UNADMITTED_A5_USED", "Unadmitted assumptions invoked: " + ", ".join(unadmitted))

    original = problem.draft.information_design
    if draft.a4_used.source == "REVIEWED_OPERATOR":
        if (original.population_information_level in (
                PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
                PopulationInformationLevel.UNRESOLVED,
            ) or original.population_observable_operator.value is None):
            issue("A4_NOT_AVAILABLE", "A finite sample or unresolved information cannot be upgraded to a population operator")
        if (draft.a4_used.level != original.population_information_level
                or draft.a4_used.operator != original.population_observable_operator.value):
            issue("A4_OPERATOR_CHANGED", "LLM changed the typed population operator rather than quoting the reviewed one")
    if draft.a4_used.source == "UNRESOLVED" and draft.claimed_identification != "UNDETERMINED":
        if not any(r.kind == "A4_INFORMATION" for r in draft.additional_requirements):
            issue("A4_REQUIRED_FOR_MATH_CLAIM", "A mathematical claim with missing A4 needs an explicit conditional A4 requirement")
        if draft.scope != "IF_ADDITIONAL_REQUIREMENTS":
            issue("A4_UNRESOLVED_SCOPE", "Missing A4 cannot yield an unconditional mathematical claim")
    if draft.a4_used.source == "ADDITIONAL_OPERATOR":
        if (draft.a4_used.level == original.population_information_level
                and draft.a4_used.operator == original.population_observable_operator.value):
            issue("A4_ADDITIONAL_EQUALS_REVIEWED", "An already reviewed operator should not be fabricated as a new information source")
    return issues


class CandidateReasonerV03:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def run(self, *, case: BusinessCase, formulation: FormulationReport,
            human_review: HumanReviewV02, routing: OrchestrationReportV02,
            allow_mock_preview: bool = False) -> CandidateReportV03:
        """Runs LLM only after v0.2 review and safe routing; no direct candidate endpoint."""
        # Recalculate everything relevant, not just a possibly forged readiness flag.
        if formulation.input_sha256 != fingerprint_business_case(case):
            raise CandidateNotAllowed("Original business inputs changed")
        try:
            confirmed = confirm_formulation(case, formulation, human_review)
        except ConfirmationError as exc:
            raise CandidateNotAllowed("Human review or draft grounding is invalid") from exc
        mode = _check_eligible(confirmed, routing, allow_mock_preview)
        base = dict(
            case_id=case.case_id,
            input_sha256=confirmed.input_sha256,
            draft_sha256=confirmed.draft_sha256,
            confirmed_problem_sha256=confirmed.fingerprint(),
            routing_sha256=canonical_sha256(routing),
            provider=self.provider.name,
            prompt_version=PROMPT_VERSION_V03,
            execution_mode=mode,
        )
        try:
            response = self.provider.generate_json(
                system_prompt=CANDIDATE_SYSTEM_PROMPT,
                user_prompt=make_candidate_user_prompt(confirmed, routing),
            )
        except Exception as exc:
            # Do not include provider payload/response, keys or source text in an error.
            return CandidateReportV03(**base, status="PROVIDER_FAILED",
                explanation="大模型调用失败，未获得候选识别结果；不改变严格库状态。",
                issues=[CandidateAuditIssueV03(code="PROVIDER_FAILURE", detail=f"Provider error: {type(exc).__name__}")])
        try:
            proposal = CandidateDraftV03.model_validate(response)
        except (ValueError, TypeError, ValidationError):
            return CandidateReportV03(**base, status="REJECTED_UNSAFE_OUTPUT",
                explanation="大模型返回的数据不符合候选推理合同；已拒绝将其作为有效答案。",
                issues=[CandidateAuditIssueV03(code="INVALID_CANDIDATE_SCHEMA", detail="Malformed, oversized or forbidden fields in LLM response")])
        issues = audit_candidate(proposal, confirmed)
        if issues:
            return CandidateReportV03(**base, status="REJECTED_UNSAFE_OUTPUT", issues=issues,
                explanation="候选结果更改了已确认目标、使用未接受假设或改变了 A4 信息；不得对外作为识别结论。")
        if proposal.claimed_identification == "UNDETERMINED":
            return CandidateReportV03(**base, status="UNDETERMINED_UNVERIFIED", candidate=proposal,
                explanation="LLM 未能给出自洽候选结论，可参考其列出的待核查条件；无数学认证。")
        return CandidateReportV03(**base, status="UNVERIFIED_CANDIDATE", candidate=proposal,
            explanation="LLM 提供了一个候选数学推理。公式、条件与反例尚未经过独立数学验证。")


@dataclass(frozen=True)
class GatewayRunV03:
    formulation: FormulationReport
    routing: OrchestrationReportV02
    candidate: CandidateReportV03 | None


class GatewayV03:
    """Optional facade. Candidate stage is reached only when the routed state allows it."""
    def __init__(self, formulation_provider: LLMProvider, *,
                 core: CoreIdentificationPort | None = None,
                 candidate_provider: LLMProvider | None = None):
        self.formulator = ProblemFormulator(formulation_provider)
        self.core = core
        self.candidate_reasoner = CandidateReasonerV03(candidate_provider) if candidate_provider is not None else None

    def run(self, case: BusinessCase, *, human_review: HumanReviewV02 | None = None,
            allow_mock_preview: bool = False) -> GatewayRunV03:
        formulation = self.formulator.formulate(case)
        routing = route_formulation(case, formulation, human_review=human_review, core=self.core)
        candidate = None
        if human_review is not None and self.candidate_reasoner is not None:
            # CandidateNotAllowed means "do not call provider", not "silently change verdict".
            if (routing.status == "CORE_UNSUPPORTED" and routing.fallback == "ELIGIBLE_NOT_IMPLEMENTED") or (
                allow_mock_preview and routing.status == "MOCK_CORE_RESULT"
                and routing.core_status == "UNSUPPORTED" and routing.fallback == "MOCK_ONLY"
            ):
                candidate = self.candidate_reasoner.run(
                    case=case, formulation=formulation, human_review=human_review,
                    routing=routing, allow_mock_preview=allow_mock_preview,
                )
        return GatewayRunV03(formulation=formulation, routing=routing, candidate=candidate)
