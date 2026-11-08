"""Meaningful boundary/round-trip tests. No HTTP or credential access."""
from copy import deepcopy
import json, tempfile, unittest
from pathlib import Path
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.business_formulator import BusinessFormulator, make_business_request
from cfm_id_llm.business_shape_cli import main
from cfm_id_llm.reviewed_intake import append_business_reply, render_confirmation_html


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='TEST-BUSINESS',business_question='我们有12家门店，邻店会互相调货。每家独立抽签开提醒。想看自己开提醒、两个邻店中一家开时，全体12家第四周缺货率的等权平均。其他门店按原抽签方式考虑。')
        refs=[x['ref'] for x in build_catalog(self.case)]
        self.fact=lambda text,reading='explicit':dict(text=text,refs=[refs[0]],reading=reading)
        c=self.fact
        self.raw={'facts':{'units':c('门店'),'action':c('开提醒'),'outcome':c('缺货率'),
            'historical_assignment':c('每家独立抽签'),'assignment_family':'INDEPENDENT_BERNOULLI',
            'connections':c('邻店互相调货'),'peer_measure':c('两个邻店中开提醒的家数')},
            'goals':[{'form':'level','quantity':'mean','question':c('一个情形的缺货率平均'),
                'who':c('全体12家'),'when':c('第四周'),'summarize':c('每家等权平均'),
                'situation':{'own_action':c('开提醒'),'peers':c('两个邻店恰有一家开提醒')},
                'remaining_assignments':c('其他门店按原抽签方式考虑')}]}

    def run_wire(self,raw=None):
        p=MockProvider(self.raw if raw is None else raw)
        result=BusinessFormulator(p).formulate(self.case)
        self.assertEqual(p.calls,1)
        return result

    def comparison(self):
        g=self.raw['goals'][0]
        g.pop('quantity');s=g.pop('situation');g.update(form='comparison',focus='peers',
            situation_a={'own_action':self.fact('不开提醒'),'peers':self.fact('超过一半开提醒')},
            situation_b={'own_action':self.fact('不开提醒'),'peers':self.fact('不超过一半开提醒')})
        return g

    def policy(self):
        g=self.raw['goals'][0]
        for k in ('quantity','situation','remaining_assignments'):g.pop(k)
        g.update(form='policy',task='choose',action_or_rule=self.fact('决定给哪些门店开提醒'),constraints=self.fact('恰好给6家开提醒'))
        return g

    def test_level_preserves_population_remaining_distribution_and_no_comparator(self):
        before=deepcopy(self.raw);r=self.run_wire();self.assertEqual(before,self.raw)
        q=r['quality']['draft']['queries'][0];s=q['semantics']
        self.assertEqual(q['target']['kind'],'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN')
        self.assertEqual(s['target_population']['value'],'全体12家')
        self.assertIn('原抽签',s['standardization_distribution']['value'])
        self.assertIsNone(s['comparator']['value'])
        self.assertFalse(r['missing_information_candidates'])
        self.assertFalse(r['identification_ready'])

    def test_two_scenarios_retain_own_and_peer_states_without_zero_peer_invention(self):
        self.comparison();r=self.run_wire();s=r['quality']['draft']['queries'][0]['semantics']
        self.assertIn('不开提醒',s['intervention']['value']);self.assertIn('不开提醒',s['comparator']['value'])
        self.assertIn('不超过一半',s['comparator']['value']);self.assertNotIn('无人',s['comparator']['value'])
        self.assertIn('情形 A',s['neighbor_exposure']['value']);self.assertIn('情形 B',s['neighbor_exposure']['value'])

    def test_partial_scenario_does_not_mask_missing_own_action(self):
        g=self.comparison();g['situation_b']['own_action']=None
        r=self.run_wire();self.assertIn('goals.q1.situation_b.own_action',[x['path'] for x in r['missing_information_candidates']])
        self.assertNotIn('本人：',r['quality']['draft']['queries'][0]['semantics']['comparator']['value'])

    def test_no_copy_of_known_peer_definition_into_unknown_scenario(self):
        self.raw['goals'][0]['situation']['peers']=None
        r=self.run_wire();self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['neighbor_exposure']['value'])
        self.assertTrue(any(x['path'].endswith('situation.peers') for x in r['missing_information_candidates']))

    def test_identical_own_states_block_both_change_label_without_relabeling(self):
        g=self.comparison();g['focus']='both'
        r=self.run_wire();self.assertIn('FOCUS_CONTRADICTS_IDENTICAL_SCENARIOS',[x['code'] for x in r['internal_recheck']])
        self.assertEqual(r['business_draft']['goals'][0]['focus'],'both')
        self.assertEqual(r['quality']['draft']['queries'][0]['target']['kind'],'TOTAL_EFFECT')
        self.assertEqual(r['confirmation_card']['status'],'SOURCE_RECHECK_REQUIRED')
        self.assertFalse(r['identification_ready'])

    def test_five_distinct_metadata_refs_and_duplicates_preserved_without_rewriting_text(self):
        self.case=BusinessCase(case_id='MANY-REFS',business_question='门店有处理。记录了结果。还有关系。第一份资料。第二份资料。第三份资料。第四份资料。第五份资料。')
        refs=[x['ref'] for x in build_catalog(self.case)]
        c=lambda text:dict(text=text,refs=[refs[0]],reading='explicit')
        self.raw={'facts':{'available_data':dict(text='五份资料的描述',refs=refs[:5]+[refs[0]],reading='explicit')},
            'goals':[dict(form='other',question=c('其他问题'))]}
        before=deepcopy(self.raw);r=self.run_wire();self.assertEqual(before,self.raw)
        f=r['business_draft']['facts']['available_data'];self.assertEqual(f['refs'],refs[:5]);self.assertEqual(f['text'],'五份资料的描述')

    def test_projection_evidence_overflow_is_rejected_not_truncated(self):
        self.case=BusinessCase(case_id='MANY-REFS',business_question='第一条材料。第二条材料。第三条材料。第四条材料。第五条材料。第六条材料。第七条材料。第八条材料。第九条材料。第十条材料。')
        refs=[x['ref'] for x in build_catalog(self.case)]
        c=lambda text,rs:dict(text=text,refs=rs,reading='explicit')
        self.raw={'goals':[dict(form='level',quantity='mean',question=c('一个水平',[refs[0]]),
            situation=dict(own_action=c('自己的状态',refs[:5]),peers=c('同伴的状态',refs[5:10])))]}
        with self.assertRaises(A0QualityValidationError) as e:self.run_wire()
        self.assertEqual(e.exception.code,'BUSINESS_PROJECTION_EVIDENCE_LIMIT')

    def test_policy_needs_action_constraints_not_solution_comparator_or_peer_state(self):
        self.policy();r=self.run_wire();q=r['quality']['draft']['queries'][0]
        self.assertEqual(q['target']['kind'],'POLICY_OPTIMIZATION')
        self.assertIn('恰好给6家',q['semantics']['policy_assignment']['value'])
        self.assertFalse(r['missing_information_candidates'])
        self.assertIsNone(q['semantics']['comparator']['value']);self.assertIsNone(q['semantics']['standardization_distribution']['value'])

    def test_budget_is_not_historical_randomization(self):
        self.policy();self.raw['facts'].pop('historical_assignment');self.raw['facts'].pop('assignment_family')
        r=self.run_wire();d=r['quality']['draft']['shared_draft']['information_design']
        self.assertEqual(d['assignment_family'],'UNRESOLVED');self.assertIsNone(d['assignment_law']['value'])

    def test_distribution_does_not_require_average_weights(self):
        g=self.raw['goals'][0];g['quantity']='distribution';g['summarize']=None
        r=self.run_wire();self.assertFalse(any(x['path'].endswith('.summarize') for x in r['missing_information_candidates']))

    def test_partial_and_omitted_information_stays_unknown(self):
        g=self.raw['goals'][0];g.pop('when');g['summarize']=None;g.pop('remaining_assignments')
        r=self.run_wire();s=r['quality']['draft']['queries'][0]['semantics']
        for k in ('time_horizon','aggregation','standardization_distribution'):self.assertIsNone(s[k]['value'])
        self.assertTrue(all(x['status']=='VERIFY_SOURCE_BEFORE_ASKING' for x in r['missing_information_candidates']))
        self.assertFalse(r['confirmation_card']['questions'])

    def test_unsupported_goal_is_retained_without_fallback_generation(self):
        self.raw['goals']=[dict(form='other',question=self.fact('研究未归类的问题'),details=self.fact('暂无法归类'))]
        r=self.run_wire();self.assertEqual(r['quality']['draft']['queries'][0]['target']['kind'],'OTHER')
        self.assertIn('TARGET_REQUIRES_REVIEW',[x['code'] for x in r['internal_recheck']]);self.assertFalse(r['core_called'])

    def test_multiple_goals_keep_order_and_primary_is_only_a_copy(self):
        first=deepcopy(self.raw['goals'][0]);self.comparison();self.raw['goals'].insert(0,first)
        r=self.run_wire();d=r['quality']['draft'];self.assertEqual([q['query_id'] for q in d['queries']],['q1','q2'])
        self.assertEqual(d['shared_draft']['target'],d['queries'][0]['target'])

    def test_interpretation_in_any_fact_stays_visible(self):
        self.raw['facts']['connections']['reading']='interpretation'
        r=self.run_wire();self.assertIn({'code':'INTERPRETATION_REQUIRES_REVIEW','path':'facts.connections'},r['internal_recheck'])
        self.assertFalse(r['scientific_approval'])

    def test_conflicting_notes_preserved_for_review(self):
        self.raw['goals'][0]['notes']=[self.fact('两句话的边界冲突','interpretation')]
        r=self.run_wire();self.assertTrue(any(x['code']=='AMBIGUITY_OR_CONFLICT' for x in r['internal_recheck']))
        self.assertEqual(r['business_draft']['goals'][0]['notes'][0]['text'],'两句话的边界冲突')

    def test_all_fact_refs_including_unprojected_notes_and_details_are_bound(self):
        other=BusinessCase(case_id='OTHER',business_question=self.case.business_question)
        for ref in ('fabricated',build_catalog(other)[0]['ref']):
            raw=deepcopy(self.raw);f=self.fact('注释');f['refs']=[ref];raw['goals'][0]['notes']=[f]
            with self.subTest(ref=ref),self.assertRaises(A0QualityValidationError) as e:self.run_wire(raw)
            self.assertEqual(e.exception.code,'A0_REFERENCE_NOT_FOUND')
        self.raw['goals']=[dict(form='other',question=self.fact('其他问题'),details=dict(text='细节',refs=['fake'],reading='explicit'))]
        with self.assertRaises(A0QualityValidationError):self.run_wire()

    def test_false_claim_with_real_ref_never_becomes_semantically_verified(self):
        self.raw['goals'][0]['when']=self.fact('五十年后')
        r=self.run_wire();self.assertFalse(r['semantic_correctness_verified']);self.assertFalse(r['identification_ready'])

    def test_wrong_shape_and_authority_fields_fail_without_retry(self):
        for name,value in [('comparator',self.fact('任意对照')),('assumptions',[]),('core_called',True)]:
            raw=deepcopy(self.raw);raw['goals'][0][name]=value;p=MockProvider(raw)
            with self.subTest(name=name),self.assertRaises(A0QualityValidationError) as e:BusinessFormulator(p).formulate(self.case)
            self.assertEqual(e.exception.code,'BUSINESS_SCHEMA_REJECTED');self.assertEqual(p.calls,1)

    def test_old_empty_sentinels_and_unreferenced_claims_rejected(self):
        for value in ('UNKNOWN','NOT_APPLICABLE',dict(text='某时',refs=[],reading='explicit')):
            raw=deepcopy(self.raw);raw['goals'][0]['when']=value
            with self.subTest(value=value),self.assertRaises(A0QualityValidationError):self.run_wire(raw)

    def test_source_claims_do_not_admit_causal_assumptions_or_population_law(self):
        r=self.run_wire();d=r['quality']['draft']['shared_draft']
        self.assertFalse(d['assumptions']);self.assertEqual(d['information_design']['population_information_level'],'UNRESOLVED')
        for flag in ('core_called','business_approval','scientific_approval','estimation_handoff_allowed'):self.assertFalse(r[flag])

    def test_plain_reply_preserves_original_and_rebinds_references_without_approval(self):
        r=self.run_wire();new=append_business_reply(self.case,r['confirmation_card'],'这里说的是超过一半，刚好一半属于另一组。')
        self.assertEqual(new.business_question,self.case.business_question);self.assertEqual(new.sources[-1].text,'这里说的是超过一半，刚好一半属于另一组。')
        with self.assertRaises(A0QualityValidationError):BusinessFormulator(MockProvider(self.raw)).formulate(new)

    def test_html_escapes_business_text_and_contains_no_action_buttons(self):
        self.raw['goals'][0]['question']=self.fact('<script>alert(1)</script>')
        html=render_confirmation_html(self.case,self.run_wire())
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html);self.assertNotIn('<button',html)

    def test_request_has_field_meanings_and_does_not_change_public_question(self):
        before=self.case.model_dump();system,user,_=make_business_request(self.case)
        self.assertEqual(before,self.case.model_dump());self.assertIn(self.case.business_question,user)
        self.assertIn('不是协变量标准化',user);self.assertNotIn('standardization_distribution',user)

    def test_cli_plain_question_replay_and_plain_followup_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);fixture=tmp/'mock.json';fixture.write_text(json.dumps(self.raw,ensure_ascii=False),encoding='utf8')
            out=tmp/'first'
            self.assertEqual(main(['--question',self.case.business_question,'--case-id',self.case.case_id,'--mock-response',str(fixture),'--output-dir',str(out)]),0)
            second=tmp/'second'
            self.assertEqual(main(['--resume',str(out),'--reply','我想看第八周。','--preview','--output-dir',str(second)]),0)
            saved=json.loads((second/'public_input.json').read_text(encoding='utf8'));self.assertEqual(saved['sources'][-1]['text'],'我想看第八周。')
            self.assertFalse((second/'model_draft.json').exists())


if __name__=='__main__':unittest.main()
