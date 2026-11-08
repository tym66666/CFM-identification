"""One observational R3 target under three equivalent symbolic A4 representations.

Developer-only minimal ablation: 3-node path; ONE p-standardized Direct target;
full enumerated p(T), independent Bernoulli p(T), one-component mixture p(T).
No real observed outcomes, estimator, or automatic scientific assumption approval.
"""
from __future__ import annotations
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import argparse
import json
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26, identify_network_business_query,
    replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline.identification_observational_factorized_a4 import (
    declare_observational_factorized_arm_population_v27p1,
)
from pfn_pipeline.identification_observational_mixture_a4 import (
    declare_observational_mixture_arm_population_v28p1,
)
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_r3_target_a4_audit import (
    compare_r3_target_a4_v28p0,
)
from pfn_pipeline.network_inquiry_shadow import declare_network_study


def _setup():
    st=declare_network_study(network_id='R3-ablation-3node',
        node_order=('n0','n1','n2'),undirected_edges=(('n0','n1'),('n1','n2')),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W=w0',observation_regime='observational',assignment_design=None,
        protocol_provenance='synthetic only; no real observational assignment evidence',
        network_provenance='fixed pre-treatment path',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    sig=declare_policy_signature(st,grouping='strict_majority_ties_low')
    request=EffectQueryV18(kind='DIRECT',node_weights=(('n2',1),),
                           reference_exposure=0,comparison_exposure=0)
    assumptions=tuple(Assumption(name=name,source='demo_specification',confirmed=True,
         evidence=['Synthetic stipulation only; cannot scientifically prove unconfoundedness'])
         for name in ('full_vector_conditional_exchangeability','consistency',
                      'fixed_pretreatment_network','finite_conditional_first_moments'))
    return st,sig,(request,),assumptions


def _run(st,sig,requests,a5,source):
    return identify_network_business_query(ObservationalEffectsInquiryV26(
        st,source,a5,sig,requests))


def generate():
    st,sig,requests,a5=_setup()
    probs=(F(1,4),F(1,2),F(3,4))
    arms=(('n2',0,0),('n2',1,0))
    fact=declare_observational_factorized_arm_population_v27p1(
        st,sig,source_id='independent-population',provenance='synthetic declared population',
        treatment_one_probabilities=probs,covered_arms=arms)
    masses=[]
    for allocation in product((0,1),repeat=3):
        p=F(1)
        for t,q in zip(allocation,probs):
            p*=q if t else 1-q
        masses.append((allocation,p))
    full=declare_observational_population_v23(st,source_id='full-population',
        provenance='synthetic exact full law',assignment_masses=masses)
    mix=declare_observational_mixture_arm_population_v28p1(
        st,sig,source_id='mixture-population',provenance='synthetic mixture source',
        components=((F(1),probs),),covered_arms=arms)
    outcomes={key:_run(st,sig,requests,a5,src) for key,src in
              (('full',full),('factorized',fact),('mixture_single_component',mix))}
    for key,out in outcomes.items():
        if out.status!='POINT' or not replay_verified_business_outcome(out):
            raise AssertionError('R3 ABLATION REQUIRED POINT+REPLAY: '+key)
    base=outcomes['full']
    for key in ('factorized','mixture_single_component'):
        c=compare_r3_target_a4_v28p0(base,outcomes[key])
        if not c.can_merge_as_one_symbolic_target:
            raise AssertionError('R3 EQUIVALENT POPULATION LAW NOT CERTIFIED: '+key)
    support=[out.result.proofs[0].arm_support for out in outcomes.values()]
    if not all(s==('1/8','3/8') for s in support):
        raise AssertionError('R3 LOCAL EXACT SUPPORT MISMATCH '+repr(support))
    different=declare_observational_factorized_arm_population_v27p1(
        st,sig,source_id='different-population',provenance='synthetic law shift',
        treatment_one_probabilities=(F(1,4),F(1,2),F(2,3)),covered_arms=arms)
    distinct=_run(st,sig,requests,a5,different)
    law_conflict=compare_r3_target_a4_v28p0(base,distinct)
    if law_conflict.can_merge_as_one_symbolic_target:
        raise AssertionError('R3 TREATMENT LAW SHIFT MUST NOT MERGE')
    missing_a5=_run(st,sig,requests,tuple(a for a in a5
        if a.name!='full_vector_conditional_exchangeability'),fact)
    sample_only=_run(st,sig,requests,a5,replace(fact,availability='FINITE_SAMPLE_ESTIMATE'))
    if missing_a5.status=='POINT' or sample_only.status=='POINT':
        raise AssertionError('R3 A4/A5 FAIL-CLOSED WAS BYPASSED')
    return {'schema_version':'cfm-id-r3-minimal-representation-ablation-v1',
        'network':'3-node path','target':'R3 p-standardized Direct, node n2, E1 exposure 0',
        'declared_observational_propensities':list(map(str,probs)),
        'support_from_independent_full_enumeration':['1/8','3/8'],
        'representations':{key:{'status':out.status,
            'theorem_replay':replay_verified_business_outcome(out),
            'arm_support':list(out.result.proofs[0].arm_support)} for key,out in outcomes.items()},
        'cross_representation_equivalence':{
            'full_vs_independent':True,'full_vs_one_component_mixture':True,
            'changed_observational_law_must_not_merge':not law_conflict.can_merge_as_one_symbolic_target},
        'ablation':{'remove_exchangeability':missing_a5.status,
                    'replace_A4_with_sample_only':sample_only.status},
        'scientific_assumptions_verified_in_real_world':False,
        'estimation_performed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report=generate()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('R3 minimal representation ablation PASS, output',args.output)

if __name__=='__main__':
    main()
