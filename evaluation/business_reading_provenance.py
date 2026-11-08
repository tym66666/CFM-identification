"""Unambiguous JSON schema and question-anchored scenario provenance.

The scenario source is the question slot being interpreted, not a new claim
that the sentence entails the proposed coordinates. No repair of prior drafts.
"""
from copy import deepcopy
import json

from . import business_reading_base as previous
from .business_core_source_refs import reference_schema, source_catalog
from .business_core_pilot_base import canonical_hash

VERSION = "business-reading-v0.21.1"
SYSTEM = previous.SYSTEM.replace(
    "遵循output_contract", "遵循output_schema"
).replace(
    "只填treated和source", "只填treated"
).replace(
    "remaining_source、source", "remaining_source"
).replace(
    "只给03和08开通其余不开通", "只给06和12开通其余不开通"
).replace(
    "03自己开通且恰好一个邻居开通", "06自己开通且恰好一个邻居开通"
) + """
first/second直接是情形对象，例如{"setting":"完整安排","treated":{"selection":"无人","ids":[]}}。
不得加complete_arrangement或local_condition包装键，也不要把schema的$defs名称写进结果。
情形属于正在解释的问句槽，来源由程序直接绑定该问句；不再填写情形source。
只有study的三个来源、population_source、remaining_source需要选择句号编号。
"""


def output_schema(question):
    q = previous.Question.model_json_schema()
    defs = q.pop("$defs")
    defs["Question"] = q
    for name in ("Complete", "Conditional"):
        defs[name]["properties"].pop("source")
        defs[name]["required"].remove("source")
    return {
        "type": "object", "additionalProperties": False,
        "required": ["study", "questions"],
        "properties": {
            "study": reference_schema(question)["$defs"]["Reading"],
            "questions": {
                "type": "object", "additionalProperties": False,
                "required": list(previous.question_slots(question)),
                "properties": {sid: {"$ref": "#/$defs/Question"} for sid in previous.question_slots(question)},
            },
        },
        "$defs": defs,
    }


def make_request(question):
    if not previous.question_slots(question):
        raise ValueError("EXPLICIT_QUESTION_SENTENCE_REQUIRED")
    return SYSTEM, json.dumps({
        "business_question": question, "source_catalog": source_catalog(question),
        "question_slots": previous.question_slots(question), "output_schema": output_schema(question),
    }, ensure_ascii=False)


def anchor_scenarios(question, raw):
    if not isinstance(raw, dict) or set(raw) != {"study", "questions"}:
        raise ValueError("READING_TOP_LEVEL_INVALID")
    if not isinstance(raw["questions"], dict) or set(raw["questions"]) != set(previous.question_slots(question)):
        raise ValueError("QUESTION_COVERAGE_MISMATCH")
    out = deepcopy(raw)
    fields = {
        "完整安排": {"setting", "treated"},
        "局部条件": {"setting", "own", "neighbors", "neighbor_count", "remaining_source"},
    }
    for sid, q in out["questions"].items():
        if not isinstance(q, dict):
            raise ValueError("QUESTION_OBJECT_REQUIRED")
        for key in ("first", "second"):
            s = q.get(key)
            if s is not None:
                if not isinstance(s, dict) or s.get("setting") not in fields or set(s) != fields[s["setting"]]:
                    raise ValueError("SCENARIO_FIELDS_INVALID")
                s["source"] = sid
    return out


def project(question, raw):
    return previous.project(question, anchor_scenarios(question, raw))


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        return previous.evaluate_draft(question, {}, packet, synthetic_protocol_selected=False)
    try:
        expanded = anchor_scenarios(question, raw)
    except ValueError as exc:
        baseline = previous.evaluate_draft(question, {}, packet, synthetic_protocol_selected=False)
        return {**baseline, "version": VERSION, "reason_code": str(exc),
                "status": "REVIEW_REQUIRED" if str(exc) == "QUESTION_COVERAGE_MISMATCH" else "REJECTED",
                "model_draft_sha256": canonical_hash(raw)}
    result = previous.evaluate_draft(question, expanded, packet, synthetic_protocol_selected=True)
    result.update(version=VERSION, prompt_version=VERSION, model_draft_sha256=canonical_hash(raw),
                  scenario_provenance="bound_to_question_slot_not_semantic_entailment")
    return result
