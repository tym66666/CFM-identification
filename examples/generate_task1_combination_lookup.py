"""Generate the Task-1 combination lookup table (组合查找表) reproducibly.

Runs the real SupportEngine and the four target families across every
design x exposure combination on one fixed 4-node network, then emits a
Markdown table into docs/. No hand-written status: every cell is computed.

Usage:  python -m examples.generate_task1_combination_lookup
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec,
    CompleteRandomizationDesignV1, HeterogeneousBernoulliDesignV1,
    TwoGroupFixedQuotaDesignV1, ClusterBernoulliDesignV24,
    MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1,
    CovariateBalanceRuleV1,
)
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, SupportEngine,
)
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family.exposure_extensions import (
    WeightedExposureSpec, GroupedExposureSpec)
# The four target-value functions are a verification/audit helper, NOT the
# formal identification route (that is identify() + the theorem backend).
from tests.task1_target_helpers import (
    local_direct_mean, peer_spillover_mean, policy_mean, policy_contrast)

NODES = ("a", "b", "c", "d")
EDGES = (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"))

# Design-standardized conditions only. Exposure sufficiency is a separate,
# optional interpretation upgrade, not a condition for the computed contrast.
ASSUMPTIONS = {"consistency": True, "random_assignment": True}
CORE = {"a": ("b",), "b": ("a",), "c": ("d",), "d": ("c",)}


def network() -> NetworkExposureSpec:
    return NetworkExposureSpec(network_id="lookup", node_ids=list(NODES), undirected_edges=list(EDGES))


DESIGNS = {
    "D1": HeterogeneousBernoulliDesignV1(propensities={"a": "1/3", "b": "1/2", "c": "2/3", "d": "1/4"}),
    "D2": CompleteRandomizationDesignV1(m=2),
    "D3": TwoGroupFixedQuotaDesignV1(groups=(("a", "b"), ("c", "d")), treated_quotas=(1, 1)),
    "D4": ClusterBernoulliDesignV24(clusters=(("a", "b"), ("c", "d")), cluster_probabilities=("1/3", "1/2")),
    "D5": MultiGroupFixedQuotaDesignV25(groups=(("a",), ("b", "c"), ("d",)), treated_quotas=(1, 1, 1)),
    "D6": TwoStageQuotaMixtureDesignV27(
        groups=(("a", "b"), ("c", "d")), quota_profiles=((1, 1), (0, 2)), profile_probabilities=("1/3", "2/3")),
    "D7": UnequalProbabilityFixedQuotaDesignV1(
        nodes=NODES, m=2,
        treated_sets=(("a", "b"), ("a", "c"), ("c", "d")), set_probabilities=("1/2", "1/4", "1/4")),
    "D8": RerandomizedBalancedDesignV1(
        base_design=UnequalProbabilityFixedQuotaDesignV1(
            nodes=NODES, m=2,
            treated_sets=(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d"), ("b", "c")),
            set_probabilities=("1/6", "1/6", "1/6", "1/6", "1/6", "1/6")),
        balance_rule=CovariateBalanceRuleV1(
            tolerance="1/2", covariates={"x": {"a": "0", "b": "0", "c": "1", "d": "1"}})),
}

DESIGN_TEXT = {
    "D1": "独立 Bernoulli：p=(a:1/3, b:1/2, c:2/3, d:1/4)",
    "D2": "固定总配额 m=2（均匀）",
    "D3": "两组固定配额：{a,b}:1, {c,d}:1",
    "D4": "簇 Bernoulli：{a,b}:1/3, {c,d}:1/2",
    "D5": "多组固定配额：{a}:1, {b,c}:1, {d}:1",
    "D6": "两阶段配额混合：profiles (1,1):1/3, (0,2):2/3",
    "D7": "不等概率固定配额 m=2：{a,b}:1/2, {a,c}:1/4, {c,d}:1/4",
    "D8": "重随机化平衡：均匀 base m=2 + 协变量 x 均值差 ≤ 1/2",
}

EXPOSURES = {
    "E1": ExposureSpec("strict_majority_ties_low"),
    "E2": ExposureSpec("three_level_treated_neighbor_fraction"),
    "E3": ExposureSpec("pretreatment_core_collaborator_majority", core_collaborators=dict(CORE)),
    "E4": ExposureSpec("exact_treated_neighbor_count"),
    "E5": ExposureSpec("any_treated_neighbor"),
    "W": WeightedExposureSpec(weights={"b": "1", "c": "2"}, mode="sum"),
    "G": GroupedExposureSpec(groups={"g1": ("b",), "g2": ("c",)}),
}

EXPOSURE_TEXT = {
    "E1": "严格多数（平票=0）",
    "E2": "邻居比例三档",
    "E3": "核心合作者多数",
    "E4": "精确处理邻居数",
    "E5": "任一处理邻居",
    "W": "加权暴露（和，w_b=1,w_c=2）",
    "G": "分组暴露（g1={b}, g2={c}，元组按 g1,g2 顺序）",
}


class CompleteOutcomes(dict):
    """Provide a well-defined potential response for any (node, a, s) cell so
    the target families isolate support-based blocking from missing outcomes."""

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        _, a, s = key
        base = 5 if a else 1
        if isinstance(s, tuple):
            return base + Fraction(sum(s))
        if isinstance(s, Fraction):
            return base + s
        return base + Fraction(s)


def _fmt_state(s) -> str:
    if isinstance(s, Fraction):
        return str(s)
    if isinstance(s, tuple):
        return "(" + ",".join(map(str, s)) + ")"
    return str(s)


def support_cell(joint: dict) -> str:
    if not joint:
        return "∅"
    by_a: dict = {}
    for (a, s), p in joint.items():
        if p:
            by_a.setdefault(a, []).append(f"{_fmt_state(s)}")
    parts = []
    for a in sorted(by_a):
        parts.append(f"a={a}:{{{','.join(sorted(by_a[a], key=repr))}}}")
    return "; ".join(parts)


def status_cell(result) -> str:
    if result.status == "POINT":
        return f"POINT ({result.value})"
    # compact blocking reason: strip node-specific noise, keep the first cause
    return f"UNSUP ({result.reason.split(' for ')[0]})"


def build_support_matrix():
    rows = []
    for dlabel, design in DESIGNS.items():
        cells = []
        for elabel, exposure in EXPOSURES.items():
            try:
                joint = SupportEngine.joint_support(
                    network=network(), assignment=AssignmentSpec(design),
                    exposure=exposure, node_id="a")
                cells.append(support_cell(joint))
            except Exception as exc:  # resource limit / undefined isolate etc.
                cells.append(f"ERR ({type(exc).__name__})")
        rows.append((dlabel, cells))
    return rows


def _node_a_states(design, exposure):
    """Positive-support exposure states at node 'a', split by own treatment."""
    joint = SupportEngine.joint_support(
        network=network(), assignment=AssignmentSpec(design), exposure=exposure, node_id="a")
    states0 = sorted({s for (a, s), p in joint.items() if a == 0 and p}, key=repr)
    states1 = sorted({s for (a, s), p in joint.items() if a == 1 and p}, key=repr)
    return states0, states1


def build_target_matrix(target):
    """target is one of local_direct_mean / peer_spillover_mean.

    Uses a VALID exposure coordinate per exposure type — a grouped tuple of
    counts, an exact rational weighted value, or an integer E1-E5 state — never
    a single 0/1 for a grouped tuple axis. Queries node ``a`` and reports the
    node-a design-standardized contrast.
    """
    rows = []
    for dlabel, design in DESIGNS.items():
        cells = []
        for elabel, exposure in EXPOSURES.items():
            try:
                states0, states1 = _node_a_states(design, exposure)
                if target is local_direct_mean:
                    common = [s for s in states0 if s in states1]
                    if not common:
                        cells.append("UNSUP (no common (a=0,a=1) coordinate at node a)")
                        continue
                    result = local_direct_mean(
                        network=network(), design=design, exposure=exposure,
                        outcomes=CompleteOutcomes(), exposure_state=common[0],
                        assumptions=ASSUMPTIONS, population=["a"])
                else:
                    if len(states0) < 2:
                        cells.append("UNSUP (<2 peer coordinates at node a)")
                        continue
                    result = peer_spillover_mean(
                        network=network(), design=design, exposure=exposure,
                        outcomes=CompleteOutcomes(), own_treatment_value=0,
                        exposed_state=states0[-1], reference_state=states0[0],
                        assumptions=ASSUMPTIONS, population=["a"])
                cells.append(status_cell(result))
            except Exception as exc:
                cells.append(f"ERR ({type(exc).__name__})")
        rows.append((dlabel, cells))
    return rows


def build_policy_rows():
    rows = []
    for dlabel, design in DESIGNS.items():
        def outcomes(treated):
            return Fraction(2 * len(treated))
        mean = policy_mean(network=network(), design=design, outcomes=outcomes, assumptions=ASSUMPTIONS)
        contrast = policy_contrast(
            network=network(), design_a=design, design_b=DESIGNS["D2"],
            outcomes=outcomes, assumptions=ASSUMPTIONS)
        rows.append((dlabel, status_cell(mean), status_cell(contrast)))
    return rows


def key_lookup_checks():
    """关键查找：概率和为1、不可能情形=0、条件概率正确。用 D7 x E1 核对节点 a。"""
    design = DESIGNS["D7"]
    exposure = EXPOSURES["E1"]
    joint = SupportEngine.joint_support(
        network=network(), assignment=AssignmentSpec(design), exposure=exposure, node_id="a")
    total = sum(joint.values(), Fraction(0))
    cond = SupportEngine.conditional_exposure(joint_support=joint, own_treatment_value=1)
    return {
        "sum_to_one": total == 1,
        "all_nonneg": all(p >= 0 for p in joint.values()),
        "conditional_normalized": sum(cond.values(), Fraction(0)) == 1,
        "joint_a1": str(joint.get((1, 0), Fraction(0))),
    }


def render() -> str:
    net = network()
    lines = []
    add = lines.append
    add("# Task 1 组合查找表（网络拓展 / POINT 拓展）")
    add("")
    add("> 本表由 `examples/generate_task1_combination_lookup.py` 自动生成，逐格运行真实")
    add("> `SupportEngine` 与四类目标，可复现。固定小网络：`N=4` 节点 `{a,b,c,d}`，")
    add("> 边 `(a,b),(a,c),(b,d),(c,d)`；支持矩阵取节点 `a`（degree=2）。")
    add("")
    add("## 设计参数")
    add("")
    for label, text in DESIGN_TEXT.items():
        add(f"- **{label}** — {text}")
    add("")
    add("## 暴露参数")
    add("")
    for label, text in EXPOSURE_TEXT.items():
        add(f"- **{label}** — {text}")
    add("")

    add("## 表 1 · 联合支持矩阵（节点 a 的正支持 (a,s) 状态）")
    add("")
    header = "| 设计 \\ 暴露 | " + " | ".join(EXPOSURES) + " |"
    add(header)
    add("|---|" + "---|" * len(EXPOSURES))
    for dlabel, cells in build_support_matrix():
        add(f"| **{dlabel}** | " + " | ".join(cells) + " |")
    add("")

    add("## 表 2 · 四类目标接入矩阵（节点 a，按原设计平均）")
    add("")
    add("**条件与结论分开**：以下数值是**按原设计平均的效应**（design-standardized），只需")
    add("`random_assignment` + `consistency` + 目标 arm 正支持；**不**以暴露充分性为前提。")
    add("若另**额外采用暴露充分性**，同一数值可升级为「暴露的因果效应」解释")
    add("（`causal_effect_under_exposure_sufficiency`），但那是更强的解释层，不改变本表数值，")
    add("也不是本表成立的条件。未单独标注时本表即 `design_standardized_contrast`。")
    add("")
    add("坐标按暴露类型取**合法状态**：E1–E5 为整数；W 为精确有理加权值；G 为**成组计数元组**")
    add("（如 `(1,0)`、`(0,1)`），**不**统一用单个 0/1。`POINT` 给出该坐标下的符号值，")
    add("`UNSUP` 记录正支持缺失或条件未确认。")
    add("")
    for title, target in (
        ("### 2a · local_direct_mean（固定一个合法 s 坐标，比较 a=1 减 a=0）", local_direct_mean),
        ("### 2b · peer_spillover_mean（own=0，比较高坐标减低坐标）", peer_spillover_mean),
    ):
        add(title)
        add("")
        add(header)
        add("|---|" + "---|" * len(EXPOSURES))
        for dlabel, cells in build_target_matrix(target):
            add(f"| **{dlabel}** | " + " | ".join(cells) + " |")
        add("")

    add("### 2c · policy_mean 与 policy_contrast（仅设计维度）")
    add("")
    add("政策值/两政策差值同样是**按原设计（完整分配律）平均**的 `design_standardized_policy_value`，")
    add("不涉及暴露映射或暴露充分性。")
    add("")
    add("| 设计 | policy_mean (E[2|A|]) | policy_contrast (vs D2) |")
    add("|---|---|---|")
    for dlabel, mean, contrast in build_policy_rows():
        add(f"| **{dlabel}** | {mean} | {contrast} |")
    add("")

    add("## 关键查找验证（D7 × E1，节点 a）")
    add("")
    checks = key_lookup_checks()
    add(f"- 单位概率之和为 1：`{'是' if checks['sum_to_one'] else '否'}`")
    add(f"- 所有概率非负：`{'是' if checks['all_nonneg'] else '否'}`")
    add(f"- 条件概率 P(S|T=1) 归一为 1：`{'是' if checks['conditional_normalized'] else '否'}`")
    add(f"- 例：P(T_a=1, S_a=0) = `{checks['joint_a1']}`")
    add("")
    add("> 说明：加权/分组暴露（W/G）在证书后端属明确缺项（见缺项表），其 POINT 识别由内部精确")
    add("> 枚举层 `randomized_arm_family` 提供，本表表 1 已记录其正支持状态。表 2a/2b 统一用整数")
    add("> 状态 0/1 查询目标，对 W（加权和）有意义，对 G（元组状态）无对应状态故记为 UNSUP；")
    add("> W/G 的四类目标接入见内部层测试 `tests/test_task1_targets.py`。新设计（D7/D8）精确支持")
    add("> 为全排列枚举，N≤8。")
    add("")
    return "\n".join(lines)


def main():
    out = Path(__file__).resolve().parents[1] / "docs" / "task1_combination_lookup.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
