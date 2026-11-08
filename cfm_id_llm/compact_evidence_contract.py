"""Opt-in source-absence notes and signed comparison operators.

Typed proposals, not inferred facts. Keep raw answers intact, project only a
declared operator, and require independent field review before fact reading.
"""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from . import business_field_contract as fields
from .quality_formulator import A0QualityValidationError
from .comparison_operator_contract import EFFECTS, LEVELS, allowed_operations, conflict_issue

CONTRACT = 'evidence-slots-1'
OPERATORS = {'INTERVENTION_MINUS_COMPARATOR': '主方案减基准方案',
             'COMPARATOR_MINUS_INTERVENTION': '基准方案减主方案'}
GUIDANCE = '''
本次另用两个独立位置表达来源缺失和差值方向，不再将它们挤进事实值。
顶层missing_information必须返回列表。仅当原文明确说明某字段未提供、尚未决定或有未解决冲突时，列出field_path、reason及支持该缺失说明的refs；对应字段仍为UNKNOWN。field_path用common.字段名或queries.q1.semantics.字段名（q1是第一个问题）。没有原文明示的缺失说明就不写该条，不给沉默的资料编理由；已定字段不能再列为缺失，部分已知的口径在goal和原文保留。reason不是字段值，不是科学结论，也不自动证明该值真的无法从其他原文得到。
每个query必须返回comparison_order对象，包含operation和refs。intervention/policy_assignment仍保留主方案，comparator保留基准，不为改变减法方向交换这两个语义角色。明确问主方案相对基准增加多少，用INTERVENTION_MINUS_COMPARATOR；明确问主方案使结果降低多少，用COMPARATOR_MINUS_INTERVENTION。不要只按新旧顺序或句中出现顺序选择。其他措辞也按用户实际要求的有向量读取。单方案水平或分别报告水平时用NOT_APPLICABLE；比较方向未给出用UNSPECIFIED，不推定正负。不知道差值的数值不等于方向未知。refs引用实际问题；编号有效仍不等于含义正确。
本协议替代前文关于在aggregation中记录减法方向的格式要求：aggregation仅写原文要求的结果量、对象汇总及权重，不再重复写减法方向；方向由comparison_order表达，goal仍忠实保留完整业务问题。程序会将声明的有向运算标注到下游目标中，但不会验证它是否读对，仍须独立逐项来源审核。缺失说明也需独立核对；不得借新位置补总体信息、科学许可或识别公式。'''


class MissingInformation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    field_path: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2500)
    refs: list[str] = Field(min_length=1, max_length=20)


