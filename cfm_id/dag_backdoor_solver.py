"""Classical back-door search via ancestral moralization; not general ID."""
from itertools import combinations
from .dag_backdoor_contract import validate,fail,digest,VERSION
from cfm_id_bridge.scientific_binding import sha


def descendants(nodes,edges,start):
    result=set();front=[start]
    while front:
        n=front.pop()
        for a,b in edges:
            if a==n and b not in result:result.add(b);front.append(b)
    return result


def moral_separation(nodes,edges,x,y,z):
    """d-separation in the graph supplied by the caller."""
    ancestors={x,y,*z};changed=True
    while changed:
        before=len(ancestors)
        ancestors.update(a for a,b in edges if b in ancestors)
        changed=len(ancestors)!=before
    moral=set()
    for a,b in edges:
        if a in ancestors and b in ancestors:moral.add(tuple(sorted((a,b))))
    for n in ancestors:
        parents=sorted(a for a,b in edges if b==n and a in ancestors)
        moral.update(combinations(parents,2))
    reached={x};front=[x];blocked=set(z)
    while front:
        n=front.pop()
        for a,b in moral:
            if n not in (a,b):continue
            other=b if n==a else a
            if other not in blocked and other not in reached:reached.add(other);front.append(other)
    return y not in reached,dict(ancestral_nodes=sorted(ancestors),
        moral_edges=[list(e) for e in sorted(moral)],reachable_after_conditioning=sorted(reached))


def functional(p,z):
    return dict(operation='BACKDOOR_ADJUSTMENT',source_id=p.information.source_id,
        outcome=p.outcome,treatment=p.treatment,sum_over=list(z),
        conditional=dict(outcomes=[p.outcome],given=[p.treatment,*z]),
        marginal=dict(variables=list(z)),empty_marginal_is_one=True)


def solve(problem):
    p=validate(problem);x,y=p.treatment,p.outcome
    forbidden=descendants(p.nodes,p.edges,x)
    graph=[(a,b) for a,b in p.edges if a!=x]
    if p.adjustment is not None:
        if set(p.adjustment)&forbidden:fail('UNSUPPORTED','ADJUSTMENT_CONTAINS_TREATMENT_DESCENDANT')
        candidates=[tuple(sorted(p.adjustment))]
    else:
        eligible=sorted(set(p.observed)-{x,y}-forbidden)
        candidates=(z for k in range(len(eligible)+1) for z in combinations(eligible,k))
    for z in candidates:
        ok,trace=moral_separation(p.nodes,graph,x,y,z)
        if not ok:continue
        cert=dict(version=VERSION,theorem='CLASSICAL_BACKDOOR_SUFFICIENT',status='POINT',
            problem_sha256=digest(p),information_sha256=sha(p.information),
            target=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=x,outcome=y,context=p.context),
            adjustment=list(z),functional=functional(p,z),graphical_trace=trace,
            positivity='DECLARED_STRICT_POSITIVE_OBSERVED_JOINT',numeric_value=None)
        cert['certificate_sha256']=sha(cert)
        return cert
    fail('UNSUPPORTED','NO_CLASSICAL_BACKDOOR_SET' if p.adjustment is None else 'SPECIFIED_SET_FAILS_CLASSICAL_BACKDOOR')
