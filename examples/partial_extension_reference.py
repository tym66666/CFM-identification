"""Executable OFFLINE reference using the existing finite theorem, no new math.

Copy the adapter shape, not its D2/E1 assumptions, to develop another theorem.
The synthetic review helpers here are never a production approval mechanism.
"""
from copy import deepcopy
from fractions import Fraction as F
from evaluation.partial_extension_acceptance import AcceptanceCase
from evaluation.bounded_policy_generalization import vertex_extrema
from cfm_id_bridge.scientific_binding import sha
from cfm_id import bounded_policy_intake as intake
from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable
from cfm_id.bounded_policy_verify import replay
from examples.bounded_policy_intake_fixture import make_case,declaration_review,existing_reviews


class BoundedPolicyReference:
    route_id='BOUNDED_POLICY_MEAN_D2_E1'

    def cases(self):
        nodes=['甲','乙','丙','丁'];edges=list(zip(nodes[:-1],nodes[1:]))
        positives=[]
        for name,graph,quota,policy in (
            ('point_observed_policy',edges,2,[1,1,0,0]),
            ('partial_missing_signature',edges,2,[1,1,1,1]),
            ('sharp_but_uninformative',[(a,b) for i,a in enumerate(nodes) for b in nodes[i+1:]],1,[1]*4)):
            b,raw,d,claims,coords=make_case(nodes,graph,quota,policy,nodes,serial=51)
            lo,hi=vertex_extrema(d,coords)
            case=AcceptanceCase(name,dict(bundle=b,raw=raw,declaration=d,claims=claims,coordinates=coords),
                'POINT' if lo==hi else 'PARTIAL',(str(lo),str(hi)),lo>0 or hi<1,True)
            positives.append(case);yield case
        # Fixed scientific bounds can collapse a zero-support interval to a point.
        p=deepcopy(positives[2].payload)
        for v in p['declaration']['information']['values']:v['value']='0'
        for r in p['declaration']['information']['bounds']:r.update(lower='0',upper='0')
        require_zero=vertex_extrema(p['declaration'],p['coordinates'])
        if require_zero!=(F(0),F(0)):raise ValueError('INDEPENDENT_ZERO_BOUND_REFERENCE_FAILED')
        yield AcceptanceCase('point_from_declared_bounds',p,'POINT',('0','0'),False,True)
        for kind,state in (
            ('missing_population','NEEDS_INPUT'),('missing_sufficiency','NEEDS_INPUT'),
            ('missing_review','REVIEW_REQUIRED'),('pending_review','REVIEW_REQUIRED'),
            ('rejected_review','CHECK_BLOCKED'),('stale_review','CHECK_BLOCKED'),
            ('sample_means','NEEDS_INPUT'),('extra_constraint','UNSUPPORTED'),
            ('incompatible_mean','INCOMPATIBLE')):
            p=deepcopy(positives[1].payload);p['review_mode']=kind
            if kind=='missing_population':p['raw']['reading']['questions']['q1']['population']=None
            if kind=='missing_sufficiency':p['declaration']['conditions']=[c for c in p['declaration']['conditions'] if c['name']!='mean_signature_sufficiency']
            if kind=='sample_means':p['declaration']['information']['availability']='FINITE_SAMPLE_ESTIMATE'
            if kind=='extra_constraint':p['declaration']['additional_constraints']=['还有一条跨节点的均值等式，不能丢弃。']
            if kind=='incompatible_mean':p['declaration']['information']['values'][0]['value']='2'
            yield AcceptanceCase(kind,p,state)

    def prepare(self,case):
        p=case.payload
        return intake.prepare(p['bundle'],p['raw'],query_id='q1',declaration=p['declaration'])

    def _review(self,case):
        p=case.payload;mode=p.get('review_mode')
        if mode=='missing_review':return None
        r=declaration_review(p['bundle'],p['raw'],p['declaration'],p['coordinates'])
        if mode in ('pending_review','rejected_review'):
            decisions=dict(r.condition_decisions)
            decisions['mean_signature_sufficiency']='PENDING' if mode=='pending_review' else 'REJECTED'
            r=r.model_copy(update={'condition_decisions':decisions})
        if mode=='stale_review':r=r.model_copy(update={'declaration_sha256':'0'*64})
        return r

    def _compile(self,case):
        p=case.payload
        return intake.compile_reviewed(p['bundle'],p['raw'],query_id='q1',declaration=p['declaration'],
            review=self._review(case),synthetic_protocol_selected=True)

    def run(self,case):
        p=case.payload;out=self.prepare(case)
        if out['state']!='REVIEW_REQUIRED':return out
        try:
            compiled=self._compile(case)
            reviews=existing_reviews(p['bundle'],p['raw'],compiled,p['claims'],p['coordinates'])
            return intake.submit(p['bundle'],p['raw'],query_id='q1',declaration=p['declaration'],
                declaration_review=self._review(case),synthetic_protocol_selected=True,**reviews)
        except BoundedPolicyUnavailable as exc:
            return dict(out,state=exc.state,reason_code=exc.reason)

    def certificate(self,result):
        return result.get('bounded_result')

    def replay(self,case,certificate):
        compiled=self._compile(case)
        return replay(certificate,inquiry=compiled.inquiry,information=compiled.information)

    def tamper(self,case,certificate):
        for name in ('endpoint','target_binding','endpoint_world'):
            bad=deepcopy(certificate)
            if name=='endpoint':
                bad['lower']=str(F(bad['lower'])-1);bad['width']=str(F(bad['upper'])-F(bad['lower']))
            if name=='target_binding':bad['target_sha256']='0'*64
            if name=='endpoint_world':bad['cells'][0]['lower_world']='2'
            # Recompute the outer hash: a checksum alone must not prove the result.
            bad.pop('certificate_sha256');bad['certificate_sha256']=sha(bad)
            yield name,bad

