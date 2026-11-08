import unittest,json
from copy import deepcopy
from examples import nbib_d1_fixture as e1,nbib_d2_fixture as e4
from evaluation import business_staged_d1_d2 as staged,business_condition_repair as repair
from evaluation.business_evidence_entries import make_request


class StagingTests(unittest.TestCase):
    def test_history_independent_of_current_goal(self):
        for entry,fixture in [('D1_EFFECTS',e1),('D2_ARM',e4)]:
            i=fixture.load_case();b=deepcopy(i['bundle']);h=staged.historical_materials(b,entry)
            # Change only the current wording, keeping it a valid question slot.
            from evaluation.business_materials_intake import goal_slots
            b['documents'][b['active_goal_document']]='邻站安排尚未决定，先评价谁的效果？'
            b['question_slots']=goal_slots(b['documents'][b['active_goal_document']])
            self.assertEqual(h,staged.historical_materials(b,entry))

    def test_study_schema_hides_current_questions(self):
        i=e4.load_case();s,u=staged.study_request(i['bundle'],'D2_ARM');m=json.loads(u)
        self.assertEqual(m['output_schema']['required'],['study']);self.assertNotIn('question_slots',m)
        self.assertNotIn(i['bundle']['active_goal_document'],m['documents'])

    def test_target_cannot_overwrite_study(self):
        i=e4.load_case();b=i['bundle'];e=staged.bind_study(b,'D2_ARM',{'study':i['raw']['study']})
        with self.assertRaisesRegex(ValueError,'TARGET_RESPONSE_ONLY'):staged.compose(b,'D2_ARM',e,{'study':{},'questions':{}})
        x=staged.compose(b,'D2_ARM',e,{'questions':i['raw']['questions']});self.assertEqual(x['study'],i['raw']['study'])
        self.assertFalse(e['scientific_approval']);self.assertFalse(e['core_called'])

    def test_historical_change_invalidates_binding(self):
        i=e4.load_case();b=i['bundle'];e=staged.bind_study(b,'D2_ARM',{'study':i['raw']['study']})
        b['documents']['study_protocol.md']+='\n更正：抽签名额待确认。'
        with self.assertRaisesRegex(ValueError,'STALE'):staged.validate_envelope(b,'D2_ARM',e)

    def test_current_target_not_historical_source(self):
        i=e4.load_case();s=deepcopy(i['raw']['study']);s['exposure_source']='target_clarification.txt:L2'
        with self.assertRaisesRegex(ValueError,'HISTORICAL_EXPOSURE_SOURCE_REQUIRED'):staged.bind_study(i['bundle'],'D2_ARM',{'study':s})

    def test_repair_contains_validation_not_gold(self):
        i=e4.load_case();raw=deepcopy(i['raw'])
        system,user=repair.make_request(i['bundle'],make_request(i['bundle'],'D2_ARM'),raw);m=json.loads(user)
        self.assertEqual(m['rejected_reading_candidate'],raw);self.assertTrue(m['public_contract_validation_issues'])
        self.assertNotIn('expected_targets',user);self.assertNotIn('science_packet',user)

    def test_repair_not_called_without_validation_error(self):
        i=e4.load_case();raw=deepcopy(i['raw']);raw['questions']['q1']['peer_evidence']={'first':i['bundle']['question_slots']['q1'],'second':None}
        with self.assertRaisesRegex(ValueError,'NO_EVIDENCE_ERROR'):repair.make_request(i['bundle'],make_request(i['bundle'],'D2_ARM'),raw)


if __name__=='__main__':unittest.main()
