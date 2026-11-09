"""Run LIT-NET-06 seed-policy finite policy mean through the extended entry.

Four households, two complete policies with known probabilities. No LLM call.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cfm_id import business_dispatch as dispatch, business_intake as intake
from cfm_id_llm import network_extended_reading as rd
from cfm_id_llm.quality import BusinessInquiryV010, MultiQueryDraftV010, QuerySemanticsV010
from cfm_id_llm.schemas import (
    BusinessCase, DraftProblemSpec, InformationDesignDraft,
    SemanticClaim, SourceDocument, StructureDraft, TargetDraft, UnitsVariablesDraft,
)
from examples import network_extended_reference as e


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-06"
OUT = ROOT / "evaluation" / "literature_cases" / "research_only" / "LIT-NET-06" / "structured_runs"
NODES = ["甲", "乙", "丙", "丁"]
EDGES = [["甲", "乙"], ["乙", "丙"], ["丙", "丁"]]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def claim(text: str, source: str) -> SemanticClaim:
    return SemanticClaim(value=text, basis="EXPLICIT_TEXT", evidence=[dict(source_id=source, quote=text)])


def run_variant(variant: str) -> dict:
    question = (CASE / variant / "business_question.md").read_text(encoding="utf8")
    # Remove the markdown title from the goal quote; keep the body.
    question = question.split("\n", 1)[1].strip() if "\n" in question else question
    source_text = "\n\n".join(
        (CASE / variant / name).read_text(encoding="utf8")
        for name in ("study_protocol.md",)
    )
    case = BusinessCase(
        case_id=f"LIT-NET-06-{variant}",
        business_question=question,
        sources=[SourceDocument(source_id="proposal", text=source_text)],
    )
    gate = claim(question, "business_question")
    proposal = claim(source_text, "proposal")
    target = TargetDraft(kind="STOCHASTIC_POLICY_VALUE", description=gate)
    shared = DraftProblemSpec(
        target=target,
        units_variables=UnitsVariablesDraft(
            analysis_unit=claim("四户", "proposal"),
            treatment=claim("接受示范培训", "proposal"),
            outcome=claim("采用新技术", "proposal"),
        ),
        structure=StructureDraft(unit_network=proposal),
        information_design=InformationDesignDraft(
            assignment_family="INDEPENDENT_BERNOULLI",
            assignment_law=proposal,
        ),
    )
    sem = QuerySemanticsV010(
        target_population=gate,
        intervention=gate,
        aggregation=gate,
        policy_assignment=gate,
        standardization_distribution=gate,
    )
    query = BusinessInquiryV010(query_id="q1", business_goal=gate, target=target, semantics=sem)
    a0 = MultiQueryDraftV010(shared_draft=shared, primary_query_id="q1", queries=[query]).model_dump(mode="json")
    s = intake.start(case, reading_format="canonical", fact_format="short_refs")
    s = intake.receive_candidate(s, a0, request_sha256=s.request_sha256)
    initial = dispatch.prepare_reader(s, "q1")
    review = e.approve(initial["query_worksheet"])
    entry = dispatch.prepare_reader(s, "q1", query_review=review)
    # Start from a valid MIX wire shape, then replace the 3-node content.
    refs = rd.reference_catalog(entry["bundle"], binding=entry["fact_binding_sha256"], family=rd.MIX)
    ids = list(refs["aliases"])
    _, raw = e.fixture("mixture")
    raw["reference_context"] = refs["context"]
    raw["study"].update(nodes=list(NODES), edges=[list(x) for x in EDGES],
                        treatment="接受示范培训记1，未接受记0",
                        outcome="下一季采用新技术记1，未采用记0",
                        outcome_kind="BINARY", context="下一季；四户同一交流网络",
                        source_ids=ids)
    raw["assignment"].update(probabilities={n: "1/2" for n in NODES}, source_ids=ids)
    if variant == "changed_target":
        policies = [
            dict(assignment={"甲": 1, "乙": 1, "丙": 0, "丁": 0}, weight="1/2", source_ids=ids),
            dict(assignment={"甲": 0, "乙": 0, "丙": 1, "丁": 1}, weight="1/2", source_ids=ids),
        ]
    else:
        policies = [
            dict(assignment={"甲": 1, "乙": 0, "丙": 1, "丁": 0}, weight="1/2", source_ids=ids),
            dict(assignment={"甲": 0, "乙": 1, "丙": 0, "丁": 1}, weight="1/2", source_ids=ids),
        ]
    raw["target"].update(population=list(NODES), components=policies, source_ids=ids)
    raw["information"][0].update(outcome_nodes=list(NODES), source_ids=ids)
    if variant == "missing_condition":
        raw["target"]["policy_distribution_complete"] = dict(value=None, source_ids=ids)
        raw["target"]["components"] = []
    options = dict(query_review=review, candidate=raw, request_sha256=entry["request_sha256"])
    plan = dispatch.inspect_methods(s, "q1", **options)
    result = e.execute(plan) if plan.get("state") == "REVIEW_REQUIRED" else plan
    folder = OUT / variant
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "business.json", case.model_dump(mode="json"))
    write_json(folder / "fact_candidate.json", raw)
    write_json(folder / "plan.json", plan)
    write_json(folder / "result.json", result)
    mc = result.get("mathematical_claim") or {}
    return dict(variant=variant, plan_state=plan.get("state"), final_state=result.get("state"),
                reason=result.get("reason_code"), independent_replay=result.get("independent_replay"),
                target_fingerprint=mc.get("target_fingerprint"))


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
