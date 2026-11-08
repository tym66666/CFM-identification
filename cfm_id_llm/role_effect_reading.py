"""Read business-role coordinates; compile reviewed quantity without text inference.

The raw candidate remains auditable. This projection grants no source/science
approval and does not establish that coordinates match the business roles.
"""
from copy import deepcopy
import json
from typing import Literal
from . import network_effect_reading as legacy
from . import requested_change_contract as quantity
from . import network_source_dependencies as dependencies
from . import reading_alignment_contract as alignment

VERSION = 'network-role-coordinates-1'
ROLE_RULE = ('target.reference记录已审参照状态的own和exposure；target.evaluated记录已审被评价状态的own和exposure。'
    '它们是业务角色，不是减法位置。将原文中的状态与编码定义逐项对应；缺失坐标保留null。'
    '不再输出operation、first、second或quantity，不交换角色。所问量由前一阶段独立审核，程序单独编译。'
    '若已审角色与原文矛盾，在unresolved记录冲突，不为符合定位而编造坐标。')


class RoleTarget(legacy.Cited):
    kind: Literal['DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT', 'OTHER', 'UNKNOWN']
    reference: legacy.LocalArm
    evaluated: legacy.LocalArm
    population: list[str] | None
    aggregation: Literal['SINGLE', 'EQUAL_MEAN', 'OTHER', 'UNKNOWN']
    population_fixed_before_assignment: legacy.Declaration = legacy.Field(description=legacy.population_contract.RULE)
    remaining_assignment: Literal['ORIGINAL_DESIGN_CONDITIONAL', 'OTHER', 'UNKNOWN']
    remaining_source_ids: list[str]
    shared_outcome_and_context: legacy.Declaration


class RoleReading(legacy.NetworkEffectReading):
    version: Literal['network-role-coordinates-1']
    target: RoleTarget


def transform_request(request):
    """Transform the public wire and guidance before any focus/recheck is appended."""
    request=deepcopy(request);body=json.loads(request['user']);schema=body['output_schema']
    target=schema['$defs']['EffectTarget'];props=target['properties']
    for old,new in (('first','reference'),('second','evaluated')):
        props[new]=props.pop(old)
        props[new]['description']=ROLE_RULE
    props.pop('operation')
    target['required']=[{'first':'reference','second':'evaluated'}.get(k,k)
        for k in target['required'] if k!='operation']
    # Shared coverage ownership changes with the actual wire, not with a test case.
    props['source_ids']['description']='本字段引用支持效应类别、评价名单及汇总方式。'+dependencies.NAMES
    body['source_coverage_contract']['groups']['EffectTarget']['source_ids']=['kind','population','aggregation']
    schema['properties']['version']['const']=VERSION
    body['fact_contract']=VERSION
    system=request['system']
    old=next(p for p in legacy.SYSTEM.splitlines() if p.startswith('target.first、second'))
    system=system.replace(old,ROLE_RULE)
    old=next(p for p in legacy.SYSTEM.splitlines() if p.startswith('target.source_ids'))
    system=system.replace(old, 'target.source_ids支持kind、population、aggregation，包括评价谁和如何汇总；子记录引用不替代它。'
        'reference和evaluated各自引用选择该角色状态的业务原文及own/exposure编码定义。'
        'shared_outcome_and_context独立记录两端是否明确使用同一结果定义、期间及研究背景；未说明为null，明确不同为false。')
    system=system.replace(alignment.FACT_GUIDANCE,alignment.SCIENCE)
    # Regenerate public dependency locations from the transformed schema.
    if 'source_dependency_contract' in body:
        body['source_dependency_contract']['field_constraints']=dependencies._schema_rules(schema)
    body['role_coordinate_contract']=dict(version=VERSION,field_constraints=[
        dict(field_path='/target/reference',description=ROLE_RULE),
        dict(field_path='/target/evaluated',description=ROLE_RULE)],automatic_repair=False)
    body['residual_field_contract']['fields']['additional_restrictions']=quantity.BACKGROUND
    schema['properties']['additional_restrictions']['description']=quantity.BACKGROUND
    return dict(system=system+'\n'+quantity.BACKGROUND,user=json.dumps(body,ensure_ascii=False))


def parse(bundle,raw,*,binding,reviewed_query):
    wire=RoleReading.model_validate(deepcopy(raw))
    amount=reviewed_query['comparison_request']['quantity']
    if amount not in quantity.QUANTITIES[:-1]:
        raise ValueError('REVIEWED_DIRECTED_QUANTITY_REQUIRED')
    first,second=quantity.POSITIONS[amount]
    canonical=wire.model_dump(mode='json');target=canonical['target']
    reference=target.pop('reference');evaluated=target.pop('evaluated')
    roles=dict(reference=reference,evaluated=evaluated)
    target.update(first=roles[first],second=roles[second],operation='FIRST_MINUS_SECOND')
    canonical['version']=legacy.VERSION
    decoded=legacy.parse(bundle,canonical,binding=binding)
    decoded['role_compilation']=dict(version=VERSION,quantity=amount,first_role=first,second_role=second,
        raw_candidate_modified=False,source_entailment_verified=False,scientific_approval=False)
    return decoded


def field_constraints(paths):
    return [dict(field_path=p,description=ROLE_RULE) for p in ('/target/reference','/target/evaluated')
        if any(q=='' or p.startswith(q+'/') or q==p or q.startswith(p+'/') for q in paths)]
