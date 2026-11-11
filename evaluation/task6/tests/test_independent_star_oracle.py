import unittest
from evaluation.task6.scripts.independent_star_oracle import run


class IndependentReferenceTest(unittest.TestCase):
    def test_finite_support_and_endpoints(self):
        r=run()
        self.assertEqual(r['assignments'],35)
        self.assertEqual(r['target_support_counts'][0],0)
        self.assertTrue(all(x>0 for x in r['target_support_counts'][1:]))
        self.assertEqual((r['lower'],r['upper']),('3/7','4/7'))
        self.assertTrue(r['non_point'])
