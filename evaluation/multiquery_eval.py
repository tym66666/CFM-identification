"""v0.9 multi-goal business benchmark: target-extraction scores, NOT math proofs.

A separate human audit is required for A4/A5, target semantics and causal formulas.
Never call network unless --provider openai-chat --allow-external is explicit.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from cfm_id_llm.multiquery_formulator import MultiQueryFormulatorV09, MultiQueryValidationError
from cfm_id_llm.multiquery import MultiQueryDraftV09, BusinessInquiryV09
from cfm_id_llm.providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from cfm_id_llm.schemas import (BusinessCase, DraftProblemSpec, EvidenceQuote,
                                SemanticClaim, TargetDraft, TargetKind)

CASES = Path(__file__).parent / "multiquery" / "business_queries.json"


def load_cases(path: Path = CASES) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Expected a list of business cases")
    for entry in raw:
        BusinessCase(case_id=entry["case_id"], business_question=entry["business_question"])
        if not entry.get("expected"):
            raise ValueError("Every benchmark must include expected query kinds")
        for goal in entry["expected"]:
            TargetKind(goal["kind"])
            if goal["quote"] not in entry["business_question"]:
                raise ValueError("Gold evidence quote not in original business description")
    return raw


def reference_fixture(entry: dict) -> MultiQueryDraftV09:
    """Human-authored expected target types as a MOCK response, *not* complete gold A1-A6.

    Other spec fields remain unresolved on purpose; this fixture validates schema,
    provenance and measurement plumbing, not LLM reasoning quality.
    """
    entries = entry["expected"]
    queries = []
    for i, item in enumerate(entries, 1):
        quote = EvidenceQuote(source_id="business_question", quote=item["quote"])
        goal = SemanticClaim(value=item["quote"], basis="EXPLICIT_TEXT", evidence=[quote])
        target = TargetDraft(kind=TargetKind(item["kind"]), description=goal)
        queries.append(BusinessInquiryV09(query_id=f"q{i}", business_goal=goal, target=target))
    draft = DraftProblemSpec(target=queries[0].target)
    return MultiQueryDraftV09(shared_draft=draft, primary_query_id="q1", queries=queries)


def score_targets(expected: list[str], predicted: list[str]) -> dict:
    gold, guess = Counter(expected), Counter(predicted)
    true_positive = sum(min(gold[x], guess[x]) for x in gold)
    precision = true_positive / sum(guess.values()) if guess else 0.0
    recall = true_positive / sum(gold.values()) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"target_precision": round(precision, 4), "target_recall": round(recall, 4),
            "target_f1": round(f1, 4), "exact_target_multiset": gold == guess,
            "unexpected_target_count": sum((guess - gold).values()),
            "missing_target_count": sum((gold - guess).values())}


def evaluate(*, provider_name: str, model: str | None, max_cases: int | None,
             allow_external: bool, fixture_dir: Path | None, base_url: str,
             case_path: Path = CASES) -> dict:
    gold = load_cases(case_path)
    if max_cases is not None:
        if max_cases < 1:
            raise ValueError("max_cases must be positive")
        gold = gold[:max_cases]
    if provider_name == "openai-chat" and not allow_external:
        raise ValueError("Explicit --allow-external required")
    provider = (OpenAICompatibleChatProvider(model=model or "", base_url=base_url)
                if provider_name == "openai-chat" else None)
    rows = []
    for entry in gold:
        case = BusinessCase(case_id=entry["case_id"], business_question=entry["business_question"])
        expected = [x["kind"] for x in entry["expected"]]
        try:
            if provider_name == "oracle-fixture":
                local = MockProvider(reference_fixture(entry).model_dump(mode="json"))
            elif provider_name == "mock":
                if fixture_dir is None:
                    raise ValueError("mock requires --fixture-dir")
                p = fixture_dir / (entry["case_id"] + ".json")
                local = MockProvider(json.loads(p.read_text(encoding="utf-8")))
            else:
                local = provider
            result = MultiQueryFormulatorV09(local).formulate(case)
            predicted = [q.target.kind.value for q in result.draft.queries]
            row = {"case_id": case.case_id, "schema_and_quotes_valid": True,
                   "model_query_count": len(predicted), "predicted_target_kinds": predicted,
                   "expected_target_kinds": expected,
                   "verification": "NOT_PERFORMED",
                   **score_targets(expected, predicted)}
        except (ValueError, OSError, MultiQueryValidationError, ProviderError) as exc:
            row = {"case_id": case.case_id, "schema_and_quotes_valid": False,
                   "expected_target_kinds": expected, "verification": "NOT_PERFORMED",
                   "error_kind": type(exc).__name__}
        rows.append(row)
    passed = [r for r in rows if r["schema_and_quotes_valid"]]
    actual_model_run = provider_name == "openai-chat"
    return {
        "benchmark_version": "cfm-id-multiquery-benchmark-v0.9",
        "evaluation_kind": "ONLINE_MODEL_TARGET_EXTRACTION" if actual_model_run else "OFFLINE_PIPELINE_FIXTURE_ONLY",
        "model": model if actual_model_run else None,
        "total": len(rows), "valid_schema_and_quotes": len(passed),
        "exact_target_multiset_count": sum(1 for r in passed if r.get("exact_target_multiset")),
        "mean_target_f1_on_valid": round(sum(r.get("target_f1", 0) for r in passed) / len(passed), 4) if passed else None,
        "causal_semantic_accuracy": "NOT_MEASURED_AUTOMATICALLY",
        "a4_a5_scientific_verification": "NOT_PERFORMED",
        "math_identification_accuracy": "NOT_MEASURED",
        "human_review_required": True,
        "cases": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CFM-ID v0.9 target coverage and format benchmark")
    p.add_argument("--provider", choices=("oracle-fixture", "mock", "openai-chat"), default="oracle-fixture")
    p.add_argument("--model")
    p.add_argument("--base-url", default="https://api.openai.com/v1")
    p.add_argument("--allow-external", action="store_true")
    p.add_argument("--fixture-dir")
    p.add_argument("--max-cases", type=int)
    p.add_argument("--case-set", default=str(CASES))
    p.add_argument("--output")
    args = p.parse_args(argv)
    try:
        r = evaluate(provider_name=args.provider, model=args.model,
                     max_cases=args.max_cases, allow_external=args.allow_external,
                     fixture_dir=Path(args.fixture_dir) if args.fixture_dir else None,
                     base_url=args.base_url, case_path=Path(args.case_set))
        message = json.dumps(r, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(message, encoding="utf-8")
        else:
            print(message)
        return 0
    except (ValueError, ProviderError, OSError, json.JSONDecodeError) as exc:
        print(f"Benchmark stopped ({type(exc).__name__}).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
