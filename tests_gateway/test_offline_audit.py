"""Fault injection against saved evidence; no model requests or real keys."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from evaluation.audit_io import AuditFailure, digest, read_json, strict_json, write_report
from evaluation.offline_audit import ROOT, audit_stage, main
from evaluation.nbib_acceptance import DATA, material_input, read
from evaluation.business_materials_intake import sources
from evaluation import business_materials as adapter
from evaluation.structured_prediction_audit import (
    DEFAULT_BENCHMARK, audit_predictions, freeze_plan,
)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


class StageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = material_input("H25-service_arm")
        cls.ref = deepcopy(read(DATA / "research_only/formal_references.json")["H25-service_arm"])
        for q in cls.ref["raw_reading"]["questions"].values():
            q["remaining_evidence_span"] = sources(cls.bundle)[q["remaining_source"]]
        cls.ref["expected_result"] = adapter.evaluate_draft(
            cls.bundle, cls.ref["raw_reading"], cls.ref["science_packet"],
            synthetic_protocol_selected=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stage = self.base / "frozen_stage"
        self.stage.mkdir()
        self.store = self.base / "saved_requests"
        self.store.mkdir()
        self.ledger = self.store / "REQUEST_LEDGER.json"
        self.cid = "H25-service_arm"
        system, user = adapter.make_request(self.bundle)
        public = dict(kind="business", bundle=self.bundle, system=system, user=user)
        encoded = json.dumps(public, ensure_ascii=False)
        save(self.stage / "public_cases.json", [dict(case_id=self.cid, input_bundle_json=encoded)])
        save(self.stage / "scoring_references.json", {self.cid: self.ref})
        body = dict(model="offline-fixture", messages=[
            dict(role="system", content=system), dict(role="user", content=user)],
            max_tokens=2048, stream=False, thinking={"type": "disabled"})
        records = []
        for i in range(1, 4):
            run = f"g{i:02d}"
            folder = self.store / run
            folder.mkdir()
            save(folder / "request_body.json", body)
            save(folder / "model_draft.json", self.ref["raw_reading"])
            save(folder / "identification_result.json", self.ref["expected_result"])
            save(folder / "result.json", dict(
                run=run, case_id=self.cid, key="fixture", attempt=i,
                transport_calls=1, status=self.ref["expected_result"]["status"]))
            save(self.stage / (run + "_pointer.json"), {"folder": str(folder)})
            records.append(dict(run_id="frozen_stage_" + run, case_id=self.cid,
                                credential_alias="fixture", attempt=i, artifact_directory=run,
                                transport_calls=1, status=self.ref["expected_result"]["status"],
                                request_body_sha256=hashlib.sha256(
                                    json.dumps(body, ensure_ascii=False).encode()).hexdigest()))
        save(self.ledger, dict(requests=records))
        self.plan = dict(
            version="language-contract-fix-v0.33", model="offline-fixture", thinking="disabled",
            slots={f"g{i:02d}": dict(case=self.cid, key="fixture", max_tokens=2048, stream=False)
                   for i in range(1, 4)},
            cases={self.cid: dict(query_count=1,
                                 public_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
                                 request_sha256=hashlib.sha256((system + "\n" + user).encode()).hexdigest())},
            source_sha256={"evaluation/business_materials.py":
                           digest(ROOT / "evaluation/business_materials.py")},
            artifact_sha256={name: digest(self.stage / name)
                             for name in ("public_cases.json", "scoring_references.json")},
        )
        save(self.stage / "EXPERIMENT_PLAN.json", self.plan)

    def audit(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("No network")):
            return audit_stage(self.stage, {"fixture": self.ledger})

    def mutate(self, path, edit):
        value = read_json(path)
        edit(value)
        save(path, value)

    def test_clean_repeated_slots_are_counted_as_attempts_not_best_of(self):
        report = self.audit()
        self.assertEqual((report["planned_slots"], report["attempted_slots"], report["strict_passes"]), (3, 3, 3))
        self.assertEqual(report["point_certificates_replayed"], 3)
        self.assertEqual(report["llm_complete_proof_accuracy"], "NOT_MEASURED")
        self.assertFalse(report["independent_blind_holdout"])

    def test_corrupt_artifact_retained_next_slots_continue_and_stale_pass_ignored(self):
        save(self.stage / "g01_audit.json", {"strict_semantic_pass": True})
        (self.store / "g01/model_draft.json").write_text("{", encoding="utf8")
        report = self.audit()
        self.assertEqual(report["status_counts"], {"ARTIFACT_PARSE_FAILURE": 1, "PASS": 2})
        self.assertEqual(report["acceptance_per_attempted_slot"]["denominator"], 3)
        self.assertEqual(report["acceptance_per_planned_slot"]["numerator"], 2)
        self.assertFalse(report["publishable_summary"])
        self.assertEqual(read_json(self.stage / "g01_audit.json"), {"strict_semantic_pass": True})

    def test_missing_file_is_not_an_unrun_attempt(self):
        (self.store / "g01/model_draft.json").unlink()
        report = self.audit()
        self.assertEqual(report["rows"][0]["classification"], "ARTIFACT_MISSING")
        self.assertEqual(report["attempted_slots"], 3)

    def test_unrun_slot_remains_in_planned_denominator(self):
        self.mutate(self.ledger, lambda x: x["requests"].pop())
        (self.stage / "g03_pointer.json").unlink()
        report = self.audit()
        self.assertEqual(report["status_counts"], {"PASS": 2, "NOT_RUN": 1})
        self.assertEqual(report["acceptance_per_planned_slot"]["denominator"], 3)
        self.assertEqual(report["acceptance_per_attempted_slot"]["denominator"], 2)

    def test_duplicate_attempt_is_failure_and_never_selects_best_output(self):
        self.mutate(self.ledger, lambda x: x["requests"].append(deepcopy(x["requests"][0])))
        report = self.audit()
        self.assertEqual(report["rows"][0]["classification"], "DUPLICATE_ATTEMPT")
        self.assertEqual(report["authenticated_attempts"], 4)
        self.assertEqual(report["attempted_slots"], 3)

    def test_unplanned_stage_request_cannot_disappear_from_call_count(self):
        def add(value):
            extra = deepcopy(value["requests"][0])
            extra["run_id"] = "frozen_stage_extra"
            value["requests"].append(extra)
        self.mutate(self.ledger, add)
        report = self.audit()
        self.assertEqual(report["strict_passes"], 3)
        self.assertEqual(report["authenticated_attempts"], 4)
        self.assertEqual(len(report["unplanned_attempts"]), 1)
        self.assertEqual(report["status"], "HAS_NONPASS_SLOTS")
        self.assertFalse(report["publishable_summary"])

    def test_malformed_ledger_does_not_invent_zero_attempts(self):
        self.ledger.write_text("{", encoding="utf8")
        report = self.audit()
        self.assertIsNone(report["attempted_slots"])
        self.assertIsNone(report["acceptance_per_attempted_slot"]["rate"])
        self.assertEqual(report["planned_slots"], 3)
        self.assertEqual(report["attempt_status_unknown_slots"], 3)

    def test_orphan_pointer_is_unknown_not_confirmed_unrun(self):
        self.mutate(self.ledger, lambda x: x["requests"].pop())
        report = self.audit()
        self.assertEqual(report["rows"][2]["classification"], "LEDGER_ARTIFACT_CONFLICT")
        self.assertIsNone(report["attempted_slots"])

    def test_wrong_pointer_and_wrong_identity_cannot_reuse_another_output(self):
        save(self.stage / "g01_pointer.json", {"folder": str(self.store / "g02")})
        report = self.audit()
        self.assertEqual(report["rows"][0]["classification"], "POINTER_LEDGER_MISMATCH")
        self.mutate(self.store / "g02/result.json", lambda x: x.update(case_id="other"))
        self.assertEqual(self.audit()["rows"][1]["classification"], "RESULT_IDENTITY_MISMATCH")

    def test_frozen_reference_damage_fails_closed_for_every_planned_slot(self):
        (self.stage / "scoring_references.json").write_text("{", encoding="utf8")
        report = self.audit()
        self.assertEqual(report["status_counts"], {"AUDIT_INPUT_FAILURE": 3})
        self.assertEqual(report["planned_slots"], 3)
        self.assertEqual(report["attempted_slots"], 3)
        self.assertFalse(report["frozen_inputs_verified"])

    def test_corrupt_plan_never_reports_zero_of_zero_success(self):
        (self.stage / "EXPERIMENT_PLAN.json").write_text("{", encoding="utf8")
        report = self.audit()
        self.assertEqual(report["status"], "AUDIT_PLAN_FAILURE")
        self.assertIsNone(report["planned_slots"])
        self.assertIsNone(report["acceptance_per_planned_slot"]["rate"])

    def test_malformed_nested_plan_is_a_report_not_an_exception(self):
        self.plan["cases"][self.cid] = []
        save(self.stage / "EXPERIMENT_PLAN.json", self.plan)
        self.assertEqual(self.audit()["status"], "AUDIT_PLAN_FAILURE")

    def test_boolean_ledger_counts_cannot_impersonate_integer_evidence(self):
        self.mutate(self.ledger, lambda x: x["requests"][0].update(transport_calls=True))
        self.assertEqual(self.audit()["rows"][0]["classification"], "TRANSPORT_COUNT_MISMATCH")

    def test_metadata_status_must_match_the_actual_identification_result(self):
        self.mutate(self.store / "g01/result.json", lambda x: x.update(status="NEEDS_INPUT"))
        self.mutate(self.ledger, lambda x: x["requests"][0].update(status="NEEDS_INPUT"))
        self.assertEqual(self.audit()["rows"][0]["classification"], "RESULT_STATUS_MISMATCH")

    def test_certificate_flag_tampering_cannot_pass(self):
        self.mutate(self.store / "g01/identification_result.json",
                    lambda x: x["results"][0].update(certificate_replay=False))
        report = self.audit()
        self.assertEqual(report["rows"][0]["classification"], "CERTIFICATE_FAILURE")
        self.assertEqual(report["point_certificates_replayed"], 2)

    def test_valid_shape_wrong_business_node_is_semantic_failure(self):
        self.mutate(self.store / "g01/model_draft.json",
                    lambda x: x["questions"]["q1"]["population"].update(ids=["S_05"]))
        self.assertEqual(self.audit()["rows"][0]["classification"], "SEMANTIC_FAILURE")

    def test_damaged_request_cannot_be_rescued_by_valid_output(self):
        self.mutate(self.store / "g01/request_body.json", lambda x: x.update(model="other"))
        self.assertEqual(self.audit()["rows"][0]["classification"], "REQUEST_LEDGER_HASH_MISMATCH")

    def test_inflight_missing_pointer_is_counted_as_incomplete_attempt(self):
        self.mutate(self.ledger, lambda x: x["requests"][0].update(status="IN_FLIGHT"))
        (self.stage / "g01_pointer.json").unlink()
        report = self.audit()
        self.assertEqual(report["rows"][0]["classification"], "INCOMPLETE_ATTEMPT")
        self.assertEqual(report["attempted_slots"], 3)

    def test_transport_and_model_format_failure_are_separate(self):
        for i, code in ((1, "PROCESS_WALL_DEADLINE"), (2, "MALFORMED_RESPONSE")):
            self.mutate(self.store / f"g{i:02d}/result.json",
                        lambda x, code=code: x.update(status="REJECTED", error_code=code))
            self.mutate(self.ledger, lambda x, i=i: x["requests"][i - 1].update(status="REJECTED"))
            (self.store / f"g{i:02d}/model_draft.json").unlink()
        report = self.audit()
        self.assertEqual(report["status_counts"], {"TRANSPORT_FAILURE": 1, "MODEL_FORMAT_FAILURE": 1, "PASS": 1})

    def test_cli_writes_failure_report_but_cannot_overwrite_evidence(self):
        (self.store / "g01/model_draft.json").write_text("{", encoding="utf8")
        output = self.base / "audit.json"
        args = ["--stage", str(self.stage), "--ledger", f"fixture={self.ledger}", "--output", str(output)]
        self.assertEqual(main(args), 2)
        self.assertEqual(read_json(output)["strict_passes"], 2)
        before = output.read_bytes()
        self.assertEqual(main(args), 2)
        self.assertEqual(output.read_bytes(), before)
        args[-1] = str(self.stage / "new_audit.json")
        self.assertEqual(main(args), 2)
        self.assertFalse((self.stage / "new_audit.json").exists())


class StructuredPredictionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.ids = ["NBIB-001", "NBIB-007"]
        self.manifest = self.base / "plan.json"
        save(self.manifest, freeze_plan(DEFAULT_BENCHMARK, self.ids))
        self.good = read_json(ROOT / "assets/benchmark_assets/examples/two_structured_predictions_EXAMPLE.json")
        self.pred = self.base / "predictions.json"
        save(self.pred, self.good)

    def audit(self, mode="json"):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("No network")):
            return audit_predictions(DEFAULT_BENCHMARK, self.manifest, self.pred, input_format=mode)

    def test_original_example_scores_without_claiming_math_or_proof(self):
        report = self.audit()
        self.assertEqual(report["matched_cases"], 2)
        self.assertEqual(report["math_identification_accuracy"], "NOT_MEASURED")
        self.assertEqual(report["llm_complete_proof_accuracy"], "NOT_MEASURED")

    def test_broken_whole_json_retains_frozen_denominator(self):
        self.pred.write_text('{"predictions":[', encoding="utf8")
        report = self.audit()
        self.assertEqual(report["status_counts"], {"ARTIFACT_PARSE_FAILURE": 2})
        self.assertEqual(report["structured_matches_per_planned_case"]["denominator"], 2)
        self.assertFalse(report["publishable_summary"])

    def test_jsonl_recovers_later_records_without_guessing_corrupt_case_id(self):
        self.pred.write_text('{"case_id":\n' + json.dumps(self.good["predictions"][1]), encoding="utf8")
        report = self.audit("jsonl")
        self.assertEqual(report["status_counts"], {"MISSING_PREDICTION": 1, "STRUCTURED_FIELDS_MATCH": 1})
        self.assertEqual(report["input_issues"][0]["line"], 1)
        self.assertEqual(report["structured_matches_per_planned_case"]["denominator"], 2)
        self.assertFalse(report["publishable_summary"])

    def test_duplicate_prediction_never_chooses_the_correct_one(self):
        self.good["predictions"].append(deepcopy(self.good["predictions"][0]))
        self.good["predictions"][-1]["assignment_family"] = "incorrect"
        save(self.pred, self.good)
        report = self.audit()
        self.assertEqual(report["status_counts"], {"DUPLICATE_PREDICTION": 1, "STRUCTURED_FIELDS_MATCH": 1})

    def test_unknown_and_unassigned_records_are_not_silently_discarded(self):
        self.good["predictions"].extend([{"case_id": "UNKNOWN"}, ["not", "a", "prediction"]])
        save(self.pred, self.good)
        report = self.audit()
        self.assertEqual(len(report["input_issues"]), 2)
        self.assertEqual(report["status"], "HAS_FAILURES")
        self.assertFalse(report["publishable_summary"])

    def test_unsafe_scientific_claim_cannot_count_as_structured_success(self):
        self.good["predictions"][0]["claims_a4_pop_available"] = True
        save(self.pred, self.good)
        self.assertEqual(self.audit()["rows"][0]["classification"], "UNSAFE_SCIENTIFIC_CLAIM")

    def test_missing_prediction_is_in_planned_denominator(self):
        self.good["predictions"].pop()
        save(self.pred, self.good)
        report = self.audit()
        self.assertEqual(report["structured_matches_per_planned_case"]["rate"], 0.5)
        self.assertEqual(report["rows"][1]["classification"], "MISSING_PREDICTION")

    def test_invalid_plan_never_manufactures_an_empty_success(self):
        self.manifest.write_text("null", encoding="utf8")
        report = self.audit()
        self.assertEqual(report["status"], "AUDIT_INPUT_FAILURE")
        self.assertIsNone(report["planned_cases"])

    def test_changed_reference_hash_blocks_scoring(self):
        value = read_json(self.manifest)
        value["reference_sha256"]["NBIB-001"] = "0" * 64
        save(self.manifest, value)
        report = self.audit()
        self.assertEqual(report["status"], "AUDIT_INPUT_FAILURE")
        self.assertEqual(len(report["rows"]), 2)


class StrictAuditIoTests(unittest.TestCase):
    def test_duplicate_nonfinite_and_bad_unicode_rejected_without_echo(self):
        for text in ('{"x":0,"x":1}', '{"x":NaN}', '{"x":1e999}', '{"private":'):
            with self.subTest(text=text), self.assertRaises(AuditFailure) as caught:
                strict_json(text)
            self.assertNotIn("private", str(caught.exception))

    def test_write_report_refuses_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            write_report(path, {"old": True})
            with self.assertRaises(FileExistsError):
                write_report(path, {"old": False})
            self.assertEqual(read_json(path), {"old": True})


if __name__ == "__main__":
    unittest.main()
