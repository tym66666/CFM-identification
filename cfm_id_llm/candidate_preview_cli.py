"""v0.11 OFFLINE candidate preview CLI; never consumes serialized real Core claims.

Production use requires an authorized in-process TrustedCoveragePortV011 supplied
by the integrating Causal-IDFM application. JSON --mock-outcomes is MOCK ONLY.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .candidate_queries import (
    BusinessQueryReviewV011, CandidateReasonerV011, CandidateSafetyError,
    CoreCoverageV011, MockCoveragePortV011,
)
from .providers import MockProvider, OpenAICompatibleChatProvider
from .quality import MultiQueryQualityReportV010
from .schemas import BusinessCase


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CFM-ID v0.11 Identification Candidate; MOCK preview only. NOT a math certificate.")
    p.add_argument("--case", required=True, help="BusinessCase JSON, already extracted from files")
    p.add_argument("--a0-report", required=True, help="Frozen v0.10 A0 quality report JSON")
    p.add_argument("--business-review", required=True, help="Explicit review of exact v0.10 draft, not a scientific license")
    p.add_argument("--mock-outcomes", required=True, help="MOCK mathematical route receipts (never production)")
    p.add_argument("--allow-mock-preview", action="store_true", help="Mandatory opt-in; outputs LLM_UNVERIFIED")
    p.add_argument("--provider", choices=("mock", "openai-chat"), default="mock")
    p.add_argument("--mock-candidate", help="Mock CandidateProposalV011 JSON for offline testing")
    p.add_argument("--model", help="Model name for openai-chat")
    p.add_argument("--base-url", default="https://api.openai.com/v1")
    p.add_argument("--allow-external", action="store_true", help="Explicit permission to send reviewed excerpts to model API")
    p.add_argument("--output", help="Write JSON result instead of stdout")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.provider == "openai-chat" and (not args.allow_external or not args.model):
            raise ValueError("External model requires --allow-external and --model")
        if args.provider == "mock" and not args.mock_candidate:
            raise ValueError("Mock provider requires --mock-candidate")
        if not args.allow_mock_preview:
            raise ValueError("Standalone CLI requires explicit --allow-mock-preview")
        case = BusinessCase.model_validate_json(Path(args.case).read_text(encoding="utf-8"))
        quality = MultiQueryQualityReportV010.model_validate_json(Path(args.a0_report).read_text(encoding="utf-8"))
        review = BusinessQueryReviewV011.model_validate_json(Path(args.business_review).read_text(encoding="utf-8"))
        entries = json.loads(Path(args.mock_outcomes).read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            raise ValueError("Mock outcome file must be a list")
        port = MockCoveragePortV011({x["query_id"]: CoreCoverageV011.model_validate(x) for x in entries})
        provider = (MockProvider(json.loads(Path(args.mock_candidate).read_text(encoding="utf-8")))
                    if args.provider == "mock" else
                    OpenAICompatibleChatProvider(model=args.model, base_url=args.base_url))
        results = CandidateReasonerV011(provider, port).run(
            case=case, quality=quality, business_review=review, allow_mock_preview=True)
        serialized = results.model_dump_json(indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(serialized, encoding="utf-8")
        else:
            print(serialized, end="")
        return 0
    except Exception as exc:
        # Never echo business material, scientific approvals, model output or credentials.
        print("Candidate preview stopped safely (" + type(exc).__name__ + "); check review hashes and mock inputs.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
