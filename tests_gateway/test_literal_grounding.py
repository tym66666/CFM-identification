from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.literal_grounding import (grounding_slots,make_grounding_request,build_grounding_result,
    QuoteReviewedIntake,TwoResponseMock,render_grounding_html)
from cfm_id_llm.literal_review_cli import main


class LiteralGroundingTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='GROUND-TEST',business_question='公司有300名员工。员工会互相交流客户问题。目标是获得AI助手是否改善员工自己的客户满意度。比较情形、汇总和时点尚未决定。核心伙伴过半启用是记录的分组。')
        self.catalog=build_catalog(self.case)
        self.fact=lambda text,i=0,reading='explicit':dict(text=text,refs=[self.catalog[i]['ref']],reading=reading)
        c=self.fact
        self.initial={'facts':{'units':c('300名员工'),'action':c('获得AI助手',2),'outcome':c('客户满意度',2,'interpretation'),
            'connections':c('员工交流，存在同伴因果影响',1),'peer_measure':c('核心伙伴过半启用',4)},
            'goals':[dict(form='comparison',focus='own',question=c('助手是否改善本人的满意度',2),who=c('全体300人'),
                situation_a=dict(own_action=c('获得AI助手',2)),
                situation_b=dict(own_action=c('未获得AI助手',3)))]}
        _,self.slots,_=grounding_slots(self.case,self.initial)
        self.review={'selections':[dict(slot_id=s['slot_id'],decision='unknown',source_ref=None,quote=None,reason='尚需核对该项口径') for s in self.slots]}

    def select(self,path,text=None,decision='quote',source_ref=None):
        i=next(i for i,s in enumerate(self.slots) if s['path']==path)
        if text is not None and source_ref is None:
            source_ref=next(s['ref'] for s in self.catalog if text in s['quote'])
        self.review['selections'][i].update(decision=decision,source_ref=source_ref,quote=text,reason='根据对应原句核对字段含义')

    def result(self):return build_grounding_result(self.case,self.initial,self.review,'offline-test')

    def test_literal_selection_restores_known_outcome_and_clears_guessed_comparator(self):
        self.select(['facts','outcome'],'客户满意度')
        self.select(['goals',0,'situation_a','own_action'],'获得AI助手')
        before=deepcopy(self.initial);r=self.result();self.assertEqual(before,self.initial)
        self.assertEqual(r['quality']['draft']['shared_draft']['units_variables']['outcome']['value'],'客户满意度')
        self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['comparator']['value'])
        self.assertTrue(r['quote_identity_verified']);self.assertFalse(r['semantic_correctness_verified'])

    def test_majority_fragment_cannot_be_freely_replaced_by_someone(self):
        self.select(['facts','peer_measure'],'核心伙伴过半启用')
        r=self.result();self.assertEqual(r['quality']['draft']['shared_draft']['structure']['exposure_mapping']['value'],'核心伙伴过半启用')
        i=next(i for i,s in enumerate(self.slots) if s['path']==['facts','peer_measure'])
        self.review['selections'][i]['quote']='核心伙伴有人启用'
        with self.assertRaises(A0QualityValidationError) as e:self.result()
        self.assertEqual(e.exception.code,'GROUNDING_QUOTE_NOT_FOUND')

    def test_existing_ref_does_not_allow_inventing_zero_peer_condition(self):
        self.select(['goals',0,'situation_b','peers'],'核心伙伴无人启用',source_ref=self.catalog[4]['ref'])
        with self.assertRaises(A0QualityValidationError) as e:self.result()
        self.assertEqual(e.exception.code,'GROUNDING_QUOTE_NOT_FOUND')

    def test_relationship_quote_removes_unstated_causal_claim_without_approving_anything(self):
        self.select(['facts','connections'],'员工会互相交流客户问题')
        r=self.result();d=r['quality']['draft']['shared_draft']
        self.assertEqual(d['structure']['unit_network']['value'],'员工会互相交流客户问题')
        self.assertFalse(d['assumptions']);self.assertFalse(r['scientific_approval'])

    def test_population_ambiguity_stays_unknown_and_preserves_prior_proposal(self):
        self.select(['goals',0,'who'],decision='ambiguous',source_ref=self.catalog[0]['ref'])
        r=self.result();self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['target_population']['value'])
        self.assertEqual(r['initial_business_draft']['goals'][0]['who']['text'],'全体300人')
        self.assertTrue(any(x['code']=='SOURCE_SCOPE_AMBIGUOUS' for x in r['internal_recheck']))

    def test_whole_review_is_required_missing_duplicate_or_foreign_slot_rejected(self):
        for mode in ('missing','duplicate','foreign'):
            raw=deepcopy(self.review)
            if mode=='missing':raw['selections'].pop()
            elif mode=='duplicate':raw['selections'][-1]=deepcopy(raw['selections'][0])
            else:raw['selections'][-1]['slot_id']='foreign'
            with self.subTest(mode=mode),self.assertRaises(A0QualityValidationError) as e:
                build_grounding_result(self.case,self.initial,raw,'offline-test')
            self.assertEqual(e.exception.code,'GROUNDING_COVERAGE_REJECTED')

    def test_case_and_candidate_changes_invalidate_old_review_ids(self):
        for change in ('case','draft'):
            case=self.case;initial=deepcopy(self.initial)
            if change=='case':case=self.case.model_copy(update={'case_id':'ANOTHER'})
            else:initial['goals'][0]['who']['text']='另一人群'
            with self.subTest(change=change),self.assertRaises(A0QualityValidationError):
                build_grounding_result(case,initial,self.review,'offline-test')

    def test_unknown_decision_cannot_smuggle_value_or_invalid_ref(self):
        self.review['selections'][0]['quote']='300名员工'
        with self.assertRaises(A0QualityValidationError) as e:self.result()
        self.assertEqual(e.exception.code,'GROUNDING_SCHEMA_REJECTED')
        self.review['selections'][0]['quote']=None;self.review['selections'][0]['source_ref']='bad'
        with self.assertRaises(A0QualityValidationError) as e:self.result()
        self.assertEqual(e.exception.code,'A0_REFERENCE_NOT_FOUND')

    def test_review_cannot_add_query_change_kind_or_approve_science(self):
        for key in ('target_kind','queries','scientific_approval'):
            raw=deepcopy(self.review);raw[key]=True
            with self.subTest(key=key),self.assertRaises(A0QualityValidationError):
                build_grounding_result(self.case,self.initial,raw,'offline-test')
        r=self.result();self.assertEqual(r['business_draft']['goals'][0]['focus'],'own')
        self.assertEqual(len(r['business_draft']['goals']),1)

    def test_valid_source_fragment_in_wrong_role_is_not_claimed_verified(self):
        self.select(['goals',0,'when'],'300名员工')
        r=self.result();self.assertFalse(r['semantic_correctness_verified']);self.assertFalse(r['business_approval'])
        self.assertFalse(r['core_called']);self.assertFalse(r['identification_ready']);self.assertFalse(r['estimation_handoff_allowed'])

    def test_exact_two_calls_including_failure_no_repair_calls(self):
        for bad in (False,True):
            review=deepcopy(self.review)
            if bad:review['selections'].pop()
            p=TwoResponseMock({'extraction':self.initial,'review':review});flow=QuoteReviewedIntake(p)
            if bad:
                with self.assertRaises(A0QualityValidationError):flow.formulate(self.case)
            else:flow.formulate(self.case)
            self.assertEqual(p.calls,2);self.assertEqual(flow.last_wire['extraction'],self.initial)

    def test_reason_and_source_html_are_escaped(self):
        self.review['selections'][0]['reason']='<script>alert(1)</script>'
        html=render_grounding_html(self.case,self.result())
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)

    def test_request_contains_complete_public_sources_and_bound_slots_no_gold(self):
        old=self.case.model_dump();_,user,_=make_grounding_request(self.case,self.initial)
        self.assertEqual(old,self.case.model_dump());self.assertIn(self.case.business_question,user)
        self.assertIn(self.slots[0]['slot_id'],user)
        self.assertIn('不可信初稿',user)

    def test_cli_offline_two_responses_and_plain_reply_preview(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);f=p/'fixture.json';f.write_text(json.dumps({'extraction':self.initial,'review':self.review}),encoding='utf8')
            out=p/'out'
            self.assertEqual(main(['--question',self.case.business_question,'--case-id',self.case.case_id,
                '--mock-response',str(f),'--output-dir',str(out)]),0)
            saved=json.loads((out/'model_draft.json').read_text(encoding='utf8'));self.assertEqual(set(saved),{'extraction','review'})
            self.assertEqual(main(['--resume',str(out),'--reply','先不确定对照，时间看第四周。','--preview','--output-dir',str(p/'reply')]),0)


if __name__=='__main__':unittest.main()
