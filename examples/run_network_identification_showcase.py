"""Verified Network Identification showcase (no PFN / no causal outcome truth).

Run the r1a, r1b and r2 parts in SEPARATE invocations; then --part assemble.
Example: python -B -m examples.run_network_identification_showcase --part r1a --er300 --output-dir showcase
Each theorem is independently executed and verified before aggregation.

The fixed-quota D2 study in this demo is HYPOTHETICAL even on the shared ER300
network; the Estimation/Policy pipeline's real shared protocol remains D1 iid
Bernoulli(1/2). Explicit A4 population operators are symbolic declarations,
not finite-sample information values.
"""
from __future__ import annotations

import argparse, copy, json, time
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from pfn_pipeline import (
    ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21,
    identify_network_business_query, identify_randomized_network_batch,
)
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source,
)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_a4_source, fixed_policy_target_from_context,
)
from pfn_pipeline._internal.identification.schemas import Assumption
from examples.run_family_route_assessment_shadow import task as legacy_arm_task
from examples.run_nonarm_network_inquiry_shadow import make_study, assumptions
from examples.run_verified_r2_signature_policy import (
    star_study, shared_er300_d2_study, assumptions as r2_assumptions,
)


def _as_json(x):
    if isinstance(x, Fraction):
        return str(x)
    if isinstance(x, dict):
        return {str(k): _as_json(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)):
        return [_as_json(v) for v in x]
    return x


def _case(title, obj, explanation):
    summary=obj.summary()
    result=summary['identification'] or {}
    if isinstance(result,dict) and result.get('results'):
        result={**result,'results':[{'kind':x.get('kind'),
                'identified_functional':x.get('identified_functional'),
                'certificate_sha256':x.get('certificate_sha256')}
                for x in result['results']]}
    if title.startswith('All Treated'):
        result={k:v for k,v in result.items() if k not in (
            'nonzero_node_weights','fixed_policy_treatment','required_observables')}
    return dict(title=title,status=obj.status,route=obj.route,reason=obj.reason_code,
                explanation=explanation,attempted=summary['attempted_routes'],result=result)


def run_r1a(*,er300:bool):
    anchor=legacy_arm_task(er300=er300)
    batch=identify_randomized_network_batch(anchor)
    nodes=batch.node_ids
    group=nodes[:3]
    cells=tuple((node,a,s) for node in group for a in (0,1) for s in batch.exposure_states
                if batch.cell(node,a,s)['status']=='POINT')
    a4=declare_a4_source(anchor,source_id='reviewed-demo-node-arm-means',
        operator='NODE_ARM_MEANS',provenance='symbolic synthetic population operator for showcase',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=tuple(group),node_order=nodes,arm_cells=cells)
    requests=tuple(EffectQueryV18(kind=kind,node_weights=((group[0],1),),
        reference_exposure=0,comparison_exposure=0 if kind=='DIRECT' else 1)
        for kind in ('DIRECT','SPILLOVER','TOTAL')) + (
        EffectQueryV18(kind='TOTAL',node_weights=tuple((n,1) for n in group),
          reference_exposure=0,comparison_exposure=1,cohort_authority='TRUSTED_FIXTURE',
          cohort_evidence='prespecified three-node synthetic demonstration cohort'),)
    effects=identify_network_business_query(EffectsInquiryV21(batch,a4,requests))
    if effects.status!='POINT':
        raise RuntimeError('R1a business effects not POINT: '+str(effects.reason_code))
    raw=copy.deepcopy(anchor.identification_spec)
    raw['information_signature']['objects'][0].pop('randomized_arm_observable',None)
    a4_denied=identify_network_business_query(ArmInquiryV21(
                         replace(anchor,identification_spec=raw)))
    if a4_denied.status=='POINT':
        raise RuntimeError('Untyped legacy information was incorrectly POINT')
    from pfn_pipeline._internal.identification.schemas import IdentificationSpec
    graph_fp=IdentificationSpec.model_validate(anchor.identification_spec).network_exposure.semantic_fingerprint()
    return dict(graph_fingerprint=graph_fp,node_count=len(nodes),arm_count=len(nodes)*2*len(batch.exposure_states),
        point_arm_count=sum(v=='POINT' for n in batch.arm_status for row in n for v in row),
        batch_sha256=batch.batch_sha256,source_spec_sha256=batch.source_spec_sha256,
        arm_matrix_status=[[[str(v) for v in row] for row in n] for n in batch.arm_status],
        arm_matrix_support_exact=[[[x for x in row] for row in n]
                                  for n in batch.population_joint_support],
        arm_matrix_support=[[[float(Fraction(x)) if x is not None else None for x in row]
                            for row in n] for n in batch.population_joint_support],
        arm_labels=[f'T={a},S={s}' for a in (0,1) for s in batch.exposure_states],
        business_cases=[
         _case('Node Direct / Spillover / Total + Team Average',effects,
               'Design-standardized arm contrasts, not fixed-allocation policy welfare'),
         _case('Node arm but only legacy variable names',a4_denied,
               'Production A4 typed operator gate rejects the untyped information')])


