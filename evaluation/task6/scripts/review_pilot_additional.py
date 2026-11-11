"""Save source-grounded rejection decisions for three observed pilot fields."""
import json
from pathlib import Path
from cfm_id import business_intake,business_field_review

FINDINGS={
 'partial_candidate':('common.variable_causal_graph','field_role',
  '该字段填写随机化、一致性与固定网络等条件，science原文不是变量因果图。'),
 'missing_baseline':('queries.q1.semantics.first_arrangement','source_coverage',
  '该值包括“自身处理=1”，本字段仅引业务问题；0/1编码位于study，不能借其他字段的引用。'),
 'missing_candidate':('queries.q1.semantics.neighbor_exposure','source_coverage',
  '该值称同伴暴露由定义决定；该字段只引用业务问题，问题没有同伴暴露定义。'),
}


def run(base):
    for label,(field,dimension,reason) in FINDINGS.items():
        folder=Path(base)/'private'/label
        session=business_intake._checked(json.loads((folder/'intake_snapshot.json').read_text(encoding='utf8')))
        sheet=business_field_review.prepare(session,'q1',authority='EXTERNAL_RESEARCH_REVIEW')['field_worksheet']
        decision=sheet['decisions'][field];decision[dimension]='REJECTED';decision['reason']=reason
        decision['source_ids']=[row['ref'] for row in sheet['fields'][field]['actual_citations']]
        review=dict(version=business_field_review.VERSION,binding_sha256=sheet['binding_sha256'],
            authority=sheet['expected_authority'],reviewer='Codex automated source review',
            evidence='AI辅助逐字段核对；仅记录发现的拒绝，其余字段待审，不是独立人工审签。',decisions=sheet['decisions'])
        result=business_field_review.submit(session,'q1',review,authority='EXTERNAL_RESEARCH_REVIEW')
        with (folder/'source_rejection_review.json').open('x',encoding='utf8') as f:
            json.dump(dict(review=review,result=result),f,ensure_ascii=False,indent=2,default=str)
        print(label,field,result.get('state'),result.get('reason_code'))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();run(a.run)
