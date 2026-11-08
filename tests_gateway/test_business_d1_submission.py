import unittest,copy
from dataclasses import replace
from unittest.mock import patch
from fractions import Fraction
from examples.nbib_d1_fixture import load_case,synthetic_context
from evaluation.business_d1_submission import probability_table,project,make_request,preview_submission,identify_submission,normalize_submission
from evaluation.business_core_pilot_base import canonical_hash
class D1SubmissionTests(unittest.TestCase):
 def setUp(self):self.i=load_case()
 def run_case(self,**kw):return identify_submission(self.i["bundle"],self.i["raw"],self.i["packet"],**kw)
 def rebind(self):self.i["bundle"]["probability_binding"]["table_sha256"]=canonical_hash(self.i["bundle"]["tables"]["design_probabilities.csv"])
 def test_two_real_certificates(self):
  r=self.run_case(context=synthetic_context(self.i),synthetic_protocol_selected=True)
  self.assertEqual(r["state"],"CORE_POINT");self.assertEqual(len(r["query_views"]),2)
  self.assertTrue(all(q["certificate_replayed"] for q in r["query_views"]))
  self.assertEqual([q["first"] for q in r["query_views"]],[[1,1],[0,1]])
  self.assertEqual([q["second"] for q in r["query_views"]],[[0,1],[0,0]])
  self.assertTrue(all(q["proof"]["results"][0]["term_count"]==160 for q in r["query_views"]))
 def test_true_heterogeneous_probabilities_not_half(self):
  _,d,_=project(self.i["bundle"],self.i["raw"]);self.assertEqual(len(d["probabilities"]),80)
  self.assertGreater(len(set(d["probabilities"].values())),1)
  for row in self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"]:
   self.assertEqual(Fraction(d["probabilities"][row["node_id"]]),Fraction(row["randomization_probability"]))
 def test_no_model_probability_override(self):
  self.i["raw"]["study"]["probabilities"]={"unit_000":"1/2"}
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_preview_does_not_compile(self):
  with patch("evaluation.business_d1_submission.compile_inquiry",side_effect=AssertionError):
   r=preview_submission(self.i["bundle"],self.i["raw"])
  self.assertEqual(r["state"],"REVIEW_REQUIRED");self.assertFalse(r["core_called"])
 def test_no_context_no_core(self):
  self.assertFalse(self.run_case(synthetic_protocol_selected=True)["core_called"])
 def test_no_explicit_selection(self):
  self.assertFalse(self.run_case(context=synthetic_context(self.i))["core_called"])
 def test_missing_independence_not_inferred_from_table(self):
  i=load_case("DEV47-missing-independence");r=identify_submission(i["bundle"],i["raw"])
  self.assertEqual(r["state"],"NEEDS_INPUT");self.assertIsNone(r["study"]["declared_independent"]);self.assertEqual(len(r["study"]["probabilities"]),80)
  self.assertFalse(r["core_called"])
 def test_missing_probabilities_not_invented(self):
  i=load_case("DEV47-missing-probabilities");r=identify_submission(i["bundle"],i["raw"])
  self.assertEqual(r["state"],"NEEDS_INPUT");self.assertIsNone(r["study"]["probabilities"]);self.assertFalse(r["core_called"])
 def test_missing_remaining_stops_both(self):
  i=load_case("DEV47-missing-remaining");r=identify_submission(i["bundle"],i["raw"])
  self.assertEqual(r["state"],"NEEDS_INPUT");self.assertFalse(r["core_called"]);self.assertEqual(set(r["query_blockers"]),{"q1","q2"})
 def test_independence_requires_source(self):
  self.i["raw"]["study"]["independence_source"]=None
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_unknown_independence_cannot_keep_positive_source(self):
  self.i["raw"]["study"]["declared_independent"]=None
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_table_tampering_rejected(self):
  self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"][0]["randomization_probability"]="1/2"
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_missing_table_row_rejected_even_rehashed(self):
  self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"].pop();self.rebind()
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_duplicate_id_rejected_even_rehashed(self):
  rows=self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"];rows[1]["node_id"]=rows[0]["node_id"];self.rebind()
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_unknown_table_node_rejected(self):
  self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"][0]["node_id"]="unit_999";self.rebind()
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_probability_out_of_range_rejected(self):
  self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"][0]["randomization_probability"]="3/2";self.rebind()
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_probability_invalid_denominator_rejected(self):
  self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"][0]["randomization_probability"]="1/0";self.rebind()
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_zero_probability_not_replaced_by_positive(self):
  self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"][0]["randomization_probability"]="0";self.rebind()
  self.assertEqual(probability_table(self.i["bundle"])["unit_000"],"0")
 def test_changed_probability_stales_review(self):
  c=synthetic_context(self.i)
  self.i["bundle"]["tables"]["design_probabilities.csv"]["rows"][0]["randomization_probability"]="1/2";self.rebind()
  r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
 def test_specified_empty_population_rejected(self):
  self.i["raw"]["questions"]["q1"]["population"]["selection"]="指定"
  self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_missing_second_question_rejected(self):
  self.i["raw"]["questions"].pop("q2");self.assertEqual(self.run_case()["state"],"DRAFT_INVALID")
 def test_swapped_reviews_rejected_before_core(self):
  c=synthetic_context(self.i);c.core_port.bindings["q1"],c.core_port.bindings["q2"]=c.core_port.bindings["q2"],c.core_port.bindings["q1"]
  r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
 def test_partial_review_denied(self):
  c=synthetic_context(self.i);c=replace(c,approval=c.approval.model_copy(update={"reviewed_query_ids":["q1"]}))
  self.assertFalse(self.run_case(context=c,synthetic_protocol_selected=True)["core_called"])
 def test_no_scientific_binding_denied(self):
  c=synthetic_context(self.i);b=c.core_port.bindings["q2"];c.core_port.bindings["q2"]=replace(b,admission=b.admission.model_copy(update={"approved_scientific_binding":None}))
  self.assertFalse(self.run_case(context=c,synthetic_protocol_selected=True)["core_called"])
 def test_stale_raw_review_denied(self):
  c=synthetic_context(self.i);self.i["raw"]["questions"]["q2"]["first"]["own"]="开通"
  self.assertFalse(self.run_case(context=c,synthetic_protocol_selected=True)["core_called"])
 def test_cached_status_not_authoritative(self):
  c=synthetic_context(self.i);c.core_port.last_real_results["q1"]={"status":"POINT","proof":"FAKE"}
  r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertEqual(r["state"],"CORE_POINT");self.assertNotIn("FAKE",str(r["review_receipts"]))
 def test_no_hidden_retry(self):
  class P:
   calls=0
   def generate_json(p,**kw):p.calls+=1;raise RuntimeError("test")
  p=P()
  with self.assertRaises(RuntimeError):normalize_submission(self.i["bundle"],p)
  self.assertEqual(p.calls,1)
if __name__=="__main__":unittest.main()

