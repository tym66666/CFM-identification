"""Human-readable representation for v0.3. Unverified is stated at every outcome."""
from __future__ import annotations
from .candidate_schemas import CandidateReportV03
from .orchestration_schemas import OrchestrationReportV02


def render_candidate_text(routing: OrchestrationReportV02, report: CandidateReportV03 | None) -> str:
    lines = [
        f"CFM-ID LLM Gateway v0.3 | {routing.case_id}",
        f"严格识别库的分流：{routing.status} | {routing.core_status or '未返回数学状态'}",
        f"严格识别库解释：{routing.explanation}",
        "提示：当前 Gateway 不会向 Estimation/Policy 交付 LLM 结果。",
    ]
    if report is None:
        lines.append("候选推理：未触发（不符合回退条件，或没有启用候选 Provider）。")
        return "\n".join(lines)
    lines.extend([
        f"候选推理：{report.status} | {report.execution_mode}",
        "候选认证级别：LLM_UNVERIFIED（不是数学证明，不是有效估计结果）",
        f"解释：{report.explanation}",
    ])
    if report.execution_mode == "MOCK_PREVIEW":
        lines.append("注意：识别库是模拟的；无法据此判断真实 Identification Library 的覆盖范围。")
    if report.issues:
        lines.extend(f"拒绝原因：{x.code} — {x.detail}" for x in report.issues)
    if report.candidate:
        d = report.candidate
        lines.extend([
            f"原目标：{d.target_kind.value} — {d.target_description}",
            f"LLM 的候选判断：{d.claimed_identification}（{d.scope}）",
            f"A4 信息依据：{d.a4_used.source} / {d.a4_used.level.value if d.a4_used.level else '无'}",
        ])
        if d.admitted_assumptions_used:
            lines.append("实际引用的已接受 A5：" + ", ".join(d.admitted_assumptions_used))
        if d.additional_requirements:
            lines.append("若要采用该候选，还需要补充（目前没有获得确认）：")
            lines.extend(f" - {x.kind}: {x.description}" for x in d.additional_requirements)
        if d.candidate_expression:
            lines.append("候选公式 / 集合（未认证）：" + d.candidate_expression)
        if d.nonidentification_witness:
            w = d.nonidentification_witness
            lines.append("候选非点识别反例（未认证）：")
            lines.append(f" - 世界 A：{w.world_a}")
            lines.append(f" - 世界 B：{w.world_b}")
            lines.append(f" - 可观测相同的理由：{w.why_observables_match}")
            lines.append(f" - 目标不同的理由：{w.why_targets_differ}")
        lines.append("候选推导：")
        lines.extend(f" - {step}" for step in d.reasoning_steps)
        if d.suggested_checks:
            lines.append("建议人工/程序核查：")
            lines.extend(f" - {step}" for step in d.suggested_checks)
    lines.append("Estimation Handoff：禁止。")
    return "\n".join(lines)
