"""A1/A4/A5/A6 non-arm study entry demonstration, WITHOUT a fake arm.

    python -B -m examples.run_nonarm_network_inquiry_shadow
    python -B -m examples.run_nonarm_network_inquiry_shadow --er300

Fixed policy and observational inquiries are constructed from an explicit
independent study. Existing arm TaskSpec is used only for a separate *legacy
regression check*, not as a policy inquiry input or source anchor.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_route_shadow import FIXED_POLICY_CANDIDATE
from pfn_pipeline.network_inquiry_shadow import (
    OBSERVATIONAL_CANDIDATE, declare_network_study, fixed_policy_target_from_context,
    declare_network_a4_source, assess_nonarm_network_inquiry,
    replay_nonarm_network_inquiry, study_from_legacy_arm,
)


def network(er300=False):
    if not er300:
        return 'route-v15-toy3',('0','1','2'),(('0','1'),('0','2'))
    import numpy as np
    from pfn_pipeline.simulation import load_graph
    from pfn_pipeline._internal.paths import DEFAULT_GRAPH
    adjacency=load_graph(DEFAULT_GRAPH)
    ids=tuple(f'node-{i}' for i in range(adjacency.shape[0]))
    edges=tuple((ids[int(i)],ids[int(j)]) for i,j in zip(*np.where(np.triu(adjacency,1)==1)))
    return 'a4-shadow-shared-ER300',ids,edges


def make_study(*,er300=False,observational=False):
    name,nodes,edges=network(er300)
    return declare_network_study(
        network_id=name,node_order=nodes,undirected_edges=edges,
        treatment_variable='treatment',outcome_variable='outcome',outcome_kind='continuous',
        context_reference='W',
        observation_regime='observational' if observational else 'experimental',
        assignment_design=None if observational else {
            'kind':'heterogeneous_bernoulli_binary_v1',
            'propensities':{n:'1/2' for n in nodes}},
        protocol_provenance=('research fixture: observational design not certified'
                             if observational else 'reviewed synthetic iid Bernoulli(.5) protocol fixture'),
        network_provenance='fixed graph fixture for testing, not a factual certification',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def assumptions():
    from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED
    return tuple(Assumption(name=name,source='demo_specification',confirmed=True,
                            evidence=['reviewed synthetic fixture']) for name in REQUIRED)


def source(study,kind='ASSIGNMENT_NODE_MEANS'):
    z=(0,)*len(study.node_order)
    return declare_network_a4_source(study,
        source_id=f'reviewed:{kind}', operator=kind,
        provenance='symbolic population information for test only; no external population data',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=study.node_order,assignment_cells=(z,) if kind=='ASSIGNMENT_NODE_MEANS' else (),
        exposure_fingerprint='g:unrelated-demo' if kind=='NODE_ARM_MEANS' else None)


def case(study, *, family, kind='ASSIGNMENT_NODE_MEANS',ass=()):
    z=(0,)*len(study.node_order)
    target=fixed_policy_target_from_context(study,z,authority='TRUSTED_FIXTURE')
    src=source(study,kind)
    result=assess_nonarm_network_inquiry(study,target,(src,),family_id=family,assumptions=ass)
    assert replay_nonarm_network_inquiry(study,target,(src,),result,assumptions=ass)
    return dict(target_digest=target.target_digest,
                study_digest=study.study_digest,
                scope_digest=study.shared_scope_digest,
                protocol_digest=study.protocol_digest,
                route_status=result.route_status,
                information_status=result.information_status,
                assumption_status=result.assumption_status,
                validity_status=result.validity_status,
                backend_capability=result.backend_capability,
                declared_q_of_policy=result.policy_assignment_probability,
                required_observable=asdict(result.required_observable),
                blockers=result.blockers,
                replay_digest=result.digest,
                mathematical_identification_from_router=result.mathematical_identification_from_router)


def run(er300=False):
    experimental=make_study(er300=er300)
    observational=make_study(er300=er300,observational=True)
    positive=case(experimental,family=FIXED_POLICY_CANDIDATE,ass=assumptions())
    arm_only=case(experimental,family=FIXED_POLICY_CANDIDATE,kind='NODE_ARM_MEANS',ass=assumptions())
    observed=case(observational,family=OBSERVATIONAL_CANDIDATE,ass=())
    assert positive['route_status']=='THEOREM_BACKEND_UNAVAILABLE'
    assert positive['information_status']=='SATISFIED'
    assert arm_only['route_status']=='INFORMATION_BLOCKED'
    assert observed['route_status']=='THEOREM_BACKEND_UNAVAILABLE'
    assert observed['assumption_status']=='NO_REGISTERED_OBSERVATIONAL_THEOREM'
    assert positive['scope_digest']==observed['scope_digest']
    assert positive['protocol_digest']!=observed['protocol_digest']
    assert positive['target_digest']==observed['target_digest']==arm_only['target_digest']

    # Old randomized-network arm is only a regression fixture; policy/observational
    # inquiries above used NO TaskSpec and NO exposure definition.
    from examples.run_family_route_assessment_shadow import task as legacy_task, source as legacy_source
    from pfn_pipeline.identification import identify
    from pfn_pipeline.identification_route_shadow import arm_target_from_task, assess_family_route, ARM_FAMILY
    old_task=legacy_task(er300)
    projected=study_from_legacy_arm(old_task)
    assert projected.network_fingerprint==experimental.network_fingerprint
    assert projected.shared_scope_digest==experimental.shared_scope_digest
    previous=identify(old_task)
    old_shadow=assess_family_route(old_task,arm_target_from_task(old_task),
                                   (legacy_source(old_task),),family_id=ARM_FAMILY)
    assert previous.status=='POINT'
    assert previous.verification_status=='VERIFIED'
    assert old_shadow.route_status=='CANDIDATE_READY'
    return {'version':'v1.7','node_count':len(experimental.node_order),
            'case_fixed_policy_assignment_info':positive,
            'case_fixed_policy_arm_only_info':arm_only,
            'case_observational_policy':observed,
            'legacy_arm_regression':{
                'status':previous.status.value if hasattr(previous.status,'value') else str(previous.status),
                'verification':previous.verification_status.value if hasattr(previous.verification_status,'value') else str(previous.verification_status),
                'route_status':old_shadow.route_status,
                'source_network_fingerprint_matches':True,
            },
            'no_fake_arm_for_nonarm_cases':True,
            'no_PFN_invoked':True,
            'no_new_causal_theorem':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--er300',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run(args.er300)
    if args.output:
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'nodes':result['node_count'],
        'fixed_policy':result['case_fixed_policy_assignment_info']['route_status'],
        'arm_only':result['case_fixed_policy_arm_only_info']['route_status'],
        'observational':result['case_observational_policy']['route_status'],
        'legacy_arm':result['legacy_arm_regression']},indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
