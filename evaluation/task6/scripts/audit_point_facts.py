"""Record this AI's explicit source audit of one immutable fictional point response."""
import argparse
import hashlib
import json
from pathlib import Path

REASONS={
 '':(['s0001','s0002','s0003','s0004','s0005','s0006','s0007','s0008'],'逐项对照原文，目标、对象、完整分配、信息与科学陈述均保留；没有额外限制。'),
 '/study':(['s0001','s0002'],'study列出五网点、二元处理与结果；network列出完整的处理前无向星形边。'),
 '/assignment':(['s0003'],'assignment明确每个网点独立以二分之一概率使用，名单依据已审study定义。'),
 '/target':(['s0008','s0001'],'问题明确全体使用和等权平均，study明确名单及使用记1的编码。'),
 '/design_facts/assignment_rule_available':(['s0003'],'assignment明确完整独立二分之一分配律。'),
 '/design_facts/network_fixed_before_treatment':(['s0002'],'network明确网络在处理前固定。'),
 '/scientific_statements/assignment_outcome_independence':(['s0004'],'science明确采用完整处理向量与全部潜在结果独立。'),
 '/scientific_statements/consistency':(['s0004'],'science明确采用实际安排下一致性。'),
 '/scientific_statements/finite_conditional_means':(['s0004'],'science明确采用所需条件一阶矩有限。'),
 '/exposure':(['s0006'],'exposure明确严格过半为1、否则为0，平票为0。'),
 '/mean_sufficiency':(['s0007'],'sufficiency明确不采用该均值限制；保留NOT_ADOPTED，不据此批准限制。'),
 '/information/0':(['s0005'],'information明确每网点与完整向量的联合总体分布，是符号总体信息而非样本。'),
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workdir',required=True);a=p.parse_args()
    d=Path(a.workdir)
    candidate=d/'fact_candidate.json'; material=Path(__file__).resolve().parents[1]/'pilot_cases/materials/point.json'
    if hashlib.sha256(candidate.read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()!='64ffd69ff37244d9ac7ac494e783aa4d2d54f8fadd0a22e5bdf7023fd66cf552':
        raise ValueError('Candidate changed; explicit audit does not apply')
    if hashlib.sha256(material.read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()!='3490b88d04b4b833aa25ae33c5e2cc506b4fa43ad1c43e6e34ab49d66fdc7e01':
        raise ValueError('Material changed; explicit audit does not apply')
    sheet=json.loads((d/'fact_source_worksheet.json').read_text(encoding='utf8'))
    if set(sheet['fields'])!=set(REASONS):raise ValueError('Worksheet differs from reviewed fields')
    if any(not set(refs)<=set(sheet['source_catalog']) for refs,_ in REASONS.values()):raise ValueError('Source refs changed')
    record={'version':sheet['version'],'binding_sha256':sheet['binding_sha256'],'authority':'SYNTHETIC_TEST',
        'reviewer':'Codex AI delegated source review of fictional point case',
        'evidence':'已逐项核对虚构业务原文及本次模型事实候选；这是AI审核，不是人类签审或科学批准。',
        'decisions':{path:dict(field_role='ACCEPTED',value_state='ACCEPTED',source_coverage='ACCEPTED',
                    reason=reason,source_ids=refs) for path,(refs,reason) in REASONS.items()}}
    (d/'source_review_EDIT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Source review prepared; mathematical and science reviews remain separate.')


if __name__=='__main__':main()
