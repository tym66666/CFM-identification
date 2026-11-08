import copy,unittest
from dataclasses import replace
from unittest.mock import patch
from examples.nbib_effects_fixture import load_case,synthetic_context
from evaluation.business_comparison_submission import identify_comparison_submission
class ComparisonSubmissionTests(unittest.TestCase):
    def setUp(self):self.i=load_case()
    def run_case(self,**kw):
        i=self.i
        return identify_comparison_submission(i["bundle"],i["raw"],i["packet"],**kw)
    def test_two_effects_certified_separately(self):
        r=self.run_case(context=synthetic_context(self.i),synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"CORE_POINT");self.assertNotIn("view",r)
        self.assertEqual([q["query_id"] for q in r["query_views"]],["q1","q2"])
        self.assertTrue(all(q["certificate_replayed"] for q in r["query_views"]))
        self.assertEqual([q["first"] for q in r["query_views"]],[[1,1],[0,1]])
        self.assertEqual([q["second"] for q in r["query_views"]],[[0,1],[0,0]])
        self.assertEqual(r["candidate_model_calls"],0);self.assertFalse(r["estimation_called"])
    def test_packet_without_context_cannot_authorize(self):
        with patch("evaluation.business_comparison_submission.compile_inquiry",side_effect=AssertionError("No compilation")):
            r=self.run_case(synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"]);self.assertEqual(r["state"],"REVIEW_REQUIRED")
    def test_no_explicit_selection_denied(self):
        r=self.run_case(context=synthetic_context(self.i));self.assertFalse(r["core_called"])
    def test_missing_second_science_denied_before_lookup(self):
        c=synthetic_context(self.i);b=c.core_port.bindings["q2"]
        c.core_port.bindings["q2"]=replace(b,admission=b.admission.model_copy(update={"approved_scientific_binding":None}))
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
    def test_partial_review_not_enough(self):
        c=synthetic_context(self.i);c=replace(c,approval=c.approval.model_copy(update={"reviewed_query_ids":["q1"]}))
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
    def test_swapped_typed_effects_rejected(self):
        c=synthetic_context(self.i);a,b=c.core_port.bindings["q1"],c.core_port.bindings["q2"]
        c.core_port.bindings["q1"],c.core_port.bindings["q2"]=b,a
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
    def test_changed_raw_stales_review(self):
        c=synthetic_context(self.i);self.i["raw"]["questions"]["q2"]["first"]["own"]="开通"
        r=self.run_case(context=c,synthetic_protocol_selected=True);self.assertFalse(r["core_called"])
    def test_missing_question_not_silently_dropped(self):
        self.i["raw"]["questions"].pop("q2")
        r=self.run_case(synthetic_protocol_selected=True);self.assertEqual(r["state"],"DRAFT_INVALID");self.assertFalse(r["core_called"])
    def test_unknown_remaining_no_core(self):
        for q in self.i["raw"]["questions"].values():q.update(remaining_source=None,remaining_evidence_span=None)
        with patch("evaluation.business_comparison_submission.compile_inquiry",side_effect=AssertionError("No compilation")):
            r=self.run_case(synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"NEEDS_INPUT");self.assertFalse(r["core_called"])
    def test_unknown_weights_no_core(self):
        for q in self.i["raw"]["questions"].values():q["aggregation"]="不明确"
        r=self.run_case(synthetic_protocol_selected=True);self.assertEqual(r["state"],"NEEDS_INPUT");self.assertFalse(r["core_called"])
    def test_cached_receipt_ignored(self):
        c=synthetic_context(self.i);c.core_port.last_real_results.update(q1={"status":"POINT","certificate":"FAKE"},q2={"status":"POINT","certificate":"FAKE"})
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"CORE_POINT");self.assertNotIn("FAKE",str(r["review_receipts"]))
    def test_missing_business_intent_cannot_certify(self):
        c=synthetic_context(self.i);b=c.core_port.bindings["q2"];c.core_port.bindings["q2"]=replace(b,business_intent=None)
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"CHECK_BLOCKED");self.assertEqual(r["query_views"],[])
        self.assertIn("q2",r["query_errors"])
if __name__=="__main__":unittest.main()

