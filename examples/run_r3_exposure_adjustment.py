"""Synthetic, deterministic 300-node R3 exposure-adjustment demo; no numeric estimates."""
from __future__ import annotations

import argparse
from dataclasses import replace
from fractions import Fraction
from html import escape
import json
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_composition import EffectQueryV18,compile_effect_query_terms
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_business import (
    ObservationalExposureAdjustedEffectsInquiryV27P2, identify_network_business_query,
    replay_verified_business_outcome,
)
from pfn_pipeline.identification_observational_exposure_adjustment import (
    declare_stratified_observational_arm_population_v27p2,
    admit_exposure_adjustment_a5_v27p2,
)
from pfn_pipeline.network_inquiry_shadow import declare_network_study


def assumption(name,*,proposed=False):
    return Assumption(name=name,source='llm_candidate' if proposed else 'demo_specification',
        confirmed=not proposed,evidence=['synthetic scenario assumption; not checked in any real company'])


def query(kind,*,node='n151',s0=0,s1=1,group=False):
    kw=dict(kind=kind,node_weights=((node,1),) if not group else (('n151',1),('n152',2)),
            reference_exposure=s0,comparison_exposure=s1)
    if group:
        kw.update(cohort_authority='HUMAN_CONFIRMED_PRETREATMENT',
                  cohort_evidence='synthetic treatment-before cohort registration')
    return EffectQueryV18(**kw)


