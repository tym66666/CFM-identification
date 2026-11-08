import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cfm_id import business_entry as api


KIT = Path(__file__).resolve().parents[1] / "examples/legacy/business_extension"


def read(name):
    return json.loads((KIT / name).read_text(encoding="utf8"))


class BusinessEntryTests(unittest.TestCase):
    def setUp(self):
        self.bundle = read("public/positive_bundle.json")
        self.envelope = read("recorded/study_envelope.json")
        self.raw = read("recorded/positive_candidate.json")

    def test_complete_reading_stops_before_scientific_review(self):
        before = deepcopy(self.raw)
        with patch("socket.create_connection", side_effect=AssertionError("NO_NETWORK")):
            r = api.preview(self.bundle, self.raw, "D2_ARM", self.envelope, contract="legacy-v0551")
        self.assertEqual(r["state"], "REVIEW_REQUIRED")
        self.assertFalse(r["core_called"])
        self.assertEqual(self.raw, before)

    def test_missing_own_treatment_keeps_known_neighbor_count(self):
        b = read("public/negative_bundle.json")
        raw = read("recorded/negative_candidate.json")
        r = api.preview(b, raw, "D2_ARM", self.envelope, contract="legacy-v0551")
        self.assertEqual(r["state"], "NEEDS_INPUT")
        self.assertEqual(raw["questions"]["q1"]["first"]["own"], "不明确")
        self.assertEqual(raw["questions"]["q1"]["first"]["neighbor_count"], 1)
        self.assertFalse(r["core_called"])

    def test_history_change_invalidates_saved_study(self):
        self.bundle["documents"]["study_protocol.md"] += "\n更正：抽签名额尚未确定。"
        with self.assertRaisesRegex(ValueError, "STALE"):
            api.prepare_request(self.bundle, "D2_ARM", self.envelope)

    def test_explicit_entries_and_envelope_rules(self):
        for entry, envelope in (("AUTO", None), ("STAGED_CORE_PEERS", None),
                                ("D1_EFFECTS", self.envelope), ("CLUSTER_ARM", self.envelope)):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                api.prepare_request(self.bundle, entry, envelope)

    def test_research_metadata_not_in_request(self):
        self.bundle["research_reference"] = {"gold_status": "PRIVATE_GOLD_SENTINEL"}
        self.bundle["science_packet"] = "PRIVATE_SCIENCE_SENTINEL"
        r = api.prepare_request(self.bundle, "D2_ARM", self.envelope)
        self.assertNotIn("PRIVATE_GOLD_SENTINEL", r["user"])
        self.assertNotIn("PRIVATE_SCIENCE_SENTINEL", r["user"])
        self.assertIn(self.bundle["question_slots"]["q1"], r["user"])

    def test_provider_errors_do_not_retry(self):
        class Provider:
            calls = 0
            def generate_json(self, **kwargs):
                self.calls += 1
                raise TimeoutError("synthetic")
        provider = Provider()
        with self.assertRaises(TimeoutError):
            api.read_once(self.bundle, provider, "D2_ARM", self.envelope)
        self.assertEqual(provider.calls, 1)

    def test_recorded_provider_called_once_without_granting_science(self):
        raw = self.raw
        class Provider:
            calls = 0
            def generate_json(self, **kwargs):
                self.calls += 1
                return deepcopy(raw)
        provider = Provider()
        r = api.read_once(self.bundle, provider, "D2_ARM", self.envelope, contract="legacy-v0551")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(r["state"], "REVIEW_REQUIRED")

    def test_text_variant_preserves_history_and_requires_new_reading(self):
        text = "这次只看unit_017站点。\n该站点自己使用情况尚未决定，若一家邻站用了系统，平均延误多少？"
        before = deepcopy(self.bundle)
        variant = api.goal_variant(self.bundle, text)
        self.assertEqual(self.bundle, before)
        self.assertEqual(variant["tables"], before["tables"])
        self.assertEqual(variant["documents"]["study_protocol.md"], before["documents"]["study_protocol.md"])
        self.assertNotEqual(variant["question_slots"], before["question_slots"])
        self.assertEqual(variant["revision_kind"], "DEVELOPMENT_GOAL_VARIANT")
        api.prepare_request(variant, "D2_ARM", self.envelope)

    def test_default_entry_uses_separate_intent_contract(self):
        from tests_gateway.test_business_question_intent_base import split
        raw = split(self.bundle, self.raw, '水平')
        result = api.preview(self.bundle, raw, 'D2_ARM', self.envelope)
        self.assertEqual(result['version'], 'business-question-intent-v0.56.1')
        self.assertEqual(result['state'], 'REVIEW_REQUIRED')
        self.assertFalse(result['core_called'])
        self.assertIn('intents', json.loads(api.prepare_request(self.bundle, 'D2_ARM', self.envelope)['user'])['output_schema']['properties'])

    def test_cli_preserves_earlier_outputs(self):
        with tempfile.TemporaryDirectory(dir=KIT, prefix="test-output-") as tmp:
            self.assertEqual(Path(tmp).resolve().parent, KIT.resolve())
            out = Path(tmp) / "result.json"
            out.write_text("earlier result", encoding="utf8")
            with self.assertRaises(SystemExit) as ctx:
                api.main(["preview", "--entry", "D2_ARM", "--bundle", str(KIT / "public/positive_bundle.json"),
                          "--envelope", str(KIT / "recorded/study_envelope.json"),
                          "--candidate", str(KIT / "recorded/positive_candidate.json"), "--output", str(out)])
            self.assertEqual(ctx.exception.code, 2)
            self.assertEqual(out.read_text(encoding="utf8"), "earlier result")


if __name__ == "__main__":
    unittest.main()
