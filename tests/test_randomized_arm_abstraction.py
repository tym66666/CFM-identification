"""v0.6: assignment x exposure x support contracts, checked against enumeration.

The oracle enumerates ORIGINAL full treatment allocations (not support formulas),
including empty/full quotas and cross-group network edges.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations, product
from math import comb
import random
import unittest
from unittest.mock import patch

from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine, ArmSupportEvidence,
)
from pfn_pipeline._internal.identification.randomized_network_arm import (
    RandomizedNetworkArmBackend, make_complete_randomization_arm_spec,
)
from pfn_pipeline._internal.identification.schemas import (
    CompleteRandomizationDesignV1, TwoGroupFixedQuotaDesignV1, NetworkExposureSpec,
)
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier


def oracle(net, design, node, a, exposure):
    """Brute-force q over full treatment vectors; never call production support."""
    neighbors = set()
    for x, y in net.undirected_edges:
        if node == x:
            neighbors.add(y)
        elif node == y:
            neighbors.add(x)
    degree = len(neighbors)
    if exposure == 'three_level_treated_neighbor_fraction' and degree == 0:
        return None
    if isinstance(design, CompleteRandomizationDesignV1):
        allocations = (set(draw) for draw in combinations(net.node_ids, design.m))
        denominator = comb(len(net.node_ids), design.m)
    else:
        allocations = (set(draw0) | set(draw1)
                       for draw0, draw1 in product(
                           combinations(design.groups[0], design.treated_quotas[0]),
                           combinations(design.groups[1], design.treated_quotas[1]),
                       ))
        denominator = (comb(len(design.groups[0]), design.treated_quotas[0])
                       * comb(len(design.groups[1]), design.treated_quotas[1]))
    counts = {}
    for treated in allocations:
        k = sum(neighbor in treated for neighbor in neighbors)
        if exposure == 'strict_majority_ties_low':
            state = int(k > degree // 2)
        elif 3 * k < degree:
            state = 0
        elif 3 * k < 2 * degree:
            state = 1
        else:
            state = 2
        key = (int(node in treated), state)
        counts[key] = counts.get(key, 0) + 1
    return {s: Fraction(counts.get((a, s), 0), denominator)
            for s in ((0, 1) if exposure == 'strict_majority_ties_low' else (0, 1, 2))}


class ComposableRandomizedArmTests(unittest.TestCase):
    def test_exact_three_level_integer_boundaries(self):
        e1 = ExposureSpec('strict_majority_ties_low')
        e2 = ExposureSpec('three_level_treated_neighbor_fraction')
        self.assertEqual(e1.states, (0, 1))
        self.assertEqual(e2.states, (0, 1, 2))
        self.assertEqual(e1.classify(2, 4), 0)  # strict majority ties low
        self.assertEqual(e1.classify(3, 4), 1)
        self.assertEqual([e2.classify(k, 3) for k in range(4)], [0, 1, 2, 2])
        self.assertEqual(e2.classify(2, 6), 1)
        self.assertEqual(e2.classify(4, 6), 2)
        with self.assertRaisesRegex(ValueError, 'isolate'):
            e2.classify(0, 0)
        with self.assertRaises(ValueError):
            ExposureSpec('not_a_known_grouping')
        with self.assertRaises(ValueError):
            SupportEngine.from_count_law(
                AssignmentSpec(CompleteRandomizationDesignV1(m=1)).conditional_neighbor_count_law(
                    NetworkExposureSpec(network_id='fixture',node_ids=['0','1'],undirected_edges=[('0','1')]),
                    '0', 1,
                ), e1, 2)

    def test_all_combinations_against_original_design_enumeration(self):
        rng = random.Random(20261014)
        cases = 0
        for n in range(2, 9):
            nodes = [str(j) for j in range(n)]
            for trial in range(5):
                edges = [(str(i), str(j)) for i in range(n) for j in range(i + 1, n)
                         if rng.random() < rng.choice((0.1, 0.4, 0.7, 1.0))]
                net = NetworkExposureSpec(
                    network_id=f'abstraction-n{n}-{trial}', node_ids=nodes, undirected_edges=edges,
                )
                permuted = list(nodes)
                rng.shuffle(permuted)
                split = rng.randrange(1, n)
                groups = (tuple(permuted[:split]), tuple(permuted[split:]))
                designs = (
                    CompleteRandomizationDesignV1(m=rng.randrange(n + 1)),
                    TwoGroupFixedQuotaDesignV1(
                        groups=groups,
                        treated_quotas=(rng.randrange(len(groups[0]) + 1),
                                        rng.randrange(len(groups[1]) + 1)),
                    ),
                )
                for design in designs:
                    assignment = AssignmentSpec(design)
                    for node in nodes:
                        for a in (0, 1):
                            law = assignment.conditional_neighbor_count_law(net, node, a)
                            self.assertEqual(len(law.conditional_count_mass), law.degree + 1)
                            self.assertEqual(sum(law.conditional_count_mass),
                                             Fraction(1) if law.own_probability else Fraction(0))
                            for grouping in ('strict_majority_ties_low', 'three_level_treated_neighbor_fraction'):
                                exposure = ExposureSpec(grouping)
                                expected = oracle(net, design, node, a, grouping)
                                if expected is None:
                                    continue
                                actual = {}
                                for state in exposure.states:
                                    with self.subTest(n=n, trial=trial, kind=design.kind,
                                                      node=node, a=a, group=grouping, s=state):
                                        evidence = SupportEngine.evaluate(
                                            network=net, assignment=assignment, exposure=exposure,
                                            node_id=node, own_treatment_value=a, exposure_value=state,
                                        )
                                        actual[state] = evidence.joint_probability
                                        self.assertEqual(evidence.joint_probability, expected[state])
                                        self.assertEqual(evidence.joint_probability,
                                                         evidence.own_probability * evidence.exposure_given_own_probability)
                                        cases += 1
                                self.assertEqual(sum(actual.values()), law.own_probability)
        self.assertGreater(cases, 2000)

    def test_full_assignment_probability_is_original_design_law(self):
        from itertools import product as product_bits
        net = NetworkExposureSpec(
            network_id='full-law', node_ids=['0', '1', '2', '3'],
            undirected_edges=[('0','2'),('1','3')],
        )
        designs = (
            CompleteRandomizationDesignV1(m=2),
            TwoGroupFixedQuotaDesignV1(groups=(('0','1'),('2','3')), treated_quotas=(1,1)),
        )
        for design in designs:
            adapter = AssignmentSpec(design)
            masses = []
            for bits in product_bits((0,1), repeat=4):
                assignment = dict(zip(net.node_ids, bits))
                mass = adapter.full_assignment_probability(net, assignment)
                masses.append(mass)
                if isinstance(design, CompleteRandomizationDesignV1):
                    expected = Fraction(1,6) if sum(bits) == 2 else Fraction(0)
                else:
                    expected = (Fraction(1,4) if bits[0]+bits[1] == 1 and bits[2]+bits[3] == 1
                                else Fraction(0))
                self.assertEqual(mass, expected)
            self.assertEqual(sum(masses), Fraction(1))
        with self.assertRaises(ValueError):
            AssignmentSpec(designs[0]).full_assignment_probability(net, {'0': 1})
        with self.assertRaises(ValueError):
            AssignmentSpec(designs[0]).full_assignment_probability(
                net, {'0':True,'1':0,'2':1,'3':0})

    def test_e2_isolate_and_impossible_own_arm(self):
        net = NetworkExposureSpec(network_id='isolated', node_ids=['0', '1', '2'],
                                  undirected_edges=[('1', '2')])
        zero_design = AssignmentSpec(CompleteRandomizationDesignV1(m=0))
        good = SupportEngine.evaluate(network=net, assignment=zero_design,
                                      exposure=ExposureSpec('strict_majority_ties_low'),
                                      node_id='0', own_treatment_value=0, exposure_value=0)
        self.assertEqual(good.joint_probability, 1)
        with self.assertRaisesRegex(ValueError, 'isolate'):
            SupportEngine.evaluate(network=net, assignment=zero_design,
                                   exposure=ExposureSpec('three_level_treated_neighbor_fraction'),
                                   node_id='0', own_treatment_value=0, exposure_value=0)
        # A zero-probability own-treatment arm has zero JOINT mass by convention;
        # the public theorem gate rejects E2 isolates before calling the engine.
        never_treated = SupportEngine.evaluate(
            network=net, assignment=zero_design,
            exposure=ExposureSpec('three_level_treated_neighbor_fraction'),
            node_id='0', own_treatment_value=1, exposure_value=0)
        self.assertEqual(never_treated.joint_probability, 0)

    def test_verifier_catches_proposer_support_corruption(self):
        net = NetworkExposureSpec(network_id='proof-gate', node_ids=['0','1','2','3'],
                                  undirected_edges=[('0','1'),('0','2')])
        spec = make_complete_randomization_arm_spec(
            net, m=2, node_id='0', own_treatment_value=1, exposure_value=0,
            source='synthetic protocol', evidence='known complete randomization',
            admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE',
        )
        backend = RandomizedNetworkArmBackend()
        correct = backend.solve(spec)
        self.assertEqual(IdentificationVerifier().verify(spec, correct).verification_status, 'VERIFIED')
        with patch.object(SupportEngine, 'evaluate', return_value=ArmSupportEvidence(
            Fraction(1,2), Fraction(1,2), Fraction(99,100),
        )):
            corrupted = backend.solve(spec)
            # The independent verifier must not use SupportEngine and therefore
            # must reject this corrupted result/certificate.
            checked = IdentificationVerifier().verify(spec, corrupted)
            self.assertEqual(checked.verification_status, 'REJECTED')


if __name__ == '__main__':
    unittest.main()
