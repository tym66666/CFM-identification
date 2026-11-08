"""Offline, mock-only v0.2 routing demo. A future real Core adapter is not bundled."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from pydantic import ValidationError
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .orchestrator import ConfirmationError, GatewayV02
from .orchestration_schemas import HumanReviewV02, canonical_sha256
from .mock_core import MockCorePort, MockCoreScenario
from .schemas import BusinessCase
from .reporting import render_routing_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CFM-ID LLM Gateway v0.2: review-bound, verified-first routing demo")
    parser.add_argument("--input", required=True, help="BusinessCase JSON")
    parser.add_argument("--provider", choices=("mock", "openai-chat"), default="mock")
    parser.add_argument("--mock-response", help="v0.1 formulation mock output")
    parser.add_argument("--model", help="Only used with openai-chat")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--review", help="Explicit human-review record JSON (no automatic approval)")
    parser.add_argument("--mock-core", help="Mock Core reply scenario JSON; NEVER real verification")
    parser.add_argument("--review-template", help="Write PENDING reviewer template to file; does not approve")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", help="Write report; otherwise print to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.provider == "mock" and not args.mock_response:
        parser.error("--mock-response required with provider=mock")
    if args.provider == "openai-chat" and not args.model:
        parser.error("--model required with provider=openai-chat")
    try:
        case = BusinessCase.model_validate_json(Path(args.input).read_text(encoding="utf-8"))
        if args.provider == "mock":
            provider = MockProvider(json.loads(Path(args.mock_response).read_text(encoding="utf-8")))
        else:
            provider = OpenAICompatibleChatProvider(model=args.model, base_url=args.base_url)
        review = (HumanReviewV02.model_validate_json(Path(args.review).read_text(encoding="utf-8"))
                  if args.review else None)
        core = (MockCorePort(MockCoreScenario.model_validate_json(Path(args.mock_core).read_text(encoding="utf-8")))
                if args.mock_core else None)
        result = GatewayV02(provider, core=core).run(case, human_review=review)
        if args.review_template:
            template = {
                "schema_version": "cfm-id-human-review-v0.2",
                "input_sha256": result.formulation.input_sha256,
                "draft_sha256": canonical_sha256(result.formulation.draft),
                "reviewed_by": "FILL_IN_REVIEWER_ID",
                "decision": "PENDING_CHANGE_TO_CONFIRMED_AFTER_REAL_REVIEW",
                "review_note": "FILL_IN_WHAT_WAS_CHECKED_AND_WHAT_REMAINS_UNCERTAIN",
                "admitted_assumptions": [],
            }
            Path(args.review_template).write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload = {
            "formulation": result.formulation.model_dump(mode="json"),
            "routing": result.routing.model_dump(mode="json"),
        }
        output = (json.dumps(payload, ensure_ascii=False, indent=2)
                  if args.format == "json" else render_routing_text(result.formulation, result.routing))
        if args.output:
            Path(args.output).write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0
    except (OSError, ValueError, ValidationError, ProviderError, ConfirmationError, json.JSONDecodeError) as exc:
        print(f"Gateway failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