def run_r1b(*,er300:bool):
    study=make_study(er300=er300)
    target=fixed_policy_target_from_context(study,(1,)*len(study.node_order),
                                             authority='TRUSTED_FIXTURE')
    full=declare_network_a4_source(study,source_id='reviewed-symbolic-full-assignment-law',
         operator='NODE_FULL_LAW',provenance='symbolic EXPERIMENTAL population full law fixture',
         admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
         outcome_nodes=study.node_order)
    fixed=identify_network_business_query(FixedPolicyInquiryV21(
         study,target,assumptions(),r1b_sources=(full,)))
    if fixed.status!='POINT':
        raise RuntimeError('R1b policy not POINT: '+str(fixed.reason_code))
    bad=declare_network_a4_source(study,source_id='reviewed-only-arm-marginals',
         operator='NODE_ARM_MEANS',provenance='insufficient arm population summary',
         admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
         outcome_nodes=study.node_order,exposure_fingerprint='unrelated-arm-label')
    refused=identify_network_business_query(FixedPolicyInquiryV21(
         study,target,assumptions(),r1b_sources=(bad,)))
    if refused.status=='POINT':
        raise RuntimeError('Weak arm-level A4 incorrectly certified policy')
    return dict(graph_fingerprint=study.network_fingerprint,business_cases=[
       _case('All Treated under original D1 experiment',fixed,
             'Full assignment positive q, but q=2^-N is practically tiny'),
       _case('Policy but only arm-level information',refused,
             'A4 cannot recover full-assignment policy mean from arm means')])


