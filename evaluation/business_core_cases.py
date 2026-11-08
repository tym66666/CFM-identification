"""Versioned synthetic revisions; reference targets are NEVER sent to the LLM."""
from copy import deepcopy
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/business_core_assets"
LICENSES = ("本轮只做合成理论练习：假定抽签规则已知，抽签与所有潜在结果独立，"
            "处理和结果按同一口径定义，实际结果对应实际分配；网络在试验前固定，结果均值有限。")
POPULATION = ("另外假定我们知道在上述试验中，各种有可能抽出的完整名单下，每个对象的总体结果分布。"
              "这是另外给定的理论信息，不是把一次试点的样本均值当总体均值。")
REMAINING = "上述情形中没指定的其他人怎么分配，仍按原抽签规则在这些条件下的概率计算平均。"


def study(n, graph, design, exposure, outcome, quota=None):
    return dict(units=n, graph=graph, center="01" if graph == "star" else None,
                design=design, probability="1/2" if design == "independent" else None,
                quota=quota, exposure=exposure, outcome=outcome)


def target(kind, nodes, aggregation, pop, question, situation=None, reference=None,
           treated=None, plan=None):
    return dict(question_quote=question, kind=kind, nodes=nodes, aggregation=aggregation,
                population_quote=pop, situation=situation, reference=reference,
                remaining="original_randomization" if kind in ("arm", "comparison") else None,
                remaining_quote=REMAINING if kind in ("arm", "comparison") else None,
                treated_nodes=treated, plan_quote=plan, unresolved=[])


def state(a, e, quote):
    return dict(own=a, peers=e, quote=quote)


