import json
import unittest
from pydantic import ValidationError
from examples.materials_candidate_fixture import load_case, synthetic_context
from tests_gateway.test_business_candidate_base import RecordingMock
from evaluation import business_candidate_identifiers as current
from evaluation.candidate_presentation import render_zh


class ExactCandidateRequestTests(unittest.TestCase):
    def run_case(self, provider=None):
        item = load_case()
        p = provider or RecordingMock()
        r = current.evaluate_with_candidates(item["bundle"], item["raw"], item["packet"],
            context=synthetic_context(item), provider=p, enable_candidates=True,
            synthetic_protocol_selected=True)
        return r, p

    def test_schema_constrains_reviewed_operator_and_level_pair(self):
        _, p = self.run_case()
        head, tail = p.calls[0][1].split(current.SCHEMA_MARKER)
        schema, end = json.JSONDecoder().raw_decode(tail)
        permitted = schema["$defs"]["CandidateA4UseV03"]["allOf"][0]["then"]["anyOf"]
        self.assertEqual(permitted, [{"properties": {"operator": {"const": "NODE_FULL_LAW"},
            "level": {"const": "NODE_FULL_LAW"}}, "required": ["operator", "level"]}])
        extra = json.loads(tail[end:].rsplit("\n", 1)[1])
        self.assertEqual(extra["target_assignment"], [1,1,1,0,0,0]*4)

    def test_descriptive_operator_still_rejected_not_auto_repaired(self):
        def bad(d):
            d["proposal"]["a4_used"] = dict(source="REVIEWED_OPERATOR", level="NODE_FULL_LAW",
                                            operator="NODE_FULL_LAW: explanation")
        r, _ = self.run_case(RecordingMock(bad))
        self.assertEqual(r["candidate_results"][0]["status"], "REJECTED_UNSAFE_OUTPUT")

    def test_presentation_retains_unsupported_and_unverified(self):
        r, _ = self.run_case()
        text = render_zh(r)
        self.assertIn("当前识别库未覆盖", text)
        self.assertIn("未验证，不构成识别证明", text)
        self.assertNotIn("Core 证书已重放", text)

    def test_presentation_rejects_forged_candidate_certificate(self):
        r, _ = self.run_case()
        r["candidate_results"][0]["mathematical_certificate"] = "FORGED"
        with self.assertRaises(ValidationError):
            render_zh(r)


if __name__ == "__main__":
    unittest.main()
