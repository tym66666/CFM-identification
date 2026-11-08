"""Independent adversarial audit of D1/D2/D3 × E1/E2/E3 joint support.

This enumerator uses only the official full-assignment q evaluator and an
independently written exposure definition; it does not reuse SupportEngine's
count-law machinery. Intended for N<=7, never ER300.
"""
from __future__ import annotations
import random
from fractions import Fraction
from itertools import product
import unittest
from pfn_pipeline._internal.identification.schemas import (
  NetworkExposureSpec, HeterogeneousBernoulliDesignV1,
  CompleteRandomizationDesignV1, TwoGroupFixedQuotaDesignV1)
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec,ExposureSpec,SupportEngine

class IndependentRandomizedSupportAudit(unittest.TestCase):
    def test_small_network_property_matrix_including_extreme_propensities(self):
        rng=random.Random(6016)
        checked=0
        for n in range(2,8):
            ids=tuple('u'+str(i) for i in range(n))
            groups=(ids[:n//2],ids[n//2:])
            for trial in range(5):
                edges=tuple((ids[i],ids[j]) for i in range(n) for j in range(i+1,n) if rng.randrange(5)<2)
                net=NetworkExposureSpec(network_id='audit',node_ids=list(ids),undirected_edges=list(edges))
                nbrs={i:set() for i in ids}
                for u,v in edges:
                    nbrs[u].add(v);nbrs[v].add(u)
                designs=(
                    HeterogeneousBernoulliDesignV1(propensities={u:str(rng.choice(
                      [Fraction(0),Fraction(1),Fraction(1,2),Fraction(1,3),Fraction(3,4)])) for u in ids}),
                    CompleteRandomizationDesignV1(m=rng.randrange(n+1)),
                    TwoGroupFixedQuotaDesignV1(groups=groups,treated_quotas=(rng.randrange(len(groups[0])+1),
                                                                           rng.randrange(len(groups[1])+1))),
                )
                for design in designs:
                    adapter=AssignmentSpec(design)
                    for g in ('strict_majority_ties_low','three_level_treated_neighbor_fraction',
                              'pretreatment_core_collaborator_majority'):
                        if g=='pretreatment_core_collaborator_majority' and any(not nbrs[u] for u in ids):
                            continue
                        core={u:(sorted(nbrs[u])[0],) for u in ids} if g=='pretreatment_core_collaborator_majority' else None
                        exposure=ExposureSpec(g,core)
                        for node in ids:
                            ref=set(core[node]) if core else nbrs[node]
                            if g=='three_level_treated_neighbor_fraction' and not ref:
                                continue
                            for a in (0,1):
                                for s in exposure.states:
                                    actual=SupportEngine.evaluate(network=net,assignment=adapter,exposure=exposure,
                                        node_id=node,own_treatment_value=a,exposure_value=s).joint_probability
                                    brute=Fraction(0)
                                    for zz in product((0,1),repeat=n):
                                        allocation=dict(zip(ids,zz))
                                        count=sum(allocation[u] for u in ref)
                                        # independent exposure rule, not ExposureSpec.classify
                                        if g=='three_level_treated_neighbor_fraction':
                                            v=(0 if 3*count<len(ref) else 1 if 3*count<2*len(ref) else 2)
                                        else:v=int(count>len(ref)//2)
                                        if allocation[node]==a and v==s:
                                            brute+=adapter.full_assignment_probability(net,allocation)
                                    self.assertEqual(actual,brute,(n,trial,design.kind,g,node,a,s))
                                    checked+=1
        self.assertGreater(checked,750)

if __name__=='__main__':unittest.main()
