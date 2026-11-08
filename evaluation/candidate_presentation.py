"""Plain-text presentation keeps certified Core results separate from LLM claims."""
import argparse
import json
from pathlib import Path
from cfm_id_llm.candidate_queries import CandidateQueryReportV011

CLAIMS = {"POINT": "模型提出可点识别（未验证）", "PARTIAL": "模型提出可部分识别（未验证）",
          "NOT_POINT": "模型提出非点识别（未验证）", "UNDETERMINED": "模型暂不能确定"}
STATUS = {"UNSUPPORTED": "当前识别库未覆盖，尚无认证结论",
          "NEEDS_INPUT": "需要补充或澄清条件", "REJECTED": "输入未通过检查"}


def render_zh(report):
    lines = ["业务识别与探索建议", "本结果来自合成实验。科学条件是假定的测试前提，不是现实企业的已批准条件。", ""]
    entries = {r["query_id"]: CandidateQueryReportV011.model_validate(r)
               for r in report.get("candidate_results", [])}
    for row in report["identification"].get("results", []):
        qid = row["query_id"]
        lines.append("问题 " + qid)
        c = entries.get(qid)
        if c and c.candidate:
            lines.append("业务问题：" + c.candidate.proposal.target_description)
        target = row.get("proposed_target", {})
        if target.get("nodes"):
            lines.append("评价范围：" + str(len(target["nodes"])) + " 个单位" +
                         ("，等权平均。" if target.get("aggregation") == "equal_mean" else "。"))
        state = row["status"]
        if state == "POINT":
            text = "在声明的条件下点识别，Core 证书已重放" if row.get("certificate_replay") is True else "POINT 声明尚无重放确认"
        else:
            text = STATUS.get(state, state)
        lines.append("Core 结果：" + text)
        if c is None:
            lines.append("探索建议：本查询未调用候选模型。")
            lines.append("")
            continue
        lines.extend(["", "LLM 探索建议：未验证，不构成识别证明，不可直接用于估计或政策执行。", "候选处理状态：" + c.status])
        if c.candidate is None:
            lines.append("原因：" + c.reason_code)
            continue
        p = c.candidate.proposal
        lines.append("模型判断：" + CLAIMS[p.claimed_identification])
        lines.append("适用范围：" + ("仅在追加条件成立时" if p.scope == "IF_ADDITIONAL_REQUIREMENTS" else "基于已声明条件"))
        if p.candidate_expression:
            lines.extend(["候选表达式（未验证）：", p.candidate_expression])
        if p.nonidentification_witness:
            w = p.nonidentification_witness
            lines.extend(["反例构想（未验证）：", "世界一：" + w.world_a, "世界二：" + w.world_b,
                          "观测相同的理由：" + w.why_observables_match, "目标不同的理由：" + w.why_targets_differ])
        if p.additional_requirements:
            lines.append("模型建议追加的条件（尚未批准）：")
            lines.extend("- " + x.description + "；理由：" + x.why_needed for x in p.additional_requirements)
        lines.append("模型给出的分析：")
        lines.extend("- " + x for x in p.reasoning_steps)
        lines.append("待核查事项：")
        lines.extend("- " + x for x in c.candidate.proposed_validation_checks)
        lines.append("")
    if not report["identification"].get("results"):
        lines.append("Core 状态：" + report["identification"]["status"])
    lines.extend(["", "说明：软件检查通过只表示格式、目标绑定和许可边界通过，不表示候选推导正确。",
                  "LLM 候选没有增加 Core 已认证查询数。未调用 Estimation 或 Policy。"])
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    text = render_zh(json.loads(args.input.read_text(encoding="utf8")))
    with args.output.open("x", encoding="utf8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
