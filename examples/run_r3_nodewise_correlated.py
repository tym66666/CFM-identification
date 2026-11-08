"""Deterministic symbolic R3 Nodewise conditional mixture A4 showcase.

Uses the synthetic tests' shared population protocol. The outputs originate
from the formal business dispatcher and independent theorem replay, NOT from
manual POINT labels, trained models or observed revenues.
"""
from __future__ import annotations
import argparse, html, json
from dataclasses import replace
from pathlib import Path
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_business import (
    ObservationalNodewiseAdjustedEffectsInquiryV28,
    identify_network_business_query,replay_verified_business_outcome,
)
from tests.test_r3_nodewise_correlated_a4 import mixture_items

STEM='CFM_ID_v2_8_P1_1_R3_Nodewise_Conditional_Correlation'

def generate():
    def run(name,grouping='strict_majority_ties_low',kind='DIRECT',a=0,b=0,
            *,status_case=None,weights=None):
        weights=weights or (('n2',1),)
        request=EffectQueryV18(kind=kind,node_weights=weights,reference_exposure=a,
            comparison_exposure=b,
            **({'cohort_authority':'TRUSTED_FIXTURE',
                'cohort_evidence':'Synthetic pretreatment team'} if len(weights)>1 else {}))
        args=list(mixture_items(300,grouping,requests=(request,),
            proposed=('exchangeability' if status_case=='a5' else None),
            sample=(status_case=='sample'),missing=(status_case=='missing')))
        if status_case=='source':args[1]=replace(args[1],admission='PROPOSED')
        if status_case=='zero':
            source=args[1];profiles=list(source.profiles)
            # Last X profile is the only source of n2's C=(1,2); enforce T_n2=0
            row=profiles[2];comps=[]
            for component in row.components:
                v=list(component.treatment_one_probabilities);v[2]='0'
                comps.append(replace(component,treatment_one_probabilities=tuple(v)))
            profiles[2]=replace(row,components=tuple(sorted(comps,
                           key=lambda c:c.treatment_one_probabilities)))
            args[1]=replace(source,profiles=tuple(profiles))
        query=ObservationalNodewiseAdjustedEffectsInquiryV28(
            args[0],args[1],args[3],args[2],args[4],args[5])
        out=identify_network_business_query(query)
        return dict(name=name,kind=kind,exposure=grouping,status=out.status,
            reason_code=out.reason_code,route=out.route,
            verified=bool(replay_verified_business_outcome(out)) if out.status=='POINT' else False,
            mathematical_result=out.summary()['identification'])
    rows=[
        run('Direct / E1 / Ring300'),
        run('Spillover / E1 / Ring300',kind='SPILLOVER',a=0,b=1),
        run('Total / E1 / Ring300',kind='TOTAL',a=0,b=1),
        run('Team-weighted Total',kind='TOTAL',a=0,b=1,
            weights=(('n2','1/2'),('n3','1/2'))),
        run('Exact neighbor count / E4',grouping='exact_treated_neighbor_count',kind='SPILLOVER',a=0,b=2),
        run('Any treated neighbor / E5',grouping='any_treated_neighbor',kind='SPILLOVER',a=0,b=1),
        run('A5 exchangeability not admitted',status_case='a5'),
        run('A4 proposed but not admitted',status_case='source'),
        run('Only finite-sample statistics',status_case='sample'),
        run('Missing conditional outcome operator',status_case='missing'),
        run('Zero local-stratum support',status_case='zero'),
    ]
    statuses={status:sum(r['status']==status for r in rows)
              for status in ('POINT','NEEDS_INPUT','UNSUPPORTED')}
    return dict(contract='CFM-ID-v2.8-P1.1-nodewise-conditional-mixture',
        study='SYMBOLIC_SYNTHETIC_ONLY',node_count=300,exposure_rules=['E1','E4','E5'],
        source_type='P(X|W) with finite correlated Bernoulli mixtures P(T|X,W)',
        target='C_i-adjusted E[Y_i(a,s)|W], NOT p-standardized arm',
        route='R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS',
        conditions=['consistency','fixed pretreatment network','finite conditional means',
                    'exposure potential outcome sufficiency',
                    'local covariate exposure mean exchangeability',
                    'positive support in every positive-mass local covariate stratum',
                    'symbolic population conditional outcome means'],
        note='Correlated treatment does NOT imply no unobserved confounding. No numeric policy or effect.',
        adapter='NO_ADAPTER',statuses=statuses,cases=rows)


