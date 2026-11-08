"""v2.2 teacher demo built from ACTUALLY executed v2.1 theorem and support runs.

No simulation ground truth, generated sales outcomes, PFN estimates, or automated
natural-language target inference. Unregistered family capabilities are shown as
CONTRACT_GAP; the 32 deliberately chosen cards are NOT market coverage data.

Run at repository root:
 python -B -m examples.run_business_coverage_showcase --output-dir assets/business_coverage_fixtures
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pfn_pipeline.identification_coverage import run_business_coverage_v22
from examples.run_network_topology_matrix import run_topology_matrix


def _json(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)


def _html(coverage: dict, topology: dict) -> str:
    # Escape script terminators and Unicode line separators before embedding JSON.
    raw=json.dumps({'coverage':coverage,'topology':topology},ensure_ascii=False,
                   separators=(',',':'),allow_nan=False)
    safe=raw.replace('</','<\\/').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    return r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Causal-IDFM — Network Identification v2.2</title>
<style>
:root{font-family:Inter,ui-sans-serif,"PingFang SC","Microsoft YaHei",sans-serif;background:#f3f5f8;color:#182234}
*{box-sizing:border-box}body{margin:0}main{max-width:1380px;margin:auto;padding:34px 30px 70px}
h1{font-size:35px;letter-spacing:-1.2px;margin:8px 0 12px}h2{font-size:21px;margin:0 0 12px}p{line-height:1.6}
small,.sub{color:#66758a;font-size:13px}.tag{display:inline-block;font-size:11px;font-weight:760;letter-spacing:.5px;border:1px solid #c8d0df;color:#36475f;padding:6px 10px;border-radius:20px}
.hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:30px}
.hero p{max-width:900px;color:#536276;margin:0}.stamp{background:#172b48;color:white;padding:11px 15px;border-radius:12px;font-size:12px;line-height:1.6;white-space:nowrap}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 32px}
.kpi,.panel{background:white;border:1px solid #dce2eb;border-radius:17px;box-shadow:0 3px 14px #14294707}
.kpi{padding:21px 22px}.kpi strong{display:block;font-size:31px;font-variant-numeric:tabular-nums;line-height:1.2;margin-bottom:8px}.kpi span{font-size:12px;color:#64748b}
.panel{padding:23px 26px;margin:18px 0}.muted{color:#66758a}
.footnote{background:#edf2f8;padding:13px 17px;border-radius:10px;color:#374966;font-size:12px;margin:14px 0}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:20px 0 12px}
input,select{font-family:inherit;border:1px solid #cdd6e2;border-radius:10px;background:white;font-size:13px;padding:10px 12px;min-width:160px}input{width:310px}
.scroll{width:100%;overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:12px;min-width:1040px}
th{text-align:left;text-transform:uppercase;letter-spacing:.5px;font-size:11px;color:#607089;background:#f7f9fc}td,th{border-bottom:1px solid #e9edf3;padding:12px 9px;vertical-align:top}
tr:hover td{background:#f7faff}td:first-child{font-weight:760;color:#355478}td:nth-child(2){max-width:310px}
.chip{font-size:11px;font-weight:740;display:inline-block;border-radius:8px;padding:5px 8px;white-space:nowrap}
.good{background:#e1f4ec;color:#06735d}.warn{background:#fff1df;color:#9b6515}.bad{background:#fbe8e8;color:#a53535}.neutral{background:#e9eff8;color:#536781}
.tgrid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.barline{display:grid;grid-template-columns:158px 1fr 36px;align-items:center;gap:10px;margin:10px 0;font-size:11px}
.bars{height:14px;border-radius:4px;background:#e7ebf1;overflow:hidden;display:flex}.bar{height:100%;background:#259c89}.bar.invalid{background:#dcac5c}.bar.none{background:#d86b6b}
.tip{font-size:11px;color:#6b7890;margin:14px 0 0}.topology{display:flex;justify-content:space-between;gap:6px;border-bottom:1px solid #e9edf3;padding:11px 0;font-size:12px}
.topology:last-child{border-bottom:0}
summary{cursor:pointer;color:#315783;font-weight:640}details{margin:10px 0}details p{font-size:12px;color:#475569;margin:7px 0}
.footer{margin-top:32px;font-size:12px;color:#718096}
@media(max-width:850px){main{padding:16px 13px}.hero{display:block}.stamp{display:inline-block;margin-top:16px}.kpis{grid-template-columns:repeat(2,1fr)}.tgrid{grid-template-columns:1fr}input{width:100%}.panel{padding:17px 13px}}
</style>
</head>
<body><main>
<header class="hero"><div><span class="tag">CAUSAL-IDFM · IDENTIFICATION · v2.2</span>
<h1>Network Identification<br/>业务覆盖与正确性看板</h1>
<p>32 张逐项审计问题卡 + 9 种固定无向网络拓扑，来自真实 theorem/verifier 调用与明确的未实现合同差距。展示数学可识别性，不展示虚构的政策收益。</p></div>
<div class="stamp">RESEARCH AUDIT / 2026-10-17<br/>LOCAL REPRODUCIBLE FIXTURES</div></header>
<section class="kpis" id="kpis"></section>
<div class="footnote"><strong>阅读说明：</strong>通过的识别基于<strong>明确声明的合成总体算子和被接受的假设</strong>；没有输入真实销售结果、没有对所有目标训练估计器。32 张卡是刻意选择的边界测试，不是现实业务市场抽样，不能用成功数宣称市场覆盖率。B04 真实 ER300 1,200 arms 是历史 v2.1 验证记录，本轮仅重新计算一个小图 Batch。</div>
<section class="panel"><h2>01 / Business Coverage Matrix</h2><div class="sub">L0 形式化 · L1 路由 · L2 总体 POINT 及阻断 · L3 估计器能力</div>
<div class="controls"><input id="search" placeholder="搜索业务问题 / 卡片编号 / 拒绝原因" aria-label="搜索业务卡"/>
<select id="status" aria-label="按识别状态筛选"><option value="all">全部识别状态</option><option value="point">POINT (含历史 ER300)</option><option value="blocked">阻断/缺口/澄清</option></select>
<select id="route" aria-label="按路由筛选"><option value="all">全部路线</option><option value="R1A">R1a</option><option value="R1B">R1b</option><option value="R2">R2</option><option value="NOT_REGISTERED">未注册/未适用</option></select>
<span class="sub" id="visible"></span></div>
<div class="scroll"><table><thead><tr><th>案例</th><th>业务问题</th><th>L0 · Target</th><th>L1 · Route</th><th>L2 · Identification</th><th>L3 · Estimation</th></tr></thead><tbody id="cards"></tbody></table></div>
<details><summary>展开：如何解读 A4 / A5 / A6 及证据来源</summary><p>点击表格中的任一案例，会在下方显示它所要求的总体信息算子、因果假设、支持条件、执行证据与未满足原因。</p></details>
<div id="detail" class="footnote">请选择表格中的案例查看数学合同与实际证据。</div></section>
<section class="panel"><h2>02 / Cross-Topology × Randomization × Exposure</h2>
<p class="sub">每张图 × D1/D2/D3 × E1/E2/E3，共 81 个组合。只有在该组合中<strong>至少存在一个</strong>经过 replay 的 POINT arm 才记作成功，不代表 81 组全部节点、全部 arms 均支持。</p>
<div class="tgrid"><div id="topbars"></div><div id="policytop"></div></div>
<div class="tip">R2 对比：固定 7 人图、恰好处理 3 人、查询全员处理；所有 R1b 完整分配均零支持，R2 在额外<strong>合成且已接受</strong> mean-majority sufficiency 下因拓扑不同而产生不同结论。</div></section>
<section class="panel"><h2>03 / Quality Gate &amp; Known Scope</h2>
<div class="tgrid"><div><strong>本轮已加强</strong><p class="sub">PFN 旧 MajorityResponse：typed A4 研究坐标、q/g、来源及节点覆盖检查；原 R1a/Batch A4 检查保留；两条旧 Network POINT 入口被 fail-closed 隔离；历史证书重放也拒绝。</p></div>
<div><strong>仍未支持</strong><p class="sub">Cluster / two-stage 等复杂 assignment、neighbor count/any-treated 等新增 exposure、有向或动态网络、通用 Observational R3、Network PARTIAL、数值政策收益估计，以及自然语言任意业务自动形式化。</p></div></div>
</section>
<div class="footer">CFM-ID v2.2 · Standalone viewer · All theorem results generated from synthetic declared study contracts · NOT production causal truth or PFN estimates.</div>
</main>
<script id="results" type="application/json">__DATA_JSON__</script>
<script>
'use strict';
const doc=JSON.parse(document.getElementById('results').textContent), cards=doc.coverage.cards, topo=doc.topology;
const el=(tag,content,cls)=>{let n=document.createElement(tag);if(content!==undefined)n.textContent=String(content);if(cls)n.className=cls;return n;};
const statusClass=s=>s.startsWith('POINT')?'good':s==='NOT_CERTIFIED'||s==='NEEDS_INPUT'?'warn':s==='NO_REGISTERED_THEOREM'?'bad':'neutral';
const kpis=[['32','边界业务测试卡'],[String(cards.filter(c=>c.l2_identification.startsWith('POINT')).length),'当前样例 POINT（含历史）'],[String(topo.combinations_total),'拓扑×设计×Exposure 组合'],[String(topo.status_counts.POINT_ARM_VERIFIED),'至少 1 个 arm 已认证的组合']];
for(let k of kpis){let d=el('div',undefined,'kpi');d.append(el('strong',k[0]),el('span',k[1]));document.getElementById('kpis').append(d);}
function details(c){const div=document.getElementById('detail');div.replaceChildren();div.append(el('strong',c.case_id+' · '+c.business_question));
 for(const [name,v] of [['数学 Target',c.target_class],['A4：所需总体信息',c.a4_required_information],['A5：因果许可',c.a5_required_assumptions],['A6：支持与有效域',c.a6_support_and_validity],['证据类型',c.evidence_type],['实际理由',c.observed_reason||'无错误原因'],['执行说明',c.evidence_note],['已匹配估计能力',c.existing_estimation_adapter]]){
  let p=el('p');p.append(el('b',name+'：'),document.createTextNode(v));div.append(p);
 }}
function render(){let v=document.getElementById('search').value.toLowerCase().trim(),s=document.getElementById('status').value,r=document.getElementById('route').value;
 let rows=cards.filter(c=>{let hit=[c.case_id,c.business_question,c.observed_reason||'',c.target_class,c.l1_route].join(' ').toLowerCase().includes(v);
  if(s==='point'&&!c.l2_identification.startsWith('POINT'))hit=false;
  if(s==='blocked'&&c.l2_identification.startsWith('POINT'))hit=false;
  if(r!=='all' && !(c.l1_route||'').includes(r))hit=false;return hit;});
 const tb=document.getElementById('cards');tb.replaceChildren();
 for(let c of rows){let tr=el('tr');const values=[c.case_id,c.business_question,c.l0_target,c.l1_route,c.l2_identification,c.l3_estimation];
 values.forEach((v,i)=>{let td=el('td');if(i===4)td.append(el('span',v,'chip '+statusClass(v)));else td.textContent=v;tr.append(td);});tr.tabIndex=0;tr.addEventListener('click',()=>details(c));tr.addEventListener('keydown',ev=>{if(ev.key==='Enter')details(c);});tb.append(tr);}
 document.getElementById('visible').textContent=rows.length+' / '+cards.length+' 张卡';}
['search','status','route'].forEach(id=>document.getElementById(id).addEventListener('input',render));render();
for(const g of topo.graphs){let positive=g.design_exposure.filter(d=>d.status==='POINT_ARM_VERIFIED').length;
 let line=el('div',undefined,'barline');line.append(el('span',g.name));let bars=el('div',undefined,'bars');let ok=el('div',undefined,'bar');ok.style.width=positive/9*100+'%';bars.append(ok);
 let other=el('div',undefined,'bar invalid');other.style.width=(9-positive)/9*100+'%';bars.append(other);line.append(bars,el('span',positive+'/9'));document.getElementById('topbars').append(line);
 const pol=g.policy_offsupport;let row=el('div',undefined,'topology');row.append(el('span',g.name));row.append(el('span','R2: '+(pol.r2_status==='POINT'?'POINT / VERIFIED':pol.r2_reason),'chip '+(pol.r2_status==='POINT'?'good':'warn')));document.getElementById('policytop').append(row);
}
</script></body></html>'''.replace('__DATA_JSON__',safe)


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument('--output-dir',type=Path,default=Path('assets/business_coverage_fixtures'))
    args=p.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    coverage=run_business_coverage_v22()
    topology=run_topology_matrix()
    files={
        'CFM_ID_Business_Coverage_32_Cards.json':_json(coverage),
        'CFM_ID_v2_2_Cross_Topology_81_Cases.json':_json(topology),
        'CFM_ID_v2_2_Business_Coverage_Dashboard.html':_html(coverage,topology),
    }
    for filename,body in files.items():
        location=args.output_dir/filename
        location.write_text(body,encoding='utf-8')
        print(f'{filename} | {len(body.encode("utf-8"))} bytes | sha256={hashlib.sha256(body.encode()).hexdigest()}')
    print('32-card evidence:',coverage['counts'])
    print('9-topology × D/E evidence:',topology['status_counts'])
    print('NOTE: no numerical treatment-effect estimation or market-coverage claim.')


if __name__=='__main__':
    main()
