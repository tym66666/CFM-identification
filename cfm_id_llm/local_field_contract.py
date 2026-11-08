"""Opt-in field-local guidance; unchanged wire, reviews and mathematical scope.

First reads and explicit rechecks share these definitions. Nothing here reads
business prose, finds evidence, changes candidates or approves assumptions.
"""
import json
from . import local_population_contract as previous

CONTRACT = 'local-role-ownership-4'
FACT_VERSION = previous.FACT_VERSION
# MISSING here means absence of population information, not merely of numbers.
# Runtime binds this independently reviewed state; no prose interpretation.
BIND_POPULATION_INFORMATION = True
project = previous.project
apply_gate = previous.apply_gate
omitted_semantics = previous.omitted_semantics
EXTRA_STATE_RULES = previous.EXTRA_STATE_RULES
review_items = previous.review_items
review_semantics = previous.review_semantics
system_prompt = previous.system_prompt
RULES = previous.RULES

ROLES = {
    ('common', 'analysis_unit'): (
        '原文定义的基本研究对象及完整对象范围。',
        '保留对象类型、名称和层级。处理行动及其编码归treatment，结果定义及单位归outcome，'
        '不在研究对象字段复写。评价名单及其选择限定归target_population，记录覆盖归sample_data_description。'),
    ('common', 'available_information'): (
        '资料声明可使用的可观察总体信息的内容及范围。',
        '已声明总体分布、总体均值、总体量的部分信息或符号总体信息范围，用STATED的value和refs；'
        '没有数值不等于没有符号总体信息。明确没有或尚未提供时，用MISSING的reason和refs，不带value；'
        '未谈及则UNKNOWN。信息部分已知时保留已知内容及明确局限，不能全部抹成MISSING。'
        '有限记录、样本统计与抽样置信区间归sample_data_description，不升级为总体信息。'
        '科学建模条件随原材料交后续读取，不填成可观察信息，也不能据此默认批准A4或A5。'),
}
ARM_SELECTION = (
    '本端source_ids引用业务原文实际选择本人状态和同伴状态的语句。'
    '两端共同条件在两个端各自引用；分散在不同原句时共同引用。'
    '编码定义只解释0/1的含义，由definition_refs声明，不能代替本问选择哪个状态的来源。'
    '状态未明确时仍为null，不根据编码表、目标类别或另一端猜测。')


def review_definition(rule):
    result = previous.review_definition(rule)
    if (rule.section, rule.name) in ROLES:
        result = dict(result)
        result['meaning'], result['excludes'] = ROLES[(rule.section, rule.name)]
        result['wire_description'] = result['meaning'] + ' ' + result['excludes']
    return result


def describe(schema):
    addition = previous.describe(schema)
    for key in ROLES:
        schema['$defs']['CompactCommon']['properties'][key[1]]['description'] = review_definition(RULES[key])['wire_description']
    return addition


def recheck_field_roles(paths, **kwargs):
    rows = previous.recheck_field_roles(paths, **kwargs)
    for path in dict.fromkeys(paths):
        parts = [p.replace('~1', '/').replace('~0', '~') for p in path.split('/')[1:]]
        key = tuple(parts[:2])
        if key in ROLES:
            rows = [r for r in rows if r['field_path'] != path]
            rows.append(dict(field_path=path, field_role=review_definition(RULES[key])['wire_description']))
    return rows


def clarify_fact_request(request):
    result = previous.clarify_fact_request(request)
    body = json.loads(result['user'])
    body['output_schema']['$defs']['LocalArm']['properties']['source_ids']['description'] = ARM_SELECTION
    return dict(result, user=json.dumps(body, ensure_ascii=False))


def fact_constraints(paths):
    rows = previous.fact_constraints(paths)
    for path in dict.fromkeys(paths):
        parts = path.split('/')[1:]
        if len(parts) >= 2 and parts[0] == 'target' and parts[1] in ('reference', 'evaluated'):
            rows = [r for r in rows if r['field_path'] != path]
            rows.append(dict(field_path=path, description=ARM_SELECTION))
    return rows


def fact_focus(raw_query, *, query_id, binding):
    focus = previous.fact_focus(raw_query, query_id=query_id, binding=binding)
    focus['reviewed_business_roles']['contract'] = CONTRACT
    return focus
