"""Demonstrate non-authoritative A1/A4/A5/A6 network-family route assessment.

Small: python -B -m examples.run_family_route_assessment_shadow
ER300: python -B -m examples.run_family_route_assessment_shadow --er300
"""
from __future__ import annotations
import argparse
import copy
from dataclasses import replace
from dataclasses import asdict
from pathlib import Path
import json

from pfn_pipeline import make_heterogeneous_bernoulli_arm_task, make_complete_randomization_arm_task
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_route_shadow import (
    ARM_FAMILY,FIXED_POLICY_CANDIDATE,arm_target_from_task,fixed_policy_target_from_study,
    assess_family_route,replay_family_route,family_catalog,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec


def task(er300=False, fixed_quota=False):
    if er300:
        import numpy as np
        from pfn_pipeline.simulation import load_graph
        from pfn_pipeline._internal.paths import DEFAULT_GRAPH
        adj=load_graph(DEFAULT_GRAPH)
        nodes=tuple('node-'+str(i) for i in range(adj.shape[0]))
        edges=[(nodes[int(i)],nodes[int(j)]) for i,j in zip(*np.where(np.triu(adj,1)==1))]
        net=NetworkExposureSpec(network_id='a4-shadow-shared-ER300', node_ids=list(nodes),undirected_edges=edges)
    else:
        net=NetworkExposureSpec(network_id='route-v15-toy3',node_ids=['0','1','2'],
                                undirected_edges=[('0','1'),('0','2')])
    kw=dict(node_id=net.node_ids[0],own_treatment_value=1,exposure_value=1,
            source='reviewed experimental protocol', evidence='admitted randomized design',
            admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
    if fixed_quota:
        return make_complete_randomization_arm_task(net,m=2,**kw)
    return make_heterogeneous_bernoulli_arm_task(net,propensities={n:'1/2' for n in net.node_ids},**kw)


def source(task,kind='NODE_ARM_MEANS', *, source_id='reviewed:source', assignment_cells=()):
    q=task.identification_spec['query']
    return declare_a4_source(task,source_id=source_id,operator=kind,
       provenance='human-reviewed population-observable declaration',
       admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
       outcome_nodes=task.node_ids,node_order=task.node_ids,
       arm_cells=((q['target_node_id'],q['own_treatment_value'],q['exposure_value']),)
                 if kind=='NODE_ARM_MEANS' else (),
       assignment_cells=assignment_cells)


def compact(r):
    return dict(target_digest=r.target_digest,target_authority=r.target_authority,
                target_resolution=r.target_resolution,route_status=r.route_status,
                target_match=r.target_match,information_status=r.information_status,
                assumption_status=r.assumption_status,validity_status=r.validity_status,
                backend_capability=r.backend_capability,
                observable=asdict(r.required_observable) if r.required_observable else None,
                sources=[asdict(x) for x in r.source_results],
                blockers=list(r.blockers),legacy_status=r.current_legacy_status,
                legacy_verification=r.current_legacy_verification,
                legacy_reason=r.current_legacy_reason,
                router_issues_causal_result=r.mathematical_identification_from_router is not None,
                replay_digest=r.digest)


def run(er300=False):
    t=task(er300)
    a=arm_target_from_task(t)
    s=source(t)
    r=assess_family_route(t,a,(s,),family_id=ARM_FAMILY)
    assert replay_family_route(t,a,(s,),r)
    report={'version':'v1.5','network_size':len(t.node_ids),
            'existing_arm':compact(r),'pfns_invoked':False,
            'family_catalog':[asdict(f) for f in family_catalog()]}
    if not er300:
        # Same scientific target, change only population observable granularity.
        z=(0,)*len(t.node_ids)
        policy=fixed_policy_target_from_study(t,z,authority='TRUSTED_FIXTURE')
        complete=source(t,'ASSIGNMENT_NODE_MEANS',source_id='assignment:source',assignment_cells=(z,))
        arm=source(t,source_id='arm:source')
        ra=assess_family_route(t,policy,(complete,),family_id=FIXED_POLICY_CANDIDATE)
        rb=assess_family_route(t,policy,(arm,),family_id=FIXED_POLICY_CANDIDATE)
        assert replay_family_route(t,policy,(complete,),ra)
        assert replay_family_route(t,policy,(arm,),rb)
        assert ra.target_digest==rb.target_digest
        report['fixed_policy_assignment_info']=compact(ra)
        report['same_fixed_policy_arm_only_info']=compact(rb)

        # Previous A4 false-positive / false-negative probes.
        weak=copy.deepcopy(t.identification_spec)
        weak['information_signature']['objects'][0].update(
            joint_scope='node_local_marginals_only',whole_network_assignment_law_available=False,
            description='pairwise marginals, NOT full arm mean')
        weak=replace(t,identification_spec=weak)
        weak_source=source(weak,'PAIRWISE_MARGINALS')
        w=assess_family_route(weak,arm_target_from_task(weak),(weak_source,),family_id=ARM_FAMILY)
        report['legacy_weak_information_false_positive']=compact(w)
        strong=copy.deepcopy(t.identification_spec)
        strong['information_signature']['objects'][0].update(
            name='P(T_vector,Y_vector|W)',variables=['treatment','outcome','context'],
            basis='WHOLE_NETWORK_ASSIGNMENT_LAW_V1',joint_scope='whole_network_assignment',
            outcome_representation='full_joint_law',whole_network_assignment_law_available=True)
        strong=replace(t,identification_spec=strong)
        strong_source=source(strong,'FULL_JOINT_LAW')
        st=assess_family_route(strong,arm_target_from_task(strong),(strong_source,),family_id=ARM_FAMILY)
        report['legacy_strong_information_false_negative']=compact(st)

        # Fixed-quota off-support policy does not become an undefined causal target.
        qt=task(fixed_quota=True)
        target=fixed_policy_target_from_study(qt,(1,1,1),authority='TRUSTED_FIXTURE')
        oq=assess_family_route(qt,target,(source(qt,'FULL_JOINT_LAW'),),family_id=FIXED_POLICY_CANDIDATE)
        report['off_support_fixed_policy']=compact(oq)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--er300',action='store_true')
    p.add_argument('--output',type=Path,default=None)
    args=p.parse_args()
    result=run(args.er300)
    if args.output:
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:(v['route_status'] if isinstance(v,dict) and 'route_status' in v else v)
                      for k,v in result.items() if k not in ('family_catalog',)},indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
