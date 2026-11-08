"""One field-role definition for local first reads, rechecks and reviews.

This opt-in profile changes guidance, not the wire, semantic acceptance,
scientific permissions, or mathematical methods. Older profiles stay frozen.
"""
from . import scoped_role_contract as previous
from .business_field_contract import fields
from .ordered_comparison_contract import LOCAL_KINDS

CONTRACT = 'local-role-ownership-3'
FACT_VERSION = previous.FACT_VERSION
project = previous.project
apply_gate = previous.apply_gate
omitted_semantics = previous.omitted_semantics
EXTRA_STATE_RULES = previous.EXTRA_STATE_RULES
review_items = previous.review_items
clarify_fact_request = previous.clarify_fact_request
fact_constraints = previous.fact_constraints

ROLES = {
    ('common', 'analysis_unit'): (
        '原文定义的基本研究对象及完整对象范围。',
        '保留对象类型、完整名册及原文明示的层级；结果名称、指标定义和计量单位归outcome，不再写入本字段。'
        '不要把对象承担的任务或订单当成研究对象，除非原文明确定义其本身为研究单位。'
        '评价子集和该名单的选择方式、选定时点归target_population；样本记录范围归sample_data_description。'),
    ('semantics', 'target_population'): (
        '本问评价哪些对象，以及原文明示的评价名单选择方式和选定时点。',
        '完整保留已给出的对象范围及其选择限定：是否在分配前选定、分配后按结果筛选，或其他选择规则；'
        '这些属于评价范围的定义，不是time_horizon所问的结果评价期间，也不是研究名册、处理分配名单或样本覆盖名单。'
        '只保留原文明示的时点和规则，名单已列出或历史采用抽签不证明它事先固定；未说明、未决定或冲突仍忠实保留。'
        '不要因部分条件未知而丢弃已知对象。refs共同支持评价选择、名单名称与实际写出的限定；'
        '不能借goal或其他字段补齐本字段。汇总方式和权重归aggregation。'),
}
RULES = {(f.section, f.name): f for section in ('common', 'semantics') for f in fields(section)}


def review_definition(rule):
    result = previous.review_definition(rule)
    if (rule.section, rule.name) in ROLES:
        result = dict(result)
        result['meaning'], result['excludes'] = ROLES[(rule.section, rule.name)]
        result['wire_description'] = result['meaning'] + ' ' + result['excludes']
    return result


def review_semantics(query, rule):
    if query.get('kind') in LOCAL_KINDS and ('semantics', rule.name) in ROLES:
        return review_definition(rule)
    return previous.review_semantics(query, rule)


def describe(schema):
    addition = previous.describe(schema)
    for key, model in ((('common', 'analysis_unit'), 'CompactCommon'),
                       (('semantics', 'target_population'), 'OrderedLocalSemantics')):
        schema['$defs'][model]['properties'][key[1]]['description'] = review_definition(RULES[key])['wire_description']
    return addition


def system_prompt(**kwargs):
    return previous.system_prompt(**kwargs).replace(
        'target_population记录评价谁，',
        'target_population记录评价谁及原文明示的名单选择方式和选定时点，')


def recheck_field_roles(paths, **kwargs):
    rows = previous.recheck_field_roles(paths, **kwargs)
    # Replace broad inherited help only for these explicitly owned fields.
    # Request, review worksheet and nested-value recheck use the same definition.
    for path in dict.fromkeys(paths):
        parts = [p.replace('~1', '/').replace('~0', '~') for p in path.split('/')[1:]]
        key = None
        if len(parts) >= 2 and parts[0] == 'common':
            key = ('common', parts[1])
        elif len(parts) >= 4 and parts[0] == 'queries' and parts[1].isdigit() and parts[2] == 'semantics':
            key = ('semantics', parts[3])
        if key in ROLES:
            rows = [r for r in rows if r['field_path'] != path]
            rows.append(dict(field_path=path, field_role=review_definition(RULES[key])['wire_description']))
    return rows


def fact_focus(raw_query, *, query_id, binding):
    focus = previous.fact_focus(raw_query, query_id=query_id, binding=binding)
    focus['reviewed_business_roles']['contract'] = CONTRACT
    return focus
