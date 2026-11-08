from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cfm_id_llm.audit import audit_draft
from cfm_id_llm.business_presentation import (
    Audience, BusinessExplanationV05, explain_business, friendly_questions,
    render_business_html, render_business_text,
)
from cfm_id_llm.business_prompts import BUSINESS_SYSTEM_PROMPT_V05, PROMPT_VERSION_V05
from cfm_id_llm.candidate_reasoner import GatewayRunV03, GatewayV03
from cfm_id_llm.formulator import ProblemFormulator
from cfm_id_llm.mock_core import MockCorePort, MockCoreScenario
from cfm_id_llm.orchestration_schemas import HumanReviewV02, canonical_sha256
from cfm_id_llm.orchestrator import route_formulation
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.schemas import BusinessCase, DraftProblemSpec, TargetKind
from evaluation.business_benchmark import load_cases, run_one
from evaluation.build_business_cases import build

HERE=Path(__file__).resolve().parents[1]

def load_json(p):
    return json.loads((HERE/p).read_text(encoding='utf-8'))

def run_fixture(name, *, scenario=None, candidate=None, review=None):
    case=BusinessCase.model_validate(load_json('examples/'+name+'.json'))
    provider=MockProvider(load_json('examples/'+name+'_mock_response.json'))
    gateway=GatewayV03(provider,core=MockCorePort(scenario) if scenario else None,
                       candidate_provider=MockProvider(load_json('examples/'+candidate)) if candidate else None)
    return case,gateway.run(case,human_review=HumanReviewV02.model_validate(load_json('examples/'+review))
                            if review else None,allow_mock_preview=True)

