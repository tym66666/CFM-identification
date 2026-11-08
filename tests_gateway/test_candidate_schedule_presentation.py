import copy
import unittest
from examples.materials_candidate_fixture import load_case, synthetic_context
from evaluation.business_candidate_base import candidate_math_context
from evaluation.business_candidate_schedule import evaluate_with_candidates
from evaluation.candidate_schedule_presentation import render_zh
from tests_gateway.test_witness_schedule import ScheduleMock

class PresentationTests(unittest.TestCase):
    def setUp(self):
        item=load_case();ctx=synthetic_context(item)
        self.math={"q1":candidate_math_context(ctx.core_port.bindings["q1"].inquiry)}
        self.report=evaluate_with_candidates(item["bundle"],item["raw"],item["packet"],
            context=ctx,provider=ScheduleMock(),enable_candidates=True,synthetic_protocol_selected=True)
    def test_clear_boundary_and_fictional_target_values(self):
        text=render_zh(self.report,math_by_query=self.math)
        self.assertIn("Core 原结果：UNSUPPORTED",text)
        self.assertIn("具体反例附件通过精确核查",text)
        self.assertIn("16 种",text)
        self.assertIn("不是业务效果估计",text)
        self.assertIn("未认证模型全文",text)
    def test_forged_saved_pass_is_not_trusted(self):
        self.report["candidate_envelopes"]["q1"]["two_world_schedule"]["world_b"]=dict(default_outcomes=["1"]*24,overrides=[])
        self.assertEqual(self.report["schedule_diagnostics"]["q1"]["status"],"PASSED_EXACT_CONSTRUCTION")
        text=render_zh(self.report,math_by_query=self.math)
        self.assertIn("反例未通过：可观测结果不同",text)
        self.assertNotIn("具体反例附件通过精确核查",text)
    def test_bad_raw_prose_is_not_silently_used_as_validated_summary(self):
        self.report["candidate_envelopes"]["q1"]["candidate"]["proposal"]["reasoning_steps"]=["WRONG_RAW_CLAIM"]
        text=render_zh(self.report,math_by_query=self.math,review_notes={"q1":["原文仍需检查。"]})
        self.assertNotIn("WRONG_RAW_CLAIM",text)
        self.assertIn("原文仍需检查",text)

if __name__=="__main__":unittest.main()

