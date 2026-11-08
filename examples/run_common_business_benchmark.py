"""Six common network business settings, *synthetic* formal-backed theorem checks.

No LLM inference or actual scientific approval. Contract wording and population
operators are hypothetical research fixtures. Each outcome comes from the formal
Core and independent replay; status is NEVER copied from expected_status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.identification import (
    make_heterogeneous_bernoulli_arm_task, make_complete_randomization_arm_task,
    make_cluster_bernoulli_arm_task, make_multi_group_quota_arm_task,
    make_two_stage_quota_arm_task,
)
from pfn_pipeline.identification_business import (
    ArmInquiryV21, ObservationalNodewiseAdjustedEffectsInquiryV28,
    identify_network_business_query, replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import EffectQueryV18
from tests.test_r3_nodewise_correlated_a4 import mixture_items

STEM = 'CFM_ID_v293_Six_Common_Business_Theorem_Benchmark'
NODES = ('a','b','c','d','e','f')
EDGES = (('a','b'),('b','c'),('c','d'),('d','e'),('e','f'),('f','a'))
GROUPS = (('a','b'),('c','d'),('e','f'))

BUSINESSES = (
    ('S1','在线账号独立 A/B 实验','广告／软件用户','D1','E5','R1a',
     '一名用户获得新推荐功能、且至少一位关联用户获得该功能时的设计标准化平均结果'),
    ('S2','固定总名额试用实验','企业 AI 灰度','D2','E4','R1a',
     '只允许三名员工试用 AI，员工 a 获得试用且恰好两名同事试用时的平均结果'),
    ('S3','门店／班级整簇随机','门店和班级','D4','E5','R1a',
     '整个团队随机启用新工具，员工 a 使用且有同伴使用时的设计标准化平均结果'),
    ('S4','多部门固定配额','跨部门 AI 试用','D5','E4','R1a',
     '三个部门分别固定一个试用名额，员工 a 试用且一名同事试用时的平均结果'),
    ('S5','两阶段随机饱和度','学校／社区实验','D6','E5','R1a',
     '先抽各组试用比例，再组内抽人；员工 a 自己试用且至少一个邻居试用的平均结果'),
    ('S6','员工自选择 AI 使用','非随机企业协作网络','OBS','E5','R3',
     '员工自愿使用 AI，并基于本人及邻居的处理前协变量调整同伴 AI 溢出效应'),
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',',':'))


def _digest(value):
    return hashlib.sha256(_canonical(value).encode('utf8')).hexdigest()


def _network(scenario):
    # D2's star deliberately has a high-degree center. Target count=3 is a
    # mathematically VALID exposure state but impossible with only 3 treated.
    edges=(tuple(('a',n) for n in NODES if n!='a')
           if scenario=='S2' else EDGES)
    return NetworkExposureSpec(network_id='v293-synthetic-'+('star6' if scenario=='S2' else 'ring6'),
        node_ids=list(NODES),undirected_edges=list(edges))


def _make_arm(scenario,variant):
    common=dict(network=_network(scenario),node_id='a',own_treatment_value=1,
        exposure_value=1,exposure_definition='any_treated_neighbor',
        source='HYPOTHETICAL_TYPED_POPULATION_OPERATOR_NOT_SAMPLE',
        evidence='Declared synthetic experimental protocol; no measured revenue',
        admitted=variant!='a4_missing',synthetic=True,query_authority='TRUSTED_FIXTURE')
    if scenario=='S1':
        if variant=='point_e4':
            common.update(exposure_definition='exact_treated_neighbor_count',exposure_value=1)
        return make_heterogeneous_bernoulli_arm_task(
            **common,propensities={n:'1/2' for n in NODES})
    if scenario=='S2':
        return make_complete_randomization_arm_task(
            **{**common,'exposure_definition':'exact_treated_neighbor_count',
               'exposure_value':3 if variant=='zero_support' else 2},m=3)
    if scenario=='S3':
        return make_cluster_bernoulli_arm_task(
            **{**common,'own_treatment_value':1,
               'exposure_value':0 if variant=='zero_support' else 1},
            clusters=GROUPS,cluster_probabilities=('1/2',)*3)
    if scenario=='S4':
        return make_multi_group_quota_arm_task(
            **{**common,'exposure_definition':'exact_treated_neighbor_count',
               'exposure_value':2 if variant=='zero_support' else 1},
            groups=GROUPS,treated_quotas=(1,1,1))
    if scenario=='S5':
        if variant=='zero_support':
            common.update(exposure_definition='exact_treated_neighbor_count',exposure_value=2)
        return make_two_stage_quota_arm_task(
            **common,groups=GROUPS,quota_profiles=((1,1,1),(2,1,0)),
            profile_probabilities=('1/2','1/2'),
            profile_exclusion_admitted=variant!='a5_missing')
    raise ValueError('Unknown experimental scenario')


def _build_inquiry(scenario,variant):
    if scenario!='S6':
        return ArmInquiryV21(_make_arm(scenario,variant))
    query=EffectQueryV18(kind='SPILLOVER',node_weights=(('n2',1),),
         reference_exposure=0,comparison_exposure=1)
    st,src,sig,assumptions,lic,requests=mixture_items(
        6,'any_treated_neighbor',requests=(query,),
        proposed='exchangeability' if variant=='a5_missing' else None,
        sample=variant=='a4_sample_only')
    return ObservationalNodewiseAdjustedEffectsInquiryV28(
        st,src,assumptions,sig,lic,requests)


# Curated *expected* outcomes, specified independently of Core execution.
# A successful synthetic fixture never establishes real-world validity.
VARIANTS = (
    ('S1','point','POINT','eligible randomized exposure arm'),
    ('S1','a4_missing','NEEDS_INPUT','unadmitted population information'),
    ('S1','point_e4','POINT','same D1 design but a DISTINCT E4 exact-count arm target'),
    ('S2','point','POINT','fixed-quota exposure supported'),
    ('S2','zero_support','UNSUPPORTED','with m=3, a treated hub cannot have 3 treated neighbors'),
    ('S2','a4_missing','NEEDS_INPUT','A4 not admitted'),
    ('S3','point','POINT','cluster randomization: treated with treated co-cluster peer'),
    ('S3','zero_support','UNSUPPORTED','a treated node always has treated co-cluster peer'),
    ('S3','a4_missing','NEEDS_INPUT','A4 not admitted'),
    ('S4','point','POINT','3 groups, each 1 treated; cross-group peer possible'),
    ('S4','zero_support','UNSUPPORTED','a has own treatment and no spare treatment for peer b'),
    ('S4','a4_missing','NEEDS_INPUT','A4 not admitted'),
    ('S5','point','POINT','D6 quota-profile mixture, exclusion accepted'),
    ('S5','a5_missing','NEEDS_INPUT','stage-one direct effect not excluded'),
    ('S5','zero_support','UNSUPPORTED','under all profiles two treated neighbors impossible'),
    ('S6','point','POINT','hypothetical nodewise exchangeability and mixture A4'),
    ('S6','a5_missing','NEEDS_INPUT','exchangeability cannot be inferred from propensity'),
    ('S6','a4_sample_only','NEEDS_INPUT','sample statistics are not population operator'),
)


def generate():
    groups={row[0]:row for row in BUSINESSES}
    cases=[]
    for scenario,variant,expected,explanation in VARIANTS:
        sid,title,area,design,exposure,route,question=groups[scenario]
        if scenario=='S1' and variant=='point_e4':
            exposure='E4'
            question='在线独立 A/B 下，用户 a 使用新功能且恰有一名关联用户使用时的设计标准化平均结果'
        if scenario=='S2' and variant=='zero_support':
            question='固定三名员工试用 AI 时，星型中心 a 自己试用且五位邻居中恰有三位试用的均值是否可识别？'
        inquiry=_build_inquiry(scenario,'point' if variant=='point_e4' else variant)
        outcome=identify_network_business_query(inquiry)
        status=outcome.status
        proof_ok=replay_verified_business_outcome(outcome) if status=='POINT' else False
        if status=='POINT' and not proof_ok:
            raise AssertionError(f'Independent replay failed for {scenario}/{variant}')
        target={'business_scenario':scenario,'intent':question,'design':design,
                'exposure':exposure,'variant':variant,
                'target_kind':'R3_adjusted_spillover' if scenario=='S6' else 'q_standardized_arm',
                'review_type':'RESEARCH_SYNTHETIC_COORDINATE_CONTRACT_NOT_EXTERNAL_APPROVAL'}
        detail=outcome.summary().get('identification') or {}
        certificate=detail.get('certificate') if isinstance(detail,dict) else None
        if status=='POINT' and not detail:
            raise AssertionError('POINT without typed identification result')
        cases.append(dict(id=f'{scenario}-{variant}',scenario_id=scenario,scenario=title,
            business_area=area,question=question,design=design,exposure=exposure,
            theorem_principle=route,variant=variant,expected_status=expected,
            actual_status=status,passed=status==expected and (status!='POINT' or proof_ok),
            reason=outcome.reason_code,route=outcome.route,
            has_verified_core_result=bool(proof_ok),
            target_contract_digest=_digest(target),
            evidence_role='HYPOTHETICAL_SYNTHETIC_A4_A5_NOT_REAL_SCIENCE',
            intended_case_interpretation=explanation,
            identification_excerpt=(str(detail.get('identified_functional') or detail.get('formula') or '')[:400] if isinstance(detail,dict) else ''),
            certificate_present=bool(certificate) or bool(proof_ok),
            numeric_effect_estimate=None))
    count=Counter(x['actual_status'] for x in cases)
    return dict(schema_version='CFM-ID-v293-six-business-formal-backed-synthetic',
        source_baseline='v2.9.2 unchanged mathematical Core',
        track='FORMAL_BACKED_COMMON_BUSINESS_SYNTHETIC',
        approvals='HYPOTHETICAL_FIXED_FIXTURES_NOT_REAL_INDEPENDENT_REVIEW',
        raw_language_evaluation='NOT_PERFORMED',
        numeric_estimation_performed=False,
        actual_representative_market_share='NOT_MEASURED',
        note='All actual statuses are from Core. Every POINT has independent replay. Six hand-curated scenarios cannot establish population business coverage.',
        scenario_count=len(BUSINESSES),case_count=len(cases),
        pass_count=sum(x['passed'] for x in cases),status_counts=dict(sorted(count.items())),
        scenarios=[dict(id=i,title=t,area=a,design=d,exposure=e,route=r,question=q)
                   for i,t,a,d,e,r,q in BUSINESSES],cases=cases)


def render_html(data):
    payload=json.dumps(data,ensure_ascii=False,sort_keys=True).replace('<','\\u003c')
    return '''<!doctype html><html lang="zh"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Causal-IDFM · 六类常用业务 Formal-backed 验收</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f8fc;color:#192b42;font:15px/1.65 system-ui,"Noto Sans SC",sans-serif}
main{max-width:1160px;margin:auto;padding:28px 18px 70px}header{background:#16334b;color:#fff;border-radius:18px;padding:30px}header p{color:#bfd5e4}
h1{font-size:28px;margin:0}h2{font-size:20px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin:20px 0}
.metric,.panel{background:#fff;border:1px solid #dce5ef;border-radius:13px;padding:18px}.metric strong{font-size:29px;display:block}.metric small{color:#677a8f}
.panel{margin-top:18px}.warn{padding:12px 16px;background:#fff5e2;border-left:4px solid #bd8b38;border-radius:5px}
.controls{display:flex;gap:10px;margin:12px 0;flex-wrap:wrap}input,select{border:1px solid #c8d4de;padding:10px;border-radius:8px;font:inherit;max-width:100%}
input{flex:1;min-width:220px}.item{margin:10px 0;border:1px solid #dce5ef;border-radius:9px;padding:12px 15px}
summary{cursor:pointer;display:flex;justify-content:space-between;gap:12px}.tag{font-size:12px;font-weight:700;padding:2px 9px;border-radius:16px;background:#edf1f5}
.POINT{background:#dff5e8;color:#176a49}.NEEDS_INPUT{background:#ffefd0;color:#805c1b}.UNSUPPORTED{background:#ffe4e6;color:#a0464a}
pre{white-space:pre-wrap;word-break:break-word;background:#f5f7fb;border-radius:8px;padding:10px;font-size:12px}
@media(max-width:700px){h1{font-size:22px}header{padding:22px}}
</style></head><body><main><header><h1>六类常用网络干扰业务 · Formal-backed 验收</h1>
<p>v2.9.2 + P0 Benchmark · 实际数学 Core + 独立 Replay · 已有定理，不新增 Family</p></header>
<div class="cards"><div class="metric"><strong id="scenarios"></strong><small>常用业务设置</small></div>
<div class="metric"><strong id="total"></strong><small>正式运行案例</small></div>
<div class="metric"><strong id="pt"></strong><small>合成 POINT / replay</small></div>
<div class="metric"><strong id="rej"></strong><small>信息或支持阻断</small></div></div>
<div class="panel warn">这是一份 <b>合成研究合同的有效域演示</b>，不代表真实企业提供了总体 A4、接受了 A5，
不验证 LLM 对原始业务文本的理解，也不推断真实业务中有多少可 POINT。每一个 POINT 仅为已经审核前提的符号识别。</div>
<div class="panel"><h2>按业务和识别状态筛选</h2><div class="controls"><input id="find" placeholder="搜索设计、业务、拒绝原因"/>
<select id="scenario"><option value="">全部业务</option></select>
<select id="status"><option value="">全部状态</option><option>POINT</option><option>NEEDS_INPUT</option><option>UNSUPPORTED</option></select></div>
<div id="cases"></div></div>
</main><script id="payload" type="application/json">'''+payload+'''</script><script>
const D=JSON.parse(document.getElementById('payload').textContent);const $=s=>document.querySelector(s);
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
$('#scenarios').textContent=D.scenario_count;$('#total').textContent=D.case_count;
$('#pt').textContent=D.status_counts.POINT||0;$('#rej').textContent=D.case_count-(D.status_counts.POINT||0);
for(const s of D.scenarios)$('#scenario').insertAdjacentHTML('beforeend',`<option value="${safe(s.id)}">${safe(s.title)}</option>`);
function render(){const q=$('#find').value.toLowerCase(),s=$('#status').value,g=$('#scenario').value;
const rows=D.cases.filter(x=>(!s||x.actual_status===s)&&(!g||x.scenario_id===g)&&JSON.stringify(x).toLowerCase().includes(q));
$('#cases').innerHTML=rows.map(x=>`<details class="item"><summary><span><b>${safe(x.scenario)}</b> · ${safe(x.variant)}</span><span class="tag ${safe(x.actual_status)}">${safe(x.actual_status)}</span></summary>
<p>${safe(x.question)}</p><p><b>Design:</b> ${safe(x.design)} · <b>Exposure:</b> ${safe(x.exposure)} · <b>Route:</b> ${safe(x.route||'not admitted')}</p>
<p>Expected=${safe(x.expected_status)} · Replay=${safe(x.has_verified_core_result)} · Case expectation passed=${safe(x.passed)}</p>
<p>审核风险：${safe(x.intended_case_interpretation)} · Reason=${safe(x.reason||'N/A')}</p>
<pre>数学合同指纹 ${safe(x.target_contract_digest)}\n${safe(x.identification_excerpt)}</pre></details>`).join('')||'<p>无匹配案例</p>'}
$('#find').addEventListener('input',render);$('#status').addEventListener('change',render);$('#scenario').addEventListener('change',render);render();
</script></body></html>'''


def run(outdir:Path):
    data=generate()
    outdir.mkdir(parents=True,exist_ok=True)
    paths=(outdir/(STEM+'.json'),outdir/(STEM+'.html'))
    paths[0].write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    paths[1].write_text(render_html(data),encoding='utf8')
    print('six-business benchmark:',data['scenario_count'],'settings,',data['case_count'],'cases;',data['status_counts'],'pass',data['pass_count'])
    if data['pass_count']!=data['case_count']:
        raise AssertionError('Unexpected Core result in one of six reviewed synthetic contracts')
    return paths

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default='common_business_assets');args=ap.parse_args()
    run(Path(args.output_dir))
