"""Second executable adapter: one reviewed joint contrast, synthetic only."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
from cfm_id_bridge.scientific_binding import sha
from cfm_id import bounded_contrast as entry
from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable
from cfm_id.bounded_contrast_verify import replay
from evaluation.partial_extension_acceptance import AcceptanceCase
from examples.bounded_contrast_fixture import make_case, reviews


def vertex_reference(p, *, ignore_a4=False):
    """Enumerate shared box vertices and evaluate both policies separately.

    No signed-coefficient producer or support engine, not used by the runtime.
    Only a small synthetic oracle; general cases may have exponentially many vertices.
    """
    st = p['inquiries']['first'].study; nodes = list(st.node_order)
    data = p['information']['first']; t = p['coordinates']
    known = {} if ignore_a4 else {(r.node,r.own,r.exposure):F(r.value) for r in data.values}
    bounds = {r.node:(F(r.lower),F(r.upper)) for r in data.bounds}
    if st.outcome_kind == 'binary':
        if data.bounds_kind == 'ALMOST_SURE_OUTCOME':
            allowed = {n:[F(v) for v in (0,1) if lo<=v<=hi] for n,(lo,hi) in bounds.items()}
            bounds = {n:(min(v),max(v)) for n,v in allowed.items()}
        else:
            bounds = {n:(max(F(0),lo),min(F(1),hi)) for n,(lo,hi) in bounds.items()}
    def cell(i,z):
        friends = [nodes.index(b if a==nodes[i] else a) for a,b in st.undirected_edges if nodes[i] in (a,b)]
        return nodes[i],z[i],int(sum(z[j] for j in friends)*2>len(friends))
    needed = {cell(i,t[s]) for s in ('first','second') for i,w in enumerate(t['unit_weights']) if F(w)}
    free = sorted(needed-set(known))
    if len(free)>16: raise ValueError('OFFLINE_VERTEX_REFERENCE_LIMIT')
    values=[]
    for endpoints in product(*(bounds[c[0]] for c in free)):
        world=dict(known);world.update(zip(free,endpoints))
        arms=[sum((F(w)*world[cell(i,t[s])] for i,w in enumerate(t['unit_weights']) if F(w)),F(0)) for s in ('first','second')]
        values.append(arms[0]-arms[1])
    return min(values),max(values)


def set_common_information(p, *, bounds=None, values=None, bounds_kind=None):
    """Test-only changes to separately declared synthetic science, never LLM repair."""
    for side in ('first','second'):
        info=p['information'][side]; updates={}
        if bounds is not None:
            updates['bounds']=[r.model_copy(update={'lower':str(bounds[0]),'upper':str(bounds[1])}) for r in info.bounds]
        if values is not None:
            updates['values']=[r.model_copy(update={'value':str(values.get((r.node,r.own,r.exposure),r.value))}) for r in info.values]
        if bounds_kind is not None:updates['bounds_kind']=bounds_kind
        p['information'][side]=info.model_copy(update=updates)
        d=p['declarations'][side]['information']
        for k in updates:
            d[k]=[r.model_dump() for r in updates[k]] if isinstance(updates[k],list) else updates[k]
    return p


def ladder_payloads():
    nodes=list('ABCD');edges=[(a,b) for i,a in enumerate(nodes) for b in nodes[i+1:]]
    base=make_case(nodes,edges,2,[1]*4,[0]*4,nodes,serial=71)
    values={(r.node,r.own,r.exposure):'1/2' for r in base['information']['first'].values}
    set_common_information(base,values=values,bounds_kind='CONDITIONAL_MEAN')
    return [set_common_information(deepcopy(base),bounds=b) for b in
            ((F(1,2),F(1,2)),(F(1,4),F(3,4)),(F(0),F(1)))]


def joint_review(p, r):
    return entry.ReviewedBoundedContrast(**entry.worksheet(p['bundle'],p['raw'],query_id='q1',
        packet=r['packet'],context=r['context'],information=p['information']),
        reviewer='Independent synthetic comparison reviewer',
        evidence='Ordered original target, common exact information and all-scope bounds explicitly reviewed',
        reviewed_direction_and_common_population=True,reviewed_complete_common_a4_model=True,
        reviewed_scientific_bounds_and_no_extra_constraints=True,synthetic_fixture=True)


def run_payload(p):
    prepared=entry.prepare(p['bundle'],p['raw'],query_id='q1')
    if prepared['state']!='REVIEW_REQUIRED':return prepared
    try:
        r=reviews(p);j=joint_review(p,r);mode=p.get('review_mode')
        if mode=='missing_joint_review':j=None
        if mode=='stale_joint_review':j=j.model_copy(update={'information_sha256':'0'*64})
        if mode=='missing_assignment_review':r['assignment_review']=None
        if mode=='missing_business_intent':
            c=r['context']['second'];b=c.core_port.bindings['q1']
            c.core_port.bindings['q1']=replace(b,business_intent=None)
        if mode=='missing_scientific_review':
            c=r['context']['second'];b=c.core_port.bindings['q1']
            c.core_port.bindings['q1']=replace(b,admission=b.admission.model_copy(update={'approved_scientific_binding':None}))
        return entry.submit(p['bundle'],p['raw'],query_id='q1',information=p['information'],joint_review=j,**r)
    except BoundedPolicyUnavailable as exc:
        return dict(prepared,state=exc.state,reason_code=exc.reason)


class BoundedContrastReference:
    route_id=entry.ROUTE

    def cases(self):
        nodes=list('ABCD');chain=list(zip(nodes[:-1],nodes[1:]))
        cases=[('both_endpoints_point',make_case(nodes,chain,2,[1,1,0,0],[0,0,1,1],nodes,serial=70)),
               ('partial_contrast',make_case(nodes,chain,2,[1]*4,[0]*4,nodes,serial=70)),
               ('same_unknown_policy_cancels',make_case(nodes,chain,2,[1]*4,[1]*4,nodes,serial=70))]
        p=make_case(nodes,[('A','B')],1,[1,1,1,0],[1,1,0,0],['A','C'],serial=70)
        set_common_information(p,values={('C',1,0):'3/5',('C',0,0):'1/5'})
        cases.append(('different_policies_cancel_unknown',p))
        cases.extend(zip(('ladder_point','ladder_informative_science','ladder_logical_only'),ladder_payloads()))
        for name,p in cases:
            low,high=vertex_reference(p);l0,u0=vertex_reference(p,ignore_a4=True)
            yield AcceptanceCase(name,p,'POINT' if low==high else 'PARTIAL',(str(low),str(high)),low>l0 or high<u0,True)
        for name,state in (('missing_second','NEEDS_INPUT'),('missing_population','NEEDS_INPUT'),
            ('assignment_conflict','NEEDS_INPUT'),('missing_joint_review','REVIEW_REQUIRED'),
            ('stale_joint_review','CHECK_BLOCKED'),('missing_assignment_review','REVIEW_REQUIRED'),
            ('missing_business_intent','CHECK_BLOCKED'),('missing_scientific_review','CHECK_BLOCKED'),
            ('incompatible_a4','INCOMPATIBLE'),('different_numeric_model','CHECK_BLOCKED')):
            p=deepcopy(cases[1][1]);p['review_mode']=name
            if name=='missing_second':p['raw']['reading']['questions']['q1']['second']['D']=None
            if name=='missing_population':p['raw']['reading']['questions']['q1']['population']=None
            if name=='assignment_conflict':p['raw']['reported_assignment']['reported_conflict']=True
            if name=='incompatible_a4':set_common_information(p,values={('A',0,0):'2'})
            if name=='different_numeric_model':
                info=p['information']['second'];values=list(info.values)
                values[0]=values[0].model_copy(update={'value':'0'})
                p['information']['second']=info.model_copy(update={'values':values})
            yield AcceptanceCase(name,p,state)

    def prepare(self,case):
        return entry.prepare(case.payload['bundle'],case.payload['raw'],query_id='q1')

    def run(self,case):return run_payload(case.payload)
    def certificate(self,result):return result.get('bounded_result')
    def replay(self,case,certificate):
        return replay(certificate,inquiries=case.payload['inquiries'],information=case.payload['information'])

    def tamper(self,case,certificate):
        for name in ('endpoint','ordered_target','shared_world'):
            bad=deepcopy(certificate)
            if name=='endpoint':bad['lower']=str(F(bad['lower'])-1);bad['width']=str(F(bad['upper'])-F(bad['lower']))
            if name=='ordered_target':bad['target_sha256']='0'*64
            if name=='shared_world':bad['cells'][0]['upper_world']='999'
            bad.pop('certificate_sha256');bad['certificate_sha256']=sha(bad)
            yield name,bad
