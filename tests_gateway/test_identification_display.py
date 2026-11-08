import unittest
from copy import deepcopy
from evaluation.identification_display import effect_summary

def proof():
    return dict(status='POINT',verification_status='VERIFIED',identified_functional='original exact formula',constituent_arms=[
        dict(node_id=n,own_treatment=a,exposure_state=1,coefficient=str(c),joint_support='1/4')
        for n in ('a','b') for a,c in ((0,'-1/2'),(1,'1/2'))])

class DisplayTests(unittest.TestCase):
    def test_compact_formula_requires_exact_coefficients(self):
        p=proof();s,compact=effect_summary(p);self.assertTrue(compact);self.assertIn('1/2',s)
        p['constituent_arms'][0]['coefficient']='-1/3';self.assertEqual(effect_summary(p),('original exact formula',False))
    def test_rejects_nonpositive_support(self):
        p=proof();p['constituent_arms'][0]['joint_support']='0'
        with self.assertRaises(ValueError):effect_summary(p)
    def test_unverified_cannot_be_displayed_as_certified(self):
        p=proof();p['verification_status']='UNVERIFIED'
        with self.assertRaises(ValueError):effect_summary(p)
    def test_duplicate_term_not_hidden_by_compaction(self):
        p=proof();p['constituent_arms'].append(deepcopy(p['constituent_arms'][0]));self.assertFalse(effect_summary(p)[1])

if __name__=='__main__':unittest.main()
