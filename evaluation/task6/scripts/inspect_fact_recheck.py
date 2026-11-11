"""Inspect a real bound fact reread; do not approve changed facts automatically."""
import argparse
import json
from pathlib import Path
from cfm_id import business_intake, project


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reread',required=True);a=p.parse_args()
    src,out=Path(a.source),Path(a.reread)
    def read(base,name):return json.loads((base/(name+'.json')).read_text(encoding='utf8'))
    entry=read(out,'fact_entry')
    result=project.inspect_methods(business_intake._checked(read(src,'intake_snapshot')),'q1',
        query_review=read(src,'a0_submitted')['query_review'],candidate=read(out,'fact_candidate'),
        request_sha256=entry['request_sha256'],reading_revision=entry['reading_revision'])
    (out/'inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({'state':result['state'],'reason_code':result.get('reason_code'),
        'changes':len(result.get('reading_change_worksheet',{}).get('changes',{}))},ensure_ascii=False))


if __name__=='__main__':main()