class ComparisonOrder(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    operation: Literal['INTERVENTION_MINUS_COMPARATOR', 'COMPARATOR_MINUS_INTERVENTION',
                       'UNSPECIFIED', 'NOT_APPLICABLE']
    refs: list[str] = Field(min_length=1, max_length=20)


def describe(schema):
    for model in (MissingInformation, ComparisonOrder):
        definition = model.model_json_schema()
        definition['properties']['refs'] = {'$ref': '#/$defs/CompactClaim/properties/refs', 'minItems': 1, 'maxItems': 20}
        schema['$defs'][model.__name__] = definition
    schema['properties']['missing_information'] = {
        'type': 'array', 'maxItems': 80, 'items': {'$ref': '#/$defs/MissingInformation'}}
    schema['required'].append('missing_information')
    query = schema['$defs']['CompactQuery']
    query['properties']['comparison_order'] = {'$ref': '#/$defs/ComparisonOrder'}
    query['required'].append('comparison_order')
    schema['$defs']['CompactSemantics']['properties']['aggregation']['description'] += (
        ' 本协议仅写结果量、汇总和权重，减法方向另填comparison_order；不在这里重复方向。')
    return GUIDANCE


def _unknown(value):
    return value == 'UNKNOWN' or (type(value) is dict and value.get('state', 'UNKNOWN') == 'UNKNOWN')


def project(raw, catalog):
    """Validate extension, remove it from legacy projection, retain audit metadata."""
    try:
        if type(raw) is not dict or type(raw.get('queries')) is not list:
            raise ValueError('Invalid container')
        notes = raw.get('missing_information')
        if type(notes) is not list or len(notes) > 80:
            raise ValueError('Missing notes list')
        known_refs = {r['ref'] for r in catalog}

        def check_refs(refs):
            if len(set(refs)) != len(refs) or any(r not in known_refs for r in refs):
                raise ValueError('Invalid references')

        allowed = {'common.' + f.name: raw.get('common', {}).get(f.name, 'UNKNOWN')
                   for f in fields.COMMON if f.shape == 'claim'}
        for i, q in enumerate(raw['queries'], 1):
            allowed.update({f'queries.q{i}.semantics.' + f.name: q.get('semantics', {}).get(f.name, 'UNKNOWN')
                            for f in fields.SEMANTICS})
        seen = set()
        for item in notes:
            note = MissingInformation.model_validate(item)
            check_refs(note.refs)
            if note.field_path in seen or note.field_path not in allowed or not _unknown(allowed[note.field_path]):
                raise ValueError('Invalid missing-information target')
            if not note.reason.strip():
                raise ValueError('Blank reason')
            seen.add(note.field_path)
        output = deepcopy(raw)
        output.pop('missing_information')
        orders, issues = {}, []
        for i, q in enumerate(output['queries'], 1):
            order = ComparisonOrder.model_validate(q.pop('comparison_order', None))
            check_refs(order.refs)
            qid = f'q{i}'; orders[qid] = order.model_dump()
            kind = q.get('kind')
            if order.operation not in allowed_operations(kind):
                raise A0QualityValidationError('Evidence slots rejected', code='A0_EVIDENCE_SLOTS_REJECTED',
                    diagnostics=dict(stage='comparison_order', issue_count=1,
                        issues=[conflict_issue(i - 1, kind)]))
            if kind in EFFECTS and order.operation == 'UNSPECIFIED':
                issues.append(dict(code='COMPARISON_DIRECTION_UNRESOLVED', path=f'queries.{qid}.comparison_order',
                                   detail='Recheck direction against original sources before clarification; do not select a sign.'))
            if order.operation in OPERATORS:
                aggregation = q.get('semantics', {}).get('aggregation')
                if type(aggregation) is dict and aggregation.get('state') in ('STATED', 'INTERPRETED'):
                    # Deterministic serialization of the proposed operator, never a meaning repair.
                    aggregation['value'] = aggregation.get('value', '') + '；比较运算：' + OPERATORS[order.operation]
                    aggregation['refs'] = list(dict.fromkeys([*aggregation.get('refs', []), *order.refs]))
        return output, dict(missing_information=deepcopy(notes), comparison_orders=orders, issues=issues,
                            semantic_correctness_verified=False, scientific_approval=False)
    except A0QualityValidationError:
        raise  # Keep bounded source-owned field diagnostics, not raw candidate text.
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
        raise A0QualityValidationError('Evidence slots rejected', code='A0_EVIDENCE_SLOTS_REJECTED') from None


def apply_gate(gate, details):
    gate['evidence_slots'] = deepcopy(details)
    gate['issues'].extend(details['issues'])
    if details['issues']:
        gate['status'] = 'FORMULATION_RECHECK_REQUIRED'


def clarify_fact_order(request):
    """Clarify endpoint notation only for this opt-in protocol's next reader.

    Business roles (main/baseline) are not arithmetic positions. Keep the base
    contract and every old request unchanged; never order policies in code.
    """
    old = 'first是所问相对变化的方案，second是基准，operation为FIRST_MINUS_SECOND；'
    new = ('first仅表示相减运算的第一端，second表示第二端，operation为FIRST_MINUS_SECOND。'
           'first/second不是主方案/基准这两个业务角色的固定别名：主方案相对基准增加多少时为主方案减基准；'
           '主方案使结果降低多少时为基准减主方案，此时first放基准、second放主方案。'
           '按完整原文核对，不把A0候选及其comparison_order当新增事实或批准；')
    if request['system'].count(old) != 1:
        raise ValueError('EVIDENCE_SLOTS_CONTRAST_INSTRUCTION_CHANGED')
    return dict(request, system=request['system'].replace(old, new))


def review_items(raw, query_id):
    """Additional source claims that must be reviewed; no natural-language tests."""
    i = int(query_id[1:]) - 1
    order_rule = fields.Field('comparison_order', '用户实际要求的有向比较；与goal、主方案和基准一起核对。',
                             '方向是模型候选，不能按新旧顺序推定；单水平不造差值。', section='query')
    yield order_rule, f'queries.{query_id}.comparison_order', raw['queries'][i]['comparison_order'], 'PROPOSED_OPERATOR'
    for n, note in enumerate(raw['missing_information']):
        path = note['field_path']
        if path.startswith('common.') or path.startswith(f'queries.{query_id}.'):
            prefix = 'common' if path.startswith('common.') else f'queries.{query_id}'
            rule = fields.Field('missing_information', '原文明确的缺失/未定说明，核对所指字段与全部原文。',
                                '不是该字段的已知值；引用真实也不证明材料其他位置没有给出答案。',
                                section='common' if prefix == 'common' else 'query')
            yield rule, f'{prefix}.missing_information[{n}]', note, 'SOURCE_ABSENCE_PROPOSAL'
