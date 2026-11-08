from copy import deepcopy
import unittest
from unittest.mock import patch
from evaluation.business_core_cases import fixtures
from evaluation.business_core_coverage_guard import evaluate_draft
from tests_gateway.test_business_core_branches import branch_reference


class CoverageGuardTests(unittest.TestCase):
    def test_extra_or_missing_questions_hold_before_core(self):
        c = fixtures()[0]
        good = branch_reference(c)
        for targets in (good["targets"][:1], good["targets"] + [deepcopy(good["targets"][0])]):
            raw = {**good, "targets": targets}
            with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
                result = evaluate_draft(c["business_question"], raw, c["packet"],
                                        synthetic_protocol_selected=True)
                self.assertEqual(result["status"], "REVIEW_REQUIRED")
                self.assertEqual(result["results"], [])
                core.assert_not_called()

    def test_invalid_branch_has_structured_rejection_before_core(self):
        c = fixtures()[1]
        raw = branch_reference(c)
        raw["targets"][0]["nodes"] = ["01", "02"]
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            result = evaluate_draft(c["business_question"], raw, c["packet"],
                                    synthetic_protocol_selected=True)
            self.assertEqual(result["reason_code"], "TARGET_BRANCH_CONTRACT_INVALID")
            core.assert_not_called()

    def test_valid_comparisons_still_replay_and_no_real_approval(self):
        c = fixtures()[0]
        result = evaluate_draft(c["business_question"], branch_reference(c), c["packet"],
                                synthetic_protocol_selected=True)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(q["certificate_replay"] for q in result["results"]))
        self.assertFalse(result["production_admission"])


if __name__ == "__main__":
    unittest.main()
