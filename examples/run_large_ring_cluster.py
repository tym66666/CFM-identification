"""One real 300-node non-ER fixed Ring with D4/E4/E5 full verifier replay.

Only synthetic symbolic identification and exact support. No PFN/estimates.
Run python -B -m examples.run_large_ring_cluster --output-dir ...
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.identification import (
    make_cluster_bernoulli_arm_task,identify,replay_population_identification,
)


def run(outdir: Path):
    n=300
    nodes=tuple(f'node-{i}' for i in range(n))
    edges=tuple((nodes[i],nodes[(i+1)%n]) for i in range(n))
    net=NetworkExposureSpec(network_id='ring-300-synthetic-D4-v24',
        node_ids=list(nodes),undirected_edges=list(edges))
    clusters=tuple(tuple(nodes[i:i+2]) for i in range(0,n,2))
    probabilities=('1/2',)*len(clusters)
    entries=[]
    for exposure,state in (
        ('exact_treated_neighbor_count',2),('any_treated_neighbor',1),
        ('strict_majority',1),
    ):
        t=make_cluster_bernoulli_arm_task(net,clusters=clusters,
            cluster_probabilities=probabilities,node_id=nodes[0],
            own_treatment_value=1,exposure_value=state,
            exposure_definition=exposure,source='documented synthetic Ring300 cluster protocol',
            evidence='fixed disjoint pretreatment pairs; cluster Bernoulli(1/2)',
            admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
        r=identify(t)
        if r.status!='POINT' or r.verification_status!='VERIFIED':
            raise AssertionError(f'Cannot certify {exposure}: {r.result.get("reason_code")}')
        replay_population_identification(r)
        cert=r.result['certificate']
        entries.append(dict(exposure=exposure,own_treatment=1,exposure_value=state,
             status=r.status.value,verification=r.verification_status.value,
             joint_support=cert['joint_arm_support_probability'],
             theorem=cert['rule_id'], target_fingerprint=t.target_fingerprint))
    result=dict(version='v2.4',network='Ring300',graph_family='fixed undirected cycle',
        n_nodes=n,cluster_count=len(clusters),design='D4 cluster-level independent Bernoulli(1/2)',
        a4='synthetic symbolic population operator, not numerical Y estimates',
        entries=entries)
    outdir.mkdir(parents=True,exist_ok=True)
    path=outdir/'CFM_ID_v2_4_Ring300_D4_Proofs.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print('Ring300:',[(v['exposure'],v['status'],v['joint_support']) for v in entries])
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',default='v24_demo')
    run(Path(p.parse_args().output_dir))
