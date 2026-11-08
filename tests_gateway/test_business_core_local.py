from copy import deepcopy
import unittest
from evaluation.business_core_cases import fixtures
from evaluation.business_core_local import canonical_singleton_mean, evaluate_draft
from tests_gateway.test_business_core_pilot import readable_reference
from tests_gateway.test_business_core_source_refs import reference_ids


class SingletonMeanTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures()[1]
        self.raw = reference_ids(self.case["business_question"],
                                 readable_reference(self.case["offline_reference_draft"]))

    def test_exact_singleton_equivalence_reaches_same_certificate(self):
        args = self.case["business_question"], self.raw, self.case["packet"]
        a = evaluate_draft(*args, synthetic_protocol_selected=True)
        changed = deepcopy(self.raw)
        changed["targets"][0]["aggregation"] = "equal_mean"
        b = evaluate_draft(self.case["business_question"], changed, self.case["packet"],
                           synthetic_protocol_selected=True)
        self.assertEqual(a["results"], b["results"])
        self.assertEqual(len(b["exact_equivalences_applied"]), 1)
        self.assertTrue(b["results"][0]["certificate_replay"])
        self.assertFalse(b["source_reference_precision_verified"])
        self.assertEqual(changed["targets"][0]["aggregation"], "equal_mean")

    def test_unknown_population_or_aggregation_not_invented(self):
        for updates in ({"nodes": None}, {"aggregation": None}, {"nodes": []}):
            raw = deepcopy(self.raw)
            raw["targets"][0].update(updates)
            result = evaluate_draft(self.case["business_question"], raw, self.case["packet"],
                                    synthetic_protocol_selected=True)
            self.assertEqual(result["results"][0]["status"], "NEEDS_INPUT")
            self.assertEqual(result["exact_equivalences_applied"], [])

    def test_multiple_or_duplicate_nodes_never_collapse(self):
        for nodes in (["01", "02"], ["01", "01"]):
            numeric = deepcopy(self.case["offline_reference_draft"])
            numeric["targets"][0].update(nodes=nodes, aggregation="equal_mean")
            projected, changes = canonical_singleton_mean(numeric)
            self.assertEqual(projected, numeric)
            self.assertEqual(changes, [])

    def test_no_scientific_information_is_added_by_equivalence(self):
        packet = deepcopy(self.case["packet"])
        packet["science"]["population_information"] = None
        raw = deepcopy(self.raw)
        raw["targets"][0]["aggregation"] = "equal_mean"
        result = evaluate_draft(self.case["business_question"], raw, packet, synthetic_protocol_selected=True)
        self.assertEqual(result["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(result["results"][0]["core_called"])


if __name__ == "__main__":
    unittest.main()