def page(data):
    encoded=json.dumps(data,sort_keys=True,ensure_ascii=False).replace('<','\\u003c')
    return '''<!doctype html><html lang="zh"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Causal-IDFM · R3 correlated nodewise</title><style>
body{margin:0;background:#f5f7fa;color:#20314c;font:15px/1.7 system-ui,'Noto Sans SC',sans-serif}
main{max-width:1040px;margin:42px auto;padding:0 20px}h1{font-size:26px}.muted{color:#64748b}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:26px 0}
.kpi,.panel{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:18px}
.kpi strong{display:block;font-size:29px}.kpi span{color:#63748c;font-size:12px}
.panel{margin:20px 0}.warn{border-left:4px solid #b68d44;background:#fffcf5;padding:10px 15px}
.case{padding:14px;margin:12px 0;border:1px solid #dfe6ef;border-radius:8px}
summary{display:flex;justify-content:space-between;cursor:pointer;gap:20px}
.tag{border-radius:20px;padding:1px 10px;background:#edf1f5;font-size:12px}
.POINT{color:#0d6744;background:#e1f8eb}.NEEDS_INPUT{color:#875a16;background:#fff0d4}
.UNSUPPORTED{color:#964354;background:#fde7ee}
input,select{padding:10px;border-radius:6px;border:1px solid #c5cfdc;font:inherit;max-width:100%;margin-right:10px}
pre{overflow-x:auto;overflow-wrap:anywhere;white-space:pre-wrap;background:#f5f7fc;padding:10px;font-size:12px}
</style></head><body><main><h1>R3 · 节点协变量调整下的相关自选择</h1>
<p class="muted">v2.8 Post-release P1.1 · 300 节点 · 合成符号总体。全部结果来自实际 Identification API。</p>
<div class="cards"><div class="kpi"><strong>300</strong><span>处理前固定无向网络</span></div>
<div class="kpi"><strong id="points"></strong><span>POINT / VERIFIED</span></div>
<div class="kpi"><strong id="blocked"></strong><span>拒绝或信息缺失</span></div>
<div class="kpi"><strong>0</strong><span>数值估计器</span></div></div>
<div class="panel"><h2>数学合同</h2>
<p><code>P(T=t|X=x,W)=Σ_h α(h|x) ∏_j r(h,j,x)^t_j (1-r(h,j,x))^(1-t_j)</code></p>
<p>目标是 <b>E[Y_i(a,s)|W]</b>，按本人处理前二元 X 与邻居 X=1 的人数分层标准化，<b>不是</b>观测 p-standardized effect，也不是固定政策收益。</p>
<p class="warn">需研究者分别接受 exposure sufficiency、局部条件均值交换性、一致性；还需要每个正权重调整层的正支持和 typed population conditional means。观测处理相关 ≠ 无混杂。这里没有销售收益数值或 PFN 估计。</p></div>
<div class="panel"><h2>业务查询与反例</h2>
<input id="find" placeholder="搜索案例、原因"/><select id="status"><option value="">所有状态</option>
<option>POINT</option><option>NEEDS_INPUT</option><option>UNSUPPORTED</option></select>
<div id="rows"></div></div></main>
<script id="payload" type="application/json">'''+encoded+'''</script>
<script>
const data=JSON.parse(document.getElementById('payload').textContent);
const counts=data.statuses;document.getElementById('points').textContent=counts.POINT;
document.getElementById('blocked').textContent=counts.NEEDS_INPUT+counts.UNSUPPORTED;
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){const f=document.getElementById('status').value,q=document.getElementById('find').value.toLowerCase();
const a=data.cases.filter(x=>(!f||x.status===f)&&JSON.stringify(x).toLowerCase().includes(q));
document.getElementById('rows').innerHTML=a.map(x=>`<details class="case"><summary><b>${safe(x.name)}</b><span class="tag ${safe(x.status)}">${safe(x.status)}</span></summary>
<p class="muted">${safe(x.route||'No certified theorem')} · ${safe(x.reason_code||'VERIFIED')} · replay=${x.verified}</p>
<pre>${safe(JSON.stringify(x.mathematical_result,null,2))}</pre></details>`).join('')||'<p>无匹配案例</p>'}
document.getElementById('status').addEventListener('change',render);document.getElementById('find').addEventListener('input',render);render();
</script></body></html>'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',default='showcase_r3_nodewise_correlated_v28p2');args=ap.parse_args()
    out=Path(args.outdir);out.mkdir(parents=True,exist_ok=True)
    data=generate()
    (out/(STEM+'.json')).write_text(json.dumps(data,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (out/(STEM+'.html')).write_text(page(data),encoding='utf-8')
    print('cases',len(data['cases']),'statuses',data['statuses'],'outdir',out)

if __name__=='__main__':main()
