"""Natural-business benchmark: natural wording in, unverified A1-A6 draft out.

Reference notes never enter prompts. This tool measures schema/evidence integrity
and rough target agreement, NOT identification proof or real-world outcome value.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

from cfm_id_llm.business_prompts import BUSINESS_SYSTEM_PROMPT_V05, PROMPT_VERSION_V05
from cfm_id_llm.formulator import ProblemFormulator
from cfm_id_llm.providers import OpenAICompatibleChatProvider, ProviderError
from cfm_id_llm.schemas import BusinessCase


def load_cases(path: Path | None = None) -> list[dict]:
    data = json.loads((path or Path(__file__).with_name('business_cases.json')).read_text(encoding='utf-8'))
    if data.get('dataset_version') != 'cfm-id-real-business-v0.5':
        raise ValueError('Unsupported business benchmark version')
    cases=data.get('cases')
    if not isinstance(cases,list) or not cases:
        raise ValueError('Missing business cases')
    ids=[c['id'] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case ids')
    for c in cases:
        business=BusinessCase.model_validate(c['business_case'])
        if business.case_id != c['id']:
            raise ValueError('Benchmark ID mismatch')
    return cases


def run_one(case_data: dict, provider) -> dict:
    """Send ONLY business_case to model, never reference_for_developers_only."""
    business=BusinessCase.model_validate(case_data['business_case'])
    try:
        report=ProblemFormulator(provider,system_prompt=BUSINESS_SYSTEM_PROMPT_V05,
                                 prompt_version=PROMPT_VERSION_V05).formulate(business)
    except (ValueError,TypeError,ProviderError) as exc:
        return {'id':business.case_id,'status':'PROVIDER_OR_SCHEMA_FAILURE',
                'error_type':type(exc).__name__, 'provider':provider.name,
                'reference_agreement':'NOT_SCORED'}
    allowed=case_data['reference_for_developers_only']['plausible_target_kinds']
    return {
        'id':business.case_id,'status':report.review_status,
        'reported_target':report.draft.target.kind.value,
        'reported_assignment':report.draft.information_design.assignment_family.value,
        'target_matches_developer_hint':report.draft.target.kind.value in allowed,
        'unresolved_questions':len(report.suggested_questions),
        'issue_codes':[x.code for x in report.issues],
        'prompt_version':report.prompt_version,
        'provider':report.provider,
        'reference_agreement':'DEVELOPER_HINT_ONLY_NOT_MATH_PROOF',
    }


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description='CFM-ID Gateway v0.5 natural business LLM benchmark')
    p.add_argument('--dry-run',action='store_true',help='List cases only; no model calls')
    p.add_argument('--all-cases',action='store_true')
    p.add_argument('--max-cases',type=int,default=4)
    p.add_argument('--case-id',action='append',help='Select one or multiple Bxx cases')
    p.add_argument('--provider',choices=('openai-chat',),default='openai-chat')
    p.add_argument('--model',help='JSON-capable chat model (required for live)')
    p.add_argument('--allow-external',action='store_true',help='Explicit consent to transmit synthetic cases')
    p.add_argument('--base-url',default='https://api.openai.com/v1')
    p.add_argument('--output',help='Save JSON report')
    args=p.parse_args(argv)
    try:
        items=load_cases()
        if args.case_id:
            ids=set(args.case_id)
            selected=[c for c in items if c['id'] in ids]
            if len(selected)!=len(ids):
                raise ValueError('Unknown case id')
        else:
            if not 1 <= args.max_cases <= len(items):
                raise ValueError('max-cases out of range')
            selected=items if args.all_cases else items[:args.max_cases]
        if args.dry_run:
            print(json.dumps({'dataset_version':'cfm-id-real-business-v0.5','selected':len(selected),
                'cases':[{'id':x['id'],'category':x['category'],
                          'question':x['business_case']['business_question']} for x in selected],
                'live_llm_called':False},ensure_ascii=False,indent=2))
            return 0
        if not args.allow_external or not args.model:
            raise ValueError('Actual LLM benchmark needs --allow-external and --model')
        provider=OpenAICompatibleChatProvider(model=args.model,base_url=args.base_url)
        rows=[run_one(x,provider) for x in selected]
        output={
            'schema_version':'cfm-id-business-benchmark-report-v0.5',
            'generated_utc':datetime.now(timezone.utc).isoformat(),
            'provider':provider.name,'prompt_version':PROMPT_VERSION_V05,
            'cases':rows,'cases_attempted':len(rows),
            'live_llm_called':True,
            'disclaimer':'Matching developer hints is only a rough semantic check; it is not mathematical identification correctness, proof, or causal estimation.',
        }
        data=json.dumps(output,ensure_ascii=False,indent=2)
        if args.output: Path(args.output).write_text(data+'\n',encoding='utf8')
        else:print(data)
        return 0
    except (ValueError,OSError,TypeError) as exc:
        print(f'Business benchmark stopped safely ({type(exc).__name__}). Check model, consent and dataset.',file=sys.stderr)
        return 2

if __name__=='__main__': raise SystemExit(main())
