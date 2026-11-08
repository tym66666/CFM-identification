"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
from pydantic import ValidationError
import cfm_id.workflows.legacy_network.materials_independence as previous
import cfm_id.workflows.legacy_network.materials_base as base
from cfm_id.materials import sources
from cfm_id.serialization import canonical_hash


VERSION = "business-materials-v0.23.4"


SYSTEM = previous.SYSTEM.replace(
    "不知道操作时first和second都填null。",
    "不知道操作时operation=不明确；已读到的部分情形可以保留，缺少的部分填不明确或null，不能因此推定完整比较。"
) + """
target_statement_sources是当前目标说明文件的原句，并不是已经通过语义验证的候选。
population_source和remaining_source只引用这些目标原句；研究协议只描述过去如何抽签，不能替用户决定现在问的目标。
remaining_source必须支持“其他人的安排继续按试验的随机规则，并在所问情形下按条件概率平均”的意思；无需包含固定关键词，意思没说清就null。
例如“别人的安排照试点抽签，只在符合前面情形的抽签结果里，按各结果本来的可能性取平均”表达了这个意思。
不要因需要这个字段而从抽签历史推断它。原句即使存在，也不意味着你对其语义的解释已经被程序证明。
"""


def target_sources(bundle):
    prefix = bundle["active_goal_document"] + ":"
    return {k: v for k, v in sources(bundle).items() if k.startswith(prefix)}


def output_schema(bundle):
    schema = previous.output_schema(bundle)
    ids = list(target_sources(bundle))
    ref_schema = {"anyOf": [{"type": "string", "enum": ids}, {"type": "null"}]} if ids else {"type": "null"}
    schema["$defs"]["Conditional"]["properties"]["remaining_source"] = deepcopy(ref_schema)
    schema["$defs"]["Question"]["properties"]["population_source"] = deepcopy(ref_schema)
    return schema


def normalize(value, raw):
    bundle = base.bundle_value(value)
    allowed = target_sources(bundle)
    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), dict):
        raise ValueError("TOP_LEVEL_INVALID")
    copied, partial = deepcopy(raw), {}
    for sid, obj in raw["questions"].items():
        q = base.Question.model_validate(obj)
        for ref in [q.population_source] + [
            w.remaining_source for w in (q.first, q.second) if isinstance(w, base.Conditional)
        ]:
            if ref is not None and ref not in allowed:
                raise ValueError("TARGET_STATEMENT_SOURCE_REQUIRED")
        # Validate even incomplete scenarios before retaining them outside the
        # compiler. Missing operation is not permission to ignore malformed data.
        for w in (q.first, q.second):
            if isinstance(w, base.Complete):
                base.select(w.treated, bundle["structure"])
            elif isinstance(w, base.Conditional):
                if w.neighbors != "恰好人数" and w.neighbor_count is not None:
                    raise ValueError("INAPPLICABLE_NEIGHBOR_COUNT")
                if w.neighbor_count is not None and w.neighbor_count < 0:
                    raise ValueError("NEGATIVE_NEIGHBOR_COUNT")
        if q.operation == "不明确" and (q.first is not None or q.second is not None):
            partial[sid] = dict(first=deepcopy(obj["first"]), second=deepcopy(obj["second"]))
            copied["questions"][sid]["first"] = None
            copied["questions"][sid]["second"] = None
    return copied, partial


def project(value, raw):
    normalized, _ = normalize(value, raw)
    return previous.project(value, normalized)


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    try:
        normalized, partial = normalize(value, raw)
    except (ValueError, ValidationError) as exc:
        return dict(version=VERSION, status="REJECTED",
            reason_code="READING_SCHEMA_INVALID" if isinstance(exc, ValidationError) else str(exc),
            results=[], production_admission=False, candidate_generator_called=False, estimation_called=False,
            policy_called=False, nonidentification_proven=False, semantic_correctness_verified=False,
            model_draft_sha256=canonical_hash(raw))
    r = previous.evaluate_draft(value, normalized, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    r.update(version=VERSION, model_draft_sha256=canonical_hash(raw),
        partial_scenarios_pending_operation=partial,
        target_source_gate="active_goal_document_membership_not_semantic_proof",
        projection_note="Unknown operation stays unknown; partial scenarios are retained but never compiled.")
    return r
