"""Focused questions about target meaning, never selected coordinates or methods.

These are program-generated proposals. Source review must distinguish a real
material gap from an extraction error before a business user is asked.
"""
from .business_field_contract import questions


def question(kind, field):
    if field == 'comparison_order':
        return '希望回答一种安排相对另一种增加或减少多少，还是只判断是否有影响？请说明比较要求；尚未决定也可以说明。'
    if field == 'standardization_distribution':
        return '没有固定的其他对象安排，希望按什么规则平均？尚未决定时可以保留，不会自动沿用试点抽签规则。'
    if field == 'neighbor_exposure':
        if kind == 'DIRECT_EFFECT':
            return ('比较本对象使用与不使用时，合作对象的使用情况希望怎样处理：'
                    '保持某种相同情况，还是按某个规则平均？请说明希望比较的业务场景，未决定也可以说明。')
        if kind == 'SPILLOVER_EFFECT':
            return ('希望比较合作对象的哪两种使用情况？在这两种情况下，本对象是否使用应保持怎样的相同状态，'
                    '或按什么共同规则平均？这些选择尚未决定也可以说明。')
    if kind == 'POLICY_OPTIMIZATION':
        if field == 'policy_assignment':
            return '可以从哪些对象中安排使用，有多少名额或预算，还有哪些限制？无需先提供希望由系统选出的名单。'
        if field == 'aggregation':
            return '希望这项安排改善谁的什么结果，整体表现怎样衡量：各对象同等计入，还是采用其他权重或目标？'
    return questions()[field]


def field_path(item):
    prefix = f"queries.{item['query_id']}."
    return prefix + ('' if item['field']=='comparison_order' else 'semantics.') + item['field']
