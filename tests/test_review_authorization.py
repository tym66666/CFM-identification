"""v2.9.2 business semantic gate and explicit approval negative examples."""
from __future__ import annotations
from dataclasses import replace
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from cfm_id_bridge.bridge import FormalQueryBindingV29,run_verified_multiquery_v29
from cfm_id_bridge.scientific_binding import ApprovedScienceBindingV291,proposed_binding_snapshot_v291,sha
from cfm_id_bridge.business_intent import ApprovedBusinessIntentV292
from examples.llm_core_fixture import reviewed_case,bindings
from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
from cfm_id_llm.orchestration_schemas import canonical_sha256

class V292BusinessIntegrity(unittest.TestCase):
    def setUp(self):
        self.case,self.reviewed=reviewed_case()
        self.arm,self.policy=bindings(self.case,self.reviewed)

    def _point(self,b):
        return run_verified_multiquery_v29(self.case,self.reviewed,(b,)).results[1]

    def test_original_business_and_science_are_point(self):
        x=self._point(self.policy)
        self.assertEqual((x.status,x.route),('POINT','R1B_FULL_ASSIGNMENT'))

    def test_old_approved_binding_without_business_intent_is_rejected(self):
        b=replace(self.policy,business_intent=None)
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as core:
            x=self._point(b)
        self.assertEqual((x.status,x.reason_code),('INCOMPATIBLE','V292_BUSINESS_TARGET_CONTRACT_REJECTED'))
        core.assert_not_called()

    def test_reapproving_wrong_policy_science_cannot_bypass_business_contract(self):
        changed=replace(self.policy.inquiry,target=fixed_policy_target_from_context(
            self.policy.inquiry.study,(1,0,0),authority='TRUSTED_FIXTURE'))
        a=self.policy.admission.model_copy(update={
            'formal_target_fingerprint':changed.target.target_digest})
        # Simulate a fresh *SCIENCE* approval for (1,0,0), not tampering with
        # already approved science. This was the follow-up bug in v2.9.1.
        q=self.reviewed.report.draft.queries[1]
        worksheet=proposed_binding_snapshot_v291(changed,
          business_review_sha256=sha(self.reviewed.human_review),
          target_sha256=canonical_sha256(q.target),
          business_quote=q.target.description.evidence[0].quote,
          a4_reference=a.a4_population_operator_reference,
          a5_reference=a.a5_assumption_reference,
          theorem_route='R1B_FULL_ASSIGNMENT',reviewer=a.scientific_reviewer,
          evidence=a.evidence_reference)
        fresh_science=ApprovedScienceBindingV291.model_validate({**worksheet,
            'reviewer_confirmed_exact_coordinates':True,
            'reviewer_confirmed_sources_and_licenses':True})
        a=a.model_copy(update={'approved_scientific_binding':fresh_science})
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as core:
            result=self._point(FormalQueryBindingV29(a,changed,self.policy.business_intent))
        self.assertEqual((result.status,result.reason_code),
                        ('INCOMPATIBLE','V292_BUSINESS_TARGET_CONTRACT_REJECTED'))
        core.assert_not_called()

    def test_unapproved_worksheet_is_not_a_valid_approval(self):
        ap=self.policy.admission.approved_scientific_binding
        d=ap.model_dump(mode='json')
        d.pop('reviewer_confirmed_exact_coordinates')
        d.pop('reviewer_confirmed_sources_and_licenses')
        with self.assertRaises(ValidationError):ApprovedScienceBindingV291.model_validate(d)
        d2=ap.model_dump(mode='json')
        d2['reviewer_confirmed_exact_coordinates']=False
        with self.assertRaises(ValidationError):ApprovedScienceBindingV291.model_validate(d2)

    def test_business_intent_confirmation_cannot_be_omitted(self):
        d=self.policy.business_intent.model_dump(mode='json')
        d.pop('reviewer_confirmed_coordinates')
        with self.assertRaises(ValidationError):ApprovedBusinessIntentV292.model_validate(d)

    def test_wrong_independent_business_coordinates_rejected(self):
        d=self.policy.business_intent.model_dump(mode='json')
        d['binding_coordinates']['assignment']=[0,0,0]
        malformed=ApprovedBusinessIntentV292.model_validate(d)
        b=replace(self.policy,business_intent=malformed)
        x=self._point(b)
        self.assertEqual(x.status,'INCOMPATIBLE')

    def test_tampered_business_source_quote_rejected(self):
        bad=self.policy.business_intent.model_copy(update={'business_quote':'user requested a different target'})
        x=self._point(replace(self.policy,business_intent=bad))
        self.assertEqual(x.status,'INCOMPATIBLE')

    def test_business_intent_cannot_smuggle_extra_unreviewed_coordinates(self):
        d=self.policy.business_intent.model_dump(mode='json')
        d['binding_coordinates']['other_claim']=123
        with self.assertRaises(ValidationError):ApprovedBusinessIntentV292.model_validate(d)

    def test_science_text_is_not_independent_business_contract(self):
        # A textual science review alone never provides a business-coordinate license.
        no_intent=replace(self.policy,business_intent=None)
        a=no_intent.admission.model_copy(update={'math_target_description':
                  'Business said all team use AI, which scientist claims was reviewed'})
        x=self._point(replace(no_intent,admission=a))
        self.assertEqual(x.status,'INCOMPATIBLE')

    def test_scientific_evidence_record_required_even_with_valid_science(self):
        b=replace(self.policy,evidence_manifest=None)
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as core:
            result=self._point(b)
        self.assertEqual((result.status,result.reason_code),
                         ('INCOMPATIBLE','V292_EVIDENCE_BINDING_REJECTED'))
        core.assert_not_called()

    def test_simultaneously_rewriting_both_a4_narratives_without_evidence_fails(self):
        other='ANOTHER_POPULATION_DATASET_REFERENCE'
        admission=self.policy.admission
        approved=admission.approved_scientific_binding.model_copy(update={
            'approved_a4_reference':other})
        a=admission.model_copy(update={
            'a4_population_operator_reference':other,
            'approved_scientific_binding':approved})
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as core:
            r=self._point(replace(self.policy,admission=a))
        self.assertEqual((r.status,r.reason_code),
                         ('INCOMPATIBLE','V292_EVIDENCE_BINDING_REJECTED'))
        core.assert_not_called()

    def test_simultaneously_rewriting_both_a5_narratives_without_evidence_fails(self):
        other='ANOTHER_CAUSAL_ASSUMPTION_REFERENCE'
        admission=self.policy.admission
        approved=admission.approved_scientific_binding.model_copy(update={
            'approved_a5_reference':other})
        a=admission.model_copy(update={
            'a5_assumption_reference':other,
            'approved_scientific_binding':approved})
        r=self._point(replace(self.policy,admission=a))
        self.assertEqual((r.status,r.reason_code),
                         ('INCOMPATIBLE','V292_EVIDENCE_BINDING_REJECTED'))

    def test_evidence_digest_mismatch_rejected_before_theorem(self):
        m=self.policy.evidence_manifest.model_dump(mode='json')
        m['a4_evidence_record']='some revised scientific materials that were not reviewed'
        from cfm_id_bridge.evidence import ReviewedScientificEvidenceV292
        with self.assertRaises(ValidationError): ReviewedScientificEvidenceV292.model_validate(m)

    def test_evidence_reviewer_confirmed_cannot_be_omitted(self):
        from cfm_id_bridge.evidence import ReviewedScientificEvidenceV292
        m=self.policy.evidence_manifest.model_dump(mode='json')
        m.pop('reviewer_confirmed_evidence_link')
        with self.assertRaises(ValidationError):ReviewedScientificEvidenceV292.model_validate(m)

    def test_point_result_carries_binding_hashes_not_just_science_snapshot(self):
        r=self._point(self.policy)
        self.assertEqual(r.status,'POINT')
        self.assertRegex(r.business_intent_sha256,r'^[0-9a-f]{64}$')
        self.assertRegex(r.scientific_evidence_sha256,r'^[0-9a-f]{64}$')

    def test_unverified_business_contract_is_not_numeric_estimation(self):
        out=self._point(self.policy)
        self.assertFalse(out.estimation_handoff_allowed)
        self.assertNotIn('numeric_effect',str(out.identification))
