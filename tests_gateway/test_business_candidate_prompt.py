import unittest
from examples.materials_candidate_fixture import load_case, synthetic_context
from tests_gateway.test_business_candidate_base import RecordingMock
from evaluation import business_candidate_base as base
from evaluation import business_candidate_prompt as refined


class CandidateExplanationTests(unittest.TestCase):
    def test_only_system_explanation_changes_not_business_or_math_inputs(self):
        item = load_case()
        first, second = RecordingMock(), RecordingMock()
        opts = dict(context=synthetic_context(item), enable_candidates=True, synthetic_protocol_selected=True)
        r1 = base.evaluate_with_candidates(item["bundle"], item["raw"], item["packet"], provider=first, **opts)
        r2 = refined.evaluate_with_candidates(item["bundle"], item["raw"], item["packet"], provider=second, **opts)
        self.assertEqual(first.calls[0][1], second.calls[0][1])
        self.assertEqual(second.calls[0][0], first.calls[0][0] + refined.ADDITIONAL_RULES)
        self.assertEqual(r1["identification"], r2["identification"])
        self.assertEqual(r1["candidate_results"], r2["candidate_results"])
        self.assertEqual(r2["version"], refined.VERSION)
        self.assertFalse(r2["estimation_handoff_allowed"])

    def test_no_provider_no_new_call(self):
        item = load_case()
        r = refined.evaluate_with_candidates(item["bundle"], item["raw"], item["packet"],
            context=synthetic_context(item), enable_candidates=True, synthetic_protocol_selected=True)
        self.assertEqual(r["candidate_gate"], "CANDIDATE_PROVIDER_REQUIRED")
        self.assertFalse(r["candidate_generator_called"])


if __name__ == "__main__":
    unittest.main()
