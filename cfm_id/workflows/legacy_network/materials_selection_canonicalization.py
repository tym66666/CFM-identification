"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import cfm_id.workflows.legacy_network.materials_remaining_declaration as previous
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.serialization import canonical_hash


VERSION = "business-materials-v0.23.8"


SYSTEM = previous.SYSTEM + """
选择全体或有跨组邻居时，ids通常填[]，由程序读取名单；若填写名单，必须恰好完整列出该范围的全部编号，不能缺失、重复或混入其他对象。
"""


def normalize(value, raw):
    bundle = bundle_value(value)
    copied, actions = deepcopy(raw), []
    if not isinstance(copied, dict) or not isinstance(copied.get("questions"), dict):
        return copied, actions
    for sid, q in copied["questions"].items():
        if not isinstance(q, dict):
            continue
        selections = [("population", q.get("population"))]
        selections += [(key + ".treated", w.get("treated")) for key in ("first", "second")
                       if isinstance((w := q.get(key)), dict) and w.get("setting") == "完整安排"]
        for field, s in selections:
            if not isinstance(s, dict) or s.get("selection") not in ("全体", "有跨组邻居"):
                continue
            if s["selection"] == "有跨组邻居" and field != "population":
                continue  # The previous adapter rejects this invalid context.
            ids = s.get("ids")
            if not isinstance(ids, list) or any(not isinstance(n, str) for n in ids):
                raise ValueError("REDUNDANT_SCOPE_IDS_INVALID")
            expected = bundle["structure"]["nodes" if s["selection"] == "全体" else "units_with_cross_group_neighbors"]
            if ids:
                if len(ids) != len(set(ids)) or set(ids) != set(expected):
                    raise ValueError("REDUNDANT_SCOPE_IDS_CONFLICT")
                actions.append(dict(question_id=sid, field=field + ".ids", selection=s["selection"],
                                    original_ids=ids, canonical_ids=[], verified_count=len(ids)))
                s["ids"] = []
    return copied, actions


def make_request(value):
    _, user = previous.make_request(value)
    return SYSTEM, user


output_schema = previous.output_schema


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
    r.update(version=VERSION, model_draft_sha256=canonical_hash(raw), redundant_scope_normalizations=actions)
    return r
