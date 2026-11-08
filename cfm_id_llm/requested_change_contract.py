"""Auditable quantity roles compiled to ordered operands, never inferred from prose."""
from copy import deepcopy
from dataclasses import asdict
from typing import Any, Literal
import json
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from . import ordered_comparison_contract as ordered, ordered_target_handoff as handoff
from .business_field_contract import Field as ReviewField
from .quality_formulator import A0QualityValidationError

CONTRACT='local-change-quantity-1'
QUANTITIES=('INCREASE','REDUCTION','REFERENCE_MINUS_EVALUATED','EVALUATED_MINUS_REFERENCE','UNSPECIFIED')
# Explicit finite syntax mapping, independent of treatment codes, outcome or words.
POSITIONS={'INCREASE':('evaluated','reference'),'REDUCTION':('reference','evaluated'),
    'REFERENCE_MINUS_EVALUATED':('reference','evaluated'),'EVALUATED_MINUS_REFERENCE':('evaluated','reference'),
    'UNSPECIFIED':('reference','evaluated')}
omitted_semantics=ordered.omitted_semantics
apply_gate=ordered.apply_gate
EXTRA_STATE_RULES=ordered.EXTRA_STATE_RULES
GUIDANCE='''局部DIRECT_EFFECT/SPILLOVER_EFFECT/LOCAL_TOTAL_EFFECT使用comparison_request，分别填写reference、evaluated、quantity、refs。LOCAL_TOTAL_EFFECT的两端同时写本人和同伴状态，不能改写为完整固定政策。
reference是比较的参照状态，evaluated是相对于参照被评价的状态，不是被减数和减数。依据原文角色：采用B相比保持A，reference=A、evaluated=B；从A变到B同理。不要按结果好坏或编码大小调换角色。
quantity描述用户请求的量：增加/多出多少为INCREASE，减少/少了/节省多少为REDUCTION，方向未给或明确未定为UNSPECIFIED。不要将所有效应统一理解为采用措施减不采用。INCREASE编译为evaluated减reference；REDUCTION编译为reference减evaluated，均允许结果为负。
原文明确X减Y时优先保留算式。已有参照角色时选择REFERENCE_MINUS_EVALUATED或EVALUATED_MINUS_REFERENCE；没有指定角色时可将X作为reference、Y作为evaluated并选择REFERENCE_MINUS_EVALUATED。不得因附近的增加、减少或改善词改变显式算式。
直接效应两端写本人状态，共同同伴条件放neighbor_exposure；同伴效应两端分别保留相同的本人状态和各端同伴条件。本人未定时两端用MISSING保留未定原因和原文引用，已知同伴条件仍写在neighbor_exposure及goal。某端缺条件不等于quantity方向未定。
每个端的状态与refs独立，quantity自己的refs引用用户请求的量。不要输出comparison_expression、comparison_order或semantics.intervention/comparator，不输出算式、自评或批准。'''
RULES={
    'reference':ReviewField('reference','本次比较的参照状态。','不固定为0，也不固定为减法第一端；未知条件和来源须保留。',section='comparison_request'),
    'evaluated':ReviewField('evaluated','相对于参照被评价的状态。','不固定为1，也不固定为减法第一端；同伴比较两端各保留本人条件。',section='comparison_request'),
    'quantity':ReviewField('quantity','用户所问的增量、减少量、显式有向差或未定向比较。',
        'INCREASE=evaluated-reference；REDUCTION=reference-evaluated；显式方向按枚举。UNSPECIFIED不授予顺序。仅表示所问量，不预言效果符号。',section='comparison_request')}
LOCAL_ROLES=dict(handoff.LOCAL_ROLES)
LOCAL_ROLES['neighbor_exposure']=(handoff.LOCAL_ROLES['neighbor_exposure'][0],
    '直接效应保留共同同伴条件；同伴效应保留本人固定或明确未定状态及两种同伴条件。目标方向只由comparison_request.quantity及角色决定，不在此另排两端。')
