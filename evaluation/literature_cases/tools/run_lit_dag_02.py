"""Run LIT-DAG-02 front-door variants through the native front-door entry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cfm_id_bridge.scientific_binding import sha
from cfm_id.dag_frontdoor import submit
from cfm_id.dag_frontdoor_contract import FrontdoorProblem, PopulationLaw
from examples.dag_frontdoor_reference import synthetic_review


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "evaluation" / "literature_cases" / "research_only" / "LIT-DAG-02" / "structured_runs"

NODES = ["体质", "吸烟", "焦油", "肺癌"]
BASE_EDGES = [["体质", "吸烟"], ["体质", "肺癌"], ["吸烟", "焦油"], ["焦油", "肺癌"]]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def problem(*, graph_status="DECLARED", edges=None) -> FrontdoorProblem:
    return FrontdoorProblem(
        version="dag-frontdoor-1",
        model="RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS",
        variable_domain="BINARY",
        nodes=NODES,
        observed=["吸烟", "焦油", "肺癌"],
        latent=["体质"],
        edges=[list(e) for e in (edges or BASE_EDGES)],
        graph_status=graph_status,
        graph_source="Synthetic front-door graph declared by the case author",
        materials_sha256=sha({"case": "LIT-DAG-02", "graph_status": graph_status, "edges": edges or BASE_EDGES}),
        context="同一随访人群与随访期",
        treatment="吸烟",
        outcome="肺癌",
        frontdoor_variable="焦油",
        information=PopulationLaw(
            source_id="lit_dag_02_synthetic_law",
            source_sha256=sha({"law": "positive synthetic observed law"}),
            variables=["吸烟", "焦油", "肺癌"],
            availability="SYMBOLIC_POPULATION_LAW",
            strictly_positive_joint=True,
            provenance="Hypothetical complete observed population law for the synthetic case",
        ),
        additional_restrictions=[],
    )


def run_variant(name: str) -> dict:
    if name == "original":
        p = problem()
    elif name == "missing_condition":
        p = problem(graph_status="UNKNOWN")
    elif name == "changed_target":
        p = problem(edges=BASE_EDGES + [["吸烟", "肺癌"]])
    else:
        raise ValueError(name)
    result = submit(p, review=synthetic_review(p), research_protocol_selected=True)
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "problem.json", p.model_dump(mode="json"))
    write_json(folder / "result.json", result)
    return dict(variant=name, state=result.get("state"), reason=result.get("reason_code"),
                independent_replay=result.get("certificate_replayed"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    args = parser.parse_args(argv)
    names = ["original", "missing_condition", "changed_target"] if args.variant == "all" else [args.variant]
    rows = [run_variant(n) for n in names]
    summary = dict(api_calls=0, synthetic_reviews=True, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
