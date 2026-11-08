"""Bound conditional-averaging citations to explicit Chinese source clauses.

This is a conservative lexical provenance gate for this curated input contract,
not semantic entailment or a causal proof. Other wording requires clarification.
"""
import json
from . import business_materials_independence as previous
from . import business_materials_base as base
from .business_materials_intake import sources, prompt_materials
from .business_core_pilot_base import canonical_hash

VERSION = "business-materials-v0.23.3"
SYSTEM = previous.SYSTEM + """
remaining_source引用的是“其余/其他安排仍按原抽签、在满足条件的方案中平均”这条目标声明，不是只说明抽签方式的历史协议。
conditional_averaging_sources列出符合本阶段明确措辞要求的原句。remaining_source只能从中选择；没有相应声明必须null。
这只是出处格式检查，不证明目标语义或科学假设。不要因为历史设计已知就自行补充目标的条件平均含义。
"""


def conditional_sources(bundle):
    return {k: text for k, text in sources(bundle).items()
            if any(w in text for w in ("其余", "其他")) and "原" in text
            and any(w in text for w in ("条件", "满足")) and "平均" in text}


def output_schema(bundle):
    schema = previous.output_schema(bundle)
    ids = list(conditional_sources(bundle))
    schema["$defs"]["Conditional"]["properties"]["remaining_source"] = (
        {"anyOf": [{"type": "string", "enum": ids}, {"type": "null"}]}
        if ids else {"type": "null"})
    schema["$defs"]["Conditional"]["properties"]["remaining_source"]["description"] = (
        "引用明确写出其余安排沿用原抽签并在满足条件的方案中平均的原句；只描述抽签规则的协议不能替代。")
    return schema


def make_request(value):
    bundle = base.bundle_value(value)
    m = prompt_materials(bundle)
    m["validated_file_bindings"] = dict(network_file="network_edges.csv", partition_file="units.csv", group_column="unit_group")
    m["conditional_averaging_sources"] = conditional_sources(bundle)
    return SYSTEM, json.dumps({**m, "output_schema": output_schema(bundle)}, ensure_ascii=False)


def check_sources(value, raw):
    allowed = conditional_sources(base.bundle_value(value))
    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), dict):
        raise ValueError("TOP_LEVEL_INVALID")
    for q in raw["questions"].values():
        if not isinstance(q, dict):
            raise ValueError("QUESTION_OBJECT_INVALID")
        for field in ("first", "second"):
            scenario = q.get(field)
            if isinstance(scenario, dict) and scenario.get("setting") == "局部条件":
                ref = scenario.get("remaining_source")
                if ref is not None and (not isinstance(ref, str) or ref not in allowed):
                    raise ValueError("CONDITIONAL_AVERAGING_SOURCE_REQUIRED")


def project(value, raw):
    check_sources(value, raw)
    return previous.project(value, raw)


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    try:
        check_sources(value, raw)
    except ValueError as exc:
        return dict(version=VERSION, status="REJECTED", reason_code=str(exc), results=[],
            production_admission=False, candidate_generator_called=False, estimation_called=False,
            policy_called=False, nonidentification_proven=False, semantic_correctness_verified=False,
            model_draft_sha256=canonical_hash(raw))
    r = previous.evaluate_draft(value, raw, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    r.update(version=VERSION, conditional_source_gate="explicit_curated_chinese_wording_not_semantic_proof")
    return r
