import copy,json,unittest
from examples.nbib_d1_fixture import load_case
from evaluation.business_d1_submission import load_bundle,make_request,preview_submission,normalize_submission
from cfm_id_llm.providers.d1_reading_contract import annotate_d1_reading_contract,D1ReadingContractProviderV0481

class D1ReadingContractTests(unittest.TestCase):
 def setUp(self):self.i=load_case();self.s,self.u=make_request(self.i['bundle'])
 def test_public_evidence_and_probability_vector_unchanged(self):
  _,u=annotate_d1_reading_contract(self.s,self.u);before,after=json.loads(self.u),json.loads(u)
  before.pop('output_schema');after.pop('output_schema');self.assertEqual(before,after)
 def test_clear_case_raw_output_not_repaired_or_approved(self):
  raw=copy.deepcopy(self.i['raw'])
  class P:
   calls=0
   def generate_json(p,**kw):p.calls+=1;return raw
  p=P();r=normalize_submission(self.i['bundle'],D1ReadingContractProviderV0481(p))
  self.assertEqual(r['draft'],raw);self.assertEqual(r['state'],'REVIEW_REQUIRED');self.assertFalse(r['core_called']);self.assertEqual(p.calls,1)
 def test_actual_failure_pattern_stays_invalid_no_output_repair(self):
  raw=copy.deepcopy(self.i['raw']);raw['study'].update(exposure=None,exposure_source=None)
  class P:
   def generate_json(p,**kw):return raw
  out=D1ReadingContractProviderV0481(P()).generate_json(system_prompt=self.s,user_prompt=self.u)
  self.assertIs(out,raw);self.assertEqual(preview_submission(self.i['bundle'],out)['state'],'DRAFT_INVALID')
 def test_missing_independence_still_unknown(self):
  i=load_case('DEV47-missing-independence')
  class P:
   def generate_json(p,**kw):return i['raw']
  r=normalize_submission(i['bundle'],D1ReadingContractProviderV0481(P()))
  self.assertEqual(r['state'],'NEEDS_INPUT');self.assertIsNone(r['draft']['study']['declared_independent']);self.assertFalse(r['core_called'])
 def test_unknown_exposure_preserves_known_own(self):
  b=load_bundle('NBIB-001');raw=copy.deepcopy(self.i['raw']);raw['study'].update(exposure=None,exposure_source=None)
  for q in raw['questions'].values():
   q.update(population=dict(selection='不明确',ids=[]),population_source=None,aggregation='不明确',remaining_source=None,remaining_evidence_span=None)
   for k in ('first','second'):q[k]['neighbors']='不明确'
  class P:
   def generate_json(p,**kw):return raw
  r=normalize_submission(b,D1ReadingContractProviderV0481(P()));self.assertEqual(r['state'],'NEEDS_INPUT')
  self.assertEqual(r['draft']['questions']['q2']['first']['own'],'不开通');self.assertFalse(r['core_called'])
 def test_non_d1_request_passthrough(self):
  u=json.dumps(dict(output_schema={}),ensure_ascii=False);self.assertEqual(annotate_d1_reading_contract('S',u),('S',u))
 def test_transport_failure_no_retry(self):
  class P:
   calls=0
   def generate_json(p,**kw):p.calls+=1;raise RuntimeError('failure')
  p=P()
  with self.assertRaises(RuntimeError):normalize_submission(self.i['bundle'],D1ReadingContractProviderV0481(p))
  self.assertEqual(p.calls,1)
if __name__=='__main__':unittest.main()
