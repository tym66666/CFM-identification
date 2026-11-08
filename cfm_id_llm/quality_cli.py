"""Standalone Gateway v0.10 A0 business formulation CLI; mathematical Core never imported.

Files can be previewed locally.  For online providers both explicit external and
source-sharing consent are required; no credentials enter log or output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .document_intake import AttachmentError, AttachmentRequestV07
from .material_integrity import create_grounded_intake, review_grounded_intake
from .multiquery import MultiQueryDraftV09
from .multisource_intake_cli import _load_manifest
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .providers.cli_options import add_chat_arguments, chat_options
from .quality_formulator import A0QualityFormulatorV010, A0QualityValidationError
from .quality_prompts import PROMPT_VERSION_V010
from .quality import draft_from_v09, audit_business_quality
from .schemas import BusinessCase


def make_parser():
    p = argparse.ArgumentParser(description='CFM-ID LLM Gateway v0.10: business-first A0 quality, no Core')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--manifest')
    g.add_argument('--question')
    g.add_argument('--case-json')
    p.add_argument('--case-id', default='a0_business_v010')
    p.add_argument('--attachment', action='append', default=[])
    p.add_argument('--provider', choices=('mock', 'openai-chat'), default='mock')
    p.add_argument('--mock-response', help='A0 v0.10 JSON response fixture')
    p.add_argument('--legacy-v09-fixture', help='Explicit migration of v0.9 response (all new slots unresolved)')
    p.add_argument('--model')
    p.add_argument('--base-url', default='https://api.openai.com/v1')
    add_chat_arguments(p)
    p.add_argument('--allow-external', action='store_true')
    p.add_argument('--allow-document-sharing', action='store_true')
    p.add_argument('--preview', action='store_true', help='read attachments without an LLM call')
    p.add_argument('--format', choices=('text','json'), default='text')
    p.add_argument('--output')
    return p


def render_business_review(report) -> str:
    result = [f'业务案例 {report.case_id}：{report.overall_business_status}',
              f'查询数量：{len(report.query_quality)}；科学审核：仍需独立进行（未调用数学库）']
    for q in report.query_quality:
        r = next(x for x in report.draft.queries if x.query_id == q.query_id)
        result.append(f'\n{q.query_id}：{r.business_goal.value}')
        result.append(f'业务理解：{q.business_status}；语义草稿：{q.semantic_status}')
        for question in q.business_questions[:2]:
            result.append(f'  必要业务澄清：{question.question}')
        for action in q.actions[:5]:
            owner = '业务问题复查' if action.owner == 'A0_FORMULATOR' else (
                '数学研究者审核' if action.owner == 'SCIENTIFIC_REVIEWER' else '业务人员澄清')
            result.append(f'  {owner}：{action.detail}')
    result.append('\n所有结果均为 LLM 候选规范化；无 POINT、无证书、无 Estimation 权限。')
    return '\n'.join(result)


def main(argv: list[str] | None = None) -> int:
    p = make_parser(); args = p.parse_args(argv)
    provider = None
    try:
        intake = None
        if args.case_json:
            if args.attachment:
                raise ValueError('Do not mix case-json and attachments')
            case = BusinessCase.model_validate_json(Path(args.case_json).read_text(encoding='utf-8'))
        else:
            if args.manifest:
                if args.attachment:
                    raise ValueError('Do not mix manifest and attachments')
                case_id, question, language, files = _load_manifest(Path(args.manifest))
            else:
                case_id, question, language = args.case_id, args.question, 'zh'
                files = [AttachmentRequestV07(path=x) for x in args.attachment]
            intake = create_grounded_intake(case_id=case_id, business_question=question,
                                            attachments=files, response_language=language)
            case = intake.case
        if args.preview:
            data = {'case_id':case.case_id, 'source_count':len(case.sources),
                    'attachment_warnings': (intake.warnings if intake else []),
                    'llm_called':False, 'core_called':False}
            message = json.dumps(data,ensure_ascii=False,indent=2) if args.format=='json' else (
                f'材料已读取：{case.case_id}, 共{len(case.sources)}份附件。未调用LLM或数学库。')
        else:
            if args.legacy_v09_fixture:
                if args.provider != 'mock' or args.mock_response:
                    raise ValueError('Legacy fixture migration is offline-only and mutually exclusive')
                raw = json.loads(Path(args.legacy_v09_fixture).read_text(encoding='utf-8'))
                draft = draft_from_v09(MultiQueryDraftV09.model_validate(raw))
                result = audit_business_quality(case,draft,provider='v09-fixture-migration',
                                                prompt_version='v0.9-fixture-explicit-migration')
            else:
                if args.provider=='mock':
                    if not args.mock_response:
                        raise ValueError('mock requires --mock-response')
                    provider = MockProvider(json.loads(Path(args.mock_response).read_text(encoding='utf-8')))
                else:
                    if not args.allow_external:
                        p.error('Online provider requires --allow-external')
                    if case.sources and not args.allow_document_sharing:
                        p.error('Online source sharing requires --allow-document-sharing')
                    if not args.model:
                        raise ValueError('Online provider requires --model')
                    provider = OpenAICompatibleChatProvider(model=args.model, base_url=args.base_url,
                                                            **chat_options(args))
                result = A0QualityFormulatorV010(provider).formulate(case)
            material = review_grounded_intake(intake,result.legacy_audit.primary_formulation) if intake else None
            if args.format=='json':
                message=json.dumps({'formulation':result.model_dump(mode='json'),
                    'material_review':material.model_dump(mode='json') if material else None,
                    'provider_diagnostics':getattr(provider, 'last_diagnostics', {})},
                    ensure_ascii=False,indent=2)
            else:
                message=render_business_review(result)
                if material and material.findings:
                    message+='\n材料风险：'+'；'.join(f.explanation for f in material.findings[:5])
        if args.output:
            Path(args.output).write_text(message+'\n',encoding='utf-8')
        else:
            print(message)
        return 0
    except (OSError,ValueError,ProviderError,AttachmentError,A0QualityValidationError,
            json.JSONDecodeError) as exc:
        code = getattr(exc, 'code', 'INPUT_OR_IO_ERROR')
        if args.format == 'json':
            failure = {'status':'REJECTED', 'error_kind':type(exc).__name__, 'error_code':code,
                       'diagnostics':getattr(exc, 'diagnostics', {}),
                       'provider_diagnostics':getattr(provider, 'last_diagnostics', {}),
                       'core_called':False, 'estimation_handoff_allowed':False,
                       'scientific_review_required':True, 'prompt_version':PROMPT_VERSION_V010}
            message = json.dumps(failure, ensure_ascii=False, indent=2) + '\n'
            if args.output:
                try:
                    Path(args.output).write_text(message, encoding='utf-8')
                except OSError:
                    print('Could not save failure diagnostics.', file=sys.stderr)
            else:
                print(message, end='')
        print(f'A0 v0.10 stopped without certification ({type(exc).__name__}; {code}).',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
