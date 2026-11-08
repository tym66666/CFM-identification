"""Versioned replacement for the legacy NBIB structured-prediction scorer.

Freeze case IDs and reference hashes before evaluating predictions. Parse each
JSONL record independently, never infer the case ID of a damaged line. This
scores structured fields only: no scientific approval or mathematical proof.
"""
import argparse
from collections import Counter
from pathlib import Path

from .audit_io import (
    AuditFailure, digest, inside, ratio, read_bytes, read_json, require,
    status_counts, strict_json, write_report,
)

VERSION = "structured-prediction-audit-v0.34"
DEFAULT_BENCHMARK = (Path(__file__).resolve().parents[1] / "assets/benchmark_assets"
                     / "benchmarks/network_business_identification")


def freeze_plan(benchmark, case_ids):
    benchmark = Path(benchmark)
    index = read_json(benchmark / "public/case_index.json")
    require(isinstance(case_ids, list) and case_ids and
            all(isinstance(x, str) for x in case_ids) and
            len(case_ids) == len(set(case_ids)), "INVALID_PLANNED_CASES")
    known = {row["case_id"] for row in index["cases"]}
    require(set(case_ids) <= known, "UNKNOWN_PLANNED_CASE")
    return dict(
        schema_version=VERSION + "-plan", case_ids=case_ids,
        benchmark_index_sha256=digest(benchmark / "public/case_index.json"),
        reference_sha256={
            cid: digest(inside(benchmark, f"gold/references/{cid}.json")) for cid in case_ids
        },
        purpose="Frozen structured-field evaluation; no mathematical identification score",
    )


def _predictions(path, input_format):
    try:
        text = read_bytes(path).decode("utf-8-sig")
    except UnicodeError:
        raise AuditFailure("ARTIFACT_PARSE_FAILURE", path) from None
    if input_format == "json":
        value = strict_json(text, path)
        rows = value.get("predictions") if isinstance(value, dict) else value
        require(isinstance(rows, list), "PREDICTION_FILE_SCHEMA_FAILURE")
        return rows, []
    require(input_format == "jsonl", "UNSUPPORTED_INPUT_FORMAT")
    rows, issues = [], []
    for line, text in enumerate(text.splitlines(), 1):
        if not text.strip():
            continue
        try:
            rows.append(strict_json(text, path))
        except AuditFailure as error:
            issues.append(dict(line=line, **error.record()))
    return rows, issues


def _match(gold, pred):
    a, b = Counter(gold), Counter(pred)
    tp = sum(min(n, b[k]) for k, n in a.items())
    precision = tp / sum(b.values()) if b else 0
    recall = tp / sum(a.values()) if a else 0
    return dict(exact=a == b, precision=precision, recall=recall,
                f1=2 * precision * recall / (precision + recall) if precision + recall else 0)


def _score(prediction, reference):
    queries = prediction.get("queries")
    require(isinstance(queries, list) and all(
        isinstance(q, dict) and isinstance(q.get("kind"), str)
        and isinstance(q.get("exact_target_semantics"), str) for q in queries),
        "PREDICTION_SCHEMA_FAILURE")
    for name in ("claimed_verified_point", "claims_a4_pop_available"):
        require(name not in prediction or type(prediction[name]) is bool, "PREDICTION_SCHEMA_FAILURE")
    require(isinstance(prediction.get("assignment_family"), str), "PREDICTION_SCHEMA_FAILURE")
    expected = reference["query_targets"]
    kind = _match([q["kind"] for q in expected], [q["kind"] for q in queries])
    semantic = _match([q["exact_target_semantics"] for q in expected],
                      [q["exact_target_semantics"] for q in queries])
    design = prediction["assignment_family"] == reference["assignment_family"]
    unsafe = prediction.get("claimed_verified_point") is True or prediction.get("claims_a4_pop_available") is True
    return dict(
        classification=("UNSAFE_SCIENTIFIC_CLAIM" if unsafe else
                        "STRUCTURED_FIELDS_MATCH" if kind["exact"] and semantic["exact"] and design
                        else "STRUCTURED_FIELDS_MISMATCH"),
        target_kind=kind, exact_target_semantics=semantic, design_family_exact=design,
        false_verified_point_from_raw_packet=prediction.get("claimed_verified_point") is True,
        false_a4_from_finite_business_data=prediction.get("claims_a4_pop_available") is True,
    )


