"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
from pydantic import ValidationError
import cfm_id.workflows.legacy_network.materials_file_roles as previous
import cfm_id.workflows.legacy_network.materials_base as base
from cfm_id.materials import sources
from cfm_id.serialization import canonical_hash


VERSION = "business-materials-v0.23.2"


SYSTEM = previous.SYSTEM + """
操作类型：问“如果采用这份确定方案，平均结果会怎样/是多少”是水平，first填该完整安排，second=null；不需要对照也不需要具体数值。
问“甲减乙”才是差值；要求替业务方选名单才是选最优；不知道操作时first和second都填null。
例如“整个仓储网络的平均缺货情况”明确评价全体仓库并求平均，不是未知评价范围。
即使给定方案在原试验中不可能出现，仍属于水平问题，不能因此把operation填不明确。
declared_independent=true必须同时填independence_source，指向明确写出组间抽签独立的原句。
如果材料仅写“每区以1/2概率整组上线”，没有“独立”声明，declared_independent和independence_source都填null。
不能从该设计通常怎样实施推断独立；不是缺省true。independence_source选择来源编号，不输出自己的推断。
"""


def output_schema(bundle):
    schema = previous.output_schema(bundle)
    s = schema["properties"]["study"]
    s["required"].append("independence_source")
    s["properties"]["independence_source"] = {
        "anyOf": [{"type": "string", "enum": list(sources(bundle))}, {"type": "null"}],
        "description": "明确声明各组抽签独立的原句编号；没有明确声明时本字段及declared_independent均null。"}
    schema["$defs"]["Question"]["properties"]["operation"]["description"] = "给定情形或固定方案的平均结果为水平；两情形之差为差值；求最优名单为选最优。支持不足不是操作未知。"
    return schema


def expand(value, raw):
    bundle = base.bundle_value(value)
    if not isinstance(raw, dict) or not isinstance(raw.get("study"), dict) or "independence_source" not in raw["study"]:
        raise ValueError("INDEPENDENCE_SOURCE_FIELD_REQUIRED")
    copied = deepcopy(raw)
    ref = copied["study"].pop("independence_source")
    catalog = sources(bundle)
    if ref is not None and (not isinstance(ref, str) or ref not in catalog):
        raise ValueError("INDEPENDENCE_SOURCE_INVALID")
    if copied["study"].get("declared_independent") is True:
        text = catalog.get(ref, "").lower()
        if not ("独立" in text or "independent" in text) or any(x in text for x in ("不独立", "非独立", "not independent")):
            raise ValueError("EXPLICIT_INDEPENDENCE_DECLARATION_REQUIRED")
    return previous.expand(copied)


def project(value, raw):
    return base.project(value, expand(value, raw))


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    try:
        expanded = expand(value, raw)
    except (ValueError, ValidationError) as exc:
        return dict(version=VERSION, status="REJECTED",
            reason_code="READING_SCHEMA_INVALID" if isinstance(exc, ValidationError) else str(exc),
            results=[], production_admission=False, candidate_generator_called=False,
            estimation_called=False, policy_called=False, nonidentification_proven=False,
            semantic_correctness_verified=False, model_draft_sha256=canonical_hash(raw))
    result = base.evaluate_draft(value, expanded, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(version=VERSION, model_draft_sha256=canonical_hash(raw),
                  independence_source=raw["study"]["independence_source"],
                  independence_source_membership_not_semantic_proof=True,
                  structural_bindings="validated_local_csv_coordinates_not_model_reconstruction")
    return result
