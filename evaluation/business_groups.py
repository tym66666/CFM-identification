"""Clarify scope provenance; do not infer or replace a missing model citation."""
import json
from . import business_groups_parameters as previous
from .business_reading_base import question_slots
from .business_core_source_refs import source_catalog

VERSION = "business-groups-v0.22.2"
SYSTEM = previous.SYSTEM + """
population只是“评价哪些对象”，不是统计总体信息；population_source只是写明评价谁、怎样汇总的原句编号，不是数据来源或A4证明。
例如问“06的平均结果是多少”，评价范围是指定06，aggregation为单个，population_source就是这个问句的编号。
单个对象也有平均结果；只有明确把多个对象的结果等权取平均时，aggregation才是等权平均。
如果问句明确说了评价谁，不要把population_source写成null；如果评价范围确实没说清，再保留不明确/null，不能默认全体。
"""
project = previous.project
NumericDraft = previous.NumericDraft
study_coordinates = previous.study_coordinates


def output_schema(question):
    schema = previous.output_schema(question)
    props = schema["$defs"]["Question"]["properties"]
    props["population"]["description"] = "要评价的对象范围，不是采用AI的对象、不是总体信息或数据来源。"
    props["aggregation"]["description"] = "评价一个对象为单个；对多个对象等权汇总才为等权平均。单个对象的平均结果仍选单个。"
    props["population_source"] = {
        "anyOf": [{"type": "string", "enum": list(source_catalog(question))}, {"type": "null"}],
        "description": "明确写出评价谁及汇总方式的原句编号，常为当前问句编号；不是总体分布或数据来源。只有没有相应原句才为null。"}
    schema["$defs"]["Conditional"]["properties"]["remaining_source"] = {
        "anyOf": [{"type": "string", "enum": list(source_catalog(question))}, {"type": "null"}],
        "description": "写明其余安排沿用原抽签、在给定条件下平均的原句编号；未说明则null。"}
    return schema


def make_request(question):
    if not question_slots(question):
        raise ValueError("EXPLICIT_QUESTION_SENTENCE_REQUIRED")
    return SYSTEM, json.dumps(dict(business_question=question, source_catalog=source_catalog(question),
        question_slots=question_slots(question), output_schema=output_schema(question)), ensure_ascii=False)


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    result = previous.evaluate_draft(question, raw, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(version=VERSION, prompt_version=VERSION)
    return result
