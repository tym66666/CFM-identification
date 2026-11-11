"""Export the case library as a public-only JSONL benchmark plus isolated references.

Public cases contain no expected status or answer. The reference JSONL lives
under research_only and must not be sent to a model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evaluation" / "literature_cases"
PUBLIC_OUT = CASES / "benchmark" / "cases.jsonl"
REF_OUT = CASES / "research_only" / "benchmark" / "references.jsonl"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-out", type=Path, default=PUBLIC_OUT)
    parser.add_argument("--reference-out", type=Path, default=REF_OUT)
    args = parser.parse_args(argv)

    registry = read_json(CASES / "registry.json")
    public_rows, reference_rows = [], []
    for case in registry["cases"]:
        for variant in case["variants"]:
            folder = ROOT / case["public_directory"] / variant["name"]
            manifest = read_json(folder / "submission_manifest.json")
            files = ["business_question.md", *manifest.get("supporting_files", [])]
            split_dag = case["case_id"] == "LIT-DAG-01" and variant["name"] != "changed_target"
            target_ids = (["do_0", "do_1"] if split_dag else
                          ["direct", "spillover", "local_total"] if variant["expected_query_count"] == 3 else ["target"])
            public_rows.append({
                "case_id": case["case_id"],
                "variant": variant["name"],
                "family": case["family"],
                "paper_id": case["paper_id"],
                "title": case.get("title"),
                "holdout": bool(case.get("heldout")),
                "public_directory": str(folder.relative_to(ROOT)).replace("\\", "/"),
                "files": [str((folder / name).relative_to(ROOT)).replace("\\", "/") for name in files],
            })
            reference_rows.append({
                "case_id": case["case_id"],
                "variant": variant["name"],
                "expected_status": variant["expected_status"],
                "expected_runtime_state": variant["expected_runtime_state"],
                "expected_query_count": variant["expected_query_count"],
                "allowed_query_counts": [1, 2] if split_dag else [variant["expected_query_count"]],
                "required_target_ids": target_ids,
                "current_scope_note": variant.get("current_scope_note", case.get("current_scope_note", "")),
                "input_sha256": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in files},
                "expected_interval": read_json(ROOT / case["research_directory"] / "reference.json").get("software_expected", {}).get(variant["name"], {}).get("interval"),
                "actual_status": variant["actual_status"],
                "reference_file": str((ROOT / case["research_directory"] / "reference.json").relative_to(ROOT)).replace("\\", "/"),
                "run_record": str((ROOT / case["research_directory"] / "run_record.md").relative_to(ROOT)).replace("\\", "/"),
                "holdout": bool(case.get("heldout")),
            })

    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.reference_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in public_rows), encoding="utf8")
    args.reference_out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reference_rows), encoding="utf8")
    print(f"wrote {len(public_rows)} public rows and {len(reference_rows)} reference rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
