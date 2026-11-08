"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictBool, ValidationError
import cfm_id.workflows.legacy_network.materials_base as previous
from cfm_id.workflows.legacy_network.target_model import Closed


SYSTEM = previous.SYSTEM.replace(
    "network_file与partition_file选择实际网络/名册文件；不要把任意网络简化成环、星形或无跨组联系。",
    "程序已绑定network_edges.csv为真实边表、units.csv的unit_group为成员分组；不要输出network_file、partition_file、group_column，不要重新选择概率表作为名册。"
).replace("draws_independent仅表示各组抽签独立；必须有明确文字，不能从每组都是1/2推断，也不表示组间无干扰。",
    "declared_independent只记录材料是否明确声称各组抽签独立；明确声称则true，明确相关则false，没有说明则null。不能从每组都是1/2推断独立。") + """
研究设计字段记录的是材料中的声明，不是你对假设真实性的批准。
例如“每个商圈以独立50%概率整体入选”明确声称组间独立，因此declared_independent=true。
“这些材料不构成科学假设的证明”是准入提醒，不会取消刚才的独立抽签声明；真正科学准入由另一模块处理。
population.selection必须逐字使用枚举，不得填“没有发券的门店”或其他自造文字。
“没有发券/没有使用”先放入情形own=不开通；它本身不定义事先评价哪些单位。未说明评价范围就填population.selection=不明确，ids=[]。
文件或问题中的“是否减少/是否影响”不提供完整比较坐标时，保留未知，不能根据希望识别的结论补全。
"""


class MaterialStudy(Closed):
    design: Literal["组内固定名额", "整组开关", "不明确"]
    group_parameters: list[previous.GroupParameter]
    declared_independent: StrictBool | None = Field(description="原文是否明确声明各组抽签独立；是则true，明确相关false，未说明null。不是科学批准。")
    design_sources: list[str]
    exposure: Literal["strict_majority", "exact_treated_neighbor_count", "any_treated_neighbor"] | None
    exposure_source: str | None
    outcome: str


def output_schema(bundle):
    schema = previous.output_schema(bundle)
    study = MaterialStudy.model_json_schema()
    schema["$defs"].update(study.pop("$defs", {}))
    schema["properties"]["study"] = study
    schema["$defs"]["Selection"]["properties"]["selection"]["description"] = "只允许列出的固定文字选项；不能写“没有发券的门店”等条件人群。"
    schema["$defs"]["Question"]["properties"]["population"]["description"] = "事先评价的单位集合；本人有没有处理放在own，不作为对象名单。范围未明则selection=不明确。"
    return schema


def expand(raw):
    if not isinstance(raw, dict) or set(raw) != {"study", "questions"}:
        raise ValueError("TOP_LEVEL_INVALID")
    study = MaterialStudy.model_validate(raw["study"]).model_dump()
    study["draws_independent"] = study.pop("declared_independent")
    study.update(network_file="network_edges.csv", partition_file="units.csv", group_column="unit_group")
    return dict(study=study, questions=deepcopy(raw["questions"]))
