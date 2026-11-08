"""Clarify aggregation for a single evaluated unit; no runtime field repair."""
import json
from . import fixed_policy_partial as previous

project=previous.project
preview=previous.preview


def make_request(bundle,envelope=None):
    system,user=previous.make_request(bundle,envelope)
    old='aggregation只有明确每人同样权重的平均才填等权平均。'
    if system.count(old)!=1:
        raise ValueError('EXPECTED_AGGREGATION_INSTRUCTION')
    instruction=('aggregation表示如何合成评价对象的平均结果。若只评价一个明确对象，且问它的平均结果，'
        '该对象权重就是1，填等权平均；无需额外要求“每个人权重相同”。'
        '若评价多个对象，只有明确等权平均时才填等权平均；加权方式未定则填不明确。')
    system=system.replace(old,instruction)
    system+='''
单个对象的平均结果表示该对象的总体均值，不是它的一次观测值。这个目标定义不授予总体信息或科学假设。
评价对象与使用名单独立：只评价一个人，仍须保留名册上所有人的已知或未知使用状态，不能删除其他人的安排。
'''
    m=json.loads(user)
    m['output_schema']['$defs']['Conditions']['properties']['aggregation']['description']=instruction
    return system,json.dumps(m,ensure_ascii=False)
