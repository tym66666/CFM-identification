"""One policy owner across stages, with exact-only legacy alias compatibility.

No paraphrase matching, priority rule, citation union or scientific approval.
The saved answer remains untouched; the projection records each redundant alias.
"""
from copy import deepcopy
from . import policy_action_contract as previous
from .quality_formulator import A0QualityValidationError

CONTRACT='single-action-target-2'
KINDS=previous.KINDS
FACT_VERSION=previous.FACT_VERSION
BIND_POPULATION_INFORMATION=previous.BIND_POPULATION_INFORMATION
EXTRA_STATE_RULES=previous.EXTRA_STATE_RULES
review_definition=previous.review_definition
review_items=previous.review_items
omitted_semantics=previous.omitted_semantics
review_semantics=previous.review_semantics
system_prompt=previous.system_prompt
clarify_fact_request=previous.clarify_fact_request
fact_constraints=previous.fact_constraints
fact_focus=previous.fact_focus
target_context=previous.target_context
admission=previous.admission
recheck_field_roles=previous.recheck_field_roles

ALIAS_RULE=('仅兼容旧客户端重复字段，不要求生成。若存在，必须与intervention具有完全相同的状态、'
    '逐字相同的value及相同且无重复的引用集合。程序不判断改写文本等价、不合并引用；不一致则复查。'
    '缺少intervention时不能用本字段补填。')


def describe(schema):
    previous.describe(schema)
    props=schema['$defs']['PolicyActionSemantics']['properties']
    props['policy_assignment']=dict(deepcopy(props['intervention']),description=ALIAS_RULE)
    return ''


def _identity(value):
    if not isinstance(value,dict):return value
    result=deepcopy(value)
    refs=result.get('refs')
    if refs is not None:
        if type(refs) is not list or any(type(x) is not str for x in refs) or len(refs)!=len(set(refs)):
            raise ValueError('INVALID_ALIAS_REFERENCES')
        result['refs']=sorted(refs)
    return result


def project(raw,catalog):
    output=deepcopy(raw);receipts=[]
    for index,query in enumerate(output.get('queries',[]) if type(output) is dict else []):
        if type(query) is not dict or query.get('kind') not in KINDS:continue
        sem=query.get('semantics')
        if type(sem) is not dict or 'policy_assignment' not in sem:continue
        try:equal='intervention' in sem and _identity(sem['intervention'])==_identity(sem['policy_assignment'])
        except ValueError:equal=False
        if not equal:
            raise A0QualityValidationError('Policy alias differs from its owner',code='A0_POLICY_ACTION_REJECTED',
                diagnostics=dict(issues=[dict(code='POLICY_ALIAS_CONFLICT',path=['queries',index,'semantics','policy_assignment'])]))
        del sem['policy_assignment']  # Projection only; original raw is retained.
        receipts.append(dict(query_id=f'q{index+1}',alias='semantics.policy_assignment',owner='semantics.intervention',
            equality='EXACT_STATE_VALUE_AND_REFERENCE_SET',raw_candidate_modified=False,citations_merged=False))
    projected,details=previous.project(output,catalog)
    details['policy_action_projection'].update(contract=CONTRACT,compatible_aliases=receipts)
    return projected,details


apply_gate=previous.apply_gate


def policy_focus(raw_query,*,query_id,binding):
    """Pass reviewed intent once; facts still read coordinates from original text."""
    if raw_query.get('kind') not in KINDS:raise ValueError('FIXED_POLICY_INTENT_REQUIRED')
    def content(value):
        return {k:deepcopy(v) for k,v in value.items() if k!='refs'} if type(value) is dict else deepcopy(value)
    sem=raw_query['semantics'];kind=raw_query['kind']
    target=dict(kind=kind,binding_sha256=binding,coordinate_owner='FACT_READER_FROM_ORIGINAL_SOURCES',
        scientific_approval=False,is_citable_source=False,
        conditions={k:content(v) for k,v in sem.items() if k not in ('intervention','comparator','policy_assignment')})
    if kind=='FIXED_POLICY_VALUE':target['policy']=content(sem['intervention'])
    else:
        operation=raw_query['comparison_order']['operation']
        if operation not in ('INTERVENTION_MINUS_COMPARATOR','COMPARATOR_MINUS_INTERVENTION'):
            raise ValueError('REVIEWED_POLICY_COMPARISON_DIRECTION_REQUIRED')
        a,b=('intervention','comparator') if operation=='INTERVENTION_MINUS_COMPARATOR' else ('comparator','intervention')
        target.update(operation='FIRST_MINUS_SECOND',first=content(sem[a]),second=content(sem[b]),
            original_operation=operation)
    return dict(query_id=query_id,business_goal=content(raw_query['goal']),reviewed_policy_target=target)
