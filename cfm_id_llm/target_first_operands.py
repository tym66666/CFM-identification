"""Target-first reading with literal arithmetic operands, including local effects.

Compatibility aliases are serialization, never an interpretation of prose.
The original response and each operand's citations remain review obligations.
"""
from copy import deepcopy
from . import target_first_reading as previous
from . import query_conditioning_contract as conditioning
from .business_field_contract import Field, COMMON, SEMANTICS
from .quality_formulator import A0QualityValidationError

CONTRACT = 'target-first-operands-1'
COMMON_FIELDS = previous.COMMON_FIELDS
DEFERRED_COMMON = previous.DEFERRED_COMMON
EXTRA_STATE_RULES = previous.EXTRA_STATE_RULES
BIND_POPULATION_INFORMATION = False
FIRST = Field('first_arrangement', '差值的被减数一端；单个水平问题中是所问安排。',
    '忠实保留本人、同伴或完整政策的条件。不是固定的新方案角色；减少量通常先放原方案。', section='semantics')
SECOND = Field('second_arrangement', '差值的减数一端，与第一端共同定义所问差值。',
    '不是固定的原方案角色。单个水平用NOT_APPLICABLE；基准未决定用MISSING。', section='semantics')
ORDER = Field('comparison_order', '差值严格表示first_arrangement减second_arrangement。',
    '先按问题确定两端；方向未说明保留UNSPECIFIED，单水平用NOT_APPLICABLE。', section='query')

def system_prompt(**kwargs):
    text = previous.SYSTEM
    text = text.replace('固定政策的行动只写intervention；不输出policy_assignment。选择政策时intervention可以UNKNOWN，',
                        '固定政策只写first_arrangement；不输出intervention、comparator或policy_assignment。选择政策时first_arrangement可以UNKNOWN，')
    start = text.index('comparison_order只声明运算方向；')
    end = text.index('\n字段已明确', start)
    text = text[:start] + ('差值的两端直接按数学顺序填写：first_arrangement是被减数，second_arrangement是减数，'
        'comparison_order.operation用FIRST_MINUS_SECOND。问减少多少时通常是原安排减新安排；'
        '问增加多少时通常是新安排减原安排。不再独立命名主方案和基准。单水平只填第一端，第二端及operation为NOT_APPLICABLE；'
        '原文未确定方向用UNSPECIFIED，不猜符号。') + text[end:]
    return text.replace('无需对照的comparator', '无需对照的second_arrangement')

def describe(schema):
    previous.describe(schema)
    sem = schema['$defs']['CompactSemantics']
    for old, rule in (('intervention',FIRST), ('comparator',SECOND)):
        sem['properties'][rule.name] = sem['properties'].pop(old)
        sem['properties'][rule.name]['description'] = rule.meaning+' '+rule.excludes
    sem['required'] += ['first_arrangement','second_arrangement']
    schema['$defs']['ComparisonOrder']['properties']['operation']['enum'] = [
        'FIRST_MINUS_SECOND','UNSPECIFIED','NOT_APPLICABLE']
    schema['$defs']['ComparisonOrder']['description'] = ORDER.meaning+' '+ORDER.excludes
    return ''

def _legacy(raw):
    output=deepcopy(raw)
    try:
        for q in output['queries']:
            sem=q['semantics']
            if any(k in sem for k in ('intervention','comparator','policy_assignment')):
                raise ValueError('DUPLICATE_OPERAND_ALIAS')
            sem['intervention']=sem.pop('first_arrangement')
            sem['comparator']=sem.pop('second_arrangement')
            op=q['comparison_order']['operation']
            if op not in ('FIRST_MINUS_SECOND','UNSPECIFIED','NOT_APPLICABLE'):
                raise ValueError('INVALID_OPERAND_OPERATION')
            if op=='FIRST_MINUS_SECOND':
                q['comparison_order']['operation']='INTERVENTION_MINUS_COMPARATOR'
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        raise A0QualityValidationError('Target operands rejected', code='TARGET_OPERANDS_REJECTED',
            diagnostics={'stage':'target_operands','reason':str(exc)[:160]}) from None
    return output

def project(raw,catalog):
    projected,details=previous.project(_legacy(raw),catalog)
    details['target_first']['contract']=CONTRACT
    details['target_first']['operand_aliases']={
        'first_arrangement':'intervention','second_arrangement':'comparator',
        'FIRST_MINUS_SECOND':'INTERVENTION_MINUS_COMPARATOR'}
    return projected,details

def apply_gate(gate,details):
    previous.apply_gate(gate,details)
    gate['reading_path']=CONTRACT

def omitted_semantics(query):
    return ('policy_assignment','intervention','comparator')

review_definition=previous.review_definition
review_semantics=previous.review_semantics

def review_items(raw,query_id):
    q=raw['queries'][int(query_id[1:])-1]
    yield ORDER,f'queries.{query_id}.comparison_order',q['comparison_order'],'PROPOSED_OPERATOR'
    for rule in (FIRST,SECOND,conditioning.RULE,previous.OUTCOME,previous.DECISION):
        value=q['semantics'][rule.name]
        yield rule,f'queries.{query_id}.semantics.{rule.name}',value,conditioning.state(value)

def recheck_field_roles(paths,**kwargs):
    rules={r.name:r for r in (*COMMON,*SEMANTICS,FIRST,SECOND,ORDER,conditioning.RULE,previous.OUTCOME,previous.DECISION)}
    rows=[]
    for path in dict.fromkeys(paths):
        names=path.replace('.', '/').split('/')
        rule=next((rules[n] for n in reversed(names) if n in rules),None)
        rows.append(dict(field_path=path,field_role=rule.meaning+' '+rule.excludes if rule else '核对原问、类别与来源，不补值。'))
    return rows

def target_context(raw_query,*,query_id):
    result=previous.target_context(raw_query,query_id=query_id)
    result['contract']=CONTRACT
    return result

admission=previous.admission
