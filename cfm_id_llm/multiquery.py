"""v0.9 optional MULTI-query draft wrapper; the v0.1 single-query schema is unchanged.

Never a Core TaskSpec, theorem result, or mathematical certificate.  A business
case can have several different questions sharing the same documented design.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import Field, model_validator

from .audit import audit_draft, fingerprint_business_case, verify_quote_provenance
from .orchestration_schemas import canonical_sha256
from .schemas import (
    AuditIssue, BusinessCase, ClarificationQuestion, DraftProblemSpec,
    EvidenceQuote, FormulationReport, SemanticClaim, SourceKind, StrictModel, TargetDraft,
)

_SHA = r"^[0-9a-f]{64}$"


class BusinessInquiryV09(StrictModel):
    query_id: str = Field(pattern=r"^q[1-9][0-9]{0,2}$")
    # This must cite an explicitly requested goal, not merely an imagined theorem.
    business_goal: SemanticClaim
    target: TargetDraft
    requested_comparison_or_policy: SemanticClaim = Field(default_factory=SemanticClaim)
    clarifying_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def require_grounded_goal(self):
        if self.business_goal.basis == "UNRESOLVED":
            raise ValueError("Each inquiry needs a source-grounded business_goal")
        return self


class MultiQueryDraftV09(StrictModel):
    schema_version: Literal["cfm-id-multiquery-v0.9"] = "cfm-id-multiquery-v0.9"
    # Reuses the unchanged v0.1 draft as common facts and primary-query semantics.
    shared_draft: DraftProblemSpec
    primary_query_id: str = Field(pattern=r"^q[1-9][0-9]{0,2}$")
    queries: list[BusinessInquiryV09] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def consistent_queries(self):
        ids = [q.query_id for q in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("Query IDs must be unique")
        by_id = {q.query_id: q for q in self.queries}
        if self.primary_query_id not in by_id:
            raise ValueError("primary_query_id does not exist")
        if by_id[self.primary_query_id].target != self.shared_draft.target:
            raise ValueError("Primary query target must equal shared_draft.target")
        # Exact same target and business goal should never produce duplicate tasks.
        seen: set[str] = set()
        for q in self.queries:
            key = canonical_sha256({"target": q.target.model_dump(mode="json"), "business_goal": q.business_goal.model_dump(mode="json")})
            if key in seen:
                raise ValueError("Duplicate business inquiry")
            seen.add(key)
        return self


class QueryAuditV09(StrictModel):
    query_id: str
    proposed_target: str
    review_status: Literal["NEEDS_CLARIFICATION", "DRAFT_READY_FOR_HUMAN_REVIEW"]
    issues: list[AuditIssue] = Field(default_factory=list)
    suggested_questions: list[ClarificationQuestion] = Field(default_factory=list)
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"


class MultiQueryReportV09(StrictModel):
    schema_version: Literal["cfm-id-multiquery-report-v0.9"] = "cfm-id-multiquery-report-v0.9"
    gateway_version: Literal["0.9.0"] = "0.9.0"
    prompt_version: str
    provider: str
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    draft: MultiQueryDraftV09
    primary_formulation: FormulationReport
    query_audits: list[QueryAuditV09]
    overall_status: Literal["NEEDS_CLARIFICATION", "DRAFT_READY_FOR_HUMAN_REVIEW"]
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    core_called: Literal[False] = False
    formal_core_spec_generated: Literal[False] = False
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bind_report(self):
        if self.draft_sha256 != canonical_sha256(self.draft):
            raise ValueError("Multi-query draft fingerprint mismatch")
        if self.primary_formulation.case_id != self.case_id or self.primary_formulation.input_sha256 != self.input_sha256:
            raise ValueError("Primary formulation not bound to business case")
        if self.primary_formulation.draft != self.draft.shared_draft:
            raise ValueError("Primary formulation must match common draft")
        if [a.query_id for a in self.query_audits] != [q.query_id for q in self.draft.queries]:
            raise ValueError("Query audits not aligned with queries")
        return self


class HumanMultiQueryReviewV09(StrictModel):
    """Externally entered human decision; a hash is NOT an authentication signature."""
    schema_version: Literal["cfm-id-multiquery-human-v0.9"] = "cfm-id-multiquery-human-v0.9"
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    confirmed_query_ids: list[str] = Field(min_length=1, max_length=8)
    reviewed_by: str = Field(min_length=2, max_length=150)
    review_note: str = Field(min_length=5, max_length=3000)
    decision: Literal["CONFIRMED"]

    @model_validator(mode="after")
    def unique_confirmations(self):
        if len(self.confirmed_query_ids) != len(set(self.confirmed_query_ids)):
            raise ValueError("Duplicate confirmed queries")
        return self


class ReviewedMultiQueryV09(StrictModel):
    schema_version: Literal["cfm-id-reviewed-multiquery-v0.9"] = "cfm-id-reviewed-multiquery-v0.9"
    report: MultiQueryReportV09
    human_review: HumanMultiQueryReviewV09
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    formal_core_spec_generated: Literal[False] = False
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bind_human_review(self):
        r, h = self.report, self.human_review
        if (h.case_id != r.case_id or h.input_sha256 != r.input_sha256 or h.draft_sha256 != r.draft_sha256):
            raise ValueError("Human approval does not match this version of source materials and all queries")
        if not set(h.confirmed_query_ids).issubset({q.query_id for q in r.draft.queries}):
            raise ValueError("Approval covers a nonexistent query")
        return self


def verify_multiquery_provenance(case: BusinessCase, draft: MultiQueryDraftV09) -> None:
    """Re-check quoted evidence in every inquiry, not just the primary query."""
    from pydantic import BaseModel
    sources = case.source_map()

    def walk(value):
        if isinstance(value, EvidenceQuote):
            yield value
        elif isinstance(value, BaseModel):
            for key in type(value).model_fields:
                yield from walk(getattr(value, key))
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for quote in walk(draft):
        if quote.source_id not in sources or quote.quote not in sources[quote.source_id]:
            raise ValueError("Multi-query cited a missing or modified evidence quote")


def audit_multiquery(case: BusinessCase, draft: MultiQueryDraftV09, *,
                     provider: str, prompt_version: str) -> MultiQueryReportV09:
    verify_multiquery_provenance(case, draft)
    # Reuse the exact old audit so that a multi-query layer cannot downgrade A4/A5 requirements.
    base = audit_draft(case, draft.shared_draft, provider=provider, prompt_version=prompt_version)
    audits: list[QueryAuditV09] = []
    for q in draft.queries:
        per_query = draft.shared_draft.model_copy(update={"target": q.target})
        verify_quote_provenance(case, per_query)
        checked = audit_draft(case, per_query, provider=provider, prompt_version=prompt_version)
        questions = list(checked.suggested_questions)
        for question in q.clarifying_questions:
            if question not in questions:
                questions.append(question)
        # A spreadsheet header cannot *by itself* establish that management requested
        # a new business objective. This is narrower than judging causal correctness.
        claimed_sources = {e.source_id for e in q.business_goal.evidence}
        declared_dicts = {s.source_id for s in case.sources if s.kind == SourceKind.DATA_DICTIONARY}
        extra_issues = list(checked.issues)
        if claimed_sources and claimed_sources.issubset(declared_dicts):
            extra_issues.append(AuditIssue(
                code="BUSINESS_GOAL_FROM_DATA_DICTIONARY_ONLY",
                field_path=f"queries.{q.query_id}.business_goal",
                severity="BLOCKING",
                detail="仅凭数据表的表头/字典不能推断业务人员真的提出了这个因果目标。"))
        status = ("NEEDS_CLARIFICATION" if checked.review_status == "NEEDS_CLARIFICATION"
                  or any(x.priority == "HIGH" for x in q.clarifying_questions)
                  or any(i.severity == "BLOCKING" for i in extra_issues)
                  else "DRAFT_READY_FOR_HUMAN_REVIEW")
        audits.append(QueryAuditV09(query_id=q.query_id, proposed_target=q.target.kind.value,
                                   review_status=status, issues=extra_issues,
                                   suggested_questions=questions))
    overall = ("NEEDS_CLARIFICATION" if any(a.review_status == "NEEDS_CLARIFICATION" for a in audits)
               else "DRAFT_READY_FOR_HUMAN_REVIEW")
    return MultiQueryReportV09(prompt_version=prompt_version, provider=provider,
                              case_id=case.case_id, input_sha256=fingerprint_business_case(case),
                              draft_sha256=canonical_sha256(draft), draft=draft,
                              primary_formulation=base, query_audits=audits,
                              overall_status=overall)


def approve_multiquery(case: BusinessCase, report: MultiQueryReportV09,
                       human_review: HumanMultiQueryReviewV09) -> ReviewedMultiQueryV09:
    if report.case_id != case.case_id or report.input_sha256 != fingerprint_business_case(case):
        raise ValueError("Source materials changed since report generation")
    fresh = audit_multiquery(case, report.draft, provider=report.provider, prompt_version=report.prompt_version)
    if fresh != report:
        raise ValueError("Report is inconsistent with independent re-audit")
    return ReviewedMultiQueryV09(report=report, human_review=human_review)


def render_multiquery_text(report: MultiQueryReportV09) -> str:
    d = report.draft.shared_draft
    lines = ["CFM-ID Gateway v0.9：业务问题规范化草稿（没有进行数学识别）",
             f"分析对象：{d.units_variables.analysis_unit.value or '待确认'}",
             f"措施：{d.units_variables.treatment.value or '待确认'}",
             f"结果指标：{d.units_variables.outcome.value or '待确认'}",
             f"从同一份业务资料提取出 {len(report.draft.queries)} 个候选因果问题："]
    byid = {x.query_id: x for x in report.query_audits}
    for q in report.draft.queries:
        audit = byid[q.query_id]
        lines.extend([f"  • {q.query_id}: {q.business_goal.value}（{q.target.kind.value}）",
                      f"    下一步：{'核查缺失条件' if audit.review_status == 'NEEDS_CLARIFICATION' else '研究者确认'}"])
    lines.append("A4/A5 仍需研究者核对；规范化 JSON 不是总体数据许可或因果识别证明。")
    lines.append("正式 Identification：未执行；Estimation：未放行。")
    return "\n".join(lines)
