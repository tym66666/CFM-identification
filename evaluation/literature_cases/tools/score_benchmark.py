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
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("Object required")
            rows.append(value)
        except (ValueError, TypeError):
            rows.append({"parse_error_line": number})
    return rows


def classify(row: dict, expected: dict) -> str:
    """Gate saved evidence, not a new mathematical proof or semantic oracle."""
    from evaluation.task6.scripts.verify_final import verify
    if row.get("parse_error_line"):
        return "INVALID_JSON_RECORD"
    if row.get("transport_complete") is not True:
        return "TRANSPORT_FAILURE"
    if row.get("contract_passed") is not True:
        return "CONTRACT_FAILURE"
    count = expected.get("expected_query_count")
    if type(count) is not int or count < 1:
        return "REFERENCE_NOT_READY"
    if type(row.get("query_count")) is not int or row["query_count"] not in expected.get("allowed_query_counts", [count]):
        return "QUERY_COVERAGE_FAILURE"
    count = row["query_count"]
    results = row.get("query_results")
    if not isinstance(results, list) or len(results) != count:
        return "QUERY_EVIDENCE_MISSING"
    ids = [q.get("query_id") for q in results if isinstance(q, dict)]
    if len(ids) != count or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != count:
        return "QUERY_COVERAGE_FAILURE"
    if not expected.get("input_sha256") or row.get("input_sha256") != expected["input_sha256"]:
        return "INPUT_BINDING_FAILURE"
    if row.get("semantic_passed") is None:
        return "SEMANTICS_NOT_SCORED"
    if row.get("semantic_passed") is not True:
        return "SEMANTIC_FAILURE"
    # Legacy self-reported expected_decision_passed/point_present never grant a pass.
    review = row.get("semantic_review") or {}
    if not isinstance(review, dict):
        return "SEMANTICS_NOT_SCORED"
    if not review.get("reviewer") or not review.get("evidence") or review.get("query_ids") != ids:
        return "SEMANTICS_NOT_SCORED"
    if review.get("input_sha256") != row["input_sha256"] or review.get("candidate_repaired") is not False:
        return "SEMANTIC_REVIEW_BINDING_FAILURE"
    required = expected.get("required_target_ids")
    if required:
        coverage = review.get("target_coverage") or {}
        if not isinstance(coverage, dict):
            return "QUERY_COVERAGE_NOT_SCORED"
        if set(coverage) != set(ids) or not all(isinstance(v, list) and v and all(isinstance(x, str) for x in v) for v in coverage.values()):
            return "QUERY_COVERAGE_NOT_SCORED"
        if set(x for values in coverage.values() for x in values) != set(required):
            return "QUERY_COVERAGE_FAILURE"
    state = expected.get("expected_runtime_state")
    for q in results:
        outcome = q.get("result") or {}
        if not isinstance(outcome, dict):
            return "QUERY_EVIDENCE_MISSING"
        if state in ("POINT", "PARTIAL"):
            reference = dict(expected_state=state)
            if state == "PARTIAL" and expected.get("expected_interval"):
                reference["expected_interval"] = expected["expected_interval"]
            if not verify(outcome, reference)["execution_evidence_gate_passed"]:
                return "MATHEMATICAL_EVIDENCE_FAILURE"
        elif state in ("NEEDS_INPUT", "UNSUPPORTED"):
            if outcome.get("state") != state:
                return "IDENTIFICATION_EXPECTATION_FAILURE"
            if outcome.get("backend_called") or outcome.get("certificate") or outcome.get("mathematical_claim") or outcome.get("independent_replay"):
                return "STOP_INCORRECTLY_CERTIFIED"
            # Correct stopping reason requires source-based review, not status alone.
            if q.get("stop_reason_reviewed") is not True or not q.get("stop_reason_evidence"):
                return "STOP_REASON_NOT_SCORED"
        else:
            return "REFERENCE_NOT_READY"
    return "PASS_RECORDED_EVIDENCE"


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
        if attempt.get("parse_error_line"):
            rows.append({**attempt, "outcome": "INVALID_JSON_RECORD", "holdout": None})
            continue
        if not all(isinstance(attempt.get(k), str) for k in ("case_id", "variant", "run_id", "model", "prompt_version")):
            rows.append({**attempt, "model": "INVALID_RECORD", "prompt_version": "INVALID_RECORD", "outcome": "INVALID_RECORD_FIELDS", "holdout": None})
            continue
        key = (attempt.get("case_id"), attempt.get("variant"))
        if key not in refs:
            rows.append({**attempt, "outcome": "UNKNOWN_CASE_VARIANT", "holdout": None})
            continue
        if not attempt.get("run_id") or attempt["run_id"] in seen:
            rows.append({**attempt, "outcome": "INVALID_OR_DUPLICATE_RUN_ID", "holdout": bool(cases[key]["holdout"])})
            continue
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
        "meaning": "Saved execution evidence plus explicit semantic review; does not independently replay certificates or establish generalization.",
        "records": [{"run_id": r.get("run_id"), "case_id": r.get("case_id"), "variant": r.get("variant"), "outcome": r["outcome"]} for r in rows],
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
