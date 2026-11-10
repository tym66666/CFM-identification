"""Call a source-bound fact reader after A0 review; never overwrite an answer."""
import argparse
import getpass
import json
import os
from pathlib import Path
from evaluation.task6.scripts.n01_fullchain import entry_from_review
from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workdir',required=True);p.add_argument('--timeout',type=float,default=120)
    args=p.parse_args(); d=Path(args.workdir)
    entry=json.loads((d/'fact_entry.json').read_text(encoding='utf8'))
    if entry_from_review(d)['request_sha256'] != entry['request_sha256']:
        raise ValueError('Stale reviewed fact request')
    if any((d/n).exists() for n in ('fact_candidate.json','fact_call_diagnostics.json')):
        raise FileExistsError('Existing call artifacts must be preserved')
    key=getpass.getpass('API key (not echoed): ')
    if not key:raise ValueError('Missing key')
    os.environ['CFM_ID_LLM_API_KEY']=key
    provider=OpenAICompatibleChatProvider(model='deepseek-v4-flash',base_url='https://newapi.sufe.edu.cn/v1',
        timeout=args.timeout,max_tokens=16384,json_mode=True,thinking='disabled',require_finish_reason=True)
    def write(name,value):
        (d/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    try:
        response=provider.generate_json(system_prompt=entry['request']['system'],user_prompt=entry['request']['user'])
        write('fact_candidate.json',response)
        print('Fact candidate returned; source review remains required.')
    except Exception as exc:
        print('Fact request failed:',type(exc).__name__,getattr(exc,'code',None))
    finally:
        write('fact_call_diagnostics.json',provider.last_diagnostics)


if __name__=='__main__':main()
