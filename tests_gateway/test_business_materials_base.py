from copy import deepcopy
from fractions import Fraction
from itertools import product
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from cfm_id_llm.providers.mock import MockProvider
from evaluation.business_core_pilot_base import canonical_hash
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_intake import load_bundle, validate_tables, goal_slots
from evaluation.business_materials_base import make_request, project, evaluate_draft, compile_inquiry


class MaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["case_id"]: c for c in fixtures()}

    def evaluate(self, cid, raw=None, packet=None):
        c = self.cases[cid]
        provider = MockProvider(c["reading_reference"] if raw is None else raw)
        system, user = make_request(c["bundle"])
        raw = provider.generate_json(system_prompt=system, user_prompt=user)
        self.assertEqual(provider.calls, 1)
        return evaluate_draft(c["bundle"], raw, c["packet"] if packet is None else packet, synthetic_protocol_selected=True)

    def test_full_original_files_and_no_graph_shape_or_id_conversion(self):
        for cid, n, e in (("NBIB-003", 72, 140), ("NBIB-020", 48, 75), ("NBIB-021", 64, 94)):
            b = load_bundle(cid)
            self.assertEqual((len(b["structure"]["nodes"]), len(b["structure"]["edges"])), (n, e))
            self.assertEqual(b["structure"]["nodes"][0], "unit_000")
            self.assertIn("outcomes.csv", b["file_inventory"])
            self.assertEqual(b["tables"]["outcomes.csv"]["rows"], [])
            self.assertEqual(set(b["tables"]["units.csv"]["rows"][0]), {"node_id", "unit_group"})
        self.assertIn("cluster_randomization.csv", load_bundle("NBIB-003")["tables"])
        self.assertIn("candidate_policies.csv", load_bundle("NBIB-020")["tables"])

    def test_original_prose_goals_without_question_marks(self):
        self.assertEqual([len(load_bundle(c)["question_slots"]) for c in ("NBIB-003", "NBIB-020", "NBIB-021")], [1, 1, 2])
        self.assertEqual(len(goal_slots("管理团队希望知道：自己用有没有变化；同事用有没有变化。")), 2)
        with self.assertRaises(ValueError):
            goal_slots("只有业务背景，没有提出目标。")

    def test_original_materials_do_not_grant_population_information(self):
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            for cid in ("NBIB-003", "NBIB-020", "NBIB-021"):
                r = self.evaluate(cid + "-original")
                self.assertTrue(r["status"] == "NEEDS_INPUT" or all(q["status"] == "NEEDS_INPUT" for q in r["results"]))
            core.assert_not_called()

    def test_clarified_and_variant_mock_routes(self):
        for cid, routes in {
            "NBIB-003-clarified": [None], "NBIB-020-clarified": [None],
            "NBIB-021-clarified": ["R1A_COMPOSITION"] * 2,
            "NBIB-003-single-store": ["R1A_RANDOMIZED_ARM"],
            "NBIB-020-whole-regions": ["R1B_FULL_ASSIGNMENT"],
            "NBIB-021-single-station": ["R1A_RANDOMIZED_ARM"],
            "NBIB-003-cross-neighbor-scope": ["R1A_COMPOSITION"],
        }.items():
            with self.subTest(case=cid):
                r = self.evaluate(cid)
                self.assertEqual([q["core"]["route"] for q in r["results"]], routes)
                self.assertEqual([q["certificate_replay"] for q in r["results"]], list(map(bool, routes)))
                self.assertFalse(r["candidate_generator_called"])
                self.assertFalse(r["production_admission"])

    def test_cross_scope_is_explicit_and_full_scope_is_not_silently_reduced(self):
        full = self.evaluate("NBIB-003-clarified")["results"][0]
        subset = self.evaluate("NBIB-003-cross-neighbor-scope")["results"][0]
        self.assertEqual(len(full["proposed_target"]["nodes"]), 72)
        self.assertEqual(full["core"]["reason_code"], "ZERO_ARM_SUPPORT")
        self.assertEqual(len(subset["proposed_target"]["nodes"]), 54)
        self.assertEqual(subset["status"], "POINT")

    def test_d4_complete_cluster_enumeration_agrees_with_every_local_cell(self):
        c = self.cases["NBIB-003-cross-neighbor-scope"]
        _, d, targets = project(c["bundle"], c["reading_reference"])
        batch = compile_inquiry(d, targets[0], c["bundle"], c["packet"]["science"]).batch
        s = c["bundle"]["structure"]
        neighbors = {n: set() for n in s["nodes"]}
        for a, b in s["edges"]:
            neighbors[a].add(b); neighbors[b].add(a)
        distributions = [set(n for g, bit in zip(s["groups"].values(), bits) if bit for n in g)
                         for bits in product((0, 1), repeat=6)]
        for node in s["nodes"]:
            for own, peers in product((0, 1), repeat=2):
                mass = Fraction(sum(int(node in z) == own and int(bool(z & neighbors[node])) == peers for z in distributions), 64)
                cell = batch.cell(node, own, peers)
                self.assertEqual(cell["status"], "POINT" if mass else "UNSUPPORTED")
                if mass:
                    # The independently replayed batch exposes exact probabilities.
                    self.assertEqual(Fraction(batch.population_joint_support[s["nodes"].index(node)][own][peers]), mass)

    def test_policy_reference_expands_exact_csv_without_using_realized_treatment(self):
        c = self.cases["NBIB-020-clarified"]
        _, _, targets = project(c["bundle"], c["reading_reference"])
        planned = [n for n, a in c["bundle"]["structure"]["policies"]["half_within_each_cluster"].items() if a]
        self.assertEqual(targets[0].treated_nodes, planned)
        self.assertEqual(len(planned), 24)
        r = self.evaluate("NBIB-020-whole-regions")["results"][0]["core"]["identification"]
        self.assertEqual(r["assignment_probability"], "1/16")

    def test_independence_source_is_not_defaulted(self):
        c = self.cases["NBIB-020-clarified"]
        raw, packet = deepcopy(c["reading_reference"]), deepcopy(c["packet"])
        raw["study"]["draws_independent"] = None
        packet["study"]["draws_independent"] = None
        self.assertEqual(self.evaluate(c["case_id"], raw, packet)["reason_code"], "INDEPENDENT_GROUP_DRAWS_NOT_DECLARED")

    def test_model_must_match_design_table_and_cannot_approve_science(self):
        c = self.cases["NBIB-003-single-store"]
        raw = deepcopy(c["reading_reference"])
        raw["study"]["group_parameters"][0]["probability"] = "1/3"
        self.assertEqual(self.evaluate(c["case_id"], raw)["reason_code"], "MODEL_PROBABILITY_CONFLICTS_WITH_TABLE")
        raw = deepcopy(c["reading_reference"]); raw["a4_admitted"] = True
        self.assertEqual(self.evaluate(c["case_id"], raw)["status"], "REJECTED")
        p = deepcopy(c["packet"]); p["science"]["population_information"] = None
        self.assertFalse(self.evaluate(c["case_id"], packet=p)["results"][0]["core_called"])

    def test_bad_edges_membership_or_policy_rejected(self):
        c = self.cases["NBIB-020-clarified"]
        for change in (
            lambda t: t["network_edges.csv"]["rows"][0].update(target_id="missing"),
            lambda t: t["network_edges.csv"]["rows"][0].update(frozen_before_rollout="0"),
            lambda t: t["network_edges.csv"]["rows"].append(deepcopy(t["network_edges.csv"]["rows"][0])),
            lambda t: t["units.csv"]["rows"][1].update(node_id="unit_000"),
            lambda t: t["candidate_policies.csv"]["rows"].pop(),
            lambda t: t["cluster_randomization.csv"]["rows"].pop(),
        ):
            tables = deepcopy(c["bundle"]["tables"]); change(tables)
            with self.assertRaises(ValueError):
                validate_tables(tables)

    def test_unknown_node_reference_and_missing_source_are_not_repaired(self):
        c = self.cases["NBIB-003-single-store"]
        raw = deepcopy(c["reading_reference"]); raw["questions"]["q1"]["population"]["ids"] = ["01"]
        self.assertEqual(self.evaluate(c["case_id"], raw)["reason_code"], "UNKNOWN_NODE_ID")
        raw = deepcopy(c["reading_reference"]); raw["questions"]["q1"]["population_source"] = None
        self.assertEqual(self.evaluate(c["case_id"], raw)["results"][0]["status"], "NEEDS_INPUT")

    def test_bundle_digest_and_independent_admission_required(self):
        c = self.cases["NBIB-003-single-store"]
        r = evaluate_draft(c["bundle"], c["reading_reference"], c["packet"])
        self.assertEqual(r["status"], "REVIEW_REQUIRED")
        p = deepcopy(c["packet"]); p["bundle_sha256"] = "different"
        self.assertEqual(self.evaluate(c["case_id"], packet=p)["reason_code"], "READING_CONFLICTS_WITH_INDEPENDENT_PROTOCOL")

    def test_requests_do_not_contain_science_packets_or_finite_values(self):
        for c in self.cases.values():
            _, user = make_request(c["bundle"])
            self.assertNotIn("EXPLICIT CONDITIONAL SYNTHETIC population", user)
            payload = json.loads(user)
            self.assertNotIn("rows", payload["finite_table_summaries"]["outcomes.csv"])
            self.assertNotIn("baseline_metric", payload["data_catalog"]["groups"])
            self.assertEqual(payload["data_catalog"]["network"]["edges"], len(c["bundle"]["structure"]["edges"]))

    def test_legacy_loader_includes_randomization_and_policy_tables_with_explicit_omission(self):
        from evaluation.nbib_semantic_eval import load_public_business_case
        intake = load_public_business_case("NBIB-020")
        names = {a.display_name for a in intake.attachments}
        self.assertIn("cluster_randomization.csv", names)
        self.assertIn("candidate_policies.csv", names)
        self.assertTrue(any("ATTACHMENT_LIMIT_OMITTED" in w for w in intake.warnings))

    def test_core_exception_or_replay_failure_is_not_a_normal_unsupported(self):
        with patch("pfn_pipeline.identification_business.replay_verified_business_outcome", return_value=False):
            with self.assertRaises(RuntimeError):
                self.evaluate("NBIB-003-single-store")


if __name__ == "__main__":
    unittest.main()
