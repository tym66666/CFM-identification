"""Small-network R3 POINT and explanatory D2/E1 quota support demo.

Run:
  python -B -m examples.run_observational_r3_and_signature --output-dir showcase_v23

No real observational data, no learned ignorability, no PFN estimates.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
from itertools import combinations
import json,html
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.network_inquiry_shadow import declare_network_study,fixed_policy_target_from_context
from pfn_pipeline.identification_policy_r2 import declare_policy_signature,admit_mean_signature_sufficiency
from pfn_pipeline.identification_observational_r3 import (
    declare_observational_population_v23,identify_observational_policy_v23,R3Unavailable)
from pfn_pipeline.identification_signature_diagnostics import diagnose_majority_quota_policy_v23
from pfn_pipeline.identification_business import (
    ObservationalPolicyInquiryV23,identify_network_business_query,replay_verified_business_outcome)


def case():
    nodes=tuple(f'staff_{k}' for k in range(5))
    star=tuple((nodes[0],n) for n in nodes[1:])
    study=declare_network_study(network_id='STAR5_OBSERVATIONAL_SYNTHETIC',
        node_order=nodes,undirected_edges=star,treatment_variable='AI_USE',
        outcome_variable='SALES',outcome_kind='continuous',context_reference='W=w0',
        observation_regime='observational',assignment_design=None,
        protocol_provenance='SYNTHETIC observational study, not a randomized experiment',
        network_provenance='pretreatment fixed star',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    # A population distribution; all five assignments have exactly 4 treated,
    # but this distribution is OBSERVATIONAL, not assumed randomized.
    table=[]
    for omitted in range(5):
        table.append((tuple(0 if k==omitted else 1 for k in range(5)),Fraction(1,5)))
    source=declare_observational_population_v23(study,
        source_id='synthetic-exact-observational-population',
        provenance='REVIEWED DEMONSTRATION ONLY: exact conditional Pobs(T|W) and SYMBOLIC E[Yobs|T,W]',
        assignment_masses=table,outcome_nodes=nodes)
    assumptions=tuple(Assumption(name=name,source='demo_specification',confirmed=True,
        evidence=['RESEARCH SYNTHETIC MODEL: assumption explicitly posited; NOT inferred from data'])
        for name in ('full_vector_conditional_exchangeability','consistency',
                     'fixed_pretreatment_network','finite_conditional_first_moments'))
    all_treated=fixed_policy_target_from_context(study,(1,1,1,1,1),authority='TRUSTED_FIXTURE')
    supported=fixed_policy_target_from_context(study,(0,1,1,1,1),authority='TRUSTED_FIXTURE')
    signature=declare_policy_signature(study,grouping='strict_majority_ties_low')
    suff=admit_mean_signature_sufficiency(study,signature,covered_nodes=nodes,
        assumption=Assumption(name='mean_signature_sufficiency',source='demo_specification',confirmed=True,
            evidence=['SYNTHETIC MODEL: mean outcome equals h_i(T_i,majority_i,W) for all assignments']))
    full=identify_network_business_query(ObservationalPolicyInquiryV23(
        study,supported,source,assumptions))
    extrapolate=identify_network_business_query(ObservationalPolicyInquiryV23(
        study,all_treated,source,assumptions,signature,suff))
    blocked=identify_network_business_query(ObservationalPolicyInquiryV23(
        study,all_treated,source,assumptions))
    unconfirmed=tuple(a for a in assumptions if a.name!='full_vector_conditional_exchangeability')
    missing=identify_network_business_query(ObservationalPolicyInquiryV23(
        study,supported,source,unconfirmed))
    sample_source=declare_observational_population_v23(study,
        source_id='finite-sample-histogram-pretending-population',
        provenance='synthetic sample data, not a population operator',
        assignment_masses=table,availability='FINITE_SAMPLE_ESTIMATE')
    finite_sample=identify_network_business_query(ObservationalPolicyInquiryV23(
        study,supported,sample_source,assumptions))
    assert full.status=='POINT' and full.route=='R3_FULL_ASSIGNMENT'
    assert extrapolate.status=='POINT' and extrapolate.route=='R3_MEAN_SIGNATURE'
    assert replay_verified_business_outcome(full) and replay_verified_business_outcome(extrapolate)
    assert blocked.reason_code=='ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT'
    assert missing.status!='POINT' and finite_sample.status!='POINT'

    graphs={
        'Path7':tuple((f'n{i}',f'n{i+1}') for i in range(6)),
        'Ring7':tuple((f'n{i}',f'n{(i+1)%7}') for i in range(7)),
        'Star7':tuple(('n0',f'n{i}') for i in range(1,7)),
        'Complete7':tuple((f'n{i}',f'n{j}') for i in range(7) for j in range(i+1,7)),
    }
    topology=[]
    for name,edges in graphs.items():
        st=declare_network_study(network_id='D2_E1_'+name,
            node_order=tuple(f'n{i}' for i in range(7)),undirected_edges=edges,
            treatment_variable='AI_USE',outcome_variable='SALES',
            outcome_kind='continuous',context_reference='W=w0',
            observation_regime='experimental',
            assignment_design={'kind':'complete_randomization_binary_v1','m':3},
            protocol_provenance='SYNTHETIC D2 3/7 FIXED QUOTA',
            network_provenance='fixed pretreatment graph',
            graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
        tgt=fixed_policy_target_from_context(st,(1,)*7,authority='TRUSTED_FIXTURE')
        result=diagnose_majority_quota_policy_v23(st,tgt)
        topology.append({'graph':name,'edges':[list(e) for e in edges],**result.summary()})
    return {
      'version':'v2.3',
      'methodology':'Exact synthetic conditional population operator; untestable observational A5 explicitly posited',
      'observational_policy':{
          'supported_full':full.summary(),'offsupport_with_mean_suff':extrapolate.summary(),
          'offsupport_without_mean_suff':blocked.summary(),
          'exchangeability_not_confirmed':missing.summary(),
          'only_finite_sample':finite_sample.summary()},
      'majority_quota_support':topology,
      'disclaimer':'No real-world estimand values, no sampling uncertainty or PFN Estimation; R3 finite enumeration <=12 nodes',
    }


def dashboard(data):
    cases=data['observational_policy'];graphs=data['majority_quota_support']
    rows=[]
    titles=[('supported_full','R3 full-assignment conditional adjustment'),
            ('offsupport_with_mean_suff','R3 signature adjustment with extra A5'),
            ('offsupport_without_mean_suff','Off-support without sufficiency'),
            ('exchangeability_not_confirmed','Unconfirmed observational exchangeability'),
            ('only_finite_sample','Finite sample is not population A4')]
    for key,label in titles:
        d=cases[key];rows.append('<tr><td>'+html.escape(label)+'</td><td><b>'+html.escape(d['status'])+'</b></td><td>'+html.escape(str(d.get('route')))+'</td><td>'+html.escape(str(d.get('reason_code')))+'</td></tr>')
    tiles=[]
    for graph in graphs:
        gaps=[v for v in graph['nodes'] if v['signature_probability']=='0']
        degree=max(v['degree'] for v in graph['nodes'])
        expl=('; '.join(f"{v['node_id']}: need {v['minimum_required_treated_neighbors']} treated neighbors, at most {v['maximum_feasible_treated_neighbors']}" for v in gaps[:3])) or 'All nodes have positive target signature support'
        tiles.append(f'''<article class="tile"><h3>{html.escape(graph['graph'])}</h3>
          <p><strong>{graph['supported_weighted_nodes']}/7</strong> supported nodes · max degree {degree}</p>
          <div class="bar"><div style="width:{100*graph['supported_weighted_nodes']/7:.1f}%"></div></div>
          <p class="small">{html.escape(expl)}</p></article>''')
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>CFM-ID v2.3 R3 &amp; Signature Support</title>
    <meta name="viewport" content="width=device-width,initial-scale=1"><style>
    body{{margin:0;background:#f5f7fb;color:#202e43;font:15px/1.7 system-ui,-apple-system,sans-serif}}
    main{{max-width:1040px;margin:auto;padding:45px 22px}}
    h1{{font-size:34px;line-height:1.18}}h2{{margin-top:42px}}
    .pill{{background:#dcecea;border-radius:20px;color:#187c66;font-weight:bold;padding:5px 10px}}
    .muted,.small{{color:#66778d;font-size:13px}}section,.tile{{background:#fff;border:1px solid #d9e2ed;border-radius:17px;padding:24px;margin-top:16px}}
    table{{width:100%;border-collapse:collapse}}th,td{{padding:12px;border-bottom:1px solid #e7edf3;text-align:left;vertical-align:top}}
    th{{background:#f4f7fb}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
    .tile{{margin:0}}.tile h3{{margin:0}}.bar{{background:#e5e9f0;height:12px;border-radius:9px;overflow:hidden}}.bar div{{height:100%;background:#258f7d}}
    .notice{{background:#fff5e7;border-left:4px solid #c8924a;padding:16px;margin:22px 0}}
    @media(max-width:650px){{.grid{{grid-template-columns:1fr}}main{{padding:20px 12px}}}} </style></head><body><main>
    <span class="pill">Causal-IDFM · Identification v2.3</span>
    <h1>Observational Network R3<br>与 Signature Support 解释</h1>
    <p class="muted">所有输出来自代码执行、数学证书重放与独立组合计数；合成模型，不代表真实企业效果。</p>
    <section><h2>01 · 观测网络政策识别</h2><p>五节点 Star；观测分配恰好四人 treated，完整全员政策从未出现。只有在额外接受结构充分性时，才能从局部签名恢复其政策均值。</p>
    <table><thead><tr><th>查询</th><th>识别状态</th><th>Route</th><th>解释代码</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
    <p class="small">R3 需要明确接受 full-vector conditional exchangeability。因果假设的真实性不能由样本数据、指纹或软件验证器判定。</p></section>
    <section><h2>02 · 七节点 D2 配额 / E1 Majority 支持对比</h2>
    <p>原实验固定 3/7 treated；政策全员 treated。颜色条显示 7 个节点中各自的政策签名具有正支持的数量，并非真实政策效果。</p>
    <div class="grid">{''.join(tiles)}</div><div class="notice">Star 中心节点需要至少 4 个 treated 邻居，但保留本人 1 个名额后只剩 2 个，因此该节点的政策签名概率严格等于 0。R2 这条公式不能使用；不等于已证明政策完全无法识别。</div></section>
    <p class="muted">边界：已知固定无向网络 · 单时点二元处理 · 固定条件 W · R3 有限总体 assignment 表 N≤12 · 无估计器 · 不含 D4/E4/E5。</p>
    </main></body></html>'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,
                                                    default=Path('showcase_v23'))
    args=parser.parse_args();args.output_dir.mkdir(exist_ok=True,parents=True)
    d=case()
    json_path=args.output_dir/'CFM_ID_v2_3_R3_and_Signature_Support.json'
    html_path=args.output_dir/'CFM_ID_v2_3_R3_and_Signature_Support.html'
    json_path.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    html_path.write_text(dashboard(d),encoding='utf8')
    print(json.dumps({'version':'v2.3','observational_cases':{
       k:(v['status'],v['route'],v['reason_code']) for k,v in d['observational_policy'].items()},
        'topology':{x['graph']:{'supported':x['supported_weighted_nodes'],
                              'zero':x['unsupported_weighted_nodes']} for x in d['majority_quota_support']},
        'html':str(html_path),'json':str(json_path)},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
