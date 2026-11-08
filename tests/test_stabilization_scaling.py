"""Slow-tier control: same R1a theorem on a larger fixed ring, no new Family."""
from __future__ import annotations

from fractions import Fraction
import unittest

from pfn_pipeline import (
    ArmInquiryV21, identify_network_business_query,
    make_complete_randomization_arm_task, replay_verified_business_outcome,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec


class GoldenScalingControl(unittest.TestCase):
    def test_same_r1a_theorem_on_300_node_ring(self):
        n, m = 300, 150
        nodes = [str(i) for i in range(n)]
        edges = [(str(i), str((i + 1) % n)) for i in range(n)]
        net = NetworkExposureSpec(
            network_id='CFM_ID_MINIMAL_GOLDEN_RING300',
            node_ids=nodes, undirected_edges=edges)
        task = make_complete_randomization_arm_task(
            net, m=m, node_id='0', own_treatment_value=1, exposure_value=1,
            source='SYNTHETIC_D2_RING300_STRESS',
            evidence='synthetic full-vector randomization and admitted symbolic population arm',
            admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE')
        outcome = identify_network_business_query(ArmInquiryV21(task))
        self.assertEqual((outcome.status, outcome.route), ('POINT', 'R1A_RANDOMIZED_ARM'))
        self.assertTrue(replay_verified_business_outcome(outcome))
        # Three fixed treated nodes: self and both ring neighbors; every
        # full assignment supporting the arm contributes equally.
        independent = Fraction(m * (m - 1) * (m - 2), n * (n - 1) * (n - 2))
        self.assertEqual(outcome.result.result['certificate']['joint_arm_support_probability'],
                         str(independent))
        self.assertIsNone(outcome.result.estimation_request)


if __name__ == '__main__':
    unittest.main()
