"""v0.9: business narrative and optional documents -> multiple draft causal queries.

Never a mathematics backend. Online external sharing requires explicit double opt-in
when using attachments. No API key is needed for --preview or offline mock fixtures.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .document_intake import AttachmentError, AttachmentRequestV07
from .material_integrity import create_grounded_intake, review_grounded_intake
from .multisource_intake_cli import _load_manifest
from .multiquery_formulator import MultiQueryFormulatorV09, MultiQueryValidationError
from .multiquery import render_multiquery_text
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .schemas import BusinessCase


def parser():
    p = argparse.ArgumentParser(description="CFM-ID v0.9: one business -> several audited candidate causal queries")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", help="Document manifest with business description and attachments")
    group.add_argument("--question", help="Natural-language business description")
    group.add_argument("--case-json", help="Previously extracted BusinessCase JSON")
    p.add_argument("--case-id", default="business_v09")
    p.add_argument("--attachment", action="append", default=[])
    p.add_argument("--provider", choices=("mock", "openai-chat"), default="mock")
    p.add_argument("--mock-response", help="Offline MultiQueryDraftV09 JSON fixture")
    p.add_argument("--model", help="Online Chat Completions JSON-capable model")
    p.add_argument("--base-url", default="https://api.openai.com/v1")
    p.add_argument("--allow-external", action="store_true")
    p.add_argument("--allow-document-sharing", action="store_true")
    p.add_argument("--preview", action="store_true", help="Summarize files without sending anything to LLM")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--output")
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        intake = None
        if args.case_json:
            if args.attachment:
                raise ValueError("Cannot mix --case-json and --attachment")
            case = BusinessCase.model_validate_json(Path(args.case_json).read_text(encoding="utf-8"))
        else:
            if args.manifest:
                if args.attachment:
                    raise ValueError("Cannot add --attachment to a manifest")
                case_id, question, language, files = _load_manifest(Path(args.manifest))
            else:
                case_id, question, language = args.case_id, args.question, "zh"
                files = [AttachmentRequestV07(path=x) for x in args.attachment]
            intake = create_grounded_intake(case_id=case_id, business_question=question,
                                            attachments=files, response_language=language)
            case = intake.case
        if args.preview:
            preview = {"case_id": case.case_id, "source_count": len(case.sources),
                       "attachments": [{"name": x.display_name, "mode": x.mode,
                                        "warnings": x.warnings} for x in intake.attachments] if intake else [],
                       "llm_called": False, "mathematical_verification": "NOT_PERFORMED"}
            result = json.dumps(preview, ensure_ascii=False, indent=2) if args.format == "json" else (
                f"已读取业务描述与 {len(case.sources)} 份资料；未调用模型或数学识别。"
                + ("\n" + "\n".join(f"• {x.display_name}: {x.mode}" for x in intake.attachments) if intake else ""))
        else:
            if args.provider == "mock":
                if not args.mock_response:
                    raise ValueError("Offline mock requires --mock-response")
                provider = MockProvider(json.loads(Path(args.mock_response).read_text(encoding="utf-8")))
            else:
                if not args.allow_external:
                    p.error("Online provider requires --allow-external")
                if (case.sources or intake and intake.attachments) and not args.allow_document_sharing:
                    p.error("Sharing business source texts online requires --allow-document-sharing")
                if not args.model:
                    raise ValueError("Online provider requires --model")
                provider = OpenAICompatibleChatProvider(model=args.model, base_url=args.base_url)
            report = MultiQueryFormulatorV09(provider).formulate(case)
            quality = review_grounded_intake(intake, report.primary_formulation) if intake is not None else None
            if args.format == "json":
                result = json.dumps({"formulation": report.model_dump(mode="json"),
                                     "material_review": quality.model_dump(mode="json") if quality else None},
                                    ensure_ascii=False, indent=2)
            else:
                result = render_multiquery_text(report)
                if quality and quality.findings:
                    result += "\n材料审查提示：" + "；".join(x.explanation for x in quality.findings[:5])
        if args.output:
            Path(args.output).write_text(result + "\n", encoding="utf-8")
        else:
            print(result)
        return 0
    except (OSError, ValueError, ProviderError, AttachmentError, MultiQueryValidationError, json.JSONDecodeError) as exc:
        print(f"v0.9 formulation stopped without mathematical conclusions ({type(exc).__name__}).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
