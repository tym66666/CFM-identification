"""Executable v1.8 business demo; outputs *population formulas* not effect values.

Run: python -B -m examples.run_verified_r1a_composition
  or python -B -m examples.run_verified_r1a_composition --er300

Explicit synthetic population information is an illustrative contract declaration,
not a measured population or the PFN's estimated response. The --er300 path
reuses the existing shared ER300 legacy response/batch bridge and requires no GPU.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pfn_pipeline import (
    simulate_task, make_heterogeneous_bernoulli_arm_task,
    identify_randomized_network_batch,
    identify_verified_node_effect, EffectQueryV18,
    identify_verified_effect_bundle, replay_verified_effect_bundle,
)
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_composition import CompositionUnavailable
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.simulation import load_graph


def main() -> None:
    arg=argparse.ArgumentParser()
    arg.add_argument('--er300', action='store_true', help='Use shared real ER300 network; slower replay')
    opts=arg.parse_args()
    if opts.er300:
        source_task=simulate_task(seed=2026)
        # Reuse the actual shared ER300 graph/protocol; do NOT rerun the
        # heavyweight legacy PFN bridge. This is population Identification only.
        if (source_task.exposure_definition != 'strict_majority' or
            source_task.assignment_design.get('design_type') != 'randomized_experiment' or
            source_task.assignment_design.get('assignment_probability') != 0.5):
            raise ValueError('Shared ER300 is not the certified Bernoulli(.5)+majority fixture')
        network=NetworkExposureSpec.model_validate(source_task.identification_spec['network_exposure'])
        if tuple(network.node_ids)!=source_task.node_ids:
            raise ValueError('Shared ER300 graph coordinates are inconsistent')
        task=make_heterogeneous_bernoulli_arm_task(
            network,propensities={n:'1/2' for n in network.node_ids},
            node_id=network.node_ids[0],own_treatment_value=0,exposure_value=0,
            source='exact declared shared synthetic ER300 protocol',
            evidence='shared TaskSpec explicitly declares Bernoulli(.5) and strict majority',
            admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
        batch=identify_randomized_network_batch(task)
    else:
        path=(Path(__file__).resolve().parents[1] /
              'pfn_pipeline/_internal/estimation/data/fixed_er_N20_p0.5_seed12345.json')
        graph=load_graph(path)
        node_ids=tuple(str(i) for i in range(graph.shape[0]))
        edges=[(node_ids[i],node_ids[j]) for i in range(len(node_ids))
               for j in range(i+1,len(node_ids)) if graph[i,j]]
        network=NetworkExposureSpec(network_id='verified-R1a-demo-N20',
                                    node_ids=list(node_ids),undirected_edges=edges)
        task=make_heterogeneous_bernoulli_arm_task(
            network,propensities={n:'1/2' for n in network.node_ids},
            node_id=network.node_ids[0],own_treatment_value=0,exposure_value=0,
            source='synthetic documented randomized experiment',
            evidence='explicit fixture: independent Bernoulli(.5) assignment',
            admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE')
        batch=identify_randomized_network_batch(task)
    selectable=[n for n in batch.node_ids if all(batch.cell(n,a,s)['status']=='POINT'
                 for a in (0,1) for s in (0,1))]
    if len(selectable)<3:
        raise RuntimeError('This example needs three nodes with all four arm events supported')
    group=tuple(selectable[:3])
    cells=tuple((n,a,s) for n in group for a in (0,1) for s in (0,1))
    source=declare_a4_source(batch.template,
        source_id='reviewed-example-population-arm-operator',
        operator='NODE_ARM_MEANS',
        provenance='synthetic population experiment; admitted symbolic operator, no real outcome values',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=group,node_order=batch.node_ids,arm_cells=cells)
    first=group[0]
    requests = tuple(EffectQueryV18(
        kind=kind, node_weights=((first,1),),
        reference_exposure=0, comparison_exposure=0 if kind=='DIRECT' else 1)
        for kind in ('DIRECT','SPILLOVER','TOTAL')) + (
            EffectQueryV18(kind='TOTAL',node_weights=tuple((n,1) for n in group),
                reference_exposure=0,comparison_exposure=1,
                cohort_authority='TRUSTED_FIXTURE',
                cohort_evidence='Synthetic demo cohort of three prespecified nodes'),)
    # All four queries reuse one independently replayed Batch. Replay the
    # resulting bundle once more rather than repeating expensive N300 replays.
    bundle=identify_verified_effect_bundle(batch,source,requests)
    replay_verified_effect_bundle(bundle)
    results={label:out.summary() for label,out in zip(
        ('direct','spillover','total','group_average_total'),bundle.results)}
    if opts.er300:
        negative={'status':'NOT_EXECUTED_ON_ER300',
                  'note':'See N20 demo and unit tests for A4 rejection evidence'}
    else:
        try:
            missing=declare_a4_source(batch.template,
                source_id='partial-operator-only-one-arm',operator='NODE_ARM_MEANS',
            provenance='test deliberately incomplete A4 operator',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=(first,),node_order=batch.node_ids,arm_cells=((first,0,0),))
            identify_verified_node_effect(batch,missing,node_id=first,kind='DIRECT',
                                          reference_exposure=0,comparison_exposure=0)
            negative={'unexpected':'PASSED'}
        except CompositionUnavailable as exc:
            negative={'status':'NOT_CERTIFIED','reason_code':exc.reason_code}
    print(json.dumps(dict(version='R1a-verified-composition-v1.8',
           network_nodes=len(batch.node_ids),tested_group=group,
           source_batch_status=batch.verification_status,
           identified_targets=results,insufficient_A4_example=negative,
           numerical_causal_effects='NOT_ESTIMATED',
           no_fixed_policy_welfare_claim=True,estimation_adapter='NOT_REGISTERED'),
           indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
