"""Optional loopback-only supervisor demo: safe file intake, NEVER theorem approval.

python -m cfm_id.local_demo --port 8765
Open http://127.0.0.1:8765/ . No LLM/model credentials are read or used.
The mathematical results available on the page are separately generated from
pre-approved, explicitly synthetic Core study fixtures and independently replayed.
"""
from __future__ import annotations
import argparse
import base64
import binascii
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import tempfile

from cfm_id_llm.document_intake import AttachmentError, AttachmentRequestV07, SUPPORTED_SUFFIXES
from cfm_id_llm.material_integrity import create_grounded_intake
from .curated_no_key import run_curated

ROOT=Path(__file__).resolve().parents[1]
STATIC=Path(__file__).resolve().parent/'web'
ROUTES={
    '/':'CFM_ID_Supervisor_Results.html',
    '/CFM_ID_No_Key_Curated_Business_Live_Demo.html':'CFM_ID_No_Key_Curated_Business_Live_Demo.html',
    '/CFM_ID_Supervisor_Results.html':'CFM_ID_Supervisor_Results.html',
    '/CFM_ID_Coverage_Map.html':'CFM_ID_Coverage_Map.html',
}
MAX_JSON=29*1024*1024

class UnsafeIntake(ValueError): pass

def intake_request(payload:dict)->dict:
    """Safe, bounded conversion of uploaded documents to v0.12 Gateway intake.

    Never grants scientific assumptions, never queries live LLM, and never
    returns a false CORE_REPLAY_VERIFIED or POINT flag.
    """
    if not isinstance(payload,dict):raise UnsafeIntake('JSON object required')
    if set(payload)-{'business_question','requirements','attachments'}:
        raise UnsafeIntake('Unknown intake fields not allowed')
    question=payload.get('business_question')
    requirements=payload.get('requirements','')
    if not isinstance(question,str) or not 3<=len(question.strip())<=10000:
        raise UnsafeIntake('Business question missing or too long')
    if not isinstance(requirements,str) or len(requirements)>1200:
        raise UnsafeIntake('Requirements invalid or too long')
    combined=question.strip()+('\n补充要求：'+requirements.strip() if requirements.strip() else '')
    files=payload.get('attachments',[])
    if not isinstance(files,list) or len(files)>8:raise UnsafeIntake('At most 8 attachments')
    name_sha=sha256(combined.encode('utf-8')).hexdigest()[:14]
    with tempfile.TemporaryDirectory(prefix='cfm-id-gateway-') as tmp:
        requests=[];total=0
        for i,item in enumerate(files):
            if not isinstance(item,dict) or set(item)!={'filename','data_base64'}:
                raise UnsafeIntake('Each attachment needs filename and base64 data only')
            name=item['filename'];encoded=item['data_base64']
            if not isinstance(name,str) or not 1<=len(name)<=200 or '/' in name or '\\' in name or '..' in name:
                raise UnsafeIntake('Unsafe attachment filename')
            suffix=Path(name).suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:raise UnsafeIntake('Unsupported file type')
            if not isinstance(encoded,str) or len(encoded)>11_300_000:raise UnsafeIntake('Oversized attachment')
            try:raw=base64.b64decode(encoded,validate=True)
            except (ValueError,binascii.Error) as exc:raise UnsafeIntake('Invalid base64') from exc
            if len(raw)>8*1024*1024:raise UnsafeIntake('Attachment exceeds 8 MB')
            total+=len(raw)
            if total>20*1024*1024:raise UnsafeIntake('Combined attachments exceed 20 MB')
            path=Path(tmp)/(f'upload_{i:02d}'+suffix);path.write_bytes(raw)
            requests.append(AttachmentRequestV07(path=str(path),label=name))
        intake=create_grounded_intake(case_id='LOCAL_V30_'+name_sha,
             business_question=combined,attachments=requests)
    return dict(schema_version='cfm-id-v3-safe-intake',
        status='REVIEW_REQUIRED_NO_IDENTIFICATION',
        case_id=intake.case.case_id,
        attachments=[{'name':files[idx]['filename'],'mode':rec.mode,'warnings':rec.warnings,
                      'source_sha256':rec.file_sha256} for idx,rec in enumerate(intake.attachments)],
        warnings=intake.warnings,
        next_steps=['业务人员确认目标和具体含义','研究人员独立审核实验、总体信息和因果假设','得到独立认证的数学查询后执行 Core 和证书复核'],
        llm_called=False, core_called=False, point_certified=False, partial_certified=False)

class Handler(BaseHTTPRequestHandler):
    def _send(self,status:int,body:bytes,kind:str):
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(body)
    def _json(self,status,value):self._send(status,json.dumps(value,ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')
    def do_GET(self):
        if self.path=='/api/health':
            self._json(200,{'status':'LOCAL_GATEWAY_PREVIEW_ONLY','online_model':False,'theorem_run_for_upload':False,'no_key_curated_core':True});return
        fname=ROUTES.get(self.path)
        if not fname:self._json(404,{'error':'Not found'});return
        try:body=(STATIC/fname).read_bytes()
        except OSError:self._json(503,{'error':'Run python -m examples.build_supervisor first'});return
        self._send(200,body,'text/html; charset=utf-8')
    def do_POST(self):
        if self.path not in ('/api/intake','/api/no-key/identify'):
            self._json(404,{'error':'Not found'});return
        if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
            self._json(415,{'error':'Only JSON supported'});return
        try:n=int(self.headers.get('Content-Length','-1'))
        except ValueError:n=-1
        if n<0 or n>MAX_JSON:self._json(413,{'error':'Request too large'});return
        try:
            body=self.rfile.read(n)
            data=json.loads(body)
            if self.path == '/api/no-key/identify':
                if not isinstance(data,dict) or set(data) != {'case_id','business_text','synthetic_protocol_selected'}:
                    raise UnsafeIntake('Curated Core expects exactly three whitelisted fields')
                result=run_curated(data['case_id'],data['business_text'],
                                   synthetic_protocol_selected=data['synthetic_protocol_selected'])
            else:
                result=intake_request(data)
            self._json(200,result)
        except (ValueError,AttachmentError,UnicodeDecodeError,json.JSONDecodeError) as exc:
            self._json(400,{'error':type(exc).__name__+': '+str(exc)[:180],
                            'point_certified':False})
        except Exception:
            # Never reveal uploaded document contents or Python traceback.
            self._json(500,{'error':'Local document intake failed; no identification was performed',
                            'point_certified':False})
    def log_message(self, format,*args):pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    if a.port<1024 or a.port>65535: p.error('Use an unprivileged local TCP port')
    http=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    print(f'Causal-IDFM v3.0 local only: http://127.0.0.1:{a.port}/ (Ctrl+C to stop)',flush=True)
    try:http.serve_forever()
    except KeyboardInterrupt:pass
    finally:http.server_close()

if __name__=='__main__':main()
