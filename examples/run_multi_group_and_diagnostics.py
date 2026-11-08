"""v2.5 real D5 and support-diagnostic showcase (no synthetic outcome values).

python -m examples.run_multi_group_and_diagnostics --output-dir /tmp/cfm_v25
Never counts a supported exposure alone as R2 POINT without admitted A5.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter
from fractions import Fraction
from math import comb

from examples.run_network_topology_matrix import topologies
from pfn_pipeline.identification import make_multi_group_quota_arm_task,identify,replay_population_identification
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec,CompleteRandomizationDesignV1,MultiGroupFixedQuotaDesignV25)
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec,ExposureSpec,SupportEngine
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import neighbor_set
from pfn_pipeline.network_inquiry_shadow import declare_network_study,fixed_policy_target_from_context
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_support_diagnostics import (
    diagnose_policy_signature_support_v25,replay_policy_signature_support_v25)

EXPOSURE={
 'E1':'strict_majority','E2':'three_level_treated_neighbor_fraction',
 'E3':'pretreatment_core_collaborator_majority',
 'E4':'exact_treated_neighbor_count','E5':'any_treated_neighbor',
}


def _study(net,design):
    return declare_network_study(network_id=net.network_id,node_order=tuple(net.node_ids),
        undirected_edges=tuple(tuple(e) for e in net.undirected_edges),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W:synthetic-review',observation_regime='experimental',
        assignment_design=design.model_dump(mode='json'),
        protocol_provenance='declared synthetic randomized experiment',
        network_provenance='fixed pretreatment network',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def _D5_design(net):
    nodes=tuple(net.node_ids)
    size=max(1,(len(nodes)+2)//3)
    groups=tuple(tuple(nodes[i:i+size]) for i in range(0,len(nodes),size))
    # Small deterministic fixtures always have >=3 groups; 300-node separate demo below.
    if len(groups)<3:
        groups=tuple(tuple(nodes[i::3]) for i in range(3))
    quotas=tuple((len(g)+1)//2 for g in groups)
    return MultiGroupFixedQuotaDesignV25(groups=groups,treated_quotas=quotas)


def _seed(net,design,exposure,core,node,a,s):
    return make_multi_group_quota_arm_task(net,groups=design.groups,treated_quotas=design.treated_quotas,
      node_id=node,own_treatment_value=a,exposure_value=s,
      exposure_definition=exposure,core_collaborators=core,
      source='synthetic documented D5 experiment',
      evidence='known pretreatment strata and quotas; independent exact-count check',
      admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')


def run_matrix():
    rows=[]
    for graph_name,net in topologies():
        design=_D5_design(net)
        assignment=AssignmentSpec(design)
        neighbors={n:neighbor_set(net,n) for n in net.node_ids}
        for ename,exposure_name in EXPOSURE.items():
            core=({node:(sorted(neighbors[node])[0],) for node in net.node_ids}
                  if ename=='E3' and all(neighbors.values()) else None)
            if ename=='E3' and core is None:
                rows.append(dict(graph=graph_name,design='D5',exposure=ename,
                    status='INVALID_GLOBAL_MAPPING',reason='E3_NO_PRETREATMENT_CORE_FOR_ISOLATE',
                    node=None,arm=None,support=None,certificate=None))
                continue
            exposure=ExposureSpec({
                'E1':'strict_majority_ties_low','E2':'three_level_treated_neighbor_fraction',
                'E3':'pretreatment_core_collaborator_majority',
                'E4':'exact_treated_neighbor_count','E5':'any_treated_neighbor'}[ename],core)
            chosen=None
            for node in net.node_ids:
                refs=exposure.reference_nodes(net,node)
                degree=len(refs) if refs is not None else net.degree_map()[node]
                if ename=='E2' and degree==0:continue
                for a in (0,1):
                    for s in exposure.states_for_degree(degree):
                        mass=SupportEngine.evaluate(network=net,assignment=assignment,
                            exposure=exposure,node_id=node,own_treatment_value=a,
                            exposure_value=s).joint_probability
                        if mass>0:
                            chosen=(node,a,s,mass);break
                    if chosen:break
                if chosen:break
            if not chosen:
                rows.append(dict(graph=graph_name,design='D5',exposure=ename,
                    status='NO_POSITIVE_ARM',reason='DESIGN_HAS_NO_VALID_POSITIVE_CELL',
                    node=None,arm=None,support=None,certificate=None))
                continue
            node,a,s,mass=chosen
            q=_seed(net,design,exposure_name,core,node,a,s)
            r=identify(q)
            if r.status!='POINT' or r.verification_status!='VERIFIED' or not replay_population_identification(r):
                raise AssertionError(f'Positive D5 arm was not independently certified: {(graph_name,ename)}')
            if Fraction(r.result['certificate']['joint_arm_support_probability'])!=mass:
                raise AssertionError('D5 selected arm support differs from theorem certificate')
            status='POINT_ARM_VERIFIED' if (ename!='E2' or all(neighbors.values())) else 'POINT_ON_VALID_NODE'
            rows.append(dict(graph=graph_name,design='D5',exposure=ename,
                status=status,reason=None,node=node,arm=[a,s],support=str(mass),
                certificate=r.result['certificate'].get('rule_id') or r.result['certificate'].get('theorem_id')))
    return dict(version='v2.5',graph_count=9,design='D5_multi_group_fixed_quotas',
       exposure_count=5,cases=len(rows),status_counts=dict(Counter(x['status'] for x in rows)),
       rows=rows,note='A positive row certifies only ONE selected arm, not all arms, not estimation and not actual business coverage')


def run_support_comparison():
    nodes=tuple(str(i) for i in range(7))
    net=NetworkExposureSpec(network_id='seven-star-v25',node_ids=list(nodes),
        undirected_edges=[('0',j) for j in nodes[1:]])
    st=_study(net,CompleteRandomizationDesignV1(m=3))
    target=fixed_policy_target_from_context(st,(1,)*7,authority='TRUSTED_FIXTURE')
    rows=[]
    for exp in ('strict_majority_ties_low','exact_treated_neighbor_count','any_treated_neighbor'):
        sig=declare_policy_signature(st,grouping=exp)
        check=diagnose_policy_signature_support_v25(st,target,sig)
        replay_policy_signature_support_v25(check,st,target,sig)
        rows.append(check.summary())
    return dict(case='star7-D2-m3-all-treated',policy='all treated',
        note='Changing signature changes A5 meaning; alternative quotas require NEW data',
        comparisons=rows)


def run_large_ring():
    n=300
    nodes=tuple(f'node-{i}' for i in range(n))
    net=NetworkExposureSpec(network_id='ring300-multi-stratum-v25',node_ids=list(nodes),
        undirected_edges=[(nodes[i],nodes[(i+1)%n]) for i in range(n)])
    groups=tuple(nodes[i:i+5] for i in range(0,n,5))
    d=MultiGroupFixedQuotaDesignV25(groups=groups,treated_quotas=(2,)*60)
    rows=[]
    for exp,state in [('strict_majority',0),('any_treated_neighbor',1),('exact_treated_neighbor_count',1)]:
        node='node-1';a=1
        t=_seed(net,d,exp,None,node,a,state)
        r=identify(t)
        if r.status!='POINT' or r.verification_status!='VERIFIED' or not replay_population_identification(r):
            raise AssertionError(f'Ring300 D5 arm not verified {exp}')
        rows.append(dict(exposure=exp,arm=[a,state],joint_support=r.result['certificate']['joint_arm_support_probability'],
            verification='VERIFIED',target_fingerprint=t.target_fingerprint))
    return dict(graph='Ring300',nodes=n,groups=60,treated_quota_each=2,
        design_kind=d.kind,rows=rows,
        note='Three chosen verified arms; no ER network and no PFN estimation')


def render_html(matrix,support,large):
    obj=json.dumps(dict(matrix=matrix,support=support,large=large),ensure_ascii=False,separators=(',',':'))
    obj=obj.replace('</','<\\/').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CFM-ID v2.5 · D5 & A6 Support</title>
<style>body{font-family:system-ui,-apple-system,"Noto Sans SC",sans-serif;background:#f6f7fb;color:#1c2634;margin:0}.wrap{max-width:1150px;margin:auto;padding:28px}h1{font-size:28px;margin-bottom:8px}p{color:#58677a;line-height:1.65}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stat,.panel{padding:18px;background:white;border:1px solid #e2e6ec;border-radius:12px}.number{font-size:27px;font-weight:700}small{color:#667487}.panel{margin-top:18px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:10px;border-bottom:1px solid #eff1f4;text-align:left}th{background:#f6f8fa}select{padding:9px;margin:4px;border-radius:8px;border:1px solid #ced6df}.scroll{max-height:410px;overflow:auto}.badge{border-radius:8px;padding:3px 8px;background:#eef2f5}.good{background:#daf4e6;color:#145e45}.bad{background:#fae5e5;color:#953b3b}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}ul{padding-left:17px}li{margin:8px 0}pre{white-space:pre-wrap;word-break:break-word;background:#f6f8fa;padding:10px} @media(max-width:780px){.stats,.cards{grid-template-columns:1fr 1fr}.wrap{padding:12px}}</style>
</head><body><div class="wrap"><h1>Causal-IDFM v2.5：D5 多组配额与零支持诊断</h1><p>D5 是既有 R1a/R1b/R2 数学定理下的新实验设计，并非新的 Family。所有绿色 POINT 来自真实求解器及独立重放。A6 零支持诊断本身不产生因果 POINT。</p>
<div id="stats" class="stats"></div><section class="panel"><h2>D5 × E1–E5 × 9 种固定网络</h2><label>图 <select id="graph"><option value="">全部</option></select></label><label> Exposure <select id="exp"><option value="">全部</option></select></label><p><small>每个成功组合仅证明至少一个指定 arm，不表示全图所有 arms 均有支持。</small></p><div class="scroll"><table><thead><tr><th>网络</th><th>设计</th><th>Exposure</th><th>状态</th><th>已验证 Arm</th><th>Support</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="panel"><h2>七节点 Star：相同政策，不同 signature 的支持</h2><p>固定处理 3 人，全员使用 AI；切换 signature 也改变了所需的充分性假设，不能为提高支持而擅自更换。</p><div id="support" class="cards"></div></section>
<section class="panel"><h2>非 ER 大图：Ring300 × D5</h2><div id="large"></div><p>以上只是符号总体识别公式、支持计算与证书重放，没有数值政策收益和 PFN 预测。</p></section></div>
<script>const DATA=__DATA__;const mx=DATA.matrix,sv=DATA.support,lg=DATA.large;
function elt(tag,props={},content=''){let e=document.createElement(tag);Object.entries(props).forEach(([k,v])=>{if(k==='className')e.className=v;else e.setAttribute(k,v)});e.textContent=String(content);return e}
function fill(){let stats=document.getElementById('stats');[[mx.cases,'D5 × E 组合'],[mx.graph_count,'网络类型'],[mx.status_counts.POINT_ARM_VERIFIED||0,'全图 Exposure 合法且找到 POINT arm'],[mx.status_counts.POINT_ON_VALID_NODE||0,'仅有效节点有 POINT arm']].forEach(([n,name])=>{let b=elt('div',{className:'stat'});b.append(elt('div',{className:'number'},n),elt('small',{},name));stats.append(b)});
let sel=document.getElementById('graph'),ex=document.getElementById('exp');[...new Set(mx.rows.map(x=>x.graph))].sort().forEach(x=>sel.append(elt('option',{value:x},x)));['E1','E2','E3','E4','E5'].forEach(x=>ex.append(elt('option',{value:x},x)));sel.onchange=show;ex.onchange=show;show();
let box=document.getElementById('support');sv.comparisons.forEach(x=>{let center=x.nodes.find(n=>n.node_id==='0');let c=elt('div',{className:'stat'});c.append(elt('h3',{},x.grouping),elt('p',{},'中心签名支持 '+center.signature_probability),elt('p',{},'全图未支持节点 '+x.unsupported_weighted_nodes),elt('small',{},'中心可达到的邻居处理人数：'+center.feasible_reference_neighbor_counts.join(', ')),elt('p',{},center.reason_code));if(x.counterfactual_d2_quotas_with_full_support)c.append(elt('small',{},'未来新实验可能的 m：'+x.counterfactual_d2_quotas_with_full_support.join(', ')));box.append(c)});
let large=document.getElementById('large');large.append(elt('p',{},lg.nodes+' 个节点 · '+lg.groups+' 组 · 每组处理 '+lg.treated_quota_each+' 人'));lg.rows.forEach(x=>large.append(elt('p',{},x.exposure+' · arm '+x.arm.join('/')+' · support='+x.joint_support+' · '+x.verification)))}
function show(){let body=document.getElementById('rows');body.replaceChildren();mx.rows.filter(x=>(!document.getElementById('graph').value||x.graph===document.getElementById('graph').value)&&(!document.getElementById('exp').value||x.exposure===document.getElementById('exp').value)).forEach(x=>{let tr=elt('tr');[x.graph,x.design,x.exposure,x.status,x.arm?x.arm.join(', '):'—',x.support||'—'].forEach((v,i)=>{let td=elt('td');if(i===3){td.append(elt('span',{className:'badge '+(x.status.includes('POINT')?'good':'bad')},v))}else td.textContent=v;tr.append(td)});body.append(tr)})}
fill();</script></body></html>'''.replace('__DATA__',obj)


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    matrix=run_matrix();support=run_support_comparison();large=run_large_ring()
    for name,value in [('CFM_ID_v2_5_45_D5_Cross_Topology.json',matrix),
       ('CFM_ID_v2_5_Star7_Support_Diagnostics.json',support),
       ('CFM_ID_v2_5_Ring300_D5_Proofs.json',large)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    (out/'CFM_ID_v2_5_D5_and_Support_Dashboard.html').write_text(render_html(matrix,support,large))
    return dict(matrix=matrix,support=support,large=large)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default='showcase_v25')
    args=ap.parse_args();summary=run(Path(args.output_dir))
    print(json.dumps({'cases':summary['matrix']['cases'],'statuses':summary['matrix']['status_counts'],
        'star_center_support':{x['grouping']:next(n['signature_probability'] for n in x['nodes'] if n['node_id']=='0')
                               for x in summary['support']['comparisons']},
        'ring300_support':[x['joint_support'] for x in summary['large']['rows']]},ensure_ascii=False))
