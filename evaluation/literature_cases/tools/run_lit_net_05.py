"""Run LIT-NET-05 campus invitation spillover through the network design entry.

Explicit synthetic structured run; no LLM call. The original is also checked
against the demo saved run, but this runner produces a fresh local output.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from cfm_id import business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from examples import network_design_exposure_reference as ref


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-05"
OUT = ROOT / "evaluation" / "literature_cases" / "research_only" / "LIT-NET-05" / "structured_runs"

NODES = [f"学生{i:02d}" for i in range(1, 13)]
GROUPS = [NODES[:6], NODES[6:]]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def read_source(variant: str, source_id: str) -> str:
    return (CASE / variant / f"source_{source_id}.md").read_text(encoding="utf8")


def edges_from_network_text(text: str) -> list[list[str]]:
    match = re.search(r"(\[\[.*\]\])", text, re.S)
    if not match:
        raise ValueError("NO_EDGE_LIST")
    return [[str(a), str(b)] for a, b in json.loads(match.group(1))]


def docs(variant: str) -> dict:
    return {
        "study": read_source(variant, "study"),
        "network": read_source(variant, "network"),
        "population": read_source(variant, "population"),
        "science": read_source(variant, "science"),
        "remaining": read_source(variant, "remaining"),
        "assignment": read_source(variant, "assignment"),
        "exposure": read_source(variant, "exposure"),
        "information": read_source(variant, "information"),
        "context": "本学年末；同一所学校、同一结果定义和评价名单。",
    }


def question(variant: str) -> str:
    if variant == "changed_target":
        return (
            "自己没有收到邀请时，没有朋友获邀相比至少一位朋友获邀，佩戴支持反冲突手环的概率会怎样变化？"
            "计算“没有朋友获邀”减“至少一位朋友获邀”，对全部12名学生等权评价。"
        )
    return (
        "自己没有收到邀请时，至少一位朋友获邀相比没有朋友获邀，佩戴支持反冲突手环的概率会怎样变化？"
        "计算“至少一位朋友获邀”减“没有朋友获邀”，对全部12名学生等权评价。"
    )


def patch_module(edges: list[list[str]]) -> None:
    ref.NODES = list(NODES)
    ref.EDGES = [list(e) for e in edges]
    ref.GROUPS = [list(g) for g in GROUPS]
    ref.DESIGNS["D3"] = dict(
        kind="TWO_GROUP_FIXED_QUOTA",
        probabilities=None,
        fixed_count=None,
        groups=[list(g) for g in GROUPS],
        treated_quotas=[2, 2],
    )
    ref.DESIGN_TEXT["D3"] = (
        "12名学生分为两组，每组6人；各组独立从组内均匀抽取2人发出邀请，"
        "每一组15份二人名单机会相同。"
    )
    ref.EXPOSURES["E5"] = (
        "ANY_TREATED_NEIGHBOR",
        1,
        "至少一位朋友收到邀请记1，没有朋友收到邀请记0。",
        "至少一位朋友获邀",
        "没有朋友获邀",
    )


def run_variant(variant: str, edges: list[list[str]]) -> dict:
    patch_module(edges)
    d = docs(variant)
    case = BusinessCase(
        case_id=f"LIT-NET-05-{variant}",
        business_question=question(variant),
        sources=[SourceDocument(source_id=k, text=v) for k, v in d.items()],
    )
    data = dict(
        nodes=list(NODES), edges=[list(e) for e in edges], population=list(NODES),
        design="D3", exposure="E5", kind="ANY_TREATED_NEIGHBOR", cores=None,
        family="spillover", target_kind="SPILLOVER_EFFECT", own=(0, 0), high=1, docs=d,
    )
    s = ref.intake.start(case, reading_format="compact", fact_format="short_refs",
                         assignment_semantics="joint-assignment-law-1")
    s = ref.intake.receive_candidate(s, ref.a0_reference(case, data), request_sha256=s.request_sha256)
    q = ref.approve(ref.dispatch.prepare_reader(s, "q1")["query_worksheet"])
    entry = ref.dispatch.prepare_reader(s, "q1", query_review=q)
    raw = ref.fact_reference(entry, data)
    raw["study"]["treatment"] = "收到反冲突项目参与邀请记1，未收到邀请记0；邀请后是否实际出席不改变这个编码"
    raw["study"]["outcome"] = "学年末是否报告佩戴支持反冲突的手环，佩戴记1，未佩戴记0"
    raw["study"]["outcome_kind"] = "BINARY"
    if variant == "missing_condition":
        raw["assignment"]["kind"] = "UNKNOWN"
        raw["assignment"]["groups"] = None
        raw["assignment"]["treated_quotas"] = None
    if variant == "changed_target":
        raw["target"]["first"]["exposure"] = 0
        raw["target"]["second"]["exposure"] = 1
    options = dict(query_review=q, candidate=raw, request_sha256=entry["request_sha256"])
    plan = dispatch.inspect_methods(s, "q1", **options)
    if plan.get("state") == "REVIEW_REQUIRED":
        result = dispatch.execute(s, "q1", **options, **ref.approval_records(plan))
    else:
        result = plan
    folder = OUT / variant
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "business.json", case.model_dump(mode="json"))
    write_json(folder / "source_documents.json", d)
    write_json(folder / "fact_candidate.json", raw)
    write_json(folder / "plan.json", plan)
    write_json(folder / "result.json", result)
    mc = result.get("mathematical_claim") or {}
    return dict(variant=variant, plan_state=plan.get("state"), final_state=result.get("state"),
                reason=result.get("reason_code"), independent_replay=result.get("independent_replay"),
                target_fingerprint=mc.get("target_fingerprint"), expression_prefix=(mc.get("expression") or "")[:160])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    args = parser.parse_args(argv)
    edges = edges_from_network_text(read_source("original", "network"))
    names = ["original", "missing_condition", "changed_target"] if args.variant == "all" else [args.variant]
    rows = [run_variant(n, edges) for n in names]
    summary = dict(api_calls=0, synthetic_reviews=True, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
