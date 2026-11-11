"""Export a demo example's source material into the literature-case layout.

This only copies public source text and saved outputs; it does not create a
reference answer or claim that a variant was run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / "demo" / "examples.json"
CASES = ROOT / "evaluation" / "literature_cases"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args(argv)

    examples = json.loads(DEMO.read_text(encoding="utf8"))
    example = next(x for x in examples if x["id"] == args.demo_id)
    case = example["case"]
    sources = {s["source_id"]: s["text"] for s in case["sources"]}

    for variant in ("original", "missing_condition", "changed_target"):
        folder = CASES / "public" / args.case_id / variant
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "business_question.md").write_text(case["business_question"], encoding="utf8")
        for source_id, text in sources.items():
            (folder / f"source_{source_id}.md").write_text(text, encoding="utf8")
        protocol = "\n\n".join(f"## {sid}\n\n{text}" for sid, text in sources.items())
        (folder / "study_protocol.md").write_text(protocol, encoding="utf8")
        (folder / "data_dictionary.md").write_text(
            "# 数据字典\n\n"
            "本案例是合成业务材料。变量、处理、结果、关系、设计、信息和科学条件的原文见"
            "`source_*.md` 与 `study_protocol.md`。\n\n"
            "公开目录只含业务材料，不含参考答案或预期识别状态。\n",
            encoding="utf8",
        )
        manifest = {
            "case_id": args.case_id,
            "variant": variant,
            "paper_id": args.paper_id,
            "title": args.title,
            "synthetic": True,
            "gold_oracle_location": "OUTSIDE_PUBLIC_CASE_DIRECTORY",
            "llm_access_scope": "PUBLIC_CASE_FILES_ONLY",
            "business_question_file": "business_question.md",
            "supporting_files": ["study_protocol.md", "data_dictionary.md"] + [
                f"source_{sid}.md" for sid in sources
            ],
            "heldout": False,
        }
        (folder / "submission_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )

    research = CASES / "research_only" / args.case_id
    research.mkdir(parents=True, exist_ok=True)
    (research / "actual_outputs.json").write_text(
        json.dumps({
            "source": f"demo/examples.json {args.demo_id} saved_runs",
            "provenance": "Historical saved demo run; not a fresh call in this package.",
            "saved_runs": example.get("saved_runs", []),
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    print(f"exported {args.case_id} from {args.demo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
