"""Deterministic 300-node symbolic observational-mixture R3 business demo."""
from __future__ import annotations

import argparse
import html
import json
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26, identify_network_business_query,
    replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import EffectQueryV18, compile_effect_query_terms
from pfn_pipeline.identification_observational_mixture_a4 import (
    declare_observational_mixture_arm_population_v28p1,
)
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.network_inquiry_shadow import declare_network_study


OUTPUT_STEM='CFM_ID_v2_8_P1_Observational_Correlated_Mixture_R3'


def generate():
    n=300; nodes=tuple(f'n{i}' for i in range(n))
    study=declare_network_study(network_id='synthetic-ring300-correlated-observed',
        node_order=nodes,undirected_edges=tuple((nodes[i],nodes[(i+1)%n]) for i in range(n)),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W=w0',observation_regime='observational',assignment_design=None,
        protocol_provenance='synthetic observational mechanism thought experiment',
        network_provenance='fixed pretreatment ring',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    good_a5=tuple(Assumption(name=x,source='demo_specification',confirmed=True,
                  evidence=['synthetic explicitly assumed; not proven by data']) for x in (
        'full_vector_conditional_exchangeability','consistency',
        'fixed_pretreatment_network','finite_conditional_first_moments'))
    mixture=((F(1,3),(F(1,4),)*n),(F(2,3),(F(3,4),)*n))

    def case(name,kind,grouping,reference,comparison,*,admission='ADMITTED',
             availability='SYMBOLIC_POPULATION_OPERATOR',bad_a5=False,
             missing_cell=False,zero_support=False):
        sig=declare_policy_signature(study,grouping=grouping)
        requests=(EffectQueryV18(kind=kind,node_weights=(('n151',1),),
                  reference_exposure=reference,comparison_exposure=comparison),)
        terms=compile_effect_query_terms(requests[0]);covered={t.coordinates for t in terms}
        if missing_cell:covered={next(iter(sorted(covered)))}
        components=(((F(1,2),(0,)*n),(F(1,2),(1,)*n)) if zero_support else mixture)
        src=declare_observational_mixture_arm_population_v28p1(study,sig,
            source_id=f'hypothetical-operator-{name.lower().replace(" ","-")}',
            provenance='synthetic population symbol (not estimated sales)',
            components=components,covered_arms=covered,
            admission=admission,availability=availability)
        a5=good_a5 if not bad_a5 else tuple(Assumption(name=a.name,source='llm_candidate',confirmed=False,evidence=['unverified A5'])
           if a.name=='full_vector_conditional_exchangeability' else a for a in good_a5)
        out=identify_network_business_query(ObservationalEffectsInquiryV26(
            study,src,a5,sig,requests))
        replay=bool(replay_verified_business_outcome(out)) if out.status=='POINT' else False
        return dict(name=name,query_type=kind,grouping=grouping,status=out.status,
            route=out.route,reason_code=out.reason_code,
            replay=replay,identification=out.summary()['identification'],
            no_numeric_estimate=True)

    rows=[
        case('Direct E1','DIRECT','strict_majority_ties_low',0,0),
        case('Spillover E1','SPILLOVER','strict_majority_ties_low',0,1),
        case('Total E1','TOTAL','strict_majority_ties_low',0,1),
        case('Spillover E5','SPILLOVER','any_treated_neighbor',0,1),
        case('Unaccepted observational A4','DIRECT','strict_majority_ties_low',0,0,admission='PROPOSED'),
        case('Sample-only A4','DIRECT','strict_majority_ties_low',0,0,availability='FINITE_SAMPLE_ESTIMATE'),
        case('Unaccepted full-vector A5','DIRECT','strict_majority_ties_low',0,0,bad_a5=True),
        case('Missing population arm mean','DIRECT','strict_majority_ties_low',0,0,missing_cell=True),
        case('Zero support with correlated adoption','SPILLOVER','strict_majority_ties_low',0,1,zero_support=True),
    ]
    counts={s:sum(x['status']==s for x in rows) for s in ('POINT','NEEDS_INPUT','UNSUPPORTED')}
    return dict(title='v2.8 P1: correlated observational treatment law · R3 POINT',
        data_kind='SYNTHETIC_SYMBOLIC_POPULATION',network='Ring300',
        node_count=n,components=2,route='R3_P_STANDARDIZED_EFFECTS',
        identification_mechanism='R3 full-vector exchangeability + consistency',
        A4_law_kind='OBSERVATIONAL_FINITE_MIXTURE_NODEWISE_BERNOULLI',
        no_exposure_sufficiency_assumed=True,
        mathematical_formula='p_obs(t|W)=sum_h pi_h product_i r_hi^(t_i)(1-r_hi)^(1-t_i)',
        scientific_assumptions_verified_in_real_world=False,
        finite_sample_estimates=None,estimator_adapter='NO_ADAPTER',
        record_count=len(rows),counts=counts,cases=rows,
        note='Software checks exact consequences of admitted A4/A5. No sales estimates or universal observational ID.')


def html_page(data):
    embedded=json.dumps(data,sort_keys=True,ensure_ascii=False).replace('<','\\u003c')
    return '''<!doctype html><html lang="zh"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CFM-ID v2.8 P1 · Observational Correlation</title>
<style>
:root{color-scheme:light;font:15px/1.6 system-ui,-apple-system,'Noto Sans SC',sans-serif;color:#14273c}
body{margin:0;background:#f4f7fb}main{max-width:1090px;margin:36px auto;padding:0 20px}
h1{font-size:27px;margin-bottom:8px}.muted{color:#607388}.lead{max-width:920px}
.metrics{display:flex;flex-wrap:wrap;gap:12px;margin:26px 0}.metric{flex:1;min-width:175px;background:#fff;border:1px solid #e0e6f1;padding:17px;border-radius:12px}
.metric strong{font-size:27px;display:block;color:#204260}.metric small{color:#687990}
.panel{background:#fff;border:1px solid #e0e6f1;border-radius:12px;padding:22px;margin:16px 0}
.grid{display:flex;gap:12px;flex-wrap:wrap}.grid input,.grid select{padding:10px;font:inherit;border:1px solid #afbbcc;border-radius:7px}
.case{padding:16px;margin:12px 0;border:1px solid #e1e8f0;border-radius:9px;background:#fff}
.case summary{cursor:pointer;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;font-weight:600}
.tag{padding:2px 10px;border-radius:20px;background:#eef3f7;font-size:12px}
.tag.POINT{background:#dcf7e9;color:#136b3c}.tag.NEEDS_INPUT{background:#fff2d7;color:#966000}.tag.UNSUPPORTED{background:#f5e8ea;color:#963343}
pre{overflow-x:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9fc;padding:12px;border-radius:6px;font-size:12px}
.warning{border-left:4px solid #a17940;background:#fffaf0;padding:12px 16px}
footer{color:#6b7c91;font-size:12px;padding:18px 0}
</style></head><body><main>
<h1>CFM-ID · R3 观测处理相关性识别</h1>
<p class="lead muted">v2.8 Post-release P1 · 固定 Ring300 · 有限混合观测 Bernoulli 总体律。所有案例调用正式 Identification API 与独立 replay。</p>
<div class="metrics"><div class="metric"><strong>300</strong><small>网络节点</small></div>
<div class="metric"><strong id="passed"></strong><small>POINT / VERIFIED</small></div>
<div class="metric"><strong id="blocked"></strong><small>安全拒绝</small></div>
<div class="metric"><strong>NO_ADAPTER</strong><small>下游数值估计能力</small></div></div>
<div class="panel"><h2>数学许可及范围</h2>
<p><code>p_obs(t|W) = Σ_h π_h ∏_i r_hi^(t_i) (1−r_hi)^(1−t_i)</code></p>
<p>该总体律可以让节点 treatment 在给定 W 后相关。识别的是 <b>p-standardized</b> arm / contrast；依旧要求明确接受 full-vector conditional exchangeability、consistency、固定处理前网络、总体 arm 条件均值与每项正支持。不需要 exposure sufficiency。</p>
<p class="warning"><b>不是现实世界因果假设验证，也不是有限样本估计。</b> 共同选择冲击若同时改变潜在结果，完整向量交换性可能失败。图中只有符号总体识别，不含任何销售增益数字。</p></div>
<div class="panel"><h2>真实查询与拒绝案例</h2><div class="grid">
<input id="search" placeholder="搜索目标、暴露规则、失败原因" aria-label="搜索案例"/>
<select id="filter" aria-label="筛选识别状态"><option value="">全部状态</option><option>POINT</option><option>NEEDS_INPUT</option><option>UNSUPPORTED</option></select></div>
<div id="records"></div></div><footer>Deterministic offline artifact · synthetic symbolic operators · Causal-IDFM</footer>
<script id="payload" type="application/json">''' + embedded + '''</script>
<script>
const data=JSON.parse(document.getElementById('payload').textContent);
document.getElementById('passed').textContent=data.counts.POINT;
document.getElementById('blocked').textContent=data.counts.NEEDS_INPUT+data.counts.UNSUPPORTED;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function draw(){const q=document.getElementById('search').value.toLowerCase(),f=document.getElementById('filter').value;
let rows=data.cases.filter(x=>(!f||x.status===f)&&JSON.stringify(x).toLowerCase().includes(q));
document.getElementById('records').innerHTML=rows.map((x,i)=>`<details class="case"><summary>
<span>${esc(x.name)} <span class="muted">· ${esc(x.grouping)}</span></span><span class="tag ${esc(x.status)}">${esc(x.status)}</span></summary>
<p>Route: ${esc(x.route||'未认证')} · Replay: ${esc(x.replay)} · Reason: ${esc(x.reason_code||'none')}</p>
<pre>${esc(JSON.stringify(x.identification,null,2))}</pre></details>`).join('')||'<p class="muted">没有匹配记录。</p>';}
document.getElementById('search').addEventListener('input',draw);
document.getElementById('filter').addEventListener('change',draw);draw();
</script></main></body></html>'''


def write(outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    data=generate()
    json_path=outdir/(OUTPUT_STEM+'.json')
    html_path=outdir/(OUTPUT_STEM+'.html')
    json_path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    html_path.write_text(html_page(data),encoding='utf-8')
    return (html_path,json_path)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',default='showcase_r3_mixture_v28p1')
    for file in write(Path(p.parse_args().outdir)):print(file)
