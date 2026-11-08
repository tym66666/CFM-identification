"""Conservative LOCAL guard for this benchmark's one-question-per-sentence input.

Not a general natural-language theorem. Repeated or missing question units are
held for review, never deduplicated or repaired. No new online request here.
"""
from pydantic import ValidationError
from .business_core_pilot_base import canonical_hash
from .business_core_source_refs import source_catalog, resolve_sources
from .business_core_pilot import numeric_projection
from .business_core_branches import expand_branches, evaluate_draft as previous

VERSION = "business-core-local-coverage-v0.20.6"


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        return previous(question, {}, packet, synthetic_protocol_selected=False)
    base = dict(version=VERSION, mode="SYNTHETIC_BENCHMARK_ONLY",
                model_draft_sha256=canonical_hash(raw), results=[], production_admission=False,
                semantic_correctness_verified=False, candidate_generator_called=False,
                estimation_called=False, policy_called=False, nonidentification_proven=False)
    units = [ref for ref, text in source_catalog(question).items() if text.rstrip().endswith(("？", "?"))]
    targets = raw.get("targets") if isinstance(raw, dict) else None
    provided = [t.get("question_source") for t in targets if isinstance(t, dict)] if isinstance(targets, list) else []
    if not units or provided != units:
        return {**base, "status": "REVIEW_REQUIRED",
                "reason_code": "QUESTION_COVERAGE_REQUIRES_REVIEW",
                "expected_question_units": units, "provided_question_units": provided}
    try:
        expanded = expand_branches(raw)
        numeric_projection(resolve_sources(question, expanded))
    except (ValueError, TypeError, KeyError, ValidationError):
        return {**base, "status": "REJECTED", "reason_code": "TARGET_BRANCH_CONTRACT_INVALID"}
    # Core/replay failures must still propagate, not be relabelled as bad input.
    result = previous(question, raw, packet, synthetic_protocol_selected=True)
    result["local_coverage_guard_version"] = VERSION
    return result
