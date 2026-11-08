"""Deterministic review of an LLM proposal; *never* an ID theorem verifier."""
from __future__ import annotations
import hashlib
import json
import re
from pydantic import BaseModel
from .schemas import (
    Ambiguity, AssignmentFamily, AuditIssue, BusinessCase, ClarificationQuestion,
    DraftProblemSpec, EvidenceQuote, FormulationReport, PopulationInformationLevel,
    SemanticClaim, TargetKind,
)
from .prompts import PROMPT_VERSION
from .assignment_evidence import has_fixed_quota_declaration


class DraftEvidenceError(ValueError):
    """The candidate cited a nonexistent or altered source quote."""


def _evidence_walk(value, path: str = "draft"):
    if isinstance(value, EvidenceQuote):
        yield path, value
    elif isinstance(value, BaseModel):
        for key in type(value).model_fields:
            yield from _evidence_walk(getattr(value, key), f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _evidence_walk(item, f"{path}[{idx}]")


def verify_quote_provenance(case: BusinessCase, draft: DraftProblemSpec) -> None:
    sources = case.source_map()
    for field_path, quote in _evidence_walk(draft):
        original = sources.get(quote.source_id)
        if original is None:
            raise DraftEvidenceError(f"{field_path}: unknown source_id {quote.source_id!r}")
        if quote.quote not in original:
            raise DraftEvidenceError(f"{field_path}: quote not a verbatim substring of source {quote.source_id!r}")


def fingerprint_business_case(case: BusinessCase) -> str:
    canonical = json.dumps(case.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _claim_quote_text(value: SemanticClaim) -> str:
    return " ".join(x.quote for x in value.evidence).lower()


def audit_draft(case: BusinessCase, draft: DraftProblemSpec, *, provider: str,
                prompt_version: str | None = None) -> FormulationReport:
    verify_quote_provenance(case, draft)
    issues: list[AuditIssue] = []
    questions: list[ClarificationQuestion] = list(draft.clarifying_questions)

    def issue(code: str, path: str, detail: str, severity: str = "BLOCKING") -> None:
        if not any(i.code == code and i.field_path == path for i in issues):
            issues.append(AuditIssue(code=code, field_path=path, detail=detail, severity=severity))

    def ask(path: str, question: str, why: str, priority: str = "HIGH") -> None:
        if not any(q.field_path == path for q in questions):
            questions.append(ClarificationQuestion(field_path=path, question=question,
                                                    reason=why, priority=priority))

    if draft.target.kind == TargetKind.UNRESOLVED:
        issue("A1_TARGET_UNRESOLVED", "target.kind", "因果目标尚未唯一确定")
        ask("target.kind", "您最终想求某个节点的设计标准化 arm mean、效应对比，还是某项完整政策的真实收益？",
            "同样的网络数据可能对应不同的因果目标")
    for name, question in [
        ("analysis_unit", "研究的基本单位是员工、客户、群组还是其他对象？"),
        ("treatment", "干预具体是什么，作用于哪个单位，处理值有哪些？"),
        ("outcome", "您希望研究的结果指标及测量时间是什么？"),
    ]:
        if getattr(draft.units_variables, name).basis == "UNRESOLVED":
            path = f"units_variables.{name}"
            issue("A2_MISSING_" + name.upper(), path, f"未明确 {name}")
            ask(path, question, "需要准确的因果目标变量语义")

    info = draft.information_design
    if info.assignment_family == AssignmentFamily.UNRESOLVED:
        issue("A4_ASSIGNMENT_UNRESOLVED", "information_design.assignment_family", "尚未确定 treatment 产生机制")
        ask("information_design.assignment_family", "treatment 是每个人独立随机分配、固定名额随机抽取，还是观察性形成？",
            "完整 assignment law 决定支持和设计标准化目标")
    elif info.assignment_family == AssignmentFamily.INDEPENDENT_BERNOULLI:
        quoted = _claim_quote_text(info.assignment_law)
        if not re.search(r"独立|independent|\bi\.?i\.?d\.?\b|bernoulli|伯努利|每人.*概率", quoted, re.I):
            issue("A4_UNGROUNDED_INDEPENDENCE", "information_design.assignment_family",
                  "独立 Bernoulli 不能仅凭『随机给一半』的陈述而获得许可")
            ask("information_design.assignment_family", "实验是否对每个人独立抛硬币决定处理，还是固定处理总人数？",
                "独立随机化需要明确协议依据")
    elif info.assignment_family == AssignmentFamily.COMPLETE_RANDOMIZATION:
        if not has_fixed_quota_declaration(case, info.assignment_law):
            issue("A4_UNGROUNDED_FIXED_QUOTA", "information_design.assignment_family",
                  "所引原句未明确支持固定人数随机分配，或包含否定、未决、近似、事后人数及其他机制；需核对实际分配规则")
            ask("information_design.assignment_family", "原试验是否按事先规定的固定人数随机选取处理单位？请说明人数、选取规则及是否每次相同。",
                "固定人数的分配规则不同于预算上限、未来政策或某次实际处理人数；仍需独立审核完整分配律")

    operator_levels = {
        PopulationInformationLevel.FULL_JOINT_LAW,
        PopulationInformationLevel.NODE_FULL_LAW,
        PopulationInformationLevel.NODE_ARM_CONDITIONAL_MEANS,
        PopulationInformationLevel.SIGNATURE_CONDITIONAL_MEANS,
        PopulationInformationLevel.ASSIGNMENT_CONDITIONAL_MEANS,
    }
    if info.population_information_level in operator_levels:
        quoted = _claim_quote_text(info.population_observable_operator)
        if not re.search(r"总体.{0,12}(律|分布|均值|算子)|条件均值|观测分布|population|joint law|joint distribution|conditional mean|operator|e\[", quoted, re.I):
            issue("A4_UNGROUNDED_POPULATION_OPERATOR", "information_design.population_information_level",
                  "有限样本字段声明不足以证明具有指定粒度的总体算子")
            ask("information_design.population_information_level", "目前能声明哪些精确的总体可观测分布或条件均值算子？",
                "变量名单或有限样本不等于总体信息许可")
    elif info.population_information_level in {
        PopulationInformationLevel.UNRESOLVED, PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION
    }:
        issue("A4_POPULATION_INFORMATION_OPEN", "information_design.population_information_level",
              "尚未明确识别所需的总体观测信息算子")
        ask("information_design.population_information_level", "您的研究设计中，能以哪种粒度定义可用的总体观测信息？",
            "需要区分实际有限样本和理论识别所允许的总体信息")

    # A direct contrast explicitly fixing every other assignment is not an
    # exposure-standardized contrast and does not require g_i. The target must
    # actually say that others remain fixed; generic "direct effect" still needs
    # clarification under network interference. This is FORMULATION gating only.
    direct_desc = " ".join([case.business_question, draft.target.description.value or ""]).lower()
    fixed_other_direct = (draft.target.kind == TargetKind.DIRECT_EFFECT
        and bool(re.search(r"(固定|保持|不变动|不变).{0,24}(其他|其余|他人)|z_-i|others.{0,30}(fixed|unchanged)", direct_desc, re.I)))
    if (draft.structure.unit_network.basis != "UNRESOLVED"
            and draft.structure.exposure_mapping.basis == "UNRESOLVED"
            and draft.target.kind in {
                TargetKind.DIRECT_EFFECT, TargetKind.SPILLOVER_EFFECT, TargetKind.LOCAL_TOTAL_EFFECT, TargetKind.TOTAL_EFFECT,
                TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN
            }
            and not fixed_other_direct):
        issue("A3_EXPOSURE_UNRESOLVED", "structure.exposure_mapping", "未定义网络暴露规则")
        ask("structure.exposure_mapping", "您希望怎样从邻居的 treatment 定义 exposure（例如计数、比例、加权规则）？",
            "暴露定义影响 design-standardized estimand 的语义")

    for ambiguity in draft.ambiguities:
        issue("AMBIGUITY_REQUIRES_REVIEW", ambiguity.field_path, ambiguity.description)
        ask(ambiguity.field_path, "请确认以下哪个解释符合真实业务：" + " / ".join(ambiguity.alternatives),
            "当前描述具有不同的有效数学形式")

    # Any explicit key must have source evidence, enforced via SemanticClaim and quote checks.
    # Even completely documented input is still a *draft*; the core is never invoked here.
    review_status = ("NEEDS_CLARIFICATION" if any(i.severity == "BLOCKING" for i in issues)
                     or any(q.priority == "HIGH" for q in questions) else "DRAFT_READY_FOR_HUMAN_REVIEW")
    priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    questions.sort(key=lambda q: priority[q.priority])
    return FormulationReport(
        prompt_version=prompt_version or PROMPT_VERSION,
        case_id=case.case_id,
        input_sha256=fingerprint_business_case(case),
        provider=provider,
        draft=draft,
        review_status=review_status,
        issues=issues,
        suggested_questions=questions,
    )
