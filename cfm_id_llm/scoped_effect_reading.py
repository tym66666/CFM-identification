"""Reviewed target kind and separately cited information coverage.

Projection uses explicit values and dependencies only. It does not infer scope,
find citations, approve source entailment, or grant scientific permission.
"""
from copy import deepcopy
from typing import Literal
import json
from pydantic import Field, create_model, model_validator
from . import owned_effect_reading as previous
from .network_policy_reading import Record

VERSION = 'network-scoped-effect-reading-1'
KIND_RULE = ('目标类别已经在A0逐字段及来源审核中确定，当前target不再输出kind，也不重新分类。'
    '程序从当前已审目标绑定该类别；它不是科学许可。目标两端仍按原文读取并独立审核，'
    '若定位与原文冲突，保留冲突，不改写业务或擅自换类别。')
SCOPE_RULE = ('study名册说明有哪些研究对象，不证明一份记录实际覆盖哪些对象。'
    '每条information先判断该份信息是否明确给出覆盖范围：未说明时scope_status=UNSPECIFIED，'
    'outcome_nodes、arm_cells和scope_source_ids均为空；明确给出时用DECLARED，保留实际名单或原文明确全体的展开名单，'
    'scope_source_ids引用声明该份信息覆盖范围的原句，definition_refs只提供对象身份定义。'
    '记录条数、样本量、研究名册和本次评价名单都不能单独证明样本对象覆盖。'
    '同一规则也适用于总体信息：已明确的总体格子和样本子集必须完整保留，不能为了安全一律留空。')
INFO_RULE = ('source_ids负责本条信息的类型与可用性；scope_source_ids负责本条实际覆盖的对象及格子。'
    '两组引用可以引用同一原段，但各自必须明确列出；定义来源不能代替覆盖声明。')

# Derive the unchanged public target fields from their single existing owner.
# Only the already-reviewed kind leaves the model's output contract.
Target = create_model('Target', __base__=Record, **{
    name: (field.annotation, deepcopy(field))
    for name, field in previous.Target.model_fields.items() if name != 'kind'})


class Information(previous.Information):
    scope_status: Literal['UNSPECIFIED', 'DECLARED'] = Field(description=SCOPE_RULE)
    scope_source_ids: list[str] = Field(description=INFO_RULE)

    @model_validator(mode='after')
    def scope_combination(self):
        if (self.operator != 'UNKNOWN' or self.availability != 'UNKNOWN') and not self.source_ids:
            raise ValueError('INFORMATION_TYPE_REQUIRES_DIRECT_EVIDENCE')
        if self.scope_status == 'UNSPECIFIED':
            if self.outcome_nodes or self.arm_cells or self.scope_source_ids:
                raise ValueError('UNSPECIFIED_INFORMATION_SCOPE_MUST_STAY_EMPTY')
        elif not self.outcome_nodes or not self.scope_source_ids:
            raise ValueError('DECLARED_INFORMATION_SCOPE_REQUIRES_NODES_AND_DIRECT_EVIDENCE')
        if len(set(self.scope_source_ids)) != len(self.scope_source_ids):
            raise ValueError('UNIQUE_SCOPE_SOURCES_REQUIRED')
        return self


class Reading(previous.Reading):
    version: Literal['network-scoped-effect-reading-1']
    target: Target
    information: list[Information]


def transform_request(request):
    request = previous.transform_request(request)
    body = json.loads(request['user']); old = body['output_schema']
    schema = Reading.model_json_schema()
    for name, node in schema['$defs'].items():
        prior = old['$defs'].get(name, {})
        for key, prop in node.get('properties', {}).items():
            if key in prior.get('properties', {}) and 'description' in prior['properties'][key]:
                prop['description'] = prior['properties'][key]['description']
    for node in [schema, *schema['$defs'].values()]:
        for key, prop in node.get('properties', {}).items():
            if key.endswith('source_ids'):
                prop.update(items={'$ref': '#/$defs/SourceId'}, uniqueItems=True)
    schema['$defs']['SourceId'] = deepcopy(old['$defs']['SourceId'])
    schema['properties']['reference_context']['const'] = old['properties']['reference_context']['const']
    info = schema['$defs']['Information']['properties']
    info['source_ids']['description'] = INFO_RULE
    info['scope_source_ids']['description'] = INFO_RULE
    info['scope_status']['description'] = SCOPE_RULE
    info['outcome_nodes']['description'] = SCOPE_RULE
    body['output_schema'] = schema; body['fact_contract'] = VERSION
    body['target_kind_contract'] = dict(origin='INDEPENDENTLY_REVIEWED_A0', model_outputs_kind=False,
        fact_coordinates_still_require_review=True, scientific_approval=False)
    groups = body['source_coverage_contract']['groups']
    groups['Target']['source_ids'] = ['population scope', 'aggregation']
    groups['Information'] = dict(source_ids=['operator', 'availability'],
        scope_source_ids=['outcome_nodes', 'arm_cells'], definition_refs=['object identity'])
    body['information_scope_contract'] = dict(version=VERSION, instruction=SCOPE_RULE,
        source_ownership=INFO_RULE, automatic_scope_inference=False)
    system = request['system'].replace(
        'target.source_ids支持kind、population、aggregation，包括评价谁和如何汇总；子记录引用不替代它。',
        'target.source_ids支持population、aggregation，包括评价谁和如何汇总；子记录引用不替代它。')
    return dict(system=system+'\n'+KIND_RULE+'\n'+SCOPE_RULE+'\n'+INFO_RULE,
                user=json.dumps(body, ensure_ascii=False))


def parse(bundle, raw, *, binding, reviewed_query):
    wire = Reading.model_validate(deepcopy(raw)); projected = wire.model_dump(mode='json')
    kind = reviewed_query['kind']
    if kind not in ('DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT'):
        raise ValueError('REVIEWED_LOCAL_KIND_REQUIRED')
    refs = previous.legacy.reference_catalog(bundle, binding=binding)
    previous.expand(deepcopy(projected), refs)
    scopes = []
    for index, info in enumerate(projected['information']):
        status = info.pop('scope_status'); scope_sources = info.pop('scope_source_ids')
        direct = list(info['source_ids'])
        info['source_ids'] = list(dict.fromkeys([*direct, *scope_sources]))
        scopes.append(dict(field_path=f'/information/{index}', status=status,
            information_source_ids=direct, scope_source_ids=scope_sources,
            outcome_nodes=deepcopy(info['outcome_nodes']), entailment_verified=False))
    projected['target']['kind'] = kind
    projected['version'] = previous.VERSION
    decoded = previous.parse(bundle, projected, binding=binding, reviewed_query=reviewed_query)
    decoded['information_scope_evidence'] = dict(version=VERSION, records=scopes,
        automatic_scope_inference=False, raw_candidate_modified=False)
    decoded['target_kind_origin'] = dict(kind=kind, origin='INDEPENDENTLY_REVIEWED_A0',
        model_outputs_kind=False, raw_goal_source_refs=deepcopy(reviewed_query['goal'].get('refs', [])),
        scientific_approval=False)
    return decoded


def field_constraints(paths):
    return previous.field_constraints(paths) + [dict(field_path=p,
        description=KIND_RULE+' '+SCOPE_RULE+' '+INFO_RULE) for p in paths]
