"""Validate the public/research-only split and public network files.

This is an integrity check, not an identification run. It does not read the
paper references into any model input and does not certify the mathematical
target.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evaluation" / "literature_cases"
FORBIDDEN_PUBLIC_NAMES = {
    "reference.json",
    "paper_extract.md",
    "actual_outputs.json",
    "run_record.md",
    "review_teacher.md",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf8"))


def read_csv(path: Path):
    with path.open(encoding="utf8", newline="") as fh:
        return list(csv.DictReader(fh))


def check_case(entry: dict) -> list[str]:
    errors: list[str] = []
    public = ROOT / entry["public_directory"]
    research = ROOT / entry["research_directory"]
    if not public.is_dir():
        errors.append(f"missing public directory: {public}")
    if not research.is_dir():
        errors.append(f"missing research directory: {research}")

    for path in public.rglob("*"):
        if path.is_file() and path.name in FORBIDDEN_PUBLIC_NAMES:
            errors.append(f"forbidden reference-like file in public: {path}")

    for variant in entry["variants"]:
        folder = public / variant["name"]
        manifest_path = folder / "submission_manifest.json"
        if not manifest_path.is_file():
            errors.append(f"missing manifest: {manifest_path}")
            continue
        manifest = read_json(manifest_path)
        if manifest.get("case_id") != entry["case_id"]:
            errors.append(f"case_id mismatch: {manifest_path}")
        if manifest.get("variant") != variant["name"]:
            errors.append(f"variant mismatch: {manifest_path}")
        for name in manifest.get("supporting_files", []):
            if not (folder / name).is_file():
                errors.append(f"missing supporting file: {folder / name}")

    return errors


def check_network(case_dir: Path) -> dict:
    units_path = case_dir / "units.csv"
    if not units_path.is_file():
        return {"error": "units.csv missing"}
    units = [row["unit_id"] for row in read_csv(units_path)]
    edge_name = "network_edges.csv" if (case_dir / "network_edges.csv").is_file() else "network_partial.csv"
    edge_path = case_dir / edge_name
    if not edge_path.is_file():
        return {"error": "network file missing"}
    edges = read_csv(edge_path)
    pairs = {(row["unit_a"], row["unit_b"]) for row in edges}
    # An undirected edge list may store each edge once. Reject a file that
    # stores both directions, since that would double-count degrees.
    reverse_duplicates = any((b, a) in pairs for a, b in pairs)
    no_self = all(a != b for a, b in pairs)
    nodes = set(units)
    unknown = sorted({x for pair in pairs for x in pair if x not in nodes})
    degrees = {u: 0 for u in units}
    for a, b in pairs:
        degrees[a] = degrees.get(a, 0) + 1
        degrees[b] = degrees.get(b, 0) + 1
    return {
        "file": edge_name,
        "units": len(units),
        "edges": len(pairs),
        "undirected_unique": not reverse_duplicates,
        "no_self_loops": no_self,
        "unknown_nodes": unknown,
        "min_degree": min(degrees.values()) if degrees else None,
        "max_degree": max(degrees.values()) if degrees else None,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    registry = read_json(CASES / "registry.json")
    report = {"version": registry["version"], "cases": [], "errors": []}
    for entry in registry["cases"]:
        errors = check_case(entry)
        networks = {}
        if entry.get("family") == "NETWORK":
            for variant in entry["variants"]:
                networks[variant["name"]] = check_network(
                    ROOT / entry["public_directory"] / variant["name"]
                )
        else:
            networks = {"not_applicable": f"family={entry.get('family')}"}
        report["cases"].append({
            "case_id": entry["case_id"],
            "status": entry.get("status"),
            "review_status": entry.get("review_status"),
            "errors": errors,
            "networks": networks,
        })
        report["errors"].extend(errors)

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf8")
    print(text, end="")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
