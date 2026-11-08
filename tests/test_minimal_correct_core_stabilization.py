"""Tiny, deterministic regression for the one frozen D2 x E1 identification case.

This suite never imports A0, R2/R3, PFN checkpoints or PARTIAL research.
All admissions and A4 operators are explicitly synthetic study fixtures.
"""
from __future__ import annotations

import copy
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import unittest

from pfn_pipeline import (
    ArmInquiryV21, identify_network_business_query, replay_verified_business_outcome,
)
from examples.minimal_correct_core_golden import (
    BASE_EDGES, SCENARIOS, ablated_task, independent_support, run_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]


class FrozenMinimalGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_scenarios()
        cls.rows = {r['change']: r for r in cls.result['scenarios']}

    def test_one_point_replays_and_has_the_exact_original_support(self):
        row = self.rows['base']
        self.assertEqual((row['status'], row['route'], row['replay_verified']),
                         ('POINT', 'R1A_RANDOMIZED_ARM', True))
        self.assertEqual((row['certified_support'], row['exact_support_oracle']), ('1/3', '1/3'))
        self.assertEqual(independent_support(m=2, edges=BASE_EDGES), Fraction(1, 3))

    def test_no_population_operator_cannot_return_point(self):
        row = self.rows['missing_a4']
        self.assertEqual((row['status'], row['reason_code']),
                         ('NEEDS_INPUT', 'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED'))
        self.assertTrue(row['same_target_as_base'])

    def test_proposed_a4_does_not_authorize_point(self):
        row = self.rows['a4_not_admitted']
        self.assertEqual(row['status'], 'NEEDS_INPUT')
        self.assertFalse(row['replay_verified'])
        self.assertTrue(row['same_target_as_base'])

    def test_unconfirmed_and_explicitly_denied_randomization_distinguished(self):
        pending = self.rows['a5_unresolved']
        denied = self.rows['a5_rejected']
        self.assertEqual((pending['status'], denied['status']), ('NEEDS_INPUT', 'UNSUPPORTED'))
        self.assertTrue(pending['same_target_as_base'])
        self.assertTrue(denied['same_target_as_base'])
        self.assertEqual(pending['reason_code'], 'REQUIRED_ASSUMPTIONS_NOT_ADMITTED')

    def test_single_quota_change_exposes_zero_support(self):
        row = self.rows['zero_quota']
        self.assertEqual((row['status'], row['exact_support_oracle'], row['reason_code']),
                         ('UNSUPPORTED', '0', 'ZERO_ARM_SUPPORT'))
        self.assertFalse(row['same_target_as_base'])

    def test_single_graph_edge_change_exposes_zero_support(self):
        row = self.rows['add_network_edge']
        self.assertEqual((row['status'], row['exact_support_oracle'], row['reason_code']),
                         ('UNSUPPORTED', '0', 'ZERO_ARM_SUPPORT'))
        self.assertFalse(row['same_target_as_base'])

    def test_different_exposure_mapping_creates_different_target(self):
        row = self.rows['different_exposure']
        self.assertEqual((row['status'], row['certified_support']), ('POINT', '1/3'))
        self.assertTrue(row['replay_verified'])
        self.assertFalse(row['same_target_as_base'])

    def test_llm_proposal_alone_cannot_authorize_query(self):
        row = self.rows['query_not_confirmed']
        self.assertEqual((row['status'], row['reason_code']),
                         ('UNSUPPORTED', 'QUERY_NOT_CONFIRMED'))

    def test_no_exposure_sufficiency_or_numerical_estimator_sneaks_in(self):
        outcome = identify_network_business_query(ArmInquiryV21(ablated_task('base')))
        self.assertEqual(outcome.status, 'POINT')
        self.assertNotIn('exposure_sufficiency', outcome.result.result['assumptions_used'])
        self.assertIsNone(outcome.result.estimation_request)
        self.assertTrue(all(not row['numeric_effect_estimated'] for row in self.rows.values()))

    def test_tampering_proof_support_is_rejected_by_original_verifier(self):
        outcome = identify_network_business_query(ArmInquiryV21(ablated_task('base')))
        self.assertTrue(replay_verified_business_outcome(outcome))
        payload = copy.deepcopy(outcome.result.result)
        payload['certificate']['joint_arm_support_probability'] = '999/1000'
        altered = replace(outcome, result=replace(outcome.result, result=payload))
        with self.assertRaisesRegex(ValueError, 'proof replay failed'):
            replay_verified_business_outcome(altered)

    def test_tampering_route_wrapper_is_rejected(self):
        outcome = identify_network_business_query(ArmInquiryV21(ablated_task('base')))
        with self.assertRaisesRegex(ValueError, 'route/result mismatch'):
            replay_verified_business_outcome(replace(outcome, route='R2_MEAN_SIGNATURE'))

    def test_small_html_only_visualizes_verified_python_snapshot(self):
        from examples.build_minimal_golden_atlas import build
        output = ROOT / 'assets/minimal_core_fixtures' / 'CFM_ID_Minimal_Golden_Ablation.html'
        self.assertEqual(build(), output.read_text(encoding='utf-8'))
        self.assertIn('script type="application/json" id="data"', build())

    def test_all_scenarios_are_exhaustive_and_have_locked_snapshot(self):
        expected = json.loads((ROOT / 'assets/benchmark_assets_stabilization' /
                               'minimal_golden_expected.json').read_text(encoding='utf-8'))
        self.assertEqual(list(self.rows), list(SCENARIOS))
        self.assertEqual(self.result, expected)


if __name__ == '__main__':
    unittest.main()