def scenario_factory():
    ids=tuple(f'n{i}' for i in range(300))
    st=declare_network_study(network_id='synthetic-ring300-observational-adjustment',
        node_order=ids,undirected_edges=tuple((ids[i],ids[(i+1)%300]) for i in range(300)),
        treatment_variable='AI',outcome_variable='performance',outcome_kind='continuous',
        context_reference='W=baseline-company',observation_regime='observational',
        assignment_design=None,
        protocol_provenance='synthetic observational network, conditions admitted only for demonstration',
        network_provenance='known before AI treatment',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    sig=declare_policy_signature(st,grouping='strict_majority_ties_low')
    records=tuple(assumption(x) for x in ('consistency','fixed_pretreatment_network',
                                         'finite_conditional_first_moments'))
    license=admit_exposure_adjustment_a5_v27p2(st,sig,covered_nodes=('n151','n152'),
        potential_outcome_exposure_sufficiency=assumption('potential_outcome_exposure_sufficiency'),
        exposure_level_conditional_exchangeability=assumption('exposure_level_conditional_exchangeability'))
    strata=(('low_adoption','2/5',(Fraction(1,3),)*300),
            ('high_adoption','3/5',(Fraction(2,3),)*300))
    queries=[('C01','本人 AI 的协变量调整 Direct','DIRECT',query('DIRECT',s0=0,s1=0),'point'),
             ('C02','邻居高暴露的调整 Spillover','SPILLOVER',query('SPILLOVER'),'point'),
             ('C03','自身和邻居同时变化的 Total','TOTAL',query('TOTAL'),'point'),
             ('C04','已登记群体的处理前加权 Total','TOTAL',query('TOTAL',group=True),'point'),
             ('C05','Exposure 充分性尚未接受','DIRECT',query('DIRECT',s0=0,s1=0),'suff_proposed'),
             ('C06','协变量调整后交换性尚未接受','SPILLOVER',query('SPILLOVER'),'exchange_proposed'),
             ('C07','仅有样本统计，缺总体算子','DIRECT',query('DIRECT',s0=0,s1=0),'sample'),
             ('C08','调整层出现零支持','DIRECT',query('DIRECT',s0=0,s1=0),'no_overlap'),
             ('C09','A4 未覆盖全部目标条件均值','TOTAL',query('TOTAL'),'missing_cells')]
    result=[]
    for caseid,title,kind,q,variant in queries:
        required={t.coordinates for t in compile_effect_query_terms(q)}
        cells=tuple((b,*t) for b in ('low_adoption','high_adoption') for t in required)
        if variant=='missing_cells':
            cells=tuple(c for c in cells if not (c[0]=='low_adoption' and c[2]==1))
        mass_rows=strata if variant!='no_overlap' else (
            ('low_adoption','2/5',(Fraction(0),)*300),
            ('high_adoption','3/5',(Fraction(2,3),)*300))
        src=declare_stratified_observational_arm_population_v27p2(st,sig,
            source_id=f'synthetic-stratified-A4-{caseid}',
            provenance='symbolic synthetic joint B, factorized T|B, and node/B arm conditional means',
            adjustment_variable='pre_campaign_adoption_context',strata=mass_rows,
            covered_cells=cells,availability='FINITE_SAMPLE_ESTIMATE' if variant=='sample'
                          else 'SYMBOLIC_POPULATION_OPERATOR')
        li=license
        if variant=='suff_proposed':
            li=replace(li,potential_outcome_exposure_sufficiency=assumption(
                'potential_outcome_exposure_sufficiency',proposed=True))
        if variant=='exchange_proposed':
            li=replace(li,exposure_level_conditional_exchangeability=assumption(
                'exposure_level_conditional_exchangeability',proposed=True))
        out=identify_network_business_query(ObservationalExposureAdjustedEffectsInquiryV27P2(
            st,src,records,sig,li,(q,)))
        if out.status=='POINT':
            assert replay_verified_business_outcome(out)
        summ=out.summary()
        result.append(dict(id=caseid,business=title,kind=kind,scenario=variant,
            status=out.status,route=out.route,reason_code=out.reason_code,
            summary=summ))
    data=dict(version='v2.7-postrelease-P2-R3-exposure-adjustment',
        substantive_target='E[Y_i(a,s)|W] after pre-treatment stratum standardization',
        graph='synthetic 300-node undirected ring',nodes=300,
        observational_law='separately ADMITTED product Bernoulli within each of two pretreatment strata',
        strata=[dict(name=b,mass=m,node_probability=str(ps[0])) for b,m,ps in strata],
        assumptions=['potential_outcome_exposure_sufficiency','exposure_level_conditional_exchangeability',
            'consistency','fixed_pretreatment_network','finite_conditional_first_moments'],
        case_counts={label:sum(c['status']==label for c in result) for label in ('POINT','NEEDS_INPUT','UNSUPPORTED')},
        cases=result,finite_sample_estimate=None,policy_value_estimate=None,
        disclaimers=['All population operators and scientific assumptions are synthetic declarations.',
            'Not p-standardized R3, not full-vector policy identification.',
            'No real company causal effect, estimator adapter, or empirical proof of exchangeability.'])
    return data


def make_html(data):
    cards=[]
    for c in data['cases']:
        ident=c['summary']['identification'] or {}
        details=''
        if c['status']=='POINT':
            for p in ident.get('results',[]):
                details+=f'<div class="formula">{escape(p["identified_functional"])}</div>'
                for b in p['support_by_stratum']:
                    details+=f'<div class="support">{escape(b["stratum"])}: {escape(", ".join(b["nonzero_term_support"]))}</div>'
        else:
            details+=f'<div class="reason">阻断原因：{escape(str(c["reason_code"]))}</div>'
        cards.append(f'<article class="case" data-status="{escape(c["status"])}" data-key="{escape(c["business"].lower())}"><div class="top"><span class="caseid">{escape(c["id"])}</span><span class="state {escape(c["status"])}">{escape(c["status"])}</span></div><h3>{escape(c["business"])}</h3><div class="small">{escape(c["kind"])} · {escape(str(c["route"] or "NO CERTIFIED ROUTE"))}</div>{details}</article>')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CFM-ID · R3 分层 Exposure Adjustment</title><style>
:root{font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC',sans-serif;color:#172b35;background:#f3f6f9}*{box-sizing:border-box}body{margin:0}
header{padding:38px max(24px,calc((100% - 1160px)/2));background:#102a3a;color:#e9f3f6}header h1{font-size:32px;line-height:1.22;margin:8px 0 14px}header p{max-width:880px;line-height:1.65;color:#bbd1de}.eyebrow{text-transform:uppercase;letter-spacing:.18em;font-size:11px;color:#7dccd4;font-weight:700}
main{max-width:1160px;margin:auto;padding:26px 22px 70px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:-42px}.metric{background:#fff;border:1px solid #e0e8ed;border-radius:12px;padding:19px;box-shadow:0 8px 18px #102a3a11}.metric strong{font-size:30px;display:block;margin:5px 0}.metric label{font-size:12px;color:#617988}
section{margin-top:27px}.note{padding:20px 22px;background:#fff;border:1px solid #e0e8ed;border-radius:12px;line-height:1.7}section h2{font-size:20px}.tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:17px 0}button,input{border:1px solid #ccdae3;background:#fff;border-radius:8px;padding:9px 12px;font:inherit}button{cursor:pointer}button.active{background:#153c50;color:white;border-color:#153c50}input{flex:1;min-width:210px}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.case{background:#fff;border-radius:12px;padding:18px;border:1px solid #dce6ec;min-width:0}.top{display:flex;justify-content:space-between;align-items:center}.caseid{font-size:11px;color:#8196a1;font-weight:800}.case h3{font-size:16px;margin:14px 0 8px;line-height:1.45}.state{font-size:10px;font-weight:800;letter-spacing:.05em;border-radius:999px;padding:6px 9px;background:#e6e9ec}.state.POINT{color:#116e54;background:#dff2ea}.state.NEEDS_INPUT{color:#926115;background:#fff1d8}.state.UNSUPPORTED{color:#9f4250;background:#fee8ec}.small{font-size:11px;color:#6d8796;overflow-wrap:anywhere;line-height:1.55}.formula{font-family:ui-monospace,monospace;font-size:11px;line-height:1.65;background:#eef5f7;padding:11px;border-radius:7px;overflow-wrap:anywhere;margin-top:12px}.support{font-size:11px;color:#356a73;margin:6px 0}.reason{font-size:12px;color:#9f4250;background:#fff3f2;padding:12px;margin-top:14px;border-radius:7px;overflow-wrap:anywhere}footer{color:#6a8290;line-height:1.6;font-size:12px;margin-top:30px}
@media(max-width:880px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:590px){.cards{grid-template-columns:1fr}header h1{font-size:26px}}
</style></head><body><header><div class="eyebrow">Network-first · Identification · Post-release P2</div><h1>观测网络：协变量分层 Exposure G-formula</h1><p>300 节点 Ring · 两个处理前协变量层 · 精确正支持 · 强 exposure 充分性与暴露层无混杂需分别接受。所有状态由正式业务 API 与独立证书重放生成。</p></header><main><div class="metrics"><div class="metric"><label>网络节点</label><strong>300</strong></div><div class="metric"><label>POINT</label><strong>'''+str(data['case_counts']['POINT'])+'''</strong></div><div class="metric"><label>NEEDS_INPUT</label><strong>'''+str(data['case_counts']['NEEDS_INPUT'])+'''</strong></div><div class="metric"><label>UNSUPPORTED</label><strong>'''+str(data['case_counts']['UNSUPPORTED'])+'''</strong></div></div><section class="note"><h2>两个人工声明的总体层</h2><p><b>low_adoption</b>：总体比例 2/5，条件 treatment probability 1/3。<br><b>high_adoption</b>：总体比例 3/5，条件 treatment probability 2/3。</p><p>新目标是 Σ<sub>b</sub> P(B=b|W) E[Y<sub>i</sub>(a,s)|B=b,W]，不是根据观测 p(T|W) 标准化的旧 arm。<b>仅调整 treatment propensity 无法消除隐藏混杂。</b></p></section><section><h2>业务查询与拒绝解释</h2><div class="tools"><button class="active" data-filter="ALL">全部</button><button data-filter="POINT">POINT</button><button data-filter="NEEDS_INPUT">NEEDS_INPUT</button><button data-filter="UNSUPPORTED">UNSUPPORTED</button><input aria-label="搜索案例" id="search" placeholder="搜索 Direct、Spillover、A4、交换性等"></div><div class="cards">'''+''.join(cards)+'''</div></section><footer>研究演示 · 仅为符号总体算子与明确接受的假设示例 · 无有限样本数值估计 · 不代表真实业务的因果结论。</footer></main><script>const bs=[...document.querySelectorAll('button[data-filter]')],cards=[...document.querySelectorAll('.case')],s=document.getElementById('search');let state='ALL';function go(){let q=s.value.trim().toLowerCase();for(const c of cards)c.hidden=!(state==='ALL'||c.dataset.status===state)||!c.dataset.key.toLowerCase().includes(q)}for(const b of bs)b.onclick=()=>{state=b.dataset.filter;bs.forEach(x=>x.classList.toggle('active',x===b));go()};s.addEventListener('input',go);</script></body></html>'''


def write(outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    data=scenario_factory()
    p=outdir/'CFM_ID_v2_7_P2_R3_Exposure_Adjustment_300_Node.json'
    h=p.with_suffix('.html')
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    h.write_text(make_html(data),encoding='utf-8')
    return p,h,data


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',default='showcase_r3_exposure_adjustment_v27p2')
    args=ap.parse_args();p,h,data=write(args.outdir)
    print(p,h,data['case_counts'])
