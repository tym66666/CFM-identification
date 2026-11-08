"""Small, honest v3.0 supervisor CLI. No scientific approval generated from files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys

from .local_demo import STATIC

def main(argv=None):
    parser=argparse.ArgumentParser(description='CFM-ID v3.0: business-first, verified-core-ready front end')
    subs=parser.add_subparsers(dest='command',required=True)
    subs.add_parser('status',help='Show actual frozen synthetic example counts and capabilities')
    doc=subs.add_parser('intake',help='Read a new business question and file descriptors, NOT theorem identification')
    doc.add_argument('--question',required=True)
    doc.add_argument('--attachment',action='append',default=[])
    doc.add_argument('--requirements',default='')
    page=subs.add_parser('export-pages',help='Copy the offline supervisor and coverage HTML')
    page.add_argument('--output-dir',default='v30_pages')
    serve=subs.add_parser('serve',help='Run a local-only file-preview server')
    serve.add_argument('--port',type=int,default=8765)
    args=parser.parse_args(argv)
    if args.command=='status':
        data=json.loads((STATIC/'CFM_ID_Supervisor_Results.json').read_text(encoding='utf-8'))
        print(json.dumps({'version':'3.0.0','math_core':'v2.9.2-unchanged',
                          'gateway':'0.12.0','core_test_cases':len(data['core_cases']),
                          'core_case_statuses':data['summary'],
                          'candidate_online_model_called':False,'production_partial':False},ensure_ascii=False,indent=2))
    elif args.command=='intake':
        from cfm_id_llm.document_intake import AttachmentRequestV07
        from cfm_id_llm.material_integrity import create_grounded_intake
        from hashlib import sha256
        q=args.question+(('\n补充要求：'+args.requirements) if args.requirements else '')
        case_id='CLI_V30_'+sha256(q.encode()).hexdigest()[:14]
        result=create_grounded_intake(case_id=case_id,business_question=q,
                     attachments=[AttachmentRequestV07(path=x) for x in args.attachment])
        print(json.dumps({'case_id':case_id,'status':'REVIEW_REQUIRED_NO_IDENTIFICATION',
              'attachments':[{'filename':Path(path).name,'mode':x.mode,'warnings':x.warnings}
                             for path,x in zip(args.attachment,result.attachments)],
              'llm_called':False,'core_called':False,'point_certified':False},ensure_ascii=False,indent=2))
    elif args.command=='export-pages':
        target=Path(args.output_dir);target.mkdir(parents=True,exist_ok=True)
        for fname in ('CFM_ID_Supervisor_Results.html','CFM_ID_Coverage_Map.html',
                      'CFM_ID_No_Key_Curated_Business_Live_Demo.html'):
            shutil.copy2(STATIC/fname,target/fname)
        print(str(target.resolve()))
    elif args.command=='serve':
        from http.server import ThreadingHTTPServer
        from .local_demo import Handler
        if not 1024<=args.port<=65535:parser.error('port must be between 1024 and 65535')
        host='127.0.0.1';server=ThreadingHTTPServer((host,args.port),Handler)
        print(f'http://{host}:{args.port}/',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
    return 0

if __name__=='__main__':raise SystemExit(main())
