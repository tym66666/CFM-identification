"""Render the v0.7 offline, MOCK-ONLY business+files walkthrough to a local HTML.
Do not interpret MOCK fixtures as real LLM accuracy, causal identification or ROI.
"""
from __future__ import annotations
import argparse
from html import escape
import json
from pathlib import Path
from cfm_id_llm.document_intake import IntakeReportV07
from cfm_id_llm.multisource_normalization import MultisourceReviewV07


def html_preview(review: MultisourceReviewV07) -> str:
    d=review.formulation.draft
    e=lambda v: escape(str(v or '尚待确认'))
    files=''.join(
        '<div class="file"><div class="fn">'+e(a.display_name)+'</div>'
        '<div class="sub">'+e(a.suffix.upper())+' · '+e(a.mode)+'</div></div>'
        for a in review.intake.attachments)
    if review.essential_business_questions:
        next_text='只需再确认：'+' / '.join(e(x) for x in review.essential_business_questions)
    else:
        next_text='无需重复填写已在附件说明的事实；下一步由研究者确认假设及总体信息。'
    notes=''.join('<li>'+e(x)+'</li>' for x in review.research_review_notes[:7])
    assignment_quote = d.information_design.assignment_law.evidence
    source = ('“'+e(assignment_quote[0].quote)+'” · '+e(assignment_quote[0].source_id)) if assignment_quote else '无来源'
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CFM-ID 多文件业务规范化（离线 Mock）</title>
<style>:root{{font-family:system-ui,-apple-system,"Microsoft Yahei",sans-serif;color:#12202d;background:#f7f9fc}}
body{{max-width:1040px;margin:0 auto;padding:38px 25px 60px;line-height:1.65}}h1{{font-size:28px;margin:5px 0 5px}}h2{{font-size:18px;margin:0 0 12px}}p{{margin:6px 0}}.muted{{color:#5b6674;font-size:14px}}.pill{{display:inline-block;border-radius:30px;padding:3px 12px;background:#ebf0f7;font-size:12px}}
.card{{background:white;border:1px solid #dce3ed;border-radius:14px;padding:22px;margin:15px 0;box-shadow:0 2px 10px #12202d07}}.columns{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}.file{{background:#f7f9fc;border:1px solid #e5eaf0;padding:12px;border-radius:10px;margin:8px 0}}.fn{{font-weight:650}}.sub{{font-size:12px;color:#586574}}dl{{display:grid;grid-template-columns:160px 1fr;gap:11px}}dt{{color:#586574}}dd{{margin:0;font-weight:550}}blockquote{{margin:10px 0;border-left:3px solid #7b98bd;padding-left:12px;color:#304157}}li{{margin:4px 0}}@media(max-width:640px){{.columns{{grid-template-columns:1fr}}dl{{grid-template-columns:1fr;gap:2px}}}}</style></head><body>
<span class="pill">OFFLINE MOCK · 不是线上模型成绩</span><h1>CFM-ID：从业务材料到因果问题草稿</h1>
<p class="muted">用户不需要手填 JSON。系统先综合业务说明与文件，再决定要不要追问。</p>
<div class="card"><h2>1. 业务负责人提交的问题</h2><p>{e(review.intake.case.business_question)}</p></div>
<div class="card"><h2>2. 同时提供的 {len(review.intake.attachments)} 份文件</h2><div class="columns">{files}</div>
<p class="muted">CSV / Excel 默认只读字段结构和行数，不向 LLM 发送个人记录。</p></div>
<div class="card"><h2>3. 系统整理出的因果问题（草稿）</h2>
<dl><dt>最主要的业务目标</dt><dd>{e(d.target.description.value)}</dd>
<dt>研究对象</dt><dd>{e(d.units_variables.analysis_unit.value)}</dd>
<dt>干预措施</dt><dd>{e(d.units_variables.treatment.value)}</dd>
<dt>结果指标</dt><dd>{e(d.units_variables.outcome.value)}</dd>
<dt>分配方式</dt><dd>{e(d.information_design.assignment_family.value)}</dd></dl>
<h2 style="margin-top:18px">为什么理解成这个分配方式？</h2><blockquote>{source}</blockquote>
<p class="muted">引文能核实材料中的表述，不等于独立证明现实随机化过程真正按此执行。</p></div>
<div class="card"><h2>4. 目前应该怎么继续？</h2><p>{next_text}</p><details style="margin-top:12px"><summary>展开研究者需要检查的条件</summary><ul>{notes}</ul></details></div>
<div class="card"><h2>哪些事情还没有做？</h2><p>没有运行正式 Identification 定理；没有估计实际销售收益；没有向 Policy 交付因果效果。</p>
<p class="muted">参考代码版本：LLM Gateway v0.7.0；数学识别库独立开发中。</p></div>
</body></html>'''


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--report',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args(argv)
    review=MultisourceReviewV07.model_validate_json(Path(args.report).read_text(encoding='utf-8'))
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(html_preview(review),encoding='utf-8')
    print(f'Written: {args.output}')


if __name__=='__main__':
    main()
