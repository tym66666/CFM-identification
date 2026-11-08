"""Offline static candidate dashboard; all data are mock, no external resources."""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def render(output: Path | None=None) -> Path:
    demo=ROOT/'assets/candidate_mock_fixtures'
    case=json.loads((demo/'business_case.json').read_text(encoding='utf-8'))
    rep=json.loads((demo/'mock_candidate_report.json').read_text(encoding='utf-8'))
    q1,q2=rep['results']
    candidate=q2.get('candidate') or {}
    proposal=candidate.get('proposal') or {}
    reqs=proposal.get('additional_requirements') or []
    quote=lambda s:html.escape(str(s),quote=True)
    refs=''.join(f'<li><b>{quote(r["kind"])}</b> · {quote(r["description"])}</li>' for r in reqs)
    markup=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFM-ID LLM Gateway v0.11 — Identification Candidate</title>
<style>body{{margin:0;background:#f5f7fb;color:#14233d;font:16px/1.6 system-ui,-apple-system,"Noto Sans SC",sans-serif}}header{{background:#122541;color:white;padding:36px 22px}}main{{max-width:1000px;margin:auto;padding:24px}}h1{{margin:0 0 10px;font-size:29px}}h2{{font-size:21px}}.sub{{color:#cbd6ea}}.pane{{background:white;border:1px solid #dce2ee;border-radius:14px;padding:22px;margin:18px 0;box-shadow:0 4px 15px #1225410c}}.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.status{{display:inline-block;padding:4px 10px;border-radius:15px;background:#edf1f8;color:#243b60;font-size:13px;font-weight:650}}.accent{{border-left:4px solid #3875dc}}code,pre{{font:13px/1.5 ui-monospace,Consolas,monospace}}pre{{overflow:auto;white-space:pre-wrap;background:#f1f4fa;padding:14px;border-radius:8px}}small{{color:#66758c}}.warn{{background:#fff4dc;border:1px solid #ecd392;padding:14px;border-radius:10px}}@media(max-width:700px){{.cols{{grid-template-columns:1fr}}}}a{{color:#315da5}}</style></head><body>
<header><main style="padding:0"><h1>Identification Candidate Reasoner · v0.11</h1><div class="sub">业务规范化完成后，严格数学库未覆盖时的探索性推导模块</div></main></header><main>
<div class="warn"><b>离线 Mock 演示</b>：此页面未调用真实 LLM 或数学 Core；不代表 R1a/R1b/R2/R3 真的未覆盖，也不证明候选公式正确。</div>
<section class="pane"><h2>企业提交的问题</h2><p>{quote(case['business_question'])}</p><small>来源：业务叙述、实验方案与有限业务数据字典。当前缺少正式总体 A4 信息及真实数学审批。</small></section>
<div class="cols"><section class="pane"><h2>q1 · 全员推广政策</h2><span class="status">{quote(q1['status'])}</span><p>Mock 数学结果设定为已有路线，不允许 Candidate LLM 重复输出。</p><small>原因：{quote(q1['reason_code'])}</small></section>
<section class="pane accent"><h2>q2 · 同事间影响</h2><span class="status">{quote(q2['status'])}</span><p>Mock 指定软件覆盖缺口，因此允许 LLM 提出候选思路，仍需后续证明。</p><small>模式：{quote(q2['mode'])}</small></section></div>
<section class="pane"><h2>q2 的候选数学分析（未经认证）</h2><p><b>候选声明：</b>{quote(proposal.get('claimed_identification',''))}，但条件范围为 {quote(proposal.get('scope',''))}</p>
<p><b>候选表达式（不等于经过检验的定理）：</b></p><pre>{quote(proposal.get('candidate_expression'))}</pre><h3>提出的新条件</h3><ul>{refs}</ul><h3>研究者下一步检查</h3><ol>{''.join('<li>'+quote(x)+'</li>' for x in candidate.get('proposed_validation_checks',[]))}</ol></section>
<section class="pane"><h2>三个不能混淆的结果</h2><p><b>业务规范化完成</b>不等于科学假设有效；<b>软件 UNSUPPORTED</b>不等于数学不可识别；<b>候选识别公式</b>不等于证书。</p><p><small>verification_level={quote(q2['verification_level'])} · estimation_handoff_allowed={quote(q2['estimation_handoff_allowed'])} · mathematical_certificate={quote(q2['mathematical_certificate'])}</small></p></section>
</main></body></html>'''
    path=output or (demo/'candidate_reasoner_walkthrough_MOCK.html')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(markup,encoding='utf-8')
    return path

if __name__=='__main__':
    print(render())
