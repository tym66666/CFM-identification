"""Audit an immutable real model fact response for the fictional partial case."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--workdir',required=True);a=p.parse_args();d=Path(a.workdir)
    material=Path(__file__).resolve().parents[1]/'pilot_cases/materials/partial.json'
    if hashlib.sha256((d/'fact_candidate.json').read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()!='adcdd5f8fc91a3c943a490f702c4c8e0195b5dcdd1463043b1a6dff6a8e65674':raise ValueError('Candidate changed')
    if hashlib.sha256(material.read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()!='0c35c0953581d8460b7fe9b7899ded2ebb08d597f3195f8c7ba12e593fdf1c66':raise ValueError('Material changed')
    w=json.loads((d/'fact_source_worksheet.json').read_text(encoding='utf8'))
    reasons={
      '':([f's{i:04d}' for i in range(1,25)],'核对虚构业务全部材料，保留目标、已知信息、拟采用条件、界限和完整模型声明。'),
      '/study':(['s0001','s0002'],'study给出七对象和编码，network给出完整的处理前星形关系。'),
      '/assignment':(['s0003'],'原文明确固定选三并且同人数名单等概率。'),
      '/target':(['s0024','s0001'],'问题要求全体使用及等权均值，study给出名单及编码。'),
      '/design_facts/assignment_rule_available':(['s0003'],'assignment明确均匀固定名额分配。'),
      '/design_facts/network_fixed_before_treatment':(['s0004'],'science明确网络在处理前固定。'),
      '/scientific_statements/assignment_outcome_independence':(['s0004'],'science明确采用完整向量与全部潜在结果独立。'),
      '/scientific_statements/consistency':(['s0004'],'science明确采用实际安排下一致性。'),
      '/scientific_statements/finite_conditional_means':(['s0004'],'science明确采用所需条件一阶矩有限。'),
      '/exposure':(['s0013'],'exposure明确严格过半为1，平票及孤立节点为0。'),
      '/mean_sufficiency':(['s0014'],'原文写拟采用全对象全安排均值暴露限制，候选保持PROPOSED。'),
      '/bounded_model':([f's{i:04d}' for i in range(15,23)],'bounds给出全安排的逐对象均值界、结果单位和期间。'),
      '/bounded_model/listed_means_are_complete_information':(['s0023'],'complete_model明确只有列出的精确总体均值。'),
      '/bounded_model/no_additional_coupling_constraints':(['s0023'],'complete_model明确无额外跨对象及跨情境耦合限制。')}
    for i in range(7):
        name='中心' if i==0 else f'网点{i}'
        coordinate='自身处理0、同伴暴露0' if i==0 else '自身处理1、同伴暴露1'
        reasons[f'/information/{i}']=(['s0005',f's{i+6:04d}'],f'information声明精确总体条件均值，{name}在{coordinate}时为1/2。')
        reasons[f'/bounded_model/bounds/{i}']=(['s0015',f's{i+16:04d}'],f'bounds明确均值界适用于全部安排，{name}下界0、上界1。')
    if set(reasons)!=set(w['fields']):raise ValueError('Unexpected source review fields')
    record={'version':w['version'],'binding_sha256':w['binding_sha256'],'authority':'SYNTHETIC_TEST',
      'reviewer':'Codex AI delegated review of fictional partial case',
      'evidence':'逐项对照真实模型事实候选和虚构业务材料，拟采用保留为拟采用；不冒充人类签审或科学批准。',
      'decisions':{k:dict(field_role='ACCEPTED',value_state='ACCEPTED',source_coverage='ACCEPTED',reason=reason,source_ids=refs)
                   for k,(refs,reason) in reasons.items()}}
    (d/'source_review_EDIT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Source review ready; proposed scientific assumption is not adopted by this source review.')


if __name__=='__main__':main()
