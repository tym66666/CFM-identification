"""v2.2 cross-topology acceptance on deterministic graphs, not an ER generator.

All networks are fixed simple undirected pre-treatment graphs. The declared
synthetic population A4 operators are *not* observed outcomes. Graph generator
names describe test shapes only; random topology parameters never enter ID.

  python -B -m examples.run_network_topology_matrix --output my.json
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

from pfn_pipeline import (
    make_heterogeneous_bernoulli_arm_task, make_complete_randomization_arm_task,
    make_two_group_quota_arm_task, identify, replay_population_identification,
    FixedPolicyInquiryV21, identify_network_business_query,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec, Assumption
from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context, declare_network_a4_source,
)
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, declare_signature_population_source,
    admit_mean_signature_sufficiency,
)


def topologies():
    """Nine explicit deterministic graphs, including isolates; no graph sampling."""
    n=7;nodes=[str(i) for i in range(n)]
    edges={
       'path':[(str(i),str(i+1)) for i in range(n-1)],
       'ring':[(str(i),str((i+1)%n)) for i in range(n)],
       'star':[('0',str(i)) for i in range(1,n)],
       'complete':[(str(i),str(j)) for i in range(n) for j in range(i+1,n)],
       'bipartite':[(str(i),str(j)) for i in range(3) for j in range(3,n)],
       'community':([(str(i),str(j)) for i in range(3) for j in range(i+1,3)]
                    +[(str(i),str(j)) for i in range(3,n) for j in range(i+1,n)]+[('1','4')]),
       'small_world_like':([(str(i),str((i+1)%n)) for i in range(n)]+[('0','3'),('2','5')]),
       'hub_scale_free_like':([('0',str(i)) for i in range(1,n)]+[('1','2'),('1','3'),('2','4')]),
       'disconnected_with_isolate':([('0','1'),('1','2'),('2','0'),('3','4'),('4','5')]),
    }
    return [(key,NetworkExposureSpec(network_id='v22-topology-'+key,node_ids=nodes,
             undirected_edges=value)) for key,value in edges.items()]


def _task(net,design,expo,node,a,s):
    common=dict(network=net,node_id=node,own_treatment_value=a,exposure_value=s,
       source='explicit v2.2 topology fixture',
       evidence='hypothetical known randomized study; no empirical outcomes',
       admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE',
       exposure_definition={'E1':'strict_majority','E2':'three_level_treated_neighbor_fraction',
                            'E3':'pretreatment_core_collaborator_majority'}[expo])
    if expo=='E3':
        neighbors={k:[] for k in net.node_ids}
        for x,y in net.undirected_edges:neighbors[x].append(y);neighbors[y].append(x)
        if any(not values for values in neighbors.values()):
            raise ValueError('E3_UNDEFINED_FOR_ISOLATE')
        common['core_collaborators']={k:(sorted(values)[0],) for k,values in neighbors.items()}
    if design=='D1':
        return make_heterogeneous_bernoulli_arm_task(**common,
                propensities={n:'1/2' for n in net.node_ids})
    if design=='D2':
        return make_complete_randomization_arm_task(**common,m=3)
    return make_two_group_quota_arm_task(**common,
        groups=(tuple(net.node_ids[:3]),tuple(net.node_ids[3:])),treated_quotas=(1,2))


def _study(net,*, m=3):
    return declare_network_study(network_id=net.network_id,node_order=tuple(net.node_ids),
        undirected_edges=tuple(net.undirected_edges),treatment_variable='AI',
        outcome_variable='sales',outcome_kind='continuous',context_reference='W',
        observation_regime='experimental',assignment_design={
            'kind':'complete_randomization_binary_v1','m':m},
        protocol_provenance='v2.2 HYPOTHETICAL randomized quota study',
        network_provenance='deterministic known network fixture',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def _r2_on_alltreated(net):
    # R1b has q(z)=0 under fixed quota of 3/7. R2 may or may not have
    # each node-class supported, depending on the graph degree/topology.
    study=_study(net)
    z=(1,)*len(net.node_ids)
    target=fixed_policy_target_from_context(study,z,authority='TRUSTED_FIXTURE')
    full=declare_network_a4_source(study,source_id='topology-v22-assignment-law',
        operator='NODE_FULL_LAW',provenance='symbolic full-law fixture',admission='ADMITTED',
        availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=study.node_order)
    assumptions=tuple(Assumption(name=n,source='demo_specification',confirmed=True,
         evidence=['hypothetical known q and full-vector randomization']) for n in REQUIRED)
    blocked=identify_network_business_query(FixedPolicyInquiryV21(
         study,target,assumptions,r1b_sources=(full,)))
    if blocked.status=='POINT':
        raise AssertionError('D2 3/7 alltreated must be off-support')
    sig=declare_policy_signature(study,grouping='strict_majority_ties_low')
    neighbors={n:[] for n in study.node_order}
    for i,j in net.undirected_edges:neighbors[i].append(j);neighbors[j].append(i)
    cells=tuple((n,1,int(bool(neighbors[n]))) for n in study.node_order)
    source=declare_signature_population_source(study,sig,
        source_id='topology-v22-signature-population',operator='NODE_SIGNATURE_MEANS',
        provenance='synthetic conditional population signature means',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=study.node_order,signature_cells=cells)
    suff=admit_mean_signature_sufficiency(study,sig,
         assumption=Assumption(name='mean_signature_sufficiency',
             source='demo_specification',confirmed=True,status='ADMITTED',
             evidence=['explicit hypothetical equality of all signature-class means']),
         covered_nodes=study.node_order)
    r2=identify_network_business_query(FixedPolicyInquiryV21(study,target,assumptions,
         r1b_sources=(full,),r2_signature=sig,r2_sufficiency=suff,
         r2_sources=(source,)))
    return dict(r1b_status=blocked.status,r1b_reason=blocked.reason_code,
         r2_status=r2.status,r2_route=r2.route,r2_reason=r2.reason_code,
         note='R2 assumes mean sufficiency: synthetic A5 explicitly, no numeric outcomes')


def run_topology_matrix():
    records=[];totals=Counter()
    for label,network in topologies():
        graph={'name':label,'node_count':len(network.node_ids),
               'edge_count':len(network.undirected_edges),
               'isolates':sum(d==0 for d in network.degree_map().values()),
               'max_degree':max(network.degree_map().values()),
               'graph_sha256':network.semantic_fingerprint(),
               'design_exposure':[]}
        for design in ('D1','D2','D3'):
            for expo in ('E1','E2','E3'):
                result=None;last_reason=None
                if expo=='E2' and graph['isolates']>0:
                    graph['design_exposure'].append(dict(design=design,exposure=expo,
                         status='PARTIAL_GRAPH_UNSUPPORTED',reason='E2 isolate exposure undefined'))
                    totals['PARTIAL_GRAPH_UNSUPPORTED']+=1
                    continue
                if expo=='E3' and graph['isolates']>0:
                    graph['design_exposure'].append(dict(design=design,exposure=expo,
                         status='INVALID_FOR_GRAPH',reason='E3 every node needs nonempty core'))
                    totals['INVALID_FOR_GRAPH']+=1
                    continue
                # choose an actually supported arm (do not assume each arm has support)
                for node in network.node_ids:
                    if expo=='E2' and network.degree_map()[node]==0:continue
                    for a in (0,1):
                        for s in ((0,1,2) if expo=='E2' else (0,1)):
                            try:
                                task=_task(network,design,expo,node,a,s)
                                proposed=identify(task)
                            except (ValueError,TypeError) as exc:
                                last_reason=f'{type(exc).__name__}: {exc}'
                                continue
                            if proposed.status=='POINT' and proposed.verification_status=='VERIFIED':
                                replay_population_identification(proposed)
                                result=(node,a,s,proposed)
                                break
                            last_reason=proposed.result.get('reason_code')
                        if result:break
                    if result:break
                if result is None:
                    graph['design_exposure'].append(dict(design=design,exposure=expo,
                         status='NOT_VERIFIED',reason=last_reason))
                    totals['NOT_VERIFIED']+=1
                else:
                    node,a,s,proof=result
                    graph['design_exposure'].append(dict(design=design,exposure=expo,
                        status='POINT_ARM_VERIFIED',sample_arm=dict(node=node,treatment=a,exposure=s),
                        population_support=proof.result['certificate'].get('joint_arm_support',None)))
                    totals['POINT_ARM_VERIFIED']+=1
        graph['policy_offsupport']=_r2_on_alltreated(network)
        totals['R2_'+graph['policy_offsupport']['r2_status']]+=1
        records.append(graph)
    return dict(version='v2.2-network-cross-topology',graph_count=len(records),
        combinations_total=sum(len(x['design_exposure']) for x in records),
        status_counts=dict(totals),graphs=records,
        limitations=['Fixed known undirected simple graphs only',
          'At least one supported arm per valid design/exposure is not all-arm positivity',
          'Network topology is input, not inferred from observed outcomes',
          'No PFN/numeric outcomes/causal assumption truth tested',
          'Random graphs (ER/BA/WS/SBM) are generation models; only fixed edge sets tested'])


def main():
    cli=argparse.ArgumentParser();cli.add_argument('--output',type=Path)
    args=cli.parse_args();data=run_topology_matrix()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'graph_count':data['graph_count'], 'combinations':data['combinations_total'],
            'status_counts':data['status_counts'],
            'per_graph':[{'graph':g['name'],'R2':g['policy_offsupport']['r2_status'],
                          'R2_reason':g['policy_offsupport']['r2_reason']} for g in data['graphs']]},
            ensure_ascii=False,indent=2))


if __name__=='__main__':main()
