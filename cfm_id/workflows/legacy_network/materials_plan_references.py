"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.materials_selection_canonicalization as previous
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.serialization import canonical_hash


VERSION = "business-materials-v0.23.9"


SYSTEM = previous.SYSTEM + """
完整安排的treated使用专门字段，不使用含义混杂的ids：
引用政策表：selection=政策名单，policy_id填表中的一个政策编号，程序展开全体安排，不能填单位编号。
引用整组：selection=指定分组，group_ids填分组编号列表。
明确列出使用者：selection=指定，node_ids填使用者的单位编号列表。
全体使用或全体不使用：selection=全体或无人，不带任何名单字段。
population的ids仍表示评价对象编号，不能拿来填写政策编号。
"""


def object_schema(properties):
    return dict(type="object", additionalProperties=False, required=list(properties), properties=properties)


def output_schema(bundle):
    schema = previous.output_schema(bundle)
    structure = bundle["structure"]
    def choice(name):
        return {"const": name, "type": "string"}
    def ids(values):
        return dict(type="array", minItems=1, uniqueItems=True, items=dict(type="string", enum=list(values)))
    choices = [
        object_schema(dict(selection=choice("指定分组"), group_ids=ids(structure["groups"]))),
        object_schema(dict(selection=choice("指定"), node_ids=ids(structure["nodes"]))),
        object_schema(dict(selection=dict(type="string", enum=["全体", "无人"]))),
    ]
    if structure["policies"]:
        choices.insert(0, object_schema(dict(selection=choice("政策名单"),
            policy_id=dict(type="string", enum=list(structure["policies"])))))
    schema["$defs"]["Complete"]["properties"]["treated"] = {"oneOf": choices}
    return schema


def make_request(value):
    _, user = previous.make_request(value)
    m = json.loads(user)
    m["output_schema"] = output_schema(bundle_value(value))
    return SYSTEM, json.dumps(m, ensure_ascii=False)


def expand(raw):
    copied = deepcopy(raw)
    if not isinstance(copied, dict) or not isinstance(copied.get("questions"), dict):
        raise ValueError("TOP_LEVEL_INVALID")
    for q in copied["questions"].values():
        if not isinstance(q, dict):
            raise ValueError("QUESTION_OBJECT_INVALID")
        for key in ("first", "second"):
            w = q.get(key)
            if not isinstance(w, dict) or w.get("setting") != "完整安排":
                continue
            s = w.get("treated")
            if not isinstance(s, dict):
                raise ValueError("PLAN_SELECTION_INVALID")
            kind = s.get("selection")
            field = {"政策名单": "policy_id", "指定分组": "group_ids", "指定": "node_ids"}.get(kind)
            if kind in ("全体", "无人"):
                if set(s) != {"selection"}:
                    raise ValueError("PLAN_SELECTION_FIELDS_INVALID")
                values = []
            elif field:
                if set(s) != {"selection", field}:
                    raise ValueError("PLAN_SELECTION_FIELDS_INVALID")
                if field == "policy_id":
                    if not isinstance(s[field], str) or not s[field]:
                        raise ValueError("POLICY_ID_REQUIRED")
                    values = [s[field]]
                else:
                    values = s[field]
                    if not isinstance(values, list) or not values or any(not isinstance(x, str) for x in values):
                        raise ValueError("PLAN_ID_LIST_REQUIRED")
                    if len(values) != len(set(values)):
                        raise ValueError("DUPLICATE_PLAN_ID")
            else:
                raise ValueError("PLAN_SELECTION_KIND_INVALID")
            w["treated"] = dict(selection=kind, ids=values)
    return copied


def project(value, raw):
    return previous.project(value, expand(raw))


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    try:
        expanded = expand(raw)
    except ValueError as exc:
        return dict(version=VERSION, status="REJECTED", reason_code=str(exc), results=[],
            production_admission=False, candidate_generator_called=False, estimation_called=False,
            policy_called=False, nonidentification_proven=False, semantic_correctness_verified=False,
            model_draft_sha256=canonical_hash(raw))
    r = previous.evaluate_draft(value, expanded, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    r.update(version=VERSION, model_draft_sha256=canonical_hash(raw),
             full_plan_reference_contract="policy_id_or_group_ids_or_node_ids")
    return r
