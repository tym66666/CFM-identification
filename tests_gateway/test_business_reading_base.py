from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from evaluation.business_core_cases import fixtures
from evaluation.business_core_pilot_base import ModelDraft, target_coordinates
from evaluation.business_reading_base import project, evaluate_draft, make_request
from tests_gateway.test_business_core_branches import branch_reference


def reading_reference(case):
    """Offline fixture construction only. Never imported by the request runner."""
    old = branch_reference(case)
    questions = {}
    units = old["study"]["units"]
    def selection(nodes):
        return {"selection": "全体", "ids": []} if len(nodes) == units else (
            {"selection": "无人", "ids": []} if not nodes else {"selection": "指定", "ids": nodes})
    for t in old["targets"]:
        def scenario(s):
            if s is None:
                return None
            return dict(setting="局部条件", own="开通" if s["own"] else "不开通",
                        neighbors={"more_than_half": "超过一半", "at_most_half": "至多一半",
                                   "at_least_one": "至少一个", "none": "一个也没有",
                                   "exact_count": "恰好人数"}[s["peer_relation"]],
                        neighbor_count=s["peer_count"], source=s["source"],
                        remaining_source=t["remaining_source"])
        questions[t["question_source"]] = dict(
            operation="差值" if t["kind"] == "comparison" else "水平",
            population=selection(t["nodes"]),
            aggregation="单个" if len(t["nodes"]) == 1 else "等权平均",
            population_source=t["population_source"],
            first=(dict(setting="完整安排", treated=selection(t["treated_nodes"]), source=t["plan_source"])
                   if t["kind"] == "fixed_plan" else scenario(t["situation"])),
            second=scenario(t.get("reference")), unresolved=[])
    return {"study": old["study"], "questions": questions}


class BusinessReadingTests(unittest.TestCase):
    def setUp(self):
        self.cases = fixtures()

    def evaluate(self, i, mutate=None):
        case = self.cases[i]
        raw = reading_reference(case)
        if mutate:
            mutate(raw)
        return evaluate_draft(case["business_question"], raw, case["packet"],
                              synthetic_protocol_selected=True)

    def test_all_six_reach_existing_core_and_replay(self):
        for i, case in enumerate(self.cases):
            with self.subTest(case=case["case_id"]):
                raw = reading_reference(case)
                before = deepcopy(raw)
                numeric, _ = project(case["business_question"], raw)
                self.assertEqual(raw, before)
                self.assertEqual(
                    [target_coordinates(t) for t in ModelDraft.model_validate(numeric).targets],
                    [target_coordinates(t) for t in ModelDraft.model_validate(case["offline_reference_draft"]).targets])
                outcome = self.evaluate(i)
                expected = "UNSUPPORTED" if i == 3 else "POINT"
                for row in outcome["results"]:
                    self.assertEqual(row["status"], expected)
                    self.assertTrue(row["core_called"])
                    self.assertEqual(row["certificate_replay"], expected == "POINT")

    def test_missing_and_extra_questions_block_before_core(self):
        for extra in (True, False):
            def change(r):
                if extra:
                    r["questions"]["s999"] = deepcopy(next(iter(r["questions"].values())))
                else:
                    r["questions"].pop(next(iter(r["questions"])))
            result = self.evaluate(0, change)
            self.assertEqual(result["status"], "REVIEW_REQUIRED")
            self.assertEqual(result["results"], [])

    def test_model_object_key_order_does_not_change_difference_order(self):
        c = self.cases[0]
        r = reading_reference(c)
        first, _ = project(c["business_question"], r)
        r["questions"] = dict(reversed(list(r["questions"].items())))
        second, _ = project(c["business_question"], r)
        self.assertEqual(first, second)

    def test_complete_arrangement_with_local_fields_is_rejected(self):
        result = self.evaluate(2, lambda r: next(iter(r["questions"].values()))["first"].update(own="开通"))
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["results"], [])

    def test_missing_population_not_filled_from_company_size(self):
        result = self.evaluate(2, lambda r: next(iter(r["questions"].values())).update(
            population={"selection": "不明确", "ids": []}))
        self.assertEqual(result["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(result["results"][0]["core_called"])

    def test_remaining_randomization_not_assumed(self):
        result = self.evaluate(1, lambda r: next(iter(r["questions"].values()))["first"].update(remaining_source=None))
        self.assertEqual(result["results"][0]["status"], "NEEDS_INPUT")
        self.assertFalse(result["results"][0]["core_called"])

    def test_nonexistent_source_rejected(self):
        result = self.evaluate(2, lambda r: next(iter(r["questions"].values()))["first"].update(source="s999"))
        self.assertEqual(result["status"], "REJECTED")

    def test_all_and_subset_are_not_silently_coerced(self):
        result = self.evaluate(2, lambda r: next(iter(r["questions"].values()))["population"].update(ids=["01"]))
        self.assertEqual(result["reason_code"], "NON_LIST_SELECTION_WITH_IDS")

    def test_study_conflict_does_not_fall_back_to_packet(self):
        result = self.evaluate(2, lambda r: r["study"].update(probability="1/3"))
        self.assertEqual(result["reason_code"], "STUDY_READING_CONFLICTS_WITH_PROTOCOL")
        self.assertEqual(result["results"], [])

    def test_missing_science_and_no_selection_do_not_admit(self):
        c = deepcopy(self.cases[2])
        r = reading_reference(c)
        result = evaluate_draft(c["business_question"], r, c["packet"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        c["packet"]["science"]["population_information"] = ""
        result = evaluate_draft(c["business_question"], r, c["packet"], synthetic_protocol_selected=True)
        self.assertFalse(result["results"][0]["core_called"])

    def test_wrong_exposure_semantics_not_converted_to_supported_state(self):
        result = self.evaluate(1, lambda r: next(iter(r["questions"].values()))["first"].update(
            neighbors="至少一个", neighbor_count=None))
        self.assertEqual(result["reason_code"], "PEER_RELATION_CONFLICTS_WITH_EXPOSURE")

    def test_extra_baseline_not_silently_discarded(self):
        def change(r):
            q = next(iter(r["questions"].values()))
            q["second"] = deepcopy(q["first"])
        result = self.evaluate(2, change)
        self.assertEqual(result["reason_code"], "LEVEL_WITH_EXTRA_SCENARIO")

    def test_unsupported_policy_contrast_is_not_a_fake_point(self):
        def change(r):
            q = next(iter(r["questions"].values()))
            q["operation"] = "差值"
            q["second"] = deepcopy(q["first"])
            q["second"]["treated"] = {"selection": "无人", "ids": []}
        result = self.evaluate(2, change)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertFalse(result["candidate_generator_called"])
        self.assertFalse(result["nonidentification_proven"])

    def test_request_has_no_reference_or_route_and_does_not_call_core(self):
        c = self.cases[0]
        with patch("evaluation.business_reading_base.evaluate_core", side_effect=AssertionError):
            _, user = make_request(c["business_question"])
        payload = json.loads(user)
        self.assertEqual(set(payload), {"business_question", "source_catalog", "question_slots",
                                       "study_schema", "output_contract"})
        self.assertEqual(len(payload["question_slots"]), 2)
        self.assertNotIn("R1A", user)
        self.assertNotIn("offline_reference", user)


if __name__ == "__main__":
    unittest.main()
