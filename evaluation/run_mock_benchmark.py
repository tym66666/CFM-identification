"""Deterministic smoke benchmark against hand-authored mock fixtures.

Measures wiring and human-authored reference alignment ONLY, not live LLM accuracy.
Run: python -m evaluation.run_mock_benchmark
"""
from __future__ import annotations
import json
from pathlib import Path
from cfm_id_llm import BusinessCase, ProblemFormulator
from cfm_id_llm.providers import MockProvider


def run() -> dict:
    root = Path(__file__).resolve().parents[1]
    suite = json.loads((root / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    outcomes = []
    for item in suite:
        case = BusinessCase.model_validate_json((root / item["case_file"]).read_text(encoding="utf-8"))
        fixture = json.loads((root / item["mock_response"]).read_text(encoding="utf-8"))
        report = ProblemFormulator(MockProvider(fixture)).formulate(case)
        assert report.draft.target.kind.value == item["reference_target"], item["id"]
        assert report.draft.information_design.assignment_family.value == item["reference_design"], item["id"]
        assert report.review_status == item["expect_review"], item["id"]
        assert report.mathematical_verification == "NOT_PERFORMED"
        assert report.estimation_handoff_allowed is False
        outcomes.append({"case_id": item["id"], "review_status": report.review_status,
                         "target": report.draft.target.kind.value,
                         "assignment": report.draft.information_design.assignment_family.value,
                         "questions": len(report.suggested_questions), "passed": True})
    return {"fixture_cases": len(outcomes), "passed": sum(x["passed"] for x in outcomes),
            "scope": "mock contract smoke only; real LLM accuracy NOT measured", "cases": outcomes}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
