"""Verified R1b fixed policy population Identification demonstration.

Run:
    python -B -m examples.run_verified_r1b_fixed_policy
    python -B -m examples.run_verified_r1b_fixed_policy --er300
    python -B -m examples.run_verified_r1b_fixed_policy --er300 --output /tmp/r1b.json

Only a *declared symbolic population observable* is used. This does not claim
that one ER300 trial supplies a reliable numerical full-assignment outcome mean.
No PFN, simulated outcome truth or policy optimizer is called.
"""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json

from pfn_pipeline.identification_policy_r1b import (
    R1bPolicyUnavailable, identify_verified_fixed_policy, replay_verified_fixed_policy,
    identify_verified_finite_policy_mixture, replay_verified_finite_policy_mixture,
)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_a4_source, fixed_policy_target_from_context,
)
from examples.run_nonarm_network_inquiry_shadow import make_study, assumptions


def make_source(study,*,operator='NODE_FULL_LAW',policy=(),source_id='reviewed:symbolic-full-network-law'):
    # This is a demonstration declaration, not empirical measured population data.
    return declare_network_a4_source(
        study,source_id=source_id,operator=operator,
        provenance='explicit symbolic population information fixture; no causal outcomes supplied',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=study.node_order,
        assignment_cells=(tuple(policy),) if operator=='ASSIGNMENT_NODE_MEANS' else (),
        exposure_fingerprint='demo-arm-g' if operator=='NODE_ARM_MEANS' else None)


def run(*,er300=False) -> dict:
    study=make_study(er300=er300)
    z=(1,)*len(study.node_order)
    target=fixed_policy_target_from_context(study,z,authority='TRUSTED_FIXTURE')
    full_source=make_source(study,policy=z)
    result=identify_verified_fixed_policy(study,target,(full_source,),assumptions=assumptions())
    assert replay_verified_fixed_policy(result)
    # A small stochastic policy with two explicitly listed, q-supported assignments.
    # This is a finite mixture of the same theorem, not a universal stochastic kernel.
    z0=(0,)*len(study.node_order)
    no_ai=fixed_policy_target_from_context(study,z0,authority='TRUSTED_FIXTURE')
    no_ai_result=identify_verified_fixed_policy(study,no_ai,(full_source,),assumptions=assumptions())
    finite_mixture=identify_verified_finite_policy_mixture(
        (result,no_ai_result),policy_probabilities=('1/4','3/4'))
    assert replay_verified_finite_policy_mixture(finite_mixture)

    # Same Q, weaker A4 information: cannot infer a full treatment-cell mean.
    refused=[]
    for what,src,aa in (
        ('arm_only_information',make_source(study,operator='NODE_ARM_MEANS'),assumptions()),
        ('unconfirmed_randomization',full_source,tuple(a for a in assumptions()
                                                 if a.name!='full_vector_randomization')),
    ):
        try:
            identify_verified_fixed_policy(study,target,(src,),assumptions=aa)
        except R1bPolicyUnavailable as err:
            refused.append({'case':what,'reason_code':err.reason_code})
        else:
            raise AssertionError(f'Expected the {what} scenario to be refused')

    return {
        'release':'R1b v1.9',
        'network':'shared fixed ER300' if er300 else 'toy three-node star',
        'node_count':len(study.node_order),
        'target':'actual fixed full-assignment mean, all treated',
        'point_result':result.summary(),
        'finite_stochastic_policy_result':finite_mixture.summary(),
        'result_replay_success':True,
        'safe_rejections':refused,
        'numeric_outcome_value':None,
        'a4_declaration':'SYMBOLIC_POPULATION_OPERATOR, not a measured population value',
        'no_exposure_sufficiency_assumed':True,
        'no_estimator_or_pfn_called':True,
        'finite_sample_warning':('An extremely small q(z)>0 proves population support, '
                                'but does not imply the full policy outcome is estimable '
                                'with usable precision from a single ER300 experiment.'),
    }


def main():
    parser=ArgumentParser()
    parser.add_argument('--er300',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    data=run(er300=args.er300)
    if args.output:
        args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    d=data['point_result']
    print(json.dumps({'network':data['network'],'nodes':data['node_count'],
          'status':d['status'],'verification':d['verification_status'],
          'q_full_policy':d['assignment_probability'],
          'a4_rule':d['a4_rule_id'],
          'certificate':d['certificate_sha256'],
          'nonzero_policy_nodes':len(d['nonzero_node_weights']),
          'finite_stochastic_policy':data['finite_stochastic_policy_result']['status'],
          'finite_policy_atoms':len(data['finite_stochastic_policy_result']['policy_support']),
          'safe_rejections':data['safe_rejections'],
          'no_numeric_policy_value_computed':True},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
