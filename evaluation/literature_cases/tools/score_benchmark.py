"""Score recorded LLM attempts against the isolated literature-case references.

No API call. Attempts are JSONL records matching benchmark/schema.json.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evaluation" / "literature_cases"
PUBLIC = CASES / "benchmark" / "cases.jsonl"
REFERENCES = CASES / "research_only" / "benchmark" / "references.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line.strip()]


def classify(row: dict, expected: dict) -> str:
    if row.get("transport_complete") is not True:
        return "TRANSPORT_FAILURE"
    if row.get("contract_passed") is not True:
        return "CONTRACT_FAILURE"
    if type(row.get("query_count")) is not int or row["query_count"] < 1:
        return "QUERY_COVERAGE_FAILURE"
    if row.get("semantic_passed") is None:
        return "SEMANTICS_NOT_SCORED"
    if row.get("semantic_passed") is not True:
        return "SEMANTIC_FAILURE"
    if row.get("expected_decision_passed") is None:
        return "DECISION_NOT_SCORED"
    if row.get("expected_decision_passed") is not True:
        return "IDENTIFICATION_EXPECTATION_FAILURE"
    if row.get("point_present") is True and row.get("point_replay_passed") is not True:
        return "CERTIFICATE_FAILURE"
    return "PASS"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    cases = {(r["case_id"], r["variant"]): r for r in read_jsonl(PUBLIC)}
    refs = {(r["case_id"], r["variant"]): r for r in read_jsonl(REFERENCES)}
    attempts = read_jsonl(args.attempts)
    rows = []
    seen = set()
    for attempt in attempts:
        key = (attempt.get("case_id"), attempt.get("variant"))
        if key not in refs:
            raise ValueError(f"UNKNOWN_CASE_VARIANT: {key}")
        if attempt.get("run_id") in seen:
            raise ValueError(f"DUPLICATE_RUN_ID: {attempt.get('run_id')}")
        seen.add(attempt.get("run_id"))
        rows.append({
            **attempt,
            "holdout": bool(cases[key]["holdout"]),
            "expected_status": refs[key]["expected_status"],
            "outcome": classify(attempt, refs[key]),
        })

    by_run = defaultdict(list)
    for row in rows:
        by_run[(row.get("model"), row.get("prompt_version"))].append(row)
    summary = {
        "attempts": len(rows),
        "by_model_prompt": {},
        "by_split": {},
    }
    for (model, prompt), group in by_run.items():
        summary["by_model_prompt"][f"{model}|{prompt}"] = dict(Counter(r["outcome"] for r in group))
    for split in ("development", "holdout"):
        group = [r for r in rows if r["holdout"] == (split == "holdout")]
        summary["by_split"][split] = dict(Counter(r["outcome"] for r in group))
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
