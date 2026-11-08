"""DAG adjustment via proper back-door graph and ancestral moralization."""
from itertools import combinations
from .dag_adjustment_contract import validate,digest,VERSION,THEOREM,CLAIM_SCOPE,Unavailable
from cfm_id_bridge.scientific_binding import sha

class CriterionFailure(Unavailable):
    def __init__(self,reason,diagnostic):
        super().__init__('UNSUPPORTED',reason)
        self.diagnostic=diagnostic

def reachable(seeds,edges,reverse=False):
    found=set(seeds);front=list(seeds)
    while front:
        node=front.pop()
        for a,b in edges:
            if reverse:a,b=b,a
            if a==node and b not in found:found.add(b);front.append(b)
    return found

def graph_parts(nodes,edges,x,y):
    # For a single treatment in a DAG, this intersection is exactly the
    # non-X vertices on directed X-to-Y paths. Reachability includes seeds.
    causal=(reachable([x],edges)&reachable([y],edges,True))-{x}
    forbidden=reachable(causal,edges)
    removed=sorted((a,b) for a,b in edges if a==x and b in causal)
    proper=[(a,b) for a,b in edges if (a,b) not in removed]
    trace=dict(causal_path_nodes=sorted(causal),forbidden_nodes=sorted(forbidden),
               removed_causal_first_edges=[list(e) for e in removed])
    return proper,forbidden,trace

def moral_separation(nodes,edges,x,y,z):
    ancestors=reachable([x,y,*z],edges,True)
    links={tuple(sorted((a,b))) for a,b in edges if a in ancestors and b in ancestors}
    for child in ancestors:
        parents=sorted(a for a,b in edges if b==child and a in ancestors)
        links.update(combinations(parents,2))
    adjacency={v:set() for v in ancestors}
    for a,b in links:
        if a not in z and b not in z:adjacency[a].add(b);adjacency[b].add(a)
    reached={x};front=[x]
    while front:
        for v in adjacency[front.pop()]-reached:reached.add(v);front.append(v)
    return y not in reached,dict(ancestral_nodes=sorted(ancestors),reachable_after_conditioning=sorted(reached))

def functional(p,z):
    return dict(operation='COVARIATE_ADJUSTMENT',source_id=p.information.source_id,
        outcome=p.outcome,treatment=p.treatment,sum_over=list(z),
        conditional=dict(outcomes=[p.outcome],given=[p.treatment,*z]),
        marginal=dict(variables=list(z)),empty_marginal_is_one=True)

def solve(problem):
    p=validate(problem);x,y=p.treatment,p.outcome
    proper,forbidden,trace=graph_parts(p.nodes,p.edges,x,y)
    if p.adjustment is not None:
        bad=sorted(set(p.adjustment)&forbidden)
        if bad:raise CriterionFailure('ADJUSTMENT_INTERSECTS_FORBIDDEN_SET',
            dict(kind='FORBIDDEN_ADJUSTMENT_NODES',nodes=bad,**trace))
        candidates=[tuple(sorted(p.adjustment))]
    else:
        eligible=sorted(set(p.observed)-{x,y}-forbidden)
        candidates=(z for size in range(len(eligible)+1) for z in combinations(eligible,size))
    tested=0
    for z in candidates:
        tested+=1
        ok,failed=moral_separation(p.nodes,proper,x,y,z)
        if not ok:
            if p.adjustment is not None:
                raise CriterionFailure('SPECIFIED_SET_FAILS_DAG_ADJUSTMENT',
                    dict(kind='PROPER_GRAPH_NOT_SEPARATED',adjustment=list(z),**trace,**failed))
            continue
        c=dict(version=VERSION,theorem=THEOREM,status='POINT',claim_scope=CLAIM_SCOPE,
            problem_sha256=digest(p),information_sha256=sha(p.information),
            target=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=x,outcome=y,context=p.context),
            adjustment=list(z),functional=functional(p,z),graphical_trace=trace,
            positivity='DECLARED_STRICT_POSITIVE_OBSERVED_JOINT',numeric_value=None)
        c['certificate_sha256']=sha(c)
        return c
    raise CriterionFailure('NO_OBSERVED_DAG_ADJUSTMENT_SET',
        dict(kind='NO_SET_SATISFIES_GRAPHICAL_CRITERION',tested_sets=tested,**trace))

