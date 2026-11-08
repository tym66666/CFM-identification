"""Accept an exact empty representation only for an inapplicable parameter.

No active quota/probability is filled. The v0.22.0 model response and its failure
remain immutable; this version is evaluated separately using new requests.
"""
from copy import deepcopy
import json
from pydantic import ValidationError
from . import business_groups_base as previous
from .business_core_pilot_base import canonical_hash
from .business_reading_base import question_slots
from .business_core_source_refs import source_catalog

VERSION = "business-groups-v0.22.1"
SYSTEM = previous.SYSTEM + """
不适用的设计参数优先填null；也允许与组数一致、每项都为null的占位列表。
这只适用于固定名额设计的probabilities，或整组开关设计的quotas。
实际需要但没提供的名额或概率依然未知，不能补值；不可把边际中奖比例当成独立抽签概率。
"""
output_schema = previous.output_schema
NumericDraft = previous.NumericDraft
study_coordinates = previous.study_coordinates


def make_request(question):
    if not question_slots(question):
        raise ValueError("EXPLICIT_QUESTION_SENTENCE_REQUIRED")
    return SYSTEM, json.dumps(dict(business_question=question, source_catalog=source_catalog(question),
        question_slots=question_slots(question), output_schema=output_schema(question)), ensure_ascii=False)


def project(question, raw):
    adapted = deepcopy(raw)
    if not isinstance(adapted, dict) or "study" not in adapted:
        raise ValueError("READING_TOP_LEVEL_INVALID")
    reading = previous.GroupReading.model_validate(adapted["study"])
    inactive = {"组内固定名额": "probabilities", "整组开关": "quotas"}.get(reading.design)
    changes = []
    if inactive is not None:
        value = getattr(reading, inactive)
        if (value is not None and reading.groups and len(value) == len(reading.groups)
                and all(v is None for v in value)):
            adapted["study"][inactive] = None
            changes.append(dict(field=inactive, equivalence="inapplicable_all_null_group_placeholders",
                                before=value, after=None))
    numeric, other = previous.project(question, adapted)
    return numeric, changes + other


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        result = previous.evaluate_numeric(question, {}, packet, synthetic_protocol_selected=False)
        return {**result, "version": VERSION}
    try:
        numeric, changes = project(question, raw)
        study_coordinates(NumericDraft.model_validate(numeric).study)
    except (ValueError, ValidationError) as exc:
        reason = "GROUP_READING_SCHEMA_INVALID" if isinstance(exc, ValidationError) else str(exc)
        baseline = previous.evaluate_numeric(question, {}, packet, synthetic_protocol_selected=False)
        status = ("REVIEW_REQUIRED" if reason == "QUESTION_COVERAGE_MISMATCH"
                  else "UNSUPPORTED" if reason.endswith("ADAPTER_UNSUPPORTED") else "REJECTED")
        return {**baseline, "version": VERSION, "status": status, "reason_code": reason,
                "model_draft_sha256": canonical_hash(raw)}
    result = previous.evaluate_numeric(question, numeric, packet, synthetic_protocol_selected=True)
    result.update(version=VERSION, prompt_version=VERSION, model_draft_sha256=canonical_hash(raw),
        normalized_draft_sha256=canonical_hash(numeric), exact_equivalences_applied=changes,
        source_reference_precision_verified=False)
    return result