def run_r2(*,er300:bool):
    d2_study=shared_er300_d2_study() if er300 else star_study()
    d2_target=fixed_policy_target_from_context(d2_study,(1,)*len(d2_study.node_order),
                                                authority='TRUSTED_FIXTURE')
    d2_full=declare_network_a4_source(d2_study,source_id='hypothetical-D2-full-law',
         operator='NODE_FULL_LAW',provenance='hypothetical D2 study population information',
         admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
         outcome_nodes=d2_study.node_order)
    sig=declare_policy_signature(d2_study,grouping='strict_majority_ties_low')
    degrees=d2_study.network().degree_map()
    sig_cells=tuple((node,1,int(degrees[node]>0)) for node in d2_study.node_order)
    sig_a4=declare_signature_population_source(d2_study,sig,
         source_id='reviewed-hypothetical-D2-signature-law',operator='NODE_SIGNATURE_MEANS',
         provenance='hypothetical accepted symbolic population signature means',
         admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
         outcome_nodes=d2_study.node_order,signature_cells=sig_cells)
    suff=admit_mean_signature_sufficiency(d2_study,sig,
         assumption=Assumption(name='mean_signature_sufficiency',
             source='demo_specification',status='ADMITTED',confirmed=True,
             evidence=['HYPOTHETICAL: mean outcome invariant across full allocations sharing (T_i,g_i)']),
         covered_nodes=d2_study.node_order)
    r2=identify_network_business_query(FixedPolicyInquiryV21(d2_study,d2_target,
         r2_assumptions(),r1b_sources=(d2_full,),
         r2_signature=sig,r2_sufficiency=suff,r2_sources=(sig_a4,)))
    if r2.status!='POINT' or r2.route!='R2_MEAN_SIGNATURE':
        raise RuntimeError('Off-support R2 not verified: '+str(r2.reason_code))
    no_suff=identify_network_business_query(FixedPolicyInquiryV21(
         d2_study,d2_target,r2_assumptions(),r1b_sources=(d2_full,)))
    if no_suff.status=='POINT':
        raise RuntimeError('Off-support D2 without sufficiency incorrectly certified')
    return dict(graph_fingerprint=d2_study.network_fingerprint,business_cases=[
        _case('All Treated under HYPOTHETICAL fixed-quota D2',r2,
              'Off-support R1b fails; R2 needs separately admitted mean-signature sufficiency'),
        _case('D2 off-support policy without sufficiency',no_suff,
              'No R1b support and no independently accepted R2 structural assumption')])


def combine(parts,er300):
    first=parts['r1a']
    if first['graph_fingerprint']!=parts['r1b']['graph_fingerprint']:
        raise ValueError('R1a/R1b demonstration network fingerprint mismatch')
    if er300 and first['graph_fingerprint']!=parts['r2']['graph_fingerprint']:
        raise ValueError('R2 hypothetical D2 must reuse the same ER300 graph')
    if first['node_count']!=300 and er300:
        raise ValueError('ER300 showcase expected a 300-node graph')
    cases=[*parts['r1a']['business_cases'], *parts['r1b']['business_cases'],
           *parts['r2']['business_cases']]
    return dict(release='v2.1 A4 hardened + business routing',
        network='shared ER300 fixed graph' if er300 else 'toy network + star D2',
        node_count=first['node_count'],arm_count=first['arm_count'],
        point_arm_count=first['point_arm_count'],
        batch_sha256=first['batch_sha256'],source_spec_sha256=first['source_spec_sha256'],
        arm_matrix_status=first['arm_matrix_status'],
        arm_matrix_support_exact=first['arm_matrix_support_exact'],
        arm_matrix_support=first['arm_matrix_support'],arm_labels=first['arm_labels'],
        business_cases=cases,
        business_verified=sum(c['status']=='POINT' for c in cases),
        business_rejected=sum(c['status']!='POINT' for c in cases),
        source_notes={
            'A4':'Explicit SYMBOLIC population information declarations, not measured outcomes',
            'A5':'R2 mean-signature sufficiency separately admitted ONLY in hypothetical D2',
            'D2':'Hypothetical fixed-quota protocol on same graph, not the shared Bernoulli Estimation protocol',
            'Estimation':'No PFN, numerical effect, or simulator truth used in Identification',
        })


