"""CFM Task 6 paired A0 evaluation; run from the ORIGINAL repository root.

Copy `evaluation/task6/` into the repo, then:
  python -m evaluation.task6.scripts.run_experiment --output outputs/task6_prepare
  python -m evaluation.task6.scripts.run_experiment --live --subset dev \
      --model <MODEL> --base-url https://YOUR-VALID-OPENAI-COMPATIBLE-URL/v1 \
      --max-calls 8 --allow-external --allow-material-sharing \
      --output outputs/task6_dev_001

NOTE: evaluates REAL A0 response and canonical A0 inspection. No scientific approvals,
      fact-reader API calls, Core execution or fabricated full-chain accuracy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
PROFILES={'prompt_only':'target-first-operands-1',
          'prompt_plus_skill':'target-first-skill-1'}

def canonical(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)

def digest(x):
    return hashlib.sha256((x if isinstance(x,str) else canonical(x)).encode('utf-8')).hexdigest()

def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')

def source_head():
    try:
        p=subprocess.run(['git','rev-parse','HEAD'],text=True,capture_output=True,check=True,timeout=5)
        return p.stdout.strip()
    except Exception:
        return None

def load_cases(subset,ids):
    for path in sorted((ROOT/'materials').glob('*.json')):
        obj=json.loads(path.read_text(encoding='utf8'))
        gold=json.loads((ROOT/'references'/(path.stem+'.gold.json')).read_text(encoding='utf8'))
        if subset!='all' and gold['split']!=subset:continue
        if ids and gold['scenario'] not in ids and obj['case_id'] not in ids:continue
        yield obj,gold

def create(args):
    # These imports MUST come from the user's checked-out project, not copied clones.
    from cfm_id import project,business_intake
    from cfm_id.business_reading_config import ReadingConfig
    from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider
    from cfm_id_llm.target_first_skill import skill_manifest

    cases=list(load_cases(args.subset,set(args.ids)))
    if not cases:raise ValueError('No matching test cases')
    profiles=[p for p in args.profiles.split(',') if p]
    if not profiles or any(p not in PROFILES for p in profiles) or len(set(profiles))!=len(profiles):
        raise ValueError('Choose valid, nonduplicated profiles: '+', '.join(PROFILES))
    all_jobs=[]
    for repeat in range(1,args.repeats+1):
        shuffled=list(cases);random.Random(args.seed+repeat).shuffle(shuffled)
        for j,(case,gold) in enumerate(shuffled):
            order=profiles if (j+repeat)%2==0 else list(reversed(profiles))
            for p in order:all_jobs.append((repeat,case,gold,p))
    if args.live:
        if not args.allow_external or not args.allow_material_sharing:
            raise ValueError('Live requires both --allow-external and --allow-material-sharing')
        if not args.model or not args.base_url:
            raise ValueError('Live requires --model and --base-url; do not assume a university API endpoint')
        if len(all_jobs)>args.max_calls:
            raise ValueError(f'Budget guard: {len(all_jobs)} calls planned, --max-calls={args.max_calls}; narrow --ids or raise explicitly')
        if args.subset=='holdout' and not args.frozen_run:
            raise ValueError('Holdout requires --frozen-run to attest protocol/candidate are frozen')
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=False)
    (out/'private').mkdir(mode=0o700)
    try:os.chmod(out/'private',0o700)
    except OSError:pass
    main_config=project.reading_config().model_dump(mode='json')
    sm=skill_manifest()
    manifest={'experiment':'CFM-Task6-A0-paired-1','created_utc':datetime.now(timezone.utc).isoformat(),
       'phase':'LIVE' if args.live else 'PREPARE_ONLY',
       'scope':'A0 only; not fact-reading or final identification',
       'git_head':source_head(),'original_reading_config':main_config,
       'profiles':PROFILES,'skill_manifest':sm,
       'comparison_limitation':'Profiles use different system prompt AND schema/parser contract; not isolated causal Skill effect',
       'model':args.model,'base_url':args.base_url,'timeout':args.timeout,
       'max_tokens':args.max_tokens,'thinking':args.thinking,'json_mode':True,
       'repeats':args.repeats,'seed':args.seed,'set':args.subset,
       'calls_planned':len(all_jobs),'calls_per_a0':1,'fact_calls_per_query':'NOT_EXECUTED',
       'manual_reference_status':'AUTHOR_DRAFT_PENDING_INDEPENDENT_REVIEW',
       'experiment_config_frozen_after_start':True,
       'source_material_hashes':{c['case_id']:digest(c) for c,g in cases}}
    write(out/'manifest.json',manifest)
    all_summaries=[]
    for index,(repeat,case,gold,profile_name) in enumerate(all_jobs,1):
        cid=case['case_id'];folder=out/'private'/f'{index:04d}_{cid}_{profile_name}_r{repeat}'
        folder.mkdir()
        cfg=dict(main_config,a0_response_contract=PROFILES[profile_name])
        config=ReadingConfig.model_validate(cfg)
        session=business_intake.start_configured(case,config)
        request=business_intake.prepare_request(session)
        request_meta={'id':index,'case_id':cid,'profile':profile_name,'repeat':repeat,
           'source_sha256':digest(case),'request_sha256':request['request_sha256'],
           'system_prompt_sha256':digest(request['system_prompt']),
           'user_prompt_sha256':digest(request['user_prompt']),
           'prompt_version':request['prompt_version'],
           'skill_loaded':profile_name=='prompt_plus_skill',
           'effective_a0_response_contract':PROFILES[profile_name]}
        write(folder/'request.json',dict(request,**request_meta))
        write(folder/'configuration.json',config.model_dump(mode='json'))
        result=dict(request_meta,api_called=False,provider_error=None,wire_state='NOT_RUN',
                    core_called=False,scientific_approval=False,fact_stage='NOT_RUN',
                    execution_stage='NOT_RUN',raw_response_saved=False,
                    usage={},elapsed_seconds=None,finished_utc=None)
        if args.live:
            provider=OpenAICompatibleChatProvider(model=args.model,base_url=args.base_url,
                   timeout=args.timeout,max_tokens=args.max_tokens,json_mode=True,
                   thinking=None if args.thinking=='none' else args.thinking,
                   require_finish_reason=True)
            start=time.monotonic()
            result['api_called']=True
            try:
                # read_once saves the *real current profile's* request SHA: no forged
                # binding of a prompt-only answer to the skill-based request.
                session=business_intake.read_once(session,provider)
                write(folder/'raw_response.json',session.candidate)
                result['raw_response_saved']=True
                inspected=business_intake.inspect(session)
                write(folder/'a0_inspection.json',inspected)
                result['wire_state']=inspected.get('state','UNKNOWN')
                result['wire_reason']=inspected.get('reason_code')
                if inspected.get('wire_gate') is not None:
                    gate=inspected['wire_gate']
                    result['wire_issue_codes']=[x.get('code') for x in gate.get('issues',[])]
                    result['wire_question_count']=len(gate.get('proposed_business_questions',[]))
                # Conservatively count a format-valid answer separately from
                # human assessment of target meaning/provenance.
                result['format_parse_success']='report' in inspected
                if result['format_parse_success']:
                    rep=inspected['report'];draft=rep.get('draft',{})
                    qs=draft.get('queries',[])
                    result['canonical_query_count']=len(qs)
                    result['canonical_kinds']=[x.get('target',{}).get('kind') for x in qs]
                write(folder/'intake_snapshot.json',session.model_dump(mode='json'))
            except Exception as exc:
                # No automatic retry, no model-result repairs; all failures retained.
                result['provider_error']=type(exc).__name__
                result['provider_error_code']=getattr(exc,'code',None)
                result['provider_error_description']=str(exc)[:300]
                result['wire_state']='CALL_OR_PARSE_FAILED'
                write(folder/'error.json',{'kind':type(exc).__name__,'code':getattr(exc,'code',None),
                    'message':str(exc)[:300]})
            finally:
                result['elapsed_seconds']=round(time.monotonic()-start,3)
                result['usage']=dict(getattr(provider,'last_diagnostics',{})).get('usage',{})
                result['provider_diagnostics']=dict(getattr(provider,'last_diagnostics',{}))
                result['finished_utc']=datetime.now(timezone.utc).isoformat()
        write(folder/'result.json',result)
        # Public-facing manifest: no raw response; do not submit private/ to Git.
        all_summaries.append(result)
        if args.live:print(f"[{index}/{len(all_jobs)}] {cid} {profile_name}: {result['wire_state']}",flush=True)
    write(out/'runs.json',all_summaries)
    write(out/'summary_status.json',{'status':'UNSCORED_AWAITING_HUMAN_REVIEW' if args.live else 'NO_API_CALLS',
       'actual_a0_api_calls':sum(x['api_called'] for x in all_summaries),
       'attempted_count_denominator':len(all_summaries),
       'model_semantic_accuracy':'NOT_ESTABLISHED',
       'fact_reading_accuracy':'NOT_MEASURED','full_chain_accuracy':'NOT_MEASURED',
       'total_prompt_tokens':sum(x['usage'].get('prompt_tokens',0) for x in all_summaries),
       'total_completion_tokens':sum(x['usage'].get('completion_tokens',0) for x in all_summaries)})
    print(json.dumps({'output':str(out),'plans':len(all_summaries),'online_calls':sum(x['api_called'] for x in all_summaries)},ensure_ascii=False))


def cli(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,help='NEW directory only; private/raw contains sensitive data')
    p.add_argument('--live',action='store_true',help='Actually call the external model; default OFF')
    p.add_argument('--subset',choices=['dev','holdout','all'],default='dev')
    p.add_argument('--ids',nargs='*',default=[],help='Scenario IDs N01..D12, or case IDs')
    p.add_argument('--profiles',default='prompt_only,prompt_plus_skill')
    p.add_argument('--repeats',type=int,default=1)
    p.add_argument('--seed',type=int,default=20261104)
    p.add_argument('--max-calls',type=int,default=8)
    p.add_argument('--model')
    p.add_argument('--base-url',help='Explicit endpoint URL; verify your provider docs')
    p.add_argument('--timeout',type=float,default=300.0)
    p.add_argument('--max-tokens',type=int,default=16384)
    p.add_argument('--thinking',choices=['none','enabled','disabled'],default='disabled')
    p.add_argument('--allow-external',action='store_true')
    p.add_argument('--allow-material-sharing',action='store_true')
    p.add_argument('--frozen-run',action='store_true')
    args=p.parse_args(argv)
    if args.repeats<1 or args.repeats>10: p.error('--repeats must be 1..10')
    if args.max_calls<1: p.error('--max-calls must be >=1')
    try:create(args);return 0
    except Exception as e:
        print(f'ERROR {type(e).__name__}: {e}',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(cli())