def audit_predictions(benchmark, manifest, predictions, *, input_format="json"):
    benchmark = Path(benchmark)
    report = dict(
        version=VERSION, evaluation_kind="STRUCTURED_PREDICTION_MATCH_ONLY",
        api_calls=0, rows=[], planned_cases=None, research_only=True,
        math_identification_accuracy="NOT_MEASURED",
        llm_complete_proof_accuracy="NOT_MEASURED",
        model_call_accuracy="NOT_MEASURED_NO_REQUEST_LEDGER",
        human_review_needed=True,
    )
    try:
        plan = read_json(manifest)
        require(plan.get("schema_version") == VERSION + "-plan", "INVALID_PLAN_SCHEMA")
        ids = plan["case_ids"]
        require(isinstance(ids, list) and ids and all(isinstance(x, str) for x in ids)
                and len(ids) == len(set(ids)), "INVALID_PLANNED_CASES")
        report.update(planned_cases=len(ids), manifest_sha256=digest(manifest))
        require(freeze_plan(benchmark, ids) == plan, "FROZEN_REFERENCE_CHANGED")
        references = {cid: read_json(inside(benchmark, f"gold/references/{cid}.json")) for cid in ids}
    except (AuditFailure, KeyError, TypeError, AttributeError) as error:
        issue = error.record() if isinstance(error, AuditFailure) else dict(classification="PLAN_SCHEMA_FAILURE")
        report.update(status="AUDIT_INPUT_FAILURE", input_issues=[issue], publishable_summary=False)
        if report["planned_cases"] is not None:
            report["rows"] = [dict(case_id=cid, classification="AUDIT_INPUT_FAILURE") for cid in ids]
        return report
    try:
        values, issues = _predictions(predictions, input_format)
        report["prediction_file_sha256"] = digest(predictions)
        file_error = None
    except AuditFailure as error:
        values, issues, file_error = [], [error.record()], error.code
    indexed = {}
    for ordinal, value in enumerate(values, 1):
        if not isinstance(value, dict) or not isinstance(value.get("case_id"), str):
            issues.append(dict(record=ordinal, classification="UNASSIGNED_PREDICTION"))
            continue
        cid = value["case_id"]
        if cid not in ids:
            issues.append(dict(record=ordinal, classification="UNKNOWN_CASE_ID"))
            continue
        indexed.setdefault(cid, []).append(value)
    for cid in ids:
        row = dict(case_id=cid)
        candidates = indexed.get(cid, [])
        if file_error:
            row["classification"] = file_error
        elif not candidates:
            row["classification"] = "MISSING_PREDICTION"
        elif len(candidates) != 1:
            row["classification"] = "DUPLICATE_PREDICTION"
        else:
            try:
                row.update(_score(candidates[0], references[cid]))
            except AuditFailure as error:
                row.update(error.record())
            except (KeyError, TypeError, AttributeError):
                row["classification"] = "REFERENCE_SCHEMA_FAILURE"
        report["rows"].append(row)
    passed = sum(r["classification"] == "STRUCTURED_FIELDS_MATCH" for r in report["rows"])
    report.update(
        status="COMPLETE" if passed == len(ids) and not issues else "HAS_FAILURES",
        input_issues=issues, prediction_records_parsed=len(values),
        matched_cases=passed, status_counts=status_counts(report["rows"]),
        structured_matches_per_planned_case=ratio(passed, len(ids)),
        # Parse/identity failures forbid publishing a headline rate as if the
        # prediction batch were intact; the planned denominator is still shown.
        publishable_summary=not issues and not any(
            r["classification"] in {"DUPLICATE_PREDICTION", "MISSING_PREDICTION",
                                    "PREDICTION_SCHEMA_FAILURE", "REFERENCE_SCHEMA_FAILURE"}
            for r in report["rows"]),
        auditor_sha256={p.name: digest(p) for p in
                        (Path(__file__), Path(__file__).with_name("audit_io.py"))},
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--output", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--case-id", action="append", required=True)
    score = sub.add_parser("score")
    score.add_argument("--manifest", type=Path, required=True)
    score.add_argument("--predictions", type=Path, required=True)
    score.add_argument("--input-format", choices=("json", "jsonl"), default="json")
    args = parser.parse_args(argv)
    try:
        report = (freeze_plan(args.benchmark_dir, args.case_id) if args.command == "freeze" else
                  audit_predictions(args.benchmark_dir, args.manifest, args.predictions,
                                    input_format=args.input_format))
        write_report(args.output, report)
    except (AuditFailure, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Offline scoring stopped safely ({type(error).__name__}).")
        return 2
    print(report.get("status", "FROZEN"))
    return 0 if args.command == "freeze" or report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
