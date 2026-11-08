"""v0.11 multiquery Candidate Reasoner: route gates, query binding, science scopes.

These are software safety tests using SYNTHETIC CORE and MOCK LLM. They cannot
measure actual LLM theorem reasoning, actual Core coverage, or theorem proofs.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from cfm_id_llm.audit import fingerprint_business_case
from cfm_id_llm.candidate_queries import (
    CandidateReasonerV011, CandidateSafetyError, CandidateProposalV011,
    BusinessQueryReviewV011, CoreCoverageV011, MockCoveragePortV011,
    CandidateBatchReportV011, CandidateQueryReportV011, ApprovedA4ReferenceV011,
    TrustedScienceScopeV011, audit_proposal_v011,
)
from cfm_id_llm.candidate_query_prompts import CANDIDATE_SYSTEM_PROMPT_V011,make_candidate_prompt_v011
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality import MultiQueryQualityReportV010, audit_business_quality
from cfm_id_llm.schemas import BusinessCase, PopulationInformationLevel

ROOT=Path(__file__).resolve().parents[1]
DEMO=ROOT/'assets/candidate_mock_fixtures'


def read(name: str) -> dict | list:
    return json.loads((DEMO/name).read_text(encoding='utf-8'))


class ExampleEnvironment:
    def __init__(self, *, payload: dict | None = None, entries: list | None = None, port=None):
        self.case=BusinessCase.model_validate(read('business_case.json'))
        self.quality=MultiQueryQualityReportV010.model_validate(read('a0_quality_report.json'))
        self.review=BusinessQueryReviewV011.model_validate(read('human_business_review_MOCK.json'))
        self.payload=payload or read('mock_candidate_q2.json')
        self.outcomes=[CoreCoverageV011.model_validate(x) for x in (entries or read('mock_core_coverage.json'))]
        self.port=port or MockCoveragePortV011({x.query_id:x for x in self.outcomes})
        self.provider=MockProvider(self.payload)

    def run(self,*, allow=True):
        return CandidateReasonerV011(self.provider,self.port).run(case=self.case,quality=self.quality,
            business_review=self.review,allow_mock_preview=allow)


class TestOnlyProductionPort:
    """Exercises the port contract; NOT a genuine mathematical Core adapter."""
    mode='PRODUCTION'
    def __init__(self, value):
        self.value=value
        self.calls=[]
    def lookup(self, *, case,quality,review,query_id):
        self.calls.append(query_id)
        return self.value[query_id]


class TestV011CandidateSafety(unittest.TestCase):
    def setUp(self):
        self.e=ExampleEnvironment()

    def test_valid_mock_one_query_only(self):
        r=self.e.run()
        self.assertEqual([x.status for x in r.results],['BLOCKED','UNVERIFIED_CANDIDATE'])
        self.assertEqual([x.reason_code for x in r.results],['NOT_A_COVERAGE_GAP','EXPLORATORY_MATH_ONLY_NOT_CERTIFIED'])
        self.assertEqual(self.e.provider.calls,1)
        self.assertEqual(self.e.port.calls,['q1','q2'])
        self.assertEqual(r.results[1].candidate.proposal.claimed_identification,'POINT')
        self.assertEqual(r.results[1].mode,'MOCK_PREVIEW')
        self.assertFalse(r.estimation_handoff_allowed)
        self.assertEqual(r.mathematical_verification,'NOT_PERFORMED')

    def test_mock_preview_must_be_explicit(self):
        r=self.e.run(allow=False)
        self.assertEqual([x.reason_code for x in r.results],['MOCK_PREVIEW_NOT_AUTHORIZED']*2)
        self.assertEqual(self.e.provider.calls,0)
        self.assertEqual(self.e.port.calls,[])

    def test_hashes_bind_both_business_material_and_candidate(self):
        r=self.e.run()
        self.assertEqual(r.input_sha256,fingerprint_business_case(self.e.case))
        self.assertEqual(r.draft_sha256,canonical_sha256(self.e.quality.draft))
        self.assertEqual(r.business_review_sha256,self.e.review.fingerprint())
        self.assertEqual(r.results[1].coverage_sha256,self.e.outcomes[1].fingerprint())
        self.assertEqual(r.results[1].science_scope_sha256,self.e.outcomes[1].science_scope.fingerprint())
        self.assertEqual(CandidateBatchReportV011.model_validate_json(r.model_dump_json()),r)

    def test_business_file_edited_rejected_before_model_and_port(self):
        self.e.case.business_question+=' 改动'
        with self.assertRaises(CandidateSafetyError): self.e.run()
        self.assertEqual(self.e.provider.calls,0)
        self.assertEqual(self.e.port.calls,[])

    def test_stale_a0_report_rejected_before_model_and_port(self):
        self.e.quality=self.e.quality.model_copy(deep=True)
        self.e.quality.draft.queries[1].semantics.intervention.value='偷偷改处理定义'  # bypass pydantic for test
        with self.assertRaises(CandidateSafetyError): self.e.run()
        self.assertEqual(self.e.provider.calls,0)
        self.assertEqual(self.e.port.calls,[])

    def test_a0_source_quote_audit_recomputed(self):
        self.e.quality=self.e.quality.model_copy(deep=True)
        self.e.quality.draft.queries[1].business_goal.evidence[0].quote='不存在的业务引文'
        self.e.quality.draft_sha256=canonical_sha256(self.e.quality.draft)
        with self.assertRaises((CandidateSafetyError,ValueError)): self.e.run()
        self.assertEqual(self.e.provider.calls,0)

    def test_business_review_not_created_automatically(self):
        x=self.e.review.model_dump(mode='json'); x.pop('decision')
        with self.assertRaises(ValidationError): BusinessQueryReviewV011.model_validate(x)

    def test_business_review_stale(self):
        self.e.review=self.e.review.model_copy(update={'draft_sha256':'1'*64})
        with self.assertRaises(CandidateSafetyError):self.e.run()
        self.assertEqual(self.e.provider.calls,0)

    def test_review_nonexistent_query(self):
        self.e.review=self.e.review.model_copy(update={'confirmed_query_ids':['q9']})
        with self.assertRaises(CandidateSafetyError):self.e.run()

    def test_partial_query_review_skips_other_query(self):
        self.e.review=self.e.review.model_copy(update={'confirmed_query_ids':['q1']})
        r=self.e.run()
        self.assertEqual(r.results[1].reason_code,'QUERY_NOT_BUSINESS_APPROVED')
        self.assertEqual(self.e.provider.calls,0)
        self.assertEqual(self.e.port.calls,['q1'])

    def test_businesse_question_needs_clarification_not_reasoned(self):
        quality=self.e.quality.model_copy(deep=True)
        from cfm_id_llm.schemas import TargetKind
        quality.draft.queries[1].target.kind=TargetKind.UNRESOLVED
        quality.draft.queries[1].target.description.value=None
        # Synthetic mutation used to derive a different *valid* report:
        quality.draft.queries[1].target.description.basis='UNRESOLVED'
        quality.draft.queries[1].target.description.evidence=[]
        # Other fields still point to original business goal; route must never run.
        quality=audit_business_quality(self.e.case,quality.draft,provider=quality.provider,prompt_version=quality.prompt_version)
        self.e.quality=quality
        self.e.review=self.e.review.model_copy(update={'draft_sha256':quality.draft_sha256})
        r=self.e.run()
        self.assertEqual(r.results[1].reason_code,'BUSINESS_FORMULATION_NOT_READY')
        self.assertEqual(self.e.provider.calls,0)

    def test_critical_recheck_blocks_query(self):
        quality=self.e.quality.model_copy(deep=True)
        from cfm_id_llm.schemas import SemanticClaim
        quality.draft.shared_draft.units_variables.outcome=SemanticClaim()
        quality=audit_business_quality(self.e.case,quality.draft,provider=quality.provider,prompt_version=quality.prompt_version)
        self.e.quality=quality
        self.e.review=self.e.review.model_copy(update={'draft_sha256':quality.draft_sha256})
        r=self.e.run()
        self.assertEqual([x.reason_code for x in r.results],['BUSINESS_FORMULATION_NOT_READY']*2)
        self.assertEqual(self.e.provider.calls,0)

    def outcome_changed(self,**kwargs):
        self.e.outcomes[1]=self.e.outcomes[1].model_copy(update=kwargs)
        self.e.port=MockCoveragePortV011({'q1':self.e.outcomes[0], 'q2':self.e.outcomes[1]})
        return self.e.run()

    def test_needs_input_no_candidate(self):
        r=self.outcome_changed(status='NEEDS_INPUT',fallback='BLOCKED')
        self.assertEqual(r.results[1].reason_code,'NOT_A_COVERAGE_GAP')
        self.assertEqual(self.e.provider.calls,0)

    def test_no_adapter_no_candidate(self):
        r=self.outcome_changed(status='NO_ADAPTER',fallback='BLOCKED')
        self.assertEqual(r.results[1].reason_code,'NOT_A_COVERAGE_GAP')
        self.assertEqual(self.e.provider.calls,0)

    def test_core_error_no_candidate(self):
        r=self.outcome_changed(status='ERROR',fallback='BLOCKED')
        self.assertEqual(r.results[1].reason_code,'NOT_A_COVERAGE_GAP')
        self.assertEqual(self.e.provider.calls,0)

    def test_verifier_failure_no_candidate(self):
        r=self.outcome_changed(status='CORE_VERIFICATION_FAILED',fallback='BLOCKED')
        self.assertEqual(r.results[1].reason_code,'NOT_A_COVERAGE_GAP')
        self.assertEqual(self.e.provider.calls,0)

    def test_route_unsupported_but_fallback_blocked_no_candidate(self):
        r=self.outcome_changed(fallback='BLOCKED')
        self.assertEqual(r.results[1].reason_code,'NOT_A_COVERAGE_GAP')
        self.assertEqual(self.e.provider.calls,0)

    def test_unsupported_bad_reason_never_fallback(self):
        r=self.outcome_changed(reason_code='A5_NOT_SCIENTIFICALLY_APPROVED')
        self.assertEqual(r.results[1].reason_code,'UNAPPROVED_COVERAGE_GAP_REASON')
        self.assertEqual(self.e.provider.calls,0)

    def test_bad_query_id_core_snapshot(self):
        r=self.outcome_changed(query_id='q7')
        self.assertEqual(r.results[1].reason_code,'CORE_COVERAGE_BINDING_MISMATCH')
        self.assertEqual(self.e.provider.calls,0)

    def test_bad_target_hash_core_snapshot(self):
        r=self.outcome_changed(target_sha256='f'*64)
        self.assertEqual(r.results[1].reason_code,'CORE_COVERAGE_BINDING_MISMATCH')
        self.assertEqual(self.e.provider.calls,0)

    def test_bad_review_hash_core_snapshot(self):
        r=self.outcome_changed(business_review_sha256='a'*64)
        self.assertEqual(r.results[1].reason_code,'CORE_COVERAGE_BINDING_MISMATCH')
        self.assertEqual(self.e.provider.calls,0)

    def test_bad_source_hash_core_snapshot(self):
        r=self.outcome_changed(input_sha256='a'*64)
        self.assertEqual(r.results[1].reason_code,'CORE_COVERAGE_BINDING_MISMATCH')
        self.assertEqual(self.e.provider.calls,0)

    def test_core_port_failure_fails_closed(self):
        self.e.port.entries.pop('q2')
        r=self.e.run()
        self.assertEqual(r.results[1].reason_code,'CORE_COVERAGE_LOOKUP_FAILED')
        self.assertEqual(self.e.provider.calls,0)

    def test_wrong_port_mode_rejected(self):
        # Simulate an unsafe attempt to pass production-looking data via a mock port.
        port=TestOnlyProductionPort({'q1':self.e.outcomes[0],'q2':self.e.outcomes[1]})
        self.e.port=port
        r=self.e.run()
        self.assertEqual([x.reason_code for x in r.results],['CORE_PORT_MODE_MISMATCH']*2)
        self.assertEqual(self.e.provider.calls,0)

    def test_mock_port_forbids_production(self):
        data=self.e.outcomes[1].model_dump(mode='json')
        data['source_mode']='PRODUCTION';data['core_version']='real-math-2.9.1'
        with self.assertRaises(ValueError):
            MockCoveragePortV011({'q2':CoreCoverageV011.model_validate(data)})

    def test_production_scope_must_be_separately_present(self):
        data=self.e.outcomes[1].model_dump(mode='json');data['source_mode']='PRODUCTION'
        data['core_version']='real-math-2.9.1';data['adapter_id']='trusted-local-port'
        data['formal_target_sha256']='2'*64
        data['business_math_crosswalk_sha256']='3'*64
        data['science_scope']=None
        with self.assertRaises(ValidationError):CoreCoverageV011.model_validate(data)

    def test_production_approved_a4_a5_required(self):
        outcomes={x.query_id:x for x in self.e.outcomes}
        v=outcomes['q2'].model_dump(mode='json');v.update({'source_mode':'PRODUCTION',
                            'core_version':'real-math-2.9.1','adapter_id':'trusted-test-contract',
                            'formal_target_sha256':'2'*64,'business_math_crosswalk_sha256':'3'*64})
        v['science_scope']['a4_sources']=[]
        port=TestOnlyProductionPort({'q2':CoreCoverageV011.model_validate(v), 'q1':outcomes['q1']})
        self.e.port=port
        r=self.e.run()
        self.assertEqual(r.results[1].reason_code,'PRODUCTION_SCIENTIFIC_ADMISSION_INCOMPLETE')
        self.assertEqual(self.e.provider.calls,0)

    def test_production_formal_target_crosswalk_bindings_required(self):
        data=self.e.outcomes[1].model_dump(mode='json')
        data.update(source_mode='PRODUCTION',core_version='v2.9.1',adapter_id='local-trusted-adapter')
        with self.assertRaises(ValidationError):CoreCoverageV011.model_validate(data)

    def test_production_gate_under_complete_test_science_still_unverified(self):
        data=self.e.outcomes[1].model_dump(mode='json')
        data.update({'source_mode':'PRODUCTION','core_version':'v2.9.1-TEST-CONTRACT',
                     'adapter_id':'test-only-trusted-bridge',
                     'formal_target_sha256':'2'*64,'business_math_crosswalk_sha256':'3'*64})
        data['science_scope']['a4_sources']=[{
            'source_id':'test-sci','operator':'population_arm_means','level':'NODE_ARM_CONDITIONAL_MEANS',
            'typed_source_sha256':'d'*64}]
        port=TestOnlyProductionPort({'q1':self.e.outcomes[0],
                                     'q2':CoreCoverageV011.model_validate(data)})
        self.e.port=port
        payload=copy.deepcopy(read('mock_candidate_q2.json'))
        payload['science_scope_sha256']=port.value['q2'].science_scope.fingerprint()
        self.e.provider=MockProvider(payload)
        r=self.e.run()
        self.assertEqual(r.results[1].status,'UNVERIFIED_CANDIDATE')
        self.assertEqual(r.results[1].mode,'TRUSTED_CORE_GAP')
        self.assertIsNone(r.results[1].mathematical_certificate)
        self.assertFalse(r.estimation_handoff_allowed)
        self.assertEqual(self.e.provider.calls,1)

    def proposal_changed(self,fn):
        x=copy.deepcopy(read('mock_candidate_q2.json'));fn(x)
        self.e.provider=MockProvider(x)
        return self.e.run()

    def test_candidate_claims_wrong_query(self):
        r=self.proposal_changed(lambda x:x.update(query_id='q1'))
        self.assertEqual(r.results[1].status,'REJECTED_UNSAFE_OUTPUT')
        self.assertIn('QUERY_CHANGED',{x.code for x in r.results[1].issues})

    def test_candidate_changes_target_hash(self):
        r=self.proposal_changed(lambda x:x.update(target_sha256='2'*64))
        self.assertIn('TARGET_HASH_CHANGED',{x.code for x in r.results[1].issues})

    def test_candidate_changes_semantics_hash(self):
        r=self.proposal_changed(lambda x:x.update(semantics_sha256='2'*64))
        self.assertIn('SEMANTICS_HASH_CHANGED',{x.code for x in r.results[1].issues})

    def test_candidate_changes_science_scope_hash(self):
        r=self.proposal_changed(lambda x:x.update(science_scope_sha256='2'*64))
        self.assertIn('SCIENTIFIC_SCOPE_CHANGED',{x.code for x in r.results[1].issues})

    def test_candidate_changes_target_kind(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(target_kind='FIXED_POLICY_VALUE'))
        self.assertIn('TARGET_KIND_CHANGED',{x.code for x in r.results[1].issues})

    def test_candidate_changes_target_description(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(target_description='给少数人推广AI'))
        self.assertIn('TARGET_DESCRIPTION_CHANGED',{x.code for x in r.results[1].issues})

    def test_candidate_invokes_unapproved_a5(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(admitted_assumptions_used=['exposure_sufficiency']))
        self.assertIn('UNADMITTED_A5_USED',{x.code for x in r.results[1].issues})

    def test_candidate_invokes_approved_a5_name(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(admitted_assumptions_used=['consistency']))
        self.assertEqual(r.results[1].status,'UNVERIFIED_CANDIDATE')

    def test_candidate_upgrades_a4_without_permission(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(a4_used={
            'source':'REVIEWED_OPERATOR','level':'NODE_ARM_CONDITIONAL_MEANS','operator':'E[Y|T,S]'}))
        self.assertIn('A4_OPERATOR_NOT_APPROVED',{x.code for x in r.results[1].issues})

    def test_candidate_missing_conditional_a4(self):
        def change(x):
            x['proposal']['additional_requirements']=[x['proposal']['additional_requirements'][1]]
        r=self.proposal_changed(change)
        self.assertIn('A4_CONDITIONAL_REQUIRED',{x.code for x in r.results[1].issues})

    def test_candidate_falsely_assumes_missing_a4(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(scope='AS_REVIEWED'))
        self.assertEqual(r.results[1].status,'REJECTED_UNSAFE_OUTPUT')

    def test_candidate_fake_certificate_blocked(self):
        r=self.proposal_changed(lambda x:x.update(mathematical_certificate={'fake':1}))
        self.assertEqual(r.results[1].reason_code,'INVALID_CANDIDATE_SCHEMA')

    def test_candidate_fake_estimation_permission_blocked(self):
        r=self.proposal_changed(lambda x:x.update(estimation_handoff_allowed=True))
        self.assertEqual(r.results[1].reason_code,'INVALID_CANDIDATE_SCHEMA')

    def test_candidate_no_validation_checks_blocked(self):
        r=self.proposal_changed(lambda x:x.update(proposed_validation_checks=[]))
        self.assertEqual(r.results[1].reason_code,'INVALID_CANDIDATE_SCHEMA')

    def test_candidate_without_formula_blocked(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(candidate_expression=None))
        self.assertEqual(r.results[1].reason_code,'INVALID_CANDIDATE_SCHEMA')

    def test_notpoint_requires_sketch(self):
        r=self.proposal_changed(lambda x:x['proposal'].update(claimed_identification='NOT_POINT',candidate_expression=None))
        self.assertEqual(r.results[1].reason_code,'INVALID_CANDIDATE_SCHEMA')

    def test_notpoint_sketch_accepted_only_unverified(self):
        def edit(x):
            p=x['proposal'];p['claimed_identification']='NOT_POINT';p['candidate_expression']=None
            p['nonidentification_witness']={
                'world_a':'两个世界在观测分布上相同，潜在结果不同',
                'world_b':'在未观测政策下赋不同潜在结果，但是观测相同',
                'why_observables_match':'目前的观测支持仅包含指定的处理组合',
                'why_targets_differ':'未观察到的反事实结果在两个世界中不同'}
        r=self.proposal_changed(edit)
        self.assertEqual(r.results[1].status,'UNVERIFIED_CANDIDATE')
        self.assertIsNone(r.results[1].mathematical_certificate)

    def test_undetermined_accepted(self):
        def edit(x):
            p=x['proposal'];p['claimed_identification']='UNDETERMINED'
            p['scope']='AS_REVIEWED';p['candidate_expression']=None;p['additional_requirements']=[]
        r=self.proposal_changed(edit)
        self.assertEqual(r.results[1].status,'UNDETERMINED_UNVERIFIED')

    def test_provider_failure_sanitized(self):
        class BrokenProvider:
            name='BROKEN_TEST'
            def generate_json(self,*,system_prompt,user_prompt):
                raise RuntimeError('SECRET_API_KEY_MUST_NOT_BE_EXPOSED')
        self.e.provider=BrokenProvider()
        r=self.e.run()
        self.assertEqual(r.results[1].status,'PROVIDER_FAILED')
        self.assertNotIn('SECRET_',r.model_dump_json())

    def test_models_forged_core_math_are_forbidden(self):
        x=self.e.run().model_dump(mode='json')
        x['results'][1]['mathematical_certificate']={'fake':'yes'}
        with self.assertRaises(ValidationError): CandidateBatchReportV011.model_validate(x)

    def test_prompt_contains_one_query_not_all_sources(self):
        q=self.e.quality.draft.queries[1]
        prompt=make_candidate_prompt_v011(self.e.quality,q,self.e.outcomes[1])
        self.assertIn('query_id_exact',prompt)
        self.assertIn('target_sha256_exact',prompt)
        self.assertIn('science_scope_sha256_exact',prompt)
        self.assertIn('共享假设',prompt) if '共享假设' in prompt else self.assertIn('shared_proposed_assumptions_not_licenses',prompt)
        self.assertNotIn('sales_before、sales_after',prompt)  # raw dictionary content not resent
        self.assertIn('UNSUPPORTED',prompt)
        self.assertIn('不等于数学上的 NOT_POINT',CANDIDATE_SYSTEM_PROMPT_V011)

    def test_standalone_module_does_not_import_math_core(self):
        text='import sys,cfm_id_llm.candidate_queries; print("pfn_pipeline" in sys.modules,"cfm_id_bridge" in sys.modules)'
        x=subprocess.run([sys.executable,'-c',text],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(x.stdout.strip(),'False False')
        self.assertEqual(x.returncode,0)

    def test_cli_without_mock_preview_never_executes(self):
        with tempfile.TemporaryDirectory() as d:
            cmd=[sys.executable,'-m','cfm_id_llm.candidate_preview_cli',
                 '--case',str(DEMO/'business_case.json'),'--a0-report',str(DEMO/'a0_quality_report.json'),
                 '--business-review',str(DEMO/'human_business_review_MOCK.json'),
                 '--mock-outcomes',str(DEMO/'mock_core_coverage.json'),
                 '--mock-candidate',str(DEMO/'mock_candidate_q2.json')]
            x=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
            self.assertNotEqual(x.returncode,0)
            self.assertIn('stopped safely',x.stderr)

    def test_cli_mock_demo(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'candidate_report.json'
            cmd=[sys.executable,'-m','cfm_id_llm.candidate_preview_cli',
                 '--case',str(DEMO/'business_case.json'),'--a0-report',str(DEMO/'a0_quality_report.json'),
                 '--business-review',str(DEMO/'human_business_review_MOCK.json'),
                 '--mock-outcomes',str(DEMO/'mock_core_coverage.json'),
                 '--mock-candidate',str(DEMO/'mock_candidate_q2.json'),
                 '--allow-mock-preview','--output',str(output)]
            x=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(x.returncode,0,x.stderr)
            data=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(data['results'][1]['mode'],'MOCK_PREVIEW')
            self.assertFalse(data['estimation_handoff_allowed'])

    def test_cli_external_requires_explicit_consent(self):
        cmd=[sys.executable,'-m','cfm_id_llm.candidate_preview_cli',
             '--case',str(DEMO/'business_case.json'),'--a0-report',str(DEMO/'a0_quality_report.json'),
             '--business-review',str(DEMO/'human_business_review_MOCK.json'),
             '--mock-outcomes',str(DEMO/'mock_core_coverage.json'),
             '--allow-mock-preview','--provider','openai-chat','--model','example']
        x=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
        self.assertNotEqual(x.returncode,0)

    def test_legacy_v03_contract_still_importable(self):
        from cfm_id_llm.candidate_reasoner import CandidateReasonerV03
        from cfm_id_llm.candidate_schemas import CandidateDraftV03
        self.assertTrue(CandidateReasonerV03)
        self.assertTrue(CandidateDraftV03)


if __name__=='__main__':unittest.main()
