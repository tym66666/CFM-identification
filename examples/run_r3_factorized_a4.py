"""Offline symbolic R3 factorized A4 showcase; no observed samples or effects."""
from __future__ import annotations

import argparse
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
import html
import json
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26,identify_network_business_query,
    replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_observational_factorized_a4 import (
    declare_observational_factorized_arm_population_v27p1,
)
from pfn_pipeline.network_inquiry_shadow import declare_network_study

BASE='CFM_ID_v2_7_P1_R3_Factorized_A4_300_Node'


def run():
    nodes=tuple('n'+str(i) for i in range(300))
    study=declare_network_study(network_id='OBS_RING300_SYNTHETIC',node_order=nodes,
        undirected_edges=tuple((nodes[i],nodes[(i+1)%300]) for i in range(300)),
        treatment_variable='AI',outcome_variable='Symbolic_Outcome',outcome_kind='continuous',
        context_reference='W=w_fixed_before_AI',observation_regime='observational',
        assignment_design=None,protocol_provenance='SYNTHETIC finite-population observational protocol',
        network_provenance='SYNTHETIC fixed undirected Ring300',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    a5=tuple(Assumption(name=name,source='demo_specification',confirmed=True,
        evidence=['SYNTHETIC scientific assumption for symbolic theorem demonstration only'])
        for name in ('full_vector_conditional_exchangeability','consistency',
                     'fixed_pretreatment_network','finite_conditional_first_moments'))
    def scenario(label,grouping,start,end,*,missing_a5=False,sample_a4=False,
                 missing_arm=False,own_zero=False):
        sig=declare_policy_signature(study,grouping=grouping)
        query=EffectQueryV18(kind='SPILLOVER',node_weights=(('n151',1),),
            reference_exposure=start,comparison_exposure=end,spillover_own_treatment=1)
        cells=(('n151',1,start),('n151',1,end))
        source=declare_observational_factorized_arm_population_v27p1(
            study,sig,source_id='SYNTHETIC-R3-300-'+grouping,
            provenance='Synthetic, symbolically declared p_obs product law and arm outcomes; NO DATA',
            treatment_one_probabilities=(('0' if own_zero else '1/3') for _ in nodes),
            covered_arms=cells[:-1] if missing_arm else cells,
            admission='ADMITTED',
            availability='FINITE_SAMPLE_ESTIMATE' if sample_a4 else 'SYMBOLIC_POPULATION_OPERATOR')
        result=identify_network_business_query(ObservationalEffectsInquiryV26(
            study,source,a5[:-1] if missing_a5 else a5,sig,(query,)))
        if result.status=='POINT':replay_verified_business_outcome(result)
        summary=result.summary()
        return dict(case=label,status=result.status,route=result.route,reason_code=result.reason_code,
            source_law=('ADMITTED conditional independent Bernoulli(0) observational law' if own_zero else 'ADMITTED conditional independent Bernoulli(1/3) observational law'),
            number_of_nodes=300,exposure=grouping,
            target='p_obs-standardized treated spillover contrast at node n151',
            support=(summary['identification']['results'][0]['arm_terms'] if result.status=='POINT' else None),
            full_summary=summary)
    cases=[
        scenario('E1 majority (both neighbors)', 'strict_majority_ties_low',0,1),
        scenario('E5 any treated neighbor','any_treated_neighbor',0,1),
        scenario('E4 exactly two treated neighbors','exact_treated_neighbor_count',0,2),
        scenario('A5 exchangeability missing','strict_majority_ties_low',0,1,missing_a5=True),
        scenario('A4 only finite-sample estimates','strict_majority_ties_low',0,1,sample_a4=True),
        scenario('A4 missing one requested arm mean','strict_majority_ties_low',0,1,missing_arm=True),
        scenario('No support for treated node','strict_majority_ties_low',0,1,own_zero=True),
    ]
    counts={status:sum(x['status']==status for x in cases)
            for status in ('POINT','NEEDS_INPUT','UNSUPPORTED')}
    data=dict(contract='CFM-ID-v2.7-Postrelease-P1-R3-FACTORIZED-A4',
        version='v2.7 post-release P1, NOT v2.8',
        description='Formal symbolic Identification only. Full-vector exchangeability and '
           'conditional product treatment law are synthetic scientific assumptions, not proved by data.',
        sample_size=None,estimated_effects=None,
        observational_law='p_obs(T|W=w) = product_i Bernoulli(T_i;1/3), except explicit zero-support case',
        node_count=300,case_counts=counts,cases=cases,
        warnings=['R3 fixed W only; no cross-W standardization',
                  'No observational generalized graphical propensity kernel',
                  'No real-world verification of p factorization or ignorability',
                  'This operator does not identify a fixed policy value',
                  'No Estimation/Policy numerical adapter'])
    return data


def page(data):
    raw=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    digest=sha256(raw.encode()).hexdigest()[:16]
    items=[]
    for c in data['cases']:
        status=c['status'];support='—'
        if c['support'] is not None:
            support=', '.join(f"{x['node_id']} T={x['own_treatment']} S={x['exposure_state']}: {x['population_support']}" for x in c['support'])
        items.append(f'<tr><td>{html.escape(c["case"])}</td><td class="{html.escape(status)}">{html.escape(status)}</td><td>{html.escape(c["reason_code"] or "—")}</td><td>{html.escape(support)}</td></tr>')
    return '''<!doctype html><html lang="zh"><meta charset="utf-8"><title>CFM-ID R3 A4 P1</title>
<style>body{font-family:system-ui,"Noto Sans CJK SC",sans-serif;margin:0 auto;max-width:1240px;padding:35px;color:#172b43;background:#f6f8fb}h1{font-size:27px}p{line-height:1.65}.lead{background:#fff;border:1px solid #dbe3f0;border-radius:12px;padding:20px}table{width:100%;border-collapse:collapse;background:white;box-shadow:0 4px 18px #172b430a}td,th{padding:15px;border-bottom:1px solid #e4eaf1;text-align:left;vertical-align:top;font-size:14px}th{background:#e9eff7}.POINT{color:#1b7b53;font-weight:700}.NEEDS_INPUT{color:#9f7222;font-weight:700}.UNSUPPORTED{color:#ad4550;font-weight:700}.caps{display:flex;gap:15px;flex-wrap:wrap;margin:22px 0}.caps span{background:white;padding:16px;border-radius:9px;min-width:155px;border:1px solid #dbe3f0}small{color:#53657e}</style>
<h1>R3 可扩展 A4：300 节点观测网络（合成识别展示）</h1>
<section class="lead"><b>v2.7 Post-release P1 — 非 v2.8</b><p>本次只扩展可认证的总体信息表达：假定观测 treatment 条件独立、具有精确节点 Bernoulli 概率，并具备 typed population arm 条件均值；另行接受完整向量观测交换性。无需枚举 2³⁰⁰ 个完整分配。</p><p><b>不是随机试验；不是 exposure sufficiency；不是销售额估计；不是可执行的固定政策价值。</b></p></section>
<div class="caps"><span>网络节点<br><b>300</b></span><span>POINT<br><b>''' +str(data['case_counts']['POINT'])+'''</b></span><span>NEEDS_INPUT<br><b>'''+str(data['case_counts']['NEEDS_INPUT'])+'''</b></span><span>UNSUPPORTED<br><b>'''+str(data['case_counts']['UNSUPPORTED'])+'''</b></span></div>
<table><tr><th>合成业务验收</th><th>系统状态</th><th>阻断原因</th><th>精确总体 arm 支持概率</th></tr>'''+''.join(items)+'''</table>
<p><small>来源：已正式执行的 R3 typed business API + theorem certificate replay。仅展示已声明总体信息的数学识别，真实世界因果假设未验证。</small></p>
<p><small>确定性数据摘要：'''+digest+'''</small></p></html>'''


def write(out_dir:Path):
    out_dir.mkdir(parents=True,exist_ok=True)
    data=run()
    json_path=out_dir/(BASE+'.json');html_path=out_dir/(BASE+'.html')
    json_path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    html_path.write_text(page(data),encoding='utf-8')
    return json_path,html_path,data


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',default='showcase_v27_r3_factorized')
    args=parser.parse_args()
    j,h,d=write(Path(args.output_dir))
    print('Wrote',j,h,'statuses:',d['case_counts'])


if __name__=='__main__':main()
