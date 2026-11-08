"""Optional ordered-mean facts in the existing comparison reading contract.

Reuses the maintained order-claim vocabulary and projection. No new scientific
default, prose classifier, source repair, or mathematical rule lives here.
"""
from copy import deepcopy
from pydantic import Field
from .network_policy_reading import Record, Declaration, documents
from cfm_id.mean_order_reading import project
from .mean_order_field_contract import OrderReading, COMPLETE_MODEL

PROFILE = 'network-source-selections-mean-orders-1'
from .mean_order_ownership import PROFILE as OWNERSHIP_PROFILE
PROFILES = (PROFILE, OWNERSHIP_PROFILE, 'network-shared-definitions-1')


class CompleteOrderModelDeclaration(Declaration):
    value: bool | None = Field(description=COMPLETE_MODEL)


class NetworkMeanOrderModel(Record):
    order_reading: OrderReading
    no_additional_constraints_beyond_declared_orders: CompleteOrderModelDeclaration


DESCRIPTION = (
    '仅在材料明确讨论均值顺序模型时填写，否则为null。复用order_reading：'
    'OWN指其余安排固定时改变本人，PEERS指本人及其余安排固定时增加邻居处理；'
    'NONDECREASING是数值条件均值不降低，NOT_ASSUMED是明确不作该假设，未提及不能补成NOT_ASSUMED。'
    '每个模型对象的两轴分别保留来源、均值/每次结果层级、全部安排/试点范围和假设/观察依据。'
    'no_additional_constraints_beyond_declared_orders单独读取“除所列基础条件、均值充分性、界限和顺序外无其他限制”的声明；'
    '它不同于bounded_model.no_additional_coupling_constraints，后者在存在顺序约束时不能填true。'
    '已在本字段完整保留的顺序不用重复放入additional_restrictions，其他限制仍须保留。'
)


def field():
    # Omitted extension must not change legacy endpoint dictionaries or hashes.
    return Field(default=None, exclude_if=lambda v: v is None, description=DESCRIPTION)


def extend_request(request):
    import json
    result = deepcopy(request)
    body = json.loads(result['user'])
    extension = NetworkMeanOrderModel.model_json_schema()
    schema = body['output_schema']
    for name, value in extension.pop('$defs', {}).items():
        schema['$defs'].setdefault(name, value)
    schema['$defs']['NetworkMeanOrderModel'] = extension
    schema['properties']['mean_order_model'] = dict(
        anyOf=[{'$ref': '#/$defs/NetworkMeanOrderModel'}, {'type': 'null'}],
        default=None, description=DESCRIPTION)
    for definition in schema['$defs'].values():
        properties = definition.get('properties', {})
        for name, prop in properties.items():
            if name.endswith('source_ids'):
                prop.update(items={'$ref': '#/$defs/SourceId'}, uniqueItems=True)
        # These fields also expand roster references. Keep the existing direct
        # citation obligation explicit at each row; never inherit parent refs.
        if ('node' in properties or 'covered_nodes' in properties) and 'source_ids' in properties:
            from .network_source_dependencies import NAMES
            prop = properties['source_ids']
            if NAMES not in prop.get('description', ''):
                prop['description'] = (prop.get('description', '') + ' ' + NAMES).strip()
    result['user'] = json.dumps(body, ensure_ascii=False)
    # Derive the existing public source rules from the extended schema too.
    # apply is idempotent and does not add a new System Prompt instruction.
    from .reading_alignment_contract import apply
    return apply(result)


def project_model(bundle, model, nodes):
    value = NetworkMeanOrderModel.model_validate(deepcopy(model))
    return project(dict(node_order=nodes, documents=documents(bundle)),
                   value.order_reading.model_dump())
