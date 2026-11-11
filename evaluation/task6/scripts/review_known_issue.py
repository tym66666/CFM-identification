"""Record one observed A0 rejection, preserving every other field as pending."""
import argparse
import json
from pathlib import Path
from cfm_id import business_intake,business_field_review


def run(folder,field,dimension,reason,expected_source_ids):
    folder=Path(folder);result=json.loads((folder/'result.json').read_text(encoding='utf8'))
    if result.get('internal_binding_is_unmodified_request') is not True:
        raise ValueError('Cannot submit a review against an unbound prompt')
    s=business_intake._checked(json.loads((folder/'intake_snapshot.json').read_text(encoding='utf8')))
    sheet=business_field_review.prepare(s,'q1',authority='EXTERNAL_RESEARCH_REVIEW')['field_worksheet']
    if field not in sheet['fields'] or dimension not in ('field_role','value_state','source_coverage'):
        raise ValueError('Unknown field or review dimension')
    citations=[r['ref'] for r in sheet['fields'][field]['actual_citations']]
    if set(citations)!=set(expected_source_ids):
        raise ValueError('The observed citations differ from the reviewed citations')
    decision=sheet['decisions'][field];decision[dimension]='REJECTED';decision['reason']=reason;decision['source_ids']=citations
    record=dict(version=business_field_review.VERSION,binding_sha256=sheet['binding_sha256'],
        authority=sheet['expected_authority'],reviewer='Codex AI source review (not independent human)',
        evidence='人工委托AI核对当前材料和模型候选，只记录指定拒绝，其余保持待审；不代表科学批准。',
        decisions=sheet['decisions'])
    result=business_field_review.submit(s,'q1',record,authority='EXTERNAL_RESEARCH_REVIEW')
    with (folder/'known_issue_review.json').open('x',encoding='utf8') as f:
        json.dump(dict(review=record,result=result),f,ensure_ascii=False,indent=2,default=str)
    print(json.dumps({'state':result['state'],'reason':result['reason_code'],'field':field},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('folder','field','dimension','reason'):p.add_argument('--'+arg,required=True)
    p.add_argument('--expected-source-ids',nargs='+',required=True);a=p.parse_args()
    run(a.folder,a.field,a.dimension,a.reason,a.expected_source_ids)
