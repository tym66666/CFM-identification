"""Offline exact acceptance. Optional crosscheck against frozen research data.

No HTTP/client imports or credentials. Does not send labels to any model.
"""
from fractions import Fraction as F
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import time

from cfm_id.mean_order_contract import MeanOrderUnavailable
from cfm_id.mean_order_solver import solve
from cfm_id.mean_order_verify import replay
from examples.mean_order_fixture import make_problem
from examples.mean_order_reference import MeanOrderReference
from evaluation.partial_extension_acceptance import evaluate


def graph_sweep():
    results=[]; graphs=0
    for n in range(1,5):
        nodes=[f'N{i}' for i in range(n)]; pairs=list(combinations(nodes,2))
        for mask in range(2**len(pairs)):
            edges=[e for j,e in enumerate(pairs) if mask & (1<<j)]; graphs+=1
            for quota in range(n+1):
                for mode in ('NONE','OWN','PEERS','BOTH'):
                    p=make_problem(nodes=nodes,edges=edges,quota=quota,mode=mode)
                    c=solve(p); ok=replay(c,problem=p)
                    results.append(dict(n=n,edges=edges,quota=quota,mode=mode,replayed=ok,
                        status=c['status'],interval=[c['lower'],c['upper']],certificate_sha256=c['certificate_sha256']))
        print(json.dumps(dict(stage='graph_sweep',completed_n=n,graphs=graphs,cases=len(results))),flush=True)
    return dict(graphs=graphs,cases=len(results),passed=all(r['replayed'] for r in results),rows=results)


def research_crosscheck(path):
    blob=path.read_bytes(); data=json.loads(blob)
    records=data['ladder']['stages']+data['counterexamples']+data['infeasible']+data['additional_cases']+data['random']
    rows=[]
    for r in records:
        if 'input' not in r or 'fraction_vertex_result' not in r:continue
        x=r['input']; label=x['label']
        if x['no_peer']:
            rows.append(dict(label=label,status='NOT_ADAPTED',reason='NO_PEER_EQUALITY_NOT_IN_CONTRACT'));continue
        values=[dict(node=f'N{i}',own=int(k.split(',')[0]),exposure=int(k.split(',')[1]),value=v)
                for i,table in enumerate(x['known']) for k,v in table.items()]
        if not values:
            rows.append(dict(label=label,status='NOT_ADAPTED',reason='EMPTY_A4_NOT_ADMITTED_BY_CURRENT_ENTRY'));continue
        p=make_problem(nodes=[f'N{i}' for i in range(x['n'])],edges=[(f'N{a}',f'N{b}') for a,b in x['edges']],
            quota=x['quota'],mode=x['mode'],first=x['first'],second=x['second'],weights=x['weights'],values=values)
        # Independent current material-completeness gate, distinct from the
        # research oracle's less restrictive mathematical feasibility domain.
        def sig(z,i):
            friends=[b if a==i else a for a,b in x['edges'] if i in (a,b)]
            return (z[i],int(sum(z[j] for j in friends)*2>len(friends)))
        missing=False
        for i,w in enumerate(x['weights']):
            a,b=sig(x['first'],i),sig(x['second'],i)
            if not F(w) or a==b:continue
            support={sig(z,i) for z in product((0,1),repeat=x['n']) if sum(z)==x['quota']}
            for c in (a,b):
                if c in support and ','.join(map(str,c)) not in x['known'][i]:missing=True
        try:
            cert=solve(p)
        except MeanOrderUnavailable as exc:
            ok=missing and exc.state=='NEEDS_INPUT'
            rows.append(dict(label=label,status=exc.state,passed=ok,reason=exc.reason));continue
        ref=r['fraction_vertex_result']; ok=not missing and replay(cert,problem=p)
        if ref['feasible']:
            ok=ok and cert['status'] in ('POINT','PARTIAL') and [cert['lower'],cert['upper']]==[ref['lower'],ref['upper']]
        else:ok=ok and cert['status']=='INCOMPATIBLE'
        rows.append(dict(label=label,status=cert['status'],passed=ok,problem=p.model_dump(),certificate=cert))
    admitted=[r for r in rows if r['status']!='NOT_ADAPTED']
    return dict(source=str(path),source_sha256=hashlib.sha256(blob).hexdigest(),
        total=len(rows),compared=len(admitted),not_adapted=len(rows)-len(admitted),
        passed=all(r['passed'] for r in admitted),rows=rows)


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--research-results',type=Path)
    args=parser.parse_args(); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    reports={'six_hook_acceptance':evaluate(MeanOrderReference()),'graph_sweep':graph_sweep()}
    if args.research_results:reports['research_crosscheck']=research_crosscheck(args.research_results)
    # Retain full inputs and certificates for the readable fixed-question ladder.
    reports['ladder_certificates']={}
    for mode in ('BOTH','OWN','NONE'):
        p=make_problem(mode=mode)
        reports['ladder_certificates'][mode]=dict(problem=p.model_dump(),certificate=solve(p))
    summary=dict(status='PASS',api_calls=0,llm_accuracy_measured=False,business_route_registered=False,
                 production_admission=False,elapsed_seconds=round(time.monotonic()-start,3))
    for name,report in reports.items():
        with (out/(name+'.json')).open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
        if report.get('passed') is False:summary['status']='FAIL'
    summary.update(graphs=reports['graph_sweep']['graphs'],graph_model_cases=reports['graph_sweep']['cases'],
                   six_hook_cases=reports['six_hook_acceptance']['cases'])
    if 'research_crosscheck' in reports:
        summary['research_compared']=reports['research_crosscheck']['compared']
        summary['research_not_adapted']=reports['research_crosscheck']['not_adapted']
    (out/'acceptance_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    if summary['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
