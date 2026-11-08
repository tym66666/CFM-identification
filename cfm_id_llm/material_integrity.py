"""v0.8: independent *document* integrity gate around v0.7 normalization.

This gate is intentionally narrower than a theorem verifier.  It checks that the
business draft did not promote table-schema metadata into causal evidence, that
contradictory protocol descriptions are escalated, and that suspicious text in
attachments is treated as data, not instructions.  Nothing in this module can
mark A4/A5 as scientifically certified or unlock Estimation.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Literal

from pydantic import Field

from .audit import _evidence_walk
from .document_intake import (
    AttachmentRequestV07, IntakeReportV07, create_intake,
)
from .multisource_normalization import (
    MultisourceReviewV07, review_intake,
)
from .schemas import (
    AssignmentFamily, FormulationReport, PopulationInformationLevel,
    StrictModel,
)

VERSION_V08 = '0.8.0'
PROMPT_VERSION_V08 = 'cfm-id-evidence-grounded-formulator-v0.8.0'

# These deliberately narrow patterns are used for quarantine, not a universal
# prompt-injection detector.  The original document is not modified on disk.
# A false negative is possible; an injection warning never proves safe content.
_DIRECT_INJECTION_PATTERNS = (
    re.compile(r'(?:忽略|无视|覆盖).{0,15}(?:此前|先前|以上|所有).{0,14}(?:指令|规则|要求|提示)', re.I),
    re.compile(r'(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|prior|system|developer|above)\s+(?:instructions?|prompts?|rules?)', re.I),
    re.compile(r'(?:系统|开发者|system|developer)\s*(?:指令|消息|message|prompt)?\s*[:：]\s*(?:ignore|忽略|你现在|you\s+must|must\s+output)', re.I),
    re.compile(r'(?:必须|直接|立刻|always|must)\s*.{0,22}(?:输出|标记|返回|return|report|output)\s*.{0,12}(?:VERIFIED\s*POINT|POINT\s*VERIFIED|LLM_UNVERIFIED)', re.I),
)

# Detection is an aid to the reviewer, not a mathematical contradiction proof.
_BEFORE_NETWORK = re.compile(
    r'(?:合作|关系|网络|边|链接).{0,30}(?:处理|随机|分配|开通|实验).{0,12}(?:前|之前)|'
    r'(?:network|collaboration|links?|edges?).{0,38}(?:recorded|measured|fixed).{0,25}before\s+(?:treatment|assignment)', re.I)
_AFTER_NETWORK = re.compile(
    r'(?:合作|关系|网络|边|链接).{0,30}(?:处理|随机|分配|开通|实验).{0,12}(?:后|之后)|'
    r'(?:network|collaboration|links?|edges?).{0,38}(?:recorded|measured|updated).{0,25}after\s+(?:treatment|assignment)', re.I)
_FIXED_QUOTA = re.compile(
    r'恰好\s*\d+.{0,35}(?:人|名|员工|销售员|随机|抽)|'
    r'固定.{0,16}(?:人|名|配额|名额)|'
    r'exactly\s+\d+.{0,35}(?:selected|treated|people|salespeople|employees)|'
    r'complete randomization', re.I)
_INDEPENDENT = re.compile(
    r'每人.{0,20}独立.{0,22}(?:随机|抽签|概率|分配)|'
    r'独立.{0,25}(?:随机|伯努利|分配)|'
    r'(?:independently|independent).{0,30}(?:assign|random|bernoulli)|iid\s+bernoulli', re.I)


class DocumentFindingV08(StrictModel):
    code: str
    severity: Literal['BLOCKING', 'REVIEW']
    source_ids: list[str] = Field(default_factory=list)
    field_path: str | None = None
    explanation: str


class MaterialQualityReportV08(StrictModel):
    version: Literal['0.8.0'] = '0.8.0'
    base: MultisourceReviewV07
    findings: list[DocumentFindingV08] = Field(default_factory=list)
    decision: Literal[
        'ASK_ESSENTIAL_BUSINESS_QUESTION',
        'REVIEW_DOCUMENT_CONFLICT_OR_QUALITY',
        'RESEARCHER_REVIEW',
    ]
    document_gate_passed: bool
    # Never a Core adapter; human review is still necessary even after a pass.
    formal_core_spec_generated: Literal[False] = False
    mathematical_verification: Literal['NOT_PERFORMED'] = 'NOT_PERFORMED'
    estimation_handoff_allowed: Literal[False] = False


def _contains_directive(text: str) -> bool:
    return any(p.search(text) for p in _DIRECT_INJECTION_PATTERNS)


def _quarantine_lines(text: str) -> tuple[str, int]:
    """Exclude obvious instructional text from *the LLM-facing excerpt*.

    The original raw bytes remain recorded by file_sha256.  A placeholder is
    visible, warnings describe the sanitization, and references to deleted text
    will fail the exact-quote provenance check.  This is a defense-in-depth
    heuristic, not an assertion that all prompt injection has been removed.
    """
    lines = text.splitlines(keepends=True)
    cleaned = []
    removed = 0
    for line in lines:
        if _contains_directive(line):
            cleaned.append('[UNTRUSTED_DOCUMENT_INSTRUCTION_QUARANTINED]\n')
            removed += 1
        else:
            cleaned.append(line)
    return ''.join(cleaned), removed


def create_grounded_intake(*, case_id: str, business_question: str,
                           attachments: list[AttachmentRequestV07],
                           response_language: Literal['zh','en'] = 'zh') -> IntakeReportV07:
    """Use the same v0.7 record format; quarantine obvious document commands.

    Version stays 0.7.0 because this function returns the *existing* intake
    contract, with the excerpt digest re-bound to the sanitized content.
    """
    intake = create_intake(case_id=case_id, business_question=business_question,
                           attachments=attachments, response_language=response_language)
    for rec, src in zip(intake.attachments, intake.case.sources):
        if rec.mode != 'TEXT_EXCERPT':
            # Table headers are untrusted as well. If such a row is malicious,
            # quarantine the whole summary line rather than forwarding a command.
            if rec.mode != 'SCHEMA_ONLY':
                continue
        filtered, count = _quarantine_lines(src.text)
        if count:
            src.text = filtered
            rec.extracted_sha256 = sha256(filtered.encode('utf-8')).hexdigest()
            rec.extracted_chars = len(filtered)
            if 'POSSIBLE_PROMPT_INJECTION_QUARANTINED' not in rec.warnings:
                rec.warnings.append('POSSIBLE_PROMPT_INJECTION_QUARANTINED')
            intake.warnings.append(f'{rec.source_id}:POSSIBLE_PROMPT_INJECTION_QUARANTINED')
    return intake


def _source_design_signals(intake: IntakeReportV07) -> tuple[set[str], set[str]]:
    """Conservatively scan input *claims*. Does not prove a design was used."""
    fixed: set[str] = set()
    independent: set[str] = set()
    for source_id, content in intake.case.source_map().items():
        if _FIXED_QUOTA.search(content):
            fixed.add(source_id)
        if _INDEPENDENT.search(content):
            independent.add(source_id)
    return fixed, independent


def _append(findings: list[DocumentFindingV08], *, code: str,
            source_ids: list[str], explanation: str,
            severity: Literal['BLOCKING', 'REVIEW'] = 'BLOCKING',
            field_path: str | None = None) -> None:
    if not any(f.code == code and f.field_path == field_path for f in findings):
        findings.append(DocumentFindingV08(
            code=code, severity=severity, source_ids=sorted(set(source_ids)),
            field_path=field_path, explanation=explanation))


def review_grounded_intake(intake: IntakeReportV07,
                           formulation: FormulationReport) -> MaterialQualityReportV08:
    """Independent post-LLM gate. The regular v0.7 audit/replay still runs."""
    base = review_intake(intake, formulation)
    findings: list[DocumentFindingV08] = []
    mode_map = {a.source_id: a.mode for a in intake.attachments}
    # Keep audit explicit: a table schema can support 'we have a T column',
    # not a complete assignment law, support proof or population operator.
    mathematically_strong_claims = [
        ('information_design.assignment_law', formulation.draft.information_design.assignment_law),
        ('information_design.population_observable_operator', formulation.draft.information_design.population_observable_operator),
        ('structure.exposure_mapping', formulation.draft.structure.exposure_mapping),
        ('structure.network_pretreatment_status', formulation.draft.structure.network_pretreatment_status),
        ('validity.support_or_positivity', formulation.draft.validity.support_or_positivity),
    ]
    for field_path, claim in mathematically_strong_claims:
        if claim.basis != 'UNRESOLVED' and claim.evidence:
            source_ids = [x.source_id for x in claim.evidence]
            # If evidence is only from data-table schema metadata, reject it
            # as sufficient support for a substantive design/theorem claim.
            if all(mode_map.get(s) == 'SCHEMA_ONLY' for s in source_ids):
                _append(findings, code='SCHEMA_METADATA_PROMOTED_TO_CAUSAL_FACT',
                        source_ids=source_ids, field_path=field_path,
                        explanation='表头和行数只证明有限样本文件结构，不能直接确认处理规则、暴露规则、支持条件或总体算子。')
    for idx, assumption in enumerate(formulation.draft.assumptions):
        if assumption.basis == 'REPORTED_BY_SOURCE' and assumption.evidence:
            source_ids = [x.source_id for x in assumption.evidence]
            if all(mode_map.get(s) == 'SCHEMA_ONLY' for s in source_ids):
                _append(findings, code='SCHEMA_METADATA_PROMOTED_TO_ASSUMPTION',
                        source_ids=source_ids, field_path=f'assumptions[{idx}]',
                        explanation='表格字段不足以证实因果假设；需其他可核对的协议或领域材料。')

    fixed, independent = _source_design_signals(intake)
    if fixed and independent and (fixed != independent or len(fixed | independent) > 1):
        _append(findings, code='POTENTIAL_ASSIGNMENT_CONFLICT',
                source_ids=list(fixed | independent),
                field_path='information_design.assignment_family',
                explanation='材料同时包含固定名额与独立分配的描述；不自动挑选其中一个，需核对真正执行的实验方案。')

    # A model omitting an explicit protocol fact is not a reason to ask the
    # business manager to repeat the file. Escalate instead to re-extraction.
    if formulation.draft.information_design.assignment_family == AssignmentFamily.UNRESOLVED and (fixed or independent):
        _append(findings, code='POSSIBLE_MISSED_ASSIGNMENT_IN_MATERIAL',
                source_ids=list(fixed | independent),
                field_path='information_design.assignment_family',
                severity='REVIEW',
                explanation='材料似乎已交代处理分配方式，但草稿未识别；先复查文档与模型抽取，不必立刻追问业务人员。')

    before = [s for s, c in intake.case.source_map().items() if _BEFORE_NETWORK.search(c)]
    after = [s for s, c in intake.case.source_map().items() if _AFTER_NETWORK.search(c)]
    if before and after:
        _append(findings, code='POTENTIAL_NETWORK_TIMING_CONFLICT',
                source_ids=list(set(before + after)), field_path='structure.network_pretreatment_status',
                explanation='网络关系的记录时间存在前后不一致的描述；需要研究者核对，不能默认网络是处理前固定的。')

    for att in intake.attachments:
        warning_codes = set(att.warnings)
        if 'POSSIBLE_PROMPT_INJECTION_QUARANTINED' in warning_codes:
            _append(findings, code='UNTRUSTED_DOCUMENT_INSTRUCTION',
                    source_ids=[att.source_id], explanation='附件包含疑似给模型的操作指令，已从模型可见摘录中隔离；原文件应由研究者核查。')
        if att.mode == 'NO_EXTRACTABLE_TEXT':
            _append(findings, code='ATTACHMENT_UNREADABLE',
                    source_ids=[att.source_id], explanation='附件无法提取文字，不得假设其中有已确认的研究设计或假设证据。')
        if {'CONTENT_TRUNCATED','PAGE_LIMIT_REACHED','SHEET_LIMIT_REACHED', 'COLUMN_LIMIT_REACHED','TABLE_ROW_SCAN_LIMIT_REACHED'} & warning_codes:
            _append(findings, code='ATTACHMENT_INCOMPLETE',
                    source_ids=[att.source_id], severity='REVIEW',
                    explanation='附件只读取了部分内容；完整文件可能包含关键限制，需核对后再形成正式规格。')

    # A document gate only classifies quality. It never calls the core and
    # cannot by itself make an unverified math input formally admissible.
    blocking = any(f.severity == 'BLOCKING' for f in findings)
    review_needed = blocking or any(f.severity == 'REVIEW' for f in findings)
    if review_needed:
        decision = 'REVIEW_DOCUMENT_CONFLICT_OR_QUALITY'
    elif base.next_action == 'ASK_ESSENTIAL_BUSINESS_QUESTION':
        decision = 'ASK_ESSENTIAL_BUSINESS_QUESTION'
    else:
        decision = 'RESEARCHER_REVIEW'
    return MaterialQualityReportV08(
        base=base, findings=findings, decision=decision,
        document_gate_passed=not blocking,
    )


def render_material_review(report: MaterialQualityReportV08) -> str:
    draft = report.base.formulation.draft
    lines = [
        'CFM-ID Gateway v0.8｜业务材料联合规范化（不是数学识别认证）',
        f'业务想回答：{draft.target.description.value or "尚需确认"}',
        f'研究对象：{draft.units_variables.analysis_unit.value or "尚需确认"}',
        f'主要措施：{draft.units_variables.treatment.value or "尚需确认"}',
        f'关心的指标：{draft.units_variables.outcome.value or "尚需确认"}',
        f'已读取材料：{len(report.base.intake.attachments)} 份',
    ]
    if report.findings:
        lines.append('需要留意的资料问题：')
        for x in report.findings:
            lines.append(f'  - {x.explanation}（{x.code}）')
    elif report.base.essential_business_questions:
        lines.append('确实需要补充的业务问题：')
        for x in report.base.essential_business_questions:
            lines.append(f'  - {x}')
    else:
        lines.append('没有发现已知的高风险材料冲突；下一步仍需研究者审核数学含义。')
    lines.append('当前只形成规范化草稿：尚无 POINT/PARTIAL 认证、没有估计销售收益。')
    return '\n'.join(lines)
