"""Preserve explicitly known aggregation even when the target population is unknown.

Reading candidates remain unapproved; missing coordinates still block Core.
"""
import json
from copy import deepcopy
from . import business_d1_study_first as prior
from . import business_d1_submission as base

VERSION='business-d1-staged-v0.49'
study_request=prior.study_request
review_study=prior.review_study

def target_request(bundle,study_raw):
    system,user=prior.target_request(bundle,study_raw);m=json.loads(user)
    q=m['output_schema']['$defs']['Question']
    old={'if':{'properties':{'population':{'properties':{'selection':{'const':'不明确'}}}}},
         'then':{'properties':{'aggregation':{'const':'不明确'}}}}
    rules=q.get('allOf',[])
    if rules.count(old)!=1:raise ValueError('EXPECTED_PRIOR_POPULATION_WEIGHT_RULE')
    q['allOf']=[r for r in rules if r!=old]
    if not q['allOf']:q.pop('allOf')
    system+='''
评价对象和汇总权重是分别读取的两个事实，不得相互推定。
如果明确说“选定后每人等权”但尚未决定选谁，population=不明确、aggregation=等权平均是允许的部分信息；仅缺评价对象，不应抹掉已说明的汇总方式。
如果已经明确覆盖全部名册，但权重尚未决定，则population=全体、aggregation=不明确；不能因全体就默认等权。
未说明、尚未决定或否定的字段保持未知；不要为了识别而填齐。其他已明示的比较状态、对象或权重仍原样保留。
'''
    return system,json.dumps(m,ensure_ascii=False)

def compose_reading(bundle,study_raw,target_raw):
    status=review_study(bundle,study_raw)
    if status['state']!='TARGET_INPUT_REQUIRED':return status
    if not isinstance(target_raw,dict) or set(target_raw)!= {'questions'}:
        status.update(state='DRAFT_INVALID',target_candidate=deepcopy(target_raw));return status
    draft=dict(study=deepcopy(study_raw['study']),questions=deepcopy(target_raw['questions']))
    result=base.preview_submission(bundle,draft)
    result.update(version=VERSION,target_normalization_performed=True,study_candidate=deepcopy(study_raw),target_candidate=deepcopy(target_raw),clarification_questions=[])
    if result['state']=='NEEDS_INPUT':
        _,_,targets=base.project(bundle,draft)
        for qid,t in zip(bundle['question_slots'],targets):
            for missing,field,text in [
                (not t.nodes,'population','这个问题要评价哪些客户经理？请说明具体范围或试验前确定的名单。'),
                (t.aggregation is None,'aggregation','这些经理的结果应怎样汇总？请说明实际采用的权重规则。'),
                (t.remaining is None,'remaining','除了题中明确指定的情况，其他人的权限如何安排？请说明这次要评价的安排规则。'),
                (t.situation is None or (t.kind=='comparison' and t.reference is None),'comparison','这个问题具体比较哪两种情况？请分别说明本人和协作同事的权限状态。')]:
                if missing:result['clarification_questions'].append(dict(query_id=qid,field=field,text=text))
    return result

def normalize_in_stages(bundle,study_provider,target_provider=None):
    s,u=study_request(bundle);raw=study_provider.generate_json(system_prompt=s,user_prompt=u)
    status=review_study(bundle,raw)
    if status['state']!='TARGET_INPUT_REQUIRED' or target_provider is None:return status
    s,u=target_request(bundle,raw);targets=target_provider.generate_json(system_prompt=s,user_prompt=u)
    return compose_reading(bundle,raw,targets)
