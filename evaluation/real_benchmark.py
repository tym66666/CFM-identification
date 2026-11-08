"""Reproducible benchmark runner for live JSON LLM providers and offline fixtures.

Stage A: noisy business description -> A1-A6 formulation.
Stage B: *frozen synthetic benchmark question* -> v0.3 CandidateReasoner.

No gold/reference fields are passed to providers. Claims/formulae are NOT graded
as mathematically correct by string matching; manual independent review required.
This module does not connect to or certify a production Identification Library.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from typing import Any

from cfm_id_llm.audit import audit_draft
from cfm_id_llm.candidate_reasoner import CandidateReasonerV03
from cfm_id_llm.formulator import ProblemFormulator
from cfm_id_llm.providers import MockProvider, OpenAICompatibleChatProvider
from cfm_id_llm.prompts import PROMPT_VERSION as FORMULATOR_PROMPT_VERSION
from cfm_id_llm.candidate_prompts import PROMPT_VERSION_V03 as CANDIDATE_PROMPT_VERSION
from cfm_id_llm.schemas import BusinessCase, DraftProblemSpec
from .frozen_problems import make_frozen_input

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / 'network_benchmark.json'
DEFAULT_FIXTURES = HERE / 'fixtures'
REVIEW_FIELDS = (
    'correct_causal_target', 'uses_only_admitted_assumptions', 'uses_valid_a4_information',
    'checks_domain_and_support', 'correct_identification_conclusion',
    'correct_formula_or_observational_equivalence',
)


def stable_sha256(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_benchmark(path: Path) -> dict:
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('dataset_version') != 'network-id-evaluation-v0.4':
        raise ValueError('Unsupported benchmark dataset version')
    ids=[]
    for stage in ('formulation','candidate'):
        entries=data[stage+'_cases']
        if not isinstance(entries,list) or len(entries)<1:
            raise ValueError('Expected nonempty benchmark cases')
        for item in entries:
            if not isinstance(item,dict) or not all(k in item for k in ('id','business_case','reference')):
                raise ValueError('Malformed benchmark entry')
            if item['id'] != item['business_case']['case_id']:
                raise ValueError('Case ID binding mismatch')
            ids.append(item['id'])
            BusinessCase.model_validate(item['business_case'])
            if stage=='candidate':
                make_frozen_input(item)  # validates exact quotes, test review, mock routing
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case IDs')
    return data


def choose_cases(data: dict, stages: tuple[str,...], *, case_ids: set[str]|None=None,
                 limit: int|None=None) -> list[tuple[str,dict]]:
    cases=[(stage,item) for stage in stages for item in data[stage+'_cases']]
    if case_ids:
        unknown = case_ids - {item['id'] for _,item in cases}
        if unknown:
            raise ValueError('Unknown case ID(s): '+','.join(sorted(unknown)))
        cases=[(stage,item) for stage,item in cases if item['id'] in case_ids]
    if limit is not None:
        if limit<1: raise ValueError('--max-cases must be positive')
        cases=cases[:limit]
    return cases


def formulation_score(reference: dict, draft: DraftProblemSpec, *, review_status: str) -> dict:
    dims={
        'target_kind':draft.target.kind.value,
        'assignment_family':draft.information_design.assignment_family.value,
        'a4_level':draft.information_design.population_information_level.value,
    }
    matches={k:dims[k]==reference[k] for k in dims}
    must=bool(reference['needs_clarification'])
    needs=review_status=='NEEDS_CLARIFICATION'
    # Conservative false-certification patterns: wrong upgrades over an unresolved assignment / A4.
    risk={
        'invented_assignment_when_unresolved': reference['assignment_family']=='UNRESOLVED'
                                             and dims['assignment_family']!='UNRESOLVED',
        'invented_population_law': reference['a4_level'] in ('UNRESOLVED','FINITE_SAMPLE_DESCRIPTION')
                                   and dims['a4_level'] not in ('UNRESOLVED','FINITE_SAMPLE_DESCRIPTION'),
        'target_misclassification':not matches['target_kind'],
    }
    return {
        'observed':dims,'field_matches':matches,'all_three_fields_match':all(matches.values()),
        'clarification_expected':must,'clarification_observed':needs,
        'clarification_match':(must==needs),'risk_flags':risk,
    }


def candidate_score(reference: dict, cand_report) -> dict:
    cand=cand_report.candidate
    result={
        'envelope_safe':(cand_report.verification_level=='LLM_UNVERIFIED'
                         and cand_report.estimation_handoff_allowed is False
                         and cand_report.mathematical_certificate is None),
        'claim_match':False,'scope_match':False,'a4_source_match':False,
        'required_kinds_covered':False,'reference_is_not_proof':True,
    }
    if cand is None:
        return result
    req={r.kind for r in cand.additional_requirements}
    expected=set(reference['required_requirement_kinds'])
    result.update({
        'candidate_claim':cand.claimed_identification,
        'candidate_scope':cand.scope,
        'claim_match':cand.claimed_identification==reference['expected_claim'],
        'scope_match':cand.scope==reference['scope'],
        'a4_source_match':cand.a4_used.source==reference['a4_source'],
        'required_kinds_covered':expected.issubset(req),
    })
    return result


def run_formulation(item: dict, provider) -> dict:
    case=BusinessCase.model_validate(item['business_case'])
    row={'id':item['id'],'stage':'formulation','risk_tags':item['reference'].get('risk_tags',[]),
         'attempted':True,'status':'FAILED','score':{},'output':None}
    try:
        rep=ProblemFormulator(provider).formulate(case)
        row['output']=rep.model_dump(mode='json')
        row['status']='VALID_DRAFT'
        row['score']=formulation_score(item['reference'],rep.draft,review_status=rep.review_status)
    except Exception as exc:
        row['status']='PROVIDER_OR_SCHEMA_FAILURE'
        row['error_type']=type(exc).__name__ # no raw text or key leakage
    return row


def run_candidate(item:dict, provider) -> dict:
    row={'id':item['id'],'stage':'candidate','risk_tags':item['reference'].get('risk_tags',[]),
         'attempted':True,'status':'FAILED','score':{},'output':None}
    try:
        case,formulation,review,routing=make_frozen_input(item)
        rep=CandidateReasonerV03(provider).run(case=case,formulation=formulation,
                                                 human_review=review,routing=routing,
                                                 allow_mock_preview=True)
        row['output']=rep.model_dump(mode='json')
        row['status']=rep.status
        row['score']=candidate_score(item['reference'],rep)
        row['setup']='SYNTHETIC_TEST_REVIEW_AND_MOCK_UNSUPPORTED_NOT_PRODUCTION'
    except Exception as exc:
        row['status']='RUNNER_FAILURE'
        row['error_type']=type(exc).__name__
    return row


def rollup(rows: list[dict]) -> dict:
    # All metrics are literal counts; cannot be interpreted as proof/LLM math accuracy.
    out={}
    for stage in ('formulation','candidate'):
        group=[r for r in rows if r['stage']==stage]
        if not group: continue
        scorekeys=(('all_three_fields_match','clarification_match') if stage=='formulation' else
                   ('claim_match','scope_match','a4_source_match','required_kinds_covered','envelope_safe'))
        counts={key:sum(r.get('score',{}).get(key) is True for r in group) for key in scorekeys}
        valid=sum((r['status']=='VALID_DRAFT' if stage=='formulation' else
                   r['status'] in ('UNVERIFIED_CANDIDATE','UNDETERMINED_UNVERIFIED')) for r in group)
        out[stage]={'attempted':len(group),'schema_and_gate_accepted':valid,'counts':counts,
                    'note':('Classification/clarification agreement only; references are synthetic, NOT a mathematical proof.'
                            if stage=='formulation' else
                            'Candidate label/scope agreement ONLY. Formula/witness correctness requires human review.')}
        if stage=='formulation':
            for risk in ('invented_assignment_when_unresolved','invented_population_law','target_misclassification'):
                out[stage].setdefault('risk_counts',{})[risk]=sum(r.get('score',{}).get('risk_flags',{}).get(risk) is True for r in group)
    return out


def make_adjudication_template(run:dict)->dict:
    records=[]
    for row in run['cases']:
        if row['stage']=='candidate' and row['status'] in ('UNVERIFIED_CANDIDATE','UNDETERMINED_UNVERIFIED'):
            records.append({
                'case_id':row['id'], 'reviewer_id':'', 'checks':{field:'NOT_REVIEWED' for field in REVIEW_FIELDS},
                'comments':'',
            })
    return {
        'schema_version':'cfm-id-math-adjudication-v0.4',
        'run_sha256':stable_sha256(run),
        'instructions':'Copy each record for TWO distinct human reviewers. PASS/FAIL/UNCERTAIN, with reasons. Never call this a formal theorem certificate.',
        'reviews':records,
    }


def adjudication_summary(run:dict, adjudication:dict)->dict:
    if adjudication.get('schema_version')!='cfm-id-math-adjudication-v0.4':
        raise ValueError('Wrong adjudication version')
    if adjudication.get('run_sha256')!=stable_sha256(run):
        raise ValueError('Adjudication file does not bind to this exact model run')
    expected={r['id'] for r in run['cases'] if r['stage']=='candidate'
              and r['status'] in ('UNVERIFIED_CANDIDATE','UNDETERMINED_UNVERIFIED')}
    seen={}
    for r in adjudication.get('reviews',[]):
        cid=r.get('case_id')
        if cid not in expected: raise ValueError('Unknown or ineligible case in manual adjudication')
        reviewer=r.get('reviewer_id','').strip()
        if not reviewer: continue
        if (cid,reviewer) in seen: raise ValueError('Duplicate reviewer/case')
        checks=r.get('checks',{})
        if set(checks)!=set(REVIEW_FIELDS) or any(v not in {'PASS','FAIL','UNCERTAIN','NOT_REVIEWED'} for v in checks.values()):
            raise ValueError('Invalid review checks')
        seen[cid,reviewer]=checks
    evaluated=agree_pass=disagreement=unresolved=0
    for cid in expected:
        available=[v for (case,_),v in seen.items() if case==cid and all(x in {'PASS','FAIL','UNCERTAIN'} for x in v.values())]
        if len(available)<2: continue
        evaluated+=1
        a,b=available[:2]
        if any(a[k]!=b[k] for k in REVIEW_FIELDS): disagreement+=1
        elif all(a[k]=='PASS' for k in REVIEW_FIELDS): agree_pass+=1
        else: unresolved+=1
    return {'candidate_cases_with_two_complete_reviews':evaluated,
            'two_reviewers_all_checks_pass':agree_pass,
            'reviewer_disagreements':disagreement,
            'reviewers_agree_not_all_pass':unresolved,
            'review_note':'Human evaluation, not a formal verification certificate. An absent decision is not a fail.'}


def main(argv: list[str]|None=None)->int:
    p=argparse.ArgumentParser(description='CFM-ID Gateway real LLM evaluation v0.4, or offline fixtures')
    p.add_argument('--dataset',type=Path,default=DEFAULT_DATASET)
    p.add_argument('--stage',choices=('formulation','candidate','both'),default='both')
    p.add_argument('--provider',choices=('fixtures','openai-chat'),default='fixtures')
    p.add_argument('--fixture-dir',type=Path,default=DEFAULT_FIXTURES)
    p.add_argument('--model',help='Explicit model for live Chat-Completions JSON API')
    p.add_argument('--base-url',default='https://api.openai.com/v1')
    p.add_argument('--timeout',type=float,default=75.0)
    p.add_argument('--max-completion-tokens',type=int,default=3500)
    p.add_argument('--max-cases',type=int)
    p.add_argument('--case-id',action='append',default=[])
    p.add_argument('--pause-seconds',type=float,default=0.0)
    p.add_argument('--allow-external',action='store_true',help='Consent to transmit the synthetic test prompts to configured API')
    p.add_argument('--all-cases',action='store_true',help='Explicitly allow all 46 API requests; costs may apply')
    p.add_argument('--dry-run',action='store_true',help='Inventory selected cases, NO model calls')
    p.add_argument('--output',type=Path,help='Write JSON report (with model drafts) to this path')
    p.add_argument('--adjudication-template',type=Path,help='Write empty manual mathematical-review template bound to report')
    args=p.parse_args(argv)
    try:
        if args.pause_seconds<0: raise ValueError('pause must be nonnegative')
        data=load_benchmark(args.dataset)
        stages=('formulation','candidate') if args.stage=='both' else (args.stage,)
        selected=choose_cases(data,stages,case_ids=set(args.case_id),limit=args.max_cases)
        if not selected: raise ValueError('No selected cases')
        if args.dry_run:
            inventory={'mode':'DRY_RUN_NO_MODEL_CALLS','dataset_sha256':stable_sha256(data),
                       'selected':len(selected),'cases':[{'stage':stage,'id':item['id']} for stage,item in selected]}
            print(json.dumps(inventory,ensure_ascii=False,indent=2));return 0
        if args.provider=='openai-chat':
            if not args.allow_external: raise ValueError('Live API requires explicit --allow-external')
            if not args.model: raise ValueError('Live API requires --model')
            if args.max_cases is None and not args.case_id and not args.all_cases:
                raise ValueError('Set --max-cases N or --all-cases to control API costs')
            if not (os.getenv('CFM_ID_LLM_API_KEY') or os.getenv('OPENAI_API_KEY')):
                raise ValueError('Missing CFM_ID_LLM_API_KEY or OPENAI_API_KEY; no online evaluation run')
            provider=OpenAICompatibleChatProvider(model=args.model,base_url=args.base_url,
                                                  timeout=args.timeout,max_completion_tokens=args.max_completion_tokens)
            run_kind='REAL_API'
        else:
            provider=None
            run_kind='OFFLINE_FIXTURES_NOT_MODEL_EVALUATION'
        rows=[]
        for ix,(stage,item) in enumerate(selected):
            if run_kind=='REAL_API':
                impl=provider
            else:
                fixture=args.fixture_dir / stage / (item['id']+'.json')
                if not fixture.is_file():
                    rows.append({'id':item['id'],'stage':stage,'status':'MISSING_FIXTURE',
                                 'attempted':False,'risk_tags':item['reference'].get('risk_tags',[]),
                                 'score':{},'output':None});continue
                impl=MockProvider(json.loads(fixture.read_text(encoding='utf-8')))
            row=run_formulation(item,impl) if stage=='formulation' else run_candidate(item,impl)
            rows.append(row)
            if run_kind=='REAL_API' and args.pause_seconds>0 and ix<len(selected)-1:
                time.sleep(args.pause_seconds)
        report={
            'schema_version':'cfm-id-evaluation-run-v0.4',
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'dataset_version':data['dataset_version'],'dataset_sha256':stable_sha256(data),
            'runner_version':'0.4.0','run_kind':run_kind,
            'provider':('openai-chat-compatible' if run_kind=='REAL_API' else 'fixture-only'),
            'model':args.model if run_kind=='REAL_API' else None,
            'prompt_versions':{'formulation':FORMULATOR_PROMPT_VERSION,'candidate':CANDIDATE_PROMPT_VERSION},
            'selected_cases':len(selected),'cases':rows,'summary':rollup(rows),
            'limitations':[
                'No formal Identification theorem, proof checker or Estimation was run.',
                'Frozen candidate stage uses TEST-ONLY synthetic review and Mock UNSUPPORTED routing; not real library coverage.',
                'Auto-scored labels/formats are not mathematical correctness. Two independent substantive human reviews recommended.',
                'All benchmark cases are synthetic; no real corporate data or live study was assessed.',
                'Offline fixture counts are software regression checks, NOT live LLM model accuracy.' if run_kind!='REAL_API' else
                    'Live API results are model outputs, NOT certified causal conclusions.',
            ],
        }
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if args.adjudication_template:
            tmpl=make_adjudication_template(report)
            args.adjudication_template.parent.mkdir(parents=True,exist_ok=True)
            args.adjudication_template.write_text(json.dumps(tmpl,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        short={'run_kind':run_kind,'selected':len(selected),'summary':report['summary'],
               'model':report['model'],'output':str(args.output) if args.output else None,
               'math_verified':False}
        print(json.dumps(short,ensure_ascii=False,indent=2))
        return 0 if all(r['status'] not in ('MISSING_FIXTURE','RUNNER_FAILURE','PROVIDER_OR_SCHEMA_FAILURE','PROVIDER_FAILED') for r in rows) else 1
    except Exception as exc:
        print(f'Evaluation stopped safely: {type(exc).__name__}; check dataset, explicit consent, key, and output path.',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
