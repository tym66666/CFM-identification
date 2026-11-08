import copy, unittest
from dataclasses import replace
from unittest.mock import patch
from examples.materials_candidate_fixture import load_case, synthetic_context
from tests_gateway.test_structured_witness_flat_candidate import FlatMock
from tests_gateway.test_structured_witness_candidate import hours
from evaluation import business_submission as s

class SubmissionTests(unittest.TestCase):
    def setUp(self): self.i=load_case()
    def run_ident(self,**kw):
        i=self.i
        return s.identify_submission(i["bundle"],i["raw"],i["packet"],**kw)
    def test_normalization_never_calls_core_or_constructs_reviews(self):
        item=self.i
        class A0:
            def generate_json(self,**kw): return copy.deepcopy(item["raw"])
        with patch("evaluation.business_materials_base.compile_inquiry",side_effect=AssertionError("NO CORE")):
            out=s.normalize_submission(item["bundle"],A0())
        self.assertEqual(out["state"],"REVIEW_REQUIRED")
        self.assertFalse(out["core_called"])
        self.assertEqual(out["draft"],item["raw"])
    def test_invalid_draft_stops(self):
        out=s.preview_submission(self.i["bundle"],{})
        self.assertEqual(out["state"],"DRAFT_INVALID")
        self.assertFalse(out["core_called"])
    def test_no_context_cannot_promote_packet(self):
        p=FlatMock()
        out=self.run_ident(candidate_provider=p,synthetic_protocol_selected=True,enable_candidates=True)
        self.assertFalse(out["core_called"]); self.assertEqual(p.calls,[])
        self.assertEqual(out["state"],"REVIEW_REQUIRED")
    def test_no_synthetic_selection(self):
        out=self.run_ident(context=synthetic_context(self.i))
        self.assertFalse(out["core_called"])
    def test_valid_review_then_candidate(self):
        p=FlatMock()
        out=self.run_ident(context=synthetic_context(self.i),candidate_provider=p,
            hours_review=hours(self.i),synthetic_protocol_selected=True,enable_candidates=True)
        self.assertEqual(out["state"],"CANDIDATE_CHECKED")
        self.assertEqual(len(p.calls),1)
        self.assertFalse(out["view"]["core"]["certificate_replayed"])
    def test_no_candidate_opt_in_means_no_call(self):
        p=FlatMock()
        out=self.run_ident(context=synthetic_context(self.i),candidate_provider=p,
            synthetic_protocol_selected=True,hours_review=hours(self.i))
        self.assertEqual(out["state"],"CANDIDATE_NOT_REQUESTED");self.assertEqual(p.calls,[])
        self.assertTrue(out["core_called"])
    def test_missing_science_stops_before_core(self):
        c=synthetic_context(self.i);b=c.core_port.bindings["q1"]
        c.core_port.bindings["q1"]=replace(b,admission=b.admission.model_copy(update={"approved_scientific_binding":None}))
        out=self.run_ident(context=c,synthetic_protocol_selected=True)
        self.assertEqual(out["state"],"SCIENCE_REVIEW_REQUIRED");self.assertEqual(c.core_port.calls,[])
    def test_stale_draft_review(self):
        c=synthetic_context(self.i)
        c=replace(c,approval=c.approval.model_copy(update={"model_draft_sha256":"0"*64}))
        p=FlatMock();out=self.run_ident(context=c,candidate_provider=p,synthetic_protocol_selected=True,enable_candidates=True)
        self.assertEqual(out["state"],"REVIEW_REQUIRED");self.assertEqual(p.calls,[])
        self.assertEqual(c.core_port.calls,[])
    def test_no_business_intent_is_blocked(self):
        c=synthetic_context(self.i);b=c.core_port.bindings["q1"]
        c.core_port.bindings["q1"]=replace(b,business_intent=None)
        out=self.run_ident(context=c,synthetic_protocol_selected=True)
        self.assertEqual(out["state"],"REVIEW_REQUIRED");self.assertEqual(c.core_port.calls,[])
    def test_receipt_is_recomputed_not_trusted(self):
        c=synthetic_context(self.i);c.core_port.last_real_results["q1"]={"status":"POINT"}
        out=self.run_ident(context=c,synthetic_protocol_selected=True)
        self.assertEqual(out["review_receipts"]["q1"]["status"],"UNSUPPORTED")
        self.assertFalse(out["view"]["core"]["certificate_replayed"])
    def test_no_retry_on_provider_failure(self):
        class Fail:
            calls=0
            def generate_json(self,**kw):
                self.calls+=1;raise RuntimeError("SIMULATED_FAILURE")
        p=Fail()
        with self.assertRaises(RuntimeError):s.normalize_submission(self.i["bundle"],p)
        self.assertEqual(p.calls,1)
if __name__=="__main__":unittest.main()

