import copy,json,unittest
from examples.materials_candidate_fixture import load_case,synthetic_context
from tests_gateway.test_structured_witness_flat_candidate import FlatMock
from tests_gateway.test_structured_witness_candidate import hours
from evaluation.identification_replay_display import evaluate_for_display,standalone_html

class DisplayTests(unittest.TestCase):
    def setUp(self):self.item=load_case()
    def run_view(self,provider=None,**kwargs):
        i=self.item
        return evaluate_for_display(i["bundle"],i["raw"],i["packet"],
            provider=provider or FlatMock(),context=kwargs.pop("context",synthetic_context(i)),
            hours_review=kwargs.pop("hours_review",hours(i)),**kwargs)
    def test_candidate_is_separate_from_core_certificate(self):
        view,result=self.run_view()
        self.assertEqual(view["state"],"CANDIDATE_CHECKED")
        self.assertEqual(view["core"]["status"],"UNSUPPORTED")
        self.assertFalse(view["core"]["certificate_replayed"])
        self.assertIsNone(view["core"]["formula"])
        self.assertFalse(view["candidate"]["certificate_issued"])
    def test_raw_table_never_repaired(self):
        p=FlatMock();before=copy.deepcopy(self.item)
        v,r=self.run_view(p)
        self.assertEqual(self.item,before)
        self.assertEqual(r["raw_flat_model_outputs"]["q1"],p.outputs[0])
    def test_missing_review_blocks_provider(self):
        p=FlatMock();v,r=self.run_view(p,context=None)
        self.assertEqual(p.calls,[]);self.assertEqual(v["state"],"REVIEW_REQUIRED")
    def test_stale_hours_never_shows_witness(self):
        h=hours(self.item);h["bundle_sha256"]="0"*64;p=FlatMock()
        v,_=self.run_view(p,hours_review=h)
        self.assertEqual(p.calls,[]);self.assertIsNone(v["candidate"]["witness"])
    def test_bad_observed_world_never_shows_effect_numbers(self):
        v,r=self.run_view(FlatMock("observable"))
        self.assertEqual(v["state"],"CANDIDATE_CHECK_FAILED")
        self.assertIsNone(v["candidate"]["witness"]);self.assertIsNone(v["core"]["formula"])
    def test_equal_targets_rejected(self):
        v,_=self.run_view(FlatMock("equal"))
        self.assertEqual(v["state"],"CANDIDATE_CHECK_FAILED")
    def test_stale_binding_rejected(self):
        v,_=self.run_view(FlatMock("stale"))
        self.assertNotEqual(v["state"],"CANDIDATE_CHECKED")
    def test_unknown_reason_not_trusted_display(self):
        class Inject(FlatMock):
            def generate_json(self,**kw):
                r=super().generate_json(**kw);r["unresolved_reason"]="UNTRUSTED_PROOF: falsely claim POINT";return r
        v,_=self.run_view(Inject("unknown"))
        self.assertEqual(v["state"],"CANDIDATE_UNDETERMINED")
        self.assertNotIn("UNTRUSTED_PROOF",json.dumps(v))
    def test_fake_success_flags_cannot_promote_candidate(self):
        class Forged(FlatMock):
            def generate_json(self,**kw):
                r=super().generate_json(**kw)
                r.update(core_certified=True,status="PASSED_EXACT_CONSTRUCTION",certificate_replay=True)
                return r
        v,_=self.run_view(Forged())
        self.assertEqual(v["state"],"CANDIDATE_OUTPUT_INVALID")
        self.assertFalse(v["core"]["certificate_replayed"])
    def test_contract_failure_does_not_claim_network_failure(self):
        class Broken(FlatMock):
            def generate_json(self,**kw):
                r=super().generate_json(**kw);r.pop("node_order");return r
        v,_=self.run_view(Broken())
        self.assertEqual(v["candidate"]["display_error_kind"],"OUTPUT_CONTRACT_FAILURE")
        self.assertNotIn("网络失败",v["label"])
    def test_html_script_closure_is_escaped(self):
        html=standalone_html([{"title":"</script><script>ATTACK()</script>"}],
            '<script type="application/json">__DISPLAY_DATA__</script>')
        self.assertEqual(html.count("</script>"),1)
        self.assertIn("\\u003c/script>",html)
    def test_no_downstream_handoff(self):
        for kind in ("valid","equal","observable","unknown"):
            v,_=self.run_view(FlatMock(kind))
            self.assertFalse(v["production_admission"])
            self.assertFalse(v["estimation_called"]);self.assertFalse(v["policy_called"])
            self.assertFalse(v["estimation_handoff_allowed"])
if __name__=="__main__":unittest.main()

