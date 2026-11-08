"""Opt-in local comparison serialization; no prose inference or approval.

The raw ordered operands are reviewed separately. Projection only renames
positions into the existing canonical contract; it never sorts or fills them.
Complete policy comparisons retain their business-role representation.
"""
from copy import deepcopy
from dataclasses import asdict
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from . import compact_unified_contract as unified
from . import compact_inline_evidence_contract as inline
from .business_field_contract import Field as ReviewField
from .quality_formulator import A0QualityValidationError

CONTRACT = 'ordered-local-comparison-1'
LOCAL_KINDS = ('DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT')
FORMS = ('ORDERED_DIFFERENCE', 'UNSPECIFIED')
EXTRA_STATE_RULES = inline.EXTRA_STATE_RULES
RULES = {
    'first': ReviewField('first', '相减的第一端（被减数）所对应的业务状态。',
        '不等于固定的启用/1或主方案；方向未定时只是第一项待比较状态，不授予顺序。缺端保留UNKNOWN或MISSING。', section='comparison_expression'),
    'second': ReviewField('second', '相减的第二端（减数）所对应的业务状态。',
        '不等于固定的未启用/0或基准；方向未定时只是第二项待比较状态，不授予顺序。缺端保留UNKNOWN或MISSING。', section='comparison_expression'),
    'form': ReviewField('form', '原文是否确定要计算第一端减第二端。',
        'ORDERED_DIFFERENCE只声明该减法；方向未给或未定用UNSPECIFIED，不因为数值未知而判方向未知。引用本问的运算要求，不借用两端引用。', section='comparison_expression'),
}
GUIDANCE = '''本次局部比较使用comparison_expression，适用于DIRECT_EFFECT、SPILLOVER_EFFECT与LOCAL_TOTAL_EFFECT。LOCAL_TOTAL_EFFECT两端同时保留本人及同伴状态；其余安排按各端条件下的原设计平均，不是两份完整固定政策的TOTAL_EFFECT。其他目标类别保持原有comparison_order及semantics.intervention/comparator。
局部比较必须返回comparison_expression={"form":"ORDERED_DIFFERENCE或UNSPECIFIED","first":字段值,"second":字段值,"refs":["本问运算要求的编号"]}；不再返回comparison_order或semantics.intervention/comparator。first与second只表示运算位置，始终计算first减second；不按编码大小、新旧或预期好坏排序。直接效应的两端是本人的两种状态，同伴条件放neighbor_exposure；同伴效应的两端须各保留本人的相同固定状态和该端同伴状态，不擅自指定本人状态。
两个端各自可为STATED/INTERPRETED的value+refs、明确未定时MISSING的reason+refs，或UNKNOWN；不得使用NOT_APPLICABLE。端的内容未定不等于减法方向未定。方向未定用form=UNSPECIFIED，已知两端仍保留，但此时first/second不声明数学顺序。form引用与两端引用分别核对，不自动继承。
例如原文问某做法使等待减少多少，先理解原问的减少量对应哪种状态减哪种状态，再分别填写两端，不把“采用该做法”固定当被减数。aggregation只写结果统计和汇总，不重复运算。评价名单、时期、按何规则平均其余安排仍写各自字段，不填进比较端。其他关于intervention/comparator/comparison_order的命名规则仅用于非局部目标，不用于这两个局部类别。类别、方向、字段内容及引用仍独立审核，程序只序列化，不修正模型答案。'''


