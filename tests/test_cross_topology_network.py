"""v2.2 verified on fixed topology variation, not merely ER300."""
import unittest
from examples.run_network_topology_matrix import run_topology_matrix

class CrossTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=run_topology_matrix()

    def test_all_9_graph_shapes(self):
        self.assertEqual(self.result['graph_count'],9)
        self.assertEqual({g['name'] for g in self.result['graphs']},{
            'path','ring','star','complete','bipartite','community',
            'small_world_like','hub_scale_free_like','disconnected_with_isolate'})

    def test_all_81_design_exposure_graph_combinations_explicitly_recorded(self):
        self.assertEqual(self.result['combinations_total'],81)
        status=self.result['status_counts']
        self.assertEqual(status['POINT_ARM_VERIFIED'],75)
        self.assertEqual(status['PARTIAL_GRAPH_UNSUPPORTED'],3)
        self.assertEqual(status['INVALID_FOR_GRAPH'],3)

    def test_isolate_is_never_silently_exposure_sufficient(self):
        graph=next(g for g in self.result['graphs'] if g['name']=='disconnected_with_isolate')
        for x in graph['design_exposure']:
            if x['exposure']=='E2':self.assertEqual(x['status'],'PARTIAL_GRAPH_UNSUPPORTED')
            if x['exposure']=='E3':self.assertEqual(x['status'],'INVALID_FOR_GRAPH')

    def test_r2_support_changes_with_topology(self):
        r2={g['name']:g['policy_offsupport'] for g in self.result['graphs']}
        for name in ('path','ring'):
            self.assertEqual(r2[name]['r2_status'],'POINT')
            self.assertEqual(r2[name]['r2_route'],'R2_MEAN_SIGNATURE')
        for name in ('star','complete','bipartite'):
            self.assertNotEqual(r2[name]['r2_status'],'POINT')
            self.assertEqual(r2[name]['r2_reason'],'ZERO_POLICY_SIGNATURE_SUPPORT')
        self.assertTrue(all(g['policy_offsupport']['r1b_status']!='POINT'
                            for g in self.result['graphs']))

    def test_no_new_numeric_estimation_claim(self):
        self.assertIn('No PFN/numeric',str(self.result['limitations']))

if __name__=='__main__':unittest.main()
