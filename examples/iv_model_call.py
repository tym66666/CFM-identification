"""One explicitly authorized model read; immutable evidence, never approval.

Consumes an actual project A0 request or dispatch reader/recheck request.
Does not generate expected answers, repair JSON, retry, or execute mathematics.
"""
import argparse
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import sys
import time
from cfm_id.business_intake import read_json, write_json
from cfm_id_llm.providers.final_content_observer import FinalContentObservedChatProvider
from cfm_id_llm.providers.base import ProviderError

ALLOWED = {'model','base_url','api_key_env','max_tokens','max_completion_tokens',
           'timeout','stream','max_stream_seconds','thinking','json_mode'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stage', required=True, choices=['a0-first','fact-first','a0-recheck','fact-recheck'])
    parser.add_argument('--allow-model-call', action='store_true')
    args=parser.parse_args(argv)
    if not args.allow_model_call:
        parser.error('Explicit --allow-model-call is required; no call was made')
    config=read_json(args.config)
    if not isinstance(config,dict) or set(config)-ALLOWED or not {'model','base_url','api_key_env'}<=set(config):
        parser.error('Supply model, base_url and api_key_env; secret values and unknown fields are forbidden')
    if not isinstance(config['api_key_env'],str) or not config['api_key_env'].isidentifier():
        parser.error('api_key_env must be an environment variable NAME, not a credential')
    key=os.getenv(config['api_key_env'])
    if not key:
        parser.error('Configured credential environment variable is not set; no call was made')
    original=read_json(args.request)
    request=original.get('request',original)
    if not isinstance(request,dict):parser.error('No prepared request')
    system=request.get('system_prompt',request.get('system'))
    user=request.get('user_prompt',request.get('user'))
    if not isinstance(system,str) or not isinstance(user,str):parser.error('Prepared system/user prompts required')
    options={k:v for k,v in config.items() if k!='api_key_env'}
    # Constructor validation precedes writing or calling the network.
    def save_final_text(text):
        with (args.output/'model_final_text.txt').open('x',encoding='utf-8') as stream:
            stream.write(text)
    provider=FinalContentObservedChatProvider(**options,api_key=key,require_finish_reason=True,
        final_content_observer=save_final_text)
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'request.json',original)
    write_json(args.output/'provider_config.json',config)
    started=datetime.now(timezone(timedelta(hours=8))).isoformat()
    timer=time.monotonic()
    record=dict(stage=args.stage,started_at=started,command=list(sys.orig_argv),
        cwd=str(Path.cwd()),python=sys.version,transport_calls=0,human_review='NOT_PERFORMED',
        mathematical_verification='NOT_PERFORMED',automatic_retry=False)
    write_json(args.output/'started.json',record)
    code=0
    try:
        candidate=provider.generate_json(system_prompt=system,user_prompt=user)
        write_json(args.output/'model_candidate.json',candidate)
        record.update(status='RECEIVED_JSON_NOT_REVIEWED')
    except ProviderError as exc:
        code=2;record.update(status='FAILED',reason_code=exc.code)
    except (ValueError,TypeError,OSError):
        code=2;record.update(status='FAILED',reason_code='CALL_OR_EVIDENCE_WRITE_FAILED')
    finally:
        record.update(finished_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
            elapsed_seconds=time.monotonic()-timer,exit_code=code,
            diagnostics=provider.last_diagnostics,
            transport_calls=provider.last_diagnostics.get('transport_calls',0))
        write_json(args.output/'run.json',record)
    print(record['status'])
    return code


if __name__=='__main__':
    raise SystemExit(main())