class Expression(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    form: Literal['ORDERED_DIFFERENCE', 'UNSPECIFIED']
    first: Any
    second: Any
    refs: list[str] = Field(min_length=1, max_length=20)


def description(rule):
    return rule.meaning + ' ' + rule.excludes


def review_definition(rule):
    if rule.section == 'comparison_expression':
        return dict(asdict(rule), wire_description=description(rule))
    return dict(unified.field_definition(rule, unified.ALIGNMENT_CONTRACT),
                wire_description=unified.field_description(rule, unified.ALIGNMENT_CONTRACT))


def describe(schema):
    unified.describe(schema, contract=unified.ALIGNMENT_CONTRACT)
    defs = schema['$defs']
    local = deepcopy(defs['CompactQuery'])
    local['properties'].pop('comparison_order')
    local['required'].remove('comparison_order')
    local.pop('allOf', None)  # Legacy target/operator conditions apply only to the nonlocal branch.
    local['properties']['kind'] = dict(type='string', enum=list(LOCAL_KINDS))
    local['properties']['semantics'] = {'$ref': '#/$defs/OrderedLocalSemantics'}
    local['properties']['comparison_expression'] = {'$ref': '#/$defs/OrderedLocalExpression'}
    local['required'].append('comparison_expression')
    semantics = deepcopy(defs['CompactSemantics'])
    for name in ('intervention', 'comparator'):
        semantics['properties'].pop(name)
        if name in semantics.get('required', []):
            semantics['required'].remove(name)
    claim = deepcopy(defs['CompactClaim'])
    claim['properties']['state']['enum'].remove('NOT_APPLICABLE')
    claim['properties']['refs'] = {'$ref': '#/$defs/CompactClaim/properties/refs'}
    operand = dict(anyOf=[{'$ref': '#/$defs/OrderedLocalClaim'}, {'$ref': '#/$defs/MissingClaim'},
                          dict(type='string', const='UNKNOWN')])
    expression = Expression.model_json_schema()
    for name in ('first', 'second'):
        expression['properties'][name] = dict(deepcopy(operand), description=description(RULES[name]))
    expression['properties']['form']['description'] = description(RULES['form'])
    expression['properties']['refs'] = {'$ref': '#/$defs/CompactClaim/properties/refs', 'minItems': 1, 'maxItems': 20}
    other = deepcopy(defs['CompactQuery'])
    other['properties']['kind'] = dict(type='string', enum=[v for v in defs['TargetKind']['enum'] if v not in LOCAL_KINDS])
    defs.update(OrderedLocalQuery=local, OrderedLocalSemantics=semantics, OrderedLocalClaim=claim,
                OrderedLocalExpression=expression, NonlocalQuery=other)
    schema['properties']['queries']['items'] = {'oneOf': [
        {'$ref': '#/$defs/OrderedLocalQuery'}, {'$ref': '#/$defs/NonlocalQuery'}]}
    return ''


def system_prompt(**kwargs):
    system = unified.system_prompt(contract=unified.ALIGNMENT_CONTRACT, **kwargs)
    old = '每个query必须有goal、kind、semantics、comparison_order'
    if system.count(old) != 1:
        raise ValueError('HISTORICAL_QUERY_INSTRUCTION_CHANGED')
    system = system.replace(old, '每个query必须有goal、kind、semantics；局部直接/同伴效应用comparison_expression，其余类别用comparison_order', 1)
    system = system.replace('MISSING只用于common/semantics里的单个claim',
                            'MISSING只用于common/semantics里的单个claim及局部comparison_expression的first/second')
    # The historical table remains authoritative for nonlocal queries only.
    lines = system.splitlines()
    for i, line in enumerate(lines):
        if '→' in line:
            for kind in LOCAL_KINDS:
                line = line.replace(kind+'、', '')
            lines[i] = line
        elif line.startswith('比较方向与比较条件分开'):
            lines[i] = '非局部目标使用以下业务角色规则；局部目标遵循下文有序表示。' + line
    system = '\n'.join(lines)
    return system + '\n\n' + GUIDANCE


def _reject(index, suffix, code, allowed=None):
    issue = dict(code=code, path=['queries', index, *suffix])
    if allowed is not None:
        issue['allowed_values'] = allowed
    raise A0QualityValidationError('Ordered local comparison rejected', code='A0_ORDERED_COMPARISON_REJECTED',
        diagnostics=dict(stage='ordered_local_comparison', issue_count=1, issues=[issue]))


def project(raw, catalog):
    from .compact_formulator import CompactClaim
    output = deepcopy(raw)
    if type(output) is not dict or type(output.get('queries')) is not list:
        return inline.project(output, catalog)
    refs = {row['ref'] for row in catalog}
    mappings = []
    for i, q in enumerate(output['queries']):
        if type(q) is not dict:
            continue  # The existing parser rejects the invalid container.
        if q.get('kind') not in LOCAL_KINDS:
            if 'comparison_expression' in q:
                _reject(i, ['comparison_expression'], 'ORDERED_SCOPE_CONFLICT')
            continue
        if 'comparison_order' in q:
            _reject(i, ['comparison_order'], 'ORDERED_LEGACY_FIELD_FORBIDDEN')
        sem = q.get('semantics')
        if type(sem) is not dict:
            _reject(i, ['semantics'], 'ORDERED_OBJECT_REQUIRED')
        for old in ('intervention', 'comparator'):
            if old in sem:
                _reject(i, ['semantics', old], 'ORDERED_LEGACY_FIELD_FORBIDDEN')
        value = q.get('comparison_expression')
        if type(value) is not dict:
            _reject(i, ['comparison_expression'], 'ORDERED_OBJECT_REQUIRED')
        for name in ('form', 'first', 'second', 'refs'):
            if name not in value:
                _reject(i, ['comparison_expression', name], 'missing')
        if value['form'] not in FORMS:
            _reject(i, ['comparison_expression', 'form'], 'ORDERED_FORM_INVALID', list(FORMS))
        try:
            expression = Expression.model_validate(value)
        except ValidationError:
            _reject(i, ['comparison_expression'], 'ORDERED_SHAPE_INVALID')
        if len(set(expression.refs)) != len(expression.refs) or any(r not in refs for r in expression.refs):
            _reject(i, ['comparison_expression', 'refs'], 'ORDERED_REFERENCES_INVALID')
        for name in ('first', 'second'):
            operand = value[name]
            try:
                if operand == 'UNKNOWN':
                    continue
                if type(operand) is not dict or operand.get('state') == 'NOT_APPLICABLE':
                    raise ValueError()
                if operand.get('state') == 'MISSING':
                    parsed = inline.MissingClaim.model_validate(operand)
                    if not parsed.reason.strip():
                        raise ValueError()
                else:
                    parsed = CompactClaim.model_validate(operand)
                if len(set(parsed.refs)) != len(parsed.refs) or any(r not in refs for r in parsed.refs):
                    raise ValueError()
            except (ValidationError, ValueError, TypeError):
                _reject(i, ['comparison_expression', name], 'ORDERED_OPERAND_INVALID')
        q.pop('comparison_expression')
        sem['intervention'], sem['comparator'] = deepcopy(value['first']), deepcopy(value['second'])
        q['comparison_order'] = dict(operation='INTERVENTION_MINUS_COMPARATOR' if expression.form == 'ORDERED_DIFFERENCE' else 'UNSPECIFIED', refs=deepcopy(expression.refs))
        mappings.append(dict(query_index=i, first='semantics.intervention', second='semantics.comparator', form=expression.form))
    projected, details = inline.project(output, catalog)
    details['ordered_local_projection'] = mappings
    return projected, details


def omitted_semantics(query):
    return ('intervention', 'comparator') if query.get('kind') in LOCAL_KINDS else ()


def review_items(raw, query_id):
    query = raw['queries'][int(query_id[1:])-1]
    if query.get('kind') not in LOCAL_KINDS:
        yield from inline.review_items(raw, query_id)
        return
    expression = query['comparison_expression']
    for name in ('first', 'second', 'form'):
        value = dict(form=expression['form'], refs=expression['refs']) if name == 'form' else expression[name]
        state = 'PROPOSED_OPERATOR' if name == 'form' else value.get('state', 'UNKNOWN') if type(value) is dict else value
        yield RULES[name], f'queries.{query_id}.comparison_expression.{name}', value, state


def recheck_field_roles(paths, **kwargs):
    result = unified.recheck_field_roles(paths, contract=unified.ALIGNMENT_CONTRACT)
    for path in dict.fromkeys(paths):
        parts = path.split('/')
        if len(parts) >= 4 and parts[1] == 'queries' and parts[2].isdigit() and parts[3] == 'comparison_expression':
            names = (parts[4],) if len(parts) >= 5 and parts[4] in RULES else tuple(RULES)
            result.append(dict(field_path=path, field_role=' '.join(description(RULES[n]) for n in names)))
    return result


apply_gate = inline.apply_gate
