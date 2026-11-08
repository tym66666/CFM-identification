"""Opt-in A0 projection that holds unconfirmed interpretations outside slots.

Explicit is the model's reading label, not verified entailment. Holding an
interpretation cannot establish correctness of the remaining claims. Core and
all scientific/estimation approvals remain unavailable.
"""
from __future__ import annotations
from copy import deepcopy
from html import escape
import json
from .schemas import BusinessCase
from .business_formulator import (
    SYSTEM_PROMPT as BASE_SYSTEM, make_business_request, build_business_result)
from .reviewed_intake import render_confirmation_html

PROMPT_VERSION = 'cfm-id-source-facts-experiment-v0.17.1'
GATE_VERSION = 'source-facts-held-interpretations-v0.17.1'
SYSTEM_PROMPT = BASE_SYSTEM + '''
本轮采用“提取已有事实，再确认缺项”的规则：
1. 原文说尚未确定、没决定或不知道的坐标必须留 null；不得因为常见研究习惯而补成相反状态。包括自己未启用、所有同伴未启用、其他人按历史设计平均等。
2. interpretation 不能当作填补缺项的办法。仅当原文支持但需要解释时使用；你想建议的备选方案只能放 notes，并明确这是待确认选项。程序会把所有未确认的解释从规范化事实坐标中隔离。
3. focus 的 own 表示本人行动变化，peers 表示同伴行动变化，both 要两者均变化。如果 A/B 本人都未使用而改变同伴状态，应为 peers；如果原文没有确定比较条件，保留可确定的目标方向，其余坐标仍为 null。
4. 每个text仅保留必要内容：不要把很多文件的名称/行数/列名混成一个长事实；引用必须支持完整文字，资料中有某事实不等于所选引用支持它。
5. 历史分配和目标平均方式是两件事；“历史独立抽签”本身不说明“目标按此平均”。政策优化的总体目标不能替代未给定的具体汇总运算和权重。'''


def make_source_fact_request(case: BusinessCase):
    _, user, catalog = make_business_request(case)
    prefix, separator, schema_text = user.partition('\n输出 Schema：\n')
    schema = json.loads(schema_text)
    for model, names in [('Level', ['situation']), ('Comparison', ['situation_a', 'situation_b'])]:
        for name in names:
            prop = schema['$defs'][model]['properties'][name]
            schema['$defs'][model]['properties'][name] = {'anyOf': [prop, {'type': 'null'}],
                'description': prop['description']+' 整个情形未知时也可填 null，程序视为空情形，不推断任何坐标。'}
    return SYSTEM_PROMPT, prefix+separator+json.dumps(schema, ensure_ascii=False, separators=(',', ':')), catalog


def build_source_fact_result(case: BusinessCase, raw: dict, provider_name: str):
    # First validate all claims, including those that will be held. This cannot
    # hide bad references/shape behind the withholding step.
    normalized = deepcopy(raw)
    normalizations = []
    if isinstance(normalized, dict) and isinstance(normalized.get('goals'), list):
        for i, g in enumerate(normalized['goals'], 1):
            if not isinstance(g, dict):
                continue
            names = {'level': ['situation'], 'comparison': ['situation_a', 'situation_b']}.get(g.get('form'), [])
            for name in names:
                if name in g and g[name] is None:
                    g[name] = {}
                    normalizations.append({'path': f'goals.q{i}.{name}', 'operation': 'DECLARED_NULL_TO_EMPTY_SITUATION'})
    candidate = build_business_result(case, normalized, provider_name)
    original = candidate['business_draft']
    projected = deepcopy(original)
    held = []

    def hold(fact, path):
        if fact is not None and fact['reading'] == 'interpretation':
            held.append({'path': path, 'proposal': deepcopy(fact), 'status': 'NEEDS_SOURCE_OR_BUSINESS_CONFIRMATION'})
            return None
        return fact

    for name, value in projected['facts'].items():
        if name == 'assignment_family':
            continue
        if name == 'covariates':
            projected['facts'][name] = [kept for i, v in enumerate(value)
                if (kept := hold(v, f'facts.covariates.{i}')) is not None]
        else:
            projected['facts'][name] = hold(value, 'facts.'+name)
    if projected['facts']['historical_assignment'] is None:
        projected['facts']['assignment_family'] = 'UNRESOLVED'
    for i, g in enumerate(projected['goals'], 1):
        for name, value in g.items():
            if name in {'question', 'notes', 'form', 'quantity', 'focus', 'task'}:
                # Goal descriptions/classification and notes remain proposals,
                # not identifying coordinates or admitted world facts.
                continue
            path = f'goals.q{i}.{name}'
            if name in {'situation', 'situation_a', 'situation_b'}:
                for coordinate, fact in value.items():
                    value[coordinate] = hold(fact, path+'.'+coordinate)
            else:
                g[name] = hold(value, path)
    result = build_business_result(case, projected, provider_name)
    result['business_draft'] = original
    result['reported_explicit_projection'] = projected
    result['held_interpretations'] = held
    result['wire_normalizations'] = normalizations
    result['prompt_version'] = PROMPT_VERSION
    result['local_gate_version'] = GATE_VERSION
    result['quality']['prompt_version'] = PROMPT_VERSION
    result['interpretation_policy'] = 'Held proposals cannot fill canonical shared facts or query semantic coordinates; explicit labels still require semantic review.'
    # Do not let withholding erase a contradiction seen in the original proposal.
    for issue in candidate['internal_recheck']:
        if issue not in result['internal_recheck']:
            result['internal_recheck'].append(issue)
        if issue not in result['confirmation_card']['internal_recheck']:
            result['confirmation_card']['internal_recheck'].append(issue)
    if held or result['internal_recheck']:
        result['confirmation_card']['status'] = 'SOURCE_RECHECK_REQUIRED'
    result['confirmation_card']['held_interpretations'] = held
    return result


def render_source_fact_html(case: BusinessCase, result: dict):
    html = render_confirmation_html(case, result)
    held = result['held_interpretations']
    if not held:
        return html
    parts = ['<section><h2>待确认的解释</h2><p>以下是模型提出的理解，尚未用来填补规范化事实或比较条件。请先核对原文；只有意思确实如此时，再用普通话确认或修正。</p><ul>']
    for item in held:
        parts.append('<li>'+escape(item['proposal']['text'])+'</li>')
    parts.append('</ul></section>')
    return html.replace('</html>', ''.join(parts)+'</html>')


class SourceFactFormulator:
    def __init__(self, provider):
        self.provider = provider
        self.last_wire = None

    def formulate(self, case: BusinessCase):
        system, user, _ = make_source_fact_request(case)
        self.last_wire = self.provider.generate_json(system_prompt=system, user_prompt=user)
        return build_source_fact_result(case, self.last_wire, self.provider.name)