def fixtures():
    cases = []

    def add(case_id, original, d, graph, design, exposure, prefix, questions, targets,
            changes, suff=None):
        public = prefix + graph + design + exposure + "".join(questions)
        public += LICENSES + POPULATION
        if suff:
            public += suff
        packet = dict(mode="SYNTHETIC_BENCHMARK_ONLY", study=d,
                      science=dict(causal_licenses=LICENSES, population_information=POPULATION,
                                   mean_signature_sufficiency=suff))
        raw = dict(study={**d, "graph_quote": graph, "design_quote": design, "exposure_quote": exposure},
                   targets=targets)
        cases.append(dict(case_id=case_id, original_case_id=original, business_question=public,
                          packet=packet, offline_reference_draft=raw, revision_notes=changes))

    nodes80 = [f"{i:02d}" for i in range(1, 81)]
    q1 = "第一个问题：邻居中超过一半有AI权限时，自己有AI权限比自己没有AI权限，每周销售额平均多多少？"
    q2 = "第二个问题：自己都没有AI权限时，邻居中超过一半有权限，比邻居中至多一半有权限，每周销售额平均多多少？"
    pop = "两个问题都对试验前登记的80位经理逐人计算，再等权平均，不按实际中奖名单选人。"
    add("NBIB-001-R20", "NBIB-001", study(80, "ring", "independent", "strict_majority", "每周销售额"),
        "合作关系在试验前已经固定：80人依次首尾相接成环，每人只与前后两位合作。",
        "每人独立抽签，以1/2的概率获得AI权限，抽中人数不固定。",
        "邻居中获得AI权限的人超过一半算高使用环境，至多一半算低使用环境。",
        "我们有80位客户经理，编号01到80，记录的结果是每周销售额。",
        [q1, q2, pop, REMAINING],
        [target("comparison", nodes80, "equal_mean", pop, q1, state(1, 1, q1), state(0, 1, q1)),
         target("comparison", nodes80, "equal_mean", pop, q2, state(0, 1, q2), state(0, 0, q2))],
        ["保留直接和溢出两类目标；明确比较方向、邻居状态、固定评价人群与等权平均。",
         "本合成版本把原来的分岗位概率改为各1/2，并新增固定环网和独立总体信息；不能当原题成绩。"])

    q = "只看预先指定的01站：如果它自己使用系统，且恰好一个相邻站点使用系统，它的平均延误是多少？"
    add("NBIB-002-R20", "NBIB-002", study(48, "ring", "fixed_count", "exact_treated_neighbor_count", "平均延误", 24),
        "试验前固定的支援关系是48站按编号首尾相接成环，每站只支援前后两站。",
        "在48站中均匀抽出恰好24站使用系统，每一种24站名单的机会相同。",
        "邻居使用状态按相邻站点中使用系统的站点数逐个计数，不把一个和两个合并。",
        "我们有48个配送站，编号01到48，试用排班系统，结果指标是平均延误。",
        [q, REMAINING.replace("其他人", "其他人")],
        [target("arm", ["01"], "single", "只看预先指定的01站", q, state(1, 1, q))],
        ["保留固定24/48与恰好一个邻居的目标；把“某站”明确为01站，补充固定环网和独立总体信息。"])

    suff = ("这道合成练习额外明确接受一个限制：每家店的收入均值只依赖本店是否安装、"
            "以及邻店中是否至少一家安装；其余具体名单不再影响收入均值。"
            "并另行给定各店所需的上述状态总体均值。这是本题的额外假设，不是数据证明的结论。")
    for original in ("NBIB-007", "NBIB-008", "NBIB-009"):
        is_staff = original == "NBIB-007"
        outcome = "交付质量" if is_staff else "季度收入"
        graph = ("试验前固定的合作关系是14人按编号首尾相接成环，每人只与前后两位合作。" if is_staff else
                 "试验前固定的互荐关系是01旗舰店与其余13店相连，其余门店之间没有直接互荐。")
        design = ("每名员工独立抽签，以1/2的概率开通平台，抽中人数不固定。" if is_staff else
                  "在14店中均匀抽出恰好7店安装系统，每一种7店名单的机会相同。")
        exp = ("合作邻居中至少一人开通就记为有邻居采用，否则记为无邻居采用。" if is_staff else
               "互荐邻居中至少一家安装就记为有邻居采用，否则记为无邻居采用。")
        pop = "按试验前登记的14名员工等权平均" if is_staff else "按试验前登记的14家店等权平均"
        plan = "让14名员工全部开通平台" if is_staff else "让14家店全部安装系统"
        q = f"我们现在只问：如果{plan}，{pop}，{outcome}会是多少？"
        add(original + "-R20", original,
            study(14, "ring" if is_staff else "star", "independent" if is_staff else "fixed_count",
                  "any_treated_neighbor", outcome, None if is_staff else 7),
            graph, design, exp,
            ("我们有14名员工，编号01到14，试用协作平台，结果指标是交付质量。" if is_staff else
             "我们有14家店，编号01到14，试用推荐系统，结果指标是季度收入。"),
            [q], [target("fixed_plan", [f"{i:02d}" for i in range(1, 15)], "equal_mean", pop, q,
                         treated=[f"{i:02d}" for i in range(1, 15)], plan=plan)],
            ["保留全员推广目标；明确目标为固定背景下同一批对象的等权平均水平，不输出数值估计。",
             "008/009由原来的总收入改为平均季度收入，007删除模糊的“如何变化”以免默补对照；这是目标澄清/范围变更。",
             "新增明确合成总体信息；009另有单独的均值充分性声明，008没有。"],
            suff if original == "NBIB-009" else None)

    # Pre-registered target perturbation: same study, genuinely different natural question.
    base = deepcopy(next(c for c in cases if c["case_id"] == "NBIB-007-R20"))
    base["case_id"] = "NBIB-007-R20-PARTIAL"
    old = "让14名员工全部开通平台"
    new = "只给01和02两名员工开通平台，其余12人都不开通"
    base["business_question"] = base["business_question"].replace(old, new)
    t = base["offline_reference_draft"]["targets"][0]
    t["question_quote"] = t["question_quote"].replace(old, new)
    t["plan_quote"] = new
    t["treated_nodes"] = ["01", "02"]
    base["revision_notes"] = ["诊断性目标扰动：同一研究条件，比较模型能否区分全员推广和仅指定两人；不是第六个独立业务。"]
    cases.append(base)
    return cases


def write_assets():
    ASSETS.mkdir(exist_ok=True)
    rows = fixtures()
    outputs = {
        "public_cases.json": [{k: r[k] for k in ("case_id", "original_case_id", "business_question", "revision_notes")} for r in rows],
        "synthetic_science_packets.json": {r["case_id"]: r["packet"] for r in rows},
        "offline_reference_drafts.json": {r["case_id"]: r["offline_reference_draft"] for r in rows},
    }
    for filename, data in outputs.items():
        (ASSETS / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


if __name__ == "__main__":
    write_assets()
