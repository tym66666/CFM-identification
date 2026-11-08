"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import json
import cfm_id.workflows.legacy_network.materials_plan_references as previous
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.materials import sources
from cfm_id.serialization import canonical_hash


VERSION = "business-materials-v0.24.0"


SYSTEM = previous.SYSTEM + """
目标优先级：只回答active_goal_document当前提出的问题。若它不是business_question.md，后者的问题仅是旧背景，不是还要一起回答的目标。
新目标可以明确改为另一份安排。candidate_policies.csv只是可选方案资料，存在某方案不代表当前问题选了它。
当前问哪些分组全部采用时，按当前目标的分组来表达，不能改回背景中的旧政策名单；研究设计和网络仍从全部材料读取。
exposure非null时，exposure_source必须引用明确给出该分类的研究材料原句；读到分类却不填来源不算完成。来源记录不表示批准A5。
水平问题的second必须null。不要为“会是多少”自造全员采用、不采用或其他基线。比较目标只有在当前问题明确要求两情形之差时才填写。
"""


def output_schema(bundle):
    schema = previous.output_schema(bundle)
    q = schema["$defs"]["Question"]
    q["allOf"] = [{"if": {"properties": {"operation": {"const": "水平"}}, "required": ["operation"]},
                   "then": {"properties": {"second": {"type": "null"}}}}]
    q["properties"]["second"]["description"] = "水平问题必须null；仅明确要求两种情形对比时填写，不能自造对照。"
    study = schema["properties"]["study"]
    study["properties"]["exposure_source"]["description"] = "非空exposure必须引用说明邻居分类的原句；它不是A5科学批准。"
    study["allOf"] = [{"if": {"properties": {"exposure": {"type": "string"}}, "required": ["exposure"]},
                       "then": {"properties": {"exposure_source": {"type": "string", "enum": list(sources(bundle))}}}}]
    return schema


def make_request(value):
    _, user = previous.make_request(value)
    bundle = bundle_value(value)
    m = json.loads(user)
    m["document_roles"] = {
        name: ("CURRENT_TARGET" if name == bundle["active_goal_document"]
               else "ORIGINAL_BUSINESS_BACKGROUND_NOT_CURRENT_TARGET" if name == "business_question.md"
               else "RESEARCH_MATERIAL_OR_OPTIONAL_PLAN") for name in bundle["documents"]}
    m["output_schema"] = output_schema(bundle)
    return SYSTEM, json.dumps(m, ensure_ascii=False)


def check(raw):
    if isinstance(raw, dict) and isinstance(raw.get("questions"), dict):
        for q in raw["questions"].values():
            if isinstance(q, dict) and q.get("operation") == "水平" and q.get("second") is not None:
                raise ValueError("LEVEL_MUST_NOT_HAVE_REFERENCE")


def project(value, raw):
    check(raw)
    return previous.project(value, raw)


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    try:
        check(raw)
    except ValueError as exc:
        return dict(version=VERSION, status="REJECTED", reason_code=str(exc), results=[],
            production_admission=False, candidate_generator_called=False, estimation_called=False,
            policy_called=False, nonidentification_proven=False, semantic_correctness_verified=False,
            model_draft_sha256=canonical_hash(raw))
    r = previous.evaluate_draft(value, raw, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    r["version"] = VERSION
    return r
