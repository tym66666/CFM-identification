"""Offline, authored-fixture evaluation of v0.8 document grounding.

NOT an online LLM accuracy benchmark. Expected labels are authored by the
project, and the model replies are authored Mock outputs. The pass rate measures
end-to-end software behavior and material-gate consistency only.
"""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path

from cfm_id_llm.formulator import ProblemFormulator
from cfm_id_llm.material_integrity import (
    PROMPT_VERSION_V08, create_grounded_intake, review_grounded_intake,
)
from cfm_id_llm.multisource_intake_cli import _load_manifest
from cfm_id_llm.multisource_cli import SYSTEM_PROMPT_V08
from cfm_id_llm.providers import MockProvider

FIXTURE_DIR = Path(__file__).resolve().parent/'packets'


def evaluate_packets(base: Path = FIXTURE_DIR) -> dict:
    rows=[]
    for directory in sorted(p for p in base.iterdir() if p.is_dir() and (p/'case.json').exists()):
        case_id, question, language, attachments = _load_manifest(directory/'case.json')
        intake=create_grounded_intake(case_id=case_id,business_question=question,
                                      response_language=language,attachments=attachments)
        raw=json.loads((directory/'mock_draft.json').read_text(encoding='utf-8'))
        expected=json.loads((directory/'expected.json').read_text(encoding='utf-8'))
        form=ProblemFormulator(MockProvider(raw),system_prompt=SYSTEM_PROMPT_V08,
                               prompt_version=PROMPT_VERSION_V08).formulate(intake.case)
        q=review_grounded_intake(intake,form)
        codes={f.code for f in q.findings}
        ok=(form.draft.target.kind.value==expected['target_kind'] and
            form.draft.information_design.assignment_family.value==expected['assignment_family'] and
            set(expected['expected_quality_codes']).issubset(codes) and
            not q.estimation_handoff_allowed and
            q.mathematical_verification=='NOT_PERFORMED')
        rows.append(dict(case_id=case_id, industry=directory.name,
                         expected_target=expected['target_kind'],
                         mock_target=form.draft.target.kind.value,
                         expected_design=expected['assignment_family'],
                         mock_design=form.draft.information_design.assignment_family.value,
                         expected_quality_codes=expected['expected_quality_codes'],
                         actual_quality_codes=sorted(codes),
                         decision=q.decision,format_and_gate_pass=ok,
                         online_llm_called=False,math_verified=False))
    return dict(benchmark='CFM-ID realistic business document packets v0.8',
                evidence_kind='AUTHORED_MOCK_FIXTURES_NOT_ONLINE_LLM_ACCURACY',
                cases=len(rows),software_checks_pass=sum(x['format_and_gate_pass'] for x in rows),
                real_llm_calls=0,mathematical_certificates=0,rows=rows)


def render_html(report: dict) -> str:
    body=[]
    for x in report['rows']:
        success='通过' if x['format_and_gate_pass'] else '需要修复'
        detail='；'.join(x['actual_quality_codes']) or '未发现已知材料风险'
        body.append('<tr><td>'+html.escape(x['industry'])+'</td><td>'+html.escape(x['expected_target'])+
                    '</td><td>'+html.escape(x['mock_design'])+'</td><td>'+html.escape(detail)+
                    '</td><td>'+html.escape(success)+'</td></tr>')
    return '''<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>CFM-ID v0.8 业务资料评测</title>
<style>body{font-family:system-ui,-apple-system,Arial,sans-serif;color:#18243b;background:#f5f7fc;padding:36px;max-width:1150px;margin:auto}h1{margin-bottom:8px}p{line-height:1.7}table{border-collapse:collapse;width:100%;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 18px #091a3720}th,td{padding:14px;text-align:left;border-bottom:1px solid #e7edf5;vertical-align:top}th{background:#e8edf8;color:#24385e}.pill{display:inline-block;padding:6px 10px;background:#e9edf5;border-radius:30px;font-size:12px}.metrics{display:flex;gap:12px;flex-wrap:wrap}.metrics div{background:white;padding:16px 20px;border-radius:12px;margin:12px 0}</style></head><body>
<h1>业务资料 → 因果问题草稿：离线质量检查</h1>
<p class="pill">这是 Mock 资料与人工编写草稿的流程测试，不是在线 LLM 正确率，也不是因果数学认证。</p>
<div class="metrics"><div>业务资料包：<strong>'''+str(report['cases'])+'''</strong></div><div>软件检查通过：<strong>'''+str(report['software_checks_pass'])+'''</strong></div><div>真实 LLM 调用：<strong>0</strong></div><div>数学识别证书：<strong>0</strong></div></div>
<p>每个业务包包含自然语言业务说明及 2–4 份支持文件。程序检查的是附件读取、原文引用、冲突警示、安全隔离，以及不把文件字段当成因果证明。</p>
<table><thead><tr><th>场景</th><th>业务目标类别（草稿）</th><th>处理分配描述</th><th>材料风险提示</th><th>软件检查</th></tr></thead><tbody>'''+''.join(body)+'''</tbody></table>
<p>下一步：接入真实模型后，用独立人工复核记录目标理解错误、假设编造和 A4 误用；不能用 Mock 测试通过率代替真实识别能力。</p></body></html>'''


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description='Offline business packet software check (not model accuracy)')
    p.add_argument('--cases-dir',type=Path,default=FIXTURE_DIR)
    p.add_argument('--output',type=Path)
    p.add_argument('--html',type=Path)
    p.add_argument('--list',action='store_true')
    args=p.parse_args(argv)
    if args.list:
        print('\n'.join(p.name for p in sorted(args.cases_dir.iterdir()) if (p/'case.json').exists()))
        return 0
    report=evaluate_packets(args.cases_dir)
    output=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(output+'\n',encoding='utf-8')
    else:
        print(output)
    if args.html:
        args.html.write_text(render_html(report),encoding='utf-8')
    return 0 if report['software_checks_pass']==report['cases'] else 1


if __name__=='__main__':
    raise SystemExit(main())
