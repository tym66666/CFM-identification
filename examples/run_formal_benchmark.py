"""Offline synthetic FORMAL_BACKED_TRACK, distinct from NBIB RAW_BUSINESS_TRACK.

Uses genuine audited Gateway drafts, synthetic human/science approvals, exact
Core identification and independent replay for 9 formal route families.  It is
not a real-world coverage fraction or evidence that scientific assumptions hold.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
from tests.test_json_route_packets import JSONPacketRegression


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='assets/formal_benchmark_assets/formal_backed_results.json')
    args=parser.parse_args(argv)
    tester=JSONPacketRegression('test_all_nine_routes_and_negative_injection')
    tester.setUp()
    tester.test_all_nine_routes_and_negative_injection()
    results=tester.formal_benchmark_results
    score=sum(x['actual']==x['expected'] for x in results)
    summary={
       'schema_version':'cfm-id-v291-formal-backed-offline-synthetic',
       'version':'2.9.1',
       'track':'FORMAL_BACKED_TRACK',
       'population_operator':'EXPLICITLY_SYNTHETIC_NOT_FROM_SAMPLE',
       'science_truth':'HYPOTHETICAL_STIPULATION_NOT_REAL_WORLD_VALIDATION',
       'cases':results,
       'count':len(results),'route_count':len(set(x['route'] for x in results)),
       'pass_count':score,'fail_count':len(results)-score,
       'scenario_counts':dict(sorted(Counter(x['scenario'] for x in results).items())),
       'numeric_estimation_performed':False,
       'raw_business_benchmark':'SEPARATE; the existing 21 NBIB golds lack admitted A4'
    }
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('version','track','count','route_count','pass_count','fail_count')},ensure_ascii=False))
    return 0 if score==len(results) else 1

if __name__=='__main__':raise SystemExit(main())
