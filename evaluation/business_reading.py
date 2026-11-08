"""Coordinate-only reading contract; scientific availability stays independent.

No free-text LLM assessment is converted into scientific admission. Unknown
coordinates remain explicit null/unknown values and are checked by the existing
bridge. No post-hoc removal of concerns from old model responses is permitted.
"""
from copy import deepcopy
import json

from . import business_reading_provenance as previous
from .business_reading_base import question_slots
from .business_core_source_refs import source_catalog
from .business_core_pilot_base import canonical_hash

VERSION = "business-reading-v0.21.2"
SYSTEM = previous.SYSTEM.replace(
    "unresolved只记录缺少的目标坐标；总体信息是否真实、数值如何计算、数据如何交付由独立环节处理。",
    "只填写目标坐标，不输出unresolved或数据审查意见。目标坐标未说清时，使用相应字段中的“不明确”或null。"
) + """
这一步不求任何数值答案。没有具体均值数字，不会让已明确的研究目标变得不明确。
科学假设、总体信息可用性和数学识别由后续独立模块审核，你不批准、不代替其判断。
人口范围、安排、比较和汇总口径已明确时，原样填写这些坐标即可。
"""


def output_schema(question):
    schema = previous.output_schema(question)
    q = schema["$defs"]["Question"]
    q["properties"].pop("unresolved")
    q["required"].remove("unresolved")
    return schema


def make_request(question):
    slots = question_slots(question)
    if not slots:
        raise ValueError("EXPLICIT_QUESTION_SENTENCE_REQUIRED")
    return SYSTEM, json.dumps({
        "business_question": question, "source_catalog": source_catalog(question),
        "question_slots": slots, "output_schema": output_schema(question),
    }, ensure_ascii=False)


def coordinate_form(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), dict):
        raise ValueError("READING_TOP_LEVEL_INVALID")
    out = deepcopy(raw)
    for q in out["questions"].values():
        if not isinstance(q, dict):
            raise ValueError("QUESTION_OBJECT_REQUIRED")
        if "unresolved" in q:
            raise ValueError("OLD_FREE_TEXT_GATE_NOT_ACCEPTED")
        # Target incompleteness is detected from the coordinates by the bridge.
        # This empty adapter field is not a scientific approval or an edit to
        # an LLM's proposed concerns (that field is forbidden in this contract).
        q["unresolved"] = []
    return out


def project(question, raw):
    return previous.project(question, coordinate_form(raw))


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        return previous.evaluate_draft(question, {}, packet, synthetic_protocol_selected=False)
    try:
        expanded = coordinate_form(raw)
    except ValueError as exc:
        baseline = previous.evaluate_draft(question, {}, packet, synthetic_protocol_selected=False)
        return {**baseline, "version": VERSION, "status": "REJECTED", "reason_code": str(exc),
                "model_draft_sha256": canonical_hash(raw)}
    result = previous.evaluate_draft(question, expanded, packet, synthetic_protocol_selected=True)
    result.update(version=VERSION, prompt_version=VERSION, model_draft_sha256=canonical_hash(raw),
                  target_completeness="validated_coordinates_not_free_text_model_data_review")
    return result
