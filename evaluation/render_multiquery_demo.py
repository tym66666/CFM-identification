"""Offline static HTML for a natural business + documents multiquery example.

Uses explicitly prepared mock model output. Never implies mathematical certification.
"""
from __future__ import annotations
import argparse
from html import escape
from pathlib import Path
import json

from cfm_id_llm.material_integrity import create_grounded_intake, review_grounded_intake
from cfm_id_llm.multisource_intake_cli import _load_manifest
from cfm_id_llm.multiquery_formulator import MultiQueryFormulatorV09
from cfm_id_llm.providers import MockProvider

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'examples/multisource/case.json'
FIXTURE = ROOT / 'examples/multisource/mock_multiquery.json'


def render_html(*, manifest: Path = MANIFEST, fixture: Path = FIXTURE) -> tuple[str, dict]:
    case_id, question, lang, files = _load_manifest(manifest)
    intake = create_grounded_intake(case_id=case_id, business_question=question,
                                    attachments=files, response_language=lang)
    mock = MockProvider(json.loads(fixture.read_text(encoding='utf-8')))
    report = MultiQueryFormulatorV09(mock).formulate(intake.case)
    material = review_grounded_intake(intake, report.primary_formulation)
    box_queries = ''
    audits = {q.query_id: a for q, a in zip(report.draft.queries, report.query_audits)}
    for q in report.draft.queries:
        a = audits[q.query_id]
        display = escape(q.business_goal.value or '待确认')
        kind = escape(q.target.kind.value)
        notes = (f'还有 {len(a.issues)} 项需要核对' if a.issues else '仍需研究者确认业务语义')
        box_queries += f'''<article class="query">
<h3>{escape(q.query_id)} · {display}</h3>
<p><span class="tag">{kind}</span><span class="tag subtle">未认证</span></p>
<p class="muted">{escape(notes)}。这里不是销售效果数值，也不是因果识别结论。</p>
</article>'''
    attachment_rows = ''.join(f'<li>{escape(x.display_name)} <small>· {escape(x.mode)}</small></li>' for x in intake.attachments)
    warnings = ''.join(f'<li>{escape(x.explanation)}</li>' for x in material.findings)
    if not warnings:
        warnings = '<li>自动审查未发现已知高风险资料冲突；不代表资料已经科学认证。</li>'
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>CFM-ID Gateway v0.9 多查询业务示例（离线 Mock）</title>
<style>body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#f5f7fb;color:#192330;line-height:1.7}}
main{{max-width:940px;margin:36px auto;padding:0 20px 40px}}h1{{font-size:1.85rem}}h2{{font-size:1.25rem;margin-top:0}}
section{{background:white;border:1px solid #e2e6ee;border-radius:16px;padding:24px;margin:16px 0}}
.meta{{color:#586577}}.notice{{border-left:4px solid #6376a0;background:#eef2fa;padding:14px 18px;border-radius:8px}}
.query{{border:1px solid #e1e7f0;border-radius:12px;padding:16px;margin:14px 0}}.query h3{{margin:0;font-size:1.06rem}}
.tag{{display:inline-block;padding:1px 9px;background:#e7ecf5;color:#263d60;border-radius:8px;font-size:.83rem;margin-right:7px}}
.tag.subtle{{background:#f1f2f5;color:#555}}.muted,small{{color:#667281}}ul{{padding-left:20px}}</style></head>
<body><main><h1>一家公司的业务问题，可能包含多个因果查询</h1>
<p class="meta">CFM-ID-LLM Gateway v0.9.0 · 离线 Mock 演示 · 未调用真实 LLM / Identification / Estimation</p>
<section><h2>业务人员提交了什么？</h2><p>{escape(question)}</p><strong>配套文件</strong><ul>{attachment_rows}</ul></section>
<section><h2>Gateway 在后台整理成什么？</h2>
<p>同一批资料只读一次，得到 {len(report.draft.queries)} 个候选因果目标。它们共享员工、处理、结果和协议信息，但目标各不相同。</p>
{box_queries}</section>
<section><h2>系统暂时不能做什么？</h2><div class="notice">这些是待确认的数学问题草稿，不是 POINT 识别认证，也没有预测实际业绩。A4 总体信息、A5 因果假设与各目标的必要条件，仍由专家或正式数学库进一步审查。</div>
<h3>资料质量提示</h3><ul>{warnings}</ul></section>
<section><h2>下一步</h2><p>专家确认真实问题和必要假设后，未来可将不同查询分别交给最新版 Identification Library；库未覆盖的查询才进入明确标注的 LLM 候选分析。</p></section>
</main></body></html>'''
    meta = {'case_id':report.case_id,'mode':'MOCK_FIXTURE_ONLY','query_count':len(report.draft.queries),
            'queries': [{'query_id': q.query_id, 'kind':q.target.kind.value,
                         'goal':q.business_goal.value} for q in report.draft.queries],
            'mathematical_verification':report.mathematical_verification,
            'document_quality_decision':material.decision, 'estimated_results':False}
    return html, meta


def main(argv=None):
    p=argparse.ArgumentParser(description='Render multiquery offline business example')
    p.add_argument('--html',default='demo_v09/multiquery_sales_MOCK.html')
    p.add_argument('--json',default='demo_v09/multiquery_sales_MOCK.json')
    args=p.parse_args(argv)
    html, meta=render_html()
    Path(args.html).parent.mkdir(parents=True,exist_ok=True)
    Path(args.json).parent.mkdir(parents=True,exist_ok=True)
    Path(args.html).write_text(html,encoding='utf-8')
    Path(args.json).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
