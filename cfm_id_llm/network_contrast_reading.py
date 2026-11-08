"""Ordered two-policy facts on one source/model; no identification decisions.

Reuse each existing network wire and parser for common scientific fields. Only
the target is extended. Endpoint projections are explicit, never model repairs.
"""
from copy import deepcopy
from functools import lru_cache
import json
from typing import Literal
from pydantic import StrictInt, create_model
from .network_policy_reading import Cited, Declaration, reference_catalog
from .network_fact_protocols import network_fact_protocol
from .source_reference_wire import expand

VERSION = 'network-policy-contrast-reading-1'
SIDES = ('first', 'second')


class PolicyEndpoint(Cited):
    assignment: dict[str, StrictInt] | None
    population: list[str] | None
    aggregation: Literal['EQUAL_MEAN', 'OTHER', 'UNKNOWN']


class PolicyContrastTarget(Cited):
    kind: Literal['FIXED_POLICY_MEAN_DIFFERENCE', 'OTHER', 'UNKNOWN']
    operation: Literal['FIRST_MINUS_SECOND', 'OTHER', 'UNKNOWN']
    first: PolicyEndpoint
    second: PolicyEndpoint
    shared_outcome_and_context: Declaration


TARGET_GUIDANCE = '''target记录两个固定完整安排下、同一人群同一结果口径的均值差，用FIXED_POLICY_MEAN_DIFFERENCE。first是所问相对变化的方案，second是基准，operation为FIRST_MINUS_SECOND；“甲比乙多多少”为甲减乙，“从甲改成乙增加多少”为乙减甲，不按出现顺序机械排序。两方案的assignment逐对象写0/1；population分别保留各自评价名单，aggregation分别保留等权平均等口径。未提及对象的安排不默认0，评价名单不默认全体，不能为了同一人群而改写原文。
shared_outcome_and_context仅记录原文是否明确两端使用相同结果定义、单位、期间与研究背景；未说明为null，明确不同为false。它是来源声明，不是独立审核批准。两端比较跨期间或不同结果、随机政策、政策优化、非等权目标、按历史设计对其余安排平均的效应不改写为此固定政策合同，保留原意、用OTHER或未知并说明。方向不明确时operation=UNKNOWN，不挑选一端。
两端各有source_ids，target.source_ids另引用比较方向和共同目标的原文；不能只引用其中一端就声称两端完整。只读取一个政策差值，不把它拆成两个互不关联的均值问题；用户另外确实要两端水平时才保留另问。'''


# The source-owned profile table is finite. Reuse one format class per valid
# profile when the lifecycle registry visits all profiles, rather than evicting
# and recreating classes across source review, parsing and diagnostics.
@lru_cache(maxsize=None)
def _base_reading_model(profile=None):
    protocol = network_fact_protocol(profile)
    from . import policy_evidence_dependencies as explicit, policy_record_definitions as records, policy_scope_reading as scopes
    from . import policy_assumption_dependencies as assumptions
    target = explicit.contrast_target_model() if profile in (explicit.CONTRACT, records.CONTRACT, scopes.CONTRACT, assumptions.CONTRACT) else PolicyContrastTarget
    # Base class is selected only from the closed source-owned protocol table.
    return create_model('NetworkPolicyContrastReading', __base__=protocol.model,
        version=(Literal[VERSION], ...), target=(target, ...))


def _base_make_request(bundle, *, binding, assignment_semantics=None, profile=None):
    from . import policy_assumption_dependencies as assumptions
    if profile == assumptions.CONTRACT:
        return assumptions.make_contrast_request(bundle,binding=binding,assignment_semantics=assignment_semantics)
    from . import policy_record_definitions as records, policy_scope_reading as scopes
    if profile == scopes.CONTRACT:
        return scopes.make_contrast_request(bundle, binding=binding, assignment_semantics=assignment_semantics)
    if profile == records.CONTRACT:
        return records.make_contrast_request(bundle, binding=binding, assignment_semantics=assignment_semantics)
    from . import policy_evidence_dependencies as explicit
    if profile == explicit.CONTRACT:
        return explicit.make_contrast_request(bundle, binding=binding, assignment_semantics=assignment_semantics)
    request = network_fact_protocol(profile).make_request(
        bundle, binding=binding, assignment_semantics=assignment_semantics)
    lines = request['system'].splitlines()
    for prefix, replacement in (
        ('target记录本次选定子问题。', TARGET_GUIDANCE),
        ('固定政策target.assignment本身',
         'target.first.assignment和target.second.assignment分别是两端固定未来安排，不需要未来抽签概率。原分配只记录在assignment。支持与识别留给数学模块，不能补造总体均值或界限。'),
    ):
        positions = [i for i, line in enumerate(lines) if line.startswith(prefix)]
        if len(positions) != 1:
            raise ValueError('CONTRAST_BASE_TARGET_INSTRUCTION_CHANGED')
        lines[positions[0]] = replacement
    body = json.loads(request['user'])
    schema = body['output_schema']
    target = PolicyContrastTarget.model_json_schema()
    for name, value in target.pop('$defs', {}).items():
        schema['$defs'].setdefault(name, value)
    schema['$defs']['PolicyContrastTarget'] = target
    schema['properties']['target'] = {'$ref': '#/$defs/PolicyContrastTarget'}
    schema['properties']['version']['const'] = VERSION
    schema['title'] = 'NetworkPolicyContrastReading'
    for definition in schema['$defs'].values():
        props = definition.get('properties', {})
        if 'source_ids' in props:
            props['source_ids'].update(items={'$ref': '#/$defs/SourceId'}, uniqueItems=True)
    result = dict(system='\n'.join(lines), user=json.dumps(body, ensure_ascii=False))
    from . import network_source_dependencies as dependencies
    from . import reading_alignment_contract as alignment
    if profile == alignment.NETWORK_CONTRACT:return alignment.apply(result)
    return dependencies.apply(result) if profile == dependencies.CONTRACT else result


