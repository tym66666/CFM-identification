"""Optional full-chain ledger: only enter REAL fact-reader + independent review results.

Generate once:
 python -m evaluation.task6.scripts.fact_stage_ledger --run outputs/task6_dev_001
After running the ORIGINAL project fact reader and signed scientific reviews,
edit fact_stage_template.csv, then:
 python -m evaluation.task6.scripts.fact_stage_ledger --run outputs/task6_dev_001 --ledger outputs/task6_dev_001/fact_stage_template.csv

No model calls and no synthetic approval occur in this script.
"""
import argparse,csv,json
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
FIELDS=('run_key','case_id','profile','repeat','query_id','fact_call_attempted','fact_wire_valid',
  'a4_scope_correct','a5_stance_correct','source_claims_correct','original_target_preserved',
  'missing_or_conflict_handled_correctly','researcher_approval_independent',
  'first_pass_full_chain_correct','wrong_certification','actual_final_status',
  'fact_api_calls','reread_api_calls','retry_api_calls','fact_prompt_tokens','fact_completion_tokens',
  'reference_documentation','reviewer_id','notes','execution_result_path','reference_json_path','model_candidate_path')

def expected(runs):
    rows=[]
    for run in runs:
        ref=json.loads((ROOT/'references'/(run['case_id']+'.gold.json')).read_text(encoding='utf8'))
        for i in range(1,ref['expected_query_count']+1):
            row=dict.fromkeys(FIELDS,'')
            row.update(run_key='|'.join((run['case_id'],run['profile'],str(run['repeat']))),
                case_id=run['case_id'],profile=run['profile'],repeat=str(run['repeat']),query_id=f'q{i}')
            rows.append(row)
    return rows

def read_csv(p):
    with Path(p).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def run(folder,ledger=None):
    path=Path(folder)
    runs=json.loads((path/'runs.json').read_text(encoding='utf8'))
    template=expected(runs)
    target=path/'fact_stage_template.csv'
    if ledger is None:
        if target.exists():raise ValueError('Refusing to overwrite an existing fact ledger')
        with target.open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,FIELDS);w.writeheader();w.writerows(template)
        print(f'Created {len(template)} EMPTY per-query lines at {target}. Do not submit these as real results.')
        return
    records=read_csv(ledger)
    ident=lambda r:(r['run_key'],r['query_id'])
    if len(records)!=len(template) or {ident(r) for r in records}!={ident(r) for r in template}:
        raise ValueError('Fact ledger has missing/duplicate/extra rows')
    status=['TRUE','FALSE','NOT_RUN']
    flags=('fact_call_attempted','fact_wire_valid','a4_scope_correct','a5_stance_correct',
        'source_claims_correct','original_target_preserved','missing_or_conflict_handled_correctly',
        'researcher_approval_independent','first_pass_full_chain_correct','wrong_certification')
    results=[]
    for r in records:
        for f in flags:
            if r[f].upper() not in status:
                raise ValueError(f"{r['run_key']} {r['query_id']}: {f} must be TRUE/FALSE/NOT_RUN")
        if r['first_pass_full_chain_correct'].upper()=='TRUE':
            if r['wrong_certification'].upper()!='FALSE':
                raise ValueError('Full-chain success incompatible with wrong certification')
            if r['actual_final_status']=='REVIEWED_MISSING_STOP':
                # Genuine missing-input stop may occur *before* fact reading.
                # It still requires an independent reasoned human verdict.
                if (r['missing_or_conflict_handled_correctly'].upper()!='TRUE'
                    or r['researcher_approval_independent'].upper()!='TRUE'
                    or not r['reference_documentation'].strip()):
                    raise ValueError('Correct early stop needs documented missing/conflict reason')
            elif not all(r[k].upper()=='TRUE' for k in ('fact_call_attempted','fact_wire_valid',
                    'a4_scope_correct','a5_stance_correct','source_claims_correct',
                    'original_target_preserved','researcher_approval_independent')):
                raise ValueError('Cannot mark mathematical full-chain success without fact evidence and independent scientific approvals')
            elif not r['actual_final_status'].strip() or not r['reference_documentation'].strip():
                raise ValueError('Full-chain success requires a final status and documented execution/certificate evidence')
            from evaluation.task6.scripts.verify_final import verify
            paths=[Path(r.get(k,'')) for k in ('execution_result_path','reference_json_path','model_candidate_path')]
            if any(not p.is_file() for p in paths):
                raise ValueError('Full-chain success requires actual result, reference, and model-candidate files')
            actual=json.loads(paths[0].read_text(encoding='utf8'))
            reference=json.loads(paths[1].read_text(encoding='utf8'))
            candidate=json.loads(paths[2].read_text(encoding='utf8'))
            if not isinstance(candidate,dict) or not candidate:
                raise ValueError('Actual model candidate is missing or invalid')
            ledger_state=r['actual_final_status']
            if ledger_state!='REVIEWED_MISSING_STOP' and actual.get('state')!=ledger_state:
                raise ValueError('Ledger state does not match recorded project outcome')
            if (actual.get('query_review') or {}).get('authority')=='SYNTHETIC_TEST':
                raise ValueError('Synthetic reviews cannot support a real-model full-chain success')
            if not verify(actual,reference)['execution_evidence_gate_passed']:
                raise ValueError('Recorded execution does not satisfy expected outcome and replay evidence')
        if (r['first_pass_full_chain_correct'].upper()!='NOT_RUN'
            or r['wrong_certification'].upper()!='NOT_RUN') and not r['reviewer_id'].strip():
            raise ValueError('Every reviewed outcome requires reviewer_id')
        for k in ('fact_api_calls','reread_api_calls','retry_api_calls','fact_prompt_tokens','fact_completion_tokens'):
            if not r[k].isdigit():raise ValueError(f'{k} requires nonnegative integer')
        results.append(r)
    evaluated=[r for r in results if r['first_pass_full_chain_correct'].upper() in ('TRUE','FALSE')]
    denom=len(evaluated)
    good=sum(r['first_pass_full_chain_correct'].upper()=='TRUE' for r in evaluated)
    wrong=[r['run_key']+' '+r['query_id'] for r in results if r['wrong_certification'].upper()=='TRUE']
    wrong_reviewed=sum(r['wrong_certification'].upper() in ('TRUE','FALSE') for r in results)
    report={'fullchain_total_queries':len(results),'fullchain_audited_queries':denom,
        'fullchain_not_yet_audited':len(results)-denom,'correct_first_pass':good,
        'first_pass_accuracy_among_audited':round(good/denom,4) if denom else None,
        'first_pass_accuracy_all_queries':round(good/len(results),4) if results and denom==len(results) else None,
        'wrong_certification_reviewed_queries':wrong_reviewed,
        'wrong_certification_count_among_reviewed':len(wrong),
        'wrong_certification_count_all_queries':len(wrong) if wrong_reviewed==len(results) else None,
        'wrong_certification_items':wrong,
        'fact_stage_api_calls':sum(int(r['fact_api_calls']) for r in results),
        'reread_api_calls':sum(int(r['reread_api_calls']) for r in results),
        'retry_api_calls':sum(int(r['retry_api_calls']) for r in results),
        'fact_stage_prompt_tokens':sum(int(r['fact_prompt_tokens']) for r in results),
        'fact_stage_completion_tokens':sum(int(r['fact_completion_tokens']) for r in results),
        'warning':'User-entered reviewed records, not auto-executed by this script. Verify evidence before citing.'}
    (path/'fullchain_scoring_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True)
    p.add_argument('--ledger')
    a=p.parse_args()
    run(a.run,a.ledger)
