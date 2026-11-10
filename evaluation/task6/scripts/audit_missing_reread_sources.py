"""Source-audit the observed fictional missing-case reread without changing it."""
import argparse
import hashlib
import json
from pathlib import Path
from cfm_id import business_intake,project

SECOND_REREAD_DIGEST='9d6be652ae021246b54451fb9bb72860f908ad3588052b026ab86fe3db8c43aa'


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reread',required=True);a=p.parse_args()
    src,out=Path(a.source),Path(a.reread)
    def read(base,name):return json.loads((base/(name+'.json')).read_text(encoding='utf8'))
    digest=hashlib.sha256((out/'fact_candidate.json').read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()
    if digest not in ('4bbd15b4d8de4f79b175850146df824d9974089313687893842fe83caf94425d', SECOND_REREAD_DIGEST):
        raise ValueError('Candidate changed; this audit applies only to the observed response')
    material=Path(__file__).resolve().parents[1]/'pilot_cases/materials/missing.json'
    if hashlib.sha256(material.read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()!='6afb318b4b734bbebc2e718da834f6d2cf721ae8f60238e2a195ac97cf4dcd27':
        raise ValueError('Original fictional case changed')
    w=read(out,'after_change_review')['source_review_worksheet']
    reasons={
      '':([f's{i:04d}' for i in range(1,25)],'逐项对照全部虚构材料，目标及声明均保留；拟采用不改为已采用，完整性保留未知。'),
      '/study':(['s0001','s0002'],'study明确七网点、编码及结果，network明确完整的处理前星形边。'),
      '/assignment':(['s0003'],'assignment明确七网点固定选三且各名单等概率，边际3/7由均匀抽样得到。'),
      '/target':(['s0024','s0025','s0001'],'业务问题要求全体使用及等权均值；study列出名单及使用记1。'),
      '/design_facts/assignment_rule_available':(['s0003'],'assignment明确固定人数和均匀完整分配律。'),
      '/design_facts/network_fixed_before_treatment':(['s0002'],'network明示网络处理前固定且边完整。'),
      '/scientific_statements/assignment_outcome_independence':(['s0004'],'science明确采用完整处理向量与全部潜在结果独立。'),
      '/scientific_statements/consistency':(['s0004'],'science明确采用观察与实际安排潜在结果一致。'),
      '/scientific_statements/finite_conditional_means':(['s0004'],'science明确采用所需条件一阶矩有限。'),
      '/exposure':(['s0013'],'exposure定义严格过半为1、平票及孤立节点为0。'),
      '/mean_sufficiency':(['s0014'],'原文仅拟采用全对象全安排的均值限制，候选保留PROPOSED。'),
      '/bounded_model':(['s0015','s0016','s0017','s0018','s0019','s0020','s0021','s0022'],'bounds给出各对象每完整安排的均值界、结果和期间；模型完整性另在子字段保留未知。'),
      '/bounded_model/listed_means_are_complete_information':(['s0005','s0023'],'列出的总体信息及complete_model未确认完整性，候选值保持null。'),
      '/bounded_model/no_additional_coupling_constraints':(['s0023'],'complete_model未确认是否存在其他耦合条件，候选值保持null。'),
    }
    for i in range(7):
        ref=f's{i+6:04d}'
        label='中心' if i==0 else f'网点{i}'
        coordinate='自身处理0、同伴暴露0' if i==0 else '自身处理1、同伴暴露1'
        reasons[f'/information/{i}']=([ref],f'information原文列出{label}的{coordinate}总体条件均值为1/2。')
        ref_bound=f's{i+16:04d}'
        reasons[f'/bounded_model/bounds/{i}']=([ref_bound],f'bounds原文明确{label}的下界为0、上界为1。')
    if digest == SECOND_REREAD_DIGEST:
        reasons['/assignment']=(['s0003'],'assignment明确固定选择三名且名单等概率，候选未额外填写逐对象概率。')
        reasons['/target']=(['s0024','s0001'],'业务问题要求全体使用及等权均值；study列出名单及使用记1。')
    if set(reasons)!=set(w['fields']):raise ValueError('Source worksheet differs from explicitly checked fields')
    review={'version':w['version'],'binding_sha256':w['binding_sha256'],'authority':'SYNTHETIC_TEST',
      'reviewer':'Codex AI delegated review of fictional case','evidence':'逐项对照本次真实模型复查候选和全部虚构业务原文；不冒充独立人类签审或批准科学条件。',
      'decisions':{path:dict(field_role='ACCEPTED',value_state='ACCEPTED',source_coverage='ACCEPTED',reason=reason,source_ids=refs)
                   for path,(refs,reason) in reasons.items()}}
    # 3/7 is mathematically implied, but the D2 wire contract cannot also carry
    # per-node Bernoulli probabilities. Preserve and reject this actual answer.
    if digest != SECOND_REREAD_DIGEST:
        review['decisions']['/assignment']['value_state']='REJECTED'
        review['decisions']['/assignment']['reason']='固定名额分配同时填写每对象概率，不符合现有分配字段组合合同；需要模型重读，不能手工改答案。'
    (out/'source_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    entry=read(out,'fact_entry')
    result=project.inspect_methods(business_intake._checked(read(src,'intake_snapshot')),'q1',
        query_review=read(src,'a0_submitted')['query_review'],candidate=read(out,'fact_candidate'),
        request_sha256=entry['request_sha256'],reading_revision=entry['reading_revision'],
        change_review=read(out,'change_review'),source_review=review)
    (out/'source_review_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({'state':result['state'],'reason':result.get('reason_code'),
      'clarification_questions':result.get('clarification_questions')},ensure_ascii=False))


if __name__=='__main__':main()
