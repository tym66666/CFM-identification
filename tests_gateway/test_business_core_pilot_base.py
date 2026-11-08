from copy import deepcopy
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from evaluation.business_core_cases import fixtures
from evaluation.business_core_pilot_base import evaluate_draft, make_request, target_coordinates, ModelDraft
from cfm_id_llm.providers.mock import MockProvider


class BusinessCorePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["case_id"]: c for c in fixtures()}

    def run_case(self, name="NBIB-007-R20", *, draft=None, packet=None, selected=True):
        c = self.cases[name]
        provider = MockProvider(draft or c["offline_reference_draft"])
        system, user = make_request(c["business_question"])
        raw = provider.generate_json(system_prompt=system, user_prompt=user)
        self.assertEqual(provider.calls, 1)
        return evaluate_draft(c["business_question"], raw, packet or c["packet"],
                              synthetic_protocol_selected=selected)

    def test_all_mock_inputs_reach_actual_expected_routes(self):
        expected = {
            "NBIB-001-R20": ["R1A_COMPOSITION", "R1A_COMPOSITION"],
            "NBIB-002-R20": ["R1A_RANDOMIZED_ARM"],
            "NBIB-007-R20": ["R1B_FULL_ASSIGNMENT"],
            "NBIB-008-R20": [None],
            "NBIB-009-R20": ["R2_MEAN_SIGNATURE"],
            "NBIB-007-R20-PARTIAL": ["R1B_FULL_ASSIGNMENT"],
        }
        for name, routes in expected.items():
            with self.subTest(name=name):
                r = self.run_case(name)
                self.assertEqual(len(r["results"]), len(routes))
                for row, route in zip(r["results"], routes):
                    self.assertTrue(row["core_called"])
                    self.assertEqual(row["core"]["route"], route)
                    self.assertEqual(row["status"], "POINT" if route else "UNSUPPORTED")
                    self.assertEqual(row["certificate_replay"], bool(route))
                self.assertFalse(r["production_admission"])
                self.assertFalse(r["semantic_correctness_verified"])

    def test_unselected_fixture_cannot_call_core(self):
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            self.assertEqual(self.run_case(selected=False)["status"], "REVIEW_REQUIRED")
            core.assert_not_called()

    def test_model_cannot_supply_scientific_approval(self):
        d = deepcopy(self.cases["NBIB-007-R20"]["offline_reference_draft"])
        d["a4_admitted"] = True
        with self.assertRaises(ValidationError):
            self.run_case(draft=d)

    def test_finite_sample_does_not_become_population_information(self):
        p = deepcopy(self.cases["NBIB-007-R20"]["packet"])
        p["science"]["population_information"] = None
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            r = self.run_case(packet=p)
            self.assertEqual(r["results"][0]["status"], "NEEDS_INPUT")
            core.assert_not_called()

    def test_removing_r2_assumption_removes_point(self):
        p = deepcopy(self.cases["NBIB-009-R20"]["packet"])
        p["science"]["mean_signature_sufficiency"] = None
        r = self.run_case("NBIB-009-R20", packet=p)
        self.assertEqual(r["results"][0]["status"], "UNSUPPORTED")
        self.assertFalse(r["candidate_generator_called"])
        self.assertFalse(r["nonidentification_proven"])

    def test_design_misreading_cannot_reach_core(self):
        d = deepcopy(self.cases["NBIB-007-R20"]["offline_reference_draft"])
        d["study"].update(design="fixed_count", probability=None, quota=7)
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            self.assertEqual(self.run_case(draft=d)["reason_code"], "STUDY_READING_CONFLICTS_WITH_PROTOCOL")
            core.assert_not_called()

    def test_invented_quote_rejected(self):
        d = deepcopy(self.cases["NBIB-007-R20"]["offline_reference_draft"])
        d["targets"][0]["question_quote"] = "不存在的业务问题"
        self.assertEqual(self.run_case(draft=d)["status"], "REJECTED")

    def test_mismatched_aggregation_held(self):
        d = deepcopy(self.cases["NBIB-007-R20"]["offline_reference_draft"])
        d["targets"][0]["aggregation"] = "single"
        self.assertEqual(self.run_case(draft=d)["results"][0]["status"], "NEEDS_INPUT")

    def test_missing_remaining_not_inferred(self):
        d = deepcopy(self.cases["NBIB-002-R20"]["offline_reference_draft"])
        d["targets"][0].update(remaining=None, remaining_quote=None)
        r = self.run_case("NBIB-002-R20", draft=d)
        self.assertEqual(r["results"][0]["reason_code"], "REMAINING_ALLOCATION_UNRESOLVED")
        self.assertFalse(r["results"][0]["core_called"])

    def test_fixed_target_is_read_from_model_not_case_id(self):
        a = self.run_case()["results"][0]["core"]
        b = self.run_case("NBIB-007-R20-PARTIAL")["results"][0]["core"]
        self.assertNotEqual(a["identification"]["target_fingerprint"], b["identification"]["target_fingerprint"])
        self.assertEqual(b["identification"]["fixed_policy_treatment"], [1, 1] + [0] * 12)

    def test_known_support_is_exact_and_is_not_an_effect_estimate(self):
        r = self.run_case("NBIB-002-R20")["results"][0]["core"]["identification"]
        self.assertEqual(r["certificate"]["joint_arm_support_probability"], "12/47")
        self.assertIsNone(r["estimation_request"])

    def test_unknown_node_and_boolean_treatment_are_rejected(self):
        d = deepcopy(self.cases["NBIB-007-R20"]["offline_reference_draft"])
        d["targets"][0]["treated_nodes"] = ["999"]
        self.assertEqual(self.run_case(draft=d)["results"][0]["status"], "NEEDS_INPUT")
        d = deepcopy(self.cases["NBIB-002-R20"]["offline_reference_draft"])
        d["targets"][0]["situation"]["own"] = True
        with self.assertRaises(ValidationError):
            self.run_case("NBIB-002-R20", draft=d)

    def test_replay_failure_is_fatal(self):
        with patch("pfn_pipeline.identification_business.replay_verified_business_outcome", return_value=False):
            with self.assertRaises(RuntimeError):
                self.run_case()

    def test_optimization_has_no_automatic_candidate_answer(self):
        d = deepcopy(self.cases["NBIB-007-R20"]["offline_reference_draft"])
        t = d["targets"][0]
        t.update(kind="optimization", treated_nodes=None, plan_quote=None)
        r = self.run_case(draft=d)
        self.assertEqual(r["results"][0]["reason_code"], "POLICY_OPTIMIZATION_OUTSIDE_IDENTIFICATION")
        self.assertFalse(r["results"][0]["core_called"])
        self.assertFalse(r["candidate_generator_called"])

    def test_prompt_has_only_public_text_and_schema(self):
        import json
        c = self.cases["NBIB-007-R20"]
        _, user = make_request(c["business_question"])
        payload = json.loads(user)
        self.assertEqual(set(payload), {"business_question", "output_schema"})
        self.assertNotIn("R1B", user)
        self.assertNotIn("offline_reference", user)


if __name__ == "__main__":
    unittest.main()
