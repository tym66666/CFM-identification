"""Small, explicit entry for business reading; never grants scientific approval.

Fixed-policy reading lives in cfm_id_llm.readers; older network reading uses
the isolated cfm_id.workflows.legacy_network compatibility implementation. This retained
API prepares a request, receives a candidate, and previews it.
Provider credentials, research labels and science packets are not API inputs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

import cfm_id.workflows.legacy_network.frozen_reading as legacy_reading
import cfm_id.workflows.legacy_network.question_intent as intent_reading
from cfm_id_llm.readers import fixed_policy as fixed_reading
import cfm_id.workflows.legacy_network.core_peers_staged_base as core_study
import cfm_id.workflows.legacy_network.staged_d1_d2 as other_study
from .materials import goal_slots
from .material_reading_contract import clarify_request
from . import fixed_assignment
from . import question_bound_assignment


ENTRIES = ("D1_EFFECTS", "STAGED_CORE_PEERS", "D2_ARM", "CLUSTER_ARM", "FIXED_POLICY", "FIXED_COMPARISON")
CONTRACTS = {"intent-v0561": intent_reading, "legacy-v0551": legacy_reading,
             "fixed-assignment": fixed_assignment,
             "fixed-assignment-id": question_bound_assignment}


def _reader(contract):
    if contract not in CONTRACTS:
        raise ValueError("UNKNOWN_READING_CONTRACT")
    return CONTRACTS[contract]


def _check(bundle, entry, envelope):
    if entry not in ENTRIES:
        raise ValueError("EXPLICIT_SUPPORTED_ENTRY_REQUIRED")
    if entry == "STAGED_CORE_PEERS":
        if envelope is None:
            raise ValueError("BOUND_STUDY_REQUIRED")
        core_study.validate_envelope(bundle, envelope)
    elif envelope is not None:
        if entry != "D2_ARM":
            raise ValueError("ENVELOPE_NOT_SUPPORTED_BY_THIS_ENTRY")
        other_study.validate_envelope(bundle, entry, envelope)


def prepare_request(bundle, entry, envelope=None, *, contract="intent-v0561"):
    """Return public prompts only. Entry selection is explicit, not model routing."""
    _check(bundle, entry, envelope)
    if entry == 'FIXED_COMPARISON':
        if contract != question_bound_assignment.CONTRACT:
            raise ValueError('COMPARISON_REQUIRES_QUESTION_BOUND_CONTRACT')
        from .fixed_comparison import make_request
        system, user = make_request(bundle)
        return {'system': system, 'user': user}
    if contract in (fixed_assignment.CONTRACT, question_bound_assignment.CONTRACT):
        if entry != 'FIXED_POLICY':
            raise ValueError('FIXED_ASSIGNMENT_REQUIRES_FIXED_POLICY_ENTRY')
        system, user = CONTRACTS[contract].make_request(bundle)
        return {'system': system, 'user': user}
    if entry == 'FIXED_POLICY':
        if contract != 'intent-v0561':
            raise ValueError('FIXED_POLICY_REQUIRES_INTENT_CONTRACT')
        system, user = fixed_reading.make_request(bundle)
        return {'system': system, 'user': user}
    system, user = _reader(contract).make_request(bundle, entry, envelope)
    request = {"system": system, "user": user}
    # Other entries and the explicit historical contract retain their requests.
    return clarify_request(request) if contract == "intent-v0561" and entry == "D1_EFFECTS" else request


def preview(bundle, candidate, entry, envelope=None, *, contract="intent-v0561"):
    """Validate a reading without approving assumptions or calling the Core.

Preserves the underlying result, including per-question states for MIXED.
REVIEW_REQUIRED means ready for independent review, never POINT.
"""
    _check(bundle, entry, envelope)
    if entry == 'FIXED_COMPARISON':
        if contract != question_bound_assignment.CONTRACT:
            raise ValueError('COMPARISON_REQUIRES_QUESTION_BOUND_CONTRACT')
        from .fixed_comparison import preview as comparison_preview
        return comparison_preview(bundle, candidate)
    if contract in (fixed_assignment.CONTRACT, question_bound_assignment.CONTRACT):
        if entry != 'FIXED_POLICY':
            raise ValueError('FIXED_ASSIGNMENT_REQUIRES_FIXED_POLICY_ENTRY')
        return CONTRACTS[contract].preview(bundle, candidate)
    if entry == 'FIXED_POLICY':
        if contract != 'intent-v0561':
            raise ValueError('FIXED_POLICY_REQUIRES_INTENT_CONTRACT')
        return fixed_reading.preview(bundle, candidate)
    result = _reader(contract).identify(bundle, candidate, entry, envelope)
    if any(result.get(k) for k in (
        "core_called", "production_admission", "estimation_called", "policy_called",
        "estimation_handoff_allowed", "candidate_model_calls",
    )):
        raise RuntimeError("READING_ENTRY_CROSSED_ITS_AUTHORITY")
    return result


def read_once(bundle, provider, entry, envelope=None, *, contract="intent-v0561"):
    """One provider invocation; errors propagate without repair/retry or fallback.

The caller must supply an authorized, separately budgeted provider. No model
provider is created here; the bundled student example uses recorded responses.
"""
    request = prepare_request(bundle, entry, envelope, contract=contract)
    candidate = provider.generate_json(
        system_prompt=request["system"], user_prompt=request["user"]
    )
    return preview(bundle, candidate, entry, envelope, contract=contract)


def goal_variant(bundle, text):
    """Create a DEVELOPMENT wording variant, preserving historical materials.

The user writes ordinary questions; this helper only indexes question spans.
It does not supply normalized coordinates, labels or scientific permissions.
Use a fresh model reading for edited text; never recycle a recorded candidate.
"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("BUSINESS_TEXT_REQUIRED")
    result = deepcopy(bundle)
    result["active_goal_document"] = "target_clarification.txt"
    result["documents"]["target_clarification.txt"] = text
    result["question_slots"] = goal_slots(text)
    result["revision_kind"] = "DEVELOPMENT_GOAL_VARIANT"
    return result


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _save_new(path, value):
    # Preserve earlier outputs. Choose a new output name for each run.
    with Path(path).open("x", encoding="utf8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    variant = commands.add_parser("variant", help="Index new natural-language questions")
    variant.add_argument("--bundle", required=True)
    variant.add_argument("--text", required=True)
    variant.add_argument("--output", required=True)
    for command in ("prepare", "preview"):
        p = commands.add_parser(command)
        p.add_argument("--entry", choices=ENTRIES, required=True)
        p.add_argument("--contract", choices=tuple(CONTRACTS), default="intent-v0561")
        p.add_argument("--bundle", required=True)
        p.add_argument("--envelope")
        p.add_argument("--output", required=True)
        if command == "preview":
            p.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    try:
        bundle = _read(args.bundle)
        if args.command == "variant":
            value = goal_variant(bundle, Path(args.text).read_text(encoding="utf-8-sig"))
        else:
            envelope = _read(args.envelope) if args.envelope else None
            if args.command == "prepare":
                value = prepare_request(bundle, args.entry, envelope, contract=args.contract)
            else:
                value = preview(bundle, _read(args.candidate), args.entry, envelope, contract=args.contract)
        _save_new(args.output, value)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        # Never echo arbitrary input content into terminal errors.
        parser.exit(2, f"INPUT_OR_OUTPUT_ERROR: {type(exc).__name__}; check inputs and use a new output path.\n")
    print(json.dumps({"command": args.command, "state": value.get("state"),
                      "http_calls": 0, "core_called": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
