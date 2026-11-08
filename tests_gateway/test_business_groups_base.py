from copy import deepcopy
from fractions import Fraction
from itertools import product, combinations
from math import comb
import json
import unittest
from unittest.mock import patch

from cfm_id_llm.providers.mock import MockProvider
from evaluation.business_groups_cases import fixtures
from evaluation.business_groups_base import (
    evaluate_draft, project, study_coordinates, GroupReading, make_request,
    NumericDraft, evaluate_numeric, _arm, _network)


def assignment_oracle(d):
    """Independent finite enumeration; no production support calculator."""
    groups = d["groups"]
    if d["design"] == "组内固定名额":
        choices = [list(combinations(g, q)) for g, q in zip(groups, d["quotas"])]
        denominator = 1
        for g, q in zip(groups, d["quotas"]):
            denominator *= comb(len(g), q)
        for selections in product(*choices):
            yield {n for selection in selections for n in selection}, Fraction(1, denominator)
    else:
        for bits in product((0, 1), repeat=len(groups)):
            probability = Fraction(1)
            treated = set()
            for g, p, bit in zip(groups, d["probabilities"], bits):
                p = Fraction(p)
                probability *= p if bit else 1 - p
                if bit:
                    treated.update(g)
            yield treated, probability


class GroupBusinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["case_id"]: c for c in fixtures()}

    def run_case(self, cid="D4-arm", *, raw=None, packet=None, selected=True):
        c = self.cases[cid]
        system, user = make_request(c["business_question"])
        provider = MockProvider(c["reading_reference"] if raw is None else raw)
        draft = provider.generate_json(system_prompt=system, user_prompt=user)
        self.assertEqual(provider.calls, 1)
        return evaluate_draft(c["business_question"], draft, c["packet"] if packet is None else packet,
                              synthetic_protocol_selected=selected)

    def test_mock_routes_and_scientific_flags(self):
        expected = {
            "D3-effects": ["R1A_COMPOSITION", "R1A_COMPOSITION"],
            "D4-arm": ["R1A_RANDOMIZED_ARM"], "D4-split-plan": [None],
            "D3-fixed-plan": ["R1B_FULL_ASSIGNMENT"], "D4-whole-plan": ["R1B_FULL_ASSIGNMENT"],
            "D3-over-quota": [None], "D3-changed-quota": ["R1B_FULL_ASSIGNMENT"],
            "D4-changed-rates": ["R1A_RANDOMIZED_ARM"],
            "D3-exact-count-offline": ["R1A_RANDOMIZED_ARM"],
            "D4-impossible-arm-offline": [None], "D3-all-points-effects-offline": [None, None]}
        for cid, routes in expected.items():
            with self.subTest(case=cid):
                result = self.run_case(cid)
                self.assertEqual([r["core"]["route"] for r in result["results"]], routes)
                self.assertEqual([r["status"] for r in result["results"]],
                                 ["POINT" if r else "UNSUPPORTED" for r in routes])
                self.assertTrue(all(r["core_called"] for r in result["results"]))
                self.assertEqual([r["certificate_replay"] for r in result["results"]], list(map(bool, routes)))
                for key in ("production_admission", "semantic_correctness_verified", "candidate_generator_called",
                            "estimation_called", "policy_called", "nonidentification_proven"):
                    self.assertFalse(result[key])

    def test_every_d3_d4_arm_matches_independent_enumeration(self):
        from pfn_pipeline.identification import identify, replay_population_identification
        for cid in ("D3-effects", "D4-arm"):
            d = self.cases[cid]["packet"]["study"]
            net = _network(d)
            distribution = list(assignment_oracle(d))
            self.assertEqual(sum(p for _, p in distribution), 1)
            for i, node in enumerate(net.node_ids):
                neighbors = {net.node_ids[(i - 1) % 8], net.node_ids[(i + 1) % 8]}
                for own, peers in product((0, 1), repeat=2):
                    mass = sum((p for z, p in distribution if int(node in z) == own
                                and int(bool(z & neighbors)) == peers), Fraction())
                    with self.subTest(design=cid, node=node, own=own, peers=peers):
                        result = identify(_arm(d, net, node, own, peers))
                        if mass:
                            self.assertEqual(result.status, "POINT")
                            self.assertEqual(result.result["certificate"]["joint_arm_support_probability"], str(mass))
                            self.assertEqual(replay_population_identification(result).verification_status, "VERIFIED")
                        else:
                            self.assertEqual(result.status, "UNSUPPORTED")
                            self.assertEqual(result.result["reason_code"], "ZERO_ARM_SUPPORT")

    def test_fixed_plan_and_exact_count_probabilities(self):
        for cid, expected in (("D3-fixed-plan", "1/24"), ("D4-whole-plan", "1/6"),
                              ("D3-changed-quota", "1/24")):
            r = self.run_case(cid)["results"][0]["core"]["identification"]
            self.assertEqual(r["assignment_probability"], expected)
            numeric, _ = project(self.cases[cid]["business_question"], self.cases[cid]["reading_reference"])
            z = set(numeric["targets"][0]["treated_nodes"])
            oracle = sum((p for a, p in assignment_oracle(self.cases[cid]["packet"]["study"]) if a == z), Fraction())
            self.assertEqual(Fraction(expected), oracle)
        r = self.run_case("D3-exact-count-offline")["results"][0]["core"]["identification"]
        self.assertEqual(r["certificate"]["joint_arm_support_probability"], "5/24")
        r = self.run_case("D4-changed-rates")["results"][0]["core"]["identification"]
        self.assertEqual(r["certificate"]["joint_arm_support_probability"], "1/3")

    def test_unsupported_keeps_original_population(self):
        r = self.run_case("D3-all-points-effects-offline")
        for q in r["results"]:
            self.assertEqual(q["proposed_target"]["nodes"], [f"{i:02d}" for i in range(1, 9)])
            self.assertEqual(q["status"], "UNSUPPORTED")
            self.assertEqual(q["core"]["reason_code"], "ZERO_ARM_SUPPORT")

    def test_science_selection_and_missing_information_stop_before_core(self):
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            self.assertEqual(self.run_case(selected=False)["status"], "REVIEW_REQUIRED")
            self.assertEqual(self.run_case("D4-finite-data-only")["results"][0]["status"], "NEEDS_INPUT")
            for field in ("population_information", "causal_licenses"):
                packet = deepcopy(self.cases["D4-arm"]["packet"])
                packet["science"][field] = None
                self.assertEqual(self.run_case(packet=packet)["results"][0]["status"], "NEEDS_INPUT")
            core.assert_not_called()

    def test_missing_probabilities_and_independence_not_defaulted(self):
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            self.assertEqual(self.run_case("D4-missing-probability")["reason_code"], "CLUSTER_PROBABILITIES_MISSING")
            for value in (None, False):
                raw = deepcopy(self.cases["D4-arm"]["reading_reference"])
                raw["study"]["draws_independent"] = value
                self.assertEqual(self.run_case(raw=raw)["reason_code"], "INDEPENDENT_GROUP_DRAWS_NOT_DECLARED")
            core.assert_not_called()

    def test_partition_overlap_missing_units_or_probability_length_rejected(self):
        mutations = [
            lambda s: s["groups"][1].__setitem__(0, "01"),
            lambda s: s["groups"][0].pop(),
            lambda s: s["probabilities"].pop(),
            lambda s: s["probabilities"].__setitem__(0, "3/2"),
            lambda s: s["probabilities"].__setitem__(0, "NaN"),
            lambda s: s["probabilities"].__setitem__(0, "1/0"),
        ]
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            for change in mutations:
                raw = deepcopy(self.cases["D4-arm"]["reading_reference"])
                change(raw["study"])
                self.assertEqual(self.run_case(raw=raw)["status"], "REJECTED")
            core.assert_not_called()

    def test_coupled_group_reordering_is_exact_but_rate_swapping_is_not(self):
        raw = deepcopy(self.cases["D4-arm"]["reading_reference"])
        raw["study"]["groups"].reverse()
        raw["study"]["probabilities"].reverse()
        self.assertEqual(self.run_case(raw=raw)["results"][0]["status"], "POINT")
        raw["study"]["probabilities"].reverse()
        self.assertEqual(self.run_case(raw=raw)["reason_code"], "STUDY_READING_CONFLICTS_WITH_PROTOCOL")

    def test_false_parameter_alias_or_model_approval_rejected(self):
        for name, value in (("quota", 4), ("a4_admitted", True), ("probability", "1/2")):
            raw = deepcopy(self.cases["D4-arm"]["reading_reference"])
            raw["study"][name] = value
            self.assertEqual(self.run_case(raw=raw)["reason_code"], "GROUP_READING_SCHEMA_INVALID")

    def test_sources_missing_targets_and_boolean_states_are_validated(self):
        for change in (
            lambda s, q: s.update(graph_source="s99"),
            lambda s, q: q.update(population_source="s99"),
            lambda s, q: q["first"].update(own=True),
        ):
            raw = deepcopy(self.cases["D4-arm"]["reading_reference"])
            change(raw["study"], next(iter(raw["questions"].values())))
            self.assertEqual(self.run_case(raw=raw)["status"], "REJECTED")
        raw = deepcopy(self.cases["D4-arm"]["reading_reference"])
        raw["questions"].clear()
        self.assertEqual(self.run_case(raw=raw)["status"], "REVIEW_REQUIRED")

    def test_unknown_target_coordinates_and_remaining_are_not_completed(self):
        for change in (
            lambda q: q.update(population=dict(selection="不明确", ids=[])),
            lambda q: q.update(aggregation="不明确"),
            lambda q: q.update(first=None),
            lambda q: q["first"].update(own="不明确"),
            lambda q: q["first"].update(remaining_source=None),
        ):
            raw = deepcopy(self.cases["D4-arm"]["reading_reference"])
            change(next(iter(raw["questions"].values())))
            r = self.run_case(raw=raw)["results"][0]
            self.assertEqual(r["status"], "NEEDS_INPUT")
            self.assertFalse(r["core_called"])

    def test_request_has_no_packet_gold_target_or_admission(self):
        for c in self.cases.values():
            system, user = make_request(c["business_question"])
            data = json.loads(user)
            self.assertEqual(set(data), {"business_question", "source_catalog", "question_slots", "output_schema"})
            self.assertNotIn("SYNTHETIC population", system + user)
            self.assertNotIn("三个来源", system)
            self.assertNotIn("unresolved只记录", system)
            self.assertEqual(set(data["output_schema"]["properties"]["study"]["properties"]),
                             set(c["reading_reference"]["study"]))

    def test_mutation_is_not_silently_applied_to_model_json(self):
        raw = deepcopy(self.cases["D3-effects"]["reading_reference"])
        before = deepcopy(raw)
        self.run_case("D3-effects", raw=raw)
        self.assertEqual(raw, before)

    def test_replay_or_core_exception_is_fatal(self):
        with patch("pfn_pipeline.identification_business.replay_verified_business_outcome", return_value=False):
            with self.assertRaises(RuntimeError):
                self.run_case()

    def test_numeric_boundary_rechecks_source_membership(self):
        c = self.cases["D4-arm"]
        for change in (
            lambda n: n["study"].update(design_source="s99"),
            lambda n: n["targets"][0].update(question_quote="伪造的问句？"),
            lambda n: n["targets"][0].update(population_quote="伪造的人口。"),
        ):
            numeric, _ = project(c["business_question"], c["reading_reference"])
            change(numeric)
            with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
                r = evaluate_numeric(c["business_question"], numeric, c["packet"], synthetic_protocol_selected=True)
                self.assertEqual(r["reason_code"], "NUMERIC_SOURCE_BINDING_INVALID")
                core.assert_not_called()
        with patch("pfn_pipeline.identification_business.identify_network_business_query", side_effect=ValueError("broken")):
            with self.assertRaisesRegex(ValueError, "broken"):
                self.run_case()


if __name__ == "__main__":
    unittest.main()
