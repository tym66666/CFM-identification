"""Deterministic OFFLINE structural stress test, NOT an LLM accuracy benchmark.

Unique graph/quota/policy/population/outcome configurations, exact independent
vertex extrema, certificate replay, tampering, and optional full mock admission.
The parameters are generated, never routed by a business-case name.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import random
import time

from cfm_id_bridge.scientific_binding import sha
from cfm_id import bounded_policy_intake as intake
from cfm_id.bounded_policy_solver import solve
from cfm_id.bounded_policy_verify import replay
from examples.bounded_policy_intake_fixture import make_case, declaration_review, existing_reviews


def vertex_extrema(declaration, coordinates):
    """Enumerate feasible target-coordinate box corners using input data only.

All non-target known means are also checked. This oracle is independent of
support primitives, the bound formula implementation and its certificate.
Independent replay additionally reconstructs every observational mean.
"""
    s,info=declaration['study'],declaration['information'];nodes=s['node_order'];n=len(nodes)
    adjacency={node:set() for node in nodes}
    for a,b in s['undirected_edges']:adjacency[a].add(b);adjacency[b].add(a)
    def cell(node,values):
        count=sum(values[j] for j in adjacency[node]);degree=len(adjacency[node])
        return node,values[node],int(count*2>degree)
    support=set()
    for vector in product((0,1),repeat=n):
        if sum(vector)==s['fixed_count']:
            values=dict(zip(nodes,vector));support.update(cell(node,values) for node in nodes)
    known={(v['node'],v['own'],v['exposure']):F(v['value']) for v in info['values']}
    bounds={v['node']:(F(v['lower']),F(v['upper'])) for v in info['bounds']}
    if s['outcome_kind']=='binary':
        if info['bounds_kind']=='ALMOST_SURE_OUTCOME':
            allowed={k:[F(v) for v in (0,1) if lo<=v<=hi] for k,(lo,hi) in bounds.items()}
            if any(not values for values in allowed.values()):raise ValueError('EMPTY_BINARY_SUPPORT')
            bounds={k:(min(v),max(v)) for k,v in allowed.items()}
        else:bounds={k:(max(lo,F(0)),min(hi,F(1))) for k,(lo,hi) in bounds.items()}
    if any(lo>hi for lo,hi in bounds.values()):raise ValueError('INFEASIBLE_BOUNDS')
    if not set(known)<=support:raise ValueError('ZERO_SUPPORT_A4')
    if any(not bounds[c[0]][0]<=v<=bounds[c[0]][1] for c,v in known.items()):raise ValueError('INCOMPATIBLE_A4')
    policy=dict(zip(nodes,coordinates['assignment']));corners=[]
    for node,weight in zip(nodes,coordinates['unit_weights']):
        c=cell(node,policy)
        if F(weight)>0 and c in support and c not in known:raise ValueError('MISSING_POSITIVE_SUPPORT_MEAN')
        corners.append((known[c],) if c in known else bounds[node])
    objective=[sum((F(w)*v for w,v in zip(coordinates['unit_weights'],corner)),F(0)) for corner in product(*corners)]
    return min(objective),max(objective)


def configurations(count,seed):
    rng=random.Random(seed);seen=set();serial=0
    while len(seen)<count:
        n=rng.randrange(2,9);nodes=['组'+str(i) for i in range(n)];density=rng.choice([0,.15,.35,.65,.85,1])
        edges=[(i,j) for i in range(n) for j in range(i+1,n) if rng.random()<density]
        quota=rng.randrange(n+1)
        policy=rng.choice([[0]*n,[1]*n,[rng.randrange(2) for _ in nodes]])
        pop=rng.choice([list(range(n)),[rng.randrange(n)],rng.sample(list(range(n)),rng.randrange(1,n+1))])
        pop.sort();continuous=bool(rng.randrange(2))
        key=(n,tuple(edges),quota,tuple(policy),tuple(pop),continuous)
        if key in seen:continue
        seen.add(key)
        yield make_case(nodes,[(nodes[i],nodes[j]) for i,j in edges],quota,policy,[nodes[i] for i in pop],continuous=continuous,serial=serial)
        serial+=1


def run(output,count=1000,seed=20261023,full_chain_every=20):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    statuses=Counter();by_size=Counter();full=0;started=time.monotonic()
    with (output/'cases.jsonl').open('x',encoding='utf8') as stream:
        for number,case in enumerate(configurations(count,seed)):
            b,raw,d,claims,expected=case
            record=declaration_review(b,raw,d,expected)
            compiled=intake.compile_reviewed(b,raw,query_id='q1',declaration=d,review=record,synthetic_protocol_selected=True)
            cert=solve(compiled.inquiry,compiled.information)
            low,high=vertex_extrema(d,expected)
            if (F(cert['lower']),F(cert['upper']))!=(low,high):raise RuntimeError('VERTEX_ORACLE_DISAGREES')
            if not replay(cert,inquiry=compiled.inquiry,information=compiled.information):raise RuntimeError('REPLAY_FAILED')
            forged=deepcopy(cert);forged['lower']=str(low-F(1,60));forged['width']=str(high-F(forged['lower']))
            forged.pop('certificate_sha256');forged['certificate_sha256']=sha(forged)
            if replay(forged,inquiry=compiled.inquiry,information=compiled.information):raise RuntimeError('FORGERY_ACCEPTED')
            chain=None
            if number%full_chain_every==0:
                options=existing_reviews(b,raw,compiled,claims,expected)
                chain=intake.submit(b,raw,query_id='q1',declaration=d,declaration_review=record,synthetic_protocol_selected=True,**options)
                if (chain['state']!=cert['status'] or not chain.get('bounded_certificate_replayed')
                        or chain.get('bounded_result')!=cert):raise RuntimeError('FULL_CHAIN_DISAGREES')
                full+=1
            row=dict(index=number,bundle=b,offline_mock_reading=raw,declaration=d,independent_target=expected,
                certificate=cert,oracle_interval=list(map(str,(low,high))),independent_replay=True,
                rehashed_forgery_rejected=True,full_mock_chain_passed=chain is not None)
            stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
            if number==0:
                for filename,value in [('bundle',b),('mock_reading',raw),('declaration',d),
                    ('worksheet',intake.prepare(b,raw,query_id='q1',declaration=d)),('full_mock_result',chain)]:
                    (output/(filename+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            statuses[cert['status']]+=1;by_size[len(b['node_order'])]+=1
            if (number+1)%100==0:print(json.dumps({'completed':number+1,'full_mock_chains':full}),flush=True)
    summary=dict(status='PASS',seed=seed,unique_parameter_configurations=count,
        exact_vertex_checks=count,independent_certificate_replays=count,rehashed_forgeries_rejected=count,
        full_mock_chains=full,status_counts=dict(statuses),node_count_distribution=dict(by_size),
        http_calls=0,llm_accuracy_measured=False,production_admission=False,
        elapsed_seconds=round(time.monotonic()-started,3),
        scope='Finite D2/E1 fixed policy means; synthetic independent science and mock readings')
    (output/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--cases',type=int,default=1000)
    p.add_argument('--seed',type=int,default=20261023);p.add_argument('--full-chain-every',type=int,default=20)
    args=p.parse_args()
    if not 1<=args.cases<=10000 or args.full_chain_every<1:p.error('positive bounded run sizes required')
    run(args.output,args.cases,args.seed,args.full_chain_every)


if __name__=='__main__':main()
