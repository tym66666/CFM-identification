"""Audit the four observed model reread changes against fictional source material."""
import argparse
import json
from pathlib import Path
from cfm_id import business_intake,project


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reread',required=True);a=p.parse_args()
    src,out=Path(a.source),Path(a.reread)
    def read(base,name):return json.loads((base/(name+'.json')).read_text(encoding='utf8'))
    sheet=read(out,'inspection')['reading_change_worksheet'];changes=sheet['changes']
    second=len(changes)==2
    paths=(['/assignment/probabilities','/target/source_ids'] if second else
           ['/additional_restrictions','/exposure/core_collaborators','/study/treatment','/target/source_ids'])
    if [x['field_path'] for x in changes.values()]!=paths:raise ValueError('Observed changes differ from explicit audit')
    if second and (changes['d0001']['after'] is not None or changes['d0002']['after']!=['s0024','s0001']):
        raise ValueError('Second-round changes differ from explicit audit')
    if not second and (changes['d0001']['after']!=[] or changes['d0002']['after'] is not None or
        changes['d0003']['after']!='使用AI记1、不使用记0' or
        changes['d0004']['after']!=['s0024','s0025','s0001']):raise ValueError('Changed values differ from explicit audit')
    catalog=sheet['source_catalog']
    def docs(*names):
        result=[key for key,row in catalog.items() if row['doc_id'] in names]
        if not result:raise ValueError('Missing source document')
        return result
    reasons=[(docs('science','network'),'删除的内容均已在专用科学条件和固定网络字段中保留，不是额外约束。'),
      (docs('exposure'),'同伴暴露为严格过半定义，不依赖指定核心同事；新增null没有添加事实。'),
      (docs('study'),'措辞变化不改变使用AI记1、不使用记0的原文编码。'),
      (docs('business_question','__question__','study'),'新增的问题引用与原业务问题同文，并保留名单及编码引用。')]
    if second:
        reasons=[(docs('assignment'),'固定名额分配只由人数与均匀机制表示，去掉多余概率不改变原文分配。'),
                 (docs('business_question','study'),'去除重复问题引用后仍保留业务问题和名单编码原文。')]
    review={'version':'reading-change-review-1','binding_sha256':sheet['binding_sha256'],
      'authority':'SYNTHETIC_TEST','reviewer':'Codex AI delegated review of fictional case',
      'evidence':'逐项核对复查前后变化和原始虚构业务材料；不代表人类签审或科学许可。',
      'decisions':{key:{'disposition':'ACCEPTED','reason':reason,'source_ids':refs}
                   for key,(refs,reason) in zip(changes,reasons)}}
    (out/'change_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    entry=read(out,'fact_entry')
    result=project.inspect_methods(business_intake._checked(read(src,'intake_snapshot')),'q1',
        query_review=read(src,'a0_submitted')['query_review'],candidate=read(out,'fact_candidate'),
        request_sha256=entry['request_sha256'],reading_revision=entry['reading_revision'],change_review=review)
    (out/'after_change_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({'state':result['state'],'reason':result.get('reason_code')},ensure_ascii=False))


if __name__=='__main__':main()
