import unittest
from copy import deepcopy
from evaluation import business_condition_evidence as gate

def sample(goal,quote):
    return {'question_slots':{'q1':goal}}, {'questions':{'q1':{'first':{'own':'开通','neighbors':'超过一半','neighbor_count':None},'second':None,'peer_evidence':{'first':quote,'second':None}}}}

class NumberingTests(unittest.TestCase):
    def test_only_numbering_can_be_omitted(self):
        b,r=sample('问题一：同事过半开通时，业绩如何？','同事过半开通时，业绩如何？');before=deepcopy(r)
        projected,receipt=gate.project_evidence(b,r);self.assertTrue(receipt['passed']);self.assertEqual(r,before)
        self.assertEqual(projected['questions']['q1']['first'],r['questions']['q1']['first'])
    def test_negation_cannot_be_omitted(self):
        b,r=sample('问题一：不是要求同事过半开通时的效果。','同事过半开通时的效果。');self.assertFalse(gate.project_evidence(b,r)[1]['passed'])
    def test_unknown_cannot_be_omitted(self):
        b,r=sample('问题一：还没决定是否比较同事过半开通的效果。','同事过半开通的效果。');self.assertFalse(gate.project_evidence(b,r)[1]['passed'])
    def test_numbering_removal_does_not_neutralize_negation(self):
        b,r=sample('问题一：不是要求同事过半开通时的效果。','不是要求同事过半开通时的效果。');self.assertFalse(gate.project_evidence(b,r)[1]['passed'])
    def test_business_prefix_not_treated_as_numbering(self):
        b,r=sample('尚未决定：同事过半开通时，业绩如何？','同事过半开通时，业绩如何？');self.assertFalse(gate.project_evidence(b,r)[1]['passed'])
    def test_wrong_question_not_accepted(self):
        b,r=sample('问题一：同事使用是否有帮助？','同事过半开通时，业绩如何？');self.assertFalse(gate.project_evidence(b,r)[1]['passed'])

if __name__=='__main__':unittest.main()
