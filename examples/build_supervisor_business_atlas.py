"""Deterministic offline supervisor UI merging implemented scopes and live Core cases.

Green means only this scenario's *hypothetical* POINT, never general coverage.
PARTIAL panel is a mathematically scoped standalone research example, not Core.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path
from examples.build_supervisor_dashboard import snapshot
from examples.run_common_business_benchmark import generate as bench
from research_partial.star7_bounded_r2_policy_demo import generate as partial

STEM='CFM_ID_v293_Supervisor_Common_Business_Coverage_and_Partial_Research'

def data():
    m=snapshot();b=bench();p=partial()
    assert b['pass_count']==b['case_count'] and m['counts']['routes']==10
    assert not p['formally_certified_partial']
    return {'version':'v2.9.2-postrelease-P0-benchmark',
        'metadata':{'counts':m['counts'],'designs':m['designs'],'exposures':m['exposures'],
                    'mechanisms':m['mechanisms'],'topologies':m['topologies']},
        'formal_business':b,'isolated_partial_research':p,
        'not_real_business_coverage':True,'numeric_estimation_performed':False}

CSS='''
:root{--navy:#142c46;--ink:#1e334b;--muted:#667b8f;--teal:#107c78;--line:#dce4eb;--bg:#f5f8fb;--paper:#fff;--ok:#176b4a;--warn:#8b651b;--stop:#944b53}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,"Noto Sans SC","Microsoft Yahei",sans-serif;font-size:14px;line-height:1.6}
main{max-width:1270px;margin:auto;padding:24px 22px 70px}.hero{border-radius:20px;background:linear-gradient(125deg,#122b45,#195b69 85%);padding:30px 34px;color:white}
h1{font-size:29px;line-height:1.25;margin:0}.hero p{color:#d3e6ef;margin:8px 0}.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.chip{border:1px solid #9bb9c4;border-radius:22px;padding:4px 9px;font-size:12px}
.tabs{display:flex;gap:7px;overflow:auto;margin-top:18px}.tab{border:1px solid var(--line);background:white;padding:10px 15px;border-radius:11px;cursor:pointer;font-weight:650;color:var(--ink)}.tab.active{background:var(--teal);color:white;border-color:var(--teal)}
.section{display:none}.section.active{display:block}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin:20px 0}.metric,.panel{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:17px}
.metric strong{font-size:27px;display:block;line-height:1.25}.metric small{color:var(--muted)}h2{font-size:22px;margin:25px 0 10px}h3{font-size:17px;margin:8px 0}
.panel{margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.item{border:1px solid var(--line);border-radius:12px;padding:14px;background:white}.item p{color:var(--muted);font-size:12px}
.callout{padding:13px 17px;background:#fff5e3;border-left:4px solid #c58a3f;border-radius:6px;margin:16px 0}.small{font-size:12px;color:var(--muted)}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}input,select{border:1px solid #cbd5df;border-radius:9px;padding:9px;font:inherit;color:var(--ink);background:white}input{min-width:225px;flex:1}
.case{border:1px solid var(--line);border-radius:11px;padding:14px;margin:9px 0;background:white}summary{cursor:pointer;display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap}
.status{font-size:11px;font-weight:750;border-radius:18px;padding:3px 8px}.POINT{background:#dcf5e5;color:var(--ok)}.NEEDS_INPUT{background:#fff0d3;color:var(--warn)}.UNSUPPORTED{background:#fde7e8;color:var(--stop)}
pre{font-size:12px;background:#f5f8fc;white-space:pre-wrap;overflow-wrap:anywhere;padding:10px;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:11px 9px;text-align:left;vertical-align:top}th{background:#f3f7fa}
.math{font-size:18px;font-family:Georgia,serif;background:#edf5f6;border-radius:10px;padding:17px;overflow:auto}.bar{height:14px;display:flex;overflow:hidden;border-radius:12px;margin:10px 0 3px}.seg{height:100%}.key{display:flex;flex-wrap:wrap;gap:16px}.key b{font-weight:700}
a{color:#14677f}button{font:inherit}
@media(max-width:720px){h1{font-size:23px}main{padding:12px}.hero{padding:24px}}
'''
JS='''
const D=JSON.parse(document.getElementById('data').textContent);
const $=s=>document.querySelector(s);const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const B=D.formal_business,P=D.isolated_partial_research,M=D.metadata;
const colors={POINT:'#197350',NEEDS_INPUT:'#d7a54d',UNSUPPORTED:'#c76f79'};
for(const status of ['POINT','NEEDS_INPUT','UNSUPPORTED']){
 const n=B.status_counts[status]||0;
 const bar=document.createElement('div');bar.className='seg';bar.style.background=colors[status];bar.style.width=(100*n/B.case_count)+'%';
 bar.title=status+': '+n;$('#bar').appendChild(bar);
}
$('#summary').textContent=`正式数学 Core 已在 ${B.scenario_count} 种合成业务设置下执行 ${B.case_count} 个查询；${B.pass_count}/${B.case_count} 个与预设数学结果一致。其中 ${B.status_counts.POINT||0} 个 POINT 均已独立 replay。`;
function render(){const q=$('#search').value.toLowerCase(),s=$('#status').value,g=$('#scene').value;
 const rows=B.cases.filter(x=>(!s||x.actual_status===s)&&(!g||x.scenario_id===g)&&JSON.stringify(x).toLowerCase().includes(q));
 $('#casecount').textContent=`显示 ${rows.length}/${B.cases.length} 个实际 Core 运行案例`;
 $('#cases').innerHTML=rows.map(x=>`<details class="case"><summary><span><b>${safe(x.scenario)}</b> · ${safe(x.variant)}</span><span class="status ${safe(x.actual_status)}">${safe(x.actual_status)}</span></summary>
 <p>${safe(x.question)}</p><p><b>${safe(x.design)}</b> · ${safe(x.exposure)} · Route: ${safe(x.route||'无 POINT 路线')} · Replay: ${x.has_verified_core_result}</p>
 <p class="small">${safe(x.intended_case_interpretation)}。Code: ${safe(x.reason||'VERIFIED')}</p><pre>${safe(x.identification_excerpt||'No admitted population functional')}
合成目标合同摘要：${safe(x.target_contract_digest)}</pre></details>`).join('')||'<p>无匹配案例</p>';
}
for(const s of B.scenarios)$('#scene').insertAdjacentHTML('beforeend',`<option value="${safe(s.id)}">${safe(s.title)}</option>`);
for(const id of ['search','status','scene'])$('#'+id).addEventListener(id==='search'?'input':'change',render);render();
$('#designs').innerHTML=M.designs.map(x=>`<div class="item"><h3>${safe(x.id)} · ${safe(x.title)}</h3><p>${safe(x.business)}</p><p>${safe(x.notes)}</p></div>`).join('');
$('#exposures').innerHTML=M.exposures.map(x=>`<div class="item"><h3>${safe(x.id)} · ${safe(x.title)}</h3><p>${safe(x.business)}</p><p>${safe(x.notes)}</p></div>`).join('');
$('#routes').innerHTML=M.mechanisms.map(x=>`<div class="item"><h3>${safe(x.id)} · ${safe(x.title)}</h3><p>${safe(x.assumptions)}</p><p>${safe(x.focus)}</p></div>`).join('');
$('#support').innerHTML=Object.entries(P.exact_signature_support).map(([key,p])=>`<tr><td>${safe(key)}</td><td>${safe(p)}</td><td>${key==='hub'?'目标不可达':'目标签名在原设计正支持'}</td></tr>`).join('');
$('.tabs').addEventListener('click',e=>{const x=e.target.closest('[data-tab]');if(!x)return;
 document.querySelectorAll('.tab').forEach(y=>y.classList.toggle('active',y===x));
 document.querySelectorAll('.section').forEach(y=>y.classList.toggle('active',y.id===x.dataset.tab));});
'''
HTML='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Causal-IDFM · 高频业务 POINT 覆盖与 PARTIAL 研究</title><style>__CSS__</style></head><body>
<main><header class="hero"><h1>网络干扰 · 高频业务 POINT 覆盖验收</h1><p>导师演示 · v2.9.2 后续 P0 增量（未改数学 Core） · 合成总体 A4/A5 + 真实 Core + 独立 replay</p>
<div class="chips"><span class="chip">6 个常用业务类型</span><span class="chip">18 个正式查询</span><span class="chip">4 个 POINT 机制</span><span class="chip">D1–D6、E1–E5 已实现组件</span><span class="chip">PARTIAL 单独列为研究示例</span></div></header>
<nav class="tabs"><button class="tab active" data-tab="business">业务实测</button><button class="tab" data-tab="library">识别能力地图</button><button class="tab" data-tab="partial">PARTIAL 研究示例</button></nav>
<section id="business" class="section active"><div class="metrics"><div class="metric"><strong>6</strong><small>真实风格、合成协议</small></div>
<div class="metric"><strong>18</strong><small>正式数学 Core 查询</small></div><div class="metric"><strong>7</strong><small>合成 POINT + replay</small></div>
<div class="metric"><strong>11</strong><small>信息门禁或结构支持阻断</small></div></div>
<p class="callout"><b>解释边界：</b>这不是抽样得到的现实市场覆盖率，也没有真实的人类审批或 LLM 文本理解准确率。每个案例的 A4/A5 为事先固定的合成研究合同；绿色仅表示该特定查询满足正式定理。</p>
<div class="panel"><h2>查询状态总览</h2><div id="bar" class="bar"></div><div class="key small"><b>POINT · 7</b><b>NEEDS_INPUT · 7</b><b>UNSUPPORTED · 4</b></div><p id="summary"></p></div>
<div class="panel"><h2>业务类型、数学目标与拒绝原因</h2><div class="controls"><input id="search" placeholder="搜索业务场景 / 设计 / 原因"/>
<select id="scene"><option value="">全部六类业务</option></select><select id="status"><option value="">全部状态</option><option>POINT</option><option>NEEDS_INPUT</option><option>UNSUPPORTED</option></select></div>
<p class="small" id="casecount"></p><div id="cases"></div></div></section>
<section id="library" class="section"><h2>数学能力地图 · 正式实现范围</h2><div class="metrics">
<div class="metric"><strong>4</strong><small>POINT 数学机制</small></div><div class="metric"><strong>10</strong><small>正式业务 Route</small></div>
<div class="metric"><strong>6</strong><small>Design</small></div><div class="metric"><strong>5</strong><small>Exposure</small></div><div class="metric"><strong>11</strong><small>前提类型名称</small></div></div>
<p class="callout">Design × Exposure 的 30 个组件组合不是 30 个无条件 POINT 场景。必须分别满足 A4、A5、A6；固定网络与均值目标仍有有效域限制。</p>
<h2>Design</h2><div id="designs" class="grid"></div><h2>Exposure</h2><div id="exposures" class="grid"></div><h2>识别机制</h2><div id="routes" class="grid"></div></section>
<section id="partial" class="section"><h2>研究原型：Star7 的有界政策值</h2>
<p class="callout"><b>未进入生产级 PARTIAL / R4：</b>下面是隔离的、用独立穷举和兼容世界反例核对的研究级演示，不是正式 Network PARTIAL 证书，也不是通过 POINT Core 认证的 policy value。</p>
<div class="panel"><p>固定 7 人星型协作网络、D2 每次恰好 3 人 treated、E1 严格多数。目标是全员 treated 时的平均结果。中心节点的目标签名零支持，其余 6 个叶节点签名支持为 1/7。</p>
<div class="math">若 Y∈[0,1] 且明确接受 mean-signature sufficiency：<br>（Σ 六个叶节点已识别的 μ<sub>i</sub>）/7 ≤ V(全员) ≤ （Σ 六个叶节点已识别的 μ<sub>i</sub> + 1）/7</div>
<p>区间宽度恒为 <b>1/7</b>。若纯粹为演示设每个叶节点 μ<sub>i</sub>=1/2，则区间为 <b>[3/7, 4/7]</b>。这是刻意虚构的符号总体值，不是实际员工销售数据。</p>
<table><thead><tr><th>节点</th><th>全员处理目标签名支持</th><th>解释</th></tr></thead><tbody id="support"></tbody></table>
<p class="small">两个实验中不可区分的潜在结果世界，中心节点在原实验永不出现的签名下分别取 0 和 1，恰好达到两端。因此在本例额外限制范围内界限是 sharp。</p></div>
<div class="panel"><h2>相关文献</h2><p><a href="https://proceedings.mlr.press/v306/wang26ez.html" target="_blank" rel="noopener noreferrer">Wang–Liu–Zhang (ICML 2026)：网络政策值非重叠、平滑性与 LP bounds</a></p>
<p><a href="https://onlinelibrary.wiley.com/doi/10.1111/j.1368-423X.2012.00368.x" target="_blank" rel="noopener noreferrer">Manski (2013)：社会互动响应约束与识别</a></p>
<p><a href="https://arxiv.org/abs/2602.03459" target="_blank" rel="noopener noreferrer">Schröder 等 (2026)：Exposure Mapping 误设下的 Partial Bounds</a></p>
<p class="small">本原型只实现一个更简单的“有界结果 + 部分签名支持”定理实例，并未复现这些论文的一般 LP 或敏感性定理。</p></div></section>
<script id="data" type="application/json">__DATA__</script><script>__JS__</script></main></body></html>'''

def run(outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    obj=data()
    p_json=outdir/(STEM+'.json');p_html=outdir/(STEM+'.html')
    p_json.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    html=HTML.replace('__CSS__',CSS).replace('__DATA__',json.dumps(obj,ensure_ascii=False,sort_keys=True).replace('<','\\u003c')).replace('__JS__',JS)
    p_html.write_text(html,encoding='utf8')
    return (p_json,p_html)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',default='showcase_v293');args=parser.parse_args()
    print('generated',*[str(p) for p in run(Path(args.output_dir))])
