"""v0.12 real-Bridge smoke and adversarial test suite.

Uses v2.9.1 as SEPARATE optional dependency, never bundles or modifies it.
When it is absent, real-Core cases are marked SKIPPED, not PASSED.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.trusted_core import (
    ApprovedBusinessMathCrosswalkV012, CandidateSafetyError,
    RealCoreCoveragePortV012,
)

CORE_PRESENT = importlib.util.find_spec('cfm_id_bridge') is not None and importlib.util.find_spec('pfn_pipeline') is not None


class TestV012ContractsWithoutMathCore(unittest.TestCase):
    def setUp(self):
        self.sha='a'*64
        self.template={
            'case_id':'C','input_sha256':self.sha,'draft_sha256':self.sha,'query_id':'q1',
            'business_target_sha256':self.sha,'business_semantics_sha256':self.sha,
            'business_review_sha256':self.sha,'v29_business_review_sha256':self.sha,
            'scientific_admission_sha256':self.sha,'formal_target_sha256':self.sha,
            'formal_target_coordinates':{'classification':'FIXED_POLICY','assignment':[1,1]},
            'a4_sources_sha256':self.sha,'a5_licenses_sha256':self.sha,
            'approved_theorem_route':'R1B_FULL_ASSIGNMENT',
            'approved_business_quote':'all treated','reviewed_by':'Synthetic reviewer',
            'review_evidence':'Manually reviewed coordinates and A4/A5 in this synthetic test',
        }

    def test_requires_both_explicit_approvals(self):
        with self.assertRaises(ValidationError):
            ApprovedBusinessMathCrosswalkV012.model_validate(self.template)

    def test_each_approval_flag_cannot_be_false(self):
        for field in ('reviewer_confirmed_business_to_math','reviewer_confirmed_a4_a5_and_route'):
            d={**self.template,'reviewer_confirmed_business_to_math':True,
               'reviewer_confirmed_a4_a5_and_route':True,field:False}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ApprovedBusinessMathCrosswalkV012.model_validate(d)

    def test_strict_schema_rejects_certificates_or_extra_claims(self):
        d={**self.template,'reviewer_confirmed_business_to_math':True,
           'reviewer_confirmed_a4_a5_and_route':True,'mathematical_certificate':'FAKE'}
        with self.assertRaises(ValidationError):ApprovedBusinessMathCrosswalkV012.model_validate(d)

    def test_production_port_rejects_raw_strings(self):
        with self.assertRaises(CandidateSafetyError):
            RealCoreCoveragePortV012(bindings={'q1':'pretend typed'},crosswalks={'q1':'pretend approval'})

    def test_production_port_rejects_missing_crosswalk(self):
        with self.assertRaises(CandidateSafetyError):
            RealCoreCoveragePortV012(bindings={'q1':'not real'},crosswalks={})

    def test_import_is_optional_and_does_not_import_mathematics(self):
        from cfm_id_llm import trusted_core
        self.assertTrue(hasattr(trusted_core,'RealCoreCoveragePortV012'))

    def test_blank_coordinates_rejected(self):
        d={**self.template,'reviewer_confirmed_business_to_math':True,
           'reviewer_confirmed_a4_a5_and_route':True,'formal_target_coordinates':{}}
        with self.assertRaises(ValidationError):ApprovedBusinessMathCrosswalkV012.model_validate(d)


@unittest.skipUnless(CORE_PRESENT, 'SEPARATE v2.9.1 REAL Core is NOT installed; integration NOT tested')
class TestV012RealCoreAdversarial(unittest.TestCase):
    def setUp(self):
        from examples.run_candidate_real_core import synthetic_env
        self.case,self.quality,self.review,self.port=synthetic_env(off_support=True)

    def lookup(self, query='q2'):
        return self.port.lookup(case=self.case, quality=self.quality,
                                review=self.review,query_id=query)

    def test_real_r1a_arm_point_replay(self):
        c=self.lookup('q1')
        self.assertEqual(c.status,'POINT')
        self.assertEqual(c.fallback,'NOT_NEEDED')
        self.assertEqual(self.port.last_real_results['q1']['verification_level'],'CORE_REPLAY_VERIFIED')

    def test_real_r1b_off_support(self):
        c=self.lookup('q2')
        self.assertEqual(c.status,'UNSUPPORTED')
        self.assertEqual(c.reason_code,'OFF_SUPPORT_ALTERNATE_THEOREM')
        self.assertEqual(c.fallback,'ELIGIBLE_NOT_EXECUTED')
        self.assertEqual(c.source_mode,'PRODUCTION')
        self.assertTrue(c.formal_target_sha256)
        self.assertTrue(c.business_math_crosswalk_sha256)

    def test_production_from_real_bridge_not_external_json(self):
        c=self.lookup('q2')
        self.assertEqual(c.business_review_sha256,self.review.fingerprint())
        self.assertEqual(c.business_math_crosswalk_sha256,self.port.crosswalks['q2'].fingerprint())
        self.assertNotIn('mock',c.core_version.lower())

    def test_supported_pair_real_r1b_point(self):
        from examples.run_candidate_real_core import synthetic_env
        case,quality,review,port=synthetic_env(off_support=False)
        q2=port.lookup(case=case,quality=quality,review=review,query_id='q2')
        self.assertEqual(q2.status,'POINT')
        self.assertEqual(port.last_real_results['q2']['verification_level'],'CORE_REPLAY_VERIFIED')

    def test_candidate_reasoner_only_called_on_actual_gap(self):
        from examples.run_candidate_real_core import run_example
        *_,report,calls,lookups,core=run_example(off_support=True)
        self.assertEqual([q.status for q in report.results],['BLOCKED','UNDETERMINED_UNVERIFIED'])
        self.assertEqual(calls,1)
        self.assertEqual(lookups,['q1','q2'])
        self.assertEqual(core['q1']['status'],'POINT')
        self.assertEqual(core['q2']['status'],'UNSUPPORTED')
        self.assertEqual(report.results[1].mode,'TRUSTED_CORE_GAP')
        self.assertFalse(report.estimation_handoff_allowed)
        self.assertIsNone(report.results[1].mathematical_certificate)

    def test_supported_pair_no_candidate_calls(self):
        from examples.run_candidate_real_core import run_example
        *_,report,calls,lookups,core=run_example(off_support=False)
        self.assertEqual([q.status for q in report.results],['BLOCKED','BLOCKED'])
        self.assertEqual(calls,0)
        self.assertEqual(core['q2']['status'],'POINT')

    def test_unapproved_worksheet_does_not_convert(self):
        from cfm_id_llm.trusted_core import unapproved_crosswalk_worksheet_v012
        paper=unapproved_crosswalk_worksheet_v012(case=self.case,quality=self.quality,
            business_review=self.review,query_id='q2',formal_binding=self.port.bindings['q2'],
            reviewer='Researcher placeholder',evidence='Reviewer has not approved this worksheet')
        self.assertNotIn('reviewer_confirmed_business_to_math',paper)
        with self.assertRaises(ValidationError):ApprovedBusinessMathCrosswalkV012.model_validate(paper)

    def test_business_source_change_blocks_before_core(self):
        self.case.business_question+=' 多余修改'
        with self.assertRaises(CandidateSafetyError):self.lookup()
        self.assertEqual(self.port.calls,[])

    def test_stale_business_review_blocks(self):
        self.review=self.review.model_copy(update={'review_note':'Changed business review after science'})
        with self.assertRaises(CandidateSafetyError):self.lookup()
        self.assertEqual(self.port.calls,[])

    def test_semantics_hash_crosswalk_modified_blocks(self):
        approval=self.port.crosswalks['q2']
        self.port.crosswalks['q2']=approval.model_copy(update={'business_semantics_sha256':'1'*64})
        with self.assertRaises(CandidateSafetyError):self.lookup()
        self.assertEqual(self.port.calls,[])

    def test_policy_coordinates_crosswalk_modified_blocks(self):
        approval=self.port.crosswalks['q2']
        bad=copy.deepcopy(approval.formal_target_coordinates)
        bad['assignment']=[1,0,0]
        self.port.crosswalks['q2']=approval.model_copy(update={'formal_target_coordinates':bad})
        with self.assertRaises(CandidateSafetyError):self.lookup()
        self.assertEqual(self.port.calls,[])

    def test_wrong_a4_source_digest_blocks(self):
        a=self.port.crosswalks['q2']
        self.port.crosswalks['q2']=a.model_copy(update={'a4_sources_sha256':'1'*64})
        with self.assertRaises(CandidateSafetyError):self.lookup()

    def test_wrong_a5_license_digest_blocks(self):
        a=self.port.crosswalks['q2']
        self.port.crosswalks['q2']=a.model_copy(update={'a5_licenses_sha256':'1'*64})
        with self.assertRaises(CandidateSafetyError):self.lookup()

    def test_wrong_route_blocks(self):
        a=self.port.crosswalks['q2']
        self.port.crosswalks['q2']=a.model_copy(update={'approved_theorem_route':'R2_MEAN_SIGNATURE'})
        with self.assertRaises(CandidateSafetyError):self.lookup()

    def test_science_approval_flags_must_have_been_explicitly_set(self):
        from cfm_id_bridge.bridge import FormalQueryBindingV29
        from cfm_id_bridge.scientific_binding import ApprovedScienceBindingV291
        b=self.port.bindings['q2']
        approved=b.admission.approved_scientific_binding
        unapproved=approved.model_dump(mode='json')
        unapproved.pop('reviewer_confirmed_exact_coordinates')
        unapproved.pop('reviewer_confirmed_sources_and_licenses')
        # The current math Core schema itself rejects omitted approval fields.
        with self.assertRaises(ValidationError):
            ApprovedScienceBindingV291.model_validate(unapproved)
        self.assertEqual(self.port.calls,[])

    def test_crosswalk_flags_mutated_after_construction_block(self):
        # Pydantic without validate_assignment allows accidental post-review mutation.
        self.port.crosswalks['q2'].reviewer_confirmed_business_to_math=False
        with self.assertRaises(CandidateSafetyError):self.lookup()
        self.assertEqual(self.port.calls,[])

    def test_science_flags_mutated_after_construction_block(self):
        b=self.port.bindings['q2']
        b.admission.approved_scientific_binding.reviewer_confirmed_exact_coordinates=False
        with self.assertRaises(CandidateSafetyError):self.lookup()
        self.assertEqual(self.port.calls,[])

    def test_missing_science_approval_blocks(self):
        from cfm_id_bridge.bridge import FormalQueryBindingV29
        b=self.port.bindings['q2']
        self.port.bindings['q2']=FormalQueryBindingV29(
            b.admission.model_copy(update={'approved_scientific_binding':None}), b.inquiry)
        with self.assertRaises(CandidateSafetyError):self.lookup()

    def test_missing_typed_binding_blocks(self):
        del self.port.bindings['q2']
        with self.assertRaises(CandidateSafetyError):self.lookup()

    def test_candidate_report_stays_unverified_on_real_gap(self):
        from examples.run_candidate_real_core import run_example
        *_,report,calls,lookups,core=run_example(off_support=True)
        self.assertEqual(report.mathematical_verification,'NOT_PERFORMED')
        q=report.results[1]
        self.assertEqual(q.verification_level,'LLM_UNVERIFIED')
        self.assertFalse(q.estimation_handoff_allowed)
        self.assertIsNone(q.mathematical_certificate)

    def test_mismatched_policy_even_with_fresh_approval_is_rejected(self):
        from cfm_id_bridge.bridge import FormalQueryBindingV29, formal_target_fingerprint_v29
        from cfm_id_bridge.scientific_binding import ApprovedScienceBindingV291,proposed_binding_snapshot_v291,sha
        from cfm_id_llm.trusted_core import unapproved_crosswalk_worksheet_v012
        from pfn_pipeline.identification_business import FixedPolicyInquiryV21
        from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
        from cfm_id_llm.trusted_core import v29_review_from_v011
        b=self.port.bindings['q2']
        altered_target=fixed_policy_target_from_context(b.inquiry.study,(1,0,0),authority='TRUSTED_FIXTURE')
        altered=FixedPolicyInquiryV21(study=b.inquiry.study,target=altered_target,
            assumptions=b.inquiry.assumptions,r1b_sources=b.inquiry.r1b_sources)
        sc=b.admission.model_copy(update={'formal_target_fingerprint':formal_target_fingerprint_v29(altered)})
        reviewer=v29_review_from_v011(self.review,legacy_draft_sha256=self.quality.legacy_audit.draft_sha256)
        q=self.quality.draft.queries[1]
        sheet=proposed_binding_snapshot_v291(altered,business_review_sha256=sha(reviewer),
            target_sha256=canonical_sha256(q.target),business_quote=q.target.description.evidence[0].quote,
            a4_reference=sc.a4_population_operator_reference,a5_reference=sc.a5_assumption_reference,
            theorem_route='R1B_FULL_ASSIGNMENT',reviewer=sc.scientific_reviewer,
            evidence=sc.evidence_reference)
        sheet.update(reviewer_confirmed_exact_coordinates=True,
                     reviewer_confirmed_sources_and_licenses=True)
        sc=sc.model_copy(update={'approved_scientific_binding':ApprovedScienceBindingV291.model_validate(sheet)})
        new_binding=FormalQueryBindingV29(sc,altered,
            business_intent=b.business_intent, evidence_manifest=b.evidence_manifest)
        cw=unapproved_crosswalk_worksheet_v012(case=self.case,quality=self.quality,
            business_review=self.review,query_id='q2',formal_binding=new_binding,
            reviewer='Different synthetic reviewer',evidence='Incorrect fresh approval tests an exact business mismatch')
        cw.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
        self.port.bindings['q2']=new_binding
        self.port.crosswalks['q2']=ApprovedBusinessMathCrosswalkV012.model_validate(cw)
        with self.assertRaisesRegex(CandidateSafetyError,'All-treated business target|Independent v2.9.2'):
            self.lookup()
        self.assertEqual(self.port.calls,[])


if __name__=='__main__':
    unittest.main()
