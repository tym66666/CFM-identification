"""Regression checks for the opt-in prompt; mocks are not LLM accuracy tests."""
from copy import deepcopy
from fractions import Fraction
import json
import unittest
from unittest.mock import Mock, patch

from cfm_id import fixed_reading_clarity as clarity
from cfm_id import question_bound_assignment as original
from cfm_id.source_locations import build_catalog
from examples.bounded_policy_intake_fixture import make_case


def without_descriptions(value):
    if isinstance(value, dict):
        return {k: without_descriptions(v) for k, v in value.items() if k != "description"}
    if isinstance(value, list):
        return [without_descriptions(v) for v in value]
    return value


class FixedReadingClarityTests(unittest.TestCase):
    def setUp(self):
        self.nodes = ["北区组", "南区组", "东区组", "西区组"]
        self.edges = [("北区组", "南区组"), ("南区组", "东区组")]

    def fixture(self, policy=None, population=None):
        return make_case(
            self.nodes, self.edges, 2,
            [1] * 4 if policy is None else policy,
            self.nodes if population is None else population,
        )

    def read(self, bundle, raw):
        provider = Mock()
        provider.generate_json.return_value = deepcopy(raw)
        before = deepcopy(raw)
        with patch("cfm_id_bridge.bridge.identify_network_business_query",
                   side_effect=AssertionError("reading called bridge")), \
             patch("pfn_pipeline.identification_business.identify_network_business_query",
                   side_effect=AssertionError("reading called Core")), \
             patch("cfm_id.bounded_policy_solver.solve",
                   side_effect=AssertionError("reading called bounded solver")):
            result = clarity.read_once(bundle, provider)
        provider.generate_json.assert_called_once_with(
            system_prompt=clarity.make_request(bundle)[0],
            user_prompt=clarity.make_request(bundle)[1],
        )
        self.assertEqual(raw, before)
        self.assertEqual(result["reading_candidate"], raw)
        for flag in ("core_called", "production_admission", "estimation_called",
                     "policy_called", "estimation_handoff_allowed"):
            self.assertFalse(result.get(flag, False), flag)
        self.assertEqual(result.get("candidate_model_calls", 0), 0)
        self.assertNotIn(result["state"], ("POINT", "CORE_POINT", "PARTIAL"))
        return result

    def test_prompt_changes_descriptions_but_preserves_public_data_and_schema_contract(self):
        bundle, _, declaration, _, _ = self.fixture()
        snapshot = deepcopy(bundle)
        old_system, old_user = original.make_request(bundle)
        new_system, new_user = clarity.make_request(bundle)
        old, new = json.loads(old_user), json.loads(new_user)
        self.assertEqual(without_descriptions(old), without_descriptions(new))
        self.assertEqual(bundle, snapshot)
        self.assertEqual(clarity.make_request(bundle), (new_system, new_user))
        self.assertEqual(original.make_request(bundle), (old_system, old_user))
        self.assertNotIn(clarity.AMBIGUOUS_RULE, new_system)
        self.assertIn(clarity.USAGE_RULE, new_system)
        self.assertIn("reading与reported_assignment是同级字段", new_system)
        for field in ("first", "second", "population"):
            self.assertIn("description", new["output_schema"]["$defs"]["Conditions"]["properties"][field])
        self.assertEqual(set(new["output_schema"]["properties"]), {"reading", "reported_assignment"})
        self.assertFalse(new["output_schema"]["additionalProperties"])
        self.assertFalse(new["output_schema"]["properties"]["reading"]["additionalProperties"])
        public_request = new_system + new_user
        for private in (declaration["information"]["source_id"], "condition_decisions",
                        "reviewed_business_target", "Independent hypothetical protocol"):
            self.assertNotIn(private, public_request)

    def test_complete_all_and_mixed_arrangements_do_not_follow_evaluation_subset(self):
        variants = [
            ([1, 1, 1, 1], self.nodes),
            ([1, 1, 1, 1], ["西区组"]),
            ([1, 0, 1, 0], ["南区组", "西区组"]),
            ([0, 0, 0, 0], ["东区组"]),
        ]
        for policy, population in variants:
            with self.subTest(policy=policy, population=population):
                bundle, raw, _, _, _ = self.fixture(policy, population)
                out = self.read(bundle, raw)
                self.assertEqual(out, original.preview(bundle, raw))
                self.assertEqual(out["state"], "REVIEW_REQUIRED")
                target = out["proposed_targets"]["q1"]
                self.assertEqual(target["assignment"], policy)
                self.assertEqual(target["unit_weights"], [
                    str(Fraction(1, len(population))) if n in population else "0"
                    for n in self.nodes
                ])
                self.assertFalse(out["question_binding"]["scientific_approval"])
                self.assertFalse(out["assignment_review"]["scientific_approval"])

    def test_unknown_usage_population_and_aggregation_are_never_recovered_from_other_fields(self):
        for missing in ("usage", "population", "aggregation"):
            with self.subTest(missing=missing):
                bundle, raw, _, _, _ = self.fixture(population=["西区组"])
                conditions = raw["reading"]["questions"]["q1"]
                if missing == "usage":
                    conditions["first"] = {
                        n: 1 if n == "西区组" else None for n in self.nodes
                    }
                elif missing == "population":
                    conditions["population"] = None
                else:
                    conditions["aggregation"] = "不明确"
                out = self.read(bundle, raw)
                self.assertEqual(out["state"], "NEEDS_INPUT")
                self.assertFalse(out.get("proposed_targets", {}))
                self.assertEqual(out, original.preview(bundle, raw))
                self.assertTrue(out["intent_condition_review"]["q1"]["missing_conditions"])

    def test_missing_original_assignment_does_not_erase_complete_target(self):
        bundle, raw, _, _, _ = self.fixture(population=["西区组"])
        raw["reported_assignment"].update(
            mechanism="NOT_FULLY_SPECIFIED", fixed_count=None, uniform_subset_declared=None,
        )
        out = self.read(bundle, raw)
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertEqual(out["proposed_targets"]["q1"]["assignment"], [1, 1, 1, 1])
        self.assertEqual(out["proposed_targets"]["q1"]["unit_weights"], ["0", "0", "0", "1"])

    def test_complete_comparison_is_not_changed_to_single_policy_level(self):
        bundle, raw, _, _, _ = self.fixture(population=["西区组"])
        goal = ("问题1：比较四组都使用和四组都不用辅助系统两种安排，"
                "只评价西区组，其平均按时完成率之差是多少？")
        bundle["documents"]["goal.txt"] = goal
        bundle["question_slots"]["q1"] = goal
        raw["reading"]["intents"]["q1"] = dict(
            kind="比较", question_id=original.question_catalog(bundle)["q1"]["question_id"])
        raw["reading"]["questions"]["q1"]["second"] = dict.fromkeys(self.nodes, 0)
        raw["reported_assignment"]["source_ids"] = [
            sid for sid, row in build_catalog(bundle["documents"]).items()
            if row["doc_id"] == "study.txt" and "原试点每轮" in row["text"]
        ]
        out = self.read(bundle, raw)
        self.assertEqual(out["state"], "UNSUPPORTED")
        self.assertEqual(out["reading_candidate"]["reading"]["intents"]["q1"]["kind"], "比较")
        self.assertEqual(out["reading_candidate"]["reading"]["questions"]["q1"]["second"],
                         dict.fromkeys(self.nodes, 0))
        self.assertFalse(out.get("proposed_targets", {}))

    def test_nested_assignment_and_extra_or_wrong_fields_are_rejected_without_repair(self):
        bundle, original_raw, _, _, _ = self.fixture()
        variants = []
        nested = deepcopy(original_raw)
        nested["reading"]["reported_assignment"] = nested.pop("reported_assignment")
        variants.append(nested)
        duplicate = deepcopy(original_raw)
        duplicate["reading"]["reported_assignment"] = deepcopy(duplicate["reported_assignment"])
        variants.append(duplicate)
        approval = deepcopy(original_raw)
        approval["scientific_approval"] = True
        variants.append(approval)
        unknown = deepcopy(original_raw)
        unknown["reading"]["questions"]["q1"]["first"]["额外对象"] = 1
        variants.append(unknown)
        dropped = deepcopy(original_raw)
        dropped["reading"]["questions"]["q1"]["first"].pop("北区组")
        variants.append(dropped)
        bad_id = deepcopy(original_raw)
        bad_id["reading"]["intents"]["q1"]["question_id"] = "question_" + "0" * 64
        variants.append(bad_id)
        for index, raw in enumerate(variants):
            with self.subTest(index=index):
                out = self.read(bundle, raw)
                self.assertEqual(out["state"], "CHECK_BLOCKED")
                self.assertEqual(out["reason_code"], "QUESTION_BOUND_READING_REJECTED")
                self.assertFalse(out.get("proposed_targets", {}))

    def test_provider_error_is_propagated_after_single_call_without_retry(self):
        bundle, _, _, _, _ = self.fixture()
        provider = Mock()
        provider.generate_json.side_effect = RuntimeError("synthetic transport failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic transport failure"):
            clarity.read_once(bundle, provider)
        provider.generate_json.assert_called_once()

    def test_base_prompt_drift_fails_before_dispatch(self):
        bundle, _, _, _, _ = self.fixture()
        system, user = original.make_request(bundle)
        for modified in (
            system.replace(clarity.AMBIGUOUS_RULE, ""),
            system + clarity.AMBIGUOUS_RULE,
        ):
            with self.subTest(modified=modified[-30:]):
                provider = Mock()
                with patch.object(original, "make_request", return_value=(modified, user)):
                    with self.assertRaisesRegex(ValueError, "EXPECTED_USAGE_RULE_CHANGED"):
                        clarity.read_once(bundle, provider)
                provider.generate_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()

