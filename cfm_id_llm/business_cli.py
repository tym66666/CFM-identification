"""v0.5 business-facing CLI: one sentence in, careful explanation out.

No official theorem adapter is bundled. Mock previews are clearly labelled.
Cloud calls require explicit --allow-external and a configured API key.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .business_presentation import Audience, explain_business, render_business_html, render_business_text
from .business_prompts import BUSINESS_SYSTEM_PROMPT_V05, PROMPT_VERSION_V05
from .candidate_reasoner import CandidateReasonerV03, GatewayRunV03, CandidateNotAllowed
from .formulator import ProblemFormulator, DraftValidationError
from .mock_core import MockCorePort, MockCoreScenario
from .orchestration_schemas import HumanReviewV02
from .orchestrator import ConfirmationError, route_formulation
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .schemas import BusinessCase


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='CFM-ID Gateway v0.5: natural business question and accessible result')
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--question', help='Natural business question, no JSON required')
    source.add_argument('--input', help='BusinessCase JSON with optional study protocol')
    p.add_argument('--case-id', default='business_demo')
    p.add_argument('--audience', choices=[x.value for x in Audience], default='business')
    p.add_argument('--formulation-provider', choices=('mock', 'openai-chat'), default='mock')
    p.add_argument('--mock-formulation', help='Mock DraftProblemSpec JSON fixture')
    p.add_argument('--formulation-model', help='Actual model, if using cloud API')
    p.add_argument('--candidate-provider', choices=('none', 'mock', 'openai-chat'), default='none')
    p.add_argument('--mock-candidate', help='Mock unverified candidate fixture')
    p.add_argument('--candidate-model')
    p.add_argument('--mock-core', help='Mock core scenario; never certified')
    p.add_argument('--review', help='Explicit signed-off researcher review, bound to the exact draft')
    p.add_argument('--allow-mock-preview', action='store_true', help='Opt in to mock unsupported -> LLM preview')
    p.add_argument('--allow-external', action='store_true', help='Confirm consent for external LLM request')
    p.add_argument('--base-url', default='https://api.openai.com/v1')
    p.add_argument('--format', choices=('text', 'json', 'html'), default='text')
    p.add_argument('--output', help='Output path; HTML output never executes LLM-generated code')
    return p


def _provider(kind: str, mock_path: str | None, model: str | None, base_url: str):
    if kind == 'none':
        return None
    if kind == 'mock':
        if not mock_path:
            raise ValueError('mock provider requires --mock-formulation / --mock-candidate')
        return MockProvider(json.loads(Path(mock_path).read_text(encoding='utf-8')))
    if not model:
        raise ValueError('online provider requires an explicit model name')
    return OpenAICompatibleChatProvider(model=model, base_url=base_url)


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if (args.formulation_provider == 'openai-chat' or args.candidate_provider == 'openai-chat') and not args.allow_external:
        p.error('Online requests require --allow-external and permission to send the business material.')
    try:
        case = (BusinessCase.model_validate_json(Path(args.input).read_text(encoding='utf-8'))
                if args.input else BusinessCase(case_id=args.case_id, business_question=args.question))
        fp = _provider(args.formulation_provider, args.mock_formulation, args.formulation_model, args.base_url)
        cp = _provider(args.candidate_provider, args.mock_candidate, args.candidate_model, args.base_url)
        review = (HumanReviewV02.model_validate_json(Path(args.review).read_text(encoding='utf-8'))
                  if args.review else None)
        core = (MockCorePort(MockCoreScenario.model_validate_json(Path(args.mock_core).read_text(encoding='utf-8')))
                if args.mock_core else None)
        form = ProblemFormulator(fp, system_prompt=BUSINESS_SYSTEM_PROMPT_V05,
                                prompt_version=PROMPT_VERSION_V05).formulate(case)
        route = route_formulation(case, form, human_review=review, core=core)
        candidate = None
        if review is not None and cp is not None and (
                (route.status == 'CORE_UNSUPPORTED' and route.fallback == 'ELIGIBLE_NOT_IMPLEMENTED') or
                (args.allow_mock_preview and route.status == 'MOCK_CORE_RESULT'
                 and route.core_status == 'UNSUPPORTED' and route.fallback == 'MOCK_ONLY')):
            candidate = CandidateReasonerV03(cp).run(
                case=case, formulation=form, human_review=review,
                routing=route, allow_mock_preview=args.allow_mock_preview,
            )
        view = explain_business(case, GatewayRunV03(form, route, candidate), audience=args.audience)
        if args.format == 'json':
            content = view.model_dump_json(indent=2)
        elif args.format == 'html':
            content = render_business_html(view)
        else:
            content = render_business_text(view)
        if args.output:
            Path(args.output).write_text(content + '\n', encoding='utf-8')
        else:
            print(content)
        return 0
    except (OSError, ValueError, ProviderError, DraftValidationError, ConfirmationError,
            CandidateNotAllowed, json.JSONDecodeError) as exc:
        # Do not echo external provider payload, keys, or original private business text.
        print(f'Business demo stopped safely ({type(exc).__name__}). Check data, consent and model settings.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
