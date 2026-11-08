"""Independent active-path replay. No solver/compiler/moral-graph imports."""
from itertools import combinations
from .dag_backdoor_contract import validate,digest,VERSION
from cfm_id_bridge.scientific_binding import sha


def active_paths(nodes,edges,x,y,z):
    """Enumerate unblocked simple paths, including opened collider descendants."""
    arrows=set(map(tuple,edges));adj={n:set() for n in nodes}
    for a,b in arrows:adj[a].add(b);adj[b].add(a)
    z=set(z);activated=set(z)
    while True:
        added={a for a,b in arrows if b in activated}-activated
        if not added:break
        activated|=added
    found=[]
    def walk(path):
        node=path[-1]
        if node==y:found.append(path);return
        for nxt in sorted(adj[node]-set(path)):
            if len(path)>1:
                previous=path[-2]
                collider=(previous,node) in arrows and (nxt,node) in arrows
                if collider and node not in activated:continue
                if not collider and node in z:continue
            walk(path+[nxt])
    walk([x]);return found


def _forbidden(p):
    # Reverse reachability per vertex, independent of the solver's forward DFS.
    result=set()
    for v in p.nodes:
        if v==p.treatment:continue
        ancestors={v}
        while True:
            new={a for a,b in p.edges if b in ancestors}-ancestors
            if not new:break
            ancestors|=new
        if p.treatment in ancestors:result.add(v)
    return result


def _trace(p,z):
    # Check every solver-provided trace field; this is not used for separation.
    edges=[(a,b) for a,b in p.edges if a!=p.treatment]
    ancestors=set()
    for v in [p.treatment,p.outcome,*z]:
        chain={v}
        while True:
            new={a for a,b in edges if b in chain}-chain
            if not new:break
            chain|=new
        ancestors|=chain
    moral=[]
    for a,b in combinations(sorted(ancestors),2):
        linked=(a,b) in edges or (b,a) in edges or any((a,c) in edges and (b,c) in edges for c in ancestors)
        if linked:moral.append([a,b])
    reach={p.treatment}
    while True:
        new={b if a in reach else a for a,b in moral if (a in reach or b in reach) and a not in z and b not in z}-reach
        if not new:break
        reach|=new
    return dict(ancestral_nodes=sorted(ancestors),moral_edges=moral,reachable_after_conditioning=sorted(reach))


def replay(certificate,*,problem):
    try:
        p=validate(problem);c=certificate
        if type(c) is not dict:return False
        expected={'version','theorem','status','problem_sha256','information_sha256','target','adjustment',
                  'functional','graphical_trace','positivity','numeric_value','certificate_sha256'}
        if set(c)!=expected:return False
        if c['certificate_sha256']!=sha({k:v for k,v in c.items() if k!='certificate_sha256'}):return False
        if (c['version'],c['theorem'],c['status'])!=(VERSION,'CLASSICAL_BACKDOOR_SUFFICIENT','POINT'):return False
        if c['problem_sha256']!=digest(p) or c['information_sha256']!=sha(p.information):return False
        if c['numeric_value'] is not None or c['positivity']!='DECLARED_STRICT_POSITIVE_OBSERVED_JOINT':return False
        if c['target']!=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=p.treatment,outcome=p.outcome,context=p.context):return False
        z=c['adjustment']
        if type(z) is not list or any(type(v) is not str for v in z):return False
        if z!=sorted(set(z)) or not set(z)<=set(p.observed)-{p.treatment,p.outcome}:return False
        if p.adjustment is not None and set(z)!=set(p.adjustment):return False
        if set(z)&_forbidden(p):return False
        graph=[e for e in p.edges if e[0]!=p.treatment]
        if active_paths(p.nodes,graph,p.treatment,p.outcome,z):return False
        expected_function=dict(operation='BACKDOOR_ADJUSTMENT',source_id=p.information.source_id,
            outcome=p.outcome,treatment=p.treatment,sum_over=z,
            conditional=dict(outcomes=[p.outcome],given=[p.treatment,*z]),
            marginal=dict(variables=z),empty_marginal_is_one=True)
        if c['functional']!=expected_function or c['graphical_trace']!=_trace(p,z):return False
        return True
    except (ValueError,TypeError,KeyError,AttributeError):return False
