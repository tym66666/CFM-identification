import copy,json,unittest
from unittest.mock import patch
from examples.nbib_d1_fixture import load_case,synthetic_context
from evaluation.business_d1_submission import load_bundle,identify_submission
from evaluation.business_d1_study_first import review_study,study_request,target_request,compose_reading,normalize_in_stages
class Provider:
 def __init__(self,value):self.value=value;self.calls=0
 def generate_json(self,**kw):self.calls+=1;return self.value
class StagedD1Tests(unittest.TestCase):
 def setUp(self):self.i=load_case();self.s=dict(study=copy.deepcopy(self.i['raw']['study']));self.t=dict(questions=copy.deepcopy(self.i['raw']['questions']))
 def test_unknown_exposure_one_call_no_fabricated_target(self):
  b=load_bundle('NBIB-001');self.s['study'].update(exposure=None,exposure_source=None);p=Provider(self.s);q=Provider(self.t)
  r=normalize_in_stages(b,p,q);self.assertEqual((p.calls,q.calls),(1,0));self.assertEqual(r['state'],'NEEDS_INPUT')
  self.assertIsNone(r['draft']);self.assertFalse(r['target_normalization_performed']);self.assertEqual(r['unparsed_questions'],b['question_slots'])
 def test_missing_independence_never_calls_target(self):
  i=load_case('DEV47-missing-independence');p=Provider(dict(study=i['raw']['study']));q=Provider(self.t)
  r=normalize_in_stages(i['bundle'],p,q);self.assertEqual(q.calls,0);self.assertEqual(r['missing_fields'],['declared_independent']);self.assertFalse(r['core_called'])
 def test_missing_table_never_defaults_half(self):
  i=load_case('DEV47-missing-probabilities');r=review_study(i['bundle'],dict(study=i['raw']['study']))
  self.assertIsNone(r['study']['probabilities']);self.assertEqual(r['missing_fields'],['probability_source'])
 def test_explicit_dependent_design_is_unsupported(self):
  self.s['study']['declared_independent']=False;r=review_study(self.i['bundle'],self.s)
  self.assertEqual(r['state'],'UNSUPPORTED');self.assertEqual(r['clarification_questions'],[])
 def test_invalid_study_source_rejected(self):
  self.s['study']['independence_source']='not-a-source';self.assertEqual(review_study(self.i['bundle'],self.s)['state'],'DRAFT_INVALID')
 def test_stage_one_does_not_accept_premature_questions(self):
  self.s.update(self.t);self.assertEqual(review_study(self.i['bundle'],self.s)['state'],'DRAFT_INVALID')
 def test_target_cannot_override_study(self):
  self.t.update(self.s);r=compose_reading(self.i['bundle'],self.s,self.t);self.assertEqual(r['state'],'DRAFT_INVALID')
 def test_clear_two_stage_is_unapproved_until_review(self):
  p,q=Provider(self.s),Provider(self.t)
  with patch('evaluation.business_d1_submission.identify_submission',side_effect=AssertionError('No Core path in reading')):
   r=normalize_in_stages(self.i['bundle'],p,q)
  self.assertEqual((p.calls,q.calls),(1,1));self.assertEqual(r['draft'],self.i['raw']);self.assertEqual(r['state'],'REVIEW_REQUIRED');self.assertFalse(r['core_called'])
 def test_composed_clear_reading_actual_review_and_certificates(self):
  r=compose_reading(self.i['bundle'],self.s,self.t);i=dict(self.i,raw=r['draft'])
  out=identify_submission(i['bundle'],i['raw'],i['packet'],context=synthetic_context(i),synthetic_protocol_selected=True)
  self.assertEqual(out['state'],'CORE_POINT');self.assertEqual(len(out['query_views']),2);self.assertTrue(all(q['certificate_replayed'] for q in out['query_views']))
 def test_unknown_population_cannot_carry_equal_weights(self):
  self.t['questions']['q1']['population']=dict(selection='不明确',ids=[])
  self.assertEqual(compose_reading(self.i['bundle'],self.s,self.t)['state'],'DRAFT_INVALID')
 def test_target_request_blocked_when_design_incomplete(self):
  self.s['study'].update(exposure=None,exposure_source=None)
  with self.assertRaises(ValueError):target_request(self.i['bundle'],self.s)
 def test_missing_remaining_not_repaired_in_stage_two(self):
  i=load_case('DEV47-missing-remaining');r=compose_reading(i['bundle'],dict(study=i['raw']['study']),dict(questions=i['raw']['questions']))
  self.assertEqual(r['state'],'NEEDS_INPUT');self.assertFalse(r['core_called']);self.assertEqual(r['draft'],i['raw'])
 def test_request_public_evidence_unchanged_between_stages(self):
  _,a=study_request(self.i['bundle']);_,b=target_request(self.i['bundle'],self.s);a,b=json.loads(a),json.loads(b)
  for k in ('documents','source_catalog','question_slots','data_catalog','validated_assignment_probabilities'):self.assertEqual(a[k],b[k])
 def test_no_target_call_without_explicit_provider(self):
  p=Provider(self.s);r=normalize_in_stages(self.i['bundle'],p);self.assertEqual(r['state'],'TARGET_INPUT_REQUIRED');self.assertEqual(p.calls,1)
if __name__=='__main__':unittest.main()
