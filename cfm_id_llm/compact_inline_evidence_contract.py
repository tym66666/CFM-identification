"""Mutually exclusive field values or source-absence proposals; no inference."""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from . import business_field_contract as fields
from . import compact_evidence_contract as legacy
from .quality_formulator import A0QualityValidationError

CONTRACT = 'inline-evidence-1'
EXTRA_STATE_RULES = {
    'MISSING': '模型称原文明示本字段未提供/未决定；reason及refs是缺失说明，'
               '不是字段值。须核查全部原文，仍可能是误读；投影为UNKNOWN，不授科学许可。'
}
GUIDANCE = '''
本协议将确定值与明确缺失说明放在同一个字段，互斥选择，不返回顶层missing_information清单，不写field_path。
common的单个claim字段及semantics字段有三种情况：原文给出该字段所问的确定内容，沿用STATED/INTERPRETED、value、refs；原文明示该字段未提供、尚未决定或存在未解决冲突，使用{"state":"MISSING","reason":"原文的未定/缺失说明","refs":["对应编号"]}，不能再带value；材料没有提供内容、也没有明示缺失原因时，仍用UNKNOWN，不编造reason或引用。需要比较但基准未定，基准为MISSING，不能写NOT_APPLICABLE。仅在原规则允许时使用NOT_APPLICABLE。
MISSING只表达来源中关于本字段的缺失声明，不证明没有其他原文给出答案；仍需独立审核。不能把否定词当成缺失判断：没有抽签但由负责人选择，给出了历史机制；名单没有调整，给出了时间稳定性；明确没有对象间联系，给出了关系事实。这些应保留确定值。没有开展随机试点本身不说明具体的历史分配办法。变量已给出但未观测，与变量不存在也不同。goal仍完整保留已定部分和未定原因，不能将未知条件改成已确定。
MISSING不用于goal、枚举、协变量列表或comparison_order。covariates仅列出原文实际说明的背景变量及可观测性，不将处理、结果、资料列表或缺失说明当作背景变量。没有相应变量就用空列表；不为填满而补造。
每个query仍必须有comparison_order，包含operation及引用实际问题的refs。intervention/policy_assignment保留主方案，comparator保留基准；明确问主方案相对基准增加多少时用INTERVENTION_MINUS_COMPARATOR，明确问主方案使结果降低多少时用COMPARATOR_MINUS_INTERVENTION，不按新旧或出现顺序机械选择。明确方向未定用UNSPECIFIED；单方案水平或分别报告水平用NOT_APPLICABLE。方向未定只在operation及goal保留，不另造缺失记录。基准未定不必然表示增加/下降方向未定。
本协议替代前文在aggregation中写减法方向的格式要求：aggregation只写原文的结果量、汇总和权重，方向单独写comparison_order。程序只序列化已声明的运算及来源，不判断其是否读对。所有字段仍须独立逐项来源审核，不补总体信息、科学许可或识别结论。'''


class MissingClaim(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    state: Literal['MISSING']
    reason: str = Field(min_length=1, max_length=2500)
    refs: list[str] = Field(min_length=1, max_length=20)


def describe(schema):
    # Reuse the exact signed operator schema and target projection contract.
    legacy.describe(schema)
    schema['properties'].pop('missing_information')
    schema['required'].remove('missing_information')
    schema['$defs'].pop('MissingInformation')
    definition = MissingClaim.model_json_schema()
    definition['properties']['refs'] = {
        '$ref': '#/$defs/CompactClaim/properties/refs', 'minItems': 1, 'maxItems': 20}
    schema['$defs']['MissingClaim'] = definition
    for section, model in (('common', 'CompactCommon'), ('semantics', 'CompactSemantics')):
        for rule in fields.fields(section):
            if rule.shape != 'claim':
                continue
            prop = schema['$defs'][model]['properties'][rule.name]
            prop['anyOf'].append({'$ref': '#/$defs/MissingClaim'})
            prop['description'] = prop.get('description', '') + (
                ' 本协议：原文明示本字段内容未提供/未定时用MISSING+reason+refs，不带value；'
                '仅未读到内容则UNKNOWN。确定值仍用STATED/INTERPRETED，不另写缺失清单。')
    return GUIDANCE


def project(raw, catalog):
    """Serialize the declared MISSING state as unknown, never classify prose."""
    try:
        if type(raw) is not dict or 'missing_information' in raw:
            raise ValueError('Separate missing-information list is forbidden')
        output = deepcopy(raw)
        notes = []

        def convert(container, section, prefix):
            if type(container) is not dict:
                raise ValueError('Invalid section')
            for rule in fields.fields(section):
                value = container.get(rule.name)
                if rule.shape != 'claim' or type(value) is not dict or value.get('state') != 'MISSING':
                    continue
                note = MissingClaim.model_validate(value)
                if not note.reason.strip():
                    raise ValueError('Blank missing reason')
                notes.append(dict(field_path=prefix+rule.name, reason=note.reason, refs=note.refs))
                container[rule.name] = 'UNKNOWN'

        convert(output.get('common'), 'common', 'common.')
        if type(output.get('queries')) is not list:
            raise ValueError('Invalid queries')
        for i, q in enumerate(output['queries'], 1):
            convert(q.get('semantics'), 'semantics', f'queries.q{i}.semantics.')
        output['missing_information'] = notes
        projected, details = legacy.project(output, catalog)
        details['absence_representation'] = 'MISSING_STATE_ON_ORIGINAL_FIELD'
        return projected, details
    except A0QualityValidationError as exc:
        # Retain the legacy public reason while preserving the precise inner location.
        raise A0QualityValidationError('Inline evidence rejected', code='A0_INLINE_EVIDENCE_REJECTED',
            diagnostics=exc.diagnostics) from None
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
        raise A0QualityValidationError('Inline evidence rejected', code='A0_INLINE_EVIDENCE_REJECTED') from None


def review_items(raw, query_id):
    # MISSING is already reviewed on its original common/semantics field, once.
    yield from legacy.review_items(dict(raw, missing_information=[]), query_id)


apply_gate = legacy.apply_gate
