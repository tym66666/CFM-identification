"""Short source references and explicit query scope over the native DAG reader.

This is a wire adapter, not a new causal model. Full locators stay local and
are rebuilt from the original material. Unknown references are never repaired.
"""
from copy import deepcopy
from hashlib import sha256
import json
from typing import Literal

from pydantic import Field, StrictInt, model_validator
from cfm_id.source_locations import build_catalog, resolve_sources
from . import dag_reading as common
from . import dag_frontdoor_reading as native

VERSION = 'dag-query-reading-1'


def _sha(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()


class QueryScope(common.StrictRecord):
    kind: Literal['ALL_TREATMENT_VALUES', 'TREATMENT_VALUES', 'UNKNOWN', 'OTHER']
    values: list[StrictInt] = Field(max_length=2, description=(
        'TREATMENT_VALUES时逐项保留该子问题明确要求的0/1取值；其他kind为[]。不填结果值、对照差值或调整变量值。'))
    source_ids: list[str]

    @model_validator(mode='after')
    def coherent(self):
        if self.kind == 'TREATMENT_VALUES':
            if not self.values or len(set(self.values)) != len(self.values) or not set(self.values) <= {0, 1}:
                raise ValueError('DISTINCT_BINARY_INTERVENTION_VALUES_REQUIRED')
        elif self.values:
            raise ValueError('NO_VALUES_FOR_UNSPECIFIED_SCOPE')
        if self.kind != 'UNKNOWN' and not self.source_ids:
            raise ValueError('QUERY_SCOPE_SOURCE_REQUIRED')
        return self


class DagQueryReading(native.FrontdoorDagReading):
    version: Literal['dag-query-reading-1']
    reference_context: str = Field(pattern=r'^c[0-9a-f]{12}$')
    query_scope: QueryScope


def reference_catalog(bundle, *, binding):
    from .source_reference_wire import catalog
    try:
        return catalog(bundle, common.documents(bundle), binding=binding, version=VERSION)
    except ValueError as exc:
        raise common.ReadingError(str(exc)) from None


def make_request(bundle, *, binding):
    b = common.public_bundle(bundle)
    refs = reference_catalog(b, binding=binding)
    schema = DagQueryReading.model_json_schema()
    schema['properties']['reference_context']['const'] = refs['context']
    schema['$defs']['QueryScope']['properties']['values'].update(
        items=dict(type='integer', enum=[0, 1]), uniqueItems=True)
    schema['$defs']['SourceId'] = dict(type='string', enum=list(refs['aliases']))
    for definition in schema['$defs'].values():
        properties = definition.get('properties', {})
        if 'source_ids' in properties:
            properties['source_ids']['items'] = {'$ref': '#/$defs/SourceId'}
            properties['source_ids']['uniqueItems'] = True
    schema['properties']['adjustment_source_ids']['items'] = {'$ref': '#/$defs/SourceId'}
    schema['properties']['adjustment_source_ids']['uniqueItems'] = True
    catalog = {alias: dict(doc_id=r['doc_id'], text=r['text']) for alias,r in refs['aliases'].items()}
    system = native.SYSTEM.replace('dag-frontdoor-reading-2', VERSION) + '''
本轮使用短原文编号。source_ids只能填写source_catalog中的s编号，不计算、不复制长哈希。
reference_context原样填写本次给定的短上下文标识；它不是业务事实或审核许可。
query_scope记录本次选定子问题请求的干预取值：明确设为0填TREATMENT_VALUES/[0]；明确设为1填[1]；明确分别设为0和1填[0,1]。不要因完整材料还含其他子问题而扩展本次目标。
请求完整干预分布函数、未限制其处理取值时用ALL_TREATMENT_VALUES/[]。取值范围确实含混或尚未决定时用UNKNOWN/[]，不能自行默认全体。额外条件分布、结果事件限制或差值等不能由当前分布目标表达时用OTHER，并保留unresolved说明。
目标取值只是业务请求，不证明这些取值可识别。不得输出公式或批准；数学后端验证完整分布后，程序再标注该子问题对应的自由干预参数取值。'''
    return dict(system=system, user=json.dumps(dict(case_id=b['case_id'], question=b['question'],
        reference_context=refs['context'], source_catalog=catalog, output_schema=schema), ensure_ascii=False))


def parse(bundle, wire, *, binding):
    """Return native projection, source-bound scope and an auditable alias map."""
    if type(wire) is not dict:
        raise common.ReadingError('QUERY_READING_OBJECT_REQUIRED')
    try:
        candidate = DagQueryReading.model_validate(deepcopy(wire))
    except ValueError:
        raise common.ReadingError('INVALID_QUERY_READING_SCHEMA') from None
    refs = reference_catalog(bundle, binding=binding)
    if candidate.reference_context != refs['context']:
        raise common.ReadingError('STALE_QUERY_REFERENCE_CONTEXT')

    def expand(value):
        if isinstance(value, dict):
            out = {}
            for key, child in value.items():
                if key.endswith('source_ids'):
                    if len(set(child)) != len(child) or any(r not in refs['aliases'] for r in child):
                        raise common.ReadingError('UNKNOWN_OR_DUPLICATE_SHORT_SOURCE')
                    out[key] = [refs['aliases'][r]['source_id'] for r in child]
                else:
                    out[key] = expand(child)
            return out
        if isinstance(value, list):
            return [expand(v) for v in value]
        return deepcopy(value)

    projected = expand(candidate.model_dump())
    scope = projected.pop('query_scope')
    projected.pop('reference_context')
    projected['version'] = 'dag-frontdoor-reading-2'
    native.parse(bundle, projected)
    if scope['source_ids']:
        resolve_sources(common.documents(bundle), scope['source_ids'])
    return dict(native_candidate=projected, query_scope=scope,
                reference_binding=dict(context=refs['context'], context_sha256=refs['context_sha256'],
                    aliases={k:v['source_id'] for k,v in refs['aliases'].items()}))
