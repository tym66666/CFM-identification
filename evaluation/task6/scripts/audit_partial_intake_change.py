"""Review one observed source-only A0 reread change on the fictional partial case."""
import argparse
import json
from pathlib import Path
from cfm_id import business_intake,intake_reading_revision


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    src,out=Path(a.source),Path(a.output)
    s=business_intake._checked(json.loads((src/'intake_snapshot.json').read_text(encoding='utf8')))
    sheet=intake_reading_revision.inspect_changes(s)['worksheet'];changes=sheet['changes']
    expected={'field_path':'/queries/0/comparison_order/refs','before_present':True,'after_present':True,
              'before':[],'after':['s0001']}
    if changes!={'d0001':expected} or 's0001' not in sheet['source_catalog']:
        raise ValueError('Reread differs from the observed one-reference change')
    review={'version':'reading-change-review-1','binding_sha256':sheet['binding_sha256'],
      'authority':'SYNTHETIC_TEST','reviewer':'Codex AI source review of fictional case',
      'evidence':'只审核单一复查变化并对照原业务问题；不是人类签审或科学批准。',
      'decisions':{'d0001':{'disposition':'ACCEPTED','source_ids':['s0001'],
      'reason':'业务问题只有一个全启用政策，新增的引用支持比较方向不适用。'}}}
    revised=intake_reading_revision.review_changes(s,review)
    out.mkdir(parents=True,exist_ok=False)
    for name,value in [('intake_snapshot',revised.model_dump(mode='json')),('change_review',review),('inspection',business_intake.inspect(revised))]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({'state':business_intake.inspect(revised)['state']},ensure_ascii=False))


if __name__=='__main__':main()
