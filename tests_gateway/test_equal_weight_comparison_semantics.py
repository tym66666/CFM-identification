"""Semantic scoring checks; these are not LLM-accuracy observations."""
from copy import deepcopy
import unittest
from evaluation.equal_weight_comparison_semantics import equivalent_target
from examples.mean_order_business_fixture import make_case


class ComparisonSemanticEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.case=make_case(population=['A','C'])
        self.bundle=self.case['bundle']
        self.ref=self.case['candidate']['comparison']

    def test_reordering_equal_weight_population_preserves_target_and_input(self):
        for population in (list('ABCD'),['A','C']):
            c=make_case(population=population);reference=c['candidate']['comparison'];actual=deepcopy(reference)
            actual['reading']['questions']['q1']['population'].reverse()
            before=deepcopy(actual);ref_before=deepcopy(reference)
            self.assertTrue(equivalent_target(c['bundle'],actual,reference))
            self.assertEqual(actual,before);self.assertEqual(reference,ref_before)

    def test_different_population_is_not_equivalent(self):
        actual=deepcopy(self.ref);actual['reading']['questions']['q1']['population']=['B','D']
        self.assertFalse(equivalent_target(self.bundle,actual,self.ref))

    def test_first_minus_second_direction_is_preserved(self):
        actual=deepcopy(self.ref);q=actual['reading']['questions']['q1'];q['first'],q['second']=q['second'],q['first']
        self.assertFalse(equivalent_target(self.bundle,actual,self.ref))

    def test_stale_question_binding_is_rejected(self):
        actual=deepcopy(self.ref);actual['reading']['intents']['q1']['question_id']='question_'+'0'*64
        self.assertFalse(equivalent_target(self.bundle,actual,self.ref))

    def test_duplicate_or_unknown_population_is_rejected(self):
        for population in (['A','A','C'],['A','Z']):
            actual=deepcopy(self.ref);actual['reading']['questions']['q1']['population']=population
            self.assertFalse(equivalent_target(self.bundle,actual,self.ref))

    def test_unknowns_are_not_filled(self):
        missing=deepcopy(self.ref);missing['reading']['questions']['q1']['population']=None
        self.assertFalse(equivalent_target(self.bundle,missing,self.ref))
        self.assertTrue(equivalent_target(self.bundle,missing,deepcopy(missing)))
        other=deepcopy(self.ref);other['reading']['questions']['q1']['first']['A']=None
        self.assertFalse(equivalent_target(self.bundle,missing,other))

    def test_aggregation_is_not_erased_when_targets_are_empty(self):
        a=deepcopy(self.ref);a['reading']['questions']['q1']['population']=None
        b=deepcopy(a);b['reading']['questions']['q1']['aggregation']='不明确'
        self.assertFalse(equivalent_target(self.bundle,a,b))

    def test_malformed_or_extra_fields_are_rejected(self):
        actual=deepcopy(self.ref);actual['reading']['questions']['q1']['invented']=True
        self.assertFalse(equivalent_target(self.bundle,actual,self.ref))
        self.assertFalse(equivalent_target(self.bundle,{},self.ref))


if __name__=='__main__':unittest.main()
