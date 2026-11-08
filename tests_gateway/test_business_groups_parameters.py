from copy import deepcopy
import unittest
from unittest.mock import patch

from evaluation.business_groups_cases import fixtures
from evaluation.business_groups_parameters import evaluate_draft, project


class EmptyInactiveParameterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["case_id"]: c for c in fixtures()}

    def run_case(self, cid, raw):
        c = self.cases[cid]
        return evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)

    def test_empty_inactive_vectors_preserve_target_and_design(self):
        for cid, field in (("D3-effects", "probabilities"), ("D4-arm", "quotas")):
            c = self.cases[cid]
            raw = deepcopy(c["reading_reference"])
            raw["study"][field] = [None] * len(raw["study"]["groups"])
            original = deepcopy(raw)
            numeric, changes = project(c["business_question"], raw)
            expected, _ = project(c["business_question"], c["reading_reference"])
            self.assertEqual(numeric, expected)
            self.assertEqual(raw, original)
            self.assertEqual(changes[0]["field"], field)
            result = self.run_case(cid, raw)
            self.assertTrue(all(r["status"] == "POINT" and r["certificate_replay"] for r in result["results"]))

    def test_nonempty_inactive_parameters_are_rejected(self):
        for cid, field, value in (("D3-effects", "probabilities", ["1/2", "1/4"]),
                                  ("D4-arm", "quotas", [1, None, None, None])):
            raw = deepcopy(self.cases[cid]["reading_reference"])
            raw["study"][field] = value
            r = self.run_case(cid, raw)
            self.assertEqual(r["status"], "REJECTED")

    def test_wrong_length_or_empty_list_is_not_an_equivalence(self):
        for cid, field in (("D3-effects", "probabilities"), ("D4-arm", "quotas")):
            for value in ([], [None], [None] * 7):
                raw = deepcopy(self.cases[cid]["reading_reference"])
                raw["study"][field] = value
                self.assertEqual(self.run_case(cid, raw)["status"], "REJECTED")

    def test_active_null_entries_remain_missing(self):
        for cid, field in (("D3-effects", "quotas"), ("D4-arm", "probabilities")):
            raw = deepcopy(self.cases[cid]["reading_reference"])
            raw["study"][field] = [None] * len(raw["study"]["groups"])
            with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
                r = self.run_case(cid, raw)
                self.assertEqual(r["status"], "NEEDS_INPUT")
                core.assert_not_called()

    def test_every_original_mock_decision_is_preserved(self):
        from evaluation.business_groups_base import evaluate_draft as old
        for c in self.cases.values():
            new = self.run_case(c["case_id"], c["reading_reference"])
            previous = old(c["business_question"], c["reading_reference"], c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(new["status"], previous["status"])
            self.assertEqual(new["results"], previous["results"])


if __name__ == "__main__":
    unittest.main()
