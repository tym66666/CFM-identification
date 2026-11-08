"""Six-hook integration for the synthetic math backend, not business intake.

The legacy scaffold has no verified-INCOMPATIBLE proof hook; Farkas proofs are
accepted separately in test_mean_order*. New explicit informativeness is tested
there too, not mapped to the scaffold's ambiguous legacy informative field.
"""
from copy import deepcopy
from fractions import Fraction as F
from cfm_id_bridge.scientific_binding import sha
from cfm_id import mean_order as entry
from cfm_id.mean_order_verify import replay
from cfm_id.mean_order_contract import MeanOrderProblem
from evaluation.partial_extension_acceptance import AcceptanceCase
from examples.mean_order_fixture import make_problem, synthetic_review


class MeanOrderReference:
    route_id='MEAN_ORDER_D2_E1_SYNTHETIC_MATH'

    def cases(self):
        for mode,bounds in [('BOTH',('1/5','1')),('OWN',('-1/5','1')),('NONE',('-1','1'))]:
            yield AcceptanceCase('ladder_'+mode,dict(problem=make_problem(mode=mode)),'PARTIAL',bounds,None,True)
        yield AcceptanceCase('nonzero_point',dict(problem=make_problem(first=[1,1,0,0],second=[0,0,1,1],
            weights=['1','0','0','0'])),'POINT',('1/5','1/5'),None,True)
        p=make_problem(nodes=['A','B'],edges=[['A','B']],quota=1,weights=['1','0'],
            values=[dict(node='B',own=1,exposure=0,value='1/2'),dict(node='B',own=0,exposure=1,value='1/2')])
        yield AcceptanceCase('joint_order_counterexample',dict(problem=p),'PARTIAL',('0','1'),None,True)
        for mode,state in [('missing','REVIEW_REQUIRED'),('stale','CHECK_BLOCKED')]:
            yield AcceptanceCase(mode+'_review',dict(problem=make_problem(),review_mode=mode),state)
        p=make_problem(first=[1,1,0,0],second=[0,0,1,1],weights=['1','0','0','0'])
        p=MeanOrderProblem.model_validate(p.model_dump()|{'values':[v.model_dump() for v in p.values if v.node!='A']})
        yield AcceptanceCase('missing_supported_target_a4',dict(problem=p),'NEEDS_INPUT')
        bad=make_problem(); bad.first.pop()
        yield AcceptanceCase('incomplete_target',dict(problem=bad),'CHECK_BLOCKED')

    def prepare(self,case): return entry.prepare(case.payload['problem'])
    def run(self,case):
        p=case.payload['problem']; mode=case.payload.get('review_mode')
        if self.prepare(case)['state']=='CHECK_BLOCKED': return self.prepare(case)
        review=synthetic_review(p)
        if mode=='missing':review=None
        if mode=='stale':review=review.model_copy(update={'problem_sha256':'0'*64})
        return entry.submit(p,review=review,synthetic_protocol_selected=True)
    def certificate(self,result): return result.get('bounded_result')
    def replay(self,case,certificate): return replay(certificate,problem=case.payload['problem'])
    def tamper(self,case,certificate):
        for kind in ('endpoint','input','world','unknown_dual'):
            c=deepcopy(certificate)
            if kind=='endpoint':c['lower']=str(F(c['lower'])-1)
            if kind=='input':c['input_sha256']='0'*64
            if kind=='world':c['cells'][0]['lower_world']='999'
            if kind=='unknown_dual':c['lower_dual']={'nonexistent-row':'1'}
            c.pop('certificate_sha256'); c['certificate_sha256']=sha(c)
            yield kind,c
