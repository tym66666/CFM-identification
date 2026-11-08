"""v2.4: 9 fixed graphs × D1/D2/D3/D4 × E1/E2/E3/E4/E5.

Runnable: python -m examples.run_common_design_exposure --output-dir /tmp/v24_demo
All POINT claims use the actual formal identifier + proof replay. All A4
population operators are declared SYNTHETIC SYMBOLIC, not observed effects.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from fractions import Fraction

from examples.run_network_topology_matrix import topologies
from pfn_pipeline.identification import (
    identify, replay_population_identification,
    make_complete_randomization_arm_task, make_two_group_quota_arm_task,
    make_heterogeneous_bernoulli_arm_task, make_cluster_bernoulli_arm_task,
)
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import neighbor_set
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context,
)
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, declare_signature_population_source,
    admit_mean_signature_sufficiency, identify_verified_signature_policy, R2PolicyUnavailable,
)
from pfn_pipeline._internal.identification.schemas import Assumption

EXP={
 'E1':'strict_majority', 'E2':'three_level_treated_neighbor_fraction',
 'E3':'pretreatment_core_collaborator_majority',
 'E4':'exact_treated_neighbor_count', 'E5':'any_treated_neighbor',
}
GROUP={
 'E1':'strict_majority_ties_low', 'E2':'three_level_treated_neighbor_fraction',
 'E3':'pretreatment_core_collaborator_majority',
 'E4':'exact_treated_neighbor_count','E5':'any_treated_neighbor',
}
A5=('known_assignment_law','full_vector_randomization','consistency',
    'fixed_pretreatment_network','finite_conditional_first_moments')


def explicit_design(net, name):
    nodes=tuple(net.node_ids);n=len(nodes)
    if name=='D1':
        return make_heterogeneous_bernoulli_arm_task,{'propensities':{x:'1/2' for x in nodes}}
    if name=='D2':
        return make_complete_randomization_arm_task,{'m':n//2}
    if name=='D3':
        left,right=nodes[:n//2],nodes[n//2:]
        return make_two_group_quota_arm_task,{'groups':(left,right),
               'treated_quotas':(len(left)//2,len(right)//2)}
    if name=='D4':
        clusters=tuple(nodes[i:i+2] for i in range(0,n,2))
        p=tuple(('1/2','2/3','1/3','3/4')[i%4] for i in range(len(clusters)))
        return make_cluster_bernoulli_arm_task,{
               'clusters':clusters,'cluster_probabilities':p}
    raise ValueError(name)


def run_matrix():
    cases=[]
    for name,net in topologies():
        neighbor={n:neighbor_set(net,n) for n in net.node_ids}
        isolates=[n for n in net.node_ids if not neighbor[n]]
        for d in ('D1','D2','D3','D4'):
            maker,options=explicit_design(net,d)
            for e in ('E1','E2','E3','E4','E5'):
                core=({n:(sorted(neighbor[n])[0],) for n in net.node_ids}
                      if e=='E3' and not isolates else None)
                if e=='E3' and isolates:
                    cases.append(dict(graph=name,design=d,exposure=e,
                        status='INVALID_GLOBAL_MAPPING',reason='E3_REQUIRES_NONEMPTY_CORE_FOR_ALL_NODES',
                        point_node=None,point_arm=None,point_support=None, certificate=None,
                        global_mapping_defined=False))
                    continue
                grouping=ExposureSpec(GROUP[e],core)
                global_defined=not(e=='E2' and isolates)
                pos=None
                # Select a reproducible, genuinely supported arm, NOT just an
                # arbitrary cell or a hand-authored POINT label.
                for node in net.node_ids:
                    if e=='E2' and not neighbor[node]:continue
                    ref=grouping.reference_nodes(net,node)
                    degree=len(ref) if ref is not None else len(neighbor[node])
                    # Constructor certifies typed D4 q later. For candidate search,
                    # construct one legal arm once; avoid any information from Y.
                    candidate=maker(net,**options,node_id=node,own_treatment_value=0,
                        exposure_value=0, exposure_definition=EXP[e],core_collaborators=core,
                        source='v2.4 synthetic known assignment fixture',
                        evidence='reviewed fixed-network test protocol',
                        admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
                    from pfn_pipeline._internal.identification.schemas import IdentificationSpec
                    contract=IdentificationSpec.model_validate(candidate.identification_spec).randomized_network_arm_theorem_contract
                    assignment=AssignmentSpec(contract.design)
                    for a in (0,1):
                        for s in grouping.states_for_degree(degree):
                            mass=SupportEngine.evaluate(network=net,assignment=assignment,
                                exposure=grouping,node_id=node,own_treatment_value=a,
                                exposure_value=s).joint_probability
                            if mass>0:
                                pos=(node,a,s,mass);break
                        if pos:break
                    if pos:break
                if pos is None:
                    cases.append(dict(graph=name,design=d,exposure=e,status='NO_POSITIVE_ARM',
                        reason='ALL_QUERIED_CELLS_ZERO_SUPPORT',global_mapping_defined=global_defined,
                        point_node=None,point_arm=None,point_support=None,certificate=None))
                    continue
                node,a,s,computed=pos
                task=maker(net,**options,node_id=node,own_treatment_value=a,
                    exposure_value=s,exposure_definition=EXP[e],core_collaborators=core,
                    source='v2.4 synthetic known assignment fixture',
                    evidence='reviewed fixed-network test protocol',
                    admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
                result=identify(task)
                if result.status!='POINT' or result.verification_status!='VERIFIED':
                    raise AssertionError(f'Uncertified actual arm: {name,d,e} {result.result.get("reason_code")}')
                replayed=replay_population_identification(result)
                if replayed.verification_status!='VERIFIED':
                    raise AssertionError('Proof replay failed')
                pi=result.result['certificate']['joint_arm_support_probability']
                if Fraction(pi)!=computed:raise AssertionError('Support differs from candidate exact law')
                cases.append(dict(graph=name,design=d,exposure=e,
                    status='POINT_ON_ELIGIBLE_NODE' if not global_defined else 'POINT_ARM_VERIFIED',
                    reason='GRAPH_CONTAINS_ISOLATE_E2_UNDEFINED' if not global_defined else None,
                    global_mapping_defined=global_defined,point_node=node,point_arm=[a,s],
                    point_support=pi, certificate=result.result['certificate']['rule_id'],
                    target_fingerprint=task.target_fingerprint))
    return dict(version='v2.4-common-assignment-exposure',graph_count=9,design_count=4,
          exposure_count=5,combination_count=len(cases),status_counts=dict(sorted(Counter(c['status'] for c in cases).items())),
          entries=cases, note='Each positive entry certifies at least ONE arm, not all node arms or numerical effects.')


def star_support_demo():
    net=next(n for key,n in topologies() if key=='star')
    nodes=tuple(net.node_ids)
    d={'kind':'complete_randomization_binary_v1','m':3}
    st=declare_network_study(network_id=net.network_id,node_order=nodes,
          undirected_edges=tuple(map(tuple,net.undirected_edges)),
          treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
          context_reference='W:synthetic-star',observation_regime='experimental',
          assignment_design=d,protocol_provenance='declared synthetic fixed quota',
          network_provenance='fixed star',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    target=fixed_policy_target_from_context(st,tuple(1 for _ in nodes),authority='TRUSTED_FIXTURE')
    assumptions=tuple(Assumption(name=x,source='demo_specification',confirmed=True,
                   evidence=['documented synthetic randomized protocol']) for x in A5)
    entries=[]
    for e in ('E1','E4','E5'):
        sig=declare_policy_signature(st,grouping=GROUP[e])
        suff=admit_mean_signature_sufficiency(st,sig,
            covered_nodes=nodes,
            assumption=Assumption(name='mean_signature_sufficiency',
                source='human_confirmation',status='ADMITTED',confirmed=True,
                evidence=['explicit hypothetical structural assumption for THIS signature']))
        source=declare_signature_population_source(st,sig,source_id=f'A4-{e}',
            operator='NODE_FULL_LAW',outcome_nodes=nodes,
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            provenance='hypothetical declared population operator, not measurements')
        try:
            r=identify_verified_signature_policy(st,target,sig,(source,),
                  assumptions=assumptions,sufficiency=suff)
            entries.append(dict(exposure=e,status='POINT',q_policy=r.policy_assignment_probability,
                signature_support=dict(zip((x[0] for x in r.policy_node_classes),r.node_class_support)),
                identified_functional=r.identified_functional,proof=r.certificate_sha256))
        except R2PolicyUnavailable as exc:
            assignment=AssignmentSpec(st.design())
            exposure=ExposureSpec(sig.grouping)
            nodes_support={}
            z=dict(zip(nodes,target.policy_assignment))
            for node in nodes:
                refs=neighbor_set(net,node)
                count=sum(z[x] for x in refs)
                arm_s=exposure.classify(count,len(refs))
                prob=SupportEngine.evaluate(network=net,assignment=assignment,
                    exposure=exposure,node_id=node,own_treatment_value=1,
                    exposure_value=arm_s).joint_probability
                nodes_support[node]=str(prob)
            entries.append(dict(exposure=e,status='UNSUPPORTED',reason=exc.reason_code,
                q_policy='0',signature_support=nodes_support))
    return dict(graph='star',n=7,m=3,policy='all treated',
                explicitly_accepted_sufficiency_per_exposure=True,
                disclaimer='Different mean-sufficiency assumptions; cannot swap for support alone',entries=entries)


def html(matrix,star):
    payload=json.dumps({'matrix':matrix,'star':star},ensure_ascii=False,separators=(',',':'))
    payload=payload.replace('</','<\\/').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CFM-ID v2.4 · Assignment & Exposure Coverage</title>
<style>body{font-family:system-ui,-apple-system,"Noto Sans SC",sans-serif;background:#f5f7fb;color:#172637;margin:0}.wrap{max-width:1170px;margin:auto;padding:28px}h1{margin:0 0 7px;font-size:28px}.sub{color:#586b81;line-height:1.7}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}.stat,.panel{background:white;border-radius:14px;border:1px solid #e4eaf0;padding:17px}.num{font-size:29px;font-weight:750}.lbl{color:#586b81;font-size:12px}.panel{margin:16px 0}h2{font-size:19px;margin:0 0 15px}.flex{display:flex;flex-wrap:wrap;gap:10px}select,input{font:inherit;padding:9px 12px;border:1px solid #cdd5df;border-radius:9px;background:white}.chip{border-radius:9px;padding:5px 9px;font-size:12px;background:#eef2f8;white-space:nowrap}.ok{background:#e0f4ee;color:#126c53}.warn{background:#fff1dc;color:#865317}.bad{background:#f8e6e5;color:#a33b3b}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:#586b81;background:#f7f9fc}td,th{padding:9px;border-bottom:1px solid #edf0f3}.scroll{overflow:auto;max-height:470px}pre{white-space:pre-wrap;word-break:break-word;background:#f7f9fc;padding:12px;border-radius:9px;font-size:12px}.star{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.title{font-weight:700}.small{font-size:12px;color:#69788b}.notice{border-left:4px solid #ce903a;padding:10px 15px;background:#fff8e8;border-radius:4px}@media(max-width:700px){.stats{grid-template-columns:repeat(2,1fr)}.star{grid-template-columns:1fr}.wrap{padding:14px}}</style></head><body><div class="wrap"><h1>Network Identification · v2.4</h1><div class="sub">D1–D4 Assignment × E1–E5 Exposure × 9 种固定网络。所有 POINT 状态由真实定理调用和证书重放生成。</div>
<div id="stats" class="stats"></div><div class="panel"><h2>为什么签名支持会是零？</h2><div class="notice">七节点 Star，固定每次处理三人，查询全员 AI。即使某个 Exposure 的 support 为正，R2 也必须另外确认它对结果均值充分，绝不自动推断。</div><div id="star" class="star" style="margin-top:14px"></div></div>
<div class="panel"><h2>跨网络拓扑与设计矩阵</h2><div class="flex"><select id="graph"><option value="">所有网络</option></select><select id="design"><option value="">所有分配设计</option></select><select id="exposure"><option value="">所有暴露规则</option></select><select id="status"><option value="">所有结果</option></select></div><p class="small" id="filtercount"></p><div class="scroll"><table><thead><tr><th>图</th><th>设计</th><th>Exposure</th><th>识别/定义状态</th><th>示例节点</th><th>精确 arm support</th></tr></thead><tbody id="rows"></tbody></table></div></div>
<p class="small">研究软件原型 · 不包括 PFN 数值估计 · 所有 A4 为假设性符号总体算子 · 不代表现实业务假设已被验证。D4 指固定簇、簇级独立 Bernoulli，而非固定簇配额或两阶段设计。</p></div><script id="payload" type="application/json">'''+payload+'''</script><script>(function(){const d=JSON.parse(document.getElementById('payload').textContent), m=d.matrix, records=m.entries;const text=(tag,val,cl)=>{const e=document.createElement(tag);e.textContent=val;if(cl)e.className=cl;return e};const el=id=>document.getElementById(id);for(const [num,name] of [[m.graph_count,'网络拓扑'],[m.design_count*m.exposure_count,'D × E 类型'],[m.combination_count,'实际组合测试'],[m.status_counts.POINT_ARM_VERIFIED||0,'全图 Exposure 合法且示例 POINT']]){let b=text('div','','stat');b.append(text('div',num,'num'),text('div',name,'lbl'));el('stats').append(b)}for(const s of d.star.entries){let c=text('div','','stat');c.append(text('div',s.exposure,'title'),text('div',s.status,s.status==='POINT'?'chip ok':'chip bad'),text('div','中心节点支持：'+s.signature_support['0'],'small'),text('div',s.reason||'已通过 R2 证书重放','small'));el('star').append(c)}function options(id,field){const v=[...new Set(records.map(x=>x[field]))].sort();for(const q of v){let x=document.createElement('option');x.value=q;x.textContent=q;el(id).append(x)}}[['graph','graph'],['design','design'],['exposure','exposure'],['status','status']].forEach(q=>options(...q));function draw(){let arr=records.filter(x=>['graph','design','exposure','status'].every(f=>!el(f).value||el(f).value===x[f]));let body=el('rows');body.replaceChildren();for(const x of arr){let tr=document.createElement('tr');for(const v of [x.graph,x.design,x.exposure,x.status,x.point_node||'—',x.point_support||'—'])tr.append(text('td',v));body.append(tr)}el('filtercount').textContent='显示 '+arr.length+' / '+records.length+' 项；POINT_ON_ELIGIBLE_NODE 表示含孤立点时仅部分节点的 exposure 有定义。'}for(const id of ['graph','design','exposure','status'])el(id).addEventListener('change',draw);draw()})();</script></body></html>'''


def run(outdir: Path):
    m=run_matrix();s=star_support_demo();outdir.mkdir(parents=True,exist_ok=True)
    for name,data in [('CFM_ID_v2_4_180_Design_Exposure_Cases.json',m),
                      ('CFM_ID_v2_4_Star_Support_Remedy.json',s)]:
        (outdir/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (outdir/'CFM_ID_v2_4_Assignment_Exposure_Showcase.html').write_text(html(m,s),encoding='utf-8')
    print('matrix:',m['combination_count'],m['status_counts'])
    print('star:',[(x['exposure'],x['status'],x['signature_support']['0']) for x in s['entries']])
    return m,s

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',default='v24_demo');args=p.parse_args()
    run(Path(args.output_dir))
