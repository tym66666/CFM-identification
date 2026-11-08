import copy,unittest
from dataclasses import replace
from unittest.mock import patch
from examples.nbib_arm_fixture import load_case,synthetic_context
from evaluation.business_arm_submission import identify_arm_submission

class ArmSubmissionTests(unittest.TestCase):
    def setUp(self):self.i=load_case()
    def run_case(self,**kw):
        i=self.i
        return identify_arm_submission(i["bundle"],i["raw"],i["packet"],**kw)
    def test_supported_arm_replays_actual_certificate(self):
        r=self.run_case(context=synthetic_context(self.i),synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"CORE_POINT")
        self.assertEqual(r["view"]["core"]["route"],"R1A_RANDOMIZED_ARM")
        self.assertEqual(r["view"]["core"]["assignment_probability"],"1/4")
        self.assertEqual(r["view"]["understanding"]["local_situation"],[0,1])
        self.assertEqual(r["view"]["understanding"]["target_nodes"],["unit_037"])
        self.assertEqual(r["view"]["understanding"]["remaining_rule"],"original_randomization")
        self.assertEqual(r["candidate_model_calls"],0)
        self.assertFalse(r["estimation_called"]);self.assertFalse(r["estimation_handoff_allowed"])
    def test_without_context_packet_does_not_authorize_core(self):
        with patch("evaluation.business_arm_submission.compile_inquiry",side_effect=AssertionError("No compile")):
            r=self.run_case(synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"REVIEW_REQUIRED");self.assertFalse(r["core_called"])
    def test_without_synthetic_selection_does_not_authorize(self):
        r=self.run_case(context=synthetic_context(self.i))
        self.assertFalse(r["core_called"])
    def test_missing_science_denied(self):
        c=synthetic_context(self.i);b=c.core_port.bindings["q1"]
        c.core_port.bindings["q1"]=replace(b,admission=b.admission.model_copy(update={"approved_scientific_binding":None}))
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"SCIENCE_REVIEW_REQUIRED");self.assertEqual(c.core_port.calls,[])
    def test_stale_model_draft_binding_denied(self):
        c=synthetic_context(self.i)
        c=replace(c,approval=c.approval.model_copy(update={"model_draft_sha256":"0"*64}))
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"REVIEW_REQUIRED");self.assertEqual(c.core_port.calls,[])
    def test_changed_target_not_accepted_by_old_review(self):
        c=synthetic_context(self.i);self.i["raw"]["questions"]["q1"]["first"]["own"]="开通"
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"])
    def test_changed_typed_query_rejected(self):
        c=synthetic_context(self.i)
        c.core_port.bindings["q1"].inquiry.task.identification_spec["query"]["own_treatment_value"]=1
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
    def test_changed_design_rejected(self):
        c=synthetic_context(self.i)
        spec=c.core_port.bindings["q1"].inquiry.task.identification_spec
        design=spec["randomized_network_arm_theorem_contract"]["design"]
        design["cluster_probabilities"]=("1/3",*design["cluster_probabilities"][1:])
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
    def test_missing_independent_business_intent_denied(self):
        c=synthetic_context(self.i);b=c.core_port.bindings["q1"]
        c.core_port.bindings["q1"]=replace(b,business_intent=None)
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertFalse(r["core_called"]);self.assertEqual(c.core_port.calls,[])
    def test_no_remaining_rule_does_not_default(self):
        q=self.i["raw"]["questions"]["q1"];q.update(remaining_source=None,remaining_evidence_span=None)
        r=self.run_case(synthetic_protocol_selected=True)
        self.assertEqual(r["state"],"NEEDS_INPUT");self.assertFalse(r["core_called"])
    def test_multiple_targets_not_silently_reduced(self):
        self.i["raw"]["questions"]["q2"]=copy.deepcopy(self.i["raw"]["questions"]["q1"])
        r=self.run_case(synthetic_protocol_selected=True)
        self.assertNotEqual(r["state"],"CORE_POINT");self.assertFalse(r["core_called"])
    def test_fake_cached_point_receipt_not_used(self):
        c=synthetic_context(self.i)
        c.core_port.last_real_results["q1"]={"status":"POINT","certificate":"FAKE"}
        r=self.run_case(context=c,synthetic_protocol_selected=True)
        self.assertEqual(r["review_receipts"]["q1"]["verification_level"],"CORE_REPLAY_VERIFIED")
        self.assertNotIn("FAKE",str(r["review_receipts"]))
if __name__=="__main__":unittest.main()

