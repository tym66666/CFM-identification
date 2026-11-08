"""v0.3 offline demo; actual production Identification adapters are not bundled.

Mock preview is *opt-in*, and even a real LLM used for the preview is NEVER a
verified identification answer. No automatic researcher confirmation exists.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError
from .candidate_reasoner import CandidateNotAllowed, GatewayV03
from .candidate_reporting import render_candidate_text
from .mock_core import MockCorePort, MockCoreScenario
from .orchestration_schemas import HumanReviewV02
from .orchestrator import ConfirmationError
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .schemas import BusinessCase


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CFM-ID Gateway v0.3 unverified Identification candidate demo")
    p.add_argument("--input", required=True, help="BusinessCase JSON")
    p.add_argument("--formulation-provider", choices=("mock", "openai-chat"), default="mock")
    p.add_argument("--mock-formulation", help="Fixture-only v0.1 DraftProblemSpec response")
    p.add_argument("--formulation-model")
    p.add_argument("--candidate-provider", choices=("none", "mock", "openai-chat"), default="none")
    p.add_argument("--mock-candidate", help="Fixture-only CandidateDraftV03 response")
    p.add_argument("--candidate-model")
    p.add_argument("--base-url", default="https://api.openai.com/v1")
    p.add_argument("--review", help="Explicit review bound to EXACT case and draft")
    p.add_argument("--mock-core", help="Mock core scenario JSON; not a real math verifier")
    p.add_argument("--allow-mock-preview", action="store_true",
                   help="Explicit opt-in: run unverified candidate after MOCK UNSUPPORTED")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--output", help="Optional output file")
    return p


def _provider(kind: str, mock_path: str | None, model: str | None, base_url: str):
    if kind == "none":
        return None
    if kind == "mock":
        if not mock_path:
            raise ValueError("A mock provider requires a fixture (--mock-formulation or --mock-candidate)")
        return MockProvider(json.loads(Path(mock_path).read_text(encoding="utf-8")))
    if not model:
        raise ValueError("openai-chat requires --formulation-model or --candidate-model")
    return OpenAICompatibleChatProvider(model=model, base_url=base_url)


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    try:
        case = BusinessCase.model_validate_json(Path(args.input).read_text(encoding="utf-8"))
        fp = _provider(args.formulation_provider, args.mock_formulation, args.formulation_model, args.base_url)
        cp = _provider(args.candidate_provider, args.mock_candidate, args.candidate_model, args.base_url)
        review = (HumanReviewV02.model_validate_json(Path(args.review).read_text(encoding="utf-8"))
                  if args.review else None)
        core = (MockCorePort(MockCoreScenario.model_validate_json(Path(args.mock_core).read_text(encoding="utf-8")))
                if args.mock_core else None)
        result = GatewayV03(fp, core=core, candidate_provider=cp).run(
            case, human_review=review, allow_mock_preview=args.allow_mock_preview)
        payload = {
            "formulation": result.formulation.model_dump(mode="json"),
            "routing": result.routing.model_dump(mode="json"),
            "candidate": result.candidate.model_dump(mode="json") if result.candidate else None,
        }
        output = (json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json"
                  else render_candidate_text(result.routing, result.candidate))
        if args.output:
            Path(args.output).write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0
    except (OSError, ValueError, ValidationError, ProviderError, ConfirmationError,
            CandidateNotAllowed, json.JSONDecodeError) as exc:
        # Avoid logging raw user material or any provider secret into stderr.
        print(f"Gateway stopped safely ({type(exc).__name__}); check input, review and provider settings.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
