from copy import deepcopy
import unittest

from evaluation.business_core_cases import fixtures
from evaluation.business_reading import evaluate_draft, project
from tests_gateway.test_business_reading_provenance import reference as old_reference


def reference(case):
    r = old_reference(case)
    for q in r["questions"].values():
        q.pop("unresolved")
    return r


class CoordinateOnlyTests(unittest.TestCase):
    def test_six_complete_targets_still_run_existing_core(self):
        for i, c in enumerate(fixtures()):
            with self.subTest(case=c["case_id"]):
                raw = reference(c)
                original = deepcopy(raw)
                result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
                self.assertEqual(raw, original)
                self.assertTrue(all(r["core_called"] for r in result["results"]))
                self.assertEqual(result["results"][0]["status"], "UNSUPPORTED" if i == 3 else "POINT")
                self.assertTrue(all(r["certificate_replay"] for r in result["results"] if r["status"] == "POINT"))

    def test_old_concern_field_is_rejected_not_dropped(self):
        c = fixtures()[4]
        raw = old_reference(c)
        next(iter(raw["questions"].values()))["unresolved"] = ["需要具体总体均值"]
        result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(result["reason_code"], "OLD_FREE_TEXT_GATE_NOT_ACCEPTED")
        self.assertEqual(result["results"], [])

    def test_unknown_coordinates_still_stop_before_core(self):
        c = fixtures()[1]
        mutations = [
            lambda q: q.update(population={"selection": "不明确", "ids": []}),
            lambda q: q.update(aggregation="不明确"),
            lambda q: q.update(first=None),
            lambda q: q["first"].update(own="不明确"),
            lambda q: q["first"].update(neighbors="不明确"),
            lambda q: q["first"].update(remaining_source=None),
        ]
        for change in mutations:
            raw = reference(c)
            change(next(iter(raw["questions"].values())))
            result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(result["results"][0]["status"], "NEEDS_INPUT")
            self.assertFalse(result["results"][0]["core_called"])

    def test_no_science_or_selection_does_not_become_admitted(self):
        c = deepcopy(fixtures()[4])
        raw = reference(c)
        result = evaluate_draft(c["business_question"], raw, c["packet"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        c["packet"]["science"]["population_information"] = ""
        result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertFalse(result["results"][0]["core_called"])

    def test_missing_second_scenario_is_not_assumed(self):
        c = fixtures()[0]
        raw = reference(c)
        next(iter(raw["questions"].values()))["second"] = None
        numeric, _ = project(c["business_question"], raw)
        self.assertIn("SECOND_SCENARIO_MISSING", numeric["targets"][0]["unresolved"])
        result = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertFalse(result["results"][0]["core_called"])


if __name__ == "__main__":
    unittest.main()