LOCAL_ROLES['aggregation']=(handoff.LOCAL_ROLES['aggregation'][0],
    '评价对象、安排平均与比较请求分别填写target_population、standardization_distribution和comparison_request；无需在本字段重复其他字段的名称和编码。')

class ChangeRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    reference: Any
    evaluated: Any
    quantity: Literal['INCREASE','REDUCTION','REFERENCE_MINUS_EVALUATED','EVALUATED_MINUS_REFERENCE','UNSPECIFIED']
    refs: list[str]=Field(min_length=1,max_length=20)

def definition(rule):
    if rule.section=='comparison_request':return dict(asdict(rule),wire_description=rule.meaning+' '+rule.excludes)
    return handoff.review_definition(rule)
review_definition=definition

def review_semantics(query,rule):
    if query.get('kind') in ordered.LOCAL_KINDS and rule.name in LOCAL_ROLES:
        d=definition(rule);d['meaning'],d['excludes']=LOCAL_ROLES[rule.name];d['wire_description']=' '.join(LOCAL_ROLES[rule.name]);return d
    return ordered.review_definition(rule)

def describe(schema):
    handoff.describe(schema);defs=schema['$defs'];q=defs['OrderedLocalQuery']
    old=defs.pop('OrderedLocalExpression');expression=ChangeRequest.model_json_schema()
    for new,previous in (('reference','first'),('evaluated','second')):expression['properties'][new]=deepcopy(old['properties'][previous])
    for name in RULES:expression['properties'][name]['description']=definition(RULES[name])['wire_description']
    expression['properties']['refs']=deepcopy(old['properties']['refs'])
    defs['LocalChangeRequest']=expression
    q['properties'].pop('comparison_expression');q['properties']['comparison_request']={'$ref':'#/$defs/LocalChangeRequest'}
    q['required']=['comparison_request' if k=='comparison_expression' else k for k in q['required']]
    for name in LOCAL_ROLES:defs['OrderedLocalSemantics']['properties'][name]['description']=' '.join(LOCAL_ROLES[name])
    return ''

def system_prompt(**kwargs):
    system=handoff.system_prompt(**kwargs)
    start=system.index('局部DIRECT_EFFECT/SPILLOVER_EFFECT采用有序表达')
    end=system.index('非局部目标沿用',start)
    system=system[:start]+GUIDANCE+'\n\n'+system[end:]
    system=system.replace('\n\n'+handoff.DIRECTION,'')
    system=system.replace('禁止null和Schema说明键；','不得用裸null替代字段或输出Schema说明键；UNKNOWN对象不带事实值，value省略或为null、refs为空；')
    return system

def _reject(i,path,code,allowed=None):
    issue=dict(code=code,path=['queries',i,*path])
    if allowed is not None:issue['allowed_values']=allowed
    raise A0QualityValidationError('Local change request rejected',code='A0_CHANGE_REQUEST_REJECTED',
        diagnostics=dict(stage='local_change_request',issue_count=1,issues=[issue]))

def _ordered(raw):
    out=deepcopy(raw);maps=[]
    if type(out) is not dict or type(out.get('queries')) is not list:return out,maps
    for i,q in enumerate(out['queries']):
        if type(q) is not dict:continue
        if q.get('kind') not in ordered.LOCAL_KINDS:
            if 'comparison_request' in q:_reject(i,['comparison_request'],'CHANGE_SCOPE_CONFLICT')
            continue
        if 'comparison_expression' in q:_reject(i,['comparison_expression'],'CHANGE_LEGACY_FIELD_FORBIDDEN')
        value=q.get('comparison_request')
        if type(value) is not dict:_reject(i,['comparison_request'],'CHANGE_OBJECT_REQUIRED')
        for name in ('reference','evaluated','quantity','refs'):
            if name not in value:_reject(i,['comparison_request',name],'missing')
        if value['quantity'] not in QUANTITIES:_reject(i,['comparison_request','quantity'],'CHANGE_QUANTITY_INVALID',list(QUANTITIES))
        try:r=ChangeRequest.model_validate(value)
        except ValidationError:_reject(i,['comparison_request'],'CHANGE_SHAPE_INVALID')
        first,second=POSITIONS[r.quantity]
        q.pop('comparison_request');q['comparison_expression']=dict(form='UNSPECIFIED' if r.quantity=='UNSPECIFIED' else 'ORDERED_DIFFERENCE',
            first=deepcopy(value[first]),second=deepcopy(value[second]),refs=deepcopy(r.refs))
        maps.append(dict(query_index=i,quantity=r.quantity,first=first,second=second,ordered=r.quantity!='UNSPECIFIED'))
    return out,maps

