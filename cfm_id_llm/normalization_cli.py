"""Independent v0.6 CLI for natural language -> grounded draft -> clarification.

Usage:
  python -m cfm_id_llm.normalization_cli formulate --case examples/sales_ambiguous.json --provider mock --mock-response examples/sales_ambiguous_mock_response.json
  python -m cfm_id_llm.normalization_cli apply-answer --case ... --review ... --answer ... --output ...

Online requests require explicit --allow-external and are never used by tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .formulator import ProblemFormulator
from .normalization_prompts import BUSINESS_SYSTEM_PROMPT_V06, PROMPT_VERSION_V06
from .normalization import (
    ClarificationAnswerV06, NormalizationReviewV06, append_clarification,
    build_normalization_review, render_review_text,
)
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .schemas import BusinessCase


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='CFM-ID Gateway v0.6: explain business -> audited draft')
    sub = p.add_subparsers(dest='command', required=True)
    first = sub.add_parser('formulate', help='create a grounded draft, not a theorem result')
    src = first.add_mutually_exclusive_group(required=True)
    src.add_argument('--question', help='everyday business question')
    src.add_argument('--case', help='BusinessCase JSON file, may include study protocols')
    first.add_argument('--case-id', default='plain_business')
    first.add_argument('--provider', choices=('mock', 'openai-chat'), default='mock')
    first.add_argument('--mock-response', help='prepared mock DraftProblemSpec JSON')
    first.add_argument('--model', help='online model name')
    first.add_argument('--base-url', default='https://api.openai.com/v1')
    first.add_argument('--allow-external', action='store_true', help='explicit permission to send case to provider')
    first.add_argument('--format', choices=('text', 'json'), default='text')
    first.add_argument('--output', help='save review, same format as --format')
    first.add_argument('--case-output', help='save BusinessCase JSON for future clarification replies')

    later = sub.add_parser('apply-answer', help='append a user answer as unverified source')
    later.add_argument('--case', required=True)
    later.add_argument('--review', required=True, help='JSON normalization review')
    later.add_argument('--answer', required=True, help='ClarificationAnswerV06 JSON')
    later.add_argument('--output', required=True, help='write enriched BusinessCase JSON')
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command == 'apply-answer':
            case = BusinessCase.model_validate_json(Path(args.case).read_text(encoding='utf-8'))
            review = NormalizationReviewV06.model_validate_json(Path(args.review).read_text(encoding='utf-8'))
            answer = ClarificationAnswerV06.model_validate_json(Path(args.answer).read_text(encoding='utf-8'))
            updated = append_clarification(case, review, answer)
            Path(args.output).write_text(updated.model_dump_json(indent=2) + '\n', encoding='utf-8')
            print('已保存补充说明；需要重新运行 LLM 规范化和审核。此补充未自动成为认证事实。')
            return 0

        case = (BusinessCase.model_validate_json(Path(args.case).read_text(encoding='utf-8'))
                if args.case else BusinessCase(case_id=args.case_id, business_question=args.question))
        if args.provider == 'mock':
            if not args.mock_response:
                raise ValueError('Mock provider requires --mock-response')
            provider = MockProvider(json.loads(Path(args.mock_response).read_text(encoding='utf-8')))
        else:
            if not args.allow_external:
                p.error('Online requests require --allow-external and permission to send business material')
            if not args.model:
                raise ValueError('Online provider requires --model')
            provider = OpenAICompatibleChatProvider(model=args.model, base_url=args.base_url)
        form = ProblemFormulator(provider, system_prompt=BUSINESS_SYSTEM_PROMPT_V06,
                                 prompt_version=PROMPT_VERSION_V06).formulate(case)
        review = build_normalization_review(case, form)
        content = review.model_dump_json(indent=2) if args.format == 'json' else render_review_text(review)
        if args.output:
            Path(args.output).write_text(content + '\n', encoding='utf-8')
        else:
            print(content)
        if args.case_output:
            Path(args.case_output).write_text(case.model_dump_json(indent=2) + '\n', encoding='utf-8')
        return 0
    except (OSError, ValueError, ProviderError, json.JSONDecodeError) as exc:
        # No private business data, model payload or credentials in CLI error details.
        print(f'Normalization stopped safely ({type(exc).__name__}). Check case, report and provider settings.',
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
