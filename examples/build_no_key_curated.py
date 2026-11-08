"""Build deterministic no-key business intake gallery, from actual Core outputs.

Offline HTML embeds Core results which were computed at BUILD TIME, not at view
or click time. For fresh local Core computation use `python -m cfm_id.local_demo`.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from cfm_id.curated_no_key import build_snapshot

ROOT=Path(__file__).resolve().parents[1]
NAME='CFM_ID_No_Key_Curated_Business_Live_Demo'

def render(out_dir:Path):
    out_dir.mkdir(parents=True,exist_ok=True)
    snap=build_snapshot()
    pjson=out_dir/(NAME+'.json')
    pjson.write_text(json.dumps(snap,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    template=(ROOT/'assets/supervisor_templates'/'no_key_curated_template.html').read_text(encoding='utf-8')
    payload=json.dumps(snap,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    payload=payload.replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    assert '<!-- NBIB_CORE_SNAPSHOT -->' in template
    html=template.replace('<!-- NBIB_CORE_SNAPSHOT -->',
                          '<script id="verified-gallery" type="application/json">'+payload+'</script>')
    phtml=out_dir/(NAME+'.html');phtml.write_text(html,encoding='utf-8')
    examples=out_dir/'sample_business_texts';examples.mkdir(exist_ok=True)
    for x in snap['cases']:
        case=x['catalog']
        (examples/(case['case_id']+'.txt')).write_text(case['business_text'],encoding='utf-8')
    return pjson,phtml

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',default='assets/supervisor_templates');args=p.parse_args()
    paths=render(Path(args.output_dir));snap=json.loads(paths[0].read_text(encoding='utf8'))
    print(json.dumps({'files':[str(x) for x in paths],
           'cases':len(snap['cases']),
           'synthetic_core_statuses':{x['catalog']['case_id']:x['synthetic']['status'] for x in snap['cases']},
           'no_api_key':True,'real_business_certified':False},ensure_ascii=False))
if __name__=='__main__': main()
