"""Reproducible D6 showcase: all POINT rows come from real theorem/replay APIs.

No finite-sample outcomes, business revenue estimates or assumption discovery.
    python -B -m examples.run_two_stage --output-dir showcase_v27
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from html import escape
import json
from pathlib import Path

from pfn_pipeline import make_two_stage_quota_arm_task
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, TwoStageQuotaMixtureDesignV27, Assumption,
)
from pfn_pipeline.identification_business import (
    ArmInquiryV21, FixedPolicyInquiryV21, identify_network_business_query,
    replay_verified_business_outcome,
)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context,
    declare_network_a4_source,
)
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source,
)
from pfn_pipeline._internal.identification.randomized_arm_family.two_stage_a5 import D6_EXCLUSION

NODES=tuple('abcdef')
GROUPS=(('a','b'),('c','d'),('e','f'))
EDGES=(('a','c'),('a','e'),('b','d'),('b','f'),('c','e'),('d','f'))
PROFILES=((1,1,1),(2,1,0))
PROFILE_WEIGHTS=('1/2','1/2')
ASSUMPTIONS=('known_assignment_law','full_vector_randomization','consistency',
             'fixed_pretreatment_network','finite_conditional_first_moments')


def study_of(net,design):
    return declare_network_study(network_id=net.network_id,node_order=tuple(net.node_ids),
        undirected_edges=tuple(tuple(e) for e in net.undirected_edges),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W:synthetic',observation_regime='experimental',
        assignment_design=design.model_dump(mode='json'),
        protocol_provenance='known synthetic two-stage assignment protocol',
        network_provenance='declared fixed pretreatment network',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def scientific_assumptions(*,profile_admitted):
    records=tuple(Assumption(name=name,source='demo_specification',confirmed=True,
        evidence=['controlled hypothetical protocol']) for name in ASSUMPTIONS)
    exclusion=Assumption(name=D6_EXCLUSION,source='human_confirmation',
        confirmed=profile_admitted,
        evidence=['hypothetically accepted: stage-one profile has no effect except via final T'])
    return records+(exclusion,)


def arm(net,design,*,node,own,s,exposure='any_treated_neighbor',profile_admitted=True):
    t=make_two_stage_quota_arm_task(net,groups=design.groups,
        quota_profiles=design.quota_profiles,
        profile_probabilities=design.profile_probabilities,
        node_id=node,own_treatment_value=own,exposure_value=s,
        source='synthetic known two-stage assignment protocol',
        evidence='declared symbolic population arm observable, not empirical sample',
        exposure_definition=exposure,admitted=True,
        profile_exclusion_admitted=profile_admitted,
        query_authority='TRUSTED_FIXTURE',synthetic=True)
    return identify_network_business_query(ArmInquiryV21(t))


def as_case(index,title,out,*,size,exposure=None,policy=None,notes=''):
    if out.status=='POINT':
        assert replay_verified_business_outcome(out)
    details=out.summary().get('identification') or {}
    proof=details.get('certificate_sha256') or details.get('certificate') or {}
    support=details.get('assignment_probability') or details.get('policy_assignment_probability')
    if isinstance(proof,dict):
        support=support or proof.get('joint_arm_support_probability')
    if out.route == 'R2_MEAN_SIGNATURE':
        classes=details.get('node_classes',())
        minimum=min((Fraction(x['joint_support']) for x in classes),default=Fraction(0))
        support=f"q(z)={details['full_assignment_probability']}; min signature support={minimum}"
    return dict(id=index, title=title, query_type=out.query_type, route=out.route,
        status=out.status, reason=out.reason_code, size=size, exposure=exposure,
        policy=policy, exact_support=support, theorem_verified=out.status=='POINT',
        assumptions='Reviewed hypothetical design and profile-exclusion' if out.status=='POINT' else 'Insufficient for this query',
        information='Declared SYMBOLIC_POPULATION_OPERATOR; not sales estimates' if out.status=='POINT' else 'See refusal reason',
        notes=notes, proof_excerpt=str(proof)[:220])


def build_data():
    net=NetworkExposureSpec(network_id='v27-two-stage-cross-group-six',
        node_ids=list(NODES),undirected_edges=list(EDGES))
    design=TwoStageQuotaMixtureDesignV27(groups=GROUPS,
        quota_profiles=PROFILES,profile_probabilities=PROFILE_WEIGHTS)
    st=study_of(net,design)
    source=declare_network_a4_source(st,source_id='v27-full-law',operator='NODE_FULL_LAW',
        provenance='synthetic reviewed full population operator',admission='ADMITTED',
        availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=NODES)
    a5=scientific_assumptions(profile_admitted=True)
    supported=fixed_policy_target_from_context(st,(1,0,1,0,1,0),authority='TRUSTED_FIXTURE')
    off=fixed_policy_target_from_context(st,(1,)*6,authority='TRUSTED_FIXTURE')
    signature=declare_policy_signature(st,grouping='any_treated_neighbor')
    sufficient=admit_mean_signature_sufficiency(st,signature,
        assumption=Assumption(name='mean_signature_sufficiency',
            source='human_confirmation',confirmed=True,
            evidence=['hypothetical mean restriction for every relevant full treatment vector']),
        covered_nodes=NODES)
    sig_source=declare_signature_population_source(st,signature,
        source_id='v27-signature-full-law',operator='NODE_FULL_LAW',outcome_nodes=NODES,
        provenance='reviewed hypothetical signature population law',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR')
    cases=[]
    def add(title,out,**kwargs):
        cases.append(as_case(f'D6-{len(cases)+1:02}',title,out,size=6,**kwargs))
    for exp,s in (('strict_majority',1),('exact_treated_neighbor_count',1),
                  ('any_treated_neighbor',1)):
        add('设计标准化节点 Arm · '+exp,
            arm(net,design,node='a',own=1,s=s,exposure=exp),exposure=exp,
            notes='同一处理前网络；按边际混合分配律 q(T|W) 定义的 Arm')
    add('原设计中完整分配正支持的固定政策',
        identify_network_business_query(FixedPolicyInquiryV21(st,supported,a5,
                                          r1b_sources=(source,))),policy='(1,0,1,0,1,0)',
        notes='R1b 要求完整 assignment 支持与对应 A4 信息')
    add('全员处理：完整分配零支持，但均值签名足够',
        identify_network_business_query(FixedPolicyInquiryV21(st,off,a5,
            r1b_sources=(source,),r2_signature=signature,
            r2_sufficiency=sufficient,r2_sources=(sig_source,))),
        policy='(1,1,1,1,1,1)',exposure='any_treated_neighbor',
        notes='R2 只有在人工接受 mean-signature sufficiency 后适用')
    add('拒绝：已知设计，但没有接受第一阶段排除假设',
        identify_network_business_query(FixedPolicyInquiryV21(st,supported,
            scientific_assumptions(profile_admitted=False),r1b_sources=(source,))),
        policy='(1,0,1,0,1,0)',notes='必须拒绝将 Y_i(T,U) 不经许可写作 Y_i(T)')
    add('拒绝：全员政策没有原设计的完整分配支持',
        identify_network_business_query(FixedPolicyInquiryV21(st,off,a5,
                                          r1b_sources=(source,))),
        policy='(1,1,1,1,1,1)',notes='不接受额外 R2 充分性时，不能将无支持政策冒充 POINT')
    add('拒绝：没有第一阶段排除假设的 Arm',
        arm(net,design,node='a',own=1,s=1,profile_admitted=False),
        exposure='any_treated_neighbor', notes='A5 未接受与结构性零支持是不同的问题')

    ring_nodes=tuple(f'r{i:03}' for i in range(300))
    ring=NetworkExposureSpec(network_id='v27-nonER-ring300',node_ids=list(ring_nodes),
        undirected_edges=[(ring_nodes[i],ring_nodes[(i+1)%300]) for i in range(300)])
    ring_groups=tuple(tuple(ring_nodes[k*100:(k+1)*100]) for k in range(3))
    ring_design=TwoStageQuotaMixtureDesignV27(groups=ring_groups,
        quota_profiles=((50,50,50),(80,40,30)),profile_probabilities=('1/2','1/2'))
    for exp,s in (('strict_majority',1),('exact_treated_neighbor_count',1),
                  ('any_treated_neighbor',1)):
        out=arm(ring,ring_design,node='r000',own=1,s=s,exposure=exp)
        cases.append(as_case(f'D6-{len(cases)+1:02}',
                'Ring300 非 ER 网络 · '+exp,out,size=300,exposure=exp,
                notes='仅一个指定 Arm 证书；不等于 Ring300 全部节点与 Arm 均已 POINT'))
    counts={status:sum(c['status']==status for c in cases)
            for status in ('POINT','NEEDS_INPUT','UNSUPPORTED')}
    return dict(title='Causal-IDFM v2.7 · D6 Two-stage Quota Mixture',
        version='2.7', network='Known fixed pretreatment undirected network',
        design='First-stage exact profile lottery; independent uniform fixed quotas by group',
        profile_weights=list(PROFILE_WEIGHTS),profiles=[list(q) for q in PROFILES],
        group_sizes=[len(g) for g in GROUPS],
        point_scope='Formal population identification under explicitly admitted A4/A5/A6; no finite-sample values',
        node_count_ring300=300, case_count=len(cases),counts=counts,cases=cases)


def render_html(data):
    payload=json.dumps(data,ensure_ascii=False,sort_keys=True).replace('<','\\u003c')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Causal-IDFM v2.7 · Two-stage Identification</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#172536;background:#f5f7fa}
*{box-sizing:border-box}body{margin:0}header{background:#162638;color:white;padding:48px max(24px,calc((100vw - 1120px)/2)) 36px}h1{font-size:clamp(25px,4vw,38px);margin:10px 0}h2{font-size:20px}header p{max-width:780px;color:#cbd5e1;line-height:1.7}.eyebrow{font-size:12px;letter-spacing:.13em;font-weight:700;color:#78b8fd}
main{max-width:1120px;margin:0 auto;padding:26px 22px 64px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:-55px;position:relative}
.stat,.card,.panel{background:white;border:1px solid #e0e6ee;border-radius:14px;box-shadow:0 6px 18px #2130450a}.stat{padding:21px}.stat strong{display:block;font-size:29px}.stat span,.meta,.caption{color:#65758b;font-size:12px}
section{margin-top:30px}.panel{padding:22px;line-height:1.7}.toolbar{display:flex;flex-wrap:wrap;gap:8px;margin:17px 0}.toolbar button{background:white;border:1px solid #cbd5e1;border-radius:7px;padding:9px 13px;cursor:pointer;color:#26394f}.toolbar button.active{background:#173e71;border-color:#173e71;color:white}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.card{padding:20px;min-height:195px}.card h3{margin:7px 0;font-size:16px;line-height:1.45}.pill{display:inline-block;padding:3px 9px;border-radius:100px;font-size:11px;font-weight:700}.POINT{color:#0c6b47;background:#e0f7ed}.NEEDS_INPUT{color:#885700;background:#fff1d2}.UNSUPPORTED{color:#974237;background:#fbe8e4}
.row{display:flex;justify-content:space-between;align-items:center;gap:10px}.mono{font-family:ui-monospace,monospace;font-size:12px;color:#2a4872;overflow-wrap:anywhere}.hint{font-size:13px;line-height:1.6;color:#43566b}.small{font-size:12px;color:#718198}.note{padding:12px 15px;border-left:3px solid #678fbe;background:#eef4fa}.empty{color:#64748b;padding:35px}
@media(max-width:750px){.grid{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}header{padding:36px 22px 82px}}
</style></head><body><header><div class="eyebrow">CFM-ID / VERIFIED POPULATION IDENTIFICATION</div>
<h1>v2.7 · Two-stage Randomization</h1><p>第一阶段按已知概率选择各组处理配额；第二阶段在每组内均匀随机处理。复用 R1a / R1b / R2 识别理论，并由独立精确计数核验支持。</p></header>
<main><div class="stats" id="stats"></div><section class="panel"><h2>识别边界</h2>
<p><b>D6 是新的 Assignment Design，不是新的 Identification Family。</b>两阶段配额分配律和完整网络先于处理固定。必须额外科学接受：第一阶段配额公告本身不会在最终处理向量之外直接影响潜在结果。</p>
<p class="note">所有 POINT 是符号总体算子的数学识别状态，并不是销售收益估计。R2 的 mean-signature sufficiency 必须另行确认。Ring300 仅核验三个指定 Arm。</p></section>
<section><h2>正式业务查询与安全拒绝</h2><div class="toolbar" id="filters"></div><div class="grid" id="cards"></div></section>
<section class="panel"><h2>尚未实现的能力</h2><p>尚无通用 stochastic policy kernel、stage-one profile 直接结果效应 Y(T,U)、任意两阶段 sequential/adaptive 设计、任意观测网络规模 R3、Network PARTIAL、DAG/IV、动态网络或全路线 PFN Estimation adapter。</p></section>
<p class="caption">离线可交互看板 · 数据由 examples.run_two_stage 调用正式 theorem/verifier/replay 实际生成 · 无效果估计值</p></main>
<script id="report" type="application/json">''' + payload + '''</script>
<script>
const data=JSON.parse(document.getElementById('report').textContent); let active='ALL';
const h=(s)=>String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const stats=document.getElementById('stats');
stats.innerHTML=[[data.case_count,'实际执行案例'],[data.counts.POINT,'POINT'],[data.counts.NEEDS_INPUT,'NEEDS_INPUT'],[data.counts.UNSUPPORTED,'UNSUPPORTED']].map(([v,t])=>`<div class="stat"><strong>${v}</strong><span>${t}</span></div>`).join('');
const filters=['ALL','POINT','NEEDS_INPUT','UNSUPPORTED'];
function draw(){document.getElementById('filters').innerHTML=filters.map(x=>`<button data-status="${x}" class="${x===active?'active':''}">${x==='ALL'?'全部案例':x}</button>`).join('');
  document.querySelectorAll('[data-status]').forEach(b=>b.addEventListener('click',()=>{active=b.dataset.status;draw()}));
  let list=data.cases.filter(c=>active==='ALL'||c.status===active);
  document.getElementById('cards').innerHTML=list.map(c=>`<article class="card"><div class="row"><span class="meta">${h(c.id)} · ${c.size} 节点</span><span class="pill ${h(c.status)}">${h(c.status)}</span></div>
  <h3>${h(c.title)}</h3><div class="mono">${h(c.route||c.reason)}</div><p class="hint">${h(c.notes)}</p><div class="small">${c.exact_support?'精确支持概率：'+h(c.exact_support):'未认证 POINT：'+h(c.reason||'')}</div></article>`).join('')||'<div class="empty">没有匹配项</div>';
}draw();
</script></body></html>'''


def run(output_dir: Path):
    output_dir.mkdir(parents=True,exist_ok=True)
    data=build_data()
    jsonpath=output_dir/'CFM_ID_v2_7_Two_Stage_Identification.json'
    htmlpath=output_dir/'CFM_ID_v2_7_Two_Stage_Identification.html'
    jsonpath.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    htmlpath.write_text(render_html(data),encoding='utf-8')
    print(json.dumps(dict(case_count=data['case_count'],counts=data['counts'],
             json=str(jsonpath),html=str(htmlpath)),ensure_ascii=False))
    return data


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,
               default=Path('showcase_v27'))
    args=parser.parse_args();run(args.output_dir)

if __name__=='__main__':main()
