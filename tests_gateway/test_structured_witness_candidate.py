import copy,json,unittest
from examples.materials_candidate_fixture import load_case,synthetic_context
from evaluation import structured_witness_candidate as pilot
from evaluation.business_core_pilot_base import canonical_hash
from evaluation.business_materials import evaluate_draft

def hours(item):
    b=item["bundle"]
    return dict(bundle_sha256=canonical_hash(b),science_packet_sha256=canonical_hash(item["packet"]),
        max_hours="1344",evidence_source="data_dictionary.md",
        evidence_quote=b["documents"]["data_dictionary.md"].strip(),
        reviewer="Synthetic independent outcome reviewer",reviewer_confirmed=True,synthetic_fixture=True)

class StructuredMock:
    name="MOCK-STRUCTURED-V039"
    def __init__(self,kind="valid"):
        self.kind=kind;self.calls=[];self.outputs=[]
    def generate_json(self,*,system_prompt,user_prompt):
        self.calls.append((system_prompt,user_prompt))
        p=json.loads(user_prompt);m=p["math"];n=len(m["node_order"])
        w=dict(schema_version="two-world-schedule-v0.37",node_order=m["node_order"],
            world_a=dict(default_outcomes=["0"]*n,overrides=[]),
            world_b=dict(default_outcomes=["0"]*n,overrides=[dict(assignment=m["target_assignment"],outcomes=["5"]*n)]))
        if self.kind=="equal":w["world_b"]=copy.deepcopy(w["world_a"])
        if self.kind=="observable":w["world_b"]=dict(default_outcomes=["1"]*n,overrides=[])
        d=dict(schema_version="structured-witness-v0.39",**p["binding"],
            decision="UNDETERMINED" if self.kind=="unknown" else "PROPOSE_COUNTEREXAMPLE",
            two_world_schedule=None if self.kind=="unknown" else w,
            unresolved_reason="Could not construct an explicit world pair" if self.kind=="unknown" else None)
        if self.kind=="extra":d["proof_text"]="This must be ignored or rejected, never displayed"
        if self.kind=="stale":d["context_sha256"]="0"*64
        self.outputs.append(copy.deepcopy(d));return d

