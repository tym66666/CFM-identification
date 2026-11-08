"""Replay on original noncausal paths; no solver, moralization or old graph imports."""
from .dag_adjustment_contract import validate,digest,VERSION,THEOREM,CLAIM_SCOPE
from cfm_id_bridge.scientific_binding import sha

def original_graph_check(nodes,edges,x,y,z):
    arrows=set(map(tuple,edges));adj={v:set() for v in nodes}
    for a,b in arrows:adj[a].add(b);adj[b].add(a)
    paths=[]
    def walk(path):
        if path[-1]==y:paths.append(path);return
        for v in sorted(adj[path[-1]]-set(path)):walk(path+[v])
    walk([x])
    causal=[path for path in paths if all((a,b) in arrows for a,b in zip(path,path[1:]))]
    causal_nodes={v for path in causal for v in path[1:]}
    # Independent transitive closure; reflexive descendants are intentional.
    reach={(a,b):a==b or (a,b) in arrows for a in nodes for b in nodes}
    for k in nodes:
        for a in nodes:
            for b in nodes:reach[a,b]=reach[a,b] or (reach[a,k] and reach[k,b])
    forbidden={v for v in nodes if any(reach[w,v] for w in causal_nodes)}
    opened={v for v in nodes if any(reach[v,w] for w in z)}
    active=[]
    for path in paths:
        if all((a,b) in arrows for a,b in zip(path,path[1:])):continue
        for prev,node,nxt in zip(path,path[1:],path[2:]):
            collider=(prev,node) in arrows and (nxt,node) in arrows
            if (collider and node not in opened) or (not collider and node in z):break
        else:active.append(path)
    trace=dict(causal_path_nodes=sorted(causal_nodes),forbidden_nodes=sorted(forbidden),
        removed_causal_first_edges=[list(e) for e in sorted({(p[0],p[1]) for p in causal})])
    ok=not(set(z)&forbidden) and not active
    return ok,trace,active

def replay(certificate,*,problem):
    try:
        p=validate(problem);c=certificate
        keys={'version','theorem','status','claim_scope','problem_sha256','information_sha256',
              'target','adjustment','functional','graphical_trace','positivity','numeric_value','certificate_sha256'}
        if type(c) is not dict or set(c)!=keys:return False
        if type(c['certificate_sha256']) is not str:return False
        if c['certificate_sha256']!=sha({k:v for k,v in c.items() if k!='certificate_sha256'}):return False
        if (c['version'],c['theorem'],c['status'],c['claim_scope'])!=(VERSION,THEOREM,'POINT',CLAIM_SCOPE):return False
        if c['problem_sha256']!=digest(p) or c['information_sha256']!=sha(p.information):return False
        if c['numeric_value'] is not None or c['positivity']!='DECLARED_STRICT_POSITIVE_OBSERVED_JOINT':return False
        z=c['adjustment']
        if type(z) is not list or any(type(v) is not str for v in z):return False
        if z!=sorted(set(z)) or not set(z)<=set(p.observed)-{p.treatment,p.outcome}:return False
        if p.adjustment is not None and set(z)!=set(p.adjustment):return False
        ok,trace,_=original_graph_check(p.nodes,p.edges,p.treatment,p.outcome,z)
        if not ok:return False
        target=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=p.treatment,outcome=p.outcome,context=p.context)
        function=dict(operation='COVARIATE_ADJUSTMENT',source_id=p.information.source_id,
            outcome=p.outcome,treatment=p.treatment,sum_over=z,
            conditional=dict(outcomes=[p.outcome],given=[p.treatment,*z]),
            marginal=dict(variables=z),empty_marginal_is_one=True)
        # Canonical hashes also distinguish JSON booleans from numbers.
        return (sha(c['target'])==sha(target) and sha(c['functional'])==sha(function)
                and sha(c['graphical_trace'])==sha(trace))
    except (ValueError,TypeError,KeyError,AttributeError):return False

