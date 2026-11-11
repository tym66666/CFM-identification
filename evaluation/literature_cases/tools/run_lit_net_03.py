"""Run LIT-NET-03 (seven-site full-policy PARTIAL) through the bounded entry.

No LLM call. The case is a project-built finite mean model; Manski (2013) is
background, not the source of the numeric [3/7,4/7] interval.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from cfm_id import business_dispatch as dispatch
from examples import network_bounded_dispatch_reference as b


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-03"
OUT = None  # Explicit new destination required; never overwrite submitted evidence.

NODES = ["中心"] + [f"网点{i}" for i in range(1, 7)]
EDGES = [["中心", n] for n in NODES[1:]]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def write_public(variant: str, case, cells: list[dict], extra: bool) -> None:
    folder = CASE / variant
    folder.mkdir(parents=True, exist_ok=True)
    docs = {s.source_id: s.text for s in case.sources}
    (folder / "business_question.md").write_text(case.business_question, encoding="utf8")
    protocol = "\n\n".join(
        docs[k] for k in ("study", "network", "assignment", "exposure", "science") if k in docs
    )
    (folder / "study_protocol.md").write_text(protocol, encoding="utf8")
    (folder / "information.md").write_text(docs["information"], encoding="utf8")
    (folder / "bounds.md").write_text(docs["bounds"], encoding="utf8")
    model = "\n\n".join(docs[k] for k in ("sufficiency", "complete_model", "extra") if k in docs)
    (folder / "model.md").write_text(model, encoding="utf8")
    (folder / "data_dictionary.md").write_text(
        "# 数据字典\n\n"
        "| 字段 | 含义 |\n|---|---|\n"
        "| `unit_id` | 网点编号：中心、网点1–网点6 |\n"
        "| `unit_a`, `unit_b` | 无向合作边 |\n"
        "| `quota` | 原试点每轮均匀抽取的固定名额 |\n\n"
        "结果：本周任务是否按时完成，完成记 1、未完成记 0。\n"
        "同伴暴露：合作邻居中严格超过一半使用 AI 为 1，否则 0；平票和孤立点为 0。\n",
        encoding="utf8",
    )
    with (folder / "units.csv").open("w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh); w.writerow(["unit_id"]); w.writerows([[n] for n in NODES])
    with (folder / "network_edges.csv").open("w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh); w.writerow(["unit_a", "unit_b"]); w.writerows(EDGES)
    with (folder / "design.csv").open("w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh); w.writerow(["design", "quota"]); w.writerow(["UNIFORM_FIXED_QUOTA", 3])
    write_json(folder / "information_cells.json", cells)
    write_json(folder / "submission_manifest.json", {
        "case_id": "LIT-NET-03",
        "variant": variant,
        "paper_id": "manski2013_social_interactions",
        "title": "七网点全网推广：平均按时完成率能确定到什么范围？",
        "synthetic": True,
        "gold_oracle_location": "OUTSIDE_PUBLIC_CASE_DIRECTORY",
        "llm_access_scope": "PUBLIC_CASE_FILES_ONLY",
        "business_question_file": "business_question.md",
        "supporting_files": ["study_protocol.md", "information.md", "bounds.md", "model.md",
                             "data_dictionary.md", "units.csv", "network_edges.csv", "design.csv",
                             "information_cells.json"],
        "heldout": False,
        "notes": "项目自建有限均值模型；不是 Manski (2013) 的数值答案。",
    })


def run_variant(variant: str, **kwargs) -> dict:
    if OUT is None: raise ValueError("REFERENCE_FIXTURE_OUTPUT_REQUIRED")
    case, cells = b.case(**kwargs)
    s, entry, options, plan = b.setup(**kwargs)
    if plan["state"] == "REVIEW_REQUIRED":
        result = dispatch.execute(s, "q1", **options, **b.approval_records(plan))
    else:
        result = plan
    folder = OUT / variant
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "business.json", case.model_dump(mode="json"))
    write_json(folder / "plan.json", plan)
    write_json(folder / "result.json", result)
    mc = result.get("mathematical_claim") or {}
    return dict(
        variant=variant,
        plan_state=plan.get("state"),
        final_state=result.get("state"),
        reason=result.get("reason_code"),
        independent_replay=result.get("independent_replay"),
        interval=mc.get("interval"),
        sharp=mc.get("sharp"),
        width=mc.get("width"),
        target_sha256=mc.get("target_sha256"),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    from . import reference_fixture
    reference_fixture.arguments(parser)
    args = parser.parse_args(argv)
    global OUT
    OUT = reference_fixture.output(args, ROOT)
    data = {
        "original": {},
        "missing_condition": {"missing_scope": True},
        "changed_target": {"extra": True},
    }
    names = list(data) if args.variant == "all" else [args.variant]
    rows = [run_variant(n, **data[n]) for n in names]
    summary = dict(evidence_kind="HAND_AUTHORED_REFERENCE_FIXTURE", automatic_business_reading=False, api_calls=0, synthetic_reviews=True, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
