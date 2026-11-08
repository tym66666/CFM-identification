"""Adversarial integration tests: independent structure, source/license and route.
All scientific sources and causal assumptions are synthetic hypotheses.
"""
import unittest
from dataclasses import replace
from unittest.mock import patch

from cfm_id_bridge.bridge import FormalQueryBindingV29,run_verified_multiquery_v29
from cfm_id_bridge.scientific_binding import proposed_binding_snapshot_v291,sha
from examples.llm_core_fixture import reviewed_case,bindings
from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context


class V291BindingHardening(unittest.TestCase):
    def setUp(self):
        self.case,self.reviewed=reviewed_case()
        self.b1,self.b2=bindings(self.case,self.reviewed)

    def _one(self,b):
        return run_verified_multiquery_v29(self.case,self.reviewed,(b,)).results[1]

    def test_correct_original_synthetic_policy_is_point(self):
        x=self._one(self.b2)
        self.assertEqual((x.status,x.route,x.verification_level),
            ('POINT','R1B_FULL_ASSIGNMENT','CORE_REPLAY_VERIFIED'))

    def test_all_treated_business_cannot_be_rebound_to_one_treated_policy(self):
        altered=replace(self.b2.inquiry,target=fixed_policy_target_from_context(
           self.b2.inquiry.study,(1,0,0),authority='TRUSTED_FIXTURE'))
        admission=self.b2.admission.model_copy(update={
           'formal_target_fingerprint':altered.target.target_digest})
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as solve:
            x=self._one(FormalQueryBindingV29(admission,altered))
        self.assertEqual(x.status,'INCOMPATIBLE');solve.assert_not_called()

    def test_a4_reference_reviewed_string_cannot_be_substituted(self):
        a=self.b2.admission.model_copy(update={
          'a4_population_operator_reference':'UNRELATED_DATA_POPULATION_SOURCE'})
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as solve:
            x=self._one(FormalQueryBindingV29(a,self.b2.inquiry))
        self.assertEqual(x.status,'INCOMPATIBLE');solve.assert_not_called()

    def test_a5_approved_randomization_cannot_be_swapped_for_observational_claim(self):
        a=self.b2.admission.model_copy(update={
          'a5_assumption_reference':'OBSERVATIONAL_EXCHANGEABILITY_ONLY'})
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as solve:
            x=self._one(FormalQueryBindingV29(a,self.b2.inquiry))
        self.assertEqual(x.status,'INCOMPATIBLE');solve.assert_not_called()

    def test_a4_typed_source_provenance_tamper_blocked(self):
        src=self.b2.inquiry.r1b_sources[0]
        tampered=replace(self.b2.inquiry,r1b_sources=(replace(src,provenance='NEW_SOURCE_PROVENANCE'),))
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as solve:
            x=self._one(FormalQueryBindingV29(self.b2.admission,tampered))
        self.assertEqual(x.status,'INCOMPATIBLE');solve.assert_not_called()

    def test_a5_actual_typed_assumption_tamper_blocked(self):
        old=self.b2.inquiry.assumptions[1]
        changed=old.model_copy(update={'evidence':['different scientific assumption evidence']})
        tampered=replace(self.b2.inquiry,assumptions=(self.b2.inquiry.assumptions[0],changed,
                     *self.b2.inquiry.assumptions[2:]))
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as solve:
            x=self._one(FormalQueryBindingV29(self.b2.admission,tampered))
        self.assertEqual(x.status,'INCOMPATIBLE');solve.assert_not_called()

    def test_forged_approval_route_different_from_actual_theorem_blocked(self):
        ap=self.b2.admission.approved_scientific_binding.model_copy(update={
            'approved_theorem_route':'R2_MEAN_SIGNATURE'})
        a=self.b2.admission.model_copy(update={'approved_scientific_binding':ap})
        x=self._one(FormalQueryBindingV29(a,self.b2.inquiry))
        self.assertEqual(x.status,'INCOMPATIBLE')

    def test_legacy_v29_admission_without_exact_binding_must_not_point(self):
        a=self.b2.admission.model_copy(update={'approved_scientific_binding':None})
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as solve:
            x=self._one(FormalQueryBindingV29(a,self.b2.inquiry))
        self.assertEqual(x.status,'INCOMPATIBLE');solve.assert_not_called()

    def test_reviewer_did_not_approve_freshly_changed_human_review(self):
        h=self.reviewed.human_review.model_copy(update={'review_note':'A newer revised business review note'})
        updated=self.reviewed.model_copy(update={'human_review':h})
        v=run_verified_multiquery_v29(self.case,updated,(self.b1,self.b2))
        self.assertTrue(all(x.status=='INCOMPATIBLE' for x in v.results))

    def test_exact_business_quote_was_bound_to_reviewed_target(self):
        ap=self.b2.admission.approved_scientific_binding.model_copy(update={
            'approved_business_quote':'a forged source quotation'})
        a=self.b2.admission.model_copy(update={'approved_scientific_binding':ap})
        x=self._one(FormalQueryBindingV29(a,self.b2.inquiry))
        self.assertEqual(x.status,'INCOMPATIBLE')

    def test_approved_coordinates_including_unit_weights_cannot_change(self):
        target=fixed_policy_target_from_context(self.b2.inquiry.study,(1,1,1),
            authority='TRUSTED_FIXTURE',unit_weights=('1','0','0'))
        inquiry=replace(self.b2.inquiry,target=target)
        a=self.b2.admission.model_copy(update={'formal_target_fingerprint':target.target_digest})
        x=self._one(FormalQueryBindingV29(a,inquiry))
        self.assertEqual(x.status,'INCOMPATIBLE')

if __name__=='__main__':unittest.main()
