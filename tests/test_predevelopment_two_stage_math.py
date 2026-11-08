"""Research-only acceptance oracles for a proposed two-stage design, no theorem route."""
from __future__ import annotations
import unittest
from fractions import Fraction
from itertools import product

from predevelopment.two_stage_exact_oracle import (
    TwoStageQuotaMixtureDraft, acceptance_witnesses,
)
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, MultiGroupFixedQuotaDesignV25,
)
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec


class TwoStagePreDevelopmentMath(unittest.TestCase):
    def test_witness_exact_mass_and_own_conditional(self):
        evidence=acceptance_witnesses()
        self.assertTrue(evidence['independent_enumeration_agrees'])
        self.assertEqual(evidence['conditional_treated_neighbor_mass'],['0','1/2','1/2'])
        self.assertEqual(evidence['exact_total_assignment_mass'],'1')
        self.assertTrue(evidence['no_theorem_route_registered'])

    def test_exhaustive_full_vector_and_factorized_joint_laws(self):
        cases=(
            TwoStageQuotaMixtureDraft(('a','b','c'),(('a','b'),('c',)),
                         (((0,1),'1/3'), ((1,0),'1/3'), ((2,1),'1/3'))),
            TwoStageQuotaMixtureDraft(('a','b','c','d'),(('a','b'),('c','d')),
                         (((1,0),'1/4'),((1,2),'1/4'),((2,1),'1/2'))),
            TwoStageQuotaMixtureDraft(('a','b','c','d','e'),(('a','b'),('c',),('d','e')),
                         (((2,0,0),'1/5'),((0,1,2),'2/5'),((1,1,1),'2/5'))),
            TwoStageQuotaMixtureDraft(('a','b','c','d','e','f'),(('a','b'),('c','d'),('e','f')),
                         (((1,0,2),'1/3'),((0,2,1),'1/3'),((2,1,0),'1/3'))),
        )
        for d in cases:
            with self.subTest(groups=len(d.groups), n=len(d.node_order)):
                self.assertEqual(sum(q for _,q in d.all_assignments()),1)
                for node in d.node_order:
                    other=tuple(x for x in d.node_order if x!=node)
                    for own in (0,1):
                        for refs in (frozenset(),frozenset(other[:1]),frozenset(other)):
                            expected=d.exhaustive_arm_joint(node,own,refs)
                            computed=d.factorized_arm_joint(node,own,refs)
                            self.assertEqual(computed,expected)
                            den=sum(expected)
                            self.assertEqual(d.conditional_neighbor_count(node,own,refs),
                                tuple(p/den for p in expected) if den else None)

    def test_fixed_profile_is_exact_d5_special_case(self):
        nodes=('a','b','c','d','e','f')
        groups=(('a','b'),('c','d'),('e','f'))
        quotas=(1,0,2)
        draft=TwoStageQuotaMixtureDraft(nodes,groups,((quotas,'1'),))
        network=NetworkExposureSpec(network_id='draft-6',node_ids=list(nodes),
                                     undirected_edges=[('a','b'),('a','c'),('a','e'),('d','f')])
        production_d5=AssignmentSpec(MultiGroupFixedQuotaDesignV25(groups=groups,treated_quotas=quotas))
        for z in product((0,1),repeat=len(nodes)):
            self.assertEqual(draft.full_q(z),production_d5.full_assignment_probability(
                network,dict(zip(nodes,z))))
        for own in (0,1):
            refs=frozenset(('b','c','e'))
            proposal=draft.factorized_arm_joint('a',own,refs)
            baseline=production_d5.conditional_neighbor_count_law(network,'a',own,refs)
            self.assertEqual(sum(proposal),baseline.own_probability)
            self.assertEqual(proposal,tuple(baseline.own_probability*p for p in baseline.conditional_count_mass))

    def test_stage_one_selection_is_not_naively_weighted_after_conditioning(self):
        d=TwoStageQuotaMixtureDraft(('a','b','c','d'),(('a','b'),('c','d')),
                (((0,1),'1/2'), ((2,1),'1/2')))
        refs=frozenset(('b','c'))
        # T_a=1 rules out the first profile. The conditional profile weights
        # are (0,1), not the marginal first-stage weights (1/2,1/2).
        self.assertEqual(d.conditional_neighbor_count('a',1,refs),
                         (Fraction(0), Fraction(1,2), Fraction(1,2)))
        self.assertEqual(d.own_probability('a',1),Fraction(1,2))

    def test_zero_probability_is_undefined_conditional_not_point(self):
        d=TwoStageQuotaMixtureDraft(('a','b','c','d'),(('a','b'),('c','d')),
                                    (((0,1),'1'),))
        refs=frozenset(('b','c'))
        self.assertEqual(d.factorized_arm_joint('a',1,refs),(0,0,0))
        self.assertIsNone(d.conditional_neighbor_count('a',1,refs))

    def test_bad_protocols_are_rejected(self):
        with self.assertRaises(ValueError):
            TwoStageQuotaMixtureDraft(('a','b'),(('a',),('a',)),(((0,0),'1'),))
        with self.assertRaises(ValueError):
            TwoStageQuotaMixtureDraft(('a','b'),(('a',),('b',)),(((2,0),'1'),))
        with self.assertRaises(ValueError):
            TwoStageQuotaMixtureDraft(('a','b'),(('a',),('b',)),(((0,0),'1/2'),))
        with self.assertRaises(ValueError):
            TwoStageQuotaMixtureDraft(('a','b'),(('a',),('b',)),(((0,0),'1/2'),((0,0),'1/2')))

if __name__=='__main__':
    unittest.main()
