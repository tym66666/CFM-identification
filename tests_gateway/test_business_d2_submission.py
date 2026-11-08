import unittest,copy
from dataclasses import replace
from unittest.mock import patch
from examples.nbib_d2_fixture import load_case,synthetic_context
from evaluation.business_d2_submission import identify_submission,preview_submission,normalize_submission,project
class D2SubmissionTests(unittest.TestCase):
 def setUp(self):self.i=load_case()
 def run_case(self,**kw):return identify_submission(self.i["bundle"],self.i["raw"],self.i["packet"],**kw)
 def test_real_complete_randomization_certificate(self):
  r=self.run_case(context=synthetic_context(self.i),synthetic_protocol_selected=True)
  self.assertEqual(r["state"],"CORE_POINT");self.assertTrue(r["query_views"][0]["certificate_replayed"])
  self.assertEqual(r["query_views"][0]["probability"],"12/47");self.assertNotEqual(r["query_views"][0]["probability"],"1/4")
  self.assertEqual(r["candidate_model_calls"],0);self.assertFalse(r["estimation_called"])
 def test_preview_never_compiles_or_reviews(self):
  with patch("evaluation.business_d2_submission.compile_inquiry",side_effect=AssertionError):
   r=preview_submission(self.i["bundle"],self.i["raw"])
  self.assertEqual(r["state"],"REVIEW_REQUIRED");self.assertFalse(r["core_called"])
 def test_original_unassigned_station_stays_unknown(self):
  i=load_case("NBIB-002");r=identify_submission(i["bundle"],i["raw"])
  self.assertEqual(r["state"],"NEEDS_INPUT");self.assertIsNone(r["proposed_targets"][0]["nodes"]);self.assertFalse(r["core_called"])
 def test_missing_remaining_stops(self):
  i=load_case("DEV46-missing-remaining");r=identify_submission(i["bundle"],i["raw"])
  self.assertEqual(r["state"],"NEEDS_INPUT");self.assertFalse(r["core_called"])
 def test_no_context_does_not_authorize(self):
  r=self.run_case(synthetic_protocol_selected=True);self.assertFalse(r["core_called"]);self.assertEqual(r["state"],"REVIEW_REQUIRED")
 def test_no_explicit_selection(self):
  r=self.run_case(context=synthetic_context(self.i));self.assertFalse(r["core_called"])
 def test_sampling_uniformity_not_assumed(self):
  self.i["raw"]["study"]["uniform_without_replacement"]=None
  r=self.run_case(synthetic_protocol_selected=True);self.assertEqual(r["state"],"NEEDS_INPUT");self.assertFalse(r["core_called"])
 def test_global_quota_not_assumed(self):
  self.i["raw"]["study"]["global_quota"]=None
  r=self.run_case(synthetic_protocol_selected=True);self.assertEqual(r["state"],"NEEDS_INPUT")
 def test_bool_is_not_quota(self):
  self.i["raw"]["study"]["global_quota"]=True
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_out_of_range_quota_rejected(self):
  self.i["raw"]["study"]["global_quota"]=49
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_different_design_not_misclassified(self):
  self.i["raw"]["study"].update(design="逐个独立抽签",global_quota=None,uniform_without_replacement=None)
  r=self.run_case();self.assertEqual(r["state"],"UNSUPPORTED");self.assertFalse(r["core_called"])
 def test_exact_count_not_collapsed_to_any(self):
  self.i["raw"]["questions"]["q1"]["first"].update(neighbors="至少一个",neighbor_count=None)
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_fake_source_rejected(self):
  self.i["raw"]["study"]["design_sources"]=["study_protocol.md:L999"]
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_unknown_operation_needs_input(self):
  self.i["raw"]["questions"]["q1"].update(operation="不明确",first=None,second=None)
  self.assertEqual(self.run_case()["state"],"NEEDS_INPUT")
 def test_level_must_not_invent_comparator(self):
  q=self.i["raw"]["questions"]["q1"];q["second"]=copy.deepcopy(q["first"])
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_missing_question_rejected(self):
  self.i["raw"]["questions"]={}
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_unknown_node_not_selected(self):
  self.i["raw"]["questions"]["q1"]["population"]["ids"]=["unit_999"]
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_stale_raw_review_denied(self):
  c=synthetic_context(self.i);self.i["raw"]["questions"]["q1"]["first"]["own"]="不开通"
  r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
 def test_missing_independent_science_denied(self):
  c=synthetic_context(self.i);b=c.core_port.bindings["q1"];c.core_port.bindings["q1"]=replace(b,admission=b.admission.model_copy(update={"approved_scientific_binding":None}))
  r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertFalse(r["core_called"])
 def test_missing_business_intent_denied(self):
  c=synthetic_context(self.i);c.core_port.bindings["q1"]=replace(c.core_port.bindings["q1"],business_intent=None)
  r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertEqual(r["state"],"CHECK_BLOCKED");self.assertFalse(r["core_called"])
 def test_cached_receipt_is_not_proof(self):
  c=synthetic_context(self.i);c.core_port.last_real_results["q1"]={"status":"POINT","certificate":"FAKE"}
  r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertEqual(r["state"],"CORE_POINT");self.assertNotIn("FAKE",str(r["review_receipts"]))
 def test_provider_called_once_and_failure_not_retried(self):
  class Provider:
   calls=0
   def generate_json(self,**kw):self.calls+=1;raise RuntimeError("test")
  p=Provider()
  with self.assertRaises(RuntimeError):normalize_submission(self.i["bundle"],p)
  self.assertEqual(p.calls,1)
 def test_negated_remaining_cannot_authorize(self):
  i=load_case("DEV46-missing-remaining");q=i["raw"]["questions"]["q1"]
  q.update(remaining_source="target_clarification.txt:L3",remaining_evidence_span=i["bundle"]["documents"]["target_clarification.txt"].splitlines()[-1])
  r=identify_submission(i["bundle"],i["raw"]);self.assertEqual(r["state"],"NEEDS_INPUT");self.assertFalse(r["core_called"])
 def test_unrelated_remaining_quote_rejected(self):
  self.i["raw"]["questions"]["q1"]["remaining_evidence_span"]="按原抽签"
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
if __name__=="__main__":unittest.main()

