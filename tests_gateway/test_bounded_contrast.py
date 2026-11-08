"""Mathematics, nested assumptions and complete review-chain acceptance."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from random import Random
import unittest
from unittest.mock import patch
from cfm_id_bridge.scientific_binding import sha
from cfm_id import bounded_contrast as entry
from cfm_id.bounded_contrast_solver import solve
from cfm_id.bounded_contrast_verify import replay
from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable
from evaluation.partial_extension_acceptance import evaluate
from examples.bounded_contrast_fixture import make_case, reviews
from examples.partial_contrast_reference import (
    BoundedContrastReference, vertex_reference, ladder_payloads, run_payload, joint_review,
)


def remove_a4(p, coord):
    for side in ('first','second'):
        q=p['inquiries'][side];s=q.r2_sources[0]
        source=replace(s,signature_cells=tuple(c for c in s.signature_cells if c!=coord))
        q=replace(q,r2_sources=(source,));p['inquiries'][side]=q
        info=p['information'][side]
        p['information'][side]=info.model_copy(update={'inquiry_sha256':sha(q),'source_sha256':sha(source),
            'values':[r for r in info.values if (r.node,r.own,r.exposure)!=coord]})


def small(first=None, second=None):
    return make_case(list('ABCD'), [('A','B')],1,
        [1,1,1,0] if first is None else first,[1,1,0,0] if second is None else second,['A','C'])


class BoundedContrastTests(unittest.TestCase):
    def test_second_adapter_uses_unchanged_acceptance_framework(self):
        report=evaluate(BoundedContrastReference())
        self.assertEqual(report['cases'],17);self.assertEqual(report['status'],'PASS')
        self.assertEqual(sum(len(r['forged_certificates_rejected']) for r in report['rows']),21)

    def test_two_uncertain_policies_have_identified_difference(self):
        case=next(c for c in BoundedContrastReference().cases() if c.name=='different_policies_cancel_unknown')
        out=run_payload(case.payload)
        self.assertEqual((out['state'],out['bounded_result']['lower'],out['bounded_result']['upper']),('POINT','1/5','1/5'))
        self.assertTrue(all(r['status']=='UNSUPPORTED' for r in out['point_assessment'].values()))
        self.assertTrue(out['bounded_certificate_replayed'])

    def test_ladder_same_input_target_a4_different_review_and_nested_sharp_sets(self):
        cases=ladder_payloads();sets=[];fixed=[];reviews_hash=[]
        for p in cases:
            fixed.append(sha(dict(bundle=p['bundle'],raw=p['raw'],inquiries=p['inquiries'],
                information={s:p['information'][s].model_dump(exclude={'bounds'}) for s in ('first','second')})))
            out=run_payload(p);c=out['bounded_result']
            self.assertTrue(c['sharp']);self.assertFalse(c['informative'])
            self.assertTrue(out['bounded_certificate_replayed']);reviews_hash.append(out['joint_review_sha256'])
            sets.append((F(c['lower']),F(c['upper'])))
        self.assertEqual(len(set(fixed)),1);self.assertEqual(len(set(reviews_hash)),3)
        self.assertEqual(sets,[(F(0),F(0)),(F(-1,2),F(1,2)),(F(-1),F(1))])
        self.assertTrue(all(a[0]>=b[0] and a[1]<=b[1] for a,b in zip(sets,sets[1:])))

    def test_binary_mean_bound_is_not_almost_sure_bound(self):
        p=ladder_payloads()[0]
        for s in ('first','second'):p['information'][s]=p['information'][s].model_copy(update={'bounds_kind':'ALMOST_SURE_OUTCOME'})
        with self.assertRaises(BoundedPolicyUnavailable) as cm:solve(p['inquiries'],p['information'])
        self.assertEqual(cm.exception.state,'INCOMPATIBLE')

    def test_canceled_supported_missing_mean_allowed_but_active_missing_mean_blocked(self):
        p=small([1,1,1,0],[1,1,1,0]);remove_a4(p,('C',1,0))
        out=run_payload(p)
        self.assertEqual(out['state'],'POINT');self.assertEqual(out['bounded_result']['lower'],'0')
        p=small();remove_a4(p,('C',1,0))
        out=run_payload(p)
        self.assertEqual(out['state'],'NEEDS_INPUT');self.assertFalse(out['bounded_backend_called'])

    def test_cancellation_cannot_bypass_missing_science_even_with_fresh_joint_record(self):
        p=small([1,1,1,0],[1,1,1,0]);r=reviews(p)
        c=r['context']['second'];b=c.core_port.bindings['q1']
        c.core_port.bindings['q1']=replace(b,admission=b.admission.model_copy(update={'approved_scientific_binding':None}))
        j=joint_review(p,r)
        out=entry.submit(p['bundle'],p['raw'],query_id='q1',information=p['information'],joint_review=j,**r)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['bounded_backend_called'])

    def test_withdrawing_sufficiency_not_silently_treated_as_box(self):
        from pfn_pipeline._internal.identification.schemas import AssumptionStatus
        p=small([1,1,1,0],[1,1,1,0])
        for s in ('first','second'):
            q=p['inquiries'][s];suff=q.r2_sufficiency
            q=replace(q,r2_sufficiency=replace(suff,assumption=suff.assumption.model_copy(update={'confirmed':False,'status':AssumptionStatus.UNRESOLVED})))
            p['inquiries'][s]=q;p['information'][s]=p['information'][s].model_copy(update={'inquiry_sha256':sha(q)})
        with self.assertRaises(BoundedPolicyUnavailable):solve(p['inquiries'],p['information'])

    def test_extra_monotonicity_not_dropped(self):
        from pfn_pipeline._internal.identification.schemas import Assumption
        p=small()
        for s in ('first','second'):
            q=p['inquiries'][s];q=replace(q,assumptions=q.assumptions+(Assumption(name='monotone_treatment_response',source='demo_specification',confirmed=True,status='ADMITTED',evidence=['Explicit extra scientific restriction']),))
            p['inquiries'][s]=q;p['information'][s]=p['information'][s].model_copy(update={'inquiry_sha256':sha(q)})
        with self.assertRaises(BoundedPolicyUnavailable) as cm:solve(p['inquiries'],p['information'])
        self.assertEqual(cm.exception.state,'UNSUPPORTED')

    def test_sample_information_never_becomes_exact(self):
        p=small()
        for s in ('first','second'):
            q=p['inquiries'][s];source=replace(q.r2_sources[0],availability='FINITE_SAMPLE_ESTIMATE')
            q=replace(q,r2_sources=(source,));p['inquiries'][s]=q
            p['information'][s]=p['information'][s].model_copy(update={'inquiry_sha256':sha(q),'source_sha256':sha(source)})
        with self.assertRaises(BoundedPolicyUnavailable) as cm:solve(p['inquiries'],p['information'])
        self.assertEqual(cm.exception.state,'NEEDS_INPUT')

    def test_no_result_before_review_and_no_result_if_independent_replay_fails(self):
        p=small();r=reviews(p)
        prepared=entry.prepare(p['bundle'],p['raw'],query_id='q1',information=p['information'],packet=r['packet'],context=r['context'])
        self.assertEqual(prepared['state'],'REVIEW_REQUIRED');self.assertFalse(prepared['bounded_backend_called'])
        self.assertNotIn('bounded_result',prepared)
        j=joint_review(p,r)
        with patch.object(entry,'replay',return_value=False):
            out=entry.submit(p['bundle'],p['raw'],query_id='q1',information=p['information'],joint_review=j,**r)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertNotIn('bounded_result',out)
        self.assertFalse(out['bounded_certificate_replayed'])

    def test_model_and_direction_changes_invalidate_existing_review(self):
        p=small();r=reviews(p);j=joint_review(p,r)
        changed=deepcopy(p['raw']);q=changed['reading']['questions']['q1'];q['first'],q['second']=q['second'],q['first']
        out=entry.submit(p['bundle'],changed,query_id='q1',information=p['information'],joint_review=j,**r)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['bounded_backend_called'])

    def test_nonuniform_math_weights_and_direction_reversal(self):
        p=small()
        for s in ('first','second'):
            q=p['inquiries'][s];q=replace(q,target=replace(q.target,unit_weights=('2/3','0','1/3','0'),target_digest=''))
            p['inquiries'][s]=q;p['information'][s]=p['information'][s].model_copy(update={'inquiry_sha256':sha(q)})
        p['coordinates']['unit_weights']=['2/3','0','1/3','0']
        c=solve(p['inquiries'],p['information']);self.assertEqual((F(c['lower']),F(c['upper'])),vertex_reference(p))
        reverse_q={'first':p['inquiries']['second'],'second':p['inquiries']['first']}
        reverse_i={'first':p['information']['second'],'second':p['information']['first']}
        d=solve(reverse_q,reverse_i)
        self.assertEqual((F(d['lower']),F(d['upper'])),(-F(c['upper']),-F(c['lower'])))
        self.assertTrue(replay(d,inquiries=reverse_q,information=reverse_i))

    def test_varied_graph_quota_policy_and_outcome_against_joint_vertex_enumeration(self):
        rng=Random(20261024)
        for k in range(32):
            n=3+k%3;nodes=[f'N{i}' for i in range(n)]
            edges=[(a,b) for i,a in enumerate(nodes) for b in nodes[i+1:] if rng.random()<.45]
            first=[rng.randrange(2) for _ in nodes];second=[rng.randrange(2) for _ in nodes]
            p=make_case(nodes,edges,k%(n+1),first,second,nodes[::2],serial=k,continuous=bool(k%2))
            c=solve(p['inquiries'],p['information'])
            with self.subTest(case=k):
                self.assertEqual((F(c['lower']),F(c['upper'])),vertex_reference(p))
                self.assertTrue(replay(c,inquiries=p['inquiries'],information=p['information']))


if __name__=='__main__':unittest.main()
