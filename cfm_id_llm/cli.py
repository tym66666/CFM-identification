"""Offline-first CLI. No network access unless provider=openai-chat is explicit."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from pydantic import ValidationError
from .formulator import DraftValidationError, ProblemFormulator
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .reporting import render_text
from .schemas import BusinessCase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CFM-ID Gateway v0.1: business -> A0–A6 unverified draft")
    parser.add_argument("--input", required=True, help="BusinessCase JSON")
    parser.add_argument("--provider", choices=["mock", "openai-chat"], default="mock")
    parser.add_argument("--mock-response", help="Fixture JSON, required if provider=mock")
    parser.add_argument("--model", help="Explicit model name, required if provider=openai-chat")
    parser.add_argument("--base-url", default="https://api.openai.com/v1", help="Chat-compatible endpoint; HTTPS or localhost")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--output", help="Report output file (optional)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.provider == "mock" and not args.mock_response:
        parser.error("--mock-response is required for mock provider")
    if args.provider == "openai-chat" and not args.model:
        parser.error("--model is required for openai-chat provider")
    try:
        case = BusinessCase.model_validate_json(Path(args.input).read_text(encoding="utf-8"))
        if args.provider == "mock":
            provider = MockProvider(json.loads(Path(args.mock_response).read_text(encoding="utf-8")))
        else:
            provider = OpenAICompatibleChatProvider(model=args.model, base_url=args.base_url)
        report = ProblemFormulator(provider).formulate(case)
    except (OSError, ValueError, ValidationError, ProviderError, DraftValidationError, json.JSONDecodeError) as exc:
        print(f"Gateway failed safely: {exc}", file=sys.stderr)
        return 2
    output = (report.model_dump_json(indent=2) if args.format == "json" else render_text(report))
    if args.output:
        try:
            Path(args.output).write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Could not write report: {type(exc).__name__}", file=sys.stderr)
            return 2
    else:
        print(output)
    return 0
