"""Run LIT-NET-02 through the existing network design/exposure entry.

The public case is a two-group, two-stage vaccine design adapted from
Hudgens-Halloran (2008). This is an explicit synthetic run, not an LLM reading.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from cfm_id_llm.schemas import BusinessCase, SourceDocument
from examples import network_design_exposure_reference as ref


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-02"
OUT = ROOT / "evaluation" / "literature_cases" / "research_only" / "LIT-NET-02" / "structured_runs"

NODES = [f"甲{i}" for i in range(1, 5)] + [f"乙{i}" for i in range(1, 5)]
EDGES = [list(e) for g in (NODES[:4], NODES[4:]) for e in itertools.combinations(g, 2)]
GROUPS = [NODES[:4], NODES[4:]]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def patch_module() -> None:
    ref.NODES = list(NODES)
    ref.EDGES = [list(e) for e in EDGES]
    ref.GROUPS = [list(g) for g in GROUPS]
    ref.DESIGNS["D6"] = dict(
        kind="TWO_STAGE_QUOTA_MIXTURE",
        probabilities=None,
        fixed_count=None,
        groups=[list(g) for g in GROUPS],
        quota_profiles=[[1, 3], [3, 1]],
        profile_probabilities=["1/2", "1/2"],
    )
    ref.DESIGN_TEXT["D6"] = (
        "先抛公平硬币：正面时甲组接种1人、乙组接种3人；反面时甲组接种3人、乙组接种1人。"
        "两个名额方案各1/2概率。给定方案后，各组从组内所有同样大小名单中等概率抽取，两组独立。"
    )
    ref.EXPOSURES["E4"] = (
        "EXACT_TREATED_NEIGHBOR_COUNT",
        3,
        "同伴状态是同组邻居中实际接种的人数，取精确人数。",
        "同组其他三人全部接种",
        "同组只有一人接种",
    )


def vaccine_docs(*, missing_first_stage: bool) -> dict:
    docs = {
        "study": (
            "两个居民小组，甲组甲1甲2甲3甲4，乙组乙1乙2乙3乙4。"
            "接种本次疫苗记1，接受安慰剂记0；结果为随访一年内是否感染，感染记1，未感染记0。"
            "结果评价期间为随访的一年，两端保持相同。"
        ),
        "network": (
            "关系在随机分配前固定，为无向网络、无自身联系。"
            "甲组内部为完全图，乙组内部为完全图，组间没有边；没有其他边。"
        ),
        "assignment": (
            "先抛公平硬币决定两组名额：正面时甲组接种1人、乙组接种3人；"
            "反面时甲组接种3人、乙组接种1人。两个方案各1/2概率。"
            "给定方案后，各组从组内所有同样大小名单中等概率抽取，两组独立。"
        ),
        "population": "评价名单在随机分配前固定为全部8人，逐人比较后等权平均，不按实际处理或结果筛选。",
        "context": "结果评价期间为随访的一年，两端保持相同；没有另行指定的背景分层或条件筛选。",
        "remaining": "每个比较端只固定本人处理和题目要求的同伴接种人数，其余完整安排按原两阶段随机规则在该端条件下平均。",
        "science": (
            "拟采用：完整随机安排与所有对象在各种完整安排下的潜在结果独立；"
            "实际观察结果对应实际完整安排；所需平均结果存在且有限；"
            "组内可以有干扰，不同组之间没有干扰；所需暴露条件具有正支持。"
        ),
        "exposure": "同伴状态是同组邻居中实际接种的人数，取精确人数，不分成过半或至少一人。",
        "information": (
            "在理论识别层面允许使用完整名单内每人的总体条件感染概率："
            "本人未接种且接种邻居恰好3人，以及本人未接种且接种邻居恰好1人。"
            "这些是符号总体平均结果算子，没有提供具体数值。"
        ),
    }
    if not missing_first_stage:
        docs["first_stage"] = (
            "拟采用：最终完整接种名单相同时，第一阶段抽到哪个名额方案不再直接影响感染结果；"
            "名额通知本身不另带来宣传或行为干预。"
        )
    return docs


def question(variant: str) -> str:
    if variant == "changed_target":
        return (
            "一个人自己没有接种时，同组只有1人接种，相比同组其他3人都接种，"
            "他的感染概率会怎样变化？按“一人接种减三人接种”计算。"
            "评价名单是全部8位居民，每人同等权重；其余安排按原两阶段抽签规则条件平均。"
        )
    if variant == "missing_condition":
        return (
            "一个人自己没有接种时，同组其他3人都接种，相比同组只有1人接种，"
            "他的感染概率会怎样变化？按“三人接种减一人接种”计算。"
            "评价名单是全部8位居民，每人同等权重；其余安排按原两阶段抽签规则条件平均。"
            "但我们不能确认第一阶段名额通知本身是否对感染结果有直接影响。"
        )
    return (
        "一个人自己没有接种时，同组其他3人都接种，相比同组只有1人接种，"
        "他的感染概率会怎样变化？按“三人接种减一人接种”计算。"
        "评价名单是全部8位居民，每人同等权重；其余安排按原两阶段抽签规则条件平均。"
    )


def build_case(variant: str) -> tuple[BusinessCase, dict]:
    missing = variant == "missing_condition"
    docs = vaccine_docs(missing_first_stage=missing)
    case = BusinessCase(
        case_id=f"LIT-NET-02-{variant}",
        business_question=question(variant),
        sources=[SourceDocument(source_id=k, text=v) for k, v in docs.items()],
    )
    data = dict(
        nodes=list(NODES),
        edges=[list(e) for e in EDGES],
        population=list(NODES),
        design="D6",
        exposure="E4",
        kind="EXACT_TREATED_NEIGHBOR_COUNT",
        cores=None,
        family="spillover",
        target_kind="SPILLOVER_EFFECT",
        own=(0, 0),
        high=3,
        docs=docs,
        missing_first_stage=missing,
    )
    return case, data


def patch_fact(raw: dict, variant: str) -> dict:
    raw["study"]["treatment"] = "接种本次疫苗记1，接受安慰剂记0"
    raw["study"]["outcome"] = "随访一年内是否感染，感染记1，未感染记0"
    raw["study"]["outcome_kind"] = "BINARY"
    if variant == "changed_target":
        raw["target"]["first"]["exposure"] = 1
        raw["target"]["second"]["exposure"] = 3
    else:
        raw["target"]["first"]["exposure"] = 3
        raw["target"]["second"]["exposure"] = 1
    if variant == "missing_condition":
        raw["first_stage_exclusion"] = None
    return raw


def run_variant(variant: str) -> dict:
    patch_module()
    case, data = build_case(variant)
    s = ref.intake.start(
        case,
        reading_format="compact",
        fact_format="short_refs",
        assignment_semantics="joint-assignment-law-1",
    )
    s = ref.intake.receive_candidate(s, ref.a0_reference(case, data), request_sha256=s.request_sha256)
    q = ref.approve(ref.dispatch.prepare_reader(s, "q1")["query_worksheet"])
    entry = ref.dispatch.prepare_reader(s, "q1", query_review=q)
    raw = patch_fact(ref.fact_reference(entry, data), variant)
    options = dict(query_review=q, candidate=raw, request_sha256=entry["request_sha256"])
    plan = ref.dispatch.inspect_methods(s, "q1", **options)
    if plan["state"] == "REVIEW_REQUIRED":
        result = ref.dispatch.execute(s, "q1", **options, **ref.approval_records(plan))
    else:
        result = plan

    folder = OUT / variant
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "business.json", case.model_dump(mode="json"))
    write_json(folder / "source_documents.json", data["docs"])
    write_json(folder / "fact_candidate.json", raw)
    write_json(folder / "plan.json", plan)
    write_json(folder / "result.json", result)
    return dict(
        variant=variant,
        plan_state=plan.get("state"),
        final_state=result.get("state"),
        reason=result.get("reason_code"),
        independent_replay=result.get("independent_replay"),
        target_fingerprint=(result.get("mathematical_claim") or {}).get("target_fingerprint"),
        expression_prefix=((result.get("mathematical_claim") or {}).get("expression") or "")[:160],
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    args = parser.parse_args(argv)
    names = ["original", "missing_condition", "changed_target"] if args.variant == "all" else [args.variant]
    rows = [run_variant(n) for n in names]
    summary = dict(api_calls=0, synthetic_reviews=True, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
