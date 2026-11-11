"""Compact structured-run artifacts and remove duplicated source attachments.

Keeps the actual result: status, mathematical claim, certificate and per-query
status. Drops raw plans, bundles, fact candidates and source catalogs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "evaluation" / "literature_cases" / "research_only"
PUBLIC = ROOT / "evaluation" / "literature_cases" / "public"
DROP_NAMES = {"plans.json", "plan.json", "business.json", "source_documents.json",
              "fact_candidate.json", "problem.json"}


def compact_result(value):
    if not isinstance(value, dict):
        return value
    out = {}
    for key in (
        "state", "reason_code", "independent_replay", "certificate_replayed",
        "all_queries_identified", "all_queries_point_identified",
        "expected_state", "final_state", "passed", "score",
        "expected_query_ids", "identified_query_ids", "unresolved_query_ids",
        "point_identified_query_ids", "partially_identified_query_ids",
        "query_id", "result_scope",
    ):
        if key in value:
            out[key] = value[key]
    for key in ("mathematical_claim", "certificate"):
        if key in value:
            out[key] = value[key]
    if "results" in value:
        out["results"] = [compact_result(x) for x in value["results"]]
    if "result" in value:
        out["result"] = compact_result(value["result"])
    return out


def compact_saved_outputs(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf8"))
    rows = []
    for run in data.get("saved_runs", []):
        result = run.get("result", {})
        rows.append({
            "title": run.get("title"),
            "state": result.get("state"),
            "independent_replay": result.get("independent_replay"),
            "mathematical_claim": result.get("mathematical_claim"),
            "certificate": result.get("certificate"),
        })
    data["saved_runs"] = rows
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    changed = 0
    for path in RESEARCH.glob("*/structured_runs/*/result.json"):
        value = json.loads(path.read_text(encoding="utf8"))
        compact = compact_result(value)
        if not args.dry_run:
            path.write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        changed += 1

    for folder in RESEARCH.glob("*/structured_runs/*"):
        if not folder.is_dir():
            continue
        for name in DROP_NAMES:
            path = folder / name
            if path.exists():
                if not args.dry_run:
                    path.unlink()
                changed += 1

    for path in RESEARCH.glob("*/actual_outputs.json"):
        if not args.dry_run:
            compact_saved_outputs(path)
        changed += 1

    # Remove source_*.md duplicates for exported demo cases; study_protocol.md
    # already contains the same source text.
    for case in ("LIT-NET-05", "LIT-NET-06", "LIT-NET-07", "LIT-DAG-02"):
        for folder in (PUBLIC / case).glob("*"):
            if not folder.is_dir():
                continue
            removed = []
            for path in folder.glob("source_*.md"):
                removed.append(path.name)
                if not args.dry_run:
                    path.unlink()
            manifest = folder / "submission_manifest.json"
            if manifest.exists() and removed:
                value = json.loads(manifest.read_text(encoding="utf8"))
                value["supporting_files"] = [
                    name for name in value.get("supporting_files", [])
                    if name not in removed
                ]
                if not args.dry_run:
                    manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
                changed += len(removed)

    print(f"compacted/changed {changed} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
