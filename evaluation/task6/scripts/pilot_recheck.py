"""One real, bound source-located reread of the pilot point baseline.

Initial model answer and rejection remain unchanged. No scientific approval.
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from cfm_id import business_intake, intake_reading_revision
from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider


def save(p,x):
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')


def run(source,output,model,base_url,timeout):
    source=Path(source);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    s=business_intake._checked(json.loads((source/'intake_snapshot.json').read_text(encoding='utf8')))
    sheet=intake_reading_revision.prepare_recheck(s,authority='EXTERNAL_RESEARCH_REVIEW')['feedback_worksheet']
    feedback=dict(version='intake-reading-feedback-1',binding_sha256=sheet['binding_sha256'],
        authority=sheet['expected_authority'],reviewer='Codex automated source review',
        evidence='AI辅助比较业务问题与study来源，仅提交引用缺漏反馈，不批准事实或科学条件。',
        issues=[dict(field_path='/queries/0/semantics/target_population',kind='OMITTED_OR_MISREAD',
                     source_ids=['s0002'],reason='该值枚举具体网点，但当前字段未引用列出名单的study原文。')])
    revised=intake_reading_revision.prepare_recheck(s,feedback=feedback,authority='EXTERNAL_RESEARCH_REVIEW')
    request=business_intake.prepare_request(revised)
    save(out/'feedback.json',feedback);save(out/'request.json',request)
    p=OpenAICompatibleChatProvider(model=model,base_url=base_url,timeout=timeout,
        max_tokens=16384,thinking='disabled',json_mode=True,require_finish_reason=True)
    row={'stage':'REREAD_NOT_FIRST_PASS','api_attempted':True,'response_received':False,
         'request_sha256':request['request_sha256'],'format_valid':None}
    try:
        revised=business_intake.read_once(revised,p)
        save(out/'model_candidate.json',revised.candidate)
        save(out/'intake_snapshot.json',revised.model_dump(mode='json'))
        inspection=business_intake.inspect(revised);save(out/'inspection.json',inspection)
        gate=inspection.get('wire_gate') or {}
        passed=('report' in inspection or gate.get('status')=='DRAFT_FOR_EXTERNAL_REVIEW')
        row.update(response_received=True,wire_state=inspection.get('state'),
                   reason_code=inspection.get('reason_code'),format_valid=passed)
    except Exception as e:
        row.update(wire_state='CALL_OR_PARSE_FAILED',error_type=type(e).__name__,error_code=getattr(e,'code',None))
    row['usage']=p.last_diagnostics.get('usage',{});row['transport_calls']=p.last_diagnostics.get('transport_calls',0)
    save(out/'result.json',row);print(json.dumps(row,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--model',required=True);p.add_argument('--base-url',required=True)
    p.add_argument('--timeout',type=float,default=90);p.add_argument('--key-stdin',action='store_true')
    a=p.parse_args()
    if a.key_stdin:
        key=getpass.getpass('API key (not echoed): ') if sys.stdin.isatty() else sys.stdin.readline().strip()
        if not key:raise ValueError('API key not supplied')
        os.environ['CFM_ID_LLM_API_KEY']=key
    run(a.source,a.output,a.model,a.base_url,a.timeout)
