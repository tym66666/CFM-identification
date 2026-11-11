"""Record two source-grounded rejection findings, never approve remaining fields."""
import json
from pathlib import Path
from cfm_id import business_intake, business_field_review


def run(base):
    base=Path(base)
    findings={
      'baseline':('queries.q1.semantics.target_population','source_coverage',
          '字段枚举了中心及网点1–4，但该字段仅引用业务问题；问题说“这5个网点”而没有列出名称，名称在study材料。当前字段自身引用不完整。'),
      'candidate':('common.variable_causal_graph','field_role',
          '字段填写随机分配独立性、一致性、固定网络和有限矩等假设，引用science材料；该材料不是变量因果图。'),
    }
    for arm,(field,dimension,reason) in findings.items():
        folder=base/'private'/('point_'+arm)
        session=business_intake._checked(json.loads((folder/'intake_snapshot.json').read_text(encoding='utf8')))
        sheet=business_field_review.prepare(session,'q1',authority='EXTERNAL_RESEARCH_REVIEW')['field_worksheet']
        decision=sheet['decisions'][field]
        decision[dimension]='REJECTED';decision['reason']=reason
        decision['source_ids']=[row['ref'] for row in sheet['fields'][field]['actual_citations']]
        review=dict(version=business_field_review.VERSION,binding_sha256=sheet['binding_sha256'],
            authority=sheet['expected_authority'],reviewer='Codex automated source review',
            evidence='AI辅助逐项核对；这里只记录明确拒绝，不构成人工独立签审或科学批准。',
            decisions=sheet['decisions'])
        result=business_field_review.submit(session,'q1',review,authority='EXTERNAL_RESEARCH_REVIEW')
        out=folder/'source_rejection_review.json'
        with out.open('x',encoding='utf8') as f:json.dump(dict(review=review,result=result),f,ensure_ascii=False,indent=2,default=str)
        print(arm,field,dimension,result.get('state'),result.get('reason_code'))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);a=p.parse_args();run(a.run)
