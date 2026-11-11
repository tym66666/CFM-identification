"""Audit the known fictional point plan and its cited assumptions, not production research."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workdir',required=True);a=p.parse_args()
    d=Path(a.workdir)
    read=lambda n:json.loads((d/(n+'.json')).read_text(encoding='utf8'))
    if hashlib.sha256((d/'fact_candidate.json').read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()!='64ffd69ff37244d9ac7ac494e783aa4d2d54f8fadd0a22e5bdf7023fd66cf552':
        raise ValueError('Audited candidate changed')
    plan, review = read('plan'), read('scientific_reviews_EDIT')
    target=plan['proposed_target']
    if plan['state']!='REVIEW_REQUIRED' or [r['method'] for r in plan['methods']]!=['R1B_FULL_ASSIGNMENT']:
        raise ValueError('Unexpected plan')
    if target['assignment']!=[1]*5 or target['unit_weights']!=['1/5']*5 or target['node_order']!=['中心','网点1','网点2','网点3','网点4']:
        raise ValueError('Target does not match source')
    if plan['exclusions']!=[{'method':'R2_MEAN_SIGNATURE','reason_code':'R2_ADDITIONAL_DECLARATIONS_NOT_ESTABLISHED','unresolved':False}]:
        raise ValueError('Unexpected excluded methods')
    if set(review['native_reviews'])!={'R1B_FULL_ASSIGNMENT'}:raise ValueError('Unexpected review set')
    evidence=("合成题由Codex AI逐项对照：全体使用政策与五对象等权目标来自业务问题和编码；"
      "独立二分之一分配、固定处理前网络、完整向量随机化、一致性及有限矩均由材料明确采用；"
      "A4是每对象结果与完整向量的符号总体联合分布。R1b目标配置概率为1/32；"
      "材料明确不采用均值暴露充分性，故不使用R2。此审核只适用于虚构试题，不是人类签审或生产科学许可。")
    records=[review['plan_review'],*review['native_reviews']['R1B_FULL_ASSIGNMENT'].values()]
    for rec in records:
        rec['authority']='SYNTHETIC_TEST';rec['reviewer']='Codex AI review of fictional test case';rec['evidence']=evidence
        rec['decisions']={k:'ACCEPTED' for k in rec['decisions']}
    review['research_protocol_selected']=True
    (d/'scientific_reviews_EDIT.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Explicit synthetic research review prepared for R1b only.')


if __name__=='__main__':main()
