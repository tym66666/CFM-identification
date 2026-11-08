from copy import deepcopy
import unittest
from unittest.mock import patch

from evaluation.business_core_cases import fixtures
from evaluation.business_core_pilot import numeric_projection, evaluate_draft


def readable_reference(numeric):
    raw = deepcopy(numeric)
    for t in raw["targets"]:
        for key in ("situation", "reference"):
            s = t[key]
            if s is None:
                continue
            code = s.pop("peers")
            exposure = raw["study"]["exposure"]
            if exposure == "strict_majority":
                s.update(peer_relation="more_than_half" if code else "at_most_half", peer_count=None)
            elif exposure == "any_treated_neighbor":
                s.update(peer_relation="at_least_one" if code else "none", peer_count=None)
            else:
                s.update(peer_relation="exact_count", peer_count=code)
    return raw


class ReadablePeerTests(unittest.TestCase):
    def setUp(self):
        self.cases = fixtures()

    def test_semantic_relations_recover_all_frozen_coordinates(self):
        for c in self.cases:
            with self.subTest(name=c["case_id"]):
                expected = c["offline_reference_draft"]
                self.assertEqual(numeric_projection(readable_reference(expected)), expected)

    def test_majority_is_a_state_not_neighbor_count(self):
        raw = readable_reference(self.cases[0]["offline_reference_draft"])
        projected = numeric_projection(raw)
        self.assertEqual(projected["targets"][0]["situation"]["peers"], 1)
        self.assertEqual(projected["targets"][1]["reference"]["peers"], 0)
        raw["targets"][0]["situation"]["peer_count"] = 2
        with self.assertRaises(ValueError):
            numeric_projection(raw)

    def test_exact_count_is_not_collapsed_to_any(self):
        c = self.cases[1]
        raw = readable_reference(c["offline_reference_draft"])
        raw["targets"][0]["situation"]["peer_relation"] = "at_least_one"
        raw["targets"][0]["situation"]["peer_count"] = None
        with self.assertRaises(ValueError):
            numeric_projection(raw)

    def test_still_blocks_spliced_quote_without_rewriting_it(self):
        c = self.cases[0]
        raw = readable_reference(c["offline_reference_draft"])
        raw["targets"][1]["reference"]["quote"] = "自己都没有AI权限时，……邻居中至多一半有权限"
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            result = evaluate_draft(c["business_question"], raw, c["packet"],
                                    synthetic_protocol_selected=True)
            self.assertEqual(result["status"], "REJECTED")
            core.assert_not_called()

    def test_new_mock_interface_reaches_actual_core_and_replay(self):
        c = self.cases[0]
        result = evaluate_draft(c["business_question"], readable_reference(c["offline_reference_draft"]),
                                c["packet"], synthetic_protocol_selected=True)
        self.assertEqual([r["core"]["route"] for r in result["results"]],
                         ["R1A_COMPOSITION", "R1A_COMPOSITION"])
        self.assertTrue(all(r["certificate_replay"] for r in result["results"]))

    def test_explicit_selection_still_required(self):
        c = self.cases[0]
        result = evaluate_draft(c["business_question"], {}, c["packet"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
