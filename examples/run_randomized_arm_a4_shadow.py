"""Optional A4 shadow demonstration. Does NOT change identify() behavior.

Run small: python -B -m examples.run_randomized_arm_a4_shadow
Run ER300: python -B -m examples.run_randomized_arm_a4_shadow --er300
No training or checkpoint required; uses original verified support backends.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import copy
import json
import numpy as np

from pfn_pipeline import make_heterogeneous_bernoulli_arm_task
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.identification_a4_shadow import (
    declare_a4_source, assess_a4_shadow, replay_a4_shadow,
)
from pfn_pipeline.simulation import load_graph
from pfn_pipeline._internal.paths import DEFAULT_GRAPH


def build_task(er300=False):
    if er300:
        adjacency=load_graph(DEFAULT_GRAPH)
        nodes=tuple(f'node-{i}' for i in range(adjacency.shape[0]))
        edges=[(nodes[int(i)],nodes[int(j)]) for i,j in zip(*np.where(np.triu(adjacency,1)==1))]
        net=NetworkExposureSpec(network_id='a4-shadow-shared-ER300',
                                node_ids=list(nodes),undirected_edges=edges)
    else:
        net=NetworkExposureSpec(network_id='a4-shadow-toy3',node_ids=['0','1','2'],
                                undirected_edges=[('0','1'),('0','2')])
    return make_heterogeneous_bernoulli_arm_task(
        net, propensities={i:'1/2' for i in net.node_ids},
        node_id=net.node_ids[0],own_treatment_value=1,exposure_value=1,
        source='trusted study fixture', evidence='explicit fixed-W Bernoulli randomization protocol',
        admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE',
    )


def enum_value(value):
    return value.value if hasattr(value, 'value') else str(value)


def run(er300=False):
    t=build_task(er300)
    q=t.identification_spec['query']
    s=declare_a4_source(t,source_id='declared:node-arm-population-law',
        operator='NODE_ARM_MEANS',provenance='explicit reviewed population arm operator declaration',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        node_order=t.node_ids,outcome_nodes=t.node_ids,
        arm_cells=((q['target_node_id'],q['own_treatment_value'],q['exposure_value']),))
    shadow=assess_a4_shadow(t,s)
    assert replay_a4_shadow(t,s,shadow)

    # Small documented pair reproduces both kinds of legacy A4 mismatch.
    mismatches={}
    if not er300:
        weak_info=copy.deepcopy(t.identification_spec)
        weak_info['information_signature']['objects'][0].update(
            joint_scope='node_local_marginals_only',whole_network_assignment_law_available=False,
            description='No joint arm operator; pairwise marginal information only')
        weak=replace(t,identification_spec=weak_info)
        weak_src=declare_a4_source(weak,source_id='declared:pairwise-marginals',
            operator='PAIRWISE_MARGINALS',provenance='explicit source lists only pairwise marginals',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            node_order=weak.node_ids,outcome_nodes=weak.node_ids)
        w=assess_a4_shadow(weak,weak_src)
        assert replay_a4_shadow(weak,weak_src,w)
        mismatches['legacy_weak_information_false_positive']={
            'legacy_status':enum_value(w.legacy_identification.status),
            'typed_A4':w.receipt.information_status,'typed_issue':w.receipt.reason,
            'difference':w.difference,
        }
        strong_info=copy.deepcopy(t.identification_spec)
        strong_info['information_signature']['objects'][0].update(
            name='P(T_vector,Y_vector|W)',variables=['treatment','outcome','context'],
            basis='WHOLE_NETWORK_ASSIGNMENT_LAW_V1',joint_scope='whole_network_assignment',
            outcome_representation='full_joint_law',whole_network_assignment_law_available=True)
        strong=replace(t,identification_spec=strong_info)
        full_src=declare_a4_source(strong,source_id='declared:full-joint-law',
            operator='FULL_JOINT_LAW',provenance='explicit full treatment-outcome population joint law',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            node_order=strong.node_ids,outcome_nodes=strong.node_ids)
        st=assess_a4_shadow(strong,full_src)
        assert replay_a4_shadow(strong,full_src,st)
        mismatches['legacy_full_information_false_negative']={
            'legacy_status':enum_value(st.legacy_identification.status),
            'legacy_reason':st.legacy_identification.result.get('reason_code'),
            'typed_A4':st.receipt.information_status,'typed_rule':st.receipt.rule_id,
            'difference':st.difference,
        }
    return {
        'version':'randomized-arm-a4-shadow-v1',
        'network_size':len(t.node_ids),
        'baseline':{'legacy_status':enum_value(shadow.legacy_identification.status),
                    'legacy_verification':enum_value(shadow.legacy_identification.verification_status),
                    'typed_information_status':shadow.receipt.information_status,
                    'typed_rule':shadow.receipt.rule_id,
                    'support':shadow.support.support,'support_verifier':shadow.support.independent_verifier_rule,
                    'support_digest':shadow.support.digest,
                    'source_spec_sha256':shadow.support.source_spec_fingerprint,
                    'receipt_sha256':shadow.receipt.digest,
                    'replay':'PASS',
                    'A4_is_math_identification':False,
                    'pfns_invoked':False},
        'small_three_node_disagreements':mismatches,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--er300',action='store_true')
    p.add_argument('--output',type=Path,default=None)
    opt=p.parse_args()
    report=run(opt.er300)
    if opt.output:
        opt.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__ == '__main__':
    main()