def _base_parse(bundle, raw, *, binding, profile=None):
    from . import policy_assumption_dependencies as assumptions
    if profile == assumptions.CONTRACT:
        return assumptions.parse_contrast(bundle,raw,binding=binding)
    from . import policy_record_definitions as records, policy_scope_reading as scopes
    if profile == scopes.CONTRACT:
        return scopes.parse_contrast(bundle, raw, binding=binding)
    if profile == records.CONTRACT:
        return records.parse_contrast(bundle, raw, binding=binding)
    from . import policy_evidence_dependencies as explicit
    if profile == explicit.CONTRACT:
        return explicit.parse_contrast(bundle, raw, binding=binding)
    model = reading_model(profile).model_validate(deepcopy(raw))
    protocol = network_fact_protocol(profile)
    refs = reference_catalog(bundle, binding=binding)
    if model.reference_context != refs['context']:
        raise ValueError('STALE_CONTRAST_REFERENCE_CONTEXT')
    target = expand(model.target.model_dump(), refs)
    # Both projections preserve every original common field. The existing
    # parsers check each policy's coordinates, sources and all model fields.
    projections, decoded = {}, {}
    kinds = {'FIXED_POLICY_MEAN_DIFFERENCE': 'FIXED_POLICY_MEAN', 'OTHER': 'OTHER', 'UNKNOWN': 'UNKNOWN'}
    for side in SIDES:
        candidate = model.model_dump()
        candidate['version'] = protocol.wire_version
        candidate['target'] = dict(candidate['target'][side], kind=kinds[model.target.kind])
        projections[side] = candidate
        decoded[side] = protocol.parse(bundle, candidate, binding=binding)
    return dict(target=target, endpoint_candidates=projections, endpoint_readings=decoded,
                projection='Two target projections with identical common source/model declarations; no scientific approval.')


@lru_cache(maxsize=None)
def reading_model(profile=None):
    from .network_mean_order_reading import NetworkMeanOrderModel, field, PROFILES
    from .mean_order_field_contract import check_outcome_binding
    if profile not in PROFILES:
        return _base_reading_model(profile)
    return create_model('NetworkPolicyContrastWithOrders', __base__=_base_reading_model(profile),
                        __validators__={'check_outcome_binding':check_outcome_binding},
                        mean_order_model=(NetworkMeanOrderModel | None, field()))


def make_request(bundle, *, binding, assignment_semantics=None, profile=None):
    from .network_mean_order_reading import extend_request, PROFILES
    request = _base_make_request(bundle, binding=binding,
        assignment_semantics=assignment_semantics, profile=profile)
    if profile not in PROFILES:return request
    request = extend_request(request)
    from . import shared_fact_definitions as shared
    from .mean_order_field_contract import outcome_contract
    if profile == shared.PROFILE:return outcome_contract(shared.apply(request))
    from . import mean_order_ownership as ownership
    return outcome_contract(ownership.apply(request) if profile == ownership.PROFILE else request)


def field_constraints(paths, *, request, profile=None):
    rows = network_fact_protocol(profile).public_constraints(paths, request=request)
    from .network_mean_order_reading import PROFILES
    if profile in PROFILES:
        from .mean_order_field_contract import field_constraints as order_constraints
        rows += order_constraints(paths, request=request)
        from . import mean_order_ownership as ownership
        if profile == ownership.PROFILE:
            rows += ownership.field_constraints(paths, request=request)
    return rows


def parse(bundle, raw, *, binding, profile=None):
    from .network_mean_order_reading import NetworkMeanOrderModel, PROFILES
    candidate = deepcopy(raw)
    orders = candidate.pop('mean_order_model', None) if profile in PROFILES else None
    result = _base_parse(bundle, candidate, binding=binding, profile=profile)
    if orders is not None:
        value = NetworkMeanOrderModel.model_validate(orders)
        refs = reference_catalog(bundle, binding=binding)
        result['mean_order_model'] = expand(value.model_dump(), refs)
    return result
