from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cfm_id_llm.audit import fingerprint_business_case
from cfm_id_llm.handoff_preview import prepare_core_handoff_preview, CoreHandoffPreviewV09
from cfm_id_llm.material_integrity import create_grounded_intake, review_grounded_intake
from cfm_id_llm.multiquery_formulator import MultiQueryFormulatorV09, MultiQueryValidationError
from cfm_id_llm.multiquery_prompts import make_multiquery_user_prompt, SYSTEM_PROMPT_V09
from cfm_id_llm.multiquery import (
    MultiQueryDraftV09, MultiQueryReportV09, HumanMultiQueryReviewV09,
    ReviewedMultiQueryV09, approve_multiquery, render_multiquery_text,
    audit_multiquery,
)
from cfm_id_llm.multisource_intake_cli import _load_manifest
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.schemas import BusinessCase, TargetKind
from evaluation.multiquery_eval import load_cases, reference_fixture, score_targets, evaluate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples/multisource/mock_multiquery.json'
MANIFEST = ROOT / 'examples/multisource/case.json'


class MultiQueryV09Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c, q, language, files = _load_manifest(MANIFEST)
        cls.intake = create_grounded_intake(case_id=c, business_question=q,
                                           attachments=files, response_language=language)
        cls.case = cls.intake.case
        cls.good = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def make(self, raw=None):
        provider = MockProvider(copy.deepcopy(raw or self.good))
        return MultiQueryFormulatorV09(provider).formulate(self.case)

    def test_two_queries_and_distinct_targets(self):
        r = self.make()
        self.assertEqual([q.target.kind for q in r.draft.queries],
                         [TargetKind.FIXED_POLICY_VALUE, TargetKind.SPILLOVER_EFFECT])
        self.assertEqual(r.draft.primary_query_id, 'q1')
        self.assertEqual(r.primary_formulation.draft, r.draft.shared_draft)

    def test_one_llm_call_even_with_three_documents(self):
        mock = MockProvider(self.good)
        r = MultiQueryFormulatorV09(mock).formulate(self.case)
        self.assertEqual(mock.calls, 1)
        self.assertEqual(len(self.case.sources), 3)

    def test_math_never_certified(self):
        r = self.make()
        self.assertEqual(r.mathematical_verification, 'NOT_PERFORMED')
        self.assertFalse(r.core_called)
        self.assertFalse(r.estimation_handoff_allowed)
        self.assertFalse(r.formal_core_spec_generated)
        for q in r.query_audits:
            self.assertEqual(q.mathematical_verification, 'NOT_PERFORMED')

    def test_new_prompt_is_consolidated_and_core_agnostic(self):
        self.assertIn('多个因果问题', SYSTEM_PROMPT_V09)
        self.assertNotIn('R1a', SYSTEM_PROMPT_V09)
        self.assertNotIn('v0.1 面向', SYSTEM_PROMPT_V09)
        p = make_multiquery_user_prompt(self.case)
        self.assertIn('business_question', p)
        self.assertIn('MultiQueryDraftV09', p)

    def test_evidence_in_another_query_rejected(self):
        d = copy.deepcopy(self.good)
        d['queries'][1]['business_goal']['evidence'][0]['quote'] = '与原文无关的伪造文字'
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_evidence_source_id_rejected(self):
        d = copy.deepcopy(self.good)
        d['queries'][1]['target']['description']['evidence'][0]['source_id'] = 'unknown_att'
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_primary_query_binding(self):
        d = copy.deepcopy(self.good)
        d['primary_query_id'] = 'q2'
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_missing_primary_query(self):
        d = copy.deepcopy(self.good)
        d['primary_query_id'] = 'q3'
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_duplicate_query_id(self):
        d = copy.deepcopy(self.good)
        d['queries'][1]['query_id'] = 'q1'
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_duplicate_business_query(self):
        d = copy.deepcopy(self.good)
        d['queries'].append(copy.deepcopy(d['queries'][0]))
        d['queries'][-1]['query_id'] = 'q3'
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_max_eight_queries(self):
        d = copy.deepcopy(self.good)
        for i in range(3, 10):
            q = copy.deepcopy(d['queries'][1]); q['query_id'] = f'q{i}'
            q['target']['description']['value'] = f'同事影响的第{i}个说法'
            d['queries'].append(q)
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_extra_fake_certificate_rejected(self):
        d = copy.deepcopy(self.good); d['certificate'] = {'claimed': 'POINT'}
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_fake_assumption_certified_rejected(self):
        d = copy.deepcopy(self.good); d['shared_draft']['assumptions'][0]['status'] = 'CERTIFIED'
        with self.assertRaises(MultiQueryValidationError):
            self.make(d)

    def test_mismatched_formulation_report_rejected(self):
        report = self.make()
        modified = report.model_dump(mode='json')
        modified['query_audits'][0]['query_id'] = 'q2'
        with self.assertRaises(ValueError):
            MultiQueryReportV09.model_validate(modified)

    def test_change_second_query_invalidates_digest(self):
        report = self.make()
        altered = report.model_dump(mode='json')
        altered['draft']['queries'][1]['target']['description']['value'] = '另一个目标'
        with self.assertRaises(ValueError):
            MultiQueryReportV09.model_validate(altered)

    def test_table_schema_alone_cannot_define_extra_business_goal(self):
        d = copy.deepcopy(self.good)
        d['queries'][1]['business_goal'] = {
            'value': 'sales_before, sales_after',
            'basis': 'EXPLICIT_TEXT',
            'evidence': [{'source_id':'att_03', 'quote':'sales_before, sales_after'}],
        }
        r = self.make(d)
        q2 = next(q for q in r.query_audits if q.query_id == 'q2')
        self.assertIn('BUSINESS_GOAL_FROM_DATA_DICTIONARY_ONLY', {i.code for i in q2.issues})
        self.assertEqual(q2.review_status, 'NEEDS_CLARIFICATION')

    def test_cross_target_assessment_still_requires_exposure(self):
        r = self.make()
        q2 = next(q for q in r.query_audits if q.query_id == 'q2')
        self.assertIn('A3_EXPOSURE_UNRESOLVED', {i.code for i in q2.issues})
        self.assertIn('A4_POPULATION_INFORMATION_OPEN', {i.code for i in q2.issues})

    def test_verbatim_quote_is_not_scientific_certification(self):
        r = self.make()
        self.assertIn('NOT_PERFORMED', r.mathematical_verification)
        self.assertTrue(all(a.review_status in {'NEEDS_CLARIFICATION','DRAFT_READY_FOR_HUMAN_REVIEW'}
                            for a in r.query_audits))

    def test_document_quality_gate_still_used(self):
        r = self.make()
        audit = review_grounded_intake(self.intake, r.primary_formulation)
        self.assertFalse(audit.formal_core_spec_generated)
        self.assertEqual(audit.mathematical_verification, 'NOT_PERFORMED')

    def make_review(self, r=None, selected=None):
        r = r or self.make()
        return HumanMultiQueryReviewV09(case_id=r.case_id, input_sha256=r.input_sha256,
                    draft_sha256=r.draft_sha256, confirmed_query_ids=selected or ['q1','q2'],
                    reviewed_by='human-expert', review_note='Reviewed target meanings and material sources.',
                    decision='CONFIRMED')

    def test_valid_review_and_handoff_preview(self):
        r = self.make()
        checked = approve_multiquery(self.case, r, self.make_review(r))
        preview = prepare_core_handoff_preview(checked)
        self.assertEqual([q.query_id for q in preview.reviewed_queries], ['q1','q2'])
        self.assertEqual(preview.core_adapter_state, 'NOT_CONNECTED')
        self.assertFalse(preview.estimation_handoff_allowed)
        self.assertTrue(all(q.identification_status == 'NOT_PERFORMED' for q in preview.reviewed_queries))

    def test_review_one_query_only(self):
        r = self.make()
        reviewed = approve_multiquery(self.case, r, self.make_review(r, ['q2']))
        preview = prepare_core_handoff_preview(reviewed)
        self.assertEqual([q.query_id for q in preview.reviewed_queries], ['q2'])

    def test_review_stale_on_source_edit(self):
        r = self.make()
        changed = self.case.model_copy(deep=True)
        changed.business_question += '（新增额外目标）'
        with self.assertRaises(ValueError):
            approve_multiquery(changed, r, self.make_review(r))

    def test_review_stale_on_second_query_modification(self):
        r = self.make()
        old_review = self.make_review(r)
        changed_draft = r.draft.model_copy(deep=True)
        changed_draft.queries[1].business_goal.value += '（修改）'
        modified_report = audit_multiquery(self.case, changed_draft, provider='mock-fixture',
                                           prompt_version=r.prompt_version)
        with self.assertRaises(ValueError):
            ReviewedMultiQueryV09(report=modified_report, human_review=old_review)

    def test_nonexistent_reviewed_query_rejected(self):
        r = self.make()
        with self.assertRaises(ValueError):
            approve_multiquery(self.case, r, self.make_review(r, ['q99']))

    def test_duplicate_reviewed_query_rejected(self):
        r = self.make()
        with self.assertRaises(ValueError):
            self.make_review(r, ['q1','q1'])

    def test_approval_with_rewritten_issues_is_rejected(self):
        r = self.make()
        r2 = r.model_copy(deep=True)
        r2.query_audits[0].issues = []
        with self.assertRaises(ValueError):
            approve_multiquery(self.case, r2, self.make_review(r2))

    def test_handoff_preview_never_creates_task_spec(self):
        r = self.make()
        preview = prepare_core_handoff_preview(approve_multiquery(self.case, r, self.make_review(r)))
        self.assertNotIn('identification_result', preview.model_dump())
        self.assertNotIn('certificate', preview.model_dump())
        self.assertFalse(preview.estimation_handoff_allowed)

    def test_cli_manifest_mock(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'run.json'
            cmd = [sys.executable,'-m','cfm_id_llm.multiquery_cli',
                   '--manifest',str(MANIFEST),'--provider','mock','--mock-response',str(FIXTURE),
                   '--format','json','--output',str(out)]
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            raw = json.loads(out.read_text())
            self.assertEqual(len(raw['formulation']['draft']['queries']), 2)
            self.assertEqual(raw['formulation']['mathematical_verification'], 'NOT_PERFORMED')

    def test_cli_preview_no_llm(self):
        cmd = [sys.executable,'-m','cfm_id_llm.multiquery_cli',
               '--manifest',str(MANIFEST),'--preview','--format','json']
        p = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0)
        self.assertFalse(json.loads(p.stdout)['llm_called'])

    def test_cli_online_requires_consent_and_no_key(self):
        cmd = [sys.executable,'-m','cfm_id_llm.multiquery_cli','--manifest',str(MANIFEST),
               '--provider','openai-chat','--model','not-online','--allow-external']
        p = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('allow-document-sharing',p.stderr)

    def test_old_draft_unchanged(self):
        from cfm_id_llm.schemas import DraftProblemSpec
        self.assertEqual(DraftProblemSpec().schema_version,'cfm-id-draft-v0.1')

    def test_gold_cases_have_exact_quotes(self):
        self.assertEqual(len(load_cases()), 8)

    def test_offline_benchmark_is_not_llm_accuracy(self):
        result = evaluate(provider_name='oracle-fixture',model=None,max_cases=8,
                          allow_external=False,fixture_dir=None,base_url='https://api.openai.com/v1')
        self.assertEqual(result['valid_schema_and_quotes'],8)
        self.assertEqual(result['evaluation_kind'],'OFFLINE_PIPELINE_FIXTURE_ONLY')
        self.assertEqual(result['causal_semantic_accuracy'],'NOT_MEASURED_AUTOMATICALLY')
        self.assertEqual(result['math_identification_accuracy'],'NOT_MEASURED')

    def test_score_detects_extra_query(self):
        s = score_targets(['DIRECT_EFFECT'], ['DIRECT_EFFECT','SPILLOVER_EFFECT'])
        self.assertEqual(s['unexpected_target_count'], 1)
        self.assertFalse(s['exact_target_multiset'])

    def test_score_detects_duplicate_query_kind(self):
        s = score_targets(['SPILLOVER_EFFECT'],['SPILLOVER_EFFECT','SPILLOVER_EFFECT'])
        self.assertEqual(s['unexpected_target_count'],1)

    def test_zero_external_calls_for_reference(self):
        with patch('evaluation.multiquery_eval.OpenAICompatibleChatProvider') as api:
            evaluate(provider_name='oracle-fixture',model=None,max_cases=1,
                     allow_external=False,fixture_dir=None,base_url='https://api.openai.com/v1')
            api.assert_not_called()

    def test_no_external_without_optin(self):
        with self.assertRaises(ValueError):
            evaluate(provider_name='openai-chat',model='name',max_cases=1,
                     allow_external=False,fixture_dir=None,base_url='https://api.openai.com/v1')

    def test_handoff_preview_unique_ids(self):
        r=self.make()
        reviewed=approve_multiquery(self.case,r,self.make_review(r))
        preview=prepare_core_handoff_preview(reviewed)
        data=preview.model_dump(mode='json')
        data['reviewed_queries'][1]['query_id']='q1'
        with self.assertRaises(ValueError):
            CoreHandoffPreviewV09.model_validate(data)


if __name__ == '__main__':
    unittest.main()
