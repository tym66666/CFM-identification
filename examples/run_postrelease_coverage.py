"""Post-v2.7 P0: rerun 48 legacy fixtures and 11 live D6 queries.

The denominator is a hand-picked research benchmark, NOT real-world coverage.
No identification equation becomes an empirical effect estimate.

    python -B -m examples.run_postrelease_coverage --output-dir showcase_v27_postrelease
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
from html import escape
import argparse
import csv
import io
import json
from pathlib import Path

from examples.run_coverage_route_closeout import build_coverage_matrix
from examples.run_two_stage import build_data as build_d6
from pfn_pipeline.identification_assumption_inventory import (
    implemented_assumption_catalog_v27, requirements_for_route_v27,
)

STEM = 'CFM_ID_v2_7_Postrelease_59_Case_Assumptions_and_Coverage'


def build_postrelease_matrix() -> dict:
    with redirect_stdout(io.StringIO()):
        prev = build_coverage_matrix()
        d6 = build_d6()
    if prev['case_total'] != 48 or d6['case_count'] != 11:
        raise AssertionError('Exact 48+11 frozen synthetic fixture count required')
    old = []
    for c in prev['cards']:
        old.append({**c, 'report_epoch':'v2.7-postrelease',
                    'fixture_origin':c['introduced_in'],
                    'evidence_scope':'REEXECUTED_HISTORICAL_FIXTURE_WITH_v2.7_CODE__NOT_ALL_NEW_ROUTES_TRIED',
                    'adapter_status': 'NO_ADAPTER_CERTIFIED_FOR_THIS_CASE',
                    'numeric_business_value':None})
    new = []
    for c in d6['cases']:
        route = c['route']
        requirements = (requirements_for_route_v27(
            route, design_kind='two_stage_quota_mixture_binary_v2_7') if route else None)
        if c['status']=='POINT' and (not c['theorem_verified'] or requirements is None):
            raise AssertionError('D6 POINT without verified theorem route')
        new.append(dict(case_id=c['id'],business_question=c['title'],
                fixture_origin='v2.7',report_epoch='v2.7-postrelease',
                evidence_scope='LIVE_V27_D6_FORMAL_API_AND_REPLAY',
                l0_target=c['query_type'], l1_route=route or 'BLOCKED',
                l2_identification=c['status'],l3_estimation='NO_NUMERIC_ESTIMATOR' if c['status']=='POINT' else 'NOT_APPLICABLE',
                a4= c['information'],
                a5='D6 base randomized A5 plus explicit profile-exclusion; R2 additionally requires mean-signature sufficiency',
                a6=f"exact allocation/signature support: {c['exact_support']}; only successful query cells", 
                reason=c['reason'],evidence_type='LIVE_FORMAL_D6_THEOREM_REPLAY_OR_SAFE_REFUSAL',
                adapter_status='NO_ADAPTER_CERTIFIED_FOR_THIS_CASE', numeric_business_value=None,
                assumption_requirements=requirements,
                d6_details={k:c[k] for k in ('size','exposure','policy','notes')},
                note='Hypothetical A4/A5 accepted only for synthetic example; no empirical causal effect value'))
    rows = old+new
    if len(rows)!=59 or len({r['case_id'] for r in rows})!=59:
        raise AssertionError('Duplicate or missing case IDs')
    normalized = Counter('POINT' if r['l2_identification'].startswith('POINT') else
        ('NEEDS_INPUT' if r['l2_identification']=='NEEDS_INPUT' else 'BLOCKED_OR_TARGET_GAP') for r in rows)
    expected = {'POINT':33,'NEEDS_INPUT':9,'BLOCKED_OR_TARGET_GAP':17}
    if dict(normalized)!=expected:
        raise AssertionError(f'Expected {expected}, observed {dict(normalized)}')
    return {
      'baseline':'v2.7',
      'version_status':'POSTRELEASE_P0_AUDIT_NOT_A_NEW_FORMAL_THEOREM_VERSION',
      'benchmark_scope':'Purpose-built synthetic cases; NOT an empirical real-world business coverage percentage',
      'case_total':len(rows), 'breakdown_by_version':{'v2.2':32,'v2.3':5,'v2.6':11,'v2.7':11},
      'counts':expected, 'assumption_catalog':implemented_assumption_catalog_v27(),
      'delta_audits':prev['delta_audits'],
      'evidence':{'legacy_48':'Re-executed historical fixtures; B04 retains archived ER300 evidence',
                  'd6_11':'Re-executed formal theorem and replay from v2.7 showcase generator',
                  'd6_original_counts':d6['counts']},
      'critical_boundaries':[
         'The 48 historical prompts are replayed under their original assumptions and targets, not silently upgraded with new assumptions or newly available routes.',
         'B20 newly has E4/R2 implementation but the original policy remains zero signature support.',
         'B24 can use R3 p-standardized direct only as a new clarified target with additional A4/A5, not an automatic validation of original self-selection.',
         'D6 profile-exclusion and any R2 sufficiency are substantive scientific premises, not outputs of the probability support kernel.',
         'POINT means identified population functional conditional on declared scientific assumptions; NO_ADAPTER means no matching finite-sample estimator is certified.',
         'UNSUPPORTED is a software scope/blocker, not mathematical proof of non-identification.',
         'This matrix does not compare outcomes from actual business trials, and does not measure fraction of real-world tasks solvable.'
      ],
      'cards':rows,
    }


def html_dashboard(report:dict)->str:
    safe=json.dumps(report,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    # All free-text fields are assigned with textContent, not innerHTML.
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CFM-ID v2.7 · 59 Case and Assumption Audit</title><style>
:root{font:15px/1.6 system-ui,-apple-system,"PingFang SC",sans-serif;color:#162b41;background:#f4f7fa}
*{box-sizing:border-box}body{margin:0}header{background:#193552;color:white;padding:34px max(20px,calc((100% - 1150px)/2))}
main{max-width:1160px;margin:auto;padding:20px 18px 65px}.lede{color:#d2dce8}h1{font-size:26px;margin:0 0 6px}h2{font-size:20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:17px 0}
.kpi,section{background:white;padding:20px;border:1px solid #d8e2ec;border-radius:12px}
.kpi strong{font-size:27px;display:block;color:#193552}.muted{color:#647689}.subtle{font-size:12px}
.filter{display:flex;gap:10px;flex-wrap:wrap}input,select{font:inherit;border:1px solid #ccd9e6;padding:9px;border-radius:8px;background:white}
input{flex:1;min-width:240px}table{width:100%;border-collapse:collapse;text-align:left}td,th{padding:11px 8px;border-bottom:1px solid #e8edf2;vertical-align:top}th{font-size:12px;color:#5d6c7c}
tr:hover{background:#f5f8fa}.tag{border-radius:6px;background:#eaf0f6;font-size:12px;padding:3px 7px;white-space:nowrap}
.good{color:#176046}.bad{color:#90582a}details{margin:5px 0}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.55 ui-monospace,monospace;background:#eef3f8;padding:13px;border-radius:7px}
@media(max-width:640px){table{font-size:12px}td:nth-child(4),th:nth-child(4){display:none}}
</style></head><body><header><h1>Causal-IDFM · v2.7 业务与假设验收</h1><div class="lede">59 张合成研究卡（旧 48 + D6 新 11）｜正式识别与估计能力严格分离</div></header>
<main><section><strong>科学边界：</strong>数据为形式化/合成验收，POINT 是总体公式识别而不是因果效应数值；假设录入不代表现实成立；UNSUPPORTED 不等于数学不可识别。</section>
<div id="metrics" class="cards"></div><section><h2>覆盖矩阵</h2><div class="filter"><input id="search" placeholder="查询 B20 / R3 / D6 / 业务关键词" aria-label="Search cases"/>
<select id="state"><option value="">全部状态</option><option>POINT</option><option>NEEDS_INPUT</option><option>BLOCKED_OR_TARGET_GAP</option></select>
<select id="origin"><option value="">全部版本</option><option>v2.2</option><option>v2.3</option><option>v2.6</option><option>v2.7</option></select></div>
<p id="count" class="muted"></p><table><thead><tr><th>编号</th><th>业务问题</th><th>识别结果</th><th>Route</th><th>说明</th></tr></thead><tbody id="rows"></tbody></table></section>
<section><h2>当前正式假设类型</h2><div id="assumptions"></div></section></main>
<script>const DATA=__DATA__;
const el=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=String(text);return x};
for(const [label,val] of Object.entries({"案例总数":DATA.case_total,"POINT":DATA.counts.POINT,"NEEDS_INPUT":DATA.counts.NEEDS_INPUT,"其他阻断或目标缺口":DATA.counts.BLOCKED_OR_TARGET_GAP})){const c=el('div','kpi'),v=el('strong','',val);c.append(v,el('span','muted',label));document.getElementById('metrics').append(c)}
for(const a of DATA.assumption_catalog.assumptions){let d=el('details'),s=el('summary','',a.name+" · "+a.layer);d.append(s,el('p','',a.description),el('p','muted',a.scientific_scope),el('p','subtle',a.machine_verifiability));document.getElementById('assumptions').append(d)}
function statusOf(x){const s=x.l2_identification;return s.startsWith('POINT')?'POINT':s==='NEEDS_INPUT'?'NEEDS_INPUT':'BLOCKED_OR_TARGET_GAP'}
function render(){const q=document.getElementById('search').value.toLowerCase(),st=document.getElementById('state').value,orig=document.getElementById('origin').value;
const data=DATA.cards.filter(c=>(!st||statusOf(c)===st)&&(!orig||c.fixture_origin===orig)&&(!q||JSON.stringify(c).toLowerCase().includes(q)));
const body=document.getElementById('rows');body.replaceChildren();for(const c of data){let row=el('tr');row.append(el('td','',c.case_id),el('td','',c.business_question));let stat=el('td',statusOf(c)==='POINT'?'good':'bad',c.l2_identification);row.append(stat,el('td','subtle',c.l1_route));let detail=el('details'),sm=el('summary','',"A4/A5/A6 与证据"),p=el('pre','',JSON.stringify({a4:c.a4,a5:c.a5,a6:c.a6,reason:c.reason,note:c.note,evidence_scope:c.evidence_scope,estimation:c.adapter_status},null,2));detail.append(sm,p);let td=el('td');td.append(detail);row.append(td);body.append(row)}
document.getElementById('count').textContent=`当前显示 ${data.length} / ${DATA.case_total} 张合成验收卡`}
for(const id of ['search','state','origin'])document.getElementById(id).addEventListener('input',render);render();
</script></body></html>'''.replace('__DATA__',safe)


def save(report:dict,folder:Path)->tuple[Path,Path,Path]:
    folder.mkdir(parents=True,exist_ok=True)
    js=folder/(STEM+'.json');ht=folder/(STEM+'.html');csvpath=folder/(STEM+'.csv')
    js.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    ht.write_text(html_dashboard(report),encoding='utf-8')
    with csvpath.open('w',encoding='utf-8-sig',newline='') as out:
        fields=['case_id','fixture_origin','business_question','l0_target','l1_route','l2_identification','l3_estimation','reason','evidence_scope']
        writer=csv.DictWriter(out,fields);writer.writeheader();writer.writerows({k:r.get(k) for k in fields} for r in report['cards'])
    return js,ht,csvpath


def main(folder:Path)->dict:
    data=build_postrelease_matrix();save(data,folder)
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',default='showcase_v27_postrelease')
    args=parser.parse_args();data=main(Path(args.output_dir));print('v2.7 postrelease cases',data['case_total'],data['counts'])