class StructuredPilotTests(unittest.TestCase):
    def setUp(self):
        self.item=load_case();self.context=synthetic_context(self.item);self.hours=hours(self.item)
    def run_case(self,p=None,**kw):
        return pilot.evaluate_with_candidates(self.item["bundle"],self.item["raw"],self.item["packet"],
            context=kw.pop("context",self.context),provider=p,hours_review=kw.pop("hours_review",self.hours),
            enable_candidates=True,synthetic_protocol_selected=True,**kw)
    def test_valid_structure_generates_only_recomputed_display(self):
        p=StructuredMock();r=self.run_case(p)
        self.assertEqual(len(p.calls),1);self.assertEqual(r["candidate_model_calls"],1)
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"PASSED_EXACT_CONSTRUCTION")
        self.assertIn("0 和 5",r["presentation_text"])
        self.assertFalse(r["raw_model_full_proof_evaluated"])
        self.assertEqual(r["identification"]["results"][0]["status"],"UNSUPPORTED")
        self.assertEqual(r["core_verified_query_count"],0);self.assertFalse(r["estimation_handoff_allowed"])
        self.assertIsNone(r["candidate_results"][0]["mathematical_certificate"])
        self.assertEqual(p.outputs[0],r["structured_attempt_records"]["q1"]["attempts"][0])
    def test_model_prompt_has_no_legacy_proof_schema_or_reference_world(self):
        p=StructuredMock();self.run_case(p);data=json.loads(p.calls[0][1])
        self.assertNotIn("candidate_expression",p.calls[0][1])
        self.assertNotIn("nonidentification_witness",p.calls[0][1])
        self.assertNotIn("reference_answer",data)
        self.assertNotIn("default_outcomes",data["math"])
    def test_equal_targets_are_rejected_not_rewritten(self):
        p=StructuredMock("equal");r=self.run_case(p)
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"TARGETS_EQUAL")
        self.assertIsNone(r["structured_attempt_records"]["q1"]["selected_attempt_index"])
        self.assertEqual(r["candidate_results"][0]["status"],"UNDETERMINED_UNVERIFIED")
        self.assertNotIn("两个虚构世界中的值",r["presentation_text"])
    def test_observed_mismatch_is_not_presented_as_nonidentification(self):
        r=self.run_case(StructuredMock("observable"))
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"OBSERVABLE_LAWS_DIFFER")
        self.assertEqual(r["candidate_results"][0]["candidate"]["proposal"]["claimed_identification"],"UNDETERMINED")
    def test_unknown_is_safe_and_raw_reason_not_trusted_prose(self):
        p=StructuredMock("unknown");r=self.run_case(p)
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"MODEL_UNDETERMINED")
        self.assertNotIn("Could not",r["presentation_text"])
    def test_extra_unchecked_text_is_rejected(self):
        r=self.run_case(StructuredMock("extra"))
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"INVALID_CONTRACT")
        self.assertNotIn("This must",r["presentation_text"])
    def test_forged_context_in_new_reply_not_accepted(self):
        r=self.run_case(StructuredMock("stale"))
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"BINDING_MISMATCH")
    def test_valid_prior_skips_provider_and_keeps_original(self):
        p=StructuredMock();first=self.run_case(p)
        prior=first["structured_attempt_records"]["q1"]["attempts"]
        bad=StructuredMock("equal");r=self.run_case(bad,prior_attempts={"q1":prior},allow_feedback=True)
        self.assertEqual(bad.calls,[]);self.assertEqual(r["candidate_model_calls"],0)
        self.assertEqual(r["structured_attempt_records"]["q1"]["attempts"],prior)
        self.assertFalse(r["candidate_generator_called"])
    def test_valid_then_invalid_history_selects_first_without_model(self):
        good=StructuredMock();bad=StructuredMock("equal")
        self.run_case(good);self.run_case(bad)
        p=StructuredMock();r=self.run_case(p,prior_attempts={"q1":[good.outputs[0],bad.outputs[0]]},allow_feedback=True)
        self.assertEqual(p.calls,[]);self.assertEqual(r["structured_attempt_records"]["q1"]["selected_attempt_index"],0)
        self.assertEqual(len(r["structured_attempt_records"]["q1"]["attempts"]),2)
    def test_failed_prior_only_gets_explicit_single_feedback(self):
        p=StructuredMock("equal");self.run_case(p)
        no=StructuredMock();r=self.run_case(no,prior_attempts={"q1":p.outputs})
        self.assertEqual(no.calls,[])
        yes=StructuredMock();r=self.run_case(yes,prior_attempts={"q1":p.outputs},allow_feedback=True)
        self.assertEqual(len(yes.calls),1)
        fb=json.loads(yes.calls[0][1])["one_explicit_feedback_revision"]
        self.assertEqual(fb["computed_targets"],{"theta_a":"0","theta_b":"0"})
        self.assertFalse(fb["reference_answer_supplied"])
        self.assertEqual(r["structured_attempt_records"]["q1"]["selected_attempt_index"],1)
    def test_failed_revision_does_not_trigger_third_attempt(self):
        p=StructuredMock("equal");self.run_case(p)
        r=self.run_case(p,prior_attempts={"q1":p.outputs[:]},allow_feedback=True)
        history=r["structured_attempt_records"]["q1"]["attempts"]
        no=StructuredMock();r=self.run_case(no,prior_attempts={"q1":history},allow_feedback=True)
        self.assertEqual(no.calls,[]);self.assertEqual(len(history),2)
    def test_prior_context_or_target_mismatch_stops_before_call(self):
        p=StructuredMock();self.run_case(p)
        for field in ("query_id","target_sha256","semantics_sha256","science_scope_sha256","context_sha256"):
            with self.subTest(field=field):
                prior=copy.deepcopy(p.outputs);prior[0][field]="x" if field=="query_id" else "0"*64
                no=StructuredMock();r=self.run_case(no,prior_attempts={"q1":prior},allow_feedback=True)
                self.assertEqual(no.calls,[]);self.assertTrue(r["structured_errors"])
    def test_bound_change_makes_prior_stale(self):
        p=StructuredMock();self.run_case(p)
        new=copy.deepcopy(self.hours);new["max_hours"]="24"
        no=StructuredMock();r=self.run_case(no,prior_attempts={"q1":p.outputs},hours_review=new,allow_feedback=True)
        self.assertEqual(no.calls,[]);self.assertTrue(r["structured_errors"])
    def test_review_missing_or_stale_or_unconfirmed_stops_calls(self):
        bad=copy.deepcopy(self.hours);bad["reviewer_confirmed"]=False
        stale=copy.deepcopy(self.hours);stale["bundle_sha256"]="0"*64
        quote=copy.deepcopy(self.hours);quote["evidence_quote"]="This is not in the business documents"
        for review in (None,bad,stale,quote):
            p=StructuredMock();r=self.run_case(p,hours_review=review)
            self.assertEqual(p.calls,[]);self.assertEqual(r["candidate_model_calls"],0)
    def test_real_core_and_review_gates_preserved(self):
        for cid in ("G32-03","G32-05","G32-07"):
            item=load_case(cid);p=StructuredMock()
            r=pilot.evaluate_with_candidates(item["bundle"],item["raw"],item["packet"],
                context=None,provider=p,enable_candidates=True,synthetic_protocol_selected=True)
            self.assertEqual(p.calls,[])
        p=StructuredMock();r=self.run_case(p,context=None)
        self.assertEqual(p.calls,[]);self.assertEqual(r["candidate_gate"],"REVIEWED_MATERIALS_CONTEXT_REQUIRED")
    def test_unsupported_scientific_scope_never_calls(self):
        # An invalid hour domain is not repaired by the model.
        h=copy.deepcopy(self.hours);h["max_hours"]="0";p=StructuredMock()
        self.run_case(p,hours_review=h);self.assertEqual(p.calls,[])
    def test_identification_result_is_byte_equivalent_to_existing_pipeline(self):
        expected=evaluate_draft(self.item["bundle"],self.item["raw"],self.item["packet"],synthetic_protocol_selected=True)
        self.assertEqual(self.run_case(StructuredMock())["identification"],expected)
    def test_none_provider_does_not_generate_a_witness(self):
        r=self.run_case()
        self.assertEqual(r["candidate_model_calls"],0)
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"NO_ATTEMPT")

if __name__=="__main__":unittest.main()

