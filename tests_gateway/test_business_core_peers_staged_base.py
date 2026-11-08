from copy import deepcopy
import json,unittest
from examples.nbib_core_peers_fixture import load_case
from evaluation import business_core_peers_staged_base as a


class StagedCorePeersTests(unittest.TestCase):
    def setUp(self):
        self.i=load_case();self.b=self.i['bundle'];self.e=a.bind_study(self.b,{'study':self.i['raw']['study']})

    def test_study_request_has_no_current_goals(self):
        _,u=a.study_request(self.b);m=json.loads(u)
        self.assertNotIn('target_clarification.txt',m['documents']);self.assertNotIn('business_question.md',m['documents'])
        self.assertNotIn('question_slots',m);self.assertEqual(m['output_schema']['required'],['study'])

    def test_same_study_across_scope_variants(self):
        b=load_case('scope_unknown')['bundle'];self.assertEqual(a.historical_materials(b),a.historical_materials(self.b))
        self.assertEqual(a.validate_envelope(b,self.e),self.e)

    def test_target_cannot_overwrite_study(self):
        with self.assertRaisesRegex(ValueError,'TARGET_RESPONSE_ONLY'):a.compose_reading(self.b,self.e,self.i['raw'])

    def test_target_schema_has_no_study(self):
        _,u=a.target_request(self.b,self.e);m=json.loads(u)
        self.assertEqual(m['output_schema']['required'],['questions']);self.assertNotIn('study',m['output_schema']['properties'])
        self.assertEqual(m['bound_study_candidate'],self.i['raw']['study'])

    def test_unknown_goal_retains_historical_e3(self):
        i=load_case('scope_unknown');r=a.compose_reading(i['bundle'],self.e,{'questions':i['raw']['questions']})
        result=a.core.preview_submission(i['bundle'],r)
        self.assertEqual(r['study']['exposure'],a.core.E3)
        self.assertEqual([q['state'] for q in result['query_views']],['NEEDS_INPUT','NEEDS_INPUT','UNSUPPORTED'])

    def test_historical_material_change_invalidates_parent(self):
        b=deepcopy(self.b);b['documents']['study_protocol.md']+='\n新协议\n'
        with self.assertRaisesRegex(ValueError,'STALE'):a.validate_envelope(b,self.e)

    def test_target_source_cannot_approve_study_reading(self):
        raw={'study':deepcopy(self.i['raw']['study'])};raw['study']['exposure_source']='target_clarification.txt:L2'
        with self.assertRaisesRegex(ValueError,'HISTORICAL'):a.bind_study(self.b,raw)

    def test_missing_study_conditions_stop_before_targets(self):
        raw={'study':deepcopy(self.i['raw']['study'])};raw['study'].update(declared_independent=None,independence_source=None)
        envelope=a.bind_study(self.b,raw);self.assertEqual(envelope['state'],'NEEDS_INPUT')
        with self.assertRaisesRegex(ValueError,'COMPLETE_STUDY'):a.target_request(self.b,envelope)


if __name__=='__main__':unittest.main()