def project(raw,catalog):
    converted,maps=_ordered(raw)
    try:projected,details=ordered.project(converted,catalog)
    except A0QualityValidationError as exc:
        diagnostics=deepcopy(exc.diagnostics)
        for issue in diagnostics.get('issues',[]):
            p=issue['path']
            if len(p)>2 and p[2]=='comparison_expression':
                p[2]='comparison_request';mapping=next((m for m in maps if m['query_index']==p[1]),None)
                if len(p)>3:p[3]='quantity' if p[3]=='form' else mapping.get(p[3],p[3]) if mapping else p[3]
        raise A0QualityValidationError(str(exc),code=exc.code,diagnostics=diagnostics) from None
    details.pop('ordered_local_projection',None);details['local_change_projection']=maps
    return projected,details

def review_items(raw,query_id):
    q=raw['queries'][int(query_id[1:])-1]
    if q.get('kind') not in ordered.LOCAL_KINDS:yield from ordered.review_items(raw,query_id);return
    request=q['comparison_request']
    for name in RULES:
        value=dict(quantity=request['quantity'],refs=request['refs']) if name=='quantity' else request[name]
        state='PROPOSED_OPERATOR' if name=='quantity' else value.get('state','UNKNOWN') if type(value) is dict else value
        yield RULES[name],f'queries.{query_id}.comparison_request.{name}',value,state

def recheck_field_roles(paths,**kwargs):
    rows=handoff.recheck_field_roles(paths)
    for path in dict.fromkeys(paths):
        if '/comparison_request' in path:
            rows.append(dict(field_path=path,field_role=GUIDANCE))
    # Remove the obsolete local operand names from inherited semantics help.
    for row in rows:row['field_role']=row['field_role'].replace('comparison_expression.first/second','comparison_request的两个角色及quantity')
    return rows

def fact_focus(raw_query,*,query_id,binding):
    converted,maps=_ordered(dict(queries=[raw_query]));focus=handoff.fact_focus(converted['queries'][0],query_id=query_id,binding=binding)
    focus['reviewed_ordered_target']['compilation']=dict(contract=CONTRACT,**dict(maps[0],query_index=int(query_id[1:])-1))
    return focus

BACKGROUND=('普通背景属性及可观测性不是科学限制：门店规模、启动前特征、某份表格可取得等描述，相关内容可保留在study.context并引用，A0的covariates仍保留原文限定。'
    'additional_restrictions只放尚未结构化表达、会限制潜在结果/分配/信息模型或指定额外方法的主张，例如均值相等、单调性、上下界、特定调整要求；包括当前不支持的条件。'
    '同段同时有背景和真限制时分别保留；不能因属于背景材料而丢弃真限制。无法判断主张角色时用unresolved请求复核，不默认为限制或删除。')

def clarify_fact_request(request):
    request=handoff.clarify_fact_request(request);body=json.loads(request['user'])
    body['output_schema']['properties']['additional_restrictions']['description']=BACKGROUND
    body['residual_field_contract']['fields']['additional_restrictions']=BACKGROUND
    request['user']=json.dumps(body,ensure_ascii=False);request['system']+='\n'+BACKGROUND
    return request

def fact_constraints(paths):
    return [dict(field_path='/additional_restrictions',description=BACKGROUND)] if any(
        p=='' or p.startswith('/additional_restrictions') or p.startswith('/study/context') for p in paths) else []
