"""v0.10 standalone Gateway quality and NBIB regression; no Core certification."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cfm_id_llm.schemas import (
    BusinessCase, SourceDocument, SourceKind, SemanticClaim, EvidenceQuote,
    TargetKind, TargetDraft, DraftProblemSpec, UnitsVariablesDraft,
    InformationDesignDraft, AssignmentFamily, ClarificationQuestion,
)
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality_formulator import A0QualityFormulatorV010,A0QualityValidationError
from cfm_id_llm.quality_prompts import make_quality_user_prompt, SYSTEM_PROMPT_V010
from cfm_id_llm.quality import (
    MultiQueryDraftV010, BusinessInquiryV010, QuerySemanticsV010,
    audit_business_quality, draft_from_v09,MultiQueryQualityReportV010,
)
from cfm_id_llm.multiquery import MultiQueryDraftV09
from evaluation.nbib_semantic_eval import (
    load_reference, load_public_business_case, make_reference_only_fixture,
    evaluate, score_human_review,ROOT as NBIB_ROOT,
)

ROOT=Path(__file__).resolve().parents[1]


def claim(text: str, *, quote: str | None = None, source: str='business_question', basis='EXPLICIT_TEXT'):
    return SemanticClaim(value=text,basis=basis,
        evidence=[EvidenceQuote(source_id=source,quote=quote or text)])


class A0QualityTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(
            case_id='QA_SALES',
            business_question=('我们有300名销售员，大家通过合作网络分享客户。我们想知道'
                               '全员推广后团队销售额如何，以及没有开通的同事是否受影响。'),
            sources=[SourceDocument(source_id='protocol',kind=SourceKind.STUDY_PROTOCOL,
                                    text='从300名销售员中恰好随机抽取150名使用AI助手，实验持续8周。'),
                     SourceDocument(source_id='dict',kind=SourceKind.DATA_DICTIONARY,
                                    text='表头：sales_before、sales_after，只有有限数据。')],
        )
        self.q1=BusinessInquiryV010(
            query_id='q1',
            business_goal=claim('全员推广后团队销售额如何'),
            target=TargetDraft(kind=TargetKind.FIXED_POLICY_VALUE,
                description=claim('全员推广后团队销售额如何')),
            semantics=QuerySemanticsV010(
                target_population=claim('300名销售员',quote='300名销售员'),
                intervention=claim('全员推广',quote='全员推广'),
                policy_assignment=claim('全部销售员使用AI助手',quote='全员推广',basis='INTERPRETATION'),
                aggregation=claim('团队销售额',quote='团队销售额'),
                time_horizon=claim('8周',quote='实验持续8周',source='protocol'),
            ))
        self.q2=BusinessInquiryV010(
            query_id='q2',
            business_goal=claim('没有开通的同事是否受影响'),
            target=TargetDraft(kind=TargetKind.SPILLOVER_EFFECT,
                description=claim('没有开通的同事是否受影响')),
            semantics=QuerySemanticsV010(
                target_population=claim('未开通的同事',quote='没有开通的同事'),
                neighbor_exposure=claim('通过合作网络的同事之间可能产生影响',quote='合作网络',basis='INTERPRETATION'),
            ))
        self.shared=DraftProblemSpec(
            target=self.q1.target,
            units_variables=UnitsVariablesDraft(
                analysis_unit=claim('销售员',quote='销售员'),
                treatment=claim('AI助手是否开通',quote='使用AI助手',source='protocol'),
                outcome=claim('销售额',quote='销售额')),
            information_design=InformationDesignDraft(
                assignment_family=AssignmentFamily.COMPLETE_RANDOMIZATION,
                assignment_law=claim('固定抽150名',source='protocol',quote='恰好随机抽取150名'),
            ),
        )
        self.draft=MultiQueryDraftV010(shared_draft=self.shared,primary_query_id='q1',
                                       queries=[self.q1,self.q2])

    def audit(self,draft=None,case=None):
        return audit_business_quality(case or self.case,draft or self.draft,
            provider='mock-fixture',prompt_version='quality-v010-test')

    def test_exact_v09_is_reused(self):
        x=self.draft.as_v09()
        self.assertIsInstance(x,MultiQueryDraftV09)
        self.assertEqual(len(x.queries),2)
        self.assertNotIn('semantics',x.model_dump_json())

    def test_business_ready_even_when_population_A4_missing(self):
        r=self.audit()
        self.assertEqual(r.overall_business_status,'FORMALIZATION_READY')
        self.assertTrue(r.scientific_review_required)
        self.assertTrue(all(q.scientific_status=='SCIENTIFIC_REVIEW_REQUIRED' for q in r.query_quality))
        self.assertTrue(all(not q.business_questions for q in r.query_quality))
        self.assertTrue(all('A4_POPULATION_INFORMATION_OPEN' in {i.code for i in q.legacy_issues}
                            for q in r.query_quality))
        self.assertFalse(r.core_called)
        self.assertFalse(r.formal_core_spec_generated)

    def test_science_questions_not_asked_to_salesperson(self):
        draft=self.draft.model_copy(deep=True)
        draft.queries[0].clarifying_questions.append(ClarificationQuestion(
            field_path='information_design.population_information_level',
            question='你能描述精确的总体 A4 算子吗？',reason='识别条件尚未授权',priority='HIGH'))
        r=self.audit(draft)
        self.assertEqual(r.overall_business_status,'FORMALIZATION_READY')
        self.assertFalse(r.query_quality[0].business_questions)
        self.assertTrue(any(a.owner=='SCIENTIFIC_REVIEWER' for a in r.query_quality[0].actions))

    def test_unresolved_business_target_still_asks(self):
        draft=self.draft.model_copy(deep=True)
        draft.queries[0].target=TargetDraft()
        draft.shared_draft.target=TargetDraft()
        r=self.audit(draft)
        self.assertEqual(r.query_quality[0].business_status,'BUSINESS_CLARIFICATION_REQUIRED')
        self.assertTrue(any(x.field_path=='target.kind' for x in r.query_quality[0].business_questions))
        self.assertNotIn('arm mean',r.query_quality[0].business_questions[0].question)

    def test_missing_a2_goes_to_reextract_first(self):
        draft=self.draft.model_copy(deep=True)
        draft.shared_draft.units_variables.outcome=SemanticClaim()
        r=self.audit(draft)
        self.assertEqual(r.overall_business_status,'FORMULATION_RECHECK_REQUIRED')
        self.assertFalse(r.query_quality[0].business_questions)
        self.assertTrue(any(a.owner=='A0_FORMULATOR' and a.code=='A2_MISSING_OUTCOME'
                            for a in r.query_quality[0].actions))

    def test_missing_policy_slot_rechecks_explicit_all_treated(self):
        draft=self.draft.model_copy(deep=True)
        draft.queries[0].semantics.policy_assignment=SemanticClaim()
        r=self.audit(draft)
        self.assertEqual(r.query_quality[0].business_status,'FORMULATION_RECHECK_REQUIRED')
        self.assertTrue(any(a.code=='POLICY_ASSIGNMENT_SEMANTICS_OPEN'
                            and a.owner=='A0_FORMULATOR' for a in r.query_quality[0].actions))

    def test_policy_present_does_not_become_core_typed_assignment(self):
        r=self.audit()
        self.assertIn('全部',r.draft.queries[0].semantics.policy_assignment.value)
        self.assertFalse(r.formal_core_spec_generated)
        self.assertEqual(r.mathematical_verification,'NOT_PERFORMED')

    def test_policy_scope_conflict_sent_to_reextraction(self):
        draft=self.draft.model_copy(deep=True)
        draft.queries[0].semantics.policy_assignment=claim(
            '只给少数销售员开通',quote='全员推广',basis='INTERPRETATION')
        r=self.audit(draft)
        self.assertEqual(r.query_quality[0].business_status,'FORMULATION_RECHECK_REQUIRED')
        self.assertTrue(any(x.code=='POLICY_SCOPE_SEMANTIC_CONFLICT' for x in r.query_quality[0].actions))
        self.assertFalse(r.core_called)

    def test_spillover_untreated_population_and_global_policy_requires_recheck(self):
        draft=self.draft.model_copy(deep=True)
        draft.queries[1].semantics.policy_assignment=claim('全员推广')
        before=draft.model_dump_json()
        report=self.audit(draft)
        self.assertEqual(report.overall_business_status,'FORMULATION_RECHECK_REQUIRED')
        self.assertTrue(any(a.code=='SPILLOVER_POLICY_POPULATION_CONFLICT'
                            and a.owner=='A0_FORMULATOR' for a in report.query_quality[1].actions))
        self.assertFalse(report.query_quality[1].business_questions)
        self.assertEqual(before,draft.model_dump_json())
        self.assertFalse(report.core_called)
        self.assertFalse(report.estimation_handoff_allowed)

    def test_spillover_explicit_peer_or_focal_exclusion_not_flagged(self):
        for policy in ('其他人全员推广，本人保持未开通','所有邻居开通，本人不开通','除本人外其余全员推广'):
            with self.subTest(policy=policy):
                case=self.case.model_copy(update={'business_question':self.case.business_question+policy+'。'})
                draft=self.draft.model_copy(deep=True)
                draft.queries[1].semantics.policy_assignment=claim(policy)
                report=self.audit(draft,case)
                self.assertFalse(any(a.code=='SPILLOVER_POLICY_POPULATION_CONFLICT'
                                     for a in report.query_quality[1].actions))

    def test_historical_or_mixed_population_not_assumed_currently_untreated(self):
        for population in ('以前未开通的同事','已开通和未开通的同事'):
            with self.subTest(population=population):
                case=self.case.model_copy(update={'business_question':self.case.business_question+population+'。'})
                draft=self.draft.model_copy(deep=True)
                draft.queries[1].semantics.target_population=claim(population)
                draft.queries[1].semantics.policy_assignment=claim('全员推广')
                report=self.audit(draft,case)
                self.assertFalse(any(a.code=='SPILLOVER_POLICY_POPULATION_CONFLICT'
                                     for a in report.query_quality[1].actions))

    def test_unknown_spillover_policy_is_not_filled_from_other_query(self):
        report=self.audit()
        self.assertEqual(report.draft.queries[1].semantics.policy_assignment.basis,'UNRESOLVED')
        self.assertEqual(report.overall_business_status,'FORMALIZATION_READY')
        self.assertFalse(any(a.code=='SPILLOVER_POLICY_POPULATION_CONFLICT'
                             for a in report.query_quality[1].actions))

    def test_population_policy_recheck_is_specific_to_spillover(self):
        draft=self.draft.model_copy(deep=True)
        draft.queries[0].semantics.target_population=claim('未开通的同事',quote='没有开通的同事')
        report=self.audit(draft)
        self.assertFalse(any(a.code=='SPILLOVER_POLICY_POPULATION_CONFLICT'
                             for a in report.query_quality[0].actions))

    def test_technical_query_cannot_mask_as_business_question(self):
        draft=self.draft.model_copy(deep=True)
        draft.queries[0].clarifying_questions.append(ClarificationQuestion(
            field_path='target.kind',question='请你补充总体 A4 观测律和识别假设吗？',
            reason='提供数学算子以便推导',priority='HIGH'))
        r=self.audit(draft)
        self.assertEqual(r.query_quality[0].business_status,'FORMALIZATION_READY')
        self.assertFalse(r.query_quality[0].business_questions)
        self.assertTrue(any(a.code=='REVIEW_INSTEAD_OF_BUSINESS_QUESTION'
                            and a.owner=='SCIENTIFIC_REVIEWER' for a in r.query_quality[0].actions))

    def test_unresolved_spillover_comparator_science_review(self):
        r=self.audit()
        self.assertTrue(any(a.code=='EFFECT_COMPARATOR_OPEN' and a.owner=='SCIENTIFIC_REVIEWER'
                            for a in r.query_quality[1].actions))
        self.assertEqual(r.query_quality[1].business_status,'FORMALIZATION_READY')

    def test_legacy_audit_preserves_binding(self):
        r=self.audit()
        self.assertEqual(r.legacy_audit.draft,r.draft.as_v09())
        self.assertEqual(r.legacy_audit.case_id,r.case_id)

    def test_signature_changes_if_one_query_changes(self):
        r=self.audit()
        mutated=r.model_dump(mode='json')
        mutated['draft']['queries'][1]['semantics']['aggregation']={
            'value':'平均增长','basis':'INTERPRETATION',
            'evidence':[{'source_id':'business_question','quote':'销售额'}]}
        with self.assertRaises(ValueError):
            MultiQueryQualityReportV010.model_validate(mutated)

    def test_policy_semantics_citation_forged_rejected(self):
        d=self.draft.model_dump(mode='json')
        d['queries'][0]['semantics']['policy_assignment']['evidence'][0]['quote']='虚构所有人全部强制处理'
        with self.assertRaises(ValueError):
            self.audit(MultiQueryDraftV010.model_validate(d))

    def test_policy_semantics_wrong_source_rejected(self):
        d=self.draft.model_dump(mode='json')
        d['queries'][0]['semantics']['policy_assignment']['evidence'][0]['source_id']='dict'
        with self.assertRaises(ValueError):
            self.audit(MultiQueryDraftV010.model_validate(d))

    def test_invalid_A5_certified_rejected(self):
        d=self.draft.model_dump(mode='json')
        d['shared_draft']['assumptions']=[{
            'name':'自我证明','statement':'本研究不依赖额外条件','status':'CERTIFIED',
            'basis':'LLM_SUGGESTION','evidence':[]}]
        with self.assertRaises(ValueError):
            MultiQueryDraftV010.model_validate(d)

    def test_model_cannot_add_point_field(self):
        d=self.draft.model_dump(mode='json');d['certificate']='POINT'
        with self.assertRaises(ValueError):MultiQueryDraftV010.model_validate(d)

    def test_primary_target_cannot_disagree(self):
        d=self.draft.model_dump(mode='json');d['primary_query_id']='q2'
        with self.assertRaises(ValueError):MultiQueryDraftV010.model_validate(d)

    def test_query_duplicate_rejected(self):
        d=self.draft.model_dump(mode='json');d['queries'][1]['query_id']='q1'
        with self.assertRaises(ValueError):MultiQueryDraftV010.model_validate(d)

    def test_too_many_queries_rejected(self):
        d=self.draft.model_dump(mode='json')
        for k in range(3,10):
            q=copy.deepcopy(d['queries'][1]);q['query_id']=f'q{k}'
            q['business_goal']['value']=f'业务目标{k}'
            d['queries'].append(q)
        with self.assertRaises(ValueError):MultiQueryDraftV010.model_validate(d)

    def test_data_dictionary_cannot_be_source_of_new_goal(self):
        d=self.draft.model_dump(mode='json')
        d['queries'][1]['business_goal']={
            'value':'sales_before', 'basis':'EXPLICIT_TEXT',
            'evidence':[{'source_id':'dict','quote':'sales_before'}]}
        r=self.audit(MultiQueryDraftV010.model_validate(d))
        self.assertEqual(r.query_quality[1].business_status,'FORMULATION_RECHECK_REQUIRED')
        self.assertTrue(any(a.code=='BUSINESS_GOAL_FROM_DATA_DICTIONARY_ONLY'
                            for a in r.query_quality[1].actions))

    def test_legacy_migration_leaves_semantic_slots_unresolved(self):
        migrated=draft_from_v09(self.draft.as_v09())
        self.assertEqual(migrated.queries[0].semantics.policy_assignment.basis,'UNRESOLVED')
        self.assertEqual(migrated.queries[1].semantics.comparator.basis,'UNRESOLVED')
        r=self.audit(migrated)
        self.assertEqual(r.query_quality[0].business_status,'FORMULATION_RECHECK_REQUIRED')

    def test_current_new_schema_only_no_math_package(self):
        script=('import sys, cfm_id_llm.quality; '
                'print("pfn_pipeline" in sys.modules, "cfm_id_bridge" in sys.modules)')
        p=subprocess.run([sys.executable,'-c',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(p.stdout.strip(),'False False')

    def test_prompt_mentions_semantic_fields_and_science_boundary(self):
        s=make_quality_user_prompt(self.case)
        self.assertIn('policy_assignment',s)
        self.assertIn('case_id',s)
        self.assertIn('科学条件',SYSTEM_PROMPT_V010)

    def test_mock_provider_uses_v010_not_v09(self):
        raw=self.draft.model_dump(mode='json')
        r=A0QualityFormulatorV010(MockProvider(raw)).formulate(self.case)
        self.assertEqual(r.gateway_version,'0.10.0')
        self.assertEqual(r.overall_business_status,'FORMALIZATION_READY')

    def test_untrusted_model_invalid_semantics_rejected(self):
        d=self.draft.model_dump(mode='json')
        d['queries'][0]['semantics']['policy_assignment']['evidence'][0]['quote']='模型伪造引文'
        with self.assertRaises(A0QualityValidationError):
            A0QualityFormulatorV010(MockProvider(d)).formulate(self.case)

    def test_cli_mock_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            case=path/'case.json';resp=path/'mock.json';out=path/'out.json'
            case.write_text(self.case.model_dump_json(),encoding='utf-8')
            resp.write_text(self.draft.model_dump_json(),encoding='utf-8')
            cmd=[sys.executable,'-m','cfm_id_llm.quality_cli','--case-json',str(case),
                 '--provider','mock','--mock-response',str(resp),'--format','json','--output',str(out)]
            x=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(x.returncode,0,x.stderr)
            result=json.loads(out.read_text(encoding='utf-8'))['formulation']
            self.assertEqual(result['overall_business_status'],'FORMALIZATION_READY')
            self.assertFalse(result['core_called'])

    def test_cli_no_external_without_consent(self):
        cmd=[sys.executable,'-m','cfm_id_llm.quality_cli','--question',self.case.business_question,
             '--provider','openai-chat','--model','n/a']
        x=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(x.returncode,0)
        self.assertIn('allow-external',x.stderr)

    def test_cli_preview_no_llm(self):
        cmd=[sys.executable,'-m','cfm_id_llm.quality_cli','--question',self.case.business_question,
             '--preview','--format','json']
        x=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(x.returncode,0,x.stderr)
        self.assertFalse(json.loads(x.stdout)['llm_called'])


class NBIBEvaluationTests(unittest.TestCase):
    def test_21_public_business_packets(self):
        entries=load_reference()
        self.assertEqual(len(entries),21)
        self.assertEqual(len(list((NBIB_ROOT/'public/cases').glob('NBIB-*'))),21)

    def test_no_research_gold_inside_public_case(self):
        public=NBIB_ROOT/'public'
        self.assertEqual(list(public.rglob('oracle')),[])
        self.assertEqual(list(public.rglob('gold')),[])
        self.assertTrue((NBIB_ROOT/'research_only/target_reference.json').exists())

    def test_real_public_documents_intake(self):
        intake=load_public_business_case('NBIB-001')
        self.assertEqual(intake.case.case_id,'NBIB-001')
        self.assertTrue(any(x.kind==SourceKind.STUDY_PROTOCOL for x in intake.case.sources))
        self.assertLessEqual(len(intake.attachments),8)
        self.assertTrue(any(x.mode=='SCHEMA_ONLY' for x in intake.attachments))

    def test_reference_mock_never_claims_llm_accuracy(self):
        scores,worksheet=evaluate(max_cases=2)
        self.assertEqual(scores['valid_schema_and_quotes'],2)
        self.assertEqual(scores['evaluation_kind'],'OFFLINE_REFERENCE_FIXTURE_ONLY')
        self.assertEqual(scores['business_semantic_accuracy'],
                         'NOT_AUTOMATICALLY_SCORED_REQUIRES_EXPERT')
        self.assertIsNone(worksheet['queries'][0]['human_labels']['critical_semantic_error'])

    def test_reference_all_21_target_only(self):
        scores,worksheet=evaluate(max_cases=21)
        self.assertEqual(scores['valid_schema_and_quotes'],21)
        self.assertEqual(scores['target_multiset_exact'],21)
        self.assertEqual(scores['formal_math_accuracy'],'NOT_MEASURED')
        self.assertEqual(scores['online_calls_made'],False)
        self.assertEqual(len(worksheet['queries']),sum(len(x['expected']) for x in load_reference()))

    def test_reference_gold_is_not_sent_in_model_prompt(self):
        intake=load_public_business_case('NBIB-001')
        text=make_quality_user_prompt(intake.case)
        self.assertNotIn('gold/references',text)
        self.assertNotIn('candidate_math_route',text)
        self.assertNotIn('FORMAL_BACKED',text)

    def test_online_requires_double_explicit_consent(self):
        with self.assertRaises(ValueError):
            evaluate(provider_name='openai-chat',model='x',max_cases=1,allow_external=True)

    def test_human_review_scores_only_real_bools(self):
        _,worksheet=evaluate(max_cases=1)
        result=score_human_review(worksheet)
        self.assertIsNone(result['critical_semantic_error_rate'])
        first=worksheet['queries'][0]['human_labels']
        first['business_goal_fidelity']=True
        first['critical_semantic_error']=False
        scores=score_human_review(worksheet)
        self.assertEqual(scores['fields']['business_goal_fidelity']['reviewed'],1)
        self.assertEqual(scores['fields']['business_goal_fidelity']['pass_rate'],1.)
        self.assertEqual(scores['critical_semantic_error_rate'],0.)

    def test_cli_eval_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=Path(tmp)/'scores.json';review=Path(tmp)/'review.json'
            cmd=[sys.executable,'-m','evaluation.nbib_semantic_eval','--max-cases','1',
                 '--output',str(result),'--human-review-template',str(review)]
            x=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(x.returncode,0,x.stderr)
            self.assertEqual(json.loads(result.read_text())['cases_total'],1)
            self.assertEqual(json.loads(review.read_text())['kind'],
                             'HUMAN_SEMANTIC_ADJUDICATION_TEMPLATE_UNSCORED')

    def test_submission_manifest_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            load_public_business_case('../research_only')


if __name__=='__main__':
    unittest.main()
