"""Deterministic synthetic, read-only R3 cross-representation audit showcase.

No real observational data, empirical causal confirmation, estimator or policy values.
Run: python -B -m examples.run_r3_target_a4_audit --outdir showcase_r3_target_a4_v28p0
"""
from __future__ import annotations

import argparse
import html
import json
from fractions import Fraction
from itertools import product
from math import prod
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_business import ObservationalEffectsInquiryV26,identify_network_business_query
from pfn_pipeline.identification_composition import EffectQueryV18,compile_effect_query_terms
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline.identification_observational_factorized_a4 import (
    declare_observational_factorized_arm_population_v27p1,
)
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.network_inquiry_shadow import declare_network_study
from pfn_pipeline.identification_r3_target_a4_audit import (
    compare_r3_target_a4_v28p0,inspect_r3_joint_handoff_v28p0,
)


def _study(n):
    nodes=tuple(f'n{i}' for i in range(n))
    edges=(tuple((nodes[i],nodes[(i+1)%n]) for i in range(n)) if n>6
           else tuple((nodes[i],nodes[i+1]) for i in range(n-1)))
    return declare_network_study(network_id=f'R3 audit demo n={n}',node_order=nodes,
        undirected_edges=edges,treatment_variable='AI',outcome_variable='sales',
        outcome_kind='continuous',context_reference='W=synthetic-w0',
        observation_regime='observational',assignment_design=None,
        protocol_provenance='artificial fixed-W observational population',
        network_provenance='fixed pre-treatment graph',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def _outcome(st,ps,source_id,*,full=False,kind='DIRECT'):
    sig=declare_policy_signature(st,grouping='strict_majority_ties_low')
    request=EffectQueryV18(kind=kind,node_weights=(('n2',1),),
                           reference_exposure=0,comparison_exposure=0 if kind=='DIRECT' else 1)
    if full:
        cells=[]
        for t in product((0,1),repeat=len(st.node_order)):
            p=prod((q if bit else 1-q for bit,q in zip(t,ps)))
            if p:
                cells.append((t,p))
        src=declare_observational_population_v23(st,source_id=source_id,
            provenance='synthetic, fully enumerated exact marginal',assignment_masses=cells)
    else:
        arms=tuple(sorted({t.coordinates for t in compile_effect_query_terms(request)}))
        src=declare_observational_factorized_arm_population_v27p1(st,sig,
            source_id=source_id,provenance='synthetic exact independent observational law',
            treatment_one_probabilities=ps,covered_arms=arms)
    assumptions=tuple(Assumption(name=k,source='demo_specification',confirmed=True,
        evidence=['Synthetic scientific stipulation; not real-world empirical validation'])
        for k in ('full_vector_conditional_exchangeability','consistency',
                  'fixed_pretreatment_network','finite_conditional_first_moments'))
    result=identify_network_business_query(ObservationalEffectsInquiryV26(st,src,assumptions,sig,(request,)))
    if result.status!='POINT':
        raise RuntimeError(f'Synthetic demo was not verified POINT: {result.summary()}')
    return result


def generate():
    st=_study(5)
    ps=tuple(Fraction(1,3) for _ in st.node_order)
    factorized=_outcome(st,ps,'factorized-source')
    full=_outcome(st,ps,'fully-enumerated-source',full=True)
    different_law=_outcome(st,tuple(Fraction(2,3) for _ in st.node_order),'inconsistent-law-source')
    spillover=_outcome(st,ps,'spillover-source',kind='SPILLOVER')
    st_large=_study(300)
    large_ps=tuple(Fraction(1,3) for _ in st_large.node_order)
    large_a=_outcome(st_large,large_ps,'large-factorized-a')
    large_b=_outcome(st_large,large_ps,'large-factorized-b')
    cases=[]
    for label,brief,a,b in (
        ('Exact law, two representations','5 nodes: finite p(T|W) versus independent Bernoulli product',factorized,full),
        ('Contradictory A4 law','5 nodes: same study/W, two differing observational distributions',factorized,different_law),
        ('Different mathematical effects','5 nodes: Direct versus Spillover, under same p(T|W)',factorized,spillover),
        ('Scalable exact match','300-node ring: two identical factorized p(T|W) sources',large_a,large_b),
    ):
        comparison=compare_r3_target_a4_v28p0(a,b)
        cases.append(dict(label=label,brief=brief,
            relationship=comparison.relationship,
            a4_consistency=comparison.a4_consistency,
            same_target_certified=comparison.same_target_certified,
            can_merge_as_one_symbolic_target=comparison.can_merge_as_one_symbolic_target,
            reasons=list(comparison.reasons),
            left_target_fp=comparison.left.original_target_fingerprints,
            right_target_fp=comparison.right.original_target_fingerprints,
            norm_left=comparison.left.cross_representation_fingerprints,
            norm_right=comparison.right.cross_representation_fingerprints))
    bundle=inspect_r3_joint_handoff_v28p0((factorized,full))
    return dict(version='v2.8-P0-readonly-R3-A4',data_kind='SYNTHETIC_SYMBOLIC_POPULATION',
        result_count=len(cases),cases=cases,
        one_target_handoff=dict(target_merge_certified=bundle['target_merge_certified'],
            estimation=bundle['estimation'],conditional_mean_values_reconciled=False),
        warning='No assumption validated in real world; no numeric causal outcome or estimator.')


def write(outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    data=generate()
    jsonfile=outdir/'CFM_ID_v2_8_P0_Cross_R3_Target_A4_Audit.json'
    jsonfile.write_text(json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    rows=[]
    for c in data['cases']:
        status='CONFIRMED SAME TARGET' if c['can_merge_as_one_symbolic_target'] else ('A4 CONFLICT' if 'CONFLICT' in c['a4_consistency'] else 'DO NOT MERGE')
        rows.append('<article><header><h3>'+html.escape(c['label'])+'</h3><span class="pill '+('yes' if c['can_merge_as_one_symbolic_target'] else 'no')+'">'+status+'</span></header><p>'+html.escape(c['brief'])+'</p><dl><dt>Target relationship</dt><dd>'+html.escape(c['relationship'])+'</dd><dt>Exact A4 check</dt><dd>'+html.escape(c['a4_consistency'])+'</dd><dt>Reason codes</dt><dd>'+html.escape(', '.join(c['reasons']) or 'None')+'</dd></dl></article>')
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CFM-ID v2.8 P0 R3 Target/A4 Audit</title><style>
    :root{font-family:ui-sans-serif,system-ui,Arial;color:#162a3b;background:#f4f7fa}body{margin:auto;max-width:1000px;padding:38px 20px}h1{font-size:29px;margin:4px 0 10px}h3{font-size:17px;margin:0}.meta{font-size:13px;color:#5b697a}.lead{line-height:1.55}.layout{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:15px;margin-top:22px}article{background:white;border:1px solid #dce4eb;border-radius:13px;padding:20px;box-shadow:0 3px 14px #263e5910}header{display:flex;gap:10px;justify-content:space-between;align-items:start}p{color:#526276;line-height:1.5}.pill{border-radius:20px;padding:5px 9px;font-weight:700;font-size:10px;white-space:nowrap}.yes{background:#d8f3e8;color:#0e7046}.no{background:#fae6df;color:#894526}dl{display:grid;grid-template-columns:130px 1fr;gap:8px;font-size:12px;word-break:break-word}dt{font-weight:600;color:#63758a}dd{margin:0;color:#193b54}footer{margin-top:24px;color:#66768a;font-size:13px}</style></head><body>
    <div class="meta">Causal-IDFM / Identification / v2.8 opt-in P0 audit</div><h1>Cross-R3 target identity &amp; A4 consistency</h1><p class="lead">Replayed POINT certificates only. Independent exact observational-law comparison, no causal estimates. Distinct identification contracts are never merged by their “Direct” labels.</p><main class="layout">'''+''.join(rows)+'''</main><footer><strong>Scientific scope:</strong> exact synthetic declared population operators; neither observational assumptions nor source truth can be proved by this dashboard. One-target grouping does not imply a verified numerical estimator.</footer></body></html>'''
    htmlfile=outdir/'CFM_ID_v2_8_P0_Cross_R3_Target_A4_Audit.html'
    htmlfile.write_text(page,encoding='utf-8')
    return htmlfile,jsonfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--outdir',type=Path,default=Path('showcase_r3_target_a4_v28p0'))
    args=parser.parse_args()
    for path in write(args.outdir):print(path)

if __name__=='__main__':main()
