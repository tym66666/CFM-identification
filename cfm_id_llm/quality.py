"""CFM-ID A0 v0.10 business-formulation quality layer.

Standalone Gateway extension based on v0.9.  No `pfn_pipeline`, no Core,
no theorem selection, no approval of A4/A5, and no Estimation handoff.
The legacy v0.9 schema/report/audit remain available unchanged.

Important distinction:
- BUSINESS clarification concerns what the user *wants* or what the business did.
- SCIENTIFIC review concerns whether mathematical A4/A5/A6 conditions hold.
- MATERIAL recheck concerns a draft failing to extract/cite something: the LLM
  should re-read the supplied materials BEFORE pestering a business user.
These are independent dimensions rather than one overloaded `NEEDS_CLARIFICATION`.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from .audit import fingerprint_business_case
from .multiquery import (
    BusinessInquiryV09, MultiQueryDraftV09, MultiQueryReportV09, audit_multiquery,
)
from .orchestration_schemas import canonical_sha256
from .schemas import (
    AuditIssue, BusinessCase, ClarificationQuestion, DraftProblemSpec,
    SemanticClaim, StrictModel, TargetDraft, TargetKind,
)

_SHA = r"^[0-9a-f]{64}$"


class QuerySemanticsV010(StrictModel):
    """Business-side proposed slots, NEVER verified typed target coordinates.

    All slots are SemanticClaim: missing information stays UNRESOLVED, and every
    proposed string carries real quote evidence.  Don't infer a treatment vector
    or a weight vector from a vague slogan.  The scientific crosswalk remains
    the Core team's independent responsibility.
    """
    target_population: SemanticClaim = Field(default_factory=SemanticClaim)
    intervention: SemanticClaim = Field(default_factory=SemanticClaim)
    comparator: SemanticClaim = Field(default_factory=SemanticClaim)
    neighbor_exposure: SemanticClaim = Field(default_factory=SemanticClaim)
    aggregation: SemanticClaim = Field(default_factory=SemanticClaim)
    time_horizon: SemanticClaim = Field(default_factory=SemanticClaim)
    policy_assignment: SemanticClaim = Field(default_factory=SemanticClaim)
    standardization_distribution: SemanticClaim = Field(default_factory=SemanticClaim)

    def unresolved_fields(self) -> list[str]:
        return [name for name in type(self).model_fields
                if getattr(self, name).basis == "UNRESOLVED"]


class BusinessInquiryV010(StrictModel):
    query_id: str = Field(pattern=r"^q[1-9][0-9]{0,2}$")
    business_goal: SemanticClaim
    target: TargetDraft
    requested_comparison_or_policy: SemanticClaim = Field(default_factory=SemanticClaim)
    clarifying_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=8)
    semantics: QuerySemanticsV010 = Field(default_factory=QuerySemanticsV010)

    @model_validator(mode="after")
    def grounded_goal(self):
        if self.business_goal.basis == "UNRESOLVED":
            raise ValueError("Each query requires a grounded user business goal")
        return self

    def as_v09(self) -> BusinessInquiryV09:
        return BusinessInquiryV09.model_validate(self.model_dump(
            mode="json", exclude={"semantics"}))


class MultiQueryDraftV010(StrictModel):
    schema_version: Literal["cfm-id-multiquery-v0.10"] = "cfm-id-multiquery-v0.10"
    shared_draft: DraftProblemSpec
    primary_query_id: str = Field(pattern=r"^q[1-9][0-9]{0,2}$")
    queries: list[BusinessInquiryV010] = Field(min_length=1, max_length=8)

    def as_v09(self) -> MultiQueryDraftV09:
        return MultiQueryDraftV09(
            shared_draft=self.shared_draft,
            primary_query_id=self.primary_query_id,
            queries=[q.as_v09() for q in self.queries],
        )

    @model_validator(mode="after")
    def v09_invariants(self):
        # Enforce all existing primary/duplicate/goal invariants, rather than
        # introducing a competing interpretation of v0.9.
        self.as_v09()
        return self


class ReviewActionV010(StrictModel):
    owner: Literal["BUSINESS_USER", "A0_FORMULATOR", "SCIENTIFIC_REVIEWER"]
    code: str = Field(min_length=2, max_length=120)
    field_path: str = Field(min_length=2, max_length=200)
    detail: str = Field(min_length=5, max_length=1200)
    suggested_question: str | None = Field(default=None, max_length=1000)


class QueryQualityAuditV010(StrictModel):
    query_id: str
    business_status: Literal[
        "FORMALIZATION_READY", "FORMULATION_RECHECK_REQUIRED", "BUSINESS_CLARIFICATION_REQUIRED"
    ]
    semantic_status: Literal["SEMANTIC_CANDIDATE_COMPLETE", "SEMANTIC_CANDIDATE_PARTIAL"]
    scientific_status: Literal["SCIENTIFIC_REVIEW_REQUIRED"] = "SCIENTIFIC_REVIEW_REQUIRED"
    unresolved_semantics: list[str] = Field(default_factory=list)
    business_questions: list[ClarificationQuestion] = Field(default_factory=list)
    actions: list[ReviewActionV010] = Field(default_factory=list)
    # Preserve the real v0.9 audit issues; do NOT make A4 disappear.
    legacy_issues: list[AuditIssue] = Field(default_factory=list)
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"


class MultiQueryQualityReportV010(StrictModel):
    schema_version: Literal["cfm-id-a0-quality-report-v0.10"] = "cfm-id-a0-quality-report-v0.10"
    gateway_version: Literal["0.10.0"] = "0.10.0"
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    provider: str
    prompt_version: str
    draft: MultiQueryDraftV010
    query_quality: list[QueryQualityAuditV010]
    legacy_audit: MultiQueryReportV09
    overall_business_status: Literal[
        "FORMALIZATION_READY", "FORMULATION_RECHECK_REQUIRED", "BUSINESS_CLARIFICATION_REQUIRED"
    ]
    scientific_review_required: Literal[True] = True
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    core_called: Literal[False] = False
    formal_core_spec_generated: Literal[False] = False
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bind_report(self):
        if canonical_sha256(self.draft) != self.draft_sha256:
            raise ValueError("v0.10 draft fingerprint mismatch")
        if self.legacy_audit.draft != self.draft.as_v09():
            raise ValueError("Legacy audit doesn't correspond to v0.10 draft")
        if (self.case_id != self.legacy_audit.case_id or
                self.input_sha256 != self.legacy_audit.input_sha256):
            raise ValueError("Business material fingerprint mismatch")
        if ([q.query_id for q in self.draft.queries] !=
                [q.query_id for q in self.query_quality]):
            raise ValueError("Query audit IDs out of alignment")
        derived = overall_business_status([q.business_status for q in self.query_quality])
        if self.overall_business_status != derived:
            raise ValueError("Overall status inconsistent with query quality")
        return self


def overall_business_status(statuses: list[str]) -> str:
    if "BUSINESS_CLARIFICATION_REQUIRED" in statuses:
        return "BUSINESS_CLARIFICATION_REQUIRED"
    if "FORMULATION_RECHECK_REQUIRED" in statuses:
        return "FORMULATION_RECHECK_REQUIRED"
    return "FORMALIZATION_READY"


# Legacy codes are deliberately not edited: all A4/A5 blockers remain visible
# inside legacy_audit and are moved to a separate, science-owned action lane.
_BUSINESS_CODES = {"A1_TARGET_UNRESOLVED"}
_REEXTRACT_CODES = {
    "A2_MISSING_ANALYSIS_UNIT", "A2_MISSING_TREATMENT", "A2_MISSING_OUTCOME",
    "BUSINESS_GOAL_FROM_DATA_DICTIONARY_ONLY",
}


def _question_is_scientific(text: str) -> bool:
    """Conservative filter: a mislabeled technical request is not a user-facing question."""
    return bool(re.search(
        r"(?:\bA[456]\b|\bPOINT\b|\bTaskSpec\b|\bpopulation\s+(?:operator|law)|"
        r"总体.{0,10}(?:算子|观测律)|暴露充分性|交换性|positivity|identifiability|因果假设许可)",
        text, re.I))


def _owner_for_field(path: str) -> str:
    if path.startswith(("information_design.", "assumptions", "validity.",
                        "structure.exposure_mapping", "structure.variable_causal_graph")):
        return "SCIENTIFIC_REVIEWER"
    if path.startswith(("units_variables.", "structure.unit_network", "structure.network_pretreatment_status")):
        return "A0_FORMULATOR"
    return "BUSINESS_USER"


def _action_from_issue(issue: AuditIssue) -> ReviewActionV010:
    if issue.code in _BUSINESS_CODES:
        owner = "BUSINESS_USER"
    elif issue.code in _REEXTRACT_CODES or issue.code == "BUSINESS_GOAL_FROM_DATA_DICTIONARY_ONLY":
        owner = "A0_FORMULATOR"
    elif issue.code == "AMBIGUITY_REQUIRES_REVIEW":
        owner = _owner_for_field(issue.field_path)
    elif issue.code.startswith(("A4_", "A3_")):
        owner = "SCIENTIFIC_REVIEWER"
    else:
        owner = "A0_FORMULATOR" if issue.severity == "WARNING" else "SCIENTIFIC_REVIEWER"
    return ReviewActionV010(owner=owner, code=issue.code, field_path=issue.field_path,
                            detail=issue.detail)


def _query_context(case: BusinessCase, q: BusinessInquiryV010) -> str:
    # Not evidence of the truth of a semantic claim: only used to detect a
    # missed extraction and send the file back to A0 rather than questioning the user.
    return " ".join([case.business_question, q.business_goal.value or "",
                     q.target.description.value or ""])


def _policy_subset_hint(text: str) -> bool:
    """A recheck hint; evaluation weights alone are not treatment allocation.

    Strip only explicit half-weight phrases within evaluation clauses. Bare
    half-population claims and treatment restrictions remain visible.
    This does not infer coordinates or certify any policy interpretation.
    """
    clauses = re.split(r"[。；;.!?！？\n]", text)
    for index, clause in enumerate(clauses):
        if re.search(r"评价|评估|计算|统计|平均|权重", clause):
            clauses[index] = re.sub(
                r"(?:各占\s*一半|权重(?:各)?(?:为|是|占)\s*一半)"
                r"(?!\s*(?:的)?(?:名额|人数|人员|对象|员工|销售员|门店|处理|治疗|开通|使用))",
                "", clause)
    return bool(re.search(
        r"部分|一半|仅给|只给|只处理|仅处理|少数|some\s+|subset|only\s+one",
        ' '.join(clauses), re.I))


def _semantic_actions(case: BusinessCase, q: BusinessInquiryV010) -> list[ReviewActionV010]:
    text = _query_context(case, q)
    result = []
    # Simple explicit textual clash audit.  This is intentionally only a
    # recheck signal; it does not certify that any other semantic mapping is right.
    query_intent = ' '.join([q.business_goal.value or '',q.target.description.value or ''])
    assignment_text = q.semantics.policy_assignment.value or ''
    intended_all = bool(re.search(r"全员|全部|所有|everyone|all\s+(employees|stores|units)", query_intent,re.I))
    proposed_subset = _policy_subset_hint(assignment_text)
    if intended_all and proposed_subset and q.target.kind != TargetKind.POLICY_OPTIMIZATION:
        result.append(ReviewActionV010(
            owner='A0_FORMULATOR', code='POLICY_SCOPE_SEMANTIC_CONFLICT',
            field_path=f'queries.{q.query_id}.semantics.policy_assignment',
            detail='原业务目标描述为全员/全部推广，但候选政策范围写成部分处理；必须重新阅读原文并核对，不能进入正式数学规格。'))
    population_text = q.semantics.target_population.value or ''
    untreated_population = bool(re.search(
        r"未(?:处理|开通|使用)|没有(?:开通|使用)|\buntreated\b", population_text, re.I))
    # A past or mixed population, or a policy explicitly excluding the focal
    # unit, is not enough to infer this clash. This remains a recheck hint,
    # never a theorem or a complete semantic validator.
    qualified_population = bool(re.search(
        r"过去|此前|原先|以前|基线|实验前|试验前|处理前|已(?:处理|开通|使用)|"
        r"\bbaseline\b|\bprevious\w*\b|pre.?treatment|\bboth\b", population_text, re.I))
    global_policy = bool(re.search(
        r"全员|(?:全部|所有)(?:\d+)?(?:人|员工|销售员|门店|单位)|"
        r"\beveryone\b|\ball\s+(?:employees|stores|units)\b", assignment_text, re.I))
    qualified_policy = bool(re.search(
        r"不|未|没有|除|其余|其他|邻居|同伴|\bpeers?\b|\bneighbou?rs?\b|"
        r"\bexcept\w*\b|\bexcluding\b|\bnot\b", assignment_text, re.I))
    if (q.target.kind == TargetKind.SPILLOVER_EFFECT and untreated_population
            and global_policy and not qualified_population and not qualified_policy):
        result.append(ReviewActionV010(
            owner='A0_FORMULATOR', code='SPILLOVER_POLICY_POPULATION_CONFLICT',
            field_path=f'queries.{q.query_id}.semantics.policy_assignment',
            detail='溢出查询以未处理者为对象，却填入全员处理政策；请复查是否误用了其他查询的政策，保留原始草稿供核对，不能自行补造干预坐标。'))
    if q.target.kind in (TargetKind.FIXED_POLICY_VALUE, TargetKind.STOCHASTIC_POLICY_VALUE,
                         TargetKind.POLICY_OPTIMIZATION):
        if q.semantics.policy_assignment.basis == "UNRESOLVED":
            if q.target.kind == TargetKind.POLICY_OPTIMIZATION:
                result.append(ReviewActionV010(owner='SCIENTIFIC_REVIEWER',
                    code='POLICY_CHOICE_CONSTRAINTS_OPEN',
                    field_path=f'queries.{q.query_id}.semantics.policy_assignment',
                    detail='政策选择的候选范围或限制尚未明确；须核对原文并补问缺项，不要求先提供待求的最优名单。'))
                return result
            mentioned = bool(re.search(r"全员|所有|全部|每个.{0,6}(员工|门店|医院)|everyone|all\s+(employees|stores|units)|whole\s+team", text, re.I))
            result.append(ReviewActionV010(
                owner="A0_FORMULATOR" if mentioned else "SCIENTIFIC_REVIEWER",
                code="POLICY_ASSIGNMENT_SEMANTICS_OPEN",
                field_path=f"queries.{q.query_id}.semantics.policy_assignment",
                detail=("材料中已有推广范围提示，应先重新提取，不要询问业务人员重复描述。"
                        if mentioned else "政策具体分配、权重或范围尚不明确；不能转换成正式政策向量。")))
    if q.target.kind in (TargetKind.DIRECT_EFFECT, TargetKind.SPILLOVER_EFFECT,
                         TargetKind.LOCAL_TOTAL_EFFECT, TargetKind.TOTAL_EFFECT, TargetKind.ATE, TargetKind.CATE):
        if q.semantics.comparator.basis == "UNRESOLVED":
            result.append(ReviewActionV010(
                owner="SCIENTIFIC_REVIEWER", code="EFFECT_COMPARATOR_OPEN",
                field_path=f"queries.{q.query_id}.semantics.comparator",
                detail="效应对照未精确给定；不得默认为某个暴露/处理对比。"))
    return result


def audit_business_quality(case: BusinessCase, draft: MultiQueryDraftV010, *,
                           provider: str, prompt_version: str) -> MultiQueryQualityReportV010:
    legacy = audit_multiquery(case, draft.as_v09(), provider=provider, prompt_version=prompt_version)
    reviews = []
    for inquiry, previous in zip(draft.queries, legacy.query_audits):
        actions = [_action_from_issue(issue) for issue in previous.issues]
        actions += _semantic_actions(case, inquiry)
        questions: list[ClarificationQuestion] = []
        for question in previous.suggested_questions:
            owner = ('SCIENTIFIC_REVIEWER' if _question_is_scientific(question.question)
                     else _owner_for_field(question.field_path))
            if owner == "BUSINESS_USER":
                # Data-dictionary-only user goals are re-extraction failures, not
                # invitations to add invented business queries.
                if any(a.code == "BUSINESS_GOAL_FROM_DATA_DICTIONARY_ONLY" for a in actions):
                    continue
                # Legacy A1's question uses expert jargon; the user should only
                # see a brief business-language clarification.
                asked = (question.model_copy(update={
                    'question': '您主要想比较哪些做法，以及希望看到个人、同事还是整体的结果？',
                    'reason': '不同的业务目标需要分开分析。',
                }) if question.field_path == 'target.kind' else question)
                if asked not in questions:
                    questions.append(asked)
            else:
                if not any(a.field_path == question.field_path and a.owner == owner for a in actions):
                    actions.append(ReviewActionV010(owner=owner,
                        code="REVIEW_INSTEAD_OF_BUSINESS_QUESTION",
                        field_path=question.field_path, detail=question.reason))
        # Check source-grounded semantic slots too; legacy v0.9 didn't know these fields.
        for field_name in type(inquiry.semantics).model_fields:
            claim = getattr(inquiry.semantics, field_name)
            if claim.basis != "UNRESOLVED":
                source_map = case.source_map()
                for quote in claim.evidence:
                    if quote.source_id not in source_map or quote.quote not in source_map[quote.source_id]:
                        raise ValueError(f"Invalid query semantics citation in {inquiry.query_id}.{field_name}")
        has_business = bool(questions or any(a.owner == "BUSINESS_USER" for a in actions))
        has_recheck = any(a.owner == "A0_FORMULATOR" for a in actions)
        status = ("BUSINESS_CLARIFICATION_REQUIRED" if has_business else
                  "FORMULATION_RECHECK_REQUIRED" if has_recheck else
                  "FORMALIZATION_READY")
        unresolved = inquiry.semantics.unresolved_fields()
        reviews.append(QueryQualityAuditV010(
            query_id=inquiry.query_id, business_status=status,
            semantic_status=("SEMANTIC_CANDIDATE_PARTIAL" if unresolved else
                             "SEMANTIC_CANDIDATE_COMPLETE"),
            unresolved_semantics=unresolved, business_questions=questions,
            actions=actions, legacy_issues=previous.issues,
        ))
    return MultiQueryQualityReportV010(
        case_id=case.case_id, input_sha256=fingerprint_business_case(case),
        draft_sha256=canonical_sha256(draft), provider=provider,
        prompt_version=prompt_version, draft=draft, query_quality=reviews,
        legacy_audit=legacy,
        overall_business_status=overall_business_status([q.business_status for q in reviews]),
    )


def draft_from_v09(legacy_draft: MultiQueryDraftV09) -> MultiQueryDraftV010:
    """Explicit legacy migration. Slots are UNRESOLVED, never fabricated."""
    return MultiQueryDraftV010(shared_draft=legacy_draft.shared_draft,
                              primary_query_id=legacy_draft.primary_query_id,
                              queries=[BusinessInquiryV010.model_validate({
                                  **q.model_dump(mode="json"), "semantics": QuerySemanticsV010().model_dump(mode="json")
                              }) for q in legacy_draft.queries])
