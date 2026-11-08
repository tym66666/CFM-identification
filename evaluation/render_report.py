"""Safe static HTML overview for the v0.4 benchmark report.

Escapes every model-supplied string, uses no JS/CDN, and prominently marks
fixture runs as NOT being real LLM evaluations.
"""
from __future__ import annotations
import argparse
from html import escape
import json
from pathlib import Path


def e(v):return escape(str(v), quote=True)


def render_html(report:dict)->str:
    if report.get('schema_version')!='cfm-id-evaluation-run-v0.4':
        raise ValueError('Not a v0.4 benchmark report')
    kind=report['run_kind']; is_real=kind=='REAL_API'
    title='真实模型候选评测' if is_real else '离线模拟通路验证'
    warning=('这是一份真实 API 输出的评测记录；标签匹配不代表数学证明已正确。'
             if is_real else '本次使用的是人工参考答案生成的离线模拟回复，尚未运行真实 LLM，不能用来评价模型准确率。')
    formula=report.get('summary',{}).get('formulation',{})
    cand=report.get('summary',{}).get('candidate',{})
    def stat(sub,caption):
        num=sub.get('schema_and_gate_accepted',0); den=sub.get('attempted',0)
        return f'<div class="stat"><strong>{e(num)} / {e(den)}</strong><span>{e(caption)}</span></div>'
    parts=[]
    for row in report['cases']:
        scores=row.get('score',{})
        if row['stage']=='formulation':
            unit=('三项字段一致' if scores.get('all_three_fields_match') else '需核查')
            evidence=('澄清判断一致' if scores.get('clarification_match') else '澄清判断有分歧')
        else:
            unit=('候选标签与参考一致' if scores.get('claim_match') else '候选标签不同/无输出')
            evidence='始终未认证' if scores.get('envelope_safe') else '无候选或需审查'
        parts.append('<tr>'+''.join('<td>'+e(s)+'</td>' for s in (
            row['id'],('业务理解' if row['stage']=='formulation' else '识别推理'),row['status'],unit,evidence,
            ', '.join(row.get('risk_tags',[])) or '—'))+'</tr>')
    cards=''
    if formula:cards+=stat(formula,'业务草稿通过输入格式和审查门禁（不是数学正确率）')
    if cand:cards+=stat(cand,'候选结果通过格式和安全审查（不是数学正确率）')
    return '''<!doctype html><html lang="zh"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CFM-ID Gateway v0.4 评测概览</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,'Noto Sans SC',sans-serif;color:#1c2834}
body{margin:0;background:#f3f5f8}main{max-width:1000px;margin:32px auto;padding:0 20px}
h1{font-size:25px;margin-bottom:8px}.sub{color:#617080;font-size:14px}
.warning{margin:25px 0 20px;background:#fff0d7;border-left:4px solid #c27b10;padding:16px 18px;border-radius:8px;font-weight:650}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.stat{background:#fff;border:1px solid #e3e7ed;border-radius:13px;padding:20px;display:flex;flex-direction:column;gap:8px}
.stat strong{font-size:27px;font-variant-numeric:tabular-nums}.stat span{font-size:13px;color:#576678}
section{background:white;border:1px solid #e3e7ed;border-radius:13px;padding:20px;margin-top:20px}
p,li{line-height:1.65;color:#405161}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;background:#f8fafc}
th,td{border-bottom:1px solid #e8ebf0;padding:10px;vertical-align:top}tbody tr:hover{background:#fcfdff}
footer{padding:20px 0;color:#617080;font-size:12px}
</style></head><body><main>
<h1>CFM-ID LLM Gateway · v0.4</h1>
<div class="sub">'''+e(title)+' · '+e(report.get('timestamp_utc',''))+' · '+e(report.get('model') or '无真实模型')+'''</div>
<div class="warning">'''+e(warning)+'''</div>
<div class="cards">'''+cards+'''</div>
<section><h2>这些检查到底测了什么？</h2>
<p><strong>业务理解：</strong>识别问题是 ATE、政策收益还是设计标准化 arm mean；认清随机分配协议及 A4 总体信息，缺失时询问。</p>
<p><strong>识别推理：</strong>在固定因果目标和假设的前提下，让模型提出候选公式、条件或反例。程序只检查格式与部分语义安全，不会冒充正式定理证明。</p>
<p><strong>数学可信度：</strong>要核对公式及观测等价反例，仍需独立数学检查和人工审阅；目前不生成正式 IdentificationResult 证书。</p></section>
<section><h2>每道题的运行情况</h2><div style="overflow-x:auto"><table><thead><tr><th>题目</th><th>类别</th><th>程序状态</th><th>与参考比较</th><th>审查保护</th><th>重点风险</th></tr></thead><tbody>'''+''.join(parts)+'''</tbody></table></div></section>
<footer>此 HTML 是评测摘要，不含敏感原始提示词或模型的完整因果推理。真正的数学细节请见 JSON 报告及人工审阅记录。</footer>
</main></body></html>'''


def main(argv=None):
    parser=argparse.ArgumentParser(description='Create static offline HTML for a v0.4 evaluation report')
    parser.add_argument('--report',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    report=json.loads(args.report.read_text(encoding='utf-8'))
    html=render_html(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(html,encoding='utf-8')
    print('Created',args.output)
    return 0


if __name__=='__main__':raise SystemExit(main())
