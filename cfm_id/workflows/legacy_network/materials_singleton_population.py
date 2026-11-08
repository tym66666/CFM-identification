"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.materials_source_roles as previous
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.serialization import canonical_hash


VERSION = "business-materials-v0.23.6"


SYSTEM = previous.SYSTEM + """
评价范围只有一个明确编号时，population.selection可以写“指定”或“单个”，ids必须仅包含该编号。
“单个”只适用于population，不适用于完整安排的treated名单；多个编号不能写单个。
"""


def output_schema(bundle):
    schema = previous.output_schema(bundle)
    single = deepcopy(schema["$defs"]["Selection"])
    single["properties"]["selection"]["enum"].append("单个")
    schema["$defs"]["PopulationSelection"] = single
    schema["$defs"]["Question"]["properties"]["population"] = {"$ref": "#/$defs/PopulationSelection"}
    return schema


def make_request(value):
    _, user = previous.make_request(value)
    m = json.loads(user)
    m["output_schema"] = output_schema(bundle_value(value))
    return SYSTEM, json.dumps(m, ensure_ascii=False)


def normalize(value, raw):
    copied, actions = deepcopy(raw), []
    if isinstance(copied, dict) and isinstance(copied.get("questions"), dict):
        for sid, q in copied["questions"].items():
            p = q.get("population") if isinstance(q, dict) else None
            if isinstance(p, dict) and p.get("selection") == "单个":
                ids = p.get("ids")
                if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str):
                    raise ValueError("SINGLETON_SCOPE_REQUIRES_ONE_ID")
                if ids[0] not in bundle_value(value)["structure"]["nodes"]:
                    raise ValueError("UNKNOWN_NODE_ID")
                p["selection"] = "指定"
                actions.append(dict(question_id=sid, field="population.selection",
                                    original="单个", canonical="指定", unchanged_ids=ids))
    return copied, actions


def project(value, raw):
    normalized, _ = normalize(value, raw)
    return previous.project(value, normalized)


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    try:
        normalized, actions = normalize(value, raw)
    except ValueError as exc:
        return dict(version=VERSION, status="REJECTED", reason_code=str(exc), results=[],
            production_admission=False, candidate_generator_called=False, estimation_called=False,
            policy_called=False, nonidentification_proven=False, semantic_correctness_verified=False,
            model_draft_sha256=canonical_hash(raw))
    r = previous.evaluate_draft(value, normalized, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    r.update(version=VERSION, equivalent_format_normalizations=actions, model_draft_sha256=canonical_hash(raw))
    return r
