import unittest
from copy import deepcopy
from examples.nbib_core_peers_fixture import load_case
from evaluation import business_core_peers_base as old, business_core_peers as new


class OptimizationPopulationTests(unittest.TestCase):
    def test_public_materials_and_schema_unchanged(self):
        i=load_case();self.assertEqual(old.make_request(i['bundle'])[1],new.make_request(i['bundle'])[1])

    def test_known_population_retained_without_fake_treatment_plan(self):
        i=load_case();r=new.preview_submission(i['bundle'],i['raw']);q=r['query_views'][2]
        self.assertEqual(q['state'],'UNSUPPORTED');self.assertEqual(q['proposed_target']['nodes'],i['bundle']['structure']['nodes'])
        self.assertIsNone(q['proposed_target']['treated_nodes']);self.assertIsNone(q['proposed_target']['aggregation']);self.assertFalse(r['core_called'])

    def test_no_posthoc_population_repair(self):
        i=deepcopy(load_case());i['raw']['questions']['q3']['population']=dict(selection='不明确',ids=[])
        r=new.preview_submission(i['bundle'],i['raw'])
        self.assertIsNone(r['query_views'][2]['proposed_target']['nodes']);self.assertEqual(r['draft'],i['raw'])


if __name__=='__main__':unittest.main()
