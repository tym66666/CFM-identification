"""Static offline explainer. Escapes all business strings; no math certification."""
from __future__ import annotations

import html
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def render(before_after: dict, exercises: dict) -> str:
    esc=lambda x: html.escape(str(x), quote=True)
    rows=''.join(
        '<tr><td>'+esc(r['id'])+'</td><td>'+esc(r['question'])+'</td><td>'+esc(r['my_selected_target'])+'</td></tr>'
        for r in exercises['results']
    )
    q=''.join('<li>'+esc(x)+'</li>' for x in before_after['pending_business_questions'])
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CFM-ID v0.6 业务规范化演示</title><style>
:root{color-scheme:light}body{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;margin:0;background:#f5f7fa;color:#172334;line-height:1.68}
main{max-width:900px;margin:auto;padding:36px 20px 70px}.box{background:white;border:1px solid #dce3ec;border-radius:14px;padding:22px;margin:16px 0}
section{margin:28px 0}h1{font-size:26px}h2{font-size:21px}h3{font-size:16px}small,.muted{color:#5d6877}
.tag{display:inline-block;padding:4px 10px;border-radius:100px;background:#f0f3f7;color:#314159;font-size:13px}
strong{font-weight:650}.arrow{text-align:center;color:#65748a;font-size:22px}.layout{display:grid;grid-template-columns:1fr 1fr;gap:12px}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e5eaf0;text-align:left;padding:10px;vertical-align:top;font-size:14px}th{background:#f5f7fa}
@media(max-width:650px){.layout{grid-template-columns:1fr}}
</style></head><body><main>
<h1>业务自然语言 → 规范化因果问题</h1>
<p>CFM-ID-LLM-Gateway v0.6 · 离线 Mock 与我自己编写的示范。<strong>不是在线 LLM 准确率、不是数学识别证书。</strong></p>
<section><h2>案例：300 名销售员，随机给一半人开通 AI</h2><div class="layout">
<div class="box"><span class="tag">第一次整理</span><h3>随机方式还不清楚</h3><p>系统不能仅凭“随机一半”就认定是独立抛硬币还是固定抽选。</p><strong>分配方式：</strong>'''+esc(before_after['initial_assignment'])+'''</div>
<div class="box"><span class="tag">向业务人员追问</span><h3>'''+esc(before_after['user_question'])+'''</h3><p>'''+esc(before_after['user_answer'])+'''</p></div></div>
<div class="arrow">↓ 重新让 LLM 规范化，按原文引用审核 ↓</div>
<div class="box"><span class="tag">第二次整理</span><h3>得到用户报告的分配方式</h3>
<p><strong>分配方式：</strong>'''+esc(before_after['revised_assignment'])+'''（来自补充回答，<strong>尚未科学认证</strong>）</p>
<p><strong>A4 总体可观测信息：</strong>'''+esc(before_after['population_information_level'])+'''</p>
<p><strong>还要继续确认：</strong></p><ul>'''+q+'''</ul>
<small>本次仍未运行严格识别定理，没有计算销售收益，也不允许交给 Estimation。</small></div></section>
<section><h2>8 个业务问题的自写规范化示范</h2><p class="muted">由当前 ChatGPT 逐项编写候选解读，程序核对结构及原文引用。撰写者看过开发参考提示，因此不属于独立准确率评测。</p>
<div class="box"><table><thead><tr><th>编号</th><th>用户实际提问</th><th>我提出的目标类型</th></tr></thead><tbody>'''+rows+'''</tbody></table></div></section>
<div class="box"><h2>最后的边界</h2><p>规范化不等于因果识别，引用到业务原话不等于接受因果假设。未来接入最新 Identification Library 后，仍需要通过正式 A4/A5/A6 和数学证明验证。</p></div>
</main></body></html>'''

def main(argv=None):
    import argparse
    from .demo_clarification import execute
    from .self_probe import run
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args(argv)
    Path(a.output).write_text(render(execute(),run()),encoding='utf-8')
    print(a.output)

if __name__=='__main__':
    main()
