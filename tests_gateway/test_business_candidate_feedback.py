import copy
import json
import unittest
from examples.materials_candidate_fixture import load_case, synthetic_context
from evaluation.business_candidate_base import candidate_math_context
from evaluation import business_candidate_schedule as first
from evaluation import business_candidate_feedback as repair
from tests_gateway.test_witness_schedule import ScheduleMock

class CaptureRepair:
    name="MOCK-REPAIR"
    def __init__(self,mutation=None):
        self.calls=[]
        self.inner=ScheduleMock(mutation)
    def generate_json(self,*,system_prompt,user_prompt):
        self.calls.append((system_prompt,user_prompt))
        return self.inner.generate_json(system_prompt=system_prompt,
            user_prompt=user_prompt.split(repair.FEEDBACK_MARKER,1)[0])

class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.item=load_case()
        self.context=synthetic_context(self.item)
        self.math=candidate_math_context(self.context.core_port.bindings["q1"].inquiry)
        def shift(e):
            e["two_world_schedule"]["world_b"]=dict(default_outcomes=["1"]*24,overrides=[])
        initial=first.evaluate_with_candidates(self.item["bundle"],self.item["raw"],self.item["packet"],
            context=self.context,provider=ScheduleMock(shift),
            enable_candidates=True,synthetic_protocol_selected=True)
        self.prior=initial["candidate_envelopes"]["q1"]
    def run_case(self,provider):
        return repair.evaluate_with_candidates(self.item["bundle"],self.item["raw"],self.item["packet"],
            context=synthetic_context(self.item),provider=provider,prior_envelope=self.prior,
            enable_candidates=True,synthetic_protocol_selected=True)
    def test_feedback_contains_only_actual_mismatches_not_replacement_worlds(self):
        f=repair.feedback_from_output(self.math,self.prior)
        self.assertFalse(f["reference_answer_supplied"])
        self.assertEqual(len(f["mismatches"]),2)
        row=f["mismatches"][0]
        self.assertEqual(row["assignment"],[0]*24)
        self.assertEqual(row["probability"],"1/12")
        self.assertEqual(row["world_a"],["0"]*24)
        self.assertEqual(row["world_b"],["1"]*24)
        self.assertNotIn("correct_world",f)
    def test_repair_runs_once_and_remains_separate_from_core(self):
        p=CaptureRepair()
        r=self.run_case(p)
        self.assertEqual(len(p.calls),1)
        self.assertTrue(r["feedback_assisted"])
        self.assertFalse(r["independent_first_attempt"])
        self.assertEqual(r["core_verified_query_count"],0)
        self.assertEqual(r["identification"]["results"][0]["status"],"UNSUPPORTED")
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"PASSED_EXACT_CONSTRUCTION")
        sent=json.loads(p.calls[0][1].split(repair.FEEDBACK_MARKER,1)[1])
        self.assertEqual(sent["previous_model_output"],self.prior)
    def test_failed_repair_is_not_automatically_retried(self):
        def shift(e):
            e["two_world_schedule"]["world_b"]=dict(default_outcomes=["1"]*24,overrides=[])
        p=CaptureRepair(shift)
        r=self.run_case(p)
        self.assertEqual(len(p.calls),1)
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"OBSERVABLE_LAWS_DIFFER")
    def test_parent_identity_change_blocks_new_api_call(self):
        self.prior["candidate"]["target_sha256"]="0"*64
        p=CaptureRepair()
        r=self.run_case(p)
        self.assertFalse(p.calls)
        self.assertEqual(r["candidate_results"][0]["status"],"PROVIDER_FAILED")
    def test_range_feedback_does_not_falsely_claim_business_hours_are_bounded_by_one(self):
        self.prior["two_world_schedule"]["world_b"]["default_outcomes"]=["20"]*24
        f=repair.feedback_from_output(self.math,self.prior)
        self.assertEqual(f["out_of_inspector_range"],["20"])
        self.assertEqual(f["mismatches"][0]["world_b"],["20"]*24)
        self.assertIn("不是把业务停机小时假定",repair.FEEDBACK_RULES)

if __name__=="__main__":
    unittest.main()

