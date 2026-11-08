from pathlib import Path
import copy,json,unittest
from examples.nbib_d1_fixture import synthetic_context
from evaluation.business_d1_submission import identify_submission
from evaluation import business_d1_study_first as old
from evaluation import business_d1_aggregation as new
class TargetBoundaryTests(unittest.TestCase):
 def setUp(self):self.cases=json.loads((Path(__file__).resolve().parents[1]/'assets/d1_condition_fixtures/materials_cases.json').read_text(encoding='utf8'))
 def read(self,name):
  i=self.cases[name];return new.compose_reading(i['bundle'],dict(study=i['raw']['study']),dict(questions=i['raw']['questions']))
 def test_explicit_weights_preserved_when_population_unknown(self):
  r=self.read('DEV49-missing-population');self.assertEqual(r['state'],'NEEDS_INPUT');self.assertFalse(r['core_called'])
  self.assertTrue(all(q['aggregation']=='等权平均' and q['population']['selection']=='不明确' for q in r['draft']['questions'].values()))
  self.assertEqual({q['field'] for q in r['clarification_questions']},{'population'})
 def test_unknown_weights_not_filled_from_all_population(self):
  r=self.read('DEV49-missing-weights');self.assertEqual(r['state'],'NEEDS_INPUT');self.assertFalse(r['core_called'])
  self.assertTrue(all(q['aggregation']=='不明确' and q['population']['selection']=='全体' for q in r['draft']['questions'].values()))
  self.assertEqual({q['field'] for q in r['clarification_questions']},{'aggregation'})
 def test_remaining_unknown_does_not_erase_known_targets(self):
  r=self.read('DEV49-missing-remaining');self.assertEqual(r['state'],'NEEDS_INPUT');self.assertFalse(r['core_called'])
  self.assertTrue(all(q['aggregation']=='等权平均' and q['remaining_source'] is None for q in r['draft']['questions'].values()))
  self.assertEqual({q['field'] for q in r['clarification_questions']},{'remaining'})
 def test_clarifications_cover_both_questions(self):
  for name in ('DEV49-missing-population','DEV49-missing-weights','DEV49-missing-remaining'):
   self.assertEqual({q['query_id'] for q in self.read(name)['clarification_questions']},{'q1','q2'})
 def test_valid_partial_reading_is_not_rewritten(self):
  i=self.cases['DEV49-missing-population'];before=copy.deepcopy(i['raw']);r=self.read(i['case_id']);self.assertEqual(r['draft'],before);self.assertEqual(i['raw'],before)
 def test_study_and_target_both_unknown_stays_in_first_stage(self):
  i=self.cases['DEV49-missing-population'];s=dict(study=copy.deepcopy(i['raw']['study']));s['study'].update(exposure=None,exposure_source=None)
  r=new.compose_reading(i['bundle'],s,dict(questions=i['raw']['questions']));self.assertEqual(r['state'],'NEEDS_INPUT');self.assertFalse(r['target_normalization_performed']);self.assertIsNone(r['draft'])
 def test_request_preserves_public_documents_and_study_candidate(self):
  i=self.cases['DEV49-missing-population'];s=dict(study=i['raw']['study']);_,a=old.target_request(i['bundle'],s);_,b=new.target_request(i['bundle'],s)
  a,b=json.loads(a),json.loads(b);a.pop('output_schema');b.pop('output_schema');self.assertEqual(a,b)
 def test_old_failure_reproduced_and_new_partial_is_not_admitted(self):
  i=self.cases['DEV49-missing-population'];r=old.compose_reading(i['bundle'],dict(study=i['raw']['study']),dict(questions=i['raw']['questions']))
  self.assertEqual(r['state'],'DRAFT_INVALID');r=self.read(i['case_id']);self.assertEqual(r['state'],'NEEDS_INPUT');self.assertFalse(r['production_admission']);self.assertFalse(r['estimation_handoff_allowed'])
 def test_invalid_source_is_not_repaired(self):
  i=self.cases['DEV49-missing-population'];i['raw']['questions']['q1']['population_source']='missing:L1'
  self.assertEqual(self.read(i['case_id'])['state'],'DRAFT_INVALID')
 def test_clear_case_still_requires_review(self):
  r=self.read('NBIB-001-two-effects-v047');self.assertEqual(r['state'],'REVIEW_REQUIRED');self.assertFalse(r['core_called']);self.assertEqual(r['clarification_questions'],[])
 def test_clear_actual_review_and_two_certificates(self):
  i=self.cases['NBIB-001-two-effects-v047'];r=self.read(i['case_id']);i=dict(i,raw=r['draft'])
  result=identify_submission(i['bundle'],i['raw'],i['packet'],context=synthetic_context(i),synthetic_protocol_selected=True)
  self.assertEqual(result['state'],'CORE_POINT');self.assertEqual(len(result['query_views']),2);self.assertTrue(all(q['certificate_replayed'] for q in result['query_views']))
if __name__=='__main__':unittest.main()
