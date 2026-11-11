"""Do not guess semantic correctness. Score objective gates and independent human labels.

  python -m evaluation.task6.scripts.score_experiment --run outputs/task6_dev_001
  # Fill the resulting review_template.csv; independent reviewer signs off.
  python -m evaluation.task6.scripts.score_experiment --run outputs/task6_dev_001 --reviews outputs/task6_dev_001/review_template.csv
"""
import argparse
import csv
import json
from collections import defaultdict,Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read_json(p):return json.loads(Path(p).read_text(encoding='utf8'))

def review_rows(runs):
    result=[]
    for r in runs:
        gold=read_json(ROOT/'references'/(r['case_id']+'.gold.json'))
        idtag='|'.join(map(str,(r['case_id'],r['profile'],r['repeat'])))
        checks=['target_kind_and_query_count','operands_and_comparison_direction',
                'evaluation_population_and_aggregation','outcome_time_background',
                'source_entailment_and_provenance','no_false_information_or_assumption_approval',
                'correct_missing_conflict_handling','A0_semantic_overall']
        for c in checks:
            result.append({'run_key':idtag,'case_id':r['case_id'],'scenario':gold['scenario'],
                'split':gold['split'],'variant':gold['variant'],'profile':r['profile'],
                'repeat':r['repeat'],'criterion':c,'judgment':'',
                'evidence_path_or_quote':'','reason_or_error_attribution':'',
                'reviewer_id':'','reviewed_utc':''})
    return result

def asrate(a,b):return None if b==0 else round(a/b,4)

