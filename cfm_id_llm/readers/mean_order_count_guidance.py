"""Opt-in count-field guidance layered on the factored reading request.

Only two JSON Schema descriptions change. No candidate values are inferred,
rewritten or approved. Keep this separate from the default reader while the
small live diagnostic is extended.
"""
import json
from cfm_id_llm.readers import mean_order as protocol

DESCRIPTIONS={
    'fixed_count':'只提取原试点明确声明每轮恰好固定的启用人数。仅声明最多或不超过某数时，这个数不能填入fixed_count；固定人数没有说明就填null。',
    'maximum_count':'只提取原试点原文另行明确声明的人数上限，不是数学上可推导的最大值。若只说每轮固定或恰好k人，没有另行声明上限，则填null，不要再把k填在这里。'
}

def make_request(bundle):
    system,user=protocol.make_request(bundle)
    payload=json.loads(user)
    fields=payload['output_schema']['properties']['comparison']['properties']['reported_assignment']['properties']
    for name,text in DESCRIPTIONS.items():
        if 'description' in fields[name]:
            raise ValueError('COUNT_FIELD_ALREADY_HAS_GUIDANCE_REVIEW_REQUIRED')
        fields[name]['description']=text
    return system,json.dumps(payload,ensure_ascii=False)
