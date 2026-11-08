"""Display recomputed schedule facts separately from unverified model prose."""
from .witness_schedule import inspect_two_worlds

LABELS = {
    "PASSED_EXACT_CONSTRUCTION": "具体反例附件通过精确核查",
    "OBSERVABLE_LAWS_DIFFER": "反例未通过：可观测结果不同",
    "TARGETS_EQUAL": "反例未通过：目标值相同",
    "NO_ARTIFACT": "未提供结构化反例",
    "UNSUPPORTED_SCOPE": "检查器不支持该科学条件或候选范围",
    "INVALID_INPUT": "附件或输入超出当前检查器的表示范围，不能据此直接判数学错误",
    "INVALID_ARTIFACT": "附件格式或维度不合法",
    "BINDING_MISMATCH": "附件节点顺序或目标维度不一致",
}


def render_zh(report, *, math_by_query, review_notes=None):
    lines = ["业务识别与反例附件核查", "这是合成实验，科学前提不是现实企业的自动批准条件。", ""]
    candidates = {r["query_id"]: r for r in report["candidate_results"]}
    for row in report["identification"]["results"]:
        qid = row["query_id"]
        lines.append("问题：" + qid)
        lines.append("Core 原结果：" + row["status"])
        r = candidates.get(qid)
        env = report.get("candidate_envelopes", {}).get(qid)
        if r is None or env is None or r["status"] not in ("UNVERIFIED_CANDIDATE","UNDETERMINED_UNVERIFIED"):
            lines.extend(["没有通过候选合同检查的模型输出。",""])
            continue
        c = env["candidate"]
        lines.extend(["业务目标：" + c["proposal"]["target_description"],
                      "模型主张：" + c["proposal"]["claimed_identification"] + "（未认证）"])
        # Never trust a saved PASSED status or a hand-edited displayed target.
        d = inspect_two_worlds(math_by_query[qid], c, env["two_world_schedule"])
        lines.append("附件核查：" + LABELS.get(d["status"], d["status"]))
        if d["status"] == "PASSED_EXACT_CONSTRUCTION":
            lines.extend([
                f"已逐一核对 {d['assignments_checked']} 种正概率分配，概率之和为 {d['support_probability_sum']}；每种分配的全部节点观测结果在两世界中一致。",
                f"按原目标和权重计算，虚构世界 A 的目标值为 {d['theta_a']}，世界 B 为 {d['theta_b']}。这些是反例数字，不是业务效果估计。",
                "支持集和目标值在本地重新计算，没有修改模型给出的结果表。",
            ])
            w = env["two_world_schedule"]
            equal = w["world_a"]["default_outcomes"] == w["world_b"]["default_outcomes"]
            lines.append("附件中的默认结果向量：" + ("逐项相同。" if equal else "不相同；必须结合覆盖项判断实际可观测结果，不能直接据默认值判定观测等价。"))
        if review_notes and qid in review_notes:
            lines.append("原文审查记录：")
            lines.extend("- " + note for note in review_notes[qid])
        lines.extend(["说明：附件核查未认证模型全文，也没有新增 Core 证书。Estimation/Policy 不接收这份候选。", ""])
    return "\n".join(lines) + "\n"