class BusinessV05Tests(unittest.TestCase):
    def test_business_prompt_is_versioned_without_pasting_theorem_registry(self):
        self.assertIn('业务人员',BUSINESS_SYSTEM_PROMPT_V05)
        self.assertIn('不能为了适配现有定理',BUSINESS_SYSTEM_PROMPT_V05)
        self.assertIn('0.5.0',PROMPT_VERSION_V05)
        self.assertNotIn('available_routes',BUSINESS_SYSTEM_PROMPT_V05)

    def test_prompt_version_only_for_new_business_formulator(self):
        case=BusinessCase.model_validate(load_json('examples/sales_ambiguous.json'))
        mock=MockProvider(load_json('examples/sales_ambiguous_mock_response.json'))
        newer=ProblemFormulator(mock,system_prompt=BUSINESS_SYSTEM_PROMPT_V05,
                                prompt_version=PROMPT_VERSION_V05).formulate(case)
        older=ProblemFormulator(mock).formulate(case)
        self.assertEqual(newer.prompt_version,PROMPT_VERSION_V05)
        self.assertNotEqual(older.prompt_version,newer.prompt_version)
        self.assertEqual(older.review_status,newer.review_status)

    def test_ambiguous_case_uses_business_questions_only(self):
        case,r=run_fixture('sales_ambiguous')
        report=explain_business(case,r)
        self.assertEqual(report.stage,'NEED_INFORMATION')
        self.assertEqual(report.audience,Audience.BUSINESS)
        self.assertLessEqual(len(report.questions),2)
        self.assertTrue(any('随机' in x for x in report.questions))
        self.assertNotIn('Bernoulli', '\n'.join(report.questions))
        self.assertFalse(report.has_numerical_estimate)
        self.assertFalse(report.estimation_handoff_allowed)

    def test_investor_report_never_looks_like_roi_estimate(self):
        case,r=run_fixture('sales_ambiguous')
        report=explain_business(case,r,audience='investor')
        text=render_business_text(report)
        self.assertIn('投资回报',text)
        self.assertIn('没有估计',text)
        self.assertFalse(report.estimation_handoff_allowed)

    def test_scholar_has_A4_A5_and_technical_details(self):
        case,r=run_fixture('complete_formulation_demo')
        report=explain_business(case,r,audience=Audience.SCHOLAR)
        self.assertEqual(report.stage,'WAIT_REVIEW')
        self.assertTrue(any('A4 population level' in x for x in report.academic_details))
        self.assertTrue(any('A5 draft proposals' in x for x in report.academic_details))
        self.assertFalse(any('A4 population level' in x for x in explain_business(case,r).academic_details))

    def test_valid_mock_point_never_becomes_verified(self):
        case,r=run_fixture('complete_formulation_demo',scenario=MockCoreScenario(**load_json('examples/mock_core_point_scenario.json')),
                           review='TEST_ONLY_review_for_complete_case.json')
        self.assertEqual(r.routing.status,'MOCK_CORE_RESULT')
        for audience in Audience:
            view=explain_business(case,r,audience=audience)
            self.assertEqual(view.stage,'MOCK_PREVIEW')
            self.assertEqual(view.verification_level,'MOCK_ONLY')
            self.assertIn('模拟',view.summary)
            self.assertFalse(view.estimation_handoff_allowed)

    def test_mock_unsupported_with_candidate_is_unverified(self):
        case,r=run_fixture('weighted_exposure_demo',
            scenario=MockCoreScenario(**load_json('examples/mock_core_unsupported_scenario.json')),
            candidate='weighted_exposure_demo_mock_candidate.json',
            review='TEST_ONLY_review_for_weighted_exposure.json')
        self.assertEqual(r.candidate.status,'UNVERIFIED_CANDIDATE')
        for audience in Audience:
            view=explain_business(case,r,audience=audience)
            self.assertEqual(view.stage,'MOCK_PREVIEW')
            self.assertEqual(view.verification_level,'MOCK_ONLY')
            self.assertTrue('大模型' in view.summary or 'The AI' in view.summary)
            self.assertFalse(view.has_numerical_estimate)

    def test_candidate_does_not_mutate_original_target(self):
        case,r=run_fixture('weighted_exposure_demo',
            scenario=MockCoreScenario(**load_json('examples/mock_core_unsupported_scenario.json')),
            candidate='weighted_exposure_demo_mock_candidate.json',
            review='TEST_ONLY_review_for_weighted_exposure.json')
        view=explain_business(case,r,audience='scholar')
        self.assertTrue(any('NETWORK_DESIGN_STANDARDIZED_ARM_MEAN' in x for x in view.academic_details))
        self.assertTrue(any('consistency' in x for x in view.academic_details))
        self.assertIn('LLM_UNVERIFIED',' '.join(view.academic_details))

    def test_tampered_formulation_rejected_by_view(self):
        case,r=run_fixture('sales_ambiguous')
        bad=copy.deepcopy(r)
        bad.formulation.input_sha256='0'*64
        with self.assertRaises(ValueError): explain_business(case,bad)

    def test_tampered_route_rejected_by_view(self):
        case,r=run_fixture('sales_ambiguous')
        bad=copy.deepcopy(r)
        bad.routing.draft_sha256='0'*64
        with self.assertRaises(ValueError): explain_business(case,bad)

    def test_candidate_unrelated_route_rejected(self):
        case,r=run_fixture('weighted_exposure_demo',
            scenario=MockCoreScenario(**load_json('examples/mock_core_unsupported_scenario.json')),
            candidate='weighted_exposure_demo_mock_candidate.json',
            review='TEST_ONLY_review_for_weighted_exposure.json')
        bad=copy.deepcopy(r);bad.candidate.routing_sha256='0'*64
        with self.assertRaises(ValueError): explain_business(case,bad)

    def test_html_escapes_untrusted_business_text(self):
        case,r=run_fixture('sales_ambiguous')
        bad=copy.deepcopy(r)
        # Claim is generated by an untrusted model, so it must be escaped by HTML rendering.
        bad.formulation.draft.units_variables.outcome.value='<img src=x onerror=alert(1)>'
        bad.routing.draft_sha256=canonical_sha256(bad.formulation.draft)
        view=explain_business(case,bad)
        view.title='<script>alert(1)</script>'
        html=render_business_html(view)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',html)
        self.assertNotIn('<img src=x',html)

    def test_report_model_disallows_estimate_fabrication(self):
        case,r=run_fixture('sales_ambiguous')
        report=explain_business(case,r)
        with self.assertRaises(ValueError):
            BusinessExplanationV05.model_validate({**report.model_dump(), 'has_numerical_estimate':True})

    def test_catalog_has_24_plain_business_questions(self):
        rows=load_cases()
        self.assertEqual(len(rows),24)
        self.assertEqual(len({x['category'] for x in rows}),8)
        for row in rows:
            with self.subTest(id=row['id']):
                question=row['business_case']['business_question']
                self.assertLess(len(question),100)
                self.assertNotIn('识别算子',question)
                self.assertNotIn('Bernoulli',question)
                self.assertNotIn('A4',question)
                self.assertNotIn('R1a',question)
        self.assertEqual(build()['cases'],rows)

    def test_catalog_references_do_not_enter_real_prompt(self):
        case=load_cases()[0]
        class Spy(MockProvider):
            def __init__(self,resp):super().__init__(resp);self.prompts=[]
            def generate_json(self,*,system_prompt,user_prompt):
                self.prompts.append(user_prompt)
                return super().generate_json(system_prompt=system_prompt,user_prompt=user_prompt)
        # No valid synthetic mock response is needed to test prompt boundaries.
        sp=Spy({'invalid':'ignored'})
        res=run_one(case,sp)
        self.assertEqual(res['status'],'PROVIDER_OR_SCHEMA_FAILURE')
        self.assertTrue(sp.prompts)
        self.assertNotIn('reference_for_developers_only',sp.prompts[0])
        self.assertNotIn('principal_ambiguity',sp.prompts[0])

    def test_cli_accepts_plain_question(self):
        question=load_json('examples/sales_ambiguous.json')['business_question']
        cmd=[sys.executable,'-m','cfm_id_llm.business_cli','--question',question,
             '--mock-formulation','examples/sales_ambiguous_mock_response.json','--format','text']
        p=subprocess.run(cmd,cwd=HERE,capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('随机',p.stdout)
        self.assertIn('NEED_INFORMATION',p.stdout)
        self.assertNotIn('LLM_UNVERIFIED',p.stdout)

    def test_cli_external_call_requires_explicit_consent(self):
        p=subprocess.run([sys.executable,'-m','cfm_id_llm.business_cli',
                          '--question','公司想知道干预对业绩的影响。','--formulation-provider','openai-chat',
                          '--formulation-model','dummy'], cwd=HERE,capture_output=True,text=True,timeout=30)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('--allow-external',p.stderr)

    def test_benchmark_dry_run_does_not_call_cloud(self):
        p=subprocess.run([sys.executable,'-m','evaluation.business_benchmark','--dry-run','--max-cases','3'],
                         cwd=HERE,capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr)
        x=json.loads(p.stdout)
        self.assertFalse(x['live_llm_called'])
        self.assertEqual(x['selected'],3)
        self.assertNotIn('reference_for_developers_only',p.stdout)

    def test_benchmark_requires_explicit_consent(self):
        p=subprocess.run([sys.executable,'-m','evaluation.business_benchmark','--model','dummy'],
                         cwd=HERE,capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,2)
        self.assertIn('stopped safely',p.stderr)

    def test_f17_fixed_others_not_forced_to_define_exposure(self):
        ds=load_json('evaluation/network_benchmark.json')
        item=next(x for x in ds['formulation_cases'] if x['id']=='F17')
        case=BusinessCase.model_validate(item['business_case'])
        draft=DraftProblemSpec.model_validate(load_json('evaluation/fixtures/formulation/F17.json'))
        report=audit_draft(case,draft,provider='TEST_ONLY')
        self.assertFalse(any(x.code=='A3_EXPOSURE_UNRESOLVED' for x in report.issues))
        self.assertEqual(report.review_status,'DRAFT_READY_FOR_HUMAN_REVIEW')

    def test_vague_direct_effect_still_requires_exposure_clarification(self):
        # A direct-effect label alone does not commit to a full-assignment target.
        from cfm_id_llm.schemas import EvidenceQuote, SemanticClaim
        case=BusinessCase(case_id='vague',business_question='我们想知道 AI 对销售员的直接效果如何。')
        draft=DraftProblemSpec(
            target={'kind':'DIRECT_EFFECT','description':{
                'value':'销售员的直接效果','basis':'EXPLICIT_TEXT',
                'evidence':[{'source_id':'business_question','quote':'直接效果'}]}},
            units_variables={'analysis_unit':{
                'value':'销售员','basis':'EXPLICIT_TEXT','evidence':[{'source_id':'business_question','quote':'销售员'}]},
                'treatment':{'value':'AI','basis':'EXPLICIT_TEXT','evidence':[{'source_id':'business_question','quote':'AI'}]},
                'outcome':{'value':'效果','basis':'EXPLICIT_TEXT','evidence':[{'source_id':'business_question','quote':'效果'}]}},
            structure={'unit_network':{'value':'存在员工联系','basis':'INTERPRETATION',
                       'evidence':[{'source_id':'business_question','quote':'销售员'}]}},
        )
        report=audit_draft(case,draft,provider='TEST_ONLY')
        self.assertTrue(any(x.code=='A3_EXPOSURE_UNRESOLVED' for x in report.issues))

    def test_html_escapes_scholar_expression(self):
        case,r=run_fixture('complete_formulation_demo',
            scenario=MockCoreScenario(**load_json('examples/mock_core_point_scenario.json')),
            review='TEST_ONLY_review_for_complete_case.json')
        bad=copy.deepcopy(r)
        bad.routing.core_expression='<svg onload="alert(1)">'
        view=explain_business(case,bad,audience='scholar')
        html=render_business_html(view)
        self.assertNotIn('<svg onload=',html)
        self.assertIn('&lt;svg onload=',html)

    def test_english_business_view_does_not_invent_an_answer(self):
        c=BusinessCase.model_validate(load_json('examples/sales_ambiguous.json'))
        c.response_language='en'
        p=MockProvider(load_json('examples/sales_ambiguous_mock_response.json'))
        r=GatewayV03(p).run(c)
        view=explain_business(c,r,audience='business')
        self.assertEqual(view.response_language,'en')
        self.assertEqual(view.stage,'NEED_INFORMATION')
        self.assertIn('cannot yet',view.summary)
        self.assertIn('Questions to clarify:',render_business_text(view))

if __name__=='__main__':unittest.main()
