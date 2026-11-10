"""Submit one source-located reread request without changing the first reply.

The caller supplies a real JSON-pointer finding and source refs. Feedback is
labelled as AI-assisted; a reread never grants scientific approval.
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from cfm_id import business_intake,intake_reading_revision
from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider


def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')


def run(source,output,model,base_url,field,refs,reason,timeout,authority='EXTERNAL_RESEARCH_REVIEW'):
    source,output=Path(source),Path(output);output.mkdir(parents=True,exist_ok=False)
    s=business_intake._checked(json.loads((source/'intake_snapshot.json').read_text(encoding='utf8')))
    sheet=intake_reading_revision.prepare_recheck(s,authority=authority)['feedback_worksheet']
    if field not in sheet['field_paths'] or any(ref not in sheet['source_catalog'] for ref in refs):
        raise ValueError('Feedback path or original source reference is invalid')
    feedback=dict(version='intake-reading-feedback-1',binding_sha256=sheet['binding_sha256'],
        authority=sheet['expected_authority'],reviewer='Codex AI source review (not independent human)',
        evidence='AI辅助核对原始材料及实际候选；反馈只请求重读，不批准科学条件。',
        issues=[dict(field_path=field,kind='OMITTED_OR_MISREAD',source_ids=refs,reason=reason)])
    s=intake_reading_revision.prepare_recheck(s,feedback=feedback,authority=authority)
    request=business_intake.prepare_request(s)
    write(output/'feedback.json',feedback);write(output/'request.json',request)
    p=OpenAICompatibleChatProvider(model=model,base_url=base_url,timeout=timeout,
        max_tokens=16384,thinking='disabled',json_mode=True,require_finish_reason=True)
    row=dict(stage='REREAD_NOT_FIRST_PASS',api_attempted=True,response_received=False,
             request_sha256=request['request_sha256'])
    try:
        s=business_intake.read_once(s,p);write(output/'model_candidate.json',s.candidate)
        write(output/'intake_snapshot.json',s.model_dump(mode='json'))
        inspection=business_intake.inspect(s);write(output/'inspection.json',inspection)
        row.update(response_received=True,wire_state=inspection.get('state'),reason_code=inspection.get('reason_code'))
    except Exception as e:
        row.update(wire_state='CALL_OR_PARSE_FAILED',error_type=type(e).__name__,error_code=getattr(e,'code',None))
    row['usage']=p.last_diagnostics.get('usage',{});row['transport_calls']=p.last_diagnostics.get('transport_calls',0)
    write(output/'result.json',row);print(json.dumps(row,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('source','output','model','base-url','field','reason'):p.add_argument('--'+arg,required=True)
    p.add_argument('--refs',nargs='+',required=True);p.add_argument('--timeout',type=float,default=90)
    p.add_argument('--authority',choices=['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST'],default='EXTERNAL_RESEARCH_REVIEW')
    p.add_argument('--key-stdin',action='store_true');a=p.parse_args()
    if a.key_stdin:
        key=getpass.getpass('API key (not echoed): ') if sys.stdin.isatty() else sys.stdin.readline().strip()
        if not key:raise ValueError('API key not supplied')
        os.environ['CFM_ID_LLM_API_KEY']=key
    run(a.source,a.output,a.model,a.base_url,a.field,a.refs,a.reason,a.timeout,a.authority)
