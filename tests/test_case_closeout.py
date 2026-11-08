"""v2.6 P0 matrix regeneration; no new causal theorem is registered."""
from __future__ import annotations
from pathlib import Path
import json
import tempfile
import unittest

from examples.run_coverage_route_closeout import (
    b20_exact_count_same_offsupport_policy,
    b24_new_observational_direct_requires_new_contract,
    build_coverage_matrix,main,
)


class V26BusinessCoverageCloseout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=build_coverage_matrix()

    def test_preserves_48_unique_versioned_cases(self):
        rows=self.report['cards']
        self.assertEqual(len(rows),48)
        self.assertEqual(len(set(row['case_id'] for row in rows)),48)
        self.assertEqual(sum(row['introduced_in']=='v2.2' for row in rows),32)
        self.assertEqual(sum(row['introduced_in']=='v2.3' for row in rows),5)
        self.assertEqual(sum(row['introduced_in']=='v2.6' for row in rows),11)
        self.assertEqual(self.report['counts'],{
            'POINT':25,'NEEDS_INPUT':7,'BLOCKED_OR_TARGET_GAP':16,
        })

    def test_b20_theorem_now_exists_but_signature_support_zero(self):
        delta=b20_exact_count_same_offsupport_policy()
        self.assertFalse(delta['original_case_point_upgraded'])
        self.assertEqual(delta['experiment_treated_quota'],4)
        self.assertEqual(delta['hub_required_total_treated'],5)
        self.assertIn('ZERO_POLICY_SIGNATURE_SUPPORT',
                      [attempt['reason'] for attempt in delta['attempted_routes']])
        self.assertNotEqual(delta['new_status'],'POINT')

    def test_b24_requires_new_target_and_a4a5(self):
        delta=b24_new_observational_direct_requires_new_contract()
        self.assertEqual(delta['missing_exchangeability_status'],'NEEDS_INPUT')
        self.assertEqual(delta['separate_conditional_witness_status'],'POINT')
        self.assertEqual(delta['separate_conditional_witness_route'],'R3_P_STANDARDIZED_EFFECTS')
        self.assertFalse(delta['original_case_point_upgraded'])
        self.assertEqual(delta['separate_conditional_witness_arm_support'],['3/8','3/8'])

    def test_matrix_not_claimed_as_market_coverage(self):
        self.assertIn('NOT population or market business coverage',
                      self.report['counts_denominator'])
        self.assertIn('B04',self.report['warnings'][-1])
        self.assertTrue(self.report['two_stage_research_oracle']['no_theorem_route_registered'])

    def test_json_html_regeneration_is_byte_stable(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left=main(Path(a)); right=main(Path(b))
            self.assertEqual(left,right)
            for suffix in ('.json','.html'):
                stem='CFM_ID_v2_6_Pre_v2_7_P0_48_Case_Correctness_Closeout'
                self.assertEqual((Path(a)/(stem+suffix)).read_bytes(),
                                 (Path(b)/(stem+suffix)).read_bytes())

if __name__=='__main__':unittest.main()