def make_html(record):
    body=json.dumps(record,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Causal-IDFM — Network Identification Showcase v2.1</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{font-family:Inter,system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;color:#16263a;background:#f5f7fb}
*{box-sizing:border-box}body{margin:0}main{max-width:1160px;margin:auto;padding:34px 24px 64px}
h1{font-size:32px;letter-spacing:-.5px;margin:12px 0 10px}h2{font-size:19px;margin:0 0 16px}
p{line-height:1.65;color:#556578}.eyebrow{color:#1a6a86;font-weight:700;letter-spacing:.12em;font-size:12px}
header{padding-bottom:18px;border-bottom:1px solid #dde4ed}.sub{max-width:820px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}
.metric{background:white;border:1px solid #e0e7ef;padding:20px;border-radius:14px}.metric b{font-size:29px;display:block;color:#174f76}
.metric span{font-size:12px;color:#6b7b8f}.section{background:#fff;border:1px solid #e0e7ef;border-radius:16px;padding:22px;margin:20px 0}
.key{display:flex;gap:14px;flex-wrap:wrap;color:#66788c;font-size:12px}.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:4px}
.cases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.case{border:1px solid #dee5ed;border-radius:12px;padding:16px;background:#fcfdff}
.badge{font-size:11px;font-weight:750;border-radius:999px;padding:4px 9px;display:inline-block;background:#e2f3eb;color:#087454}
.badge.block{background:#fdf0dd;color:#865613}.case h3{font-size:15px;line-height:1.4;margin:12px 0 5px}
.case p{font-size:12px;margin:4px 0}.tag{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11px;color:#43546a;word-break:break-all}
pre{background:#f2f5f9;color:#35465a;font-size:11px;line-height:1.6;padding:12px;white-space:pre-wrap;word-break:break-word;border-radius:10px;max-height:190px;overflow:auto}
small{color:#74849a}#heat{max-width:100%;overflow-x:auto}#hover{color:#1a5c86;font-weight:600;min-height:24px;font-size:13px;margin-top:8px}
footer{color:#74849a;font-size:12px;margin-top:35px;line-height:1.6}details{margin-top:9px}summary{cursor:pointer;color:#386e9a;font-size:12px;font-weight:600}
@media(max-width:750px){.metrics{grid-template-columns:repeat(2,1fr)}.cases{grid-template-columns:1fr} main{padding:20px 13px}}
</style></head><body><main>
<header><div class="eyebrow">CAUSAL-IDFM / VERIFIED IDENTIFICATION SHOWCASE</div>
<h1>网络干扰下的因果识别</h1>
<p class="sub">对业务查询进行正式数学识别、验证与安全诊断。此页由真实代码运行记录生成，显示总体可识别性与支持概率；不提供未经估计的因果效果数值。</p></header>
<div class="metrics" id="metrics"></div>
<section class="section"><h2>Network Arms：Population Support 矩阵</h2>
<p>横向四列表示 (0,0)、(0,1)、(1,0)、(1,1)；纵向是实际网络中的节点。颜色越深代表该 arm 的总体正支持概率越大。悬停查看精确节点与概率近似值。</p>
<div id="heat"></div><div id="hover">将鼠标移到热图单元格上查看。</div>
<div class="key"><span><i class="dot" style="background:#d7e6f5"></i>低支持</span><span><i class="dot" style="background:#087e8b"></i>高支持</span><span><i class="dot" style="background:#e4e7eb"></i>Zero / Undefined</span></div></section>
<section class="section"><h2>真实运行的业务查询和识别结论</h2><div class="cases" id="cases"></div></section>
<section class="section"><h2>数学与实现边界</h2>
<p><b>POINT Identification ≠ 得到效应数值</b>。已知协议、完整潜在结果独立性、总体信息算子和正支持等条件允许数学识别；有限样本模型估计精度由 Estimation 单独评估。</p>
<p><b>R1b 与 R2 不混用：</b>完整分配有支持且 A4 足够时走 R1b；仅当另外接受 mean-signature sufficiency 且类支持成立时，才允许 R2 处理某些 off-support 政策。</p>
<p><b>来源与实证边界：</b>本页的 A4 总体算子属于经明确声明的符号研究资料；D2 固定配额在共享 ER300 图上是单独构造的假设性协议，不是 Estimation 的原 Bernoulli(.5) 实验。</p>
</section><footer>Research demonstration · No PFN call · No simulator ground-truth leakage · Model assumptions require expert validation.</footer>
</main><script type="application/json" id="data">''' + body + '''</script>
<script>
const r=JSON.parse(document.getElementById('data').textContent);
const metrics=[['Network nodes',r.node_count],['Verified arms',r.point_arm_count+' / '+r.arm_count],['Verified business queries',r.business_verified],['Safely blocked',r.business_rejected]];
document.getElementById('metrics').innerHTML=metrics.map(([label,n])=>'<div class="metric"><b>'+n+'</b><span>'+label+'</span></div>').join('');
const width=820, height=r.node_count*3+25, rowH=3, cellW=110, x0=120;
const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
svg.setAttribute('width','820');svg.setAttribute('height',String(height));
const NS='http://www.w3.org/2000/svg';const el=(name,attr,parent=svg)=>{let e=document.createElementNS(NS,name);Object.entries(attr).forEach(([k,v])=>e.setAttribute(k,String(v)));parent.appendChild(e);return e};
for(let c=0;c<4;c++){let t=el('text',{x:x0+c*cellW+5,y:13,'font-size':11,fill:'#5a6980'});t.textContent=r.arm_labels[c]}
for(let i=0;i<r.node_count;i++){if(i%25===0){let t=el('text',{x:2,y:26+i*rowH,'font-size':10,fill:'#6c7b8f'});t.textContent='node-'+i}
 for(let a=0;a<2;a++)for(let s=0;s<2;s++){let idx=2*a+s,status=r.arm_matrix_status[i][a][s],v=r.arm_matrix_support[i][a][s];
 let k=v==null?0:Math.min(1,Math.max(0,(v-.03)/.40));let light=86-48*k;
 let fill=status==='POINT'?`hsl(184,55%,${light}%)`:'#e4e7eb';
 let q=el('rect',{x:x0+idx*cellW,y:19+i*rowH,width:cellW-4,height:rowH-0.25,fill});
 q.addEventListener('mouseenter',()=>{document.getElementById('hover').textContent=`node-${i} · ${r.arm_labels[idx]} · ${status} · support≈${v==null?'undefined':v.toFixed(8)}`})}}
document.getElementById('heat').append(svg);
const area=document.getElementById('cases');
for(const c of r.business_cases){const card=document.createElement('article');card.className='case';
 const badge=document.createElement('span');badge.className='badge'+(c.status==='POINT'?'':' block');badge.textContent=c.status;card.append(badge);
 const h=document.createElement('h3');h.textContent=c.title;card.append(h);
 const p=document.createElement('p');p.textContent=c.explanation;card.append(p);
 const route=document.createElement('p');route.className='tag';route.textContent=c.route||c.reason||'Not routed';card.append(route);
 const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='查看识别记录 / 数学公式';
 const pre=document.createElement('pre');pre.textContent=JSON.stringify(c.result||c.attempted,null,2);details.append(summary,pre);card.append(details);area.append(card)}
</script></body></html>'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--er300',action='store_true')
    parser.add_argument('--part',choices=('assemble','r1a','r1b','r2'),default='assemble')
    parser.add_argument('--output-dir',type=Path,default=Path('showcase'))
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.part=='assemble':
        # Assembly is a PRESENTATION step and cannot create Identification
        # results. Requires separately run, verified per-family JSON records.
        payload={p:json.loads((args.output_dir/f'{p}_verified.json').read_text(encoding='utf-8'))
                 for p in ('r1a','r1b','r2')}
        data=combine(payload,args.er300)
        (args.output_dir/'network_identification_v21.json').write_text(
            json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (args.output_dir/'network_identification_v21.html').write_text(make_html(data),encoding='utf-8')
        print(json.dumps({k:data[k] for k in ('network','node_count', 'arm_count',
            'point_arm_count','business_verified','business_rejected')},ensure_ascii=False,indent=2))
    else:
        began=time.perf_counter()
        data={'r1a':run_r1a,'r1b':run_r1b,'r2':run_r2}[args.part](er300=args.er300)
        path=args.output_dir/f'{args.part}_verified.json'
        path.write_text(json.dumps(_as_json(data),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'{args.part}: verified; {time.perf_counter()-began:.2f}s',flush=True)


if __name__=='__main__':
    main()
