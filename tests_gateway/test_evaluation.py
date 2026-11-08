"""Benchmark infrastructure tests; offline fixtures are never LLM accuracy tests."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cfm_id_llm.candidate_reasoner import CandidateReasonerV03
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.schemas import BusinessCase
from evaluation.frozen_problems import make_frozen_input
from evaluation.math_oracles import run_oracles
from evaluation.real_benchmark import (
    DEFAULT_DATASET, DEFAULT_FIXTURES, REVIEW_FIELDS,
    adjudication_summary, candidate_score, choose_cases, formulation_score,
    load_benchmark, make_adjudication_template, rollup, run_candidate,
    run_formulation, stable_sha256,
)


class SpyProvider(MockProvider):
    def __init__(self,response):
        super().__init__(response)
        self.prompts=[]
    def generate_json(self,*,system_prompt,user_prompt):
        self.prompts.append((system_prompt,user_prompt))
        return super().generate_json(system_prompt=system_prompt,user_prompt=user_prompt)


class FailProvider:
    name='test-only-fail'
    def generate_json(self,*,system_prompt,user_prompt):
        raise RuntimeError('SIMULATED_KEY_SECRET_SHOULD_NEVER_LEAK')


class BenchmarkV04Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset=load_benchmark(DEFAULT_DATASET)

    def test_dataset_counts_and_unique_id(self):
        self.assertEqual(len(self.dataset['formulation_cases']),30)
        self.assertEqual(len(self.dataset['candidate_cases']),16)
        self.assertEqual(len({x['id'] for x in self.dataset['formulation_cases']+self.dataset['candidate_cases']}),46)

    def test_dataset_has_no_real_customer_identifiers(self):
        self.assertIn('Synthetic',self.dataset['provenance'])
        self.assertNotIn('actual client',json.dumps(self.dataset,ensure_ascii=False).lower())

    def test_frozen_inputs_ready_and_test_only(self):
        for item in self.dataset['candidate_cases']:
            with self.subTest(item=item['id']):
                case,form,review,route=make_frozen_input(item)
                self.assertEqual(form.review_status,'DRAFT_READY_FOR_HUMAN_REVIEW')
                self.assertEqual(review.reviewed_by,'BENCHMARK_FIXTURE_ONLY')
                self.assertEqual(route.status,'MOCK_CORE_RESULT')
                self.assertEqual(route.verification_level,'MOCK_ONLY')

    def test_manual_test_fixtures_complete(self):
        for stage in ('formulation','candidate'):
            for item in self.dataset[stage+'_cases']:
                self.assertTrue((DEFAULT_FIXTURES/stage/(item['id']+'.json')).is_file())

    def test_all_fixtures_roundtrip_through_unchanged_gateways(self):
        rows=[]
        for item in self.dataset['formulation_cases']:
            p=MockProvider(json.loads((DEFAULT_FIXTURES/'formulation'/(item['id']+'.json')).read_text(encoding='utf8')))
            rows.append(run_formulation(item,p))
        for item in self.dataset['candidate_cases']:
            p=MockProvider(json.loads((DEFAULT_FIXTURES/'candidate'/(item['id']+'.json')).read_text(encoding='utf8')))
            rows.append(run_candidate(item,p))
        summary=rollup(rows)
        self.assertEqual(summary['formulation']['attempted'],30)
        self.assertEqual(summary['candidate']['attempted'],16)
        self.assertEqual(summary['formulation']['schema_and_gate_accepted'],30)
        self.assertEqual(summary['candidate']['schema_and_gate_accepted'],16)
        self.assertEqual(summary['candidate']['counts']['envelope_safe'],16)
        # v0.5 corrects F17 fixed-others; F18/F23 still require explicit clarification.
        self.assertEqual(summary['formulation']['counts']['clarification_match'],28)

    def test_all_candidate_fixtures_remain_llm_unverified(self):
        for item in self.dataset['candidate_cases']:
            fixture=json.loads((DEFAULT_FIXTURES/'candidate'/(item['id']+'.json')).read_text(encoding='utf8'))
            r=run_candidate(item,MockProvider(fixture))
            self.assertEqual(r['output']['verification_level'],'LLM_UNVERIFIED')
            self.assertFalse(r['output']['estimation_handoff_allowed'])
            self.assertIsNone(r['output']['mathematical_certificate'])
            self.assertEqual(r['output']['execution_mode'],'MOCK_PREVIEW')

    def test_gold_not_visible_in_formulation_prompt(self):
        item=copy.deepcopy(self.dataset['formulation_cases'][1])
        item['reference']['rationale']='NEVER_PUT_GOLD_IN_PROMPT_42'
        fixture=json.loads((DEFAULT_FIXTURES/'formulation'/(item['id']+'.json')).read_text(encoding='utf8'))
        sp=SpyProvider(fixture)
        run_formulation(item,sp)
        self.assertEqual(sp.calls,1)
        self.assertNotIn('NEVER_PUT_GOLD_IN_PROMPT_42',str(sp.prompts))

    def test_gold_not_visible_in_candidate_prompt(self):
        item=copy.deepcopy(self.dataset['candidate_cases'][1])
        item['reference']['reference_math']='NEVER_SHOW_THIS_GOLD_EXPRESSION_99'
        sp=SpyProvider(json.loads((DEFAULT_FIXTURES/'candidate'/(item['id']+'.json')).read_text(encoding='utf8')))
        run_candidate(item,sp)
        self.assertEqual(sp.calls,1)
        self.assertNotIn('NEVER_SHOW_THIS_GOLD_EXPRESSION_99',str(sp.prompts))

    def test_bad_candidate_target_rejected_by_existing_audit(self):
        item=self.dataset['candidate_cases'][0]
        d=json.loads((DEFAULT_FIXTURES/'candidate'/(item['id']+'.json')).read_text(encoding='utf8'))
        d['target_kind']='FIXED_POLICY_VALUE'
        r=run_candidate(item,MockProvider(d))
        self.assertEqual(r['status'],'REJECTED_UNSAFE_OUTPUT')
        self.assertIsNone(r['output']['candidate'])

    def test_bad_candidate_certificate_rejected(self):
        item=self.dataset['candidate_cases'][0]
        d=json.loads((DEFAULT_FIXTURES/'candidate'/(item['id']+'.json')).read_text(encoding='utf8'))
        d['mathematical_certificate']={'bad':True}
        r=run_candidate(item,MockProvider(d))
        self.assertEqual(r['status'],'REJECTED_UNSAFE_OUTPUT')
        self.assertIsNone(r['output']['mathematical_certificate'])

    def test_failed_provider_redacts_error_text(self):
        r=run_formulation(self.dataset['formulation_cases'][0],FailProvider())
        self.assertEqual(r['status'],'PROVIDER_OR_SCHEMA_FAILURE')
        self.assertNotIn('SIMULATED_KEY_SECRET',json.dumps(r))
        rc=run_candidate(self.dataset['candidate_cases'][0],FailProvider())
        self.assertEqual(rc['status'],'PROVIDER_FAILED')
        self.assertNotIn('SIMULATED_KEY_SECRET',json.dumps(rc))

    def test_full_form_score_wont_call_math_proof(self):
        item=self.dataset['formulation_cases'][1]
        fixture=json.loads((DEFAULT_FIXTURES/'formulation'/(item['id']+'.json')).read_text(encoding='utf8'))
        r=run_formulation(item,MockProvider(fixture))
        self.assertTrue(r['score']['all_three_fields_match'])
        self.assertNotIn('math_verified',r['score'])

    def test_reference_signatures(self):
        row=self.dataset['candidate_cases'][5]
        self.assertEqual(row['reference']['expected_claim'],'NOT_POINT')
        self.assertEqual(row['fixed_formal_problem']['a4_level'],'NODE_ARM_CONDITIONAL_MEANS')

    def test_cannot_request_unknown_case(self):
        with self.assertRaises(ValueError):
            choose_cases(self.dataset,('formulation',),case_ids={'F999'})

    def test_duplicate_ids_and_wrong_dataset_version(self):
        x=copy.deepcopy(self.dataset)
        x['dataset_version']='bogus'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'cases.json'
            p.write_text(json.dumps(x),encoding='utf8')
            with self.assertRaises(ValueError):load_benchmark(p)
            x['dataset_version']=self.dataset['dataset_version']
            x['formulation_cases'].append(x['formulation_cases'][0])
            p.write_text(json.dumps(x),encoding='utf8')
            with self.assertRaises(ValueError):load_benchmark(p)

    def test_dry_run_does_not_require_api_key(self):
        proc=subprocess.run([sys.executable,'-m','evaluation.real_benchmark','--dry-run','--max-cases','2'],
            cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['selected'],2)

    def test_no_live_call_without_explicit_consent(self):
        env=dict(os.environ);env.pop('CFM_ID_LLM_API_KEY',None);env.pop('OPENAI_API_KEY',None)
        proc=subprocess.run([sys.executable,'-m','evaluation.real_benchmark','--provider','openai-chat',
                             '--model','test-only-model','--max-cases','1'],
            cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,2)
        self.assertIn('stopped safely',proc.stderr)

    def test_even_with_consent_missing_key_prevents_live_call(self):
        env=dict(os.environ);env.pop('CFM_ID_LLM_API_KEY',None);env.pop('OPENAI_API_KEY',None)
        proc=subprocess.run([sys.executable,'-m','evaluation.real_benchmark','--provider','openai-chat',
                             '--model','test-only-model','--max-cases','1','--allow-external'],
            cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,2)
        self.assertIn('stopped safely',proc.stderr)

    def test_manual_template_needs_two_independent_reviewers(self):
        fake={'schema_version':'cfm-id-evaluation-run-v0.4','cases':[
                {'stage':'candidate','id':'C01','status':'UNVERIFIED_CANDIDATE'}]}
        template=make_adjudication_template(fake)
        self.assertEqual(template['run_sha256'],stable_sha256(fake))
        self.assertEqual(len(template['reviews']),1)
        self.assertEqual(adjudication_summary(fake,template)['candidate_cases_with_two_complete_reviews'],0)
        record=template['reviews'][0]
        r1=copy.deepcopy(record);r1['reviewer_id']='person-A'
        r2=copy.deepcopy(record);r2['reviewer_id']='person-B'
        for r in (r1,r2):r['checks']={key:'PASS' for key in REVIEW_FIELDS}
        template['reviews']=[r1,r2]
        self.assertEqual(adjudication_summary(fake,template)['two_reviewers_all_checks_pass'],1)
        r2['checks']['correct_formula_or_observational_equivalence']='FAIL'
        self.assertEqual(adjudication_summary(fake,template)['reviewer_disagreements'],1)

    def test_manual_adjudication_bound_to_report_hash(self):
        fake={'schema_version':'cfm-id-evaluation-run-v0.4','cases':[
                {'stage':'candidate','id':'C01','status':'UNVERIFIED_CANDIDATE'}]}
        template=make_adjudication_template(fake)
        template['run_sha256']='0'*64
        with self.assertRaises(ValueError):adjudication_summary(fake,template)

    def test_manual_adjudication_duplicate_or_unknown_rejected(self):
        fake={'schema_version':'cfm-id-evaluation-run-v0.4','cases':[
                {'stage':'candidate','id':'C01','status':'UNVERIFIED_CANDIDATE'}]}
        t=make_adjudication_template(fake)
        r=t['reviews'][0];r['reviewer_id']='same'
        r['checks']={key:'PASS' for key in REVIEW_FIELDS}
        t['reviews']=[r,copy.deepcopy(r)]
        with self.assertRaises(ValueError):adjudication_summary(fake,t)
        t['reviews']=[dict(r,case_id='NOT_A_CASE')]
        with self.assertRaises(ValueError):adjudication_summary(fake,t)

    def test_oracle_exact_small_graphs(self):
        res=run_oracles()
        self.assertEqual(len(res),8)
        self.assertTrue(all(v['passed'] for v in res.values()))
        self.assertEqual(res['check_direct_design_vs_fixed_others']['design_standardized_direct_contrast'],'-5')
        self.assertEqual(res['check_arm_compression_not_policy']['policy_target_world_B'],'1')

    def test_benchmark_includes_essential_failure_cases(self):
        f_tags=set(tag for r in self.dataset['formulation_cases'] for tag in r['reference']['risk_tags'])
        c_tags=set(tag for r in self.dataset['candidate_cases'] for tag in r['reference']['risk_tags'])
        self.assertTrue({'prompt_injection','ambiguous_assignment','observational','finite_vs_population'}.issubset(f_tags))
        self.assertTrue({'arm_not_policy','off_support_r2','zero_arm_support'}.issubset(c_tags))


if __name__=='__main__':unittest.main()

class HtmlV04Tests(unittest.TestCase):
    def test_renderer_escapes_untrusted_fields(self):
        from evaluation.render_report import render_html
        report={'schema_version':'cfm-id-evaluation-run-v0.4','run_kind':'REAL_API',
                'timestamp_utc':'2026-10-17T16:34:00Z','model':'<script>bad()</script>',
                'summary':{},'cases':[{'id':'<img src=x onerror=alert(1)>','stage':'candidate',
                                       'status':'UNVERIFIED_CANDIDATE',
                                       'score':{'claim_match':True,'envelope_safe':True},
                                       'risk_tags':['<b>oops</b>']} ]}
        html=render_html(report)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('&lt;img src=x',html)
        self.assertNotIn('<script>bad()',html)
        self.assertNotIn('<img src=x onerror=',html)

    def test_renderer_labels_mock_as_not_real_llm(self):
        from evaluation.render_report import render_html
        report={'schema_version':'cfm-id-evaluation-run-v0.4','run_kind':'OFFLINE_FIXTURES_NOT_MODEL_EVALUATION',
                'timestamp_utc':'t','summary':{},'cases':[]}
        s=render_html(report)
        self.assertIn('尚未运行真实 LLM',s)
