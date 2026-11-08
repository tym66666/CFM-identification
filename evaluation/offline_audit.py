"""Read-only re-audit of frozen v032/v033 business-material experiments.

The frozen plan supplies the denominator; the ledger supplies attempt identity.
No providers, credentials, arbitrary stage Python, or historical scores execute.
This is research-side evaluation, never a model-facing feedback interface.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .audit_io import (
    AuditFailure, digest, inside, ratio, read_json, require, status_counts,
    strict_json, write_report,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = "offline-audit-v0.34"
PROFILES = {
    "language-generalization-v0.32": "business_materials_whole_clause_evidence",
    "language-contract-fix-v0.33": "business_materials",
}
FORMAT_ERRORS = {
    "MALFORMED_RESPONSE", "DUPLICATE_JSON_KEY", "NON_FINITE_JSON",
    "INVALID_JSON", "NON_OBJECT_JSON", "INVALID_JSON_RESPONSE",
}


def _adapter(version):
    # Explicit local implementations; never import a path from an artifact.
    from . import business_materials_whole_clause_evidence, business_materials
    return {"business_materials_whole_clause_evidence": business_materials_whole_clause_evidence,
            "business_materials": business_materials}[PROFILES[version]]


def _plan(stage):
    p = read_json(stage / "EXPERIMENT_PLAN.json")
    require(isinstance(p, dict) and p.get("version") in PROFILES, "UNSUPPORTED_AUDIT_PROFILE")
    require(isinstance(p.get("slots"), dict) and p["slots"], "PLAN_SCHEMA_FAILURE")
    require(isinstance(p.get("cases"), dict), "PLAN_SCHEMA_FAILURE")
    for run, slot in p["slots"].items():
        require(isinstance(run, str) and Path(run).name == run
                and "/" not in run and "\\" not in run, "PLAN_SCHEMA_FAILURE")
        require(isinstance(slot, dict) and isinstance(slot.get("key"), str)
                and slot.get("case") in p["cases"], "PLAN_SCHEMA_FAILURE")
        require(isinstance(p["cases"][slot["case"]], dict), "PLAN_SCHEMA_FAILURE")
        count = p["cases"][slot["case"]].get("query_count")
        require(type(count) is int and count > 0, "PLAN_SCHEMA_FAILURE")
    return p


def _frozen_inputs(stage, plan, root):
    for base, field in ((root, "source_sha256"), (stage, "artifact_sha256")):
        hashes = plan.get(field)
        require(isinstance(hashes, dict) and hashes, "FROZEN_INPUTS_NOT_DECLARED")
        for name, expected in hashes.items():
            require(digest(inside(base, name)) == expected, "FROZEN_INPUT_CHANGED", name)
    public = read_json(stage / "public_cases.json")
    require(isinstance(public, list), "PUBLIC_CASE_SCHEMA_FAILURE")
    indexed = {}
    for row in public:
        require(isinstance(row, dict) and isinstance(row.get("case_id"), str),
                "PUBLIC_CASE_SCHEMA_FAILURE")
        require(row["case_id"] not in indexed, "DUPLICATE_PUBLIC_CASE")
        indexed[row["case_id"]] = strict_json(row["input_bundle_json"], "public_cases.json")
        item = indexed[row["case_id"]]
        require(isinstance(item, dict) and isinstance(item.get("bundle"), dict)
                and isinstance(item["bundle"].get("structure"), dict),
                "PUBLIC_CASE_SCHEMA_FAILURE")
        info = plan["cases"][row["case_id"]]
        require(hashlib.sha256(row["input_bundle_json"].encode()).hexdigest()
                == info["public_sha256"], "PUBLIC_CASE_HASH_MISMATCH")
        require(hashlib.sha256((item["system"] + "\n" + item["user"]).encode()).hexdigest()
                == info["request_sha256"], "PROMPT_HASH_MISMATCH")
    refs = read_json(stage / "scoring_references.json")
    require(isinstance(refs, dict), "REFERENCE_SCHEMA_FAILURE")
    require(all(s["case"] in refs and s["case"] in indexed for s in plan["slots"].values()),
            "REFERENCE_COVERAGE_FAILURE")
    return indexed, refs


def _ledgers(plan, paths):
    result = {}
    for alias in sorted({s["key"] for s in plan["slots"].values()} | set(paths)):
        try:
            require(alias in paths, "LEDGER_REQUIRED")
            path = Path(paths[alias]).resolve()
            require(path.name == "REQUEST_LEDGER.json", "LEDGER_FILE_REQUIRED")
            value = read_json(path)
            require(isinstance(value, dict) and isinstance(value.get("requests"), list),
                    "LEDGER_SCHEMA_FAILURE")
            require(all(isinstance(r, dict) and isinstance(r.get("run_id"), str)
                        for r in value["requests"]), "LEDGER_SCHEMA_FAILURE")
            result[alias] = (path, value["requests"], None)
        except AuditFailure as error:
            result[alias] = (None, [], error.record())
    return result


def _coordinates(targets):
    from .business_core_pilot_base import target_coordinates
    values = [target_coordinates(t) for t in targets]
    for value in values:
        for key in ("nodes", "treated_nodes"):
            if value[key] is not None:
                value[key] = sorted(value[key])
    return values


def _quotes(targets):
    return [(t.population_quote, t.remaining_quote, t.plan_quote, t.question_quote,
             t.situation.quote if t.situation else None,
             t.reference.quote if t.reference else None) for t in targets]


def _decision(result):
    return [result["status"], result.get("reason_code"), [
        [q["status"], q.get("reason_code"), q.get("core", {}).get("route"),
         q.get("core", {}).get("reason_code"), q["core_called"], q["certificate_replay"]]
        for q in result["results"]]]


def check_semantics(adapter, public, raw, reference):
    """Preserve the frozen coordinate/quote rules, independently of old scores."""
    require(reference["score_mode"] == "FROZEN_COORDINATE_REFERENCE",
            "UNSUPPORTED_SCORING_RULE")
    _, study, targets = adapter.project(public["bundle"], raw)
    _, expected_study, expected_targets = adapter.project(
        public["bundle"], reference["raw_reading"])
    def span(value):
        return value.rstrip("；;。！？!?").strip() if isinstance(value, str) else value
    expected = reference["raw_reading"]["questions"]
    return dict(
        study=study == expected_study,
        query_coverage=set(raw["questions"]) == set(expected),
        targets=_coordinates(targets) == _coordinates(expected_targets),
        source_quotes=_quotes(targets) == _quotes(expected_targets),
        raw_remaining_declaration=all(raw["questions"][sid]["remaining_source"]
                                      == q["remaining_source"] for sid, q in expected.items()),
        evidence_span_semantics=all(span(raw["questions"][sid].get("remaining_evidence_span"))
                                    == span(q.get("remaining_evidence_span"))
                                    for sid, q in expected.items()),
    )


def _slot(row, stage, plan, ledger, public, reference, adapter):
    run, slot = row["run"], plan["slots"][row["run"]]
    path, entries, error = ledger
    if error:
        row.update(classification="ATTEMPT_STATUS_UNKNOWN", issue=error)
        return
    matches = [x for x in entries if x["run_id"] == stage.name + "_" + run]
    row.update(attempted=bool(matches), authenticated_attempts=len(matches))
    if not matches:
        # A stray pointer is not proof of an API call, nor proof no call happened.
        if (stage / (run + "_pointer.json")).exists():
            row.update(attempted=None, classification="LEDGER_ARTIFACT_CONFLICT")
        else:
            row["classification"] = "NOT_RUN"
        return
    require(len(matches) == 1, "DUPLICATE_ATTEMPT")
    record = matches[0]
    require(record.get("case_id") == slot["case"] and record.get("credential_alias") == slot["key"],
            "ATTEMPT_IDENTITY_MISMATCH")
    if record.get("status") in ("IN_FLIGHT", "PREPARED"):
        row["classification"] = "INCOMPLETE_ATTEMPT"
        return
    folder = inside(path.parent, record["artifact_directory"])
    pointer = read_json(stage / (run + "_pointer.json"))
    require(isinstance(pointer, dict) and isinstance(pointer.get("folder"), str),
            "ARTIFACT_SCHEMA_FAILURE", "pointer")
    require(Path(pointer["folder"]).resolve() == folder, "POINTER_LEDGER_MISMATCH")
    meta = read_json(folder / "result.json")
    require(isinstance(meta, dict), "ARTIFACT_SCHEMA_FAILURE", "result.json")
    require(meta.get("run") == run and meta.get("case_id") == slot["case"]
            and meta.get("key") == slot["key"]
            and type(meta.get("attempt")) is int and type(record.get("attempt")) is int
            and meta["attempt"] > 0
            and meta.get("attempt") == record.get("attempt"), "RESULT_IDENTITY_MISMATCH")
    require(type(meta.get("transport_calls")) is int and meta["transport_calls"] == 1
            and type(record.get("transport_calls")) is int
            and record["transport_calls"] == 1, "TRANSPORT_COUNT_MISMATCH")
    require(isinstance(meta.get("status"), str) and meta["status"]
            and meta.get("status") == record.get("status"), "LEDGER_RESULT_MISMATCH")
    body = read_json(folder / "request_body.json")
    require(hashlib.sha256(json.dumps(body, ensure_ascii=False).encode()).hexdigest()
            == record.get("request_body_sha256"), "REQUEST_LEDGER_HASH_MISMATCH")
    expected_body = dict(model=plan["model"], messages=[
        dict(role="system", content=public["system"]),
        dict(role="user", content=public["user"])],
        max_tokens=slot["max_tokens"], stream=slot["stream"],
        thinking={"type": plan["thinking"]})
    require(body == expected_body, "REQUEST_MISMATCH")
    row.update(payload_match=True, elapsed_seconds=meta.get("elapsed_seconds"))
    if meta.get("error_code"):
        row.update(classification=("MODEL_FORMAT_FAILURE" if meta["error_code"] in FORMAT_ERRORS
                                   else "TRANSPORT_FAILURE"), provider_error_code=meta["error_code"])
        return
    if meta["status"] == "LOCAL_ERROR":
        row["classification"] = "LOCAL_EXECUTION_FAILURE"
        return
    raw = read_json(folder / "model_draft.json")
    original = read_json(folder / "identification_result.json")
    require(isinstance(raw, dict) and isinstance(original, dict)
            and isinstance(original.get("results"), list), "ARTIFACT_SCHEMA_FAILURE")
    require(original.get("status") == meta["status"], "RESULT_STATUS_MISMATCH")
    try:
        checks = check_semantics(adapter, public, raw, reference)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        if isinstance(error, AuditFailure):
            raise
        row.update(classification="CONTRACT_FAILURE", error_kind=type(error).__name__)
        return
    row.update(semantic_checks=checks, semantic_passed=all(checks.values()))
    replay = adapter.evaluate_draft(public["bundle"], raw, reference["science_packet"],
                                    synthetic_protocol_selected=True)
    # Evaluate directly, never consume gNN_audit.json or a trusted-looking PASS.
    row["expected_decision_passed"] = _decision(original) == _decision(reference["expected_result"])
    row["result_reproduced"] = json.loads(json.dumps(replay)) == original
    require(all(original.get(k) is False for k in
                ("production_admission", "candidate_generator_called", "estimation_called", "policy_called")),
            "EXECUTION_BOUNDARY_FAILURE")
    points = [q for q in original["results"] if q["status"] == "POINT"]
    row["point_present"] = bool(points)
    row["point_replay_passed"] = (all(q.get("certificate_replay") is True for q in points)
                                  and row["result_reproduced"])
    row["identification_statuses"] = ([q["status"] for q in original["results"]]
                                       or [original["status"]])
    if not row["semantic_passed"]:
        row["classification"] = "SEMANTIC_FAILURE"
    elif points and not row["point_replay_passed"]:
        row["classification"] = "CERTIFICATE_FAILURE"
    elif not row["result_reproduced"]:
        row["classification"] = "RESULT_REPLAY_FAILURE"
    elif not row["expected_decision_passed"]:
        row["classification"] = "IDENTIFICATION_EXPECTATION_FAILURE"
    else:
        row.update(classification="PASS", point_certificates_replayed=len(points))


def audit_stage(stage, ledger_paths, *, root=ROOT):
    stage = Path(stage).resolve()
    result = dict(version=VERSION, evaluation_kind="OFFLINE_REAUDIT_OF_SAVED_MODEL_OUTPUTS",
                  api_calls=0, stage=stage.name, rows=[], planned_slots=None,
                  llm_complete_proof_accuracy="NOT_MEASURED",
                  independent_blind_holdout=False, research_only=True,
                  verification_scope="Exact support and rule replay; not a proof-assistant formalization")
    try:
        plan = _plan(stage)
        result.update(plan_sha256=digest(stage / "EXPERIMENT_PLAN.json"),
                      profile=plan["version"], planned_slots=len(plan["slots"]))
    except (AuditFailure, KeyError, TypeError, AttributeError) as error:
        result.update(status="AUDIT_PLAN_FAILURE",
                      issue=error.record() if isinstance(error, AuditFailure)
                      else dict(classification="PLAN_SCHEMA_FAILURE"),
                      acceptance_per_planned_slot=ratio(0, None))
        return result
    ledgers = _ledgers(plan, ledger_paths)
    frozen_error = None
    try:
        public, refs = _frozen_inputs(stage, plan, Path(root))
        adapter = _adapter(plan["version"])
    except (AuditFailure, KeyError, TypeError, AttributeError) as error:
        frozen_error = (error.record() if isinstance(error, AuditFailure)
                        else dict(classification="FROZEN_INPUT_SCHEMA_FAILURE"))
    result["frozen_inputs_verified"] = frozen_error is None
    if frozen_error:
        result["frozen_input_issue"] = frozen_error
    else:
        # Diagnostic grouping only, not graph-isomorphism or statistical
        # independence detection. Different wordings can share one setting.
        structures = Counter()
        for cid in {s["case"] for s in plan["slots"].values()}:
            shape = public[cid].get("bundle", {}).get("structure", {})
            signature = {k: shape.get(k) for k in ("nodes", "edges", "groups", "cluster_rates")}
            structures[json.dumps(signature, sort_keys=True)] += 1
        result.update(unique_case_ids=len({s["case"] for s in plan["slots"].values()}),
                      exact_structure_group_count=len(structures),
                      exact_structure_group_sizes=sorted(structures.values(), reverse=True),
                      structure_grouping_scope="Exact named network/design structure; not independent sample count")
    for run, slot in plan["slots"].items():
        row = dict(run=run, case_id=slot["case"], attempted=None,
                   classification="AUDIT_INTERNAL_FAILURE")
        ledger = ledgers[slot["key"]]
        if ledger[2] is None:
            entries = [e for e in ledger[1] if e["run_id"] == stage.name + "_" + run]
            orphan = not entries and (stage / (run + "_pointer.json")).exists()
            row.update(attempted=None if orphan else bool(entries), authenticated_attempts=len(entries))
        try:
            if frozen_error:
                row["classification"] = "AUDIT_INPUT_FAILURE"
            else:
                _slot(row, stage, plan, ledger, public[slot["case"]], refs[slot["case"]], adapter)
        except AuditFailure as error:
            row.update(error.record())
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            row["classification"] = "ARTIFACT_SCHEMA_FAILURE"
        except Exception as error:
            # Preserve the slot and continue, without exposing arbitrary error text.
            row.update(classification="AUDIT_INTERNAL_FAILURE", error_kind=type(error).__name__)
        result["rows"].append(row)
    rows = result["rows"]
    unknown = sum(r["attempted"] is None for r in rows)
    attempts = None if unknown else sum(r["attempted"] for r in rows)
    passes = sum(r["classification"] == "PASS" for r in rows)
    prefix = stage.name + "_"
    planned_runs = {prefix + run for run in plan["slots"]}
    stage_requests = [(alias, e) for alias, (_, entries, error) in ledgers.items()
                      if error is None for e in entries if e["run_id"].startswith(prefix)]
    unplanned = [dict(credential_alias=alias, run_id=e["run_id"])
                 for alias, e in stage_requests
                 if e["run_id"] not in planned_runs
                 or alias != plan["slots"][e["run_id"][len(prefix):]]["key"]]
    ledger_incomplete = any(v[2] for v in ledgers.values())
    result.update(
        status="COMPLETE" if passes == len(rows) and not unplanned and not ledger_incomplete
        else "HAS_NONPASS_SLOTS",
        attempted_slots=attempts, attempt_status_unknown_slots=unknown,
        confirmed_not_attempted_slots=sum(r["attempted"] is False for r in rows),
        authenticated_attempts=None if ledger_incomplete else len(stage_requests),
        audited_credential_aliases=sorted(ledgers),
        unplanned_attempts=unplanned,
        publishable_summary=not unplanned and not ledger_incomplete and unknown == 0
        and frozen_error is None and all(r["classification"] in {
            "PASS", "NOT_RUN", "TRANSPORT_FAILURE", "MODEL_FORMAT_FAILURE",
            "CONTRACT_FAILURE", "SEMANTIC_FAILURE", "IDENTIFICATION_EXPECTATION_FAILURE",
            "CERTIFICATE_FAILURE", "RESULT_REPLAY_FAILURE", "LOCAL_EXECUTION_FAILURE",
        } for r in rows),
        status_counts=status_counts(rows), strict_passes=passes,
        acceptance_per_planned_slot=ratio(passes, len(rows)),
        acceptance_per_attempted_slot=ratio(passes, attempts),
        semantic_passed_slots=sum(r.get("semantic_passed") is True for r in rows),
        point_certificates_replayed=sum(r.get("point_certificates_replayed", 0) for r in rows),
        identification_status_counts=dict(Counter(
            s for r in rows if r["classification"] == "PASS" for s in r["identification_statuses"])),
        auditor_sha256={p.name: digest(p) for p in
                        (Path(__file__), Path(__file__).with_name("audit_io.py"))},
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--ledger", action="append", default=[], metavar="ALIAS=REQUEST_LEDGER.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    paths = {}
    try:
        for value in args.ledger:
            alias, path = value.split("=", 1)
            require(alias not in paths, "DUPLICATE_LEDGER_ALIAS")
            paths[alias] = Path(path)
        require(not args.output.resolve().is_relative_to(args.stage.resolve()),
                "OUTPUT_MUST_NOT_MODIFY_FROZEN_STAGE")
        require(all(not args.output.resolve().is_relative_to(p.resolve().parent)
                    for p in paths.values()), "OUTPUT_MUST_NOT_MODIFY_LEDGER_DIRECTORY")
        report = audit_stage(args.stage, paths)
        write_report(args.output, report)
    except (AuditFailure, OSError, ValueError) as error:
        print(json.dumps(dict(status="AUDIT_OUTPUT_OR_ARGUMENT_FAILURE", error_kind=type(error).__name__)))
        return 2
    print(json.dumps({k: report[k] for k in ("version", "status", "planned_slots", "api_calls")}))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
