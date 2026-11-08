"""R2 verified policy demo: finite-sample values and simulator truth are NEVER read.

  python -B -m examples.run_verified_r2_signature_policy
  python -B -m examples.run_verified_r2_signature_policy --er300 --output /tmp/r2.json
  python -B -m examples.run_verified_r2_signature_policy --er300-baseline

The ER300 off-support experiment is a *hypothetical D2 protocol on the shared
ER300 graph*, NOT the existing shared Bernoulli(.5) Estimation protocol.
"""
from __future__ import annotations
import argparse
import json
from fractions import Fraction
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED
from pfn_pipeline.identification_policy_r2 import (
    identify_verified_signature_policy,replay_verified_signature_policy,
    declare_policy_signature,admit_mean_signature_sufficiency,
    declare_signature_population_source,R2PolicyUnavailable,
)
from pfn_pipeline.identification_policy_r1b import identify_verified_fixed_policy,R1bPolicyUnavailable
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study,declare_network_a4_source,fixed_policy_target_from_context,
)
from examples.run_nonarm_network_inquiry_shadow import make_study


def assumptions():
    return tuple(Assumption(name=n,source='demo_specification',confirmed=True,
            evidence=['independently reviewed synthetic experimental protocol']) for n in REQUIRED)


def star_study():
    nodes=('hub','leaf1','leaf2','leaf3','leaf4')
    return declare_network_study(
        network_id='r2-star5-offsupport',node_order=nodes,
        undirected_edges=tuple(('hub',n) for n in nodes[1:]),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W',observation_regime='experimental',
        assignment_design={'kind':'complete_randomization_binary_v1','m':4},
        protocol_provenance='hypothetical fixed-quota toy fixture, NOT an actual experiment',
        network_provenance='declared fixed star network',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def shared_er300_d2_study():
    base=make_study(er300=True)
    return declare_network_study(
        network_id=base.network_id,node_order=base.node_order,
        undirected_edges=base.undirected_edges,
        treatment_variable=base.treatment_variable,outcome_variable=base.outcome_variable,
        outcome_kind=base.outcome_kind,context_reference=base.context_reference,
        observation_regime='experimental',
        assignment_design={'kind':'complete_randomization_binary_v1','m':150},
        protocol_provenance=('HYPOTHETICAL fixed-quota D2 protocol on original shared ER300 graph; '
                             'not the shared iid Bernoulli experiment'),
        network_provenance='existing shared ER300 fixed graph file',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def case(study):
    z=(1,)*len(study.node_order)
    target=fixed_policy_target_from_context(study,z,authority='TRUSTED_FIXTURE')
    signature=declare_policy_signature(study,grouping='strict_majority_ties_low')
    # The source declares ONLY the queried node-class coordinates, not every
    # logically possible arm (some would have zero support and be undefined).
    degrees=study.network().degree_map()
    cells=tuple((node,1,int(degrees[node]>0)) for node in study.node_order)
    source=declare_signature_population_source(study,signature,
            source_id='reviewed-symbolic-node-signature-means',operator='NODE_SIGNATURE_MEANS',
            outcome_nodes=study.node_order,signature_cells=cells,
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            provenance='explicit reviewed symbolic population operator, no outcome values')
    suff=admit_mean_signature_sufficiency(study,signature,
        assumption=Assumption(name='mean_signature_sufficiency',source='demo_specification',
           confirmed=True,status='ADMITTED',evidence=[
             'RESEARCH FIXTURE: conditionally identical MEAN outcomes for every full allocation sharing (T_i,S_i)']),
        covered_nodes=study.node_order)
    result=identify_verified_signature_policy(study,target,signature,(source,),
             assumptions=assumptions(),sufficiency=suff)
    assert replay_verified_signature_policy(result)
    # q(all treated)==0 here; the stronger A5 claim is essential.
    # Contrast the same Q under R1b's weaker A5 but stronger A4 requirements.
    # In D2 q(z)=0, R1b must refuse; under baseline Bernoulli q(z)>0 it may work.

    assignment_source=declare_network_a4_source(study,source_id='declared-full-law',
        operator='NODE_FULL_LAW',provenance='hypothetical symbolic population full law',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=study.node_order)
    try:
        fixed=identify_verified_fixed_policy(study,target,(assignment_source,),assumptions=assumptions())
    except R1bPolicyUnavailable as exc:
        if result.policy_assignment_probability!='0':
            raise AssertionError('R1b unexpectedly refused a supported policy') from exc
        r1b_comparison=exc.reason_code
    else:
        if result.policy_assignment_probability=='0':
            raise AssertionError('R1b must refuse q(z)=0')
        if fixed.target_fingerprint!=result.target_fingerprint:
            raise AssertionError('Same policy Q must have same scientific target identity')
        r1b_comparison='POINT / VERIFIED'
    # An unconfirmed structural condition cannot be used by R2.
    proposed=admit_mean_signature_sufficiency(study,signature,
        assumption=Assumption(name='mean_signature_sufficiency',source='llm_candidate',
            status='PROPOSED',confirmed=False,evidence=['LLM suggested majority']),
        covered_nodes=study.node_order)
    try:
        identify_verified_signature_policy(study,target,signature,(source,),
                  assumptions=assumptions(),sufficiency=proposed)
    except R2PolicyUnavailable as exc:
        r2_refusal=exc.reason_code
    else:
        raise AssertionError('R2 must refuse unadmitted structural sufficiency')
    probabilities=[Fraction(item) for item in result.node_class_support]
    return {
        'support_summary': {'minimum_approx':float(min(probabilities)),
                            'maximum_approx':float(max(probabilities)),
                            'mean_approx':float(sum(probabilities)/len(probabilities)),
                            'note':'Presentation-only float summaries; exact Fraction proofs remain in result'},
        'study':('shared ER300 original iid Bernoulli(1/2) protocol'
                 if len(study.node_order)==300 and result.policy_assignment_probability!='0'
                 else 'shared ER300 graph with HYPOTHETICAL D2 150/300 fixed quota'
                 if len(study.node_order)==300 else '5-node star D2 4/5 fixed quota'),
        'node_count':len(study.node_order),
        'policy':'all treated',
        'result':result.summary(),
        'replay':True,
        'contrast':{'R1b_result':r1b_comparison,'R2_proposed_A5_refusal':r2_refusal},
        'A4_note':'reviewed SYMBOLIC population operator; not measured means or a numeric effect',
        'assumption_note':'A5 mean-signature sufficiency is an explicit SYNTHETIC assumption, not data-verified',
        'numeric_policy_welfare':None,
        'pfn_used':False,
    }


def main():
    p=argparse.ArgumentParser();p.add_argument('--er300',action='store_true')
    p.add_argument('--er300-baseline',action='store_true');p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.er300 and args.er300_baseline: p.error('Choose only one ER300 design')
    data=case(make_study(er300=True) if args.er300_baseline else
              shared_er300_d2_study() if args.er300 else star_study())
    if args.output: args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'study':data['study'],'nodes':data['node_count'],
         'R2_status':data['result']['status'],'replay':data['replay'],
         'full_assignment_q':data['result']['full_assignment_probability'],
         'supported_signature_classes':len(data['result']['node_classes']),
         'first_three_classes':data['result']['node_classes'][:3],
         'signature_support_summary':data['support_summary'],
         'safe_refusals':data['contrast'],'no_numeric_welfare':True},
         ensure_ascii=False,indent=2))

if __name__=='__main__': main()
