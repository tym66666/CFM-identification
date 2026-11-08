"""Human explanation of *draft* semantics, never proof or estimates."""
from __future__ import annotations
from .schemas import FormulationReport, SemanticClaim


def _show(claim: SemanticClaim) -> str:
    if claim.value is None:
        return "未确定 / unresolved"
    return f"{claim.value} [{claim.basis}]"


def render_text(report: FormulationReport) -> str:
    d = report.draft
    parts = [
        f"CFM-ID LLM Gateway v{report.gateway_version} | {report.case_id}",
        "仅为 LLM 规范化草稿：未运行识别定理、未验证因果识别、未估计数值。",
        f"审查状态: {report.review_status} | 输入指纹: {report.input_sha256[:16]}…",
        "",
        f"A1 Target: {d.target.kind.value} — {_show(d.target.description)}",
        f"A2 Units: {_show(d.units_variables.analysis_unit)}",
        f"   Treatment: {_show(d.units_variables.treatment)}",
        f"   Outcome: {_show(d.units_variables.outcome)}",
        f"A3 Unit network: {_show(d.structure.unit_network)}",
        f"   Variable DAG: {_show(d.structure.variable_causal_graph)}",
        f"   Exposure: {_show(d.structure.exposure_mapping)}",
        f"A4 Assignment: {d.information_design.assignment_family.value} — {_show(d.information_design.assignment_law)}",
        f"   Population operator: {d.information_design.population_information_level.value} — {_show(d.information_design.population_observable_operator)}",
        "A5 Assumptions (all unadmitted LLM proposals):",
    ]
    for a in d.assumptions:
        parts.append(f"   - {a.name}: {a.status} ({a.basis})")
    if not d.assumptions:
        parts.append("   - 未提取 / none")
    parts.append(f"A6 Support/domain: {_show(d.validity.support_or_positivity)} / {_show(d.validity.query_domain)}")
    if report.issues:
        parts.append("\n待审查问题：")
        for issue in report.issues:
            parts.append(f"  - [{issue.severity}] {issue.code}: {issue.detail}")
    if report.suggested_questions:
        parts.append("\n优先澄清问题：")
        for i, q in enumerate(report.suggested_questions, 1):
            parts.append(f"  {i}. [{q.priority}] {q.question}")
    parts.append("\n认证状态: NOT_PERFORMED | Estimation Handoff: DISALLOWED")
    return "\n".join(parts)


def render_routing_text(formulation: FormulationReport, route) -> str:
    """Compact human-readable summary; intentionally no claim of math beyond receipt."""
    labels = {
        "NEEDS_CLARIFICATION": "业务信息仍不够明确",
        "AWAITING_HUMAN_REVIEW": "等待研究者确认数学问题",
        "NO_CORE_CONNECTED": "还没有连接严格识别库",
        "MOCK_CORE_RESULT": "仅模拟识别库的分流",
        "CORE_VERIFIED": "严格识别库已验证（需可信正式适配器）",
        "CORE_NEEDS_INPUT": "严格识别库要求补充信息",
        "CORE_UNSUPPORTED": "当前严格库没有对应定理",
        "CORE_NO_ADAPTER": "缺少规格转换适配器",
        "CORE_INCOMPATIBLE": "输入与识别要求有冲突",
        "CORE_ERROR": "识别库执行异常",
        "CORE_VERIFICATION_FAILED": "独立数学重放没有通过",
        "CORE_BINDING_FAILED": "识别结果不是针对这份问题",
    }
    lines = [
        f"CFM-ID LLM Gateway v0.2 | {route.case_id}",
        f"处理结果：{labels.get(route.status, route.status)} [{route.status}]",
        f"说明：{route.explanation}",
        f"认证级别：{route.verification_level}",
        f"后续 LLM 候选推理：{route.fallback}（v0.2 尚未实现自动推理）",
        "有限样本 Estimation：未放行",
    ]
    if route.core_status:
        lines.append(f"识别库报告状态：{route.core_status}")
    if route.core_route:
        lines.append(f"声称的定理路线：{route.core_route}")
    if route.core_expression:
        lines.append(f"识别表达式（必须结合认证级别阅读）：{route.core_expression}")
    if route.next_steps:
        lines.append("下一步：")
        lines.extend(f"  - {step}" for step in route.next_steps)
    return "\n".join(lines)
