"""Generate a very small, offline, source-derived Golden Case ablation viewer.

No new theorem, no inference in JavaScript, no network requests.  Every status
comes from the public Python Core and has a locked test fixture.
"""
from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from examples.minimal_correct_core_golden import run_scenarios

HEAD = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Causal-IDFM · 最小正确识别 / 消融</title>
<style>
:root{color-scheme:light;--ink:#172a3a;--muted:#536777;--line:#d9e2e9;--paper:#f4f7fa;--green:#186b53;--red:#ad4a42;--amber:#925a17}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Noto Sans SC",sans-serif;background:var(--paper);color:var(--ink)}
main{max-width:960px;margin:auto;padding:28px 18px 46px}h1{font-size:1.7rem;letter-spacing:-.025em;margin:0 0 7px}h2{font-size:1.06rem;margin:0 0 14px}
p{line-height:1.62;margin:7px 0 12px}.sub{color:var(--muted);font-size:.93rem}.panel{border:1px solid var(--line);background:#fff;border-radius:13px;padding:20px;margin-top:16px}
.grid{display:grid;grid-template-columns:minmax(155px,1fr) minmax(160px,2fr);gap:14px;align-items:center}.graph{width:100%;max-height:132px}
button{background:white;border:1px solid #c9d7e2;border-radius:8px;padding:9px 13px;color:var(--ink);cursor:pointer;text-align:left;font-size:.86rem}
button[aria-pressed="true"]{border:2px solid #2a647e;background:#ebf4f8;font-weight:700;padding:8px 12px}
.choices{display:flex;flex-wrap:wrap;gap:7px}.status{font-weight:750;padding:5px 10px;border-radius:6px;background:#edf3f7;display:inline-block}.status.POINT{color:var(--green)}.status.NEEDS_INPUT{color:var(--amber)}.status.UNSUPPORTED{color:var(--red)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8fa;border-radius:9px;padding:12px;font-size:.84rem}
.pair{display:grid;grid-template-columns:150px 1fr;gap:8px 14px;margin:12px 0}.pair dt{color:var(--muted)}.pair dd{margin:0;font-weight:600;overflow-wrap:anywhere}
small{color:var(--muted)}@media(max-width:650px){.grid{grid-template-columns:1fr}.pair{grid-template-columns:1fr;gap:2px}}
</style></head><body><main>
<h1>一个最小问题，逐项消融</h1>
<p class="sub">Causal-IDFM · Golden Path · 离线数学演示（来自正式 Python Core；不是预测的实际销售额）</p>
<section class="panel"><h2>固定数学问题</h2><div class="grid"><svg class="graph" viewBox="0 0 300 115" aria-label="三节点路径图 0—1—2">
<line x1="52" y1="56" x2="150" y2="56" stroke="#98adbc" stroke-width="4"/><line x1="150" y1="56" x2="248" y2="56" stroke="#98adbc" stroke-width="4"/>
<circle cx="52" cy="56" r="23" fill="#236a80"/><circle cx="150" cy="56" r="23" fill="#236a80"/><circle cx="248" cy="56" r="23" fill="#236a80"/>
<text x="52" y="62" fill="white" text-anchor="middle" font-size="17">0</text><text x="150" y="62" fill="white" text-anchor="middle" font-size="17">1</text><text x="248" y="62" fill="white" text-anchor="middle" font-size="17">2</text></svg>
<div><strong>D2</strong>：三人中恰好两人接受处理，三种完整分配等概率。<br><strong>E1</strong>：处理前邻居严格多数。<br><strong>Target</strong>：节点 0 的设计标准化总体均值 μ₀ᑫ(1,1|W)。<br><strong>Oracle</strong>：原始完整分配独立穷举，正支持为 1/3。</div></div></section>
<section class="panel"><h2>仅改变一个因素</h2><div id="choices" class="choices" role="group" aria-label="选择消融方案"></div>
<p id="description" class="sub" aria-live="polite"></p>
<div><span class="status" id="status">读取结果...</span></div>
<dl class="pair"><dt>理论路线</dt><dd id="route"></dd><dt>精确支持 (oracle)</dt><dd id="support"></dd><dt>证书中的支持</dt><dd id="certificate"></dd><dt>独立 Replay</dt><dd id="replay"></dd><dt>安全拒绝原因</dt><dd id="reason"></dd><dt>Target 身份未变？</dt><dd id="target"></dd></dl>
<p class="sub">显示的是识别状态而非因果数值。UNSUPPORTED 不等于已经证明 NON-ID；缺 A4/A5 不能由 LLM 或样本统计自行填补。</p></section>
<section class="panel"><h2>唯一研发规则</h2>
<p>先在这个 3 节点问题上复现失败 → 每次只改一个条件 → 找到最小失败层 → 经独立 support/verifier 对拍 → 再去更大的网络测试。旧数学 Core 和已发布证书不因消融而被重写。</p>
<p class="sub">A0 / Estimation / PARTIAL 不在这个最小测试回路中；它们有各自的独立集成或研究测试。</p></section>
<small>数据由 Python identify_network_business_query() 和 replay_verified_business_outcome() 实际产生，前端不进行因果推理。</small>
<script type="application/json" id="data">__JSON_DATA__</script>
<script>
"use strict";
const doc=JSON.parse(document.getElementById('data').textContent);
const descriptions={base:'完整 A4/A5/A6，D2×E1：应 POINT 且能重放',missing_a4:'只删除 typed 总体 A4 算子，变量名称仍存在',a4_not_admitted:'只把 A4 来源改为尚未批准',a5_unresolved:'只把完整向量随机化假设改为待确认',a5_rejected:'只把完整向量随机化假设改为明确不接受',zero_quota:'只把固定处理配额从 2 改成 1',add_network_edge:'只增加网络边 (0,2)，形成三角形',different_exposure:'只把 E1 改成 E2，目标曝光状态按 E2 定义',query_not_confirmed:'只将查询授权标记为 PROPOSED'};
const choices=document.getElementById('choices');
function val(id,v){document.getElementById(id).textContent=String(v===null?'—':v)}
function show(i){const r=doc.scenarios[i];
 for(const b of choices.children)b.setAttribute('aria-pressed',String(+b.dataset.index===i));
 val('description',descriptions[r.change]||r.change);val('route',r.route);val('support',r.exact_support_oracle);
 val('certificate',r.certified_support);val('replay',r.replay_verified?'VERIFIED':'未执行（非 POINT）');
 val('reason',r.reason_code);val('target',r.same_target_as_base?'是':'否');
 const stat=document.getElementById('status');stat.textContent=r.status;stat.className='status '+r.status;
}
doc.scenarios.forEach((r,i)=>{const b=document.createElement('button');b.type='button';b.dataset.index=i;
b.textContent=(i+1)+'. '+({base:'Base 完整',missing_a4:'撤去 A4',a4_not_admitted:'A4 未批准',a5_unresolved:'A5 待确认',a5_rejected:'A5 否认',zero_quota:'减少处理配额',add_network_edge:'增加一条边',different_exposure:'E1 → E2',query_not_confirmed:'查询未审核'}[r.change]||r.change);
b.setAttribute('aria-pressed','false');b.addEventListener('click',()=>show(i));choices.appendChild(b)});
show(0);
</script></main></body></html>
'''


def build() -> str:
    data = json.dumps(run_scenarios(), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    # Prevent embedded script tags from breaking out in any future data extension.
    return HEAD.replace('__JSON_DATA__', data.replace('<', '\\u003c').replace('>', '\\u003e'))


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', default='assets/minimal_core_fixtures/CFM_ID_Minimal_Golden_Ablation.html')
    args=parser.parse_args(argv)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(build(),encoding='utf-8')
    print(dest)
    return 0


if __name__=='__main__':raise SystemExit(main())
