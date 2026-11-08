"""Goal-specific extraction forms: no irrelevant policy/arm fields to fill."""
from copy import deepcopy
import json
from .business_core_source_refs import (
    SYSTEM as SOURCE_SYSTEM, reference_schema, source_catalog)
from .business_core_local import evaluate_draft as evaluate_local
from .business_core_pilot_base import canonical_hash

VERSION = "business-core-branches-v0.20.5"
COMMON = {"kind", "question_source", "nodes", "population_source", "unresolved"}
FIELDS = {
    "arm": COMMON | {"situation", "remaining", "remaining_source"},
    "comparison": COMMON | {"aggregation", "situation", "reference", "remaining", "remaining_source"},
    "fixed_plan": COMMON | {"aggregation", "treated_nodes", "plan_source"},
    "optimization": {"kind", "question_source", "unresolved"},
    "unclear": {"kind", "question_source", "unresolved"},
}
SYSTEM = SOURCE_SYSTEM + """
每个目标按kind选择且只填写对应分支的字段，不填写其他分支字段。
arm只表示一个明确对象的臂均值，nodes只能有一个编号，无须再选平均方式。
comparison填写两种情形。fixed_plan只填写推广名单及评价范围，绝不填写situation、reference或remaining。
population_source应支持“评价哪些对象”，不能仅引用公司总人数作为目标人群依据；可能与question_source相同。
"""


def branch_schema(question):
    schema = reference_schema(question)
    template = schema["$defs"]["ReadableTarget"]
    branches = []
    for kind, fields in FIELDS.items():
        props = {k: deepcopy(v) for k, v in template["properties"].items() if k in fields}
        props["kind"] = {"type": "string", "const": kind}
        if kind == "arm":
            props["nodes"] = {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 1}
        branches.append({"type": "object", "additionalProperties": False,
                         "properties": props, "required": list(props)})
    schema["$defs"]["ReadableTarget"] = {
        "oneOf": branches, "discriminator": {"propertyName": "kind"}}
    return schema


def make_request(question):
    return SYSTEM, json.dumps({
        "business_question": question, "source_catalog": source_catalog(question),
        "output_schema": branch_schema(question),
    }, ensure_ascii=False)


def expand_branches(raw):
    if not isinstance(raw, dict) or set(raw) != {"study", "targets"}:
        raise ValueError("BRANCH_TOP_LEVEL_FIELDS_INVALID")
    out = deepcopy(raw)
    for t in out["targets"]:
        kind = t.get("kind")
        if kind not in FIELDS or set(t) != FIELDS[kind]:
            raise ValueError("BRANCH_FIELDS_INVALID")
        if kind == "arm" and (not isinstance(t["nodes"], list) or len(t["nodes"]) != 1):
            raise ValueError("ARM_REQUIRES_ONE_EXPLICIT_NODE")
        # These nulls denote fields that do not apply to the chosen target type,
        # not missing causal information being imputed by the application.
        for name in ("nodes", "population_source", "aggregation", "situation", "reference",
                     "remaining", "remaining_source", "treated_nodes", "plan_source"):
            if name not in t:
                t[name] = "single" if kind == "arm" and name == "aggregation" else None
    return out


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        return evaluate_local(question, {}, packet, synthetic_protocol_selected=False)
    expanded = expand_branches(raw)
    result = evaluate_local(question, expanded, packet, synthetic_protocol_selected=True)
    result.update(version=VERSION, prompt_version=VERSION,
                  model_draft_sha256=canonical_hash(raw),
                  expanded_branch_sha256=canonical_hash(expanded))
    return result
