"""Versioned DAG reading extension for explicit single-front-door roles.

The v1 reader is preserved. Shared fact/source validation is reused without
discarding the new role from any business proposal or review.
"""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, model_validator
from . import dag_reading as common
from cfm_id.source_locations import build_catalog, resolve_sources


class FrontdoorChoice(common.StrictRecord):
    status: Literal['UNSPECIFIED', 'SPECIFIED', 'UNDECIDED', 'FORBIDDEN'] = Field(
        description='仅记录用户对前门变量的选择：未指定单个变量为UNSPECIFIED；明确要求检验或采用某变量为SPECIFIED；选择尚未决定或含混为UNDECIDED；明确禁止相应用途为FORBIDDEN。不是识别判据的判断。')
    variable: str | None = Field(
        description='使用材料中的同一变量名。SPECIFIED必须有一个变量；UNSPECIFIED必须null；尚未决定或禁止时保留已提到的变量，否则null。')
    source_ids: list[str]

    @model_validator(mode='after')
    def consistent(self):
        if self.status == 'SPECIFIED' and self.variable is None:
            raise ValueError('SPECIFIED_FRONTDOOR_VARIABLE_REQUIRED')
        if self.status == 'UNSPECIFIED' and self.variable is not None:
            raise ValueError('UNSPECIFIED_FRONTDOOR_CANNOT_CHOOSE_VARIABLE')
        return self


class FrontdoorDagReading(common.DagReading):
    version: Literal['dag-frontdoor-reading-2']
    frontdoor_choice: FrontdoorChoice
    adjustment: list[str] | None = Field(description=(
        '仅记录用户明确要求的普通协变量调整/控制集合；不能把前门变量填进这里。'
        '明确指定空调整集才[]；仅解释某变量不是控制变量不等于要求空调整集，未指定普通调整集合为null。'))
    additional_restrictions: list[common.Note] = Field(description=(
        '只列其他字段尚未表达的额外科学约束。前门变量选择由frontdoor_choice表示，不是额外科学限制。'
        '真正的单调性、额外排除限制等仍须保留。'))


SYSTEM = common.SYSTEM.replace('当前后门路线', '当前识别路线').replace('后门是否成立', '图形识别条件是否成立') + """
本请求使用前门角色扩展格式dag-frontdoor-reading-2。共同的变量、图、目标、信息和声明语义保持不变。
frontdoor_choice与adjustment是两种不同的用户要求，分别忠实提取，不能互换。
明确指定用某变量作前门变量，或要求检验该变量能否用于前门识别，均为SPECIFIED；定理是否成立交给后端，不能因此改成UNDECIDED。
只说想用前门方法但未指定哪个变量，以及根本未指定前门变量，均为UNSPECIFIED、variable=null；不根据图上的中介位置替用户选择。
明确说还在考虑、尚未决定采用哪个或是否采用某变量时为UNDECIDED；明确禁止某变量/前门用途时为FORBIDDEN。有明确提到的变量保留其名称。
单纯说变量是中介、传导环节或画在处理与结果之间，不等于用户指定它作为前门变量。若只是讨论中介效应，按真实target分类，不改成一般干预分布。
“控制/调整某变量”的要求只进入adjustment，不能为了前门可运行删掉；同时提出两类要求时都保留。
“用M作前门变量，不是要求把它当控制变量”属于角色澄清，不表示指定空调整集合；adjustment保持null。
前门变量的选择与其source_ids不是科学审批，也不是证明。不要输出公式或判断三项图形条件成立；额外科学约束仍保留。
"""


def make_request(bundle):
    b = common.public_bundle(bundle)
    catalog = build_catalog(common.documents(b))
    schema = FrontdoorDagReading.model_json_schema()
    schema['$defs']['SourceId'] = dict(type='string', enum=list(catalog),
        description='必须原样使用本次材料目录中的source_id。')
    for definition in schema['$defs'].values():
        properties = definition.get('properties', {})
        if 'source_ids' in properties:
            properties['source_ids']['items'] = {'$ref': '#/$defs/SourceId'}
    schema['properties']['adjustment_source_ids']['items'] = {'$ref': '#/$defs/SourceId'}
    return dict(system=SYSTEM, user=json.dumps(dict(case_id=b['case_id'], question=b['question'],
                    source_catalog=catalog, output_schema=schema), ensure_ascii=False))


def parse(bundle, wire):
    common.public_bundle(bundle)
    if type(wire) is not dict:
        raise common.ReadingError('DAG_READING_OBJECT_REQUIRED')
    try:
        c = FrontdoorDagReading.model_validate(deepcopy(wire))
    except ValueError:
        raise common.ReadingError('INVALID_FRONTDOOR_READING_SCHEMA') from None
    # Validate the common facts/provenance with the unchanged v1 reader.
    base = c.model_dump()
    base.pop('frontdoor_choice')
    base['version'] = 'dag-reading-1'
    common.parse(bundle, base)
    choice = c.frontdoor_choice
    if choice.variable is not None and choice.variable not in {v.name for v in c.variables}:
        raise common.ReadingError('UNKNOWN_FRONTDOOR_ROLE_VARIABLE')
    if choice.status != 'UNSPECIFIED' and not choice.source_ids:
        raise common.ReadingError('SOURCE_REQUIRED_FOR_FRONTDOOR_ROLE')
    if choice.source_ids:
        try:
            resolve_sources(common.documents(bundle), choice.source_ids)
        except ValueError:
            raise common.ReadingError('UNKNOWN_DUPLICATE_OR_STALE_FRONTDOOR_SOURCE') from None
    return c

