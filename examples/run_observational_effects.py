"""v2.6 synthetic R3 p-standardized effect / Family taxonomy showcase.

Run: python -B -m examples.run_observational_effects --output-dir path
Every POINT is derived by the formal R3 backend + replay, never hard-coded.
"""
from __future__ import annotations
import argparse
import html
import json
from dataclasses import replace
from fractions import Fraction
from itertools import product
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26,ObservationalPolicyInquiryV23,
    identify_network_business_query,replay_verified_business_outcome,
)
from pfn_pipeline.network_inquiry_shadow import declare_network_study,fixed_policy_target_from_context

STATES={
    'strict_majority_ties_low':'E1 Majority',
    'exact_treated_neighbor_count':'E4 Exact Count',
    'any_treated_neighbor':'E5 Any Treated',
}


def main(output_dir:Path):
    output_dir.mkdir(parents=True,exist_ok=True)
    st=declare_network_study(network_id='synthetic-path5-observational',
      node_order=tuple(f'emp-{i}' for i in range(5)),
      undirected_edges=tuple((f'emp-{i}',f'emp-{i+1}') for i in range(4)),
      treatment_variable='AI_Access',outcome_variable='Sales',
      outcome_kind='continuous',context_reference='W=declared_pretreatment_stratum',
      observation_regime='observational',assignment_design=None,
      protocol_provenance='synthetic observational protocol for route demonstration',
      network_provenance='fixed before AI adoption',
      graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    allocations=list(product((0,1),repeat=5))
    unnormalized={t:(3 if t[0]==t[1] else 1) for t in allocations}
    denominator=sum(unnormalized.values())
    src=declare_observational_population_v23(st,
       source_id='synthetic-population-declaration-v26',
       provenance='SYNTHETIC symbolic complete observational law; NOT real customer data',
       assignment_masses=[(t,Fraction(unnormalized[t],denominator)) for t in allocations])
    names=('full_vector_conditional_exchangeability','consistency',
      'fixed_pretreatment_network','finite_conditional_first_moments')
    a5=tuple(Assumption(name=n,source='demo_specification',confirmed=True,
          evidence=['SYNTHETIC FOR SHOWCASE; scientific truth not checked']) for n in names)
    def req(kind,node='emp-2',s0=0,s1=0,group=None):
        return EffectQueryV18(kind=kind,
           node_weights=((node,1),) if group is None else group,
           reference_exposure=s0,comparison_exposure=s1,
           cohort_authority='TRUSTED_FIXTURE' if group is not None else None,
           cohort_evidence='synthetic pretreatment-declared department' if group is not None else None)
    cases=[
      ('C38','本人使用 AI 的标准化直接效应','E1 Majority',
        ObservationalEffectsInquiryV26(st,src,a5,declare_policy_signature(st,grouping='strict_majority_ties_low'),(req('DIRECT'),))),
      ('C39','同事多数使用 AI 的标准化溢出效应','E1 Majority',
        ObservationalEffectsInquiryV26(st,src,a5,declare_policy_signature(st,grouping='strict_majority_ties_low'),(req('SPILLOVER',s0=0,s1=1),))),
      ('C40','本人和同事状态共同变化的标准化总效应','E1 Majority',
        ObservationalEffectsInquiryV26(st,src,a5,declare_policy_signature(st,grouping='strict_majority_ties_low'),(req('TOTAL',s0=0,s1=1),))),
      ('C41','处理前分组的标准化平均总效应','E1 Majority',
        ObservationalEffectsInquiryV26(st,src,a5,declare_policy_signature(st,grouping='strict_majority_ties_low'),
            (req('TOTAL',s0=0,s1=1,group=(('emp-1','1'),('emp-2','2'),('emp-3','1'))),))),
      ('C42','精确邻居 treated 人数变化的标准化效应','E4 Exact Count',
        ObservationalEffectsInquiryV26(st,src,a5,declare_policy_signature(st,grouping='exact_treated_neighbor_count'),(req('SPILLOVER',s0=0,s1=2),))),
      ('C43','任一邻居 treated 的标准化效应','E5 Any Treated',
        ObservationalEffectsInquiryV26(st,src,a5,declare_policy_signature(st,grouping='any_treated_neighbor'),(req('SPILLOVER',s0=0,s1=1),))),
      ('C44','全员获得 AI 的固定政策值（与效应目标不同）','R3 Full Policy',
        ObservationalPolicyInquiryV23(st,
            fixed_policy_target_from_context(st,(1,1,1,1,1),authority='TRUSTED_FIXTURE'),src,a5)),
      ('C45','未确认条件交换性仍请求 Direct','E1 Majority',
        ObservationalEffectsInquiryV26(st,src,tuple(x for x in a5 if x.name!='full_vector_conditional_exchangeability'),
            declare_policy_signature(st,grouping='strict_majority_ties_low'),(req('DIRECT'),))),
      ('C46','稀疏观测 assignment 缺少高/低暴露 arm','E1 Majority',
        ObservationalEffectsInquiryV26(st,replace(src,assignment_masses=((tuple([0]*5),'1/2'),(tuple([1]*5),'1/2'))),
            a5,declare_policy_signature(st,grouping='strict_majority_ties_low'),(req('SPILLOVER',s0=0,s1=1),))),
      ('C47','样本频数冒充总体分配律','E1 Majority',
        ObservationalEffectsInquiryV26(st,replace(src,availability='FINITE_SAMPLE_ESTIMATE'),
            a5,declare_policy_signature(st,grouping='strict_majority_ties_low'),(req('DIRECT'),))),
      ('C48','缺少目标员工的总体 outcome 算子','E1 Majority',
        ObservationalEffectsInquiryV26(st,replace(src,outcome_nodes=('emp-0',)),
            a5,declare_policy_signature(st,grouping='strict_majority_ties_low'),(req('DIRECT'),))),
    ]
    cards=[]
    for cid,label,exposure,query in cases:
        result=identify_network_business_query(query)
        if result.status=='POINT':
            assert replay_verified_business_outcome(result)
        summary=result.summary()
        detail=summary.get('identification') or {}
        cards.append(dict(id=cid,label=label,exposure=exposure,status=result.status,
           route=result.route or 'NO_APPLICABLE_ROUTE',reason=result.reason_code,
           theorem=detail.get('theorem_id'),
           proof_targets=detail.get('results',[]) if result.status=='POINT' else [],
           explanation='可输出经过验证的总体识别泛函；没有因果效应数值估计' if result.status=='POINT'
                       else '没有 POINT 结论；不能把此拒绝当作非识别证明'))
    category_audit=[
      dict(axis='A1 TARGET',key='Arm/Direct/Spillover/Total',rule='通用精确线性代数：R1a 和 R3 共享 EffectQueryV18；标准化分配律不同'),
      dict(axis='A4 INFORMATION',key='Observational p(T|W)',rule='不是随机化设计 q，不产生因果许可；固定 W，最多 12 节点'),
      dict(axis='A5 IDENTIFICATION',key='R3 Conditional Exchangeability',rule='同一个交换性门禁供 policy 与 arm/effect 使用；不推断 exposure sufficiency'),
      dict(axis='A6 SUPPORT',key='Assignment cell vs Signature/Arm cell',rule='Policy FULL 看 p(z)>0；R3 标准化 contrast 看每个 arm 的 rho_i(a,s)>0'),
      dict(axis='ROUTE',key='R3-POLICY vs R3-EFFECT',rule='不同 Target 与不同支持条件，但不新建 Family；同一问题可以多路推导但应相容'),
    ]
    output=dict(version='v2.6',dataset='synthetic-path5-conditional-observational-population',
      nodes=5,assignment_masses=len(allocations),outcome='Sales',
      observational_law='p_obs(T|W) with nonindependent treatment allocations',
      simulated_population_operator=True,exchangeability_empirically_verified=False,
      effect_estimator_adapter=False,cards=cards,classification_audit=category_audit,
      counts={x:sum(c['status']==x for c in cards) for x in ('POINT','NEEDS_INPUT','UNSUPPORTED')})
    stem='CFM_ID_v2_6_Observational_Effects_and_Taxonomy'
    (output_dir/(stem+'.json')).write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
    data=json.dumps(output,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    page='''<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFM-ID v2.6 | Observational Network Effects</title><style>
:root{color-scheme:light}body{margin:0;background:#f3f6fa;color:#18314b;font:15px/1.55 system-ui,-apple-system,'Noto Sans CJK SC',sans-serif}
header{background:#122a47;color:#f6f9ff;padding:29px max(24px,calc((100vw - 1120px)/2))}h1{margin:0 0 8px;font-size:26px}main{max-width:1120px;margin:24px auto;padding:0 16px}
.subtitle{color:#bad4ec}section{background:white;padding:20px;border:1px solid #d9e2ef;border-radius:14px;margin-bottom:20px}
h2{margin:0 0 12px;font-size:18px}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.kpi{background:#f5f7fc;padding:13px;border-radius:10px}.kpi b{font-size:25px;display:block}.muted{color:#5d6e85;font-size:13px}
.pill{display:inline-block;border-radius:8px;background:#e9f0f8;padding:4px 10px;font-weight:600;font-size:12px}.POINT{color:#18785a;background:#e2f5ed}.NEEDS_INPUT{color:#9d5f10;background:#fff3d8}.UNSUPPORTED{color:#9b3842;background:#ffeced}
button,input{border:1px solid #ccd8e6;border-radius:9px;padding:8px 11px;background:white;font:inherit}button{cursor:pointer}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:15px}
.card{padding:13px;border:1px solid #e0e6ef;border-radius:11px;margin:9px 0}.card summary{cursor:pointer;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.card summary strong{flex:1}.details{padding:10px 0 0}.monospace{font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f8fc;padding:9px;border-radius:7px}
.tax{width:100%;border-collapse:collapse}.tax td,.tax th{padding:10px;text-align:left;border-bottom:1px solid #e3e9f1;vertical-align:top}.tagline{border-left:4px solid #6c91c3;padding-left:13px;color:#47617b}
@media(max-width:680px){.kpis{grid-template-columns:1fr 1fr}.tax{font-size:12px}}
</style></head><body><header><h1>Network Identification · v2.6</h1><div class="subtitle">R3 Observational p-standardized Direct / Spillover / Total · 扩展 A1，不新增 Family</div></header>
<main><section><h2>真实代码运行汇总</h2><div class="kpis" id="stats"></div><p class="tagline">这些是合成的、显式声明的总体信息与假设下的数学识别公式。没有真实销售额、估计数值或自动证明交换性。</p></section>
<section><h2>业务查询与安全拒绝</h2><div class="toolbar"><button data-filter="ALL">全部</button><button data-filter="POINT">POINT</button><button data-filter="NEEDS_INPUT">需补信息</button><button data-filter="UNSUPPORTED">当前不适用</button><input id="search" placeholder="搜索业务 / Route / Code" aria-label="搜索查询"></div><div id="cards"></div></section>
<section><h2>有限、正交、可复用的分类</h2><table class="tax"><thead><tr><th>分类轴</th><th>对象</th><th>与其他轴的边界</th></tr></thead><tbody id="tax"></tbody></table></section>
<section><h2>尚未支持</h2><p>本版观测 R3 仍限固定 W 与有限显式分配总体律（最多 12 节点）；不支持由样本自动确认交换性、任意 ER300 observational inference、连续 W 的 g-formula、通用 two-stage randomization、数值 PFN adapter。</p></section></main>
<script id="payload" type="application/json">'''+data+'''</script><script>
const d=JSON.parse(document.getElementById('payload').textContent);const $=x=>document.getElementById(x);
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('stats').innerHTML=[['小图节点',d.nodes],['业务案例',d.cards.length],['POINT',d.counts.POINT],['安全拒绝',d.cards.length-d.counts.POINT]].map(([k,v])=>'<div class="kpi"><b>'+v+'</b><span class="muted">'+k+'</span></div>').join('');
$('tax').innerHTML=d.classification_audit.map(x=>'<tr><td><b>'+esc(x.axis)+'</b></td><td>'+esc(x.key)+'</td><td>'+esc(x.rule)+'</td></tr>').join('');
let filter='ALL';function render(){const needle=$('search').value.toLowerCase();const rows=d.cards.filter(c=>(filter==='ALL'||c.status===filter)&&(JSON.stringify(c).toLowerCase().includes(needle)));
$('cards').innerHTML=rows.map(c=>{const obj=(c.proof_targets||[]).map(p=>p.kind+'\\n'+p.identified_functional+'\\n'+JSON.stringify(p.arm_terms)).join('\\n\\n');return '<details class="card"><summary><span class="muted">'+esc(c.id)+'</span><strong>'+esc(c.label)+'</strong><span class="pill '+esc(c.status)+'">'+esc(c.status)+'</span></summary><div class="details"><p>Exposure: '+esc(c.exposure)+' · Route: '+esc(c.route)+'</p><p>'+esc(c.explanation)+'</p><p>阻断原因: '+esc(c.reason||'无')+'</p>'+(obj?'<pre class="monospace">'+esc(obj)+'</pre>':'')+'</div></details>'}).join('')||'<p class="muted">无匹配结果</p>';}
document.querySelectorAll('button[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;render()}));$('search').addEventListener('input',render);render();
</script></body></html>'''
    (output_dir/(stem+'.html')).write_text(page,encoding='utf-8')
    print(json.dumps(dict(json=str(output_dir/(stem+'.json')),html=str(output_dir/(stem+'.html')),
          counts=output['counts']),ensure_ascii=False))
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=Path('showcase_v26'))
    args=parser.parse_args();main(args.output_dir)