def score(folder,reviews=None):
    folder=Path(folder);runs=read_json(folder/'runs.json')
    rows=review_rows(runs)
    if reviews is None:
        path=folder/'review_template.csv'
        if path.exists():raise ValueError(f'{path} exists: refusing to overwrite independent judgments')
        with path.open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    else:
        with Path(reviews).open(newline='',encoding='utf-8-sig') as f:judged=list(csv.DictReader(f))
        expected={(x['run_key'],x['criterion']) for x in rows}
        actual={(x['run_key'],x['criterion']) for x in judged}
        if len(actual)!=len(judged) or expected!=actual:
            raise ValueError('Review CSV rows missing, duplicated or unrecognized; no silent denominator changes')
        for row in judged:
            if row['judgment'].strip().upper() not in ('PASS','FAIL','UNCERTAIN','NOT_REVIEWED'):
                raise ValueError('Only PASS/FAIL/UNCERTAIN/NOT_REVIEWED permitted, cannot silently treat blanks as PASS')
            if row['judgment'].strip().upper() in ('PASS','FAIL') and not row['reviewer_id'].strip():
                raise ValueError('Every PASS/FAIL needs an independent reviewer_id')
        rows=judged
    scores=[]
    labels={(row['run_key'],row['criterion']):row for row in rows}
    for r in runs:
        gold=read_json(ROOT/'references'/(r['case_id']+'.gold.json'))
        key='|'.join(map(str,(r['case_id'],r['profile'],r['repeat'])))
        judgments={k:labels[(key,k)]['judgment'].strip().upper() or 'NOT_REVIEWED' for k in
                   ('target_kind_and_query_count','operands_and_comparison_direction',
                    'evaluation_population_and_aggregation','outcome_time_background',
                    'source_entailment_and_provenance','no_false_information_or_assumption_approval',
                    'correct_missing_conflict_handling','A0_semantic_overall')}
        # An errored or invalid response is NEVER a correct missing-material detection.
        valid=bool(r.get('format_parse_success'))
        a0_keys = [k for k in judgments if k != 'correct_missing_conflict_handling']

        passed = valid and all(judgments[k] == 'PASS' for k in a0_keys)
        complete = all(judgments[k] in ('PASS', 'FAIL') for k in a0_keys)
        correct_missing=valid and judgments['correct_missing_conflict_handling']=='PASS' and gold['variant']=='changed'
        scores.append(dict(case_id=r['case_id'],profile=r['profile'],repeat=r['repeat'],
          variant=gold['variant'],domain=gold['domain'],split=gold['split'],
          api_called=r['api_called'],response_obtained=r['raw_response_saved'],
          format_parse_success=valid,canonical_query_count=r.get('canonical_query_count'),
          query_count_correct=(valid and r.get('canonical_query_count')==gold['expected_query_count']),
          primary_kind_correct=(valid and gold['expected_primary_kind']!='MULTI' and
                                (r.get('canonical_kinds') or [None])[0]==gold['expected_primary_kind']),
          wire_state=r['wire_state'],human_review_complete=complete,
          human_a0_fully_correct=passed if complete else None,
          missing_conflict_handled_correctly=(correct_missing if gold['variant']=='changed'
              and judgments['correct_missing_conflict_handling'] in ('PASS','FAIL') else None),
          judgments=judgments,usage=r.get('usage',{})))
    aggregate={}
    for profile in sorted(set(x['profile'] for x in scores)):
        group=[x for x in scores if x['profile']==profile]
        tested=sum(x['api_called'] for x in group)
        accepted=sum(x['format_parse_success'] for x in group)
        human=[x for x in group if x['human_review_complete']]
        semantic=sum(x['human_a0_fully_correct'] is True for x in human)
        missing = [
            x for x in group
            if x['variant'] == 'changed'
            and x['judgments']['correct_missing_conflict_handling'] in ('PASS', 'FAIL')
        ]
        aggregate[profile]={'attempted':tested,'responses':sum(x['response_obtained'] for x in group),
             'format_parsed':accepted,'format_parse_rate_all_attempts':asrate(accepted,tested),
             'kind_correct_safely_scored':sum(x['primary_kind_correct'] for x in group),
             'kind_count_eligible':sum(x['canonical_query_count']==1 and x['format_parse_success'] for x in group),
             'query_count_correct_all_attempts':sum(x['query_count_correct'] for x in group),
             'human_reviewed':len(human),'human_a0_pass':semantic,
             'human_a0_accuracy_among_reviewed':asrate(semantic,len(human)),
             'human_a0_accuracy_all_attempts':asrate(semantic,tested) if len(human)==tested else None,
             'negative_cases_reviewed':len(missing),
             'negative_cases_correct_missing_or_conflict':sum(x['missing_conflict_handled_correctly'] is True for x in missing),
             'prompt_tokens':sum(x['usage'].get('prompt_tokens',0) for x in group),
             'completion_tokens':sum(x['usage'].get('completion_tokens',0) for x in group)}
    # Pair-level deltas only if the exact same case and repeat have both fully reviewed.
    paired=defaultdict(dict)
    for s in scores:paired[(s['case_id'],s['repeat'])][s['profile']]=s
    pairs=[]
    for (cid,rep),record in paired.items():
        if not all(p in record for p in ('prompt_only','prompt_plus_skill')):continue
        b,n=record['prompt_only'],record['prompt_plus_skill']
        if b['human_a0_fully_correct'] is None or n['human_a0_fully_correct'] is None:continue
        pairs.append({'case_id':cid,'repeat':rep,'prompt_only_correct':b['human_a0_fully_correct'],
                      'prompt_plus_skill_correct':n['human_a0_fully_correct'],
                      'delta':int(n['human_a0_fully_correct'])-int(b['human_a0_fully_correct'])})
    result={'scope':'A0 only; not identification accuracy','profiles':aggregate,
      'paired_complete_human_reviews':len(pairs),'paired_net_improvement':sum(x['delta'] for x in pairs),
      'paired_records':pairs,'repeat_runs_not_new_scenarios':True,
      'independent_situations_count':len({x['case_id'].rsplit('-',1)[0] for x in scores}),
      'business_materials_count':len({x['case_id'] for x in scores}),
      'reference_gold_status':'AUTHOR_DRAFT_PENDING_INDEPENDENT_REVIEW',
      'semantic_scores_not_verified_until_reviewed':True,
      'reviewer_identity_warning':'Labels are user-provided; reviewer_id cannot prove independence or human review. References remain unverified.',
      'fact_stage':'NOT_MEASURED','full_chain':'NOT_MEASURED'}
    (folder/'scoring_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k in ('profiles','paired_complete_human_reviews','paired_net_improvement')},ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True)
    p.add_argument('--reviews')
    args=p.parse_args()
    score(args.run,args.reviews)
