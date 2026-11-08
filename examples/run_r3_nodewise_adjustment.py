"""Deterministic v2.8 300-node showcase from real business API + verifier.

All assumptions and population operators are stipulations in a SYNTHETIC proof
fixture; no effect sizes, estimation, or empirical identification claims.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from fractions import Fraction
from html import escape
import json
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_business import (
    ObservationalNodewiseAdjustedEffectsInquiryV28,
    identify_network_business_query,replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import EffectQueryV18, compile_effect_query_terms
from pfn_pipeline.identification_observational_nodewise_adjustment import (
    declare_nodewise_local_arm_population_v28, admit_nodewise_adjustment_a5_v28,
)
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.network_inquiry_shadow import declare_network_study


def a5(name,proposed=False):
    return Assumption(name=name,source='llm_candidate' if proposed else 'demo_specification',
        confirmed=not proposed,evidence=['Synthetic v2.8 proof fixture, not real company evidence'])


def effect(kind,*,group=False,reference=0,comparison=1):
    kwargs=(dict(cohort_authority='TRUSTED_FIXTURE',
                 cohort_evidence='Synthetic pre-registered two-employee cohort') if group else {})
    return EffectQueryV18(kind=kind,node_weights=(('n2','1/2'),('n3','1/2')) if group else (('n2',1),),
        reference_exposure=reference,comparison_exposure=comparison,**kwargs)


def scenario_factory():
    n=300
    nodes=tuple(f'n{i}' for i in range(n))
    edges=tuple((nodes[j],nodes[(j+1)%n]) for j in range(n))
    study=declare_network_study(network_id='v28-SYNTHETIC-300-node-ring',node_order=nodes,
        undirected_edges=edges,treatment_variable='AI_copilot',outcome_variable='sales',
        outcome_kind='continuous',context_reference='W=synthetic_company',
        observation_regime='observational',assignment_design=None,
        protocol_provenance='Synthetic declared observational population, not a random experiment',
        network_provenance='Observed fixed pre-AI training partner network',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    features=(tuple(j%2 for j in range(n)),
        tuple(j%2 if j!=n-1 else 1-(j%2) for j in range(n)),
        tuple(1 for _ in range(n)))
    masses=('1/5','2/5','2/5')
    propensities=(tuple(Fraction(1,3) for _ in nodes),
                  tuple(Fraction(2,3) for _ in nodes),
                  tuple(Fraction(1,2) for _ in nodes))
    assumptions=tuple(a5(x) for x in ('consistency','fixed_pretreatment_network',
                                        'finite_conditional_first_moments'))
    neighborhood={node:set() for node in nodes}
    for u,v in edges:neighborhood[u].add(v);neighborhood[v].add(u)
    pos={node:j for j,node in enumerate(nodes)}
    cases=[
        ('V28-01','本人AI的节点局部协变量调整 Direct','strict_majority_ties_low',effect('DIRECT',comparison=0),'point'),
        ('V28-02','同事AI暴露变化的节点调整 Spillover','strict_majority_ties_low',effect('SPILLOVER'),'point'),
        ('V28-03','本人和邻居联合改变的 Total','strict_majority_ties_low',effect('TOTAL'),'point'),
        ('V28-04','预先登记两名员工的加权 Total','strict_majority_ties_low',effect('TOTAL',group=True),'point'),
        ('V28-05','E4 精确两个邻居处理的 Spillover','exact_treated_neighbor_count',effect('SPILLOVER',comparison=2),'point'),
        ('V28-06','E5 至少一个邻居处理的 Spillover','any_treated_neighbor',effect('SPILLOVER'),'point'),
        ('V28-07','潜在结果 exposure sufficiency 未获许可','strict_majority_ties_low',effect('DIRECT',comparison=0),'suff_proposed'),
        ('V28-08','局部协变量暴露交换性未获许可','strict_majority_ties_low',effect('SPILLOVER'),'exchange_proposed'),
        ('V28-09','只有有限样本，不是总体均值算子','strict_majority_ties_low',effect('DIRECT',comparison=0),'sample'),
        ('V28-10','目标节点调整层总体均值信息不完整','strict_majority_ties_low',effect('TOTAL'),'missing_cell'),
        ('V28-11','某个正质量节点调整层内缺少处理支持','strict_majority_ties_low',effect('DIRECT',comparison=0),'zero_support')]
    results=[]
    for cid,title,grouping,query,variant in cases:
        sig=declare_policy_signature(study,grouping=grouping)
        arms={term.coordinates for term in compile_effect_query_terms(query)}
        cells={(node,feature[pos[node]],sum(feature[pos[j]] for j in neighborhood[node]),t,s)
            for feature in features for node,t,s in arms}
        if variant=='missing_cell':
            cells={c for c in cells if not (c[0]=='n2' and c[3]==1)}
        ps=propensities
        if variant=='zero_support':
            last=list(ps[2]);last[2]=Fraction(0)
            ps=(*ps[:2],tuple(last))
        profiles=[(f'profile{j}',mass,feature,probs)
            for j,(mass,feature,probs) in enumerate(zip(masses,features,ps))]
        source=declare_nodewise_local_arm_population_v28(study,sig,
            source_id=f'synthetic-v28-A4-{cid}',
            provenance='exact synthetic symbolic P(X), P(T|X) and arm conditional outcome means',
            feature_name='pre_AI_digital_skill',profiles=profiles,covered_cells=cells,
            availability='FINITE_SAMPLE_ESTIMATE' if variant=='sample' else 'SYMBOLIC_POPULATION_OPERATOR')
        licensed_nodes=tuple(sorted({node for node,_,_ in arms}))
        license=admit_nodewise_adjustment_a5_v28(study,sig,feature_name='pre_AI_digital_skill',
            covered_nodes=licensed_nodes,
            potential_outcome_exposure_sufficiency=a5('potential_outcome_exposure_sufficiency',
                proposed=variant=='suff_proposed'),
            local_covariate_exposure_mean_exchangeability=a5('local_covariate_exposure_mean_exchangeability',
                proposed=variant=='exchange_proposed'))
        outcome=identify_network_business_query(ObservationalNodewiseAdjustedEffectsInquiryV28(
            study,source,assumptions,sig,license,(query,)))
        if outcome.status=='POINT':
            assert replay_verified_business_outcome(outcome)
        results.append(dict(id=cid,business=title,exposure=grouping,scenario=variant,
            status=outcome.status,route=outcome.route,reason_code=outcome.reason_code,
            summary=outcome.summary()))
    data=dict(version='v2.8',implementation='R3 node-specific local-covariate POINT subroute',
        nodes=n,graph='synthetic ring',feature_name='pre_AI_digital_skill',
        local_adjustment='C_i=(X_i, number of undirected neighbors whose pretreatment X=1)',
        observation_regime='observational',
        observable_law='exact synthetic finite P(X-vector|W) and factorized P(T|X-vector,W)',
        target_semantics='E[Y_i(a,s)|W], not observational p-standardized effect or policy value',
        cases=results,case_counts={s:sum(c['status']==s for c in results)
                                   for s in ('POINT','NEEDS_INPUT','UNSUPPORTED')},
        assumptions_required=['consistency','fixed_pretreatment_network',
            'finite_conditional_first_moments','potential_outcome_exposure_sufficiency',
            'local_covariate_exposure_mean_exchangeability'],
        finite_sample_effect_values=None,numeric_policy_values=None,
        disclaimers=['Synthetic stipulated overall data law and causal assumptions; no real company data.',
            'P(T|X) factorization does not imply exposure ignorability.',
            'Node-specific binary X and neighbor count, NOT arbitrary high-dimensional covariate adjustment.',
            'POINT is about a symbolic population formula, not a finite-sample estimator.'])
    return data


def make_html(data):
    entries=[]
    for c in data['cases']:
        val=c['summary'].get('identification') or {}
        details=''
        if c['status']=='POINT':
            for proof in val.get('results',[]):
                details+=f'<div class="formula">{escape(proof["identified_functional"])}</div>'
                for term in proof['support_by_term']:
                    for row in term['local_strata']:
                        details+=f'<div class="support">{escape(term["node"])}: X={row["own_pretreatment_covariate"]}, neighbor-X-count={row["neighbor_covariate_count"]}, P(C)={escape(row["population_mass"])}, P(arm|C)={escape(row["arm_support"])}</div>'
        else:
            details=f'<div class="reason">门禁拒绝：{escape(str(c["reason_code"]))}</div>'
        entries.append(f'<article class="card" data-status="{c["status"]}" data-key="{escape(c["business"].lower())}"><header><span>{c["id"]}</span><b class="status {c["status"]}">{c["status"]}</b></header><h3>{escape(c["business"])}</h3><div class="subtitle">{escape(c["exposure"])} · {escape(str(c["route"] or "NOT VERIFIED"))}</div>{details}</article>')
    css='''body{margin:0;background:#f3f6f9;color:#193341;font:14px/1.65 system-ui,-apple-system,"Noto Sans SC",sans-serif}*{box-sizing:border-box}.hero{background:#102a3a;color:#edf8fb;padding:40px max(24px,calc((100% - 1220px)/2))}.hero h1{font-size:29px;margin:5px 0}.hero p{max-width:920px;color:#bad2dd}.eyebrow{letter-spacing:.13em;color:#65c7d1;font-size:11px;text-transform:uppercase;font-weight:700}.main{max-width:1220px;margin:auto;padding:26px 22px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:-50px}.metric,.note,.card{background:white;border:1px solid #dce5eb;border-radius:12px}.metric{padding:17px 19px;box-shadow:0 5px 15px #1232}.metric strong{display:block;font-size:30px}.metric label,.subtitle{color:#6e8290;font-size:11px}.note{padding:17px 23px;margin:24px 0;line-height:1.85}.note p{margin:6px 0}.tools{display:flex;gap:9px;margin:18px 0;flex-wrap:wrap}button,input{background:white;border:1px solid #c6d6e0;border-radius:8px;padding:9px 12px;font:inherit}button.active{background:#183b4d;color:white}input{flex:1;min-width:180px}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.card{padding:17px;overflow-wrap:anywhere}.card header{display:flex;justify-content:space-between;color:#6d8792;font-size:11px}.card h3{font-size:15px;line-height:1.45;margin:12px 0 6px}.status{padding:4px 9px;border-radius:99px}.status.POINT{background:#e0f1e8;color:#146a4c}.status.NEEDS_INPUT{background:#fff2da;color:#856010}.status.UNSUPPORTED{background:#ffeded;color:#a5404a}.formula{font-family:ui-monospace,Consolas,monospace;font-size:11px;padding:12px;background:#eaf3f7;border-radius:7px;margin-top:12px;overflow-wrap:anywhere}.support{font-size:11px;color:#366f7c;margin-top:6px}.reason{margin-top:12px;color:#9e404c;background:#fff2f1;padding:11px;border-radius:6px;font-size:12px}footer{padding:30px 0;color:#778b98;font-size:12px}@media(max-width:920px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:590px){.cards{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}'''
    return f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Causal-IDFM v2.8 | Node-specific R3</title><style>{css}</style></head><body><div class="hero"><div class="eyebrow">Causal-IDFM · v2.8 · R3</div><h1>观测网络中的节点级与邻居协变量调整</h1><p>300 节点固定无向 Ring · 三个处理前协变量配置 · 每节点的 X_i 与邻居 X 正值人数 · 精确总体 A4 + 明确接受 A5 + 独立证书重放。全部结果由正式业务 API 实时生成，不是销售数值估计。</p></div><div class="main"><div class="metrics"><div class="metric"><label>网络节点</label><strong>300</strong></div><div class="metric"><label>POINT</label><strong>{data['case_counts']['POINT']}</strong></div><div class="metric"><label>NEEDS_INPUT</label><strong>{data['case_counts']['NEEDS_INPUT']}</strong></div><div class="metric"><label>UNSUPPORTED</label><strong>{data['case_counts']['UNSUPPORTED']}</strong></div></div><section class="note"><h2>数学目标与信息边界</h2><p><b>目标：</b>θ_i(a,s)=Σ_c P(C_i=c) E[Y_i^obs | T_i=a,S_i=s,C_i=c]。其中 C_i=(本人处理前 X_i, 邻居处理前 X 为 1 的人数)。目标不随观测 propensity 改变，但可以随目标协变量总体改变。</p><p><b>A5：</b>必须单独接受个体 exposure potential outcome sufficiency 和给定 C_i 的 exposure-level 均值交换性。</p><p><b>A4：</b>仅接受经人工声明的精确 P(X-vector) + 因子化 P(T|X-vector) + 条件均值总体算子；不从实际有限样本推断总体律。</p></section><h2>可筛选的业务识别案例</h2><div class="tools"><button class="active" data-filter="ALL">全部</button><button data-filter="POINT">POINT</button><button data-filter="NEEDS_INPUT">NEEDS_INPUT</button><button data-filter="UNSUPPORTED">UNSUPPORTED</button><input id="search" aria-label="搜索案例" placeholder="搜索 Direct、Spillover、交换性或支持"></div><div class="cards">{''.join(entries)}</div><footer>研究演示，不提供真实世界假设证据、有限样本因果数值或 Policy Welfare。R4/R5/A0 未在本轮扩展。</footer></div><script>const btns=[...document.querySelectorAll('button[data-filter]')],cards=[...document.querySelectorAll('.card')],search=document.getElementById('search');let filter='ALL';function apply(){{const q=search.value.trim().toLowerCase();for(const card of cards)card.hidden=(filter!=='ALL'&&card.dataset.status!==filter)||!card.dataset.key.includes(q)}}for(const b of btns)b.addEventListener('click',()=>{{filter=b.dataset.filter;btns.forEach(x=>x.classList.toggle('active',x===b));apply()}});search.addEventListener('input',apply);</script></body></html>'''


def write(outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    data=scenario_factory()
    j=outdir/'CFM_ID_v2_8_Nodewise_Neighbor_Adjustment_300_Node.json'
    h=outdir/'CFM_ID_v2_8_Nodewise_Neighbor_Adjustment_300_Node.html'
    j.write_text(json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    h.write_text(make_html(data),encoding='utf-8')
    return j,h,data

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',default='showcase_r3_nodewise_v28');args=ap.parse_args()
    j,h,data=write(args.outdir)
    print(j,h,data['case_counts'])
