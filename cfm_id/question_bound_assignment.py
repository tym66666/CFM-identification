"""Explicit ID-bound reading: source rendering is program-owned, not LLM text.

No candidate text is repaired. This new contract never accepts a model quote;
it resolves a current, bundle-bound question ID and retains all model fields.
The resolved view is for compatibility with established downstream contracts.
"""
from copy import deepcopy
import json
from typing import Literal
from pydantic import ConfigDict, Field
from cfm_id_llm.schemas import StrictModel
from cfm_id_bridge.scientific_binding import sha
from cfm_id_llm.readers.fixed_policy_base import Conditions
from . import fixed_assignment

CONTRACT = 'fixed-assignment-id'


class BoundIntent(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    kind: Literal['比较', '水平', '选最优', '不明确']
    question_id: str = Field(pattern=r'^question_[0-9a-f]{64}$')


class BoundReading(StrictModel):
    intents: dict[str, BoundIntent]
    questions: dict[str, Conditions]


class BoundAssignmentReading(StrictModel):
    reading: BoundReading
    reported_assignment: fixed_assignment.ReportedAssignment


def question_catalog(bundle):
    slots = bundle['question_slots']
    if (type(slots) is not dict or not slots or any(
            type(qid) is not str or not qid.strip() or type(text) is not str or not text.strip()
            for qid, text in slots.items())):
        raise ValueError('EXPLICIT_QUESTION_SLOTS_REQUIRED')
    # Full bundle includes roster, material versions and the complete query set.
    # Even if text repeats, qid distinguishes its exact slot. No normalization.
    bundle_hash = sha(bundle)
    documents = bundle['documents']
    if type(documents) is not dict or any(type(d) is not str or type(t) is not str for d,t in documents.items()):
        raise ValueError('EXPLICIT_DOCUMENTS_REQUIRED')
    catalog = {}
    for qid, text in slots.items():
        locations = []
        for doc_id, source in documents.items():
            start = source.find(text)
            while start >= 0:
                locations.append(dict(doc_id=doc_id, start=start, end=start+len(text)))
                start = source.find(text, start+1)
        if not locations:
            raise ValueError('QUESTION_SLOT_NOT_IN_CURRENT_MATERIALS')
        catalog[qid] = dict(question_id='question_' + sha(dict(contract=CONTRACT,
            bundle_sha256=bundle_hash, query_id=qid, text=text)), text=text, locations=locations)
    return catalog


def resolve_reading(bundle, raw):
    """Return (legacy-shaped view, program-owned source receipt), without mutation."""
    BoundAssignmentReading.model_validate(raw)
    catalog = question_catalog(bundle)
    reading = raw['reading']
    if set(reading['intents']) != set(catalog) or set(reading['questions']) != set(catalog):
        raise ValueError('EXACT_QUESTION_COVERAGE_REQUIRED')
    resolved = deepcopy(raw)
    for qid, record in catalog.items():
        original = reading['intents'][qid]
        if original['question_id'] != record['question_id']:
            raise ValueError('QUESTION_ID_UNKNOWN_STALE_OR_WRONG_SLOT')
        resolved['reading']['intents'][qid] = dict(kind=original['kind'], quote=record['text'])
    # Existing coordinate validation is still applied; it may preserve genuine
    # nulls as missing, but never fills population, arrangements or assumptions.
    fixed_assignment.target_reading.project(bundle, resolved['reading'])
    receipt = dict(contract=CONTRACT, bundle_sha256=sha(bundle), candidate_sha256=sha(raw),
        catalog_sha256=sha(catalog), resolved_wrapper_sha256=sha(resolved),
        question_sources=catalog, text_origin='CURRENT_BUNDLE_QUESTION_SLOTS',
        model_quote_supplied=False, scientific_approval=False)
    return resolved, receipt


def make_request(bundle):
    system, user = fixed_assignment.make_request(bundle)
    message = json.loads(user)
    old = 'quote完整照抄对应question_slots。'
    if system.count(old) != 1:
        raise ValueError('EXPECTED_QUESTION_QUOTE_RULE_CHANGED')
    system = system.replace(old,
        'question_id复制question_catalog中该问题对应的ID；不要复抄问题原句。')
    system += '\n本合同为fixed-assignment-id。reading.intents每个问题只含kind和question_id，禁止quote。程序从当前材料定位原句；ID正确不代表意图或条件正确。其余读取、缺项和科学审核要求不变。\n'
    message['question_catalog'] = question_catalog(bundle)
    # Keep roster-specific condition rules and the historical JSON schema refs.
    message['output_schema']['$defs']['Intent'] = BoundIntent.model_json_schema()
    return system, json.dumps(message, ensure_ascii=False)


def attach_source_view(out, raw, receipt):
    # Preserve the raw, quote-free candidate, including on final Core results.
    out.update(contract=CONTRACT, reading_candidate=deepcopy(raw),
        question_binding=deepcopy(receipt))
    return out


def preview(bundle, raw):
    try:
        resolved, receipt = resolve_reading(bundle, raw)
    except (ValueError, TypeError, KeyError):
        return dict(contract=CONTRACT, state='CHECK_BLOCKED', reason_code='QUESTION_BOUND_READING_REJECTED',
            reading_candidate=deepcopy(raw), core_called=False, candidate_model_calls=0,
            query_views=[], intent_condition_review={}, production_admission=False,
            estimation_called=False, policy_called=False, estimation_handoff_allowed=False)
    return attach_source_view(fixed_assignment.preview(bundle, resolved), raw, receipt)
