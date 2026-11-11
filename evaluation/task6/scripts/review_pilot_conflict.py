"""Reject a model claim if it silently ignores the supplied opposing policy."""
import json
from pathlib import Path
from cfm_id import business_intake,business_field_review


def run(base,arm):
    folder=Path(base)/'private'/('conflict_'+arm)
    session=business_intake._checked(json.loads((folder/'intake_snapshot.json').read_text(encoding='utf8')))
    sheet=business_field_review.prepare(session,'q1',authority='EXTERNAL_RESEARCH_REVIEW')['field_worksheet']
    field='queries.q1.semantics.first_arrangement'
    candidate=sheet['fields'][field]['candidate']
    if not isinstance(candidate,dict) or candidate.get('state')!='STATED':
        print('No fixed target to reject; inspect manually.');return
    text=str(candidate.get('value',''))
    if '使用' not in text and '启用' not in text:
        print('Unexpected candidate; inspect manually.');return
    decision=sheet['decisions'][field]
    decision['value_state']='REJECTED'
    decision['reason']='业务问题要求所有网点使用AI，但补充邮件要求所有网点不使用且明确尚未协调；不能直接接受单一目标。'
    decision['source_ids']=[row['ref'] for row in sheet['fields'][field]['actual_citations']]
    review=dict(version=business_field_review.VERSION,binding_sha256=sheet['binding_sha256'],
        authority=sheet['expected_authority'],reviewer='Codex automated source review',
        evidence='AI辅助核对问题和冲突邮件；仅记录拒绝，其余字段待审，不代表独立人工或科学批准。',
        decisions=sheet['decisions'])
    result=business_field_review.submit(session,'q1',review,authority='EXTERNAL_RESEARCH_REVIEW')
    with (folder/'conflict_rejection_review.json').open('x',encoding='utf8') as f:
        json.dump(dict(review=review,result=result),f,ensure_ascii=False,indent=2,default=str)
    print(arm,result.get('state'),result.get('reason_code'))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--arm',choices=['baseline','candidate'],required=True)
    a=p.parse_args();run(a.run,a.arm)
