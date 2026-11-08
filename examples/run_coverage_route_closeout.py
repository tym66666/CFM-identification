"""Pre-v2.7, version-preserving v2.6 business/route audit of 32+5+11 cases.

Reruns all historical *fixtures* on the current v2.6 working tree and adds
specific B20/B24 delta witnesses.  Does NOT claim that unchanged historical
business prompts acquire a causal license just because an API was added.

python -B -m examples.run_coverage_route_closeout --output-dir showcase_v26_closeout
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import asdict
from fractions import Fraction
import html
import io
from itertools import product
import json
from pathlib import Path
import tempfile

from pfn_pipeline.identification_coverage import run_business_coverage_v22,_study,_assumptions,_full_source
from pfn_pipeline.identification_business import (
    FixedPolicyInquiryV21,ObservationalEffectsInquiryV26,
    identify_network_business_query,replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature,declare_signature_population_source,
    admit_mean_signature_sufficiency,
)
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.network_inquiry_shadow import (
    fixed_policy_target_from_context,declare_network_study,
)
from examples.run_observational_r3_and_signature import case as observational_policy_cases
from examples.run_observational_effects import main as observational_effect_cases
from predevelopment.two_stage_exact_oracle import acceptance_witnesses


BASE = Path(__file__).resolve().parents[1]


def b20_exact_count_same_offsupport_policy():
    """A new E4 theorem now exists; the old D2 star5 all-on policy still fails A6."""
    study=_study('d2')
    target=fixed_policy_target_from_context(study,(1,)*5,authority='TRUSTED_FIXTURE')
    sig=declare_policy_signature(study,grouping='exact_treated_neighbor_count')
    deg=study.network().degree_map()
    src=declare_signature_population_source(study,sig,source_id='b20-exact-population',
        operator='NODE_SIGNATURE_MEANS',provenance='symbolic synthetic outcome operator',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=study.node_order,
        signature_cells=tuple((n,1,deg[n]) for n in study.node_order))
    lic=admit_mean_signature_sufficiency(study,sig,
       covered_nodes=study.node_order,
       assumption=Assumption(name='mean_signature_sufficiency',source='demo_specification',
          status='ADMITTED',confirmed=True,
          evidence=['HYPOTHETICAL additional exact-count sufficiency, not an empirical fact']))
    query=FixedPolicyInquiryV21(study,target,_assumptions(),
              r1b_sources=(_full_source(study),),
              r2_signature=sig,r2_sufficiency=lic,r2_sources=(src,))
    out=identify_network_business_query(query)
    assert out.status!='POINT' and out.result is None
    assert any(reason=='ZERO_POLICY_SIGNATURE_SUPPORT' for _,reason in out.attempted_routes),out.attempted_routes
    return {
        'case_id':'B20',
        'old_v22_verdict':'NO_REGISTERED_THEOREM',
        'updated_theorem_applicable':'R2 with E4 exact-neighbor-count signature (new since v2.4)',
        'original_policy':'D2 star5 m=4, all five treated; q(all-on)=0',
        'hypothetical_new_a5':'Explicitly admitted exact-count mean sufficiency for this NEW witness only',
        'new_status':out.status,
        'new_reason':out.reason_code,
        'attempted_routes':[{'route':r,'reason':code} for r,code in out.attempted_routes],
        'hub_degree':deg['hub'],
        'hub_required_total_treated':deg['hub']+1,
        'experiment_treated_quota':4,
        'original_case_point_upgraded':False,
        'interpretation':'Theorem family/exposure code is now present, but hub exact-count support remains zero; no POINT.',
    }


def b24_new_observational_direct_requires_new_contract():
    """Alternative p-standardized Direct target works ONLY with added A4/A5.

    B24's original natural-language `direct effect` was not specific enough to
    certify equivalence with this redesigned p-standardized target. Hence the
    original B24 verdict is not silently upgraded.
    """
    st=declare_network_study(network_id='coverage-v22-observational',
      node_order=('0','1','2'),undirected_edges=(('0','1'),('0','2')),
      treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
      context_reference='W',observation_regime='observational',assignment_design=None,
      protocol_provenance='self-selected use of AI',network_provenance='fixed hypothetical graph',
      graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    source=declare_observational_population_v23(st,
       source_id='b24-synthetic-population-new-information',
       provenance='ADDITIONAL hypothetical observational population operator, not supplied in original B24',
       assignment_masses=[(z,Fraction(1,8)) for z in product((0,1),repeat=3)])
    accepted=tuple(Assumption(name=n,source='demo_specification',confirmed=True,
         status='ADMITTED', evidence=['EXTRA hypothetical assumption, not present in original B24'])
         for n in ('full_vector_conditional_exchangeability','consistency',
                   'fixed_pretreatment_network','finite_conditional_first_moments'))
    sig=declare_policy_signature(st,grouping='strict_majority_ties_low')
    direct=EffectQueryV18(kind='DIRECT',node_weights=(('0','1'),),
         reference_exposure=0,comparison_exposure=0)
    missing=identify_network_business_query(ObservationalEffectsInquiryV26(
        st,source,tuple(),sig,(direct,)))
    complete=identify_network_business_query(ObservationalEffectsInquiryV26(
        st,source,accepted,sig,(direct,)))
    assert missing.status!='POINT' and complete.status=='POINT'
    assert replay_verified_business_outcome(complete)
    return {
        'case_id':'B24','old_v22_verdict':'NO_REGISTERED_THEOREM',
        'new_registered_route':'R3_P_STANDARDIZED_EFFECTS',
        'original_case_target_ambiguity':'Direct may mean p-standardized or controlled-neighbor; not identical without specification',
        'missing_exchangeability_status':missing.status,
        'missing_exchangeability_reason':missing.reason_code,
        'separate_conditional_witness_status':complete.status,
        'separate_conditional_witness_route':complete.route,
        'separate_conditional_witness_target_fingerprint':complete.result.proofs[0].target_fingerprint,
        'separate_conditional_witness_arm_support':list(complete.result.proofs[0].arm_support),
        'original_case_point_upgraded':False,
        'interpretation':'A re-specified target with NEW symbolic A4 and accepted full-vector A5 is POINT. The original self-selection case lacks them.',
    }


def build_coverage_matrix():
    # FIRST regenerate the old exact fixture audit, not merely load a JSON.
    old=run_business_coverage_v22()
    archived=json.loads((BASE/'assets/business_coverage_fixtures'/'CFM_ID_Business_Coverage_32_Cards.json').read_text('utf8'))
    if old!=archived:
        raise AssertionError('v2.2 original 32-card fixture evidence drifted in v2.6')
    # SECOND rerun the v2.3 policy suite and map the original five scenarios.
    policy=observational_policy_cases()['observational_policy']
    v23=[('C33','supported_full','观测支持的完整固定政策'),
         ('C34','offsupport_with_mean_suff','离支持固定政策+已接受签名充分性'),
         ('C35','offsupport_without_mean_suff','离支持、未接受结构充分性'),
         ('C36','exchangeability_not_confirmed','未确认 full-vector exchangeability'),
         ('C37','only_finite_sample','只有有限样本而非总体算子')]
    # THIRD execute v2.6 query suite through official API, with replay.
    with tempfile.TemporaryDirectory(prefix='v26-route-audit-') as d, redirect_stdout(io.StringIO()):
        current=observational_effect_cases(Path(d))
    rows=[]
    for case in old['cards']:
        rows.append({
            'case_id':case['case_id'], 'business_question':case['business_question'],
            'introduced_in':'v2.2','evidence_scope':'REEXECUTED_ORIGINAL_V22_FIXTURE_IN_V26',
            'l0_target':case['target_class'],'l1_route':case['l1_route'],
            'l2_identification':case['l2_identification'],'l3_estimation':case['l3_estimation'],
            'a4':case['a4_required_information'],'a5':case['a5_required_assumptions'],
            'a6':case['a6_support_and_validity'],'reason':case['observed_reason'],
            'evidence_type':case['evidence_type'],
            'note':'Historical EXACT fixture kept unchanged. Later routes are evaluated separately in B20/B24 deltas.',
        })
    for cid,key,label in v23:
        item=policy[key]
        rows.append({'case_id':cid,'business_question':label,'introduced_in':'v2.3',
             'evidence_scope':'REEXECUTED_V23_R3_POLICY_IN_V26',
             'l0_target':'FIXED_POLICY_VALUE','l1_route':item['route'] or 'BLOCKED',
             'l2_identification':item['status'],'l3_estimation':'NO_NUMERIC_ESTIMATOR',
             'a4':'Exact observational full assignment population operator',
             'a5':'Admitted full-vector observational conditional exchangeability',
             'a6':'Full assignment or admitted mean-signature policy cell positivity',
             'reason':item['reason_code'],'evidence_type':'LIVE_R3_THEOREM_OR_REFUSAL',
             'note':'Synthetic declared observational population and assumed A5; no estimator.'})
    for item in current['cards']:
        rows.append({'case_id':item['id'],'business_question':item['label'],
           'introduced_in':'v2.6','evidence_scope':'REEXECUTED_V26_R3_EFFECT_IN_V26',
           'l0_target':'OBSERVATIONAL_P_STANDARDIZED_EFFECT' if item['id']!='C44' else 'FIXED_POLICY_VALUE',
           'l1_route':item['route'],'l2_identification':item['status'],
           'l3_estimation':'NO_NUMERIC_ESTIMATOR' if item['status']=='POINT' else 'NOT_APPLICABLE',
           'a4':'Exact p_obs(T|W) and assignment-conditioned node outcome means',
           'a5':'Full-vector exchangeability, consistency, stable pretreatment network',
           'a6':'Each arm or target assignment cell has positive population support',
           'reason':item['reason'],'evidence_type':'LIVE_R3_THEOREM_REPLAY_OR_REFUSAL',
           'note':item['explanation']})
    if len(rows)!=48 or len({r['case_id'] for r in rows})!=48:
        raise AssertionError('Exactly 32+5+11 DISTINCT versioned test case IDs expected')
    counts=Counter('POINT' if x['l2_identification'].startswith('POINT') else
                   ('NEEDS_INPUT' if x['l2_identification']=='NEEDS_INPUT' else
                    'BLOCKED_OR_TARGET_GAP') for x in rows)
    return {
        'baseline':'v2.6',
        'stage':'PRE_V2_7_P0_REVIEW_NO_TWO_STAGE_PRODUCTION_BACKEND',
        'case_total':len(rows),'counts':dict(counts),
        'counts_denominator':'Purpose-built synthetic test cases, NOT population or market business coverage',
        'reexecution':{'v22_exact_fixture_bytes_match':True,'v23_policy_cases':5,
                       'v26_effect_cases':11},
        'delta_audits':[b20_exact_count_same_offsupport_policy(),
                        b24_new_observational_direct_requires_new_contract()],
        'two_stage_research_oracle':acceptance_witnesses(),
        'warnings':[
          'The 32 v2.2 case statuses are preserved for EXACT ORIGINAL fixtures; not all cases have been reformulated under new route options.',
          'B20 changes from missing theorem to available E4/R2 theorem but zero policy-signature support; still not POINT.',
          'B24 has a new p-standardized R3 route only after additional target disambiguation, population A4 and admitted A5; original self-selected observational case remains unproved.',
          'UNSUPPORTED is not a proof of mathematical non-identifiability.',
          'POINT certifies a population functional under declared assumptions, not estimated business outcomes.',
          'Two-stage numbers are a mathematical design-law research oracle, NOT D6, not R1a/R1b/R2 registered, not v2.7.',
          'The v2.2 B04 ER300 component remains an archived v2.1 result; this audit reruns only a toy batch for that card.',
        ],
        'cards':rows,
    }


def dashboard(data):
    # Static local, no CDN/assets. All untrusted labels are HTML-escaped.
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    payload=payload.replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CFM-ID v2.6 · Pre-v2.7 Correctness Closeout</title>
<style>
:root{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;background:#f3f6fb;color:#172c47}
*{box-sizing:border-box}body{margin:0}header{background:#162c4b;color:#fff;padding:36px max(20px,calc((100% - 1130px)/2))}
main{max-width:1170px;padding:18px 20px 65px;margin:auto}h1{font-size:30px;margin:5px 0}h2{font-size:19px}
small,.muted{color:#677890}.lead{color:#bbcee8;max-width:830px;line-height:1.6}
section{background:white;border:1px solid #dce4ee;border-radius:14px;padding:23px;margin:17px 0}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.kpi{padding:14px;border-radius:10px;background:#f1f5fb}
.kpi strong{font-size:27px;display:block}.kpi small{font-size:12px}.toolbar{display:flex;gap:8px;flex-wrap:wrap}
input,select{padding:9px 12px;border:1px solid #cdd8e6;border-radius:8px;font:inherit}input{flex:1;min-width:200px}
.row{display:grid;grid-template-columns:65px 1fr 115px 95px;gap:10px;align-items:center;border-bottom:1px solid #e6edf5;padding:12px 5px;font-size:13px}
.row summary{cursor:pointer}.card{border-bottom:1px solid #e5ebf2;padding:12px 2px;font-size:13px}.card summary{cursor:pointer;display:flex;gap:12px;align-items:center}
.card .id{width:46px;font-weight:bold;color:#48698a}.card .name{flex:1}.pill{display:inline-block;border-radius:18px;font-size:11px;font-weight:700;padding:5px 9px;background:#edf1f7;color:#345069}
.point{background:#dff5ea;color:#09755a}.warning{background:#fff0d8;color:#956418}.detail{color:#465f7b;padding:8px 0 4px 60px;line-height:1.65;overflow-wrap:anywhere}
.note{border-left:4px solid #b77b3e;background:#fff9ed;padding:12px 15px;margin:12px 0;font-size:13px;line-height:1.6}
pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:11px;background:#f5f7fb;border-radius:8px;font-size:12px}
@media(max-width:750px){.kpis{grid-template-columns:repeat(2,1fr)}header{padding:24px 16px}main{padding:12px}.detail{padding-left:8px}}
</style></head><body><header><small style="color:#d3e6ff">CAUSAL-IDFM · IDENTIFICATION · v2.6</small>
<h1>业务覆盖与路线正确性审计</h1>
<div class="lead">Pre-v2.7 P0 工作副本。48 张版本累计测试卡，逐项区分旧案例证据、新定理是否可用、补足条件后的新案例；不把新增 Route 或支持概率自动当成真实因果推断结论。</div>
</header><main><section><div class="kpis" id="stats"></div><p class="note"><b>口径：</b>是 32+5+11 个刻意构造的合成验收案例，不是实际市场问题覆盖率。B04 的 ER300 1200 arms 为旧发布记录；本轮重新执行其小图验证，没有声称重跑 ER300。</p></section>
<section><h2>01 / 48 张问题卡 · 维持原情境判定</h2>
<div class="toolbar"><input id="search" placeholder="搜索编号 / 业务问题 / 线路 / 失败原因" aria-label="搜索"/>
<select id="stage"><option value="all">全部版本</option><option value="v2.2">v2.2</option><option value="v2.3">v2.3</option><option value="v2.6">v2.6</option></select>
<select id="status"><option value="all">全部状态</option><option value="point">POINT</option><option value="blocked">阻断/未支持/待澄清</option></select></div><div id="cards"></div><p class="muted" id="visible"></p></section>
<section><h2>02 / 关键状态迁移（不是无条件 POINT）</h2><div id="deltas"></div></section>
<section><h2>03 / Two-stage 预研算术，不是生产识别</h2><pre id="oracle"></pre><p class="note">这里只用有理数完整枚举核对两阶段完整分配概率与条件邻居处理数分布。没有注册新的 AssignmentSpec，也没有给 R1a/R1b/R2 添加 D6，更没有形成 v2.7 发布。</p></section>
<section><h2>04 / 研究与科学边界</h2><div id="warnings"></div></section></main>
<script id="data" type="application/json">''' + payload + '''</script><script>
const d=JSON.parse(document.getElementById('data').textContent);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=id=>document.getElementById(id);
$('stats').innerHTML=[['48','累计测试卡'],[d.counts.POINT||0,'历史情境 POINT (含 B04 历史 ER300)'],[d.delta_audits.length,'重点条件迁移审计'],['0','Two-stage 生产注册']].map(([v,k])=>`<div class="kpi"><strong>${v}</strong><small>${esc(k)}</small></div>`).join('');
function render(){let q=$('search').value.toLowerCase(),st=$('stage').value,sta=$('status').value;let cases=d.cards.filter(c=>{
 let ok=[c.case_id,c.business_question,c.l1_route,c.reason,c.l0_target].join(' ').toLowerCase().includes(q);
 return ok&&(st==='all'||c.introduced_in===st)&&(sta==='all'||(sta==='point'?c.l2_identification.startsWith('POINT'):!c.l2_identification.startsWith('POINT')));
}); $('cards').innerHTML=cases.map(c=>`<details class="card"><summary><span class="id">${esc(c.case_id)}</span><span class="name">${esc(c.business_question)}</span><span class="muted">${esc(c.introduced_in)}</span><span class="pill ${c.l2_identification.startsWith('POINT')?'point':'warning'}">${esc(c.l2_identification)}</span></summary><div class="detail"><p><b>A1：</b>${esc(c.l0_target)}<br><b>Route：</b>${esc(c.l1_route)}<br><b>A4：</b>${esc(c.a4)}<br><b>A5：</b>${esc(c.a5)}<br><b>A6：</b>${esc(c.a6)}<br><b>阻断原因：</b>${esc(c.reason||'无')}<br><b>证据：</b>${esc(c.evidence_scope)} — ${esc(c.evidence_type)}<br><b>L3：</b>${esc(c.l3_estimation)}<br><b>说明：</b>${esc(c.note)}</p></div></details>`).join('');$('visible').textContent=cases.length+' / '+d.cards.length+' 张卡';}
['search','stage','status'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',render));render();
$('deltas').innerHTML=d.delta_audits.map(x=>`<article class="note"><b>${esc(x.case_id)}</b><p>${esc(x.interpretation)}</p><p>原始 v2.2：${esc(x.old_v22_verdict)} · 原案例直接升级 POINT：${x.original_case_point_upgraded?'是':'否'}</p><details><summary>查看运行证据</summary><pre>${esc(JSON.stringify(x,null,2))}</pre></details></article>`).join('');
$('oracle').textContent=JSON.stringify(d.two_stage_research_oracle,null,2);
$('warnings').innerHTML=d.warnings.map(x=>`<p class="muted">• ${esc(x)}</p>`).join('');
</script></body></html>'''


def main(output_dir: Path):
    output_dir.mkdir(parents=True,exist_ok=True)
    data=build_coverage_matrix()
    stem='CFM_ID_v2_6_Pre_v2_7_P0_48_Case_Correctness_Closeout'
    json_path=output_dir/(stem+'.json')
    html_path=output_dir/(stem+'.html')
    json_path.write_text(json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n',encoding='utf8')
    html_path.write_text(dashboard(data),encoding='utf8')
    print(json.dumps({'stage':data['stage'],'cases':data['case_total'],
              'counts':data['counts'],'json':str(json_path),'html':str(html_path)},ensure_ascii=False))
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,default=Path('showcase_v26_closeout'))
    args=parser.parse_args()
    main(args.output_dir)
