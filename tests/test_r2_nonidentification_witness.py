"""Independent witness: R2's extra mean-sufficiency is indispensable off support.

Two complete potential-outcome schedules share EXACTLY the randomized law of
(T_vector, Y_vector^obs), yet disagree on all-treated policy value. They are
both consistent with the D2 randomized design and arbitrary interference; one
cannot issue POINT just from q and an exposure grouping. The extra A5 mean-
signature sufficiency excludes the second world.
"""
from fractions import Fraction
from itertools import product
import unittest

class R2OffSupportWitness(unittest.TestCase):
    def test_star5_two_worlds_same_full_observable_law_different_policy(self):
        n=5;m=4;z=(1,)*5
        support=[t for t in product((0,1),repeat=n) if sum(t)==m]
        self.assertEqual(len(support),5)
        def potential_world_a(t):
            return (Fraction(0),)*5
        def potential_world_b(t):
            # Only the unsupported all-treated configuration differs.
            return ((Fraction(1),)+(Fraction(0),)*4) if t==z else (Fraction(0),)*5
        observed_a={t:(Fraction(1,5),potential_world_a(t)) for t in support}
        observed_b={t:(Fraction(1,5),potential_world_b(t)) for t in support}
        self.assertEqual(observed_a,observed_b)
        Va=sum(potential_world_a(z),Fraction(0))/n
        Vb=sum(potential_world_b(z),Fraction(0))/n
        self.assertEqual(Va,Fraction(0))
        self.assertEqual(Vb,Fraction(1,5))
        # In world B, the hub is treated both in observed assignments (K=3)
        # and all-treated (K=4), and its majority state is 1 in both cases.
        # Yet the hub mean response differs. Thus B violates the extra R2 A5.
        hub_observed=potential_world_b((1,1,1,1,0))[0]
        hub_policy=potential_world_b(z)[0]
        self.assertNotEqual(hub_observed,hub_policy)

if __name__=='__main__':unittest.main()
