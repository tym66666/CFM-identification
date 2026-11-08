"""Incomplete acceptance records must never be reported as identification passes."""
import unittest
from evaluation.nbib_acceptance import classify_attempt


class AcceptanceEvidenceTests(unittest.TestCase):
    def row(self, **changes):
        return dict(dict(track="SYNTHETIC_REGRESSION", transport_complete=True,
                         contract_passed=True, query_count=1, semantic_passed=True,
                         expected_decision_passed=True), **changes)

    def test_missing_point_evidence_is_unscored(self):
        self.assertEqual(classify_attempt(self.row(), 1), "IDENTIFICATION_EVIDENCE_NOT_SCORED")

    def test_non_boolean_point_flag_cannot_skip_replay(self):
        for value in (None, 0, 1, "true", "false", []):
            with self.subTest(value=value):
                self.assertEqual(classify_attempt(self.row(point_present=value), 1),
                                 "IDENTIFICATION_EVIDENCE_NOT_SCORED")

    def test_query_count_requires_integer_not_boolean_or_float(self):
        for count in (True, 1.0, "1", None):
            row = self.row(point_present=False)
            row["query_count"] = count
            with self.subTest(count=count):
                self.assertEqual(classify_attempt(row, 1), "QUERY_COVERAGE_FAILURE")

    def test_explicit_nonpoint_and_replayed_point_remain_valid(self):
        self.assertEqual(classify_attempt(self.row(point_present=False), 1), "PASS")
        self.assertEqual(classify_attempt(self.row(point_present=True, point_replay_passed=True), 1), "PASS")
        self.assertEqual(classify_attempt(self.row(point_present=True), 1), "CERTIFICATE_FAILURE")

    def test_raw_semantic_pass_never_requires_or_claims_point(self):
        row = self.row()
        row["track"] = "NBIB_RAW"
        self.assertEqual(classify_attempt(row, 1), "BUSINESS_SEMANTICS_PASS_ONLY")


if __name__ == "__main__":
    unittest.main()
