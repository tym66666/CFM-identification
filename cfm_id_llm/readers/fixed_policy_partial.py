"""Require explicit partial arrangements in the fixed-policy prompt schema.

Runtime validation is unchanged. No null response is repaired into coordinates.
"""
import json
from copy import deepcopy
from . import fixed_policy_base as base

project = base.project
preview = base.preview


def make_request(bundle, envelope=None):
    system, user = base.make_request(bundle, envelope)
    m = json.loads(user)
    schema = m['output_schema']
    arrangement = dict(type='object', additionalProperties=False, required=bundle['node_order'],
        properties={n: {'enum': [0, 1, None]} for n in bundle['node_order']})
    for qid in bundle['question_slots']:
        for kind, sides in (('比较', ('first', 'second')), ('水平', ('first',))):
            schema.setdefault('allOf', []).append({
                'if': {'properties': {'intents': {'properties': {qid: {'properties': {'kind': {'const': kind}}}}}}},
                'then': {'properties': {'questions': {'properties': {qid: {'properties': {
                    side: deepcopy(arrangement) for side in sides}}}}}}})
    system += '''
输出前核对：kind=比较时，first和second必须分别是包含所有名册编号的对象，任何一端都不能是null。
两端安排都未决定时，两个对象内每个人都填null，而不是将second整个设为null。
kind=水平时first也保留完整对象，已知项不丢失，未知项填null；second才为null。这只是表示缺项，不替用户决定安排。
'''
    return system, json.dumps(m, ensure_ascii=False)
