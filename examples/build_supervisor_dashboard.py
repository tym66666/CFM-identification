"""Build an offline supervisor dashboard from implemented metadata plus curated examples.

The example status is an applicability classification, NOT a measured real-world
coverage rate, and not a live POINT verifier for arbitrary new business inputs.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from html import escape
from pfn_pipeline.identification_observational_nodewise_adjustment import implemented_assumption_catalog_v28
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentDesign
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureGrouping

DESIGNS=[
 dict(id='D1',title='独立 Bernoulli',family='HeterogeneousBernoulliDesignV1',business='用户/员工独立 A/B 灰度',priority='高',notes='已知个体处理概率；适合单元级实验；群体曝光可能发生干扰'),
 dict(id='D2',title='固定总配额',family='CompleteRandomizationDesignV1',business='固定 100 名试用资格',priority='高',notes='所有节点统一配额；极端完整政策可能零支持'),
 dict(id='D3',title='两组独立配额',family='TwoGroupFixedQuotaDesignV1',business='销售/客服两部门名额',priority='中',notes='两组特例；多部门可使用 D5'),
 dict(id='D4',title='簇级 Bernoulli',family='ClusterBernoulliDesignV24',business='门店/班级整体随机',priority='高',notes='簇内全同一 treatment，部分 spillover arms 必定零支持'),
 dict(id='D5',title='多组固定配额',family='MultiGroupFixedQuotaDesignV25',business='多部门独立试用名额',priority='高',notes='可处理 3–64 个处理前非空分组'),
 dict(id='D6',title='两阶段配额混合',family='TwoStageQuotaMixtureDesignV27',business='先随机饱和度，再组内配额',priority='中',notes='第一阶段 quota profile 可相关；必须额外接受无直接结果效应 A5'),
 dict(id='D7',title='不等概率固定配额',family='UnequalProbabilityFixedQuotaDesign',business='按已知名单概率抽固定名额',priority='中',notes='各完整名单概率不等或按对象权重归一；精确支持用全排列枚举（N≤8）'),
 dict(id='D8',title='重随机化平衡',family='RerandomizedBalancedDesign',business='先抽固定名额再按平衡规则重抽样',priority='中',notes='拒绝抽样 q_B(A)=q(A)1{B(A)}/P_q(B)；精确支持用全排列枚举（N≤8）'),
]
EXPOSURES=[
 dict(id='E1',title='邻居严格多数',grouping='strict_majority_ties_low',business='多数同事启用 AI',notes='阈值型；不是自动的充分性假设'),
 dict(id='E2',title='邻居处理比例三档',grouping='three_level_treated_neighbor_fraction',business='同事启用比例低/中/高',notes='孤立节点三档定义无效'),
 dict(id='E3',title='核心合作者多数',grouping='pretreatment_core_collaborator_majority',business='核心合作同事启用情况',notes='必须事前给定非空合法核心集合'),
 dict(id='E4',title='精确处理邻居人数',grouping='exact_treated_neighbor_count',business='恰有 k 位同事使用 AI',notes='状态数量随度数变化；高阶支持可能困难'),
 dict(id='E5',title='至少一位邻居处理',grouping='any_treated_neighbor',business='是否有任一同伴使用 AI',notes='粗粒度便于解释；R2/R3 不可因此默认充分性'),
]
TOPOLOGIES=[
 dict(id='path',title='路径型 Path',notes='链式接触、相邻干扰；固定无向图可表达',draw='path'),
 dict(id='ring',title='环型 Ring',notes='循环合作、定期邻接；固定无向图可表达',draw='ring'),
 dict(id='star',title='星型 Star',notes='团队领导与外围成员；中心节点可能零签名支持',draw='star'),
 dict(id='complete',title='完全连接 Complete',notes='高度密集团队；多数 exposure 可能受配额限制',draw='complete'),
 dict(id='bipartite',title='二部图 Bipartite',notes='买卖方连接仅在无向边层面可表示；非均衡理论',draw='bipartite'),
 dict(id='community',title='社群 Community',notes='部门/群组关系；不可自动假设社群间无干扰',draw='community'),
 dict(id='small_world_like',title='小世界 Small-world-like',notes='局部密集与远距连接的测试图',draw='smallworld'),
 dict(id='hub_scale_free_like',title='Hub / Scale-free-like',notes='核心节点高度连接，支持受配额影响',draw='hub'),
 dict(id='disconnected_with_isolate',title='断开/孤立节点',notes='E2 对孤立节点无定义；E3 必须有非空核心合作者',draw='isolate'),
]
MECHANISMS=[
 dict(id='R1a',title='随机实验的 Exposure Arm/Contrasts',focus='实验 q 标准化效应',assumptions='已知 q、全向量随机化、consistency、A4 arm 均值、联合 arm 正支持',example='本人使用 AI vs 不用；邻居多数已处理时的差异',confidence='正式实现'),
 dict(id='R1b',title='有支持的完整分配政策',focus='真实固定政策值与有限混合',assumptions='已知 q、完整政策正支持、完整 assignment A4',example='指定全公司 AI 开通向量的平均结果',confidence='正式实现'),
 dict(id='R2',title='均值 Signature 结构外推',focus='部分 off-support 真实政策',assumptions='随机化条件 + 独立接受 mean-signature sufficiency + 签名支持',example='实验固定名额，但业务询问全员使用 AI',confidence='正式实现，强结构假设'),
 dict(id='R3',title='观测网络条件交换性/调整',focus='观测政策、p 标准化与局部调整效应',assumptions='full-vector 或 exposure-level 交换性、必要结构限制、typed 总体律及逐层支持',example='员工自选是否启用 AI，控制处理前个人与邻居特征',confidence='正式有限子域；不能自动证明无混杂'),
]
SCENARIOS=[
 ('独立线上 A/B','广告/软件','D1 / E1、E5','R1a','条件支持','单元级 Bernoulli 可用；需独立随机化、A4、arm support'),
 ('固定总人数灰度','企业 AI','D2 / E4、E5','R1a、R1b','条件支持','完整政策不一定有 q>0；可识别的 arm 与 rollout 要区别'),
 ('两部门配额','企业管理','D3 / E1、E3','R1a、R2','条件支持','核心合作者集合需事前定义；R2 需独立 A5'),
 ('门店整体试用','连锁零售','D4 / E1、E2','R1a、R1b','条件支持','簇内处理相同，必须逐节点检查目标状态是否可达'),
 ('多部门分配资格','企业 AI','D5 / E4','R1a、R1b、R2','条件支持','分组固定配额；全员 rollout 可能零支持'),
 ('两阶段饱和度','学校/社区','D6 / E1、E5','R1a、R2','条件支持','只能在配额混合子域下复用原定理；第一阶段直接效应需排除'),
 ('实验支持内完整政策','企业 AI','任一合法 D / 完整向量','R1b','条件支持','必须有完整政策 q(z)>0 和 assignment-level A4'),
 ('实验零支持政策','企业 AI','D2 / E1、E5','R2','强假设条件支持','签名均值充分性 + 每个权重节点签名正支持'),
 ('观测性自选择网络','企业 AI','观测总体 p / E1–E5','R3','强假设条件支持','需独立接受交换性；不能从处理概率模型推出因果无混杂'),
 ('观测协变量调整','社交网络','节点 X_i + 邻居 X 计数','R3','有限子域','仅一个二元节点协变量/邻居正值计数及受限总体律'),
 ('相互竞争的双边市场','平台','买卖双方与库存/均衡','未实现通用','仅部分可表达','二分图可用无向边表达，但竞争/均衡/多类处理缺独立定理'),
 ('主管影响员工更强','企业 AI','有向加权网络','未实现通用','未实现','目前主要简单无向图，没有权重或方向的通用识别'),
 ('动态扩散与反复干预','社交媒体','多期动态网络','未实现','未实现','不支持通用动态或处理改变网络'),
 ('员工获得不同 AI 剂量','企业 AI','多值/连续 treatment','未实现','未实现','目前处理变量为单时点二元'),
 ('跨公司推广政策','跨企业','跨 W 与新网络总体','未实现通用','未实现','固定 W 结果不能自动推广到其他总体'),
 ('复杂随机 rollout','大型平台','任意 stochastic policy kernel','未实现通用','未实现','R1b 只支持固定分配与有限认证混合'),
]
REFERENCES=[
 dict(title='Aronow & Samii (2017)',use='Exposure × Design × Estimand；设计标准化与支持条件',url='https://arxiv.org/abs/1305.6156'),
 dict(title='Hudgens & Halloran (2008)',use='部分干扰、两阶段实验与直接/间接效应',url='https://pmc.ncbi.nlm.nih.gov/articles/PMC2600548/'),
 dict(title='LinkedIn Engineering (2018)',use='个体随机 vs 社交图簇随机的实际平台案例',url='https://www.linkedin.com/blog/engineering/ab-testing-experimentation/detecting-interference-an-a-b-test-of-a-b-tests'),
 dict(title='LinkedIn Engineering (2020)',use='在线随机分配与哈希分桶工程实践',url='https://www.linkedin.com/blog/engineering/ab-testing-experimentation/a-b-testing-variant-assignment'),
 dict(title='Airbnb / Management Science (2024)',use='双边平台干扰偏差与 cluster randomized 实验',url='https://pubsonline.informs.org/doi/10.1287/mnsc.2020.01157'),
 dict(title='Biometrics: Two-stage randomized experiments',use='两阶段直接/溢出效应及效能分析',url='https://academic.oup.com/biometrics/article/79/3/2370/7513883'),
 dict(title='Forastiere, Airoldi & Mealli (2021)',use='观测网络个人/邻居协变量与无混杂假设',url='https://arxiv.org/abs/1609.06245'),
]

def snapshot():
    catalog=implemented_assumption_catalog_v28()
    assert {x['name'] for x in catalog['assumptions']}
    actualdesign={x.__name__ for x in AssignmentDesign.__args__}
    actualexp=set(ExposureGrouping.__args__)
    assert {x['family'] for x in DESIGNS}==actualdesign
    assert {x['grouping'] for x in EXPOSURES}==actualexp
    assert len(catalog['route_ids'])==10 and len(catalog['assumptions'])==11
    return dict(version='v2.9.2-research-coverage-map',core_math='v2.8 postrelease P1.1 (unchanged)',
        counts=dict(mechanisms=len(MECHANISMS),routes=len(catalog['route_ids']),
            design=len(DESIGNS),exposure=len(EXPOSURES),topology_shapes=len(TOPOLOGIES),design_exposure_cells=len(DESIGNS)*len(EXPOSURES),
            premise_names=len(catalog['assumptions'])),
        verified_by='implemented_assumption_catalog_v28, AssignmentDesign union, ExposureGrouping Literal',
        caveat='NOT empirical business coverage; each case requires A4/A5/A6 checks; no observed business effects',
        designs=DESIGNS,exposures=EXPOSURES,topologies=TOPOLOGIES,mechanisms=MECHANISMS,
        routes=catalog['route_ids'],assumptions=catalog['assumptions'],
        scenarios=[dict(name=x[0],area=x[1],setting=x[2],route=x[3],status=x[4],notes=x[5]) for x in SCENARIOS],
        references=REFERENCES)

CSS='''
:root{color-scheme:light;--bg:#f7f9fc;--ink:#112238;--muted:#596b80;--accent:#176a6a;--border:#dce5ec;--soft:#e9f3f1;--warn:#fff3de;--blocked:#fcebea;--white:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Inter,"Noto Sans SC","Microsoft Yahei",system-ui,sans-serif;color:var(--ink);line-height:1.55}
.wrap{max-width:1240px;margin:0 auto;padding:32px 22px 90px}.hero{background:linear-gradient(135deg,#102844,#174c61 60%,#13726c);color:white;padding:36px;border-radius:20px}
.hero h1{font-size:34px;line-height:1.2;margin:0 0 12px}.hero p{color:#cde5e8;max-width:920px;margin:0}.chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}.chip{border:1px solid #93bcc3;padding:5px 12px;border-radius:30px;font-size:12px}
.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:13px;margin-top:18px}.metric{border:1px solid var(--border);background:white;border-radius:14px;padding:16px}.metric b{font-size:27px;display:block;line-height:1.2}.metric span{font-size:12px;color:var(--muted)}
h2{margin-top:34px;font-size:24px;line-height:1.3}h3{font-size:18px;margin:12px 0 6px}.subtitle{color:var(--muted);margin-top:-9px}.panel{background:white;border:1px solid var(--border);border-radius:16px;padding:20px;margin-top:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.item{border:1px solid var(--border);border-radius:12px;padding:16px;background:#fff}.item p{font-size:13px;color:var(--muted);margin:6px 0}.tag{display:inline-block;border-radius:20px;padding:3px 9px;font-size:11px;background:#e9f3f1;color:#245a57}
.list{padding-left:20px}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:12px;text-align:left;border-bottom:1px solid var(--border);vertical-align:top}th{color:#4d6177;background:#f6f9fb;white-space:nowrap}th:first-child{border-radius:6px 0 0 0}
.matrix{display:grid;grid-template-columns:190px repeat(5,minmax(110px,1fr));min-width:760px;gap:6px}.mhead,.mcell{border-radius:9px;padding:10px;font-size:12px}.mhead{background:#e7eef4;font-weight:700}.mcell{background:#e8f4ef;border:1px solid #cce7d9;cursor:pointer;text-align:left}.mcell:hover,.mcell:focus{outline:2px solid #138a78}.hint{color:var(--muted);font-size:12px}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}input,select{font:inherit;border:1px solid #cbd7df;border-radius:9px;padding:10px 12px;background:white;color:#112238}input{min-width:240px;flex:1}.status{font-size:12px;font-weight:700;white-space:nowrap}.status.good{color:#18705d}.status.limited{color:#9b672a}.status.none{color:#ae4c49}
.detail{margin-top:14px;background:#edf6f6;border:1px solid #c6dede;padding:15px;border-radius:11px;font-size:13px}a{color:#126478;text-decoration:none}a:hover{text-decoration:underline}
.alert{border-left:4px solid #c28b40;background:#fff6e9;padding:12px 16px;border-radius:6px}.footer{margin-top:35px;font-size:12px;color:var(--muted)}button{font:inherit}
@media(max-width:800px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.hero h1{font-size:25px}.wrap{padding:16px 14px}.hero{padding:25px}}
'''
JS='''
const D=window.CFM_DATA;
const $=s=>document.querySelector(s);
const safe=(s)=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const mapStatus=s=>s==='条件支持'?'good':s.includes('假设')||s==='有限子域'||s==='仅部分可表达'?'limited':'none';
const designBox=$('#designs');D.designs.forEach(d=>{designBox.insertAdjacentHTML('beforeend',`<div class="item"><span class="tag">${d.id} · ${d.priority}优先</span><h3>${safe(d.title)}</h3><p><b>业务：</b>${safe(d.business)}</p><p>${safe(d.notes)}</p></div>`)});
const expBox=$('#exposures');D.exposures.forEach(e=>expBox.insertAdjacentHTML('beforeend',`<div class="item"><span class="tag">${e.id}</span><h3>${safe(e.title)}</h3><p><b>示例：</b>${safe(e.business)}</p><p>${safe(e.notes)}</p></div>`));
const GRAPH_EDGES={
 path:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6]],
 ring:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,0]],
 star:[[0,1],[0,2],[0,3],[0,4],[0,5],[0,6]],
 complete:Array.from({length:7},(_,i)=>Array.from({length:7},(_,j)=>i<j?[i,j]:null)).flat().filter(Boolean),
 bipartite:[[0,3],[0,4],[1,4],[1,5],[2,5],[2,6],[2,3]],
 community:[[0,1],[1,2],[0,2],[3,4],[4,5],[3,5],[2,3],[5,6]],
 smallworld:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,0],[0,3],[1,4]],
 hub:[[0,1],[0,2],[0,3],[0,4],[0,5],[0,6],[1,2],[3,4]],
 isolate:[[0,1],[1,2],[2,3],[3,4],[4,5]]
};
function graphSvg(kind){
 const points=kind==='path'||kind==='isolate'
   ?Array.from({length:7},(_,i)=>[21+i*36,43])
   :kind==='star'||kind==='hub'
   ?[[128,45],...Array.from({length:6},(_,j)=>[128+86*Math.cos(j*Math.PI/3),45+30*Math.sin(j*Math.PI/3)])]
   :kind==='bipartite'
   ?[[60,15],[60,44],[60,73],[195,10],[195,30],[195,53],[195,75]]
   :Array.from({length:7},(_,j)=>[128+94*Math.cos(j*2*Math.PI/7),45+32*Math.sin(j*2*Math.PI/7)]);
 const edges=GRAPH_EDGES[kind]||[];
 return '<svg aria-label="示意网络结构" role="img" viewBox="0 0 256 90" width="100%" height="90">'+
 edges.map(([i,j])=>`<line x1="${points[i][0]}" y1="${points[i][1]}" x2="${points[j][0]}" y2="${points[j][1]}" stroke="#93b4bd" stroke-width="1.7"/>`).join('')+
 points.map(([x,y],i)=>`<circle cx="${x}" cy="${y}" r="5.2" fill="${kind==='isolate'&&i===6?'#c0765b':'#166b74'}"/>`).join('')+'</svg>';
}
const topoBox=$('#topologies');D.topologies.forEach(t=>topoBox.insertAdjacentHTML('beforeend',`<div class="item"><span class="tag">${safe(t.id)}</span>${graphSvg(t.draw)}<h3>${safe(t.title)}</h3><p>${safe(t.notes)}</p></div>`));
const mechBox=$('#mechanisms');D.mechanisms.forEach(r=>mechBox.insertAdjacentHTML('beforeend',`<div class="item"><span class="tag">${r.id} · ${safe(r.confidence)}</span><h3>${safe(r.title)}</h3><p><b>识别：</b>${safe(r.focus)}</p><p><b>关键：</b>${safe(r.assumptions)}</p><p><b>业务：</b>${safe(r.example)}</p></div>`));
const mat=$('#matrix');mat.insertAdjacentHTML('beforeend','<div class="mhead">Design \\ Exposure</div>');D.exposures.forEach(e=>mat.insertAdjacentHTML('beforeend',`<div class="mhead">${e.id} ${safe(e.title)}</div>`));
D.designs.forEach(d=>{mat.insertAdjacentHTML('beforeend',`<div class="mhead">${d.id} ${safe(d.title)}</div>`);D.exposures.forEach(e=>{const b=document.createElement('button');b.className='mcell';b.innerHTML='<strong>适用组件</strong><div class="hint">POINT 须逐实例验证</div>';b.addEventListener('click',()=>{$('#cellDetail').textContent=`${d.id} × ${e.id}：${d.title} + ${e.title}。该组合属于已实现的组件适用域；必须有固定处理前网络、该 exposure 有定义、目标签名正支持、已接受 A5 与足够 A4。${d.notes}；${e.notes}`;});mat.appendChild(b)})});
function renderCases(){const term=$('#search').value.trim().toLowerCase(),status=$('#filterStatus').value,area=$('#filterArea').value;const rows=D.scenarios.filter(x=>(!status||mapStatus(x.status)===status)&&(!area||x.area===area)&&(!term||Object.values(x).join(' ').toLowerCase().includes(term)));$('#caseCount').textContent=`显示 ${rows.length}/${D.scenarios.length} 个预设业务类型（不是实际覆盖率抽样）`;$('#caseBody').innerHTML=rows.map(x=>`<tr><td><strong>${safe(x.name)}</strong><div class="hint">${safe(x.area)}</div></td><td>${safe(x.setting)}</td><td>${safe(x.route)}</td><td><span class="status ${mapStatus(x.status)}">${safe(x.status)}</span></td><td>${safe(x.notes)}</td></tr>`).join('')||'<tr><td colspan="5">没有匹配的预设场景</td></tr>';}
D.scenarios.forEach(c=>{if(![...$('#filterArea').options].some(x=>x.value===c.area))$('#filterArea').add(new Option(c.area,c.area));});['#search','#filterStatus','#filterArea'].forEach(s=>$(s).addEventListener('input',renderCases));renderCases();
$('#assumptions').innerHTML=D.assumptions.map(x=>`<tr><td><code>${safe(x.name)}</code></td><td>${safe(x.layer)}</td><td>${safe(x.scientific_scope)}</td></tr>`).join('');
$('#refs').innerHTML=D.references.map(x=>`<li><a href="${safe(x.url)}" target="_blank" rel="noopener noreferrer">${safe(x.title)}</a> — ${safe(x.use)}</li>`).join('');
'''
HTML='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Causal-IDFM · Network POINT Coverage Atlas · v2.9.2</title><style>__CSS__</style></head><body><main class="wrap">
<section class="hero"><h1>网络干扰 POINT 识别能力地图</h1><p>导师展示版 · Causal-IDFM v2.9.2 · 定理、业务、设计、暴露、假设与未支持范围同屏对照。这里展示的是<strong>正式组件与适用条件</strong>，不是对真实世界识别成功率的估算。</p><div class="chips"><span class="chip">最新数学 Core 未改写</span><span class="chip">单时点二元 treatment</span><span class="chip">已知固定无向网络</span><span class="chip">A4 + A5 + A6 才能 POINT</span></div></section>
<div class="metrics"><div class="metric"><b>4</b><span>核心 POINT 原理</span></div><div class="metric"><b>10</b><span>正式业务路由</span></div><div class="metric"><b>6</b><span>已实现 Assignment</span></div><div class="metric"><b>5</b><span>Exposure 规则</span></div><div class="metric"><b>11</b><span>已编目前提名称</span></div></div>
<section><h2>01 · 常用实验 Design</h2><p class="subtitle">优先按“真实业务怎么分配处理资格”选择；常用程度是文献和案例驱动的定性优先级，不是统计频率。</p><div class="grid" id="designs"></div></section>
<section><h2>02 · 已实现的 Exposure Mapping</h2><p class="subtitle">定义一个 exposure 类别 ≠ 证明该类别充分刻画全部真实潜在结果。</p><div class="grid" id="exposures"></div></section>
<section><h2>03 · 已测试的九种固定无向网络形态</h2><p class="subtitle">来自 v2.2 跨拓扑验收，具体组合的 Arm/Signature 正支持仍需重新计算。二部图可表示不等于已支持双边市场均衡机制。</p><div class="grid" id="topologies"></div></section>
<section><h2>04 · 4 种数学识别机制</h2><div class="grid" id="mechanisms"></div></section>
<section><h2>05 · Design × Exposure 组件矩阵</h2><div class="alert"><strong>重要：</strong>以下绿色表示“支持该参数化组合并有正式定理可检查”，<strong>不表示所有节点和所有处理暴露状态都 POINT</strong>。点击任意单元查看条件。</div><div class="panel tablewrap"><div class="matrix" id="matrix"></div><div class="detail" id="cellDetail">点击 D×E 单元可查看对应的 A4/A5/A6 与有效域提醒。</div></div></section>
<section><h2>06 · 哪些业务设置能处理？</h2><p class="subtitle">预先整理的典型类别，展示当前实现边界，不是有代表性分母的真实业务覆盖率抽样。</p><div class="panel"><div class="controls"><input id="search" placeholder="搜索业务、Exposure、场景，例如：门店、政策、自选择"><select id="filterArea"><option value="">全部业务域</option></select><select id="filterStatus"><option value="">全部状态</option><option value="good">条件支持</option><option value="limited">有限/强假设</option><option value="none">未实现</option></select></div><div class="hint" id="caseCount"></div><div class="tablewrap"><table><thead><tr><th>业务设置</th><th>设计/暴露</th><th>路线</th><th>状态</th><th>限制及原因</th></tr></thead><tbody id="caseBody"></tbody></table></div></div></section>
<section><h2>07 · A4 / A5 / A6 为什么是必需的？</h2><div class="grid"><div class="item"><span class="tag">A4</span><h3>总体信息</h3><p>不是 CSV 变量名单；必须存在与 Target 匹配的可观测总体算子与粒度。</p></div><div class="item"><span class="tag">A5</span><h3>因果许可</h3><p>随机化、条件交换性、均值签名充分性或局部暴露充分性必须明确接受并记录作用域。</p></div><div class="item"><span class="tag">A6</span><h3>有效域与核验</h3><p>正支持、合法暴露状态、独立 theorem replay 与正确业务目标身份。</p></div></div><div class="panel tablewrap"><table><thead><tr><th>已编目前提</th><th>层级</th><th>正式适用范围</th></tr></thead><tbody id="assumptions"></tbody></table></div></section>
<section><h2>08 · 还没做到的重点</h2><div class="panel"><ul class="list"><li>不能宣称已覆盖“大多数现实网络干扰 POINT 问题”：没有独立代表性的业务分母，且科学假设真实性不能通过软件自动证实。</li><li>观测性 R3 仍有强交换性或 Exposure Sufficiency 限制；一般高维混杂、复杂自选择机制尚非通用实现。</li><li>有向/加权/动态或未知网络、通用多值/连续 treatment、跨总体迁移、一般 stochastic policy kernel 尚未完成。</li><li>本图不是数值 Estimation 系统；POINT 表示总体函数被识别，不意味着有限样本可准确估计。</li><li>v2.9.2 审批硬化侧重 A0↔数学绑定，不会新增识别定理。</li></ul></div></section>
<section><h2>09 · 用于导师问答的参考文献</h2><div class="panel"><ul class="list" id="refs"></ul></div></section><div class="footer">由源码中 AssignmentDesign、ExposureGrouping、implemented_assumption_catalog_v28 以及人工审核的典型业务案例共同生成；离线可读，无外部脚本依赖。© Causal-IDFM Research Demo</div>
</main><script>window.CFM_DATA=__DATA__;</script><script>__JS__</script></body></html>'''

def generate(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    data=snapshot()
    jsonpath=directory/'CFM_ID_Coverage_Atlas.json'
    htmlpath=directory/'CFM_ID_Coverage_Atlas.html'
    jsonpath.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    htmlpath.write_text(HTML.replace('__CSS__',CSS).replace('__JS__',JS)
        .replace('__DATA__',json.dumps(data,ensure_ascii=False,sort_keys=True).replace('</','<\\/'))+'\n',encoding='utf-8')
    return jsonpath,htmlpath

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',default='assets/coverage_fixtures');a=p.parse_args();
    for x in generate(a.outdir):print(x)
