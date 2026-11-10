"""Select and review the proposed bounded model only for this fictional trial."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--workdir',required=True);a=p.parse_args();d=Path(a.workdir)
    read=lambda n:json.loads((d/(n+'.json')).read_text(encoding='utf8'))
    if hashlib.sha256((d/'fact_candidate.json').read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()!='adcdd5f8fc91a3c943a490f702c4c8e0195b5dcdd1463043b1a6dff6a8e65674':raise ValueError('Candidate changed')
    plan,review,candidate=read('plan'),read('scientific_reviews_EDIT'),read('fact_candidate')
    method='BOUNDED_POLICY_MEAN_D2_E1';target=plan['proposed_target']
    if plan['state']!='REVIEW_REQUIRED' or [r['method'] for r in plan['methods']]!=[method]:raise ValueError('Unexpected plan')
    if target['assignment']!=[1]*7 or target['unit_weights']!=['1/7']*7 or target['node_order']!=['中心',*[f'网点{i}' for i in range(1,7)]]:
        raise ValueError('Target differs from original question')
    if candidate['mean_sufficiency']['status']!='PROPOSED':raise ValueError('Expected the explicitly proposed assumption')
    b=candidate['bounded_model']
    if not (b['listed_means_are_complete_information']['value'] is True and b['no_additional_coupling_constraints']['value'] is True):
        raise ValueError('Complete model statements missing')
    if set(review['native_reviews'])!={method}:raise ValueError('Unexpected review set')
    evidence=('仅针对虚构题，在合成研究中选择并批准原文明确拟采用的全对象、全安排均值暴露充分性；'
      '这不是把原文PROPOSED改写为ADOPTED，也不是现实研究的科学批准。'
      '原文另明确固定选三的均匀分配、完整向量独立性、一致性、处理前固定网络和有限矩。'
      '逐项核对七个精确总体均值、全安排均值界[0,1]、信息完整以及无额外耦合声明；'
      '目标是七网点全使用的等权平均。项目源审核、科学审核与数学重放互不替代。')
    for rec in [review['plan_review'],*review['native_reviews'][method].values()]:
        rec['authority']='SYNTHETIC_TEST';rec['reviewer']='Codex AI review of fictional research proposal';rec['evidence']=evidence
        rec['decisions']={k:'ACCEPTED' for k in rec['decisions']}
    review['research_protocol_selected']=True
    (d/'scientific_reviews_EDIT.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Fictional proposed mean assumption explicitly selected for synthetic research review.')


if __name__=='__main__':main()
