"""Safe business -> grounded draft -> human clarification, independent of CFM-ID core.

No result from this module is a formal TaskSpec, A4 license, approved A5
assumption, IdentificationResult or Estimation permission. User answers are
untrusted source claims until a researcher confirms their scientific meaning.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import Field, model_validator

from .audit import audit_draft, fingerprint_business_case, verify_quote_provenance
from .orchestration_schemas import canonical_sha256
from .schemas import (
    BusinessCase, ClarificationQuestion, FormulationReport,
    SourceDocument, SourceKind, StrictModel,
)


class StaleNormalizationError(ValueError):
    """Report or reply references older source/draft state."""


class UserQuestionV06(StrictModel):
    question_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    field_path: str
    question: str
    question_kind: Literal["BUSINESS_FACT", "RESEARCH_REVIEW"]
    reason: str
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"


class NormalizationReviewV06(StrictModel):
    version: Literal["0.6.0"] = "0.6.0"
    case_id: str
    input_sha256: str
    draft_sha256: str
    response_language: Literal["zh", "en"] = "zh"
    provider: str
    formulation: FormulationReport
    next_action: Literal["ASK_BUSINESS", "RESEARCHER_REVIEW"]
    business_questions: list[UserQuestionV06] = Field(default_factory=list, max_length=2)
    research_review_notes: list[str] = Field(default_factory=list, max_length=12)
    core_formal_spec_generated: Literal[False] = False
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def consistent(self):
        if (self.case_id != self.formulation.case_id or
                self.input_sha256 != self.formulation.input_sha256 or
                self.draft_sha256 != canonical_sha256(self.formulation.draft) or
                self.provider != self.formulation.provider):
            raise ValueError("Review hashes and formulation must match")
        if self.next_action == "ASK_BUSINESS" and not self.business_questions:
            raise ValueError("ASK_BUSINESS requires at least one question")
        if self.next_action == "RESEARCHER_REVIEW" and self.business_questions:
            raise ValueError("RESEARCHER_REVIEW must not require a business answer")
        return self


class ClarificationAnswerV06(StrictModel):
    question_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    answer: str = Field(min_length=2, max_length=3000)


# Not every missing mathematical requirement should be pushed onto a sales manager.
# These are business-language translations of precise audit fields.
_FRIENDLY_ZH = {
    "target.kind": "您想比较个人使用后的变化、对其他人的影响，还是某个推广方案的整体收益？",
    "units_variables.analysis_unit": "我们要研究的是员工、客户、门店，还是其他对象？",
    "units_variables.treatment": "您做了什么改变？例如开放 AI、发券或改造设备。",
    "units_variables.outcome": "您最关心哪项结果，例如销售额、订单量或等待时间？",
    "information_design.assignment_family": "当初是怎样选出使用这项措施的人或门店的？是各自随机抽取、固定名额随机选，还是由业务人员决定？",
    "structure.exposure_mapping": "您想怎样衡量周围人的参与情况，例如参与人数、比例还是合作关系强弱？如果还没有想好，也可以说明。",
    "information_design.population_information_level": "目前保存了哪些记录？例如谁使用了措施、合作关系和最终结果。",
}
_FRIENDLY_EN = {
    "target.kind": "Are you comparing participants, connected people, or the outcome of a rollout plan?",
    "units_variables.analysis_unit": "Are we studying employees, customers, stores or something else?",
    "units_variables.treatment": "What change did you introduce, such as AI access, coupons or equipment upgrades?",
    "units_variables.outcome": "Which business outcome matters most, such as revenue or waiting time?",
    "information_design.assignment_family": "How did you choose recipients: independent random draws, a fixed random quota, or business judgement?",
    "structure.exposure_mapping": "How should we describe peers' participation: counts, shares or relationship strengths?",
    "information_design.population_information_level": "What records were retained, such as treatment assignments, relationships and outcomes?",
}
_ORDER = (
    "target.kind", "information_design.assignment_family", "units_variables.outcome",
    "units_variables.treatment", "units_variables.analysis_unit",
    "structure.exposure_mapping", "information_design.population_information_level",
)


def _qid(input_sha: str, draft_sha: str, field: str, text: str) -> str:
    return sha256(f"{input_sha}:{draft_sha}:{field}:{text}".encode("utf-8")).hexdigest()


def _fresh_audit(case: BusinessCase, formulation: FormulationReport) -> FormulationReport:
    if (formulation.case_id != case.case_id or
            formulation.input_sha256 != fingerprint_business_case(case)):
        raise StaleNormalizationError("Formulation is not bound to these business sources")
    # Re-check original evidence and blockers instead of trusting a caller-edited status.
    verify_quote_provenance(case, formulation.draft)
    return audit_draft(case, formulation.draft, provider=formulation.provider,
                       prompt_version=formulation.prompt_version)


def build_normalization_review(case: BusinessCase,
                               formulation: FormulationReport) -> NormalizationReviewV06:
    checked = _fresh_audit(case, formulation)
    draft_sha = canonical_sha256(checked.draft)
    language = case.response_language
    translations = _FRIENDLY_ZH if language == "zh" else _FRIENDLY_EN
    outstanding = {q.field_path: q for q in checked.suggested_questions
                   if q.priority == "HIGH"}
    selected: list[UserQuestionV06] = []
    # Ask up to two practical questions. Complex A4 licenses remain for experts.
    for path in _ORDER:
        if path not in outstanding or path not in translations:
            continue
        original: ClarificationQuestion = outstanding[path]
        user_text = translations[path]
        selected.append(UserQuestionV06(
            question_id=_qid(checked.input_sha256, draft_sha, path, user_text),
            field_path=path, question=user_text,
            question_kind="BUSINESS_FACT", reason=original.reason,
            priority=original.priority,
        ))
        if len(selected) >= 2:
            break

    en = language == "en"
    notes = []
    if checked.draft.information_design.population_information_level.value in (
        "UNRESOLVED", "FINITE_SAMPLE_DESCRIPTION"
    ):
        notes.append("Researchers still must specify the allowed A4 population observable law; finite records alone are not an A4 license."
                     if en else "A4 仍需研究者确定可用的总体观测信息及其粒度；业务人员提供原始记录并不等于满足 A4。")
    if checked.draft.assumptions:
        notes.append("A5 assumptions remain reported or proposed until separately reviewed."
                     if en else "A5 中的假设都是来源陈述或 LLM 候选；必须另行确认，不能因为文本提及就认证成立。")
    else:
        notes.append("No causal assumption has been scientifically confirmed by this gateway; researchers must review A5."
                     if en else "当前尚无经过科学确认的因果假设；研究者必须在识别前审查 A5。")
    if checked.draft.target.kind.value in ("FIXED_POLICY_VALUE", "POLICY_OPTIMIZATION", "STOCHASTIC_POLICY_VALUE"):
        notes.append("Policy value cannot be silently replaced by four-arm means or design-standardized effects."
                     if en else "政策目标不能被无条件改写成四臂均值或设计标准化效应。")
    if checked.draft.structure.unit_network.basis != "UNRESOLVED":
        notes.append("Mentioning relations does not establish a fixed pretreatment graph or exposure sufficiency."
                     if en else "提及单位之间存在关系，不表示已获得处理前固定的网络，更不表示暴露映射具有充分性。")
    if checked.issues:
        notes.append(("Unresolved technical audit issues: " if en else "以下技术审核阻塞仍然存在：")
                     + ", ".join(sorted({x.code for x in checked.issues})))
    if not selected and checked.review_status == "NEEDS_CLARIFICATION":
        notes.append("Some technical ambiguities remain and require research review."
                     if en else "仍有非业务可直接回答的数学歧义，需由研究者审阅完整草稿。")

    return NormalizationReviewV06(
        case_id=case.case_id, input_sha256=checked.input_sha256,
        draft_sha256=draft_sha, response_language=language, provider=checked.provider,
        formulation=checked,
        next_action="ASK_BUSINESS" if selected else "RESEARCHER_REVIEW",
        business_questions=selected, research_review_notes=notes,
    )


def append_clarification(case: BusinessCase, review: NormalizationReviewV06,
                         answer: ClarificationAnswerV06) -> BusinessCase:
    """Add an answer as a *new* unverified business source, never silently patch math.

    The caller must run ProblemFormulator again on the returned BusinessCase.
    Previously issued formulation reviews and human approvals become stale.
    """
    refreshed = build_normalization_review(case, review.formulation)
    if refreshed != review:
        raise StaleNormalizationError("Review contents do not match fresh deterministic audit")
    if (answer.input_sha256 != review.input_sha256 or
            answer.draft_sha256 != review.draft_sha256):
        raise StaleNormalizationError("Reply is bound to an older source or draft")
    question = next((q for q in refreshed.business_questions
                     if q.question_id == answer.question_id and q.question_kind == "BUSINESS_FACT"), None)
    if question is None:
        raise ValueError("Reply does not match an active business question")
    source_suffix = sha256((answer.question_id + ':' + answer.answer).encode("utf-8")).hexdigest()[:20]
    source_id = 'business_reply_' + source_suffix
    new_source = SourceDocument(
        source_id=source_id, kind=SourceKind.BUSINESS_NARRATIVE,
        label=f"用户补充说明（未经科学验证）：{question.field_path}",
        text=f"针对问题『{question.question}』，用户补充：{answer.answer}",
    )
    if source_id in case.source_map():
        raise ValueError("Same clarification was already incorporated")
    # Keep all previous content unchanged; do not upgrade reply to STUDY_PROTOCOL.
    return BusinessCase(
        case_id=case.case_id, business_question=case.business_question,
        response_language=case.response_language,
        sources=[*case.sources, new_source],
    )


def render_review_text(review: NormalizationReviewV06) -> str:
    d = review.formulation.draft
    en = review.response_language == "en"
    if en:
        lines = [
            "CFM-ID: business question formalization (draft, no identification run)",
            f"Goal: {d.target.description.value or 'Not resolved'}",
            f"Unit: {d.units_variables.analysis_unit.value or 'To confirm'}",
            f"Intervention: {d.units_variables.treatment.value or 'To confirm'}",
            f"Outcome: {d.units_variables.outcome.value or 'To confirm'}",
            f"Assignment: {d.information_design.assignment_family.value}",
            f"Next: {'Clarify business facts' if review.next_action == 'ASK_BUSINESS' else 'Researcher review'}",
        ]
        if review.business_questions:
            lines.append('Please answer first:')
            lines.extend(f"  {i}. {q.question}" for i, q in enumerate(review.business_questions, 1))
        if review.research_review_notes:
            lines.append('For researcher review:')
            lines.extend(f"  - {x}" for x in review.research_review_notes[:4])
        lines.append('Identification: NOT PERFORMED; Estimation: NOT ALLOWED.')
    else:
        lines = [
            "CFM-ID：业务问题规范化（草稿，尚未进行因果识别）",
            f"研究目标：{d.target.description.value or '尚未确定'}",
            f"分析对象：{d.units_variables.analysis_unit.value or '待确认'}",
            f"措施：{d.units_variables.treatment.value or '待确认'}",
            f"结果指标：{d.units_variables.outcome.value or '待确认'}",
            f"分配方式：{d.information_design.assignment_family.value}",
            f"下一步：{'补充业务信息' if review.next_action == 'ASK_BUSINESS' else '研究者审查'}",
        ]
        if review.business_questions:
            lines.append('建议先回答：')
            lines.extend(f"  {i}. {q.question}" for i, q in enumerate(review.business_questions, 1))
        if review.research_review_notes:
            lines.append('后台仍需核查：')
            lines.extend(f"  - {x}" for x in review.research_review_notes[:4])
        lines.append('数学认证：未执行；估计：未放行。')
    return '\n'.join(lines)
