"""Extend the conservative population/own-state overlap gate to level queries.

Uses the frozen v0.19.1 model prompt. Only local admission changes; no extra
LLM request and no invented replacement population. Known data are preserved.
"""
from copy import deepcopy
from .semantic_roles_clarified import (PROMPT_VERSION,make_role_request,build_role_result as previous_result,
    ClarifiedRoleFormulator,render_role_html)


def build_role_result(case,raw,provider_name):
    initial=previous_result(case,raw,provider_name)
    effective=deepcopy(initial['role_draft']);held=[]
    for i,g in enumerate(effective['goals']):
        if g['form']!='level':continue
        pop=g.get('population');own=(g.get('situation') or {}).get('own_action')
        if not pop or pop['role']!='target_scope' or not own:continue
        p=pop['evidence']
        if own['ref']==p['ref'] and (own['quote'] in p['quote'] or p['quote'] in own['quote']):
            pop['role']='ambiguous'
            held.append({'code':'POPULATION_SCENARIO_OVERLAP','path':f'goals.q{i+1}.population',
                'population_quote':deepcopy(p),'own_quote':deepcopy(own),'decision':'HOLD_SCOPE_FOR_SOURCE_REVIEW_ONLY',
                'explanation':'评价范围与情形中的本人状态来自重叠短语。系统需先核对已给材料，不能将处理情形直接作为人群；不自动认定业务方漏说。'})
    result=previous_result(case,effective,provider_name) if held else initial
    if held:
        result['model_role_draft']=initial['model_role_draft']
        result['role_scope_holds']=initial['role_scope_holds']+held
        result['internal_recheck']+=initial['role_scope_holds']+held
        result['confirmation_card']['internal_recheck']+=initial['role_scope_holds']+held
        result['confirmation_card']['status']='SOURCE_RECHECK_REQUIRED'
    result['local_gate_version']='semantic-roles-level-and-comparison-overlap-v0.19.2'
    return result


class ScopedRoleFormulator(ClarifiedRoleFormulator):
    def formulate(self,case):
        system,user,_=make_role_request(case)
        self.last_wire=self.provider.generate_json(system_prompt=system,user_prompt=user)
        return build_role_result(case,self.last_wire,self.provider.name)
