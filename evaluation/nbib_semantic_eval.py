"""NBIB v0.1 A0 semantics benchmark harness for standalone Gateway v0.10.

- Model input: ONLY PUBLIC cases and local file summaries.
- Targets/labels: RESEARCH_ONLY, never shared in LLM prompt.
- Automatic metric: target-kind coverage + schema/provenance, NOT causal
  identification accuracy or rigorous semantic equivalence.
- Human worksheet: unscored until actual expert annotation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from cfm_id_llm.document_intake import AttachmentRequestV07
from cfm_id_llm.material_integrity import create_grounded_intake
from cfm_id_llm.providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from cfm_id_llm.providers.cli_options import add_chat_arguments, chat_options
from cfm_id_llm.quality_prompts import PROMPT_VERSION_V010
from cfm_id_llm.quality_formulator import A0QualityFormulatorV010
from cfm_id_llm.quality import (
    BusinessInquiryV010, MultiQueryDraftV010, QuerySemanticsV010,
)
from cfm_id_llm.schemas import (
    DraftProblemSpec, EvidenceQuote, SemanticClaim, SourceKind,
    TargetDraft, TargetKind,
)
from evaluation.multiquery_eval import score_targets

ROOT = Path(__file__).parent / 'nbib'
PUBLIC = ROOT / 'public' / 'cases'
REFERENCE = ROOT / 'research_only' / 'target_reference.json'

# NBIB v0.1 source descriptions have some formal terms; do not claim blind,
# leakage-free real-world score. Keep originals verbatim for auditability.
PREFERRED = ('study_protocol.md','data_dictionary.md','design_probabilities.csv',
             'cluster_randomization.csv','network_edges.csv','units.csv',
             'candidate_policies.csv','core_collaborators.csv','network_after.csv',
             'market_episodes.csv','treatment.csv','outcomes.csv')


def load_reference(path: Path = REFERENCE) -> list[dict]:
    cases = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(cases,list):
        raise ValueError('NBIB references must be a list')
    return cases


def load_public_business_case(case_id: str, *, root: Path = PUBLIC):
    folder = (root / case_id).resolve()
    if not folder.is_relative_to(root.resolve()) or not folder.is_dir():
        raise ValueError('Invalid public NBIB case directory')
    manifest = json.loads((folder/'submission_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('case_id') != case_id:
        raise ValueError('NBIB manifest case id mismatch')
    question = (folder/'business_question.md').read_text(encoding='utf-8').strip()
    declared = set(manifest['supporting_files'])
    chosen = [x for x in PREFERRED if x in declared]
    for name in chosen:
        if not (folder/name).is_file():
            raise ValueError('NBIB declared public attachment is missing')
    attachment_paths = chosen[:8]
    attachments = [AttachmentRequestV07(
        path=str(folder/name),
        kind=(SourceKind.STUDY_PROTOCOL if name == 'study_protocol.md' else
              SourceKind.DATA_DICTIONARY if name == 'data_dictionary.md' else SourceKind.OTHER),
    ) for name in attachment_paths]
    intake = create_grounded_intake(case_id=case_id, business_question=question,
                                    attachments=attachments,response_language='zh')
    omitted = sorted(declared - set(attachment_paths))
    if omitted:
        intake.warnings.append('ATTACHMENT_LIMIT_OMITTED: ' + ', '.join(omitted))
    return intake


def make_reference_only_fixture(entry: dict) -> dict:
    """Target-only fixtures intentionally leave A2-A6 and new semantics unresolved."""
    queries=[]
    for i,item in enumerate(entry['expected'],1):
        evidence = EvidenceQuote(source_id='business_question',quote=item['quote'])
        claim = SemanticClaim(value=item['quote'],basis='EXPLICIT_TEXT',evidence=[evidence])
        target = TargetDraft(kind=TargetKind(item['kind']),description=claim)
        queries.append(BusinessInquiryV010(query_id=f'q{i}',business_goal=claim,target=target))
    return MultiQueryDraftV010(shared_draft=DraftProblemSpec(target=queries[0].target),
                                primary_query_id='q1',queries=queries).model_dump(mode='json')


def _worksheet_for(case_id,reference,report):
    return [dict(case_id=case_id,query_id=q.query_id,
                 predicted_target=q.target.kind.value,
                 business_goal=q.business_goal.value,
                 semantics=q.semantics.model_dump(mode='json'),
                 expected_target_kind=None, # annotator must align targets before adjudication
                 human_labels={
                     'business_goal_fidelity':None,
                     'intervention_comparator_fidelity':None,
                     'network_assignment_fidelity':None,
                     'policy_scope_fidelity':None,
                     'a4_a5_not_invented':None,
                     'critical_semantic_error':None,
                 },
                 reviewer_notes='') for q in report.draft.queries]


def evaluate(*, provider_name: str = 'reference-fixture', model: str | None = None,
             max_cases: int | None = None, allow_external: bool = False,
             allow_document_sharing: bool = False, base_url: str = 'https://api.openai.com/v1',
             fixtures_dir: Path | None = None, public_dir: Path = PUBLIC,
             ref_path: Path = REFERENCE, timeout: float = 60.0, stream: bool = False,
             max_stream_seconds: float = 300.0, max_completion_tokens: int | None = None,
             thinking: str | None = None, json_mode: bool = True,
             max_tokens: int | None = None, require_finish_reason: bool = False) -> tuple[dict,dict]:
    if provider_name == 'openai-chat' and not (allow_external and allow_document_sharing):
        raise ValueError('External and document sharing consent both required')
    entries = load_reference(ref_path)
    if max_cases is not None:
        if max_cases < 1:
            raise ValueError('max_cases must be positive')
        entries=entries[:max_cases]
    online = provider_name=='openai-chat'
    provider = (OpenAICompatibleChatProvider(model=model or '',base_url=base_url,
                timeout=timeout, stream=stream, max_stream_seconds=max_stream_seconds,
                max_completion_tokens=max_completion_tokens, thinking=thinking,
                max_tokens=max_tokens, require_finish_reason=require_finish_reason,
                json_mode=json_mode) if online else None)
    rows=[]; worksheets=[]
    for entry in entries:
        case_id=entry['case_id']
        expected = [item['kind'] for item in entry['expected']]
        if online:
            provider.last_diagnostics = {}
        try:
            intake=load_public_business_case(case_id,root=public_dir)
            case=intake.case
            if provider_name=='reference-fixture':
                agent=MockProvider(make_reference_only_fixture(entry))
            elif provider_name=='mock':
                if fixtures_dir is None:
                    raise ValueError('Mock provider requires --fixtures-dir')
                agent=MockProvider(json.loads((fixtures_dir/f'{case_id}.json').read_text(encoding='utf-8')))
            else:
                agent=provider
            report=A0QualityFormulatorV010(agent).formulate(case)
            predicted=[q.target.kind.value for q in report.draft.queries]
            result={
                'case_id':case_id,'schema_and_quote_checks_passed':True,
                'expected_kinds':expected,'predicted_kinds':predicted,
                'business_status':report.overall_business_status,
                'query_semantic_statuses':[q.semantic_status for q in report.query_quality],
                'scientific_review_required':True,
                'source_warnings':intake.warnings,
                **score_targets(expected,predicted),
            }
            worksheets.extend(_worksheet_for(case_id,entry,report))
        except (ValueError,OSError,ProviderError) as exc:
            result={'case_id':case_id,'schema_and_quote_checks_passed':False,
                    'expected_kinds':expected,'error_kind':type(exc).__name__,
                    'error_code':getattr(exc,'code','INPUT_OR_IO_ERROR'),
                    'diagnostics':getattr(exc,'diagnostics',{}),
                    'scientific_review_required':True}
        if online:
            result['provider_diagnostics'] = dict(provider.last_diagnostics)
        rows.append(result)
    valid=[x for x in rows if x['schema_and_quote_checks_passed']]
    result={
        'benchmark':'CFM-ID-A0-NBIB-v0.10',
        'evaluation_kind':('ONLINE_MODEL_OUTPUT' if online else 'OFFLINE_REFERENCE_FIXTURE_ONLY'),
        'model':model if online else None,
        'prompt_version':PROMPT_VERSION_V010,
        'provider_request_attempts':sum(x.get('provider_diagnostics',{}).get('transport_calls',0) for x in rows),
        'source':'NBIB-v0.1 public cases + reviewed target-only labels (v2.9.1 package)',
        'nbib_v01_known_limitations':['PUBLIC_INPUT_HAS_A4_A5_TERMINOLOGY',
                                      'SEVEN_PRIORITY_REVIEW_ITEMS_OPEN',
                                      'NO_FORMAL_BACKED_CERTIFICATE_FOR_THESE_21_CASES'],
        'cases_total':len(rows), 'valid_schema_and_quotes':len(valid),
        'target_multiset_exact':sum(bool(x['exact_target_multiset']) for x in valid),
        'target_f1_mean_on_valid':(round(sum(x['target_f1'] for x in valid)/len(valid),4)
                                   if valid else None),
        'business_semantic_accuracy':'NOT_AUTOMATICALLY_SCORED_REQUIRES_EXPERT',
        'formal_math_accuracy':'NOT_MEASURED',
        'a4_a5_scientific_approval':'NOT_PERFORMED',
        'online_calls_made':online,
        'cases':rows,
    }
    worksheet={'benchmark':'CFM-ID-A0-NBIB-v0.10',
               'kind':'HUMAN_SEMANTIC_ADJUDICATION_TEMPLATE_UNSCORED',
               'allowed_label_values':[True,False,None],
               'notes':'Fill human_labels only after reading unaltered public materials and predictions. No labels are prefilled. Never treat this as a Core certificate.',
               'queries':worksheets}
    return result,worksheet


def score_human_review(worksheet: dict) -> dict:
    """Compute quality from ACTUAL human-provided booleans, never inferred from mocks."""
    labels=('business_goal_fidelity','intervention_comparator_fidelity',
            'network_assignment_fidelity','policy_scope_fidelity',
            'a4_a5_not_invented')
    all_rows=worksheet['queries']
    scores={}
    for label in labels:
        assessed=[r['human_labels'][label] for r in all_rows if type(r['human_labels'][label]) is bool]
        scores[label]={'reviewed':len(assessed),
                       'pass_rate':round(sum(assessed)/len(assessed),4) if assessed else None}
    critical=[r['human_labels']['critical_semantic_error'] for r in all_rows
              if type(r['human_labels']['critical_semantic_error']) is bool]
    return {'evaluation_kind':'HUMAN_ADJUDICATION_ONLY', 'query_count':len(all_rows),
            'critical_semantic_error_rate':round(sum(critical)/len(critical),4) if critical else None,
            'critical_semantic_error_reviewed':len(critical), 'fields':scores,
            'mathematical_certification':'NOT_PERFORMED'}


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description='NBIB v0.10 business-language model eval, no mathematical Core')
    p.add_argument('--provider',choices=('reference-fixture','mock','openai-chat'),default='reference-fixture')
    p.add_argument('--model')
    p.add_argument('--max-cases',type=int)
    p.add_argument('--base-url',default='https://api.openai.com/v1')
    add_chat_arguments(p)
    p.add_argument('--allow-external',action='store_true')
    p.add_argument('--allow-document-sharing',action='store_true')
    p.add_argument('--fixtures-dir')
    p.add_argument('--public-dir')
    p.add_argument('--reference')
    p.add_argument('--output')
    p.add_argument('--human-review-template')
    p.add_argument('--score-human-review',help='Only calculate rates from expert-filled annotations; do not call LLM')
    args=p.parse_args(argv)
    try:
        if args.score_human_review:
            response=score_human_review(json.loads(Path(args.score_human_review).read_text(encoding='utf-8')))
            template=None
        else:
            response,template=evaluate(provider_name=args.provider,model=args.model,max_cases=args.max_cases,
                allow_external=args.allow_external,allow_document_sharing=args.allow_document_sharing,
                base_url=args.base_url,
                fixtures_dir=Path(args.fixtures_dir) if args.fixtures_dir else None,
                public_dir=Path(args.public_dir) if args.public_dir else PUBLIC,
                ref_path=Path(args.reference) if args.reference else REFERENCE,
                **chat_options(args))
        message=json.dumps(response,ensure_ascii=False,indent=2)+'\n'
        if args.output:
            Path(args.output).write_text(message,encoding='utf-8')
        else:
            print(message)
        if args.human_review_template and template is not None:
            Path(args.human_review_template).write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return 0
    except (ValueError,OSError,ProviderError,json.JSONDecodeError) as exc:
        print(f'NBIB v0.10 evaluation stopped ({type(exc).__name__}).',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
