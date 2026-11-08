"""Transfer to new graphs, subset/single-object targets, POINT and missing conditions."""
from copy import deepcopy
import unittest
from cfm_id import research_versions as versions
from examples.research_condition_transfer_reference import cases
from examples.research_condition_reading_reference import assess,prepare_session


class ConditionTransferTests(unittest.TestCase):
    def setUp(self):self.cases={c['name']:c for c in cases()}

    def test_six_frozen_references_include_point_partial_and_two_blocking_negatives(self):
        for name,c in self.cases.items():
            with self.subTest(case=name):
                out=assess(c,c['reference'])
                self.assertTrue(out['passed'],out['final_state'])
                self.assertEqual(out['final_state'],c['expected_state'])
                self.assertEqual(out['result']['independent_replay'],c['expected_interval'] is not None)
                self.assertEqual(out['result']['backend_called'],c['expected_interval'] is not None)

    def test_condition_population_is_not_evaluation_population(self):
        for name in ('cold_both','retail_both'):
            with self.subTest(case=name):
                c=self.cases[name];wire=c['reference']
                target=wire['comparison']['reading']['questions']['q1']['population']
                self.assertEqual(len(target),2 if name.startswith('cold') else 1)
                self.assertTrue(all(set(r['nodes'])==set(c['bundle']['node_order']) for r in wire['order_reading']['claims']))
                bad=deepcopy(wire)
                for r in bad['order_reading']['claims']:r['nodes']=target
                out=assess(c,bad)
                self.assertFalse(out['semantic_passed'])
                self.assertFalse(out['result']['backend_called'])

    def test_complete_reference_admission_does_not_depend_on_expected_status_label(self):
        c=self.cases['retail_both']
        s,native,score=prepare_session(c,c['reference'])
        self.assertTrue(score['passed']);self.assertIsNotNone(native);self.assertIsNotNone(s.review)
        wrong_label=deepcopy(c);wrong_label['expected_state']='PARTIAL'
        s2,native2,score2=prepare_session(wrong_label,c['reference'])
        self.assertTrue(score2['passed']);self.assertIsNotNone(native2);self.assertIsNotNone(s2.review)
        self.assertFalse(assess(wrong_label,c['reference'])['passed'])

    def test_two_real_model_ladders_include_redundant_order_removal(self):
        for first,second,equal in [('cold_both','cold_own',False),('retail_both','retail_none',True)]:
            with self.subTest(first=first):
                c=self.cases[first];a,an,_=prepare_session(c,c['reference'])
                c=self.cases[second];b,bn,_=prepare_session(c,c['reference'],parent=a)
                plan=versions.plan_comparison(a,b,before_submission=an,after_submission=bn)
                out=versions.compare_versions(a,b,plan=plan,before_submission=an,after_submission=bn,research_protocol_selected=True)
                self.assertEqual(out['state'],'COMPARED')
                self.assertTrue(out['both_results_independently_replayed'])
                self.assertEqual(out['conclusion']['declaration_relation'],'WEAKENING')
                self.assertEqual(out['conclusion']['intervals_equal'],equal)

    def test_observation_or_unknown_scope_cannot_be_promoted_to_full_science(self):
        for name in ('cold_observed','retail_scope_unknown'):
            with self.subTest(case=name):
                c=self.cases[name];wire=deepcopy(c['reference'])
                wire['order_reading']['claims'][1].update(declaration='提出条件',quantity='平均潜在结果',scope='ALL_BINARY_ASSIGNMENTS')
                before=deepcopy(wire);out=assess(c,wire)
                self.assertFalse(out['semantic_passed'])
                self.assertFalse(out['result']['backend_called'])
                self.assertEqual(wire,before)
                self.assertIsNone(out['result']['mathematical_claim'])

    def test_single_shop_target_cannot_silently_become_all_units(self):
        c=self.cases['retail_both'];raw=deepcopy(c['reference'])
        raw['comparison']['reading']['questions']['q1']['population']=list(c['bundle']['node_order'])
        out=assess(c,raw)
        self.assertFalse(out['semantic_passed'])
        self.assertFalse(out['result']['backend_called'])

    def test_observation_followups_do_not_demand_turning_records_into_assumptions(self):
        c=self.cases['cold_observed'];out=assess(c,c['reference'])
        questions=[r['text'] for r in out['clarification']['questions']]
        self.assertTrue(any('仅报告观察' in q for q in questions))
        later=[q for q in questions if '仅报告观察' not in q]
        self.assertEqual(len(later),2)
        self.assertTrue(all(q.startswith('若另拟提出科学条件') for q in later))
        self.assertEqual(out['final_state'],'NEEDS_INPUT')
        self.assertFalse(out['result']['backend_called'])
        c=self.cases['retail_scope_unknown'];out=assess(c,c['reference'])
        self.assertTrue(any(q['text'].startswith('请明确条件是否') for q in out['clarification']['questions']))
        self.assertFalse(out['result']['backend_called'])


if __name__=='__main__':unittest.main()
