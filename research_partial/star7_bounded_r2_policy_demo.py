"""Isolated Star7 policy-value identified-set *research demonstration*.

Not a production PARTIAL certificate. Under an explicitly stipulated bounded
outcome [0,1], mean-signature sufficiency, known D2 complete-randomized q and
population arm means for supported signatures, sharp policy-value bounds have
an analytic formula. A pair of observationally equivalent worlds attains both
endpoints. Exact support is checked by the existing engine AND independent
complete-vector enumeration, with no individual outcome samples or estimation.
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, CompleteRandomizationDesignV1,
)
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)

STEM = 'CFM_ID_Star7_Research_Only_Bounded_Policy_Partial'
NODES = ('hub',) + tuple(f'leaf{i}' for i in range(1,7))


def support_table():
    graph=NetworkExposureSpec(network_id='RESEARCH_ONLY_STAR7',node_ids=list(NODES),
        undirected_edges=[('hub',x) for x in NODES[1:]])
    q=AssignmentSpec(CompleteRandomizationDesignV1(m=3))
    exposure=ExposureSpec('strict_majority_ties_low')
    # Independent oracle does NOT call SupportEngine or its underlying count law.
    total=0
    brute={n:0 for n in NODES}
    for treated in combinations(NODES,3):
        total+=1
        treated=set(treated)
        for n in NODES:
            neighbors=(NODES[1:] if n=='hub' else ('hub',))
            if n in treated and 2*sum(x in treated for x in neighbors)>len(neighbors):
                brute[n]+=1
    out={}
    for n in NODES:
        exact=SupportEngine.evaluate(network=graph,assignment=q,exposure=exposure,
            node_id=n,own_treatment_value=1,exposure_value=1).joint_probability
        independently=Fraction(brute[n],total)
        if exact!=independently:
            raise AssertionError(f'Support engine / full enumeration discrepancy at {n}')
        out[n]=str(exact)
    assert total==35
    return out


def bound_for_leaves(leaf_means):
    """Bound assuming exact observed leaf signature means, outcome in [0,1]."""
    if set(leaf_means)!=set(NODES[1:]):
        raise ValueError('Exactly the six leaf conditional population means are required')
    if any(not (Fraction(0)<=Fraction(v)<=Fraction(1)) for v in leaf_means.values()):
        raise ValueError('Bounded outcome support [0,1] required; leaf means must comply')
    support=support_table()
    if support['hub']!='0' or any(Fraction(s)<=0 for n,s in support.items() if n!='hub'):
        raise AssertionError('Expected supported-leaf / unsupported-hub design boundary absent')
    s=sum((Fraction(v) for v in leaf_means.values()),Fraction(0))
    return s/7,(s+1)/7


def world_outcome(node,assignment,center_unknown_signature_mean):
    """Deterministic potential outcomes for compatible witness worlds.

    Both worlds agree on EVERY assignment the D2 design can produce, because
    treated hub + majority treated neighbors needs >=5 treated (D2 has 3).
    Other node/signature means are fixed at 1/2.
    """
    if not Fraction(0)<=center_unknown_signature_mean<=Fraction(1):
        raise ValueError('Outcome must remain in [0,1]')
    treated=set(assignment)
    if node=='hub' and node in treated and sum(x in treated for x in NODES[1:])>=4:
        return center_unknown_signature_mean
    return Fraction(1,2)


def witness_checks():
    worlds=(Fraction(0),Fraction(1))
    for treated in combinations(NODES,3):
        for node in NODES:
            if world_outcome(node,treated,worlds[0]) != world_outcome(node,treated,worlds[1]):
                raise AssertionError('Counterexample worlds disagree on an observable assignment')
    all_treated=NODES
    valuations=[sum((world_outcome(i,all_treated,v) for i in NODES),Fraction(0))/7 for v in worlds]
    assert valuations==[Fraction(3,7),Fraction(4,7)]
    return [str(v) for v in valuations]


def generate():
    support=support_table()
    # Purely synthetic example. These are NOT recovered population operators.
    illustrative={leaf:Fraction(1,2) for leaf in NODES[1:]}
    lo,hi=bound_for_leaves(illustrative)
    worlds=witness_checks()
    if [str(lo),str(hi)]!=worlds:
        raise AssertionError('Analytic bounds and sharpness witnesses disagree')
    return dict(schema_version='RESEARCH_PARTIAL_NOT_FORMAL_BACKEND',status='RESEARCH_ONLY',
        formally_certified_partial=False,production_route=None,
        business_question='固定三人试用的 Star7 员工协作网：全员启用 AI 的平均结果值域',
        network='seven-node pretreatment fixed undirected star',
        design='D2 exactly three treated among seven; uniform over 35 assignments',
        target='V(1_7)=1/7 Σ_i E[Y_i(1_7)|W]',
        assumptions=['full-vector randomization','consistency','fixed pretreatment network',
             'mean-signature sufficiency for E1 strict-majority exposure',
             'bounded outcome Y_i(z) in [0,1] for ALL relevant policies',
             'population arm means exactly known for supported leaf signatures',
             'NO other cross-node or cross-signature shape restrictions'],
        missing_signature='hub: own=1 and strict-majority treated neighbors=1',
        exact_signature_support=support,
        symbolic_lower='(Σ_{leaf i} μ_i(1,1))/7',
        symbolic_upper='(Σ_{leaf i} μ_i(1,1) + 1)/7',
        sharp_width='1/7',
        illustrative_leaf_means='1/2 for each leaf, hypothetical only',
        illustrative_interval=[str(lo),str(hi)],
        counterexample_world_policy_values=worlds,
        note='Independently matching observed randomization laws do not distinguish the hub potential outcome at the impossible signature. NOT a production PARTIAL engine. NOT a real estimate.')


def run(outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    path=outdir/(STEM+'.json')
    path.write_text(json.dumps(generate(),sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return path

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default='research_partial/output');args=ap.parse_args()
    p=run(Path(args.output_dir));print('RESEARCH ONLY:',p)
