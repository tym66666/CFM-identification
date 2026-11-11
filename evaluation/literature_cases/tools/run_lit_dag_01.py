"""Run LIT-DAG-01 through the existing DAG back-door entry.

Uses the repository's frozen synthetic business reference builder and the
normal inspect/review/replay path. No LLM call, no real-world approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from examples.dag_business_reference import _case, assess


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-DAG-01"
OUT = ROOT / "evaluation" / "literature_cases" / "research_only" / "LIT-DAG-01" / "structured_runs"


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def write_public(variant: str, case: dict) -> None:
    folder = CASE / variant
    folder.mkdir(parents=True, exist_ok=True)
    docs = case["bundle"]["documents"]
    (folder / "business_question.md").write_text(case["bundle"]["question"], encoding="utf8")
    (folder / "variables.md").write_text(docs["variables"], encoding="utf8")
    (folder / "graph.md").write_text(docs["relations"] + "\n\n" + docs["context"], encoding="utf8")
    (folder / "model.md").write_text(docs["model"], encoding="utf8")
    (folder / "information.md").write_text(docs["information"], encoding="utf8")
    (folder / "data_dictionary.md").write_text(
        "# 数据字典\n\n"
        "本案例使用二元变量。变量含义、取值编码见 `variables.md`；\n"
        "直接因果关系见 `graph.md`；结构模型假设见 `model.md`；\n"
        "总体信息见 `information.md`。\n\n"
        "所有变量均有观测；没有样本表，本案例使用完整符号总体联合分布，不是有限样本。\n",
        encoding="utf8",
    )
    write_json(folder / "submission_manifest.json", {
        "case_id": "LIT-DAG-01",
        "variant": variant,
        "paper_id": "pearl1995_backdoor",
        "title": "培训、业绩与资深员工：后门调整",
        "synthetic": True,
        "gold_oracle_location": "OUTSIDE_PUBLIC_CASE_DIRECTORY",
        "llm_access_scope": "PUBLIC_CASE_FILES_ONLY",
        "business_question_file": "business_question.md",
        "supporting_files": ["variables.md", "graph.md", "model.md", "information.md", "data_dictionary.md"],
        "heldout": False,
        "notes": "Pearl (1995) 后门准则的合成业务应用；不是现实医学事实，也不是论文数据复现。",
    })


def variants() -> dict[str, dict]:
    return {
        "original": _case("LIT-DAG-01-original"),
        "missing_condition": _case("LIT-DAG-01-missing_condition", missing=True),
        "changed_target": _case("LIT-DAG-01-changed_target", mediator=True),
    }


def run_variant(name: str, case: dict) -> dict:
    write_public(name, case)
    result = assess(case, case["reference"])
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "bundle.json", case["bundle"])
    write_json(folder / "reference_wire.json", case["reference"])
    write_json(folder / "result.json", result)
    return dict(
        variant=name,
        expected=case["expected_state"],
        final_state=result.get("final_state"),
        passed=result.get("passed"),
        score=result.get("score"),
        reason=result.get("result", {}).get("reason_code"),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    args = parser.parse_args(argv)
    data = variants()
    names = list(data) if args.variant == "all" else [args.variant]
    rows = [run_variant(name, data[name]) for name in names]
    summary = dict(api_calls=0, synthetic_reviews=True, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(r["passed"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
