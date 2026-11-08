"""Frozen semantics gate precedes synthetic approvals and version comparison."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from cfm_id import research_session as work, research_versions as versions
from cfm_id_bridge.scientific_binding import sha
from examples.research_condition_reading_reference import cases,assess,prepare_session


class ConditionReadingTests(unittest.TestCase):
    def setUp(self):
        self.cases={c['name']:c for c in cases()}

    def test_frozen_positive_versions_use_actual_candidate_and_replay(self):
        for name in ('both','own_only','no_orders'):
            with self.subTest(name=name):
                c=self.cases[name];raw=deepcopy(c['reference']);old=deepcopy(raw)
                result=assess(c,raw)
                self.assertTrue(result['passed'])
                self.assertTrue(result['result']['independent_replay'])
                self.assertEqual(result['result']['mathematical_claim']['interval'],c['expected_interval'])
                self.assertEqual(raw,old)
                self.assertTrue(result['no_review_blocked'])

    def test_undecided_is_not_automatic_nonassumption(self):
        c=self.cases['peer_undecided']
        with patch('examples.research_condition_reading_reference.endpoint_reviews',side_effect=AssertionError('no approval')):
            result=assess(c,c['reference'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['final_state'],'NEEDS_INPUT')
        self.assertFalse(result['result']['backend_called'])
        self.assertTrue(result['clarification']['questions'])
        questions=[r['text'] for r in result['clarification']['questions']]
        self.assertTrue(any('同伴' in q and '尚未决定' in q and 'A、B、C、D' in q for q in questions))
        self.assertFalse(any('观察到' in q for q in questions))

    def test_observed_reading_has_its_own_question_and_never_grants_science(self):
        c=self.cases['peer_undecided'];raw=deepcopy(c['reference'])
        # Exercise the untrusted reading view, not an approval of its source meaning.
        raw['order_reading']['claims'][1].update(declaration='仅报告观察',quantity='历史样本统计',scope='HISTORICAL_SUPPORT')
        s=work.receive_candidate(work.start('MEAN_ORDER_D2_E1',c['bundle']),raw)
        view=work.inspect(s)
        self.assertEqual(view['state'],'NEEDS_INPUT')
        questions=[r['text'] for r in work.clarification_plan(s)['questions']]
        self.assertTrue(any('同伴' in q and '观察到' in q for q in questions))
        self.assertFalse(any('尚不能确认采用意向' in q for q in questions))
        self.assertFalse(view['backend_called'])
        self.assertIsNone(view['mathematical_claim'])

    def test_two_undecided_axes_keep_two_specific_questions(self):
        c=self.cases['both'];raw=deepcopy(c['reference'])
        for claim in raw['order_reading']['claims']:claim['declaration']='尚不明确'
        s=work.receive_candidate(work.start('MEAN_ORDER_D2_E1',c['bundle']),raw)
        questions=[r['text'] for r in work.clarification_plan(s)['questions']]
        adoption=[q for q in questions if '尚不能确认采用意向' in q]
        self.assertEqual(len(adoption),2)
        self.assertTrue(any('本人' in q for q in adoption))
        self.assertTrue(any('同伴' in q for q in adoption))

    def test_old_misleading_plan_is_stale_and_undecided_reply_does_not_approve(self):
        c=self.cases['peer_undecided']
        s=work.receive_candidate(work.start('MEAN_ORDER_D2_E1',c['bundle']),c['reference'])
        current=work.clarification_plan(s);old=deepcopy(current)
        old['questions'][0]['text']='观察到的相关变化不能代替科学假设；请独立确认是否愿意接受这个条件。'
        with self.assertRaisesRegex(ValueError,'STALE_OR_CHANGED_CLARIFICATION_PLAN'):
            work.append_reply(s,old,old['questions'][0]['clarification_id'],'仍未决定。')
        next_session=work.append_reply(s,current,current['questions'][0]['clarification_id'],'仍未决定。')
        self.assertIsNone(next_session.candidate)
        self.assertIsNone(next_session.review)
        self.assertEqual(work.inspect(next_session)['state'],'READING_REQUIRED')

    def test_wrong_adoption_is_retained_and_withholds_approval(self):
        c=self.cases['peer_undecided'];raw=deepcopy(c['reference'])
        raw['order_reading']['claims'][1]['declaration']='提出条件'
        original=deepcopy(raw)
        with patch('examples.research_condition_reading_reference.endpoint_reviews',side_effect=AssertionError('no approval')):
            result=assess(c,raw)
        self.assertFalse(result['semantic_passed'])
        self.assertEqual(result['final_state'],'REVIEW_REQUIRED')
        self.assertFalse(result['result']['backend_called'])
        self.assertIsNone(result['result']['mathematical_claim'])
        self.assertEqual(raw,original)

    def test_valid_schema_wrong_target_and_old_source_ids_cannot_get_review(self):
        c=self.cases['own_only']
        for kind in ('target','source','question_id'):
            with self.subTest(kind=kind):
                raw=deepcopy(c['reference'])
                if kind=='target':raw['comparison']['reading']['questions']['q1']['population']=['A']
                if kind=='source':raw['order_reading']['claims'][0]['source_ids']=self.cases['both']['reference']['order_reading']['claims'][0]['source_ids']
                if kind=='question_id':raw['comparison']['reading']['intents']['q1']['question_id']=self.cases['both']['reference']['comparison']['reading']['intents']['q1']['question_id']
                result=assess(c,raw)
                self.assertFalse(result['semantic_passed'])
                self.assertFalse(result['result']['backend_called'])
                self.assertIsNone(result['result']['mathematical_claim'])

    def test_fork_rereads_changed_material_and_comparison_has_two_native_proofs(self):
        c=self.cases['both'];a,an,_=prepare_session(c,c['reference'])
        c=self.cases['own_only'];b,bn,_=prepare_session(c,c['reference'],parent=a)
        self.assertNotEqual(a.candidate,b.candidate)
        event=next(e for e in b.history if e['action']=='CONDITION_VERSION_CREATED')
        self.assertFalse(event['reading_reused_from_identical_request'])
        self.assertFalse(event['approvals_inherited'])
        plan=versions.plan_comparison(a,b,before_submission=an,after_submission=bn)
        r=versions.compare_versions(a,b,plan=plan,before_submission=an,after_submission=bn,research_protocol_selected=True)
        self.assertEqual(r['state'],'COMPARED')
        self.assertTrue(r['both_results_independently_replayed'])
        self.assertEqual(r['conclusion']['declaration_relation'],'WEAKENING')

    def test_request_uses_public_materials_and_is_unaffected_by_private_reference(self):
        c=self.cases['both'];s=work.start('MEAN_ORDER_D2_E1',c['bundle'])
        request=work.prepare_request(s)
        c['fixture']['provenance']='PRIVATE_REFERENCE_SENTINEL'
        self.assertNotIn('PRIVATE_REFERENCE_SENTINEL',str(work.prepare_request(s)))
        self.assertEqual(request,work.prepare_request(s))
        for c in self.cases.values():
            self.assertEqual(c['bundle']['question_slots'],s.bundle['question_slots'])
        self.assertEqual(len({sha(c['bundle']['documents']['conditions.txt']) for c in self.cases.values()}),4)


if __name__=='__main__':unittest.main()
