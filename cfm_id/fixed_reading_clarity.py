"""Opt-in prompt clarification; the reading contract and validation are unchanged."""
import json
from . import question_bound_assignment as base

PROMPT_REVISION = 'fixed-reading-clarity-1'
AMBIGUOUS_RULE = '只提到一人时，其余填null'
USAGE_RULE = ('只说明一人的使用状态、且材料未说明其余人的使用状态时，其余才填null；'
              '“只评价某人”限定评价对象，不撤销已经说明的其他人的使用状态')


def make_request(bundle):
    system, user = base.make_request(bundle)
    if system.count(AMBIGUOUS_RULE) != 1:
        raise ValueError('EXPECTED_USAGE_RULE_CHANGED')
    system = system.replace(AMBIGUOUS_RULE, USAGE_RULE)
    message = json.loads(user)
    fields = message['output_schema']['$defs']['Conditions']['properties']
    fields['first']['description'] = (
        '第一种完整使用安排：node_order中每个对象的使用状态。与population独立；'
        '明确使用填1、明确不用填0、未说明才填null。不评价某人不代表不知道其使用状态。')
    fields['second']['description'] = (
        '比较时为第二种完整使用安排，同样覆盖全部名册；水平问题为null。'
        '不得根据评价对象筛掉安排中的任何人。')
    fields['population']['description'] = (
        '只列要汇总谁的结果，与谁使用工具是两件事。不能把使用名单当评价名单，'
        '也不能把未纳入评价者的已知使用状态改为null。评价范围未定则null。')
    system += '''
输出前分别核对两件事：所有对象各自用不用，以及最后汇总谁的结果。
“只评价某对象”只限制population；“只有某对象使用，其余不用”限制使用安排；
“其余是否使用未定”才使对应使用状态为null。只采用当前材料明确表达的事实。
JSON层级固定为：
根对象
  reading
    intents
    questions
  reported_assignment
reading与reported_assignment是同级字段；reading内部不能放reported_assignment。
这只是字段含义和结构核对，不生成新事实、不批准科学假设、不修复缺项。
'''
    return system, json.dumps(message, ensure_ascii=False)


def read_once(bundle, provider):
    """One request, unchanged strict preview, no repair, retry, or approval."""
    system, user = make_request(bundle)
    raw = provider.generate_json(system_prompt=system, user_prompt=user)
    return base.preview(bundle, raw)

