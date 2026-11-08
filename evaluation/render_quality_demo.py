"""Render a STATIC offline MOCK demonstration of v0.10 business/science separation."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import json

from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality_formulator import A0QualityFormulatorV010
from cfm_id_llm.schemas import BusinessCase


ROOT=Path(__file__).resolve().parents[1]


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--html',default=str(ROOT/'demo_v010/a0_quality_walkthrough_MOCK.html'))
    ap.add_argument('--json',default=str(ROOT/'demo_v010/a0_quality_walkthrough_MOCK.json'))
    args=ap.parse_args(argv)
    case=BusinessCase.model_validate_json((ROOT/'examples/quality/sales_business_case.json').read_text(encoding='utf-8'))
    response=json.loads((ROOT/'examples/quality/mock_multiquery_v010.json').read_text(encoding='utf-8'))
    report=A0QualityFormulatorV010(MockProvider(response)).formulate(case)
    cards=[]
    for q,review in zip(report.draft.queries,report.query_quality):
        scientific=''.join(f'<li>{escape(a.detail)}</li>' for a in review.actions if a.owner=='SCIENTIFIC_REVIEWER')
        values=[]
        for key in ('intervention','comparator','neighbor_exposure','aggregation','policy_assignment'):
            v=getattr(q.semantics,key)
            values.append('<div class="field"><span>'+escape(key)+'</span><b>'+
                    escape(v.value if v.value is not None else '待确认 / UNRESOLVED')+'</b></div>')
        cards.append('''<article><div class="eyebrow">{id} · {kind}</div><h3>{title}</h3>
        <div class="status">{status}</div><div class="fields">{values}</div>
        <div class="foot">数学条件仍需研究者审核{scientific}</div></article>'''.format(
            id=escape(q.query_id),kind=escape(q.target.kind.value),
            title=escape(q.business_goal.value or ''),status=escape(review.business_status),
            values=''.join(values), scientific=('<ul>'+scientific+'</ul>' if scientific else '')))
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CFM-ID Gateway v0.10 · 业务规范化质量演示（Mock）</title>
<style>body{font-family:system-ui,-apple-system,"Noto Sans CJK SC",sans-serif;margin:0;background:#f8f9fb;color:#1c2734;line-height:1.5}
.wrap{max-width:1080px;margin:auto;padding:36px 24px 80px}h1{font-size:28px;margin:6px 0 12px}
h2{font-size:21px;margin-top:38px}.eyebrow{color:#59718c;font-size:12px;letter-spacing:.09em;font-weight:700;text-transform:uppercase}
.lead{font-size:17px;max-width:750px}.notice{border:1px solid #c5d0dd;background:#fff;padding:14px 18px;border-radius:10px;color:#344b63}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px;margin-top:22px}
article{background:white;border:1px solid #d9e0e8;border-radius:14px;padding:22px;box-shadow:0 4px 14px #18253608}
article h3{font-size:19px;min-height:55px}.status{display:inline-block;border:1px solid #9bd4ae;color:#23603e;background:#eefaf0;padding:5px 10px;border-radius:999px;font-size:12px;font-weight:bold}
.fields{margin-top:17px}.field{border-top:1px solid #eef1f5;padding:10px 0;display:flex;justify-content:space-between;gap:24px;font-size:13px}
.field span{color:#59718c;min-width:120px}.field b{text-align:right;max-width:400px;font-weight:500}
.foot{background:#f4f6f9;border-radius:9px;padding:13px 16px;margin-top:15px;font-size:12px;color:#3d4c5d}
.foot ul{padding-left:20px;margin-bottom:0}.meta{display:flex;gap:12px;flex-wrap:wrap;margin:15px 0}
.kpi{background:white;border:1px solid #d9e0e8;padding:14px 18px;border-radius:9px;min-width:120px}
.kpi b{display:block;font-size:19px}.kpi small{color:#678}.subtle{font-size:13px;color:#687a8e}
</style><div class="wrap">
<div class="eyebrow">CFM-ID · STANDALONE LLM GATEWAY · v0.10.0</div>
<h1>同一批业务资料，两个独立的因果问题</h1>
<p class="lead">用户无需知道 A4/A5。模型先整理业务语义；缺少严格数学条件时，问题应交给研究者，而不是要求业务人员补充专业证明。</p>
<div class="notice"><b>离线人工 Mock 演示：</b>以下并非真实线上大模型成绩，也没有数学 POINT 或证书。本页面展示软件接口与审查结果。</div>
<div class="meta"><div class="kpi"><b>2</b><small>业务因果查询</small></div><div class="kpi"><b>FORMALIZATION_READY</b><small>业务规范化状态</small></div><div class="kpi"><b>REVIEW REQUIRED</b><small>独立科学审核</small></div></div>
<h2>公司提出的业务问题</h2><div class="notice">{question}</div>
<h2>规范化后的独立查询草稿</h2><div class="grid">{cards}</div>
<h2>为什么这不会直接产生 POINT？</h2><p>虽然处理分配方案已由实验说明描述，仍缺少正式总体 A4 信息和独立 A5 假设许可；效应对照、暴露和精确政策坐标还需要研究者核对。该版本完全不导入数学 Core。</p>
<div class="subtle">Source: examples/quality/* · Rendered from v0.10 programmatic audit. NBIB benchmarking is separate.</div></div></html>'''.replace('{question}',escape(case.business_question)).replace('{cards}',''.join(cards))
    htmlpath=Path(args.html); htmlpath.parent.mkdir(parents=True,exist_ok=True)
    htmlpath.write_text(html,encoding='utf-8')
    jsonpath=Path(args.json);jsonpath.parent.mkdir(parents=True,exist_ok=True)
    jsonpath.write_text(report.model_dump_json(indent=2)+'\n',encoding='utf-8')
    print('MOCK A0 v0.10 preview:',htmlpath,'→',report.overall_business_status)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
