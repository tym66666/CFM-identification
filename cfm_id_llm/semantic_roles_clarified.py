"""Clarified field descriptions plus a conservative literal-overlap review gate.

Overlap is a possible scope conflict, not proof of a wrong population. Preserve
the original role draft and own-state, hold population for source review.
"""
from copy import deepcopy
import json
from .semantic_roles_base import (SYSTEM_PROMPT as BASE_SYSTEM, make_role_request as base_request,
    build_role_result as base_result, SemanticRoleFormulator, RoleDraft, render_role_html)
from .business_formulator import Facts as LegacyFacts

PROMPT_VERSION='cfm-id-business-semantic-roles-v0.19.1'
SYSTEM_PROMPT=BASE_SYSTEM+'''
核对完整性：同伴集合与同伴暴露的计算规则是两个字段，peer_measure应保留人数/比例/阈值，不能只放伙伴名单定义。
全体中统一抽出固定名额是COMPLETE_RANDOMIZATION，只有先分层、再各层固定名额才是STRATIFIED_FIXED_QUOTAS；不要仅见“恰好若干”就认作分层。
“每人/每店算一份”已说明等权；“只有一家”已说明恰好一家；“其他对象照原来抽签方式考虑”已说明目标分配口径。这些普通话无需重复询问。
复制quote时不得把“每家”改成“每店”等近义表述；无法准确截取短语时直接复制该ref整句。''' 


def make_role_request(case):
    _,user,catalog=base_request(case)
    prefix,_,schema_text=user.partition('\n输出Schema：\n');schema=json.loads(schema_text)
    shared=schema['$defs']['SharedFacts']['properties']
    for name in ('units','action','outcome','historical_assignment','connections','peer_measure','connections_timing','covariates'):
        shared[name]['description']=LegacyFacts.model_fields[name].description
    shared['peer_measure']['description']='同伴暴露的计算/分组规则：人数、比例、过半等阈值。不是谁算伙伴；集合另存connections。保留已知完整边界。'
    shared['assignment_family']['description']='仅分类已知历史规则：INDEPENDENT_BERNOULLI=各单位独立抽签；COMPLETE_RANDOMIZATION=全体中统一固定名额；CLUSTER_RANDOMIZATION=按整组分配；STRATIFIED_FIXED_QUOTAS=分层后各层固定名额；OBSERVATIONAL=观察性自主采用；OTHER=当前类别未列出的其他已说明规则（如两阶段设计，保留原句）；证据不清时UNRESOLVED。'
    schema['$defs']['Population']['properties']['role']['description']='target_scope仅当这一问的范围已说清；background仅公司规模；ambiguous用于历史未使用子组与设想本人未使用尚未分清。不能仅因原句提到某人群就认定范围已明确。'
    schema['$defs']['Aggregation']['properties']['weights']['description']='明确的对象权重：“每人/每店算一份”就是等权。未提供则null。'
    for kind in ('Level','Comparison'):
        schema['$defs'][kind]['properties']['remaining_assignments']['description']='目标如何考虑未单独限定的其他单位处理：若明确说按原抽签方式，摘录该句。仅历史抽签本身不能推定目标这样平均。'
    schema['$defs']['Clarification']['properties']['question']['description']='只问资料还没明确的关键意思。资料已给的恰好人数、等权或目标分配规则，不重复问、不改成未知。'
    return SYSTEM_PROMPT,prefix+'\n输出Schema：\n'+json.dumps(schema,ensure_ascii=False,separators=(',',':')),catalog


def build_role_result(case,raw,provider_name):
    initial=base_result(case,raw,provider_name) # Validate every original fragment before any holding.
    effective=deepcopy(initial['role_draft']);held=[]
    for i,g in enumerate(effective['goals']):
        pop=g.get('population')
        if g['form']!='comparison' or not pop or pop['role']!='target_scope':continue
        p=pop['evidence']
        for situation in ('situation_a','situation_b'):
            own=(g.get(situation) or {}).get('own_action')
            if not own or own['ref']!=p['ref']:continue
            if own['quote'] in p['quote'] or p['quote'] in own['quote']:
                pop['role']='ambiguous'
                held.append({'code':'POPULATION_OWN_STATE_OVERLAP','path':f'goals.q{i+1}.population',
                    'population_quote':deepcopy(p),'own_quote':deepcopy(own),'decision':'HOLD_SCOPE_FOR_REVIEW_ONLY',
                    'explanation':'相同原句被同时用作评价范围和本人状态，可能有历史子组/设想状态歧义；保留本人状态，不替业务方决定范围。'})
                if not any(c['about']=='population' for c in g['clarifications']) and len(g['clarifications'])<8:
                    g['clarifications'].append({'about':'population','evidence':deepcopy(p),
                        'question':'这里指实际处于这个状态的那一组对象，还是对要评价的对象设想本人处于这个状态？'})
                break
    result=base_result(case,effective,provider_name) if held else initial
    result['model_role_draft']=initial['role_draft']
    result['role_scope_holds']=held
    result['prompt_version']=PROMPT_VERSION;result['quality']['prompt_version']=PROMPT_VERSION
    result['local_gate_version']='semantic-roles-literal-overlap-v0.19.1'
    result['internal_recheck']+=held;result['confirmation_card']['internal_recheck']+=held
    return result


class ClarifiedRoleFormulator(SemanticRoleFormulator):
    def formulate(self,case):
        system,user,_=make_role_request(case)
        self.last_wire=self.provider.generate_json(system_prompt=system,user_prompt=user)
        return build_role_result(case,self.last_wire,self.provider.name)
