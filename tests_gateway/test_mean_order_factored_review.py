"""Independent synthetic assertions test binding; no LLM or credential access."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from cfm_id_bridge.scientific_binding import sha
from examples.mean_order_business_fixture import make_case,endpoint_reviews,business_review
from cfm_id import mean_order_business as legacy
from evaluation import mean_order_factored_reading as protocol
from evaluation import mean_order_factored_review as adapter

class FactoredReviewTests(unittest.TestCase):
    def setUp(self):
        self.c=make_case()
        self.bundle=self.c['bundle']
        self.wire=protocol.reference_wire(self.bundle,self.c['candidate'])
        self.chain=endpoint_reviews(self.c,self.c['candidate'])
        self.old=business_review(self.c,self.c['candidate'],self.chain)
        self.review=self.make_review(self.wire,self.old)

    def make_review(self,wire,old):
        return adapter.ReviewedFactoredReading(
            **adapter.worksheet(self.bundle,wire,legacy_review=old),
            reviewer='Independent synthetic reader',
            evidence='Explicit assertion for fixture testing, not automatic scientific approval',
            reviewed_full_wire_semantics_and_sources=True,
            reviewed_projection_and_losses=True,synthetic_fixture=True)

    def call(self,wire=None,old=None,new=None,chain=None):
        return adapter.submit(self.bundle,self.wire if wire is None else wire,query_id='q1',
            science=self.c['science'],review=self.old if old is None else old,
            factored_review=self.review if new is None else new,**(self.chain if chain is None else chain))

    def test_explicit_both_reviews_replay_and_preserve_wire(self):
        before=deepcopy(self.wire);out=self.call()
        self.assertEqual(out['state'],'PARTIAL')
        self.assertEqual([out['bounded_result']['lower'],out['bounded_result']['upper']],['1/5','1'])
        self.assertTrue(out['bounded_certificate_replayed']);self.assertTrue(out['factored_review_checked'])
        self.assertEqual(out['wire_candidate'],before);self.assertEqual(self.wire,before)
        self.assertFalse(out['production_admission']);self.assertFalse(out['scientific_approval'])

    def test_legacy_review_alone_cannot_pass_new_gate(self):
        with patch.object(legacy,'submit',side_effect=AssertionError('must not call legacy submit')):
            out=adapter.submit(self.bundle,self.wire,query_id='q1',science=self.c['science'],
                review=self.old,**self.chain)
        self.assertEqual(out['state'],'REVIEW_REQUIRED');self.assertFalse(out['core_called'])

    def test_new_review_does_not_replace_legacy_review_or_explicit_selection(self):
        for options in ({'review':None,'synthetic_protocol_selected':True},
                        {'review':self.old,'synthetic_protocol_selected':False}):
            chain=dict(self.chain);chain.update(options)
            with patch.object(legacy,'submit',side_effect=AssertionError('must not call')):
                out=adapter.submit(self.bundle,self.wire,query_id='q1',science=self.c['science'],
                    factored_review=self.review,**chain)
            self.assertEqual(out['state'],'REVIEW_REQUIRED');self.assertFalse(out['core_called'])

    def test_projection_collision_detected_by_full_wire_binding(self):
        observed=deepcopy(self.wire)
        observed['order_reading']['claims'][1].update(declaration='仅报告观察',quantity='历史样本统计',scope='HISTORICAL_SUPPORT')
        unclear=deepcopy(observed);unclear['order_reading']['claims'][1]['quantity']='尚不明确'
        projected=protocol.to_canonical(self.bundle,observed)
        self.assertEqual(projected,protocol.to_canonical(self.bundle,unclear))
        # A synthetic record about this blocked reading is not a valid science
        # admission; it only lets us test that identical legacy projections
        # cannot reuse the original full-wire attestation.
        old=self.old.model_copy(update={'candidate_sha256':sha(projected)})
        review=self.make_review(observed,old)
        adapter.validate_review(self.bundle,observed,legacy_review=old,review=review)
        with self.assertRaises(ValueError):
            adapter.validate_review(self.bundle,unclear,legacy_review=old,review=review)
        for wire in (observed,unclear):
            with patch.object(legacy,'submit',side_effect=AssertionError('blocked reading')):
                out=self.call(wire,old=old,new=review)
            self.assertEqual(out['state'],'NEEDS_INPUT');self.assertFalse(out['core_called'])

    def test_modified_full_wire_cannot_reuse_review_even_with_new_legacy_review(self):
        changed=deepcopy(self.wire);changed['order_reading']['claims'].reverse()
        new_canonical=protocol.to_canonical(self.bundle,changed)
        new_chain=endpoint_reviews(self.c,new_canonical)
        new_old=business_review(self.c,new_canonical,new_chain)
        with patch.object(legacy,'submit',side_effect=AssertionError('stale full-wire review')):
            out=self.call(changed,old=new_old,new=self.review,chain=new_chain)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['core_called'])
        fresh=self.make_review(changed,new_old)
        self.assertEqual(self.call(changed,old=new_old,new=fresh,chain=new_chain)['state'],'PARTIAL')

    def test_legacy_review_record_changed_requires_new_binding(self):
        old=self.old.model_copy(update={'evidence':self.old.evidence+' changed review record'})
        with patch.object(legacy,'submit',side_effect=AssertionError('stale review linkage')):
            out=self.call(old=old)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['core_called'])

    def test_bundle_changed_is_not_silently_rebound(self):
        changed=deepcopy(self.bundle);changed['documents']['extra.txt']='A later note.'
        with self.assertRaises(ValueError):
            adapter.validate_review(changed,self.wire,legacy_review=self.old,review=self.review)

    def test_pending_axis_in_legacy_review_still_blocks_after_new_binding(self):
        decisions=dict(self.old.axis_decisions);decisions[next(iter(decisions))]='PENDING'
        old=self.old.model_copy(update={'axis_decisions':decisions})
        new=self.make_review(self.wire,old);out=self.call(old=old,new=new)
        self.assertTrue(out['factored_review_checked']);self.assertEqual(out['state'],'REVIEW_REQUIRED')
        self.assertFalse(out['core_called']);self.assertFalse(out['bounded_backend_called'])

    def test_stale_legacy_problem_still_blocked_after_new_binding(self):
        old=self.old.model_copy(update={'problem_sha256':'0'*64});new=self.make_review(self.wire,old)
        out=self.call(old=old,new=new)
        self.assertTrue(out['factored_review_checked']);self.assertEqual(out['state'],'CHECK_BLOCKED')
        self.assertFalse(out['core_called']);self.assertFalse(out['bounded_backend_called'])

    def test_strict_flags_schema_and_typed_separate_record(self):
        for field in ('reviewed_full_wire_semantics_and_sources','reviewed_projection_and_losses','synthetic_fixture'):
            for value in (False,1,'true'):
                bad=self.review.model_dump();bad[field]=value
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    adapter.ReviewedFactoredReading.model_validate(bad)
        with patch.object(legacy,'submit',side_effect=AssertionError('untyped record')):
            out=self.call(new=self.review.model_dump())
        self.assertEqual(out['state'],'CHECK_BLOCKED')
        bad=deepcopy(self.wire);bad['order_reading']['scientific_approval']=True
        self.assertEqual(self.call(bad)['state'],'CHECK_BLOCKED')

if __name__=='__main__':unittest.main()
