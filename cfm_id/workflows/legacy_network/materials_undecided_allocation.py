"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import re
import cfm_id.workflows.legacy_network.materials_optional_tables as previous


REMAINING_INSTRUCTION = '''
remaining_source不是“哪里提到了其他人的安排”，而是“哪句肯定说明按原抽签规则作条件平均”。
来源句若说尚未决定、没有说明、待定或不沿用原随机规则，说明这个前提缺失，必须填null。
不能把否定或未定声明引用成肯定支持；也不能用过去试验怎么抽签来替代当前问题的安排。
填写来源前分别检查：原句存在；原句肯定支持这个字段的全部含义。只满足前一项仍填null。
'''


_UNCERTAIN = re.compile(r'(?:尚|还|暂)?(?:未|没|没有)(?:能|有|最终)?(?:决定|确定|定下|说明|商定)|待定|另行决定|'
    r'\b(?:not\s+(?:yet\s+)?(?:decided|specified|determined)|undecided|to\s+be\s+decided)\b', re.I)


_DENIED = re.compile(r'(?:不|并非|不是)(?:再|继续)?(?:按|按照|沿用|遵循).{0,24}(?:抽签|随机|分配)|'
    r'\b(?:do\s+not|not)\s+(?:follow|use)\s+(?:the\s+)?original\s+random', re.I)


def make_request(value):
    system,user=previous.make_request(value)
    message=json.loads(user)
    message['output_schema']['$defs']['Question']['properties']['remaining_source']['description'] = (
        '肯定支持所有局部情形沿原抽签规则作条件平均的目标原句。仅提到安排、说尚未决定/待定/未说明/不沿用时必须null；完整安排也填null。')
    return system+REMAINING_INSTRUCTION,json.dumps(message,ensure_ascii=False)
