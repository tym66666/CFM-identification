import copy,json,unittest
from examples.materials_candidate_fixture import load_case,synthetic_context
from tests_gateway.test_structured_witness_candidate import StructuredMock,hours
from evaluation import structured_witness_flat_candidate as flat

class FlatMock(StructuredMock):
    def generate_json(self,*,system_prompt,user_prompt):
        nested=super().generate_json(system_prompt=system_prompt,user_prompt=user_prompt)
        result=flat.nested_to_flat(nested)
        self.outputs[-1]=copy.deepcopy(result)
        return result

class FlatProtocolTests(unittest.TestCase):
    def setUp(self):
        self.item=load_case();self.c=synthetic_context(self.item)
    def run_case(self,p,**kw):
        i=self.item
        return flat.evaluate_with_candidates(i["bundle"],i["raw"],i["packet"],provider=p,context=self.c,
            hours_review=hours(i),synthetic_protocol_selected=True,enable_candidates=True,**kw)
    def sample(self):
        p=FlatMock();self.run_case(p);return p.outputs[0]
    def test_lossless_mapping_of_every_numeric_value(self):
        d=self.sample();nested=flat.flat_to_nested(d)
        self.assertEqual(flat.nested_to_flat(nested),d)
        self.assertEqual(nested["two_world_schedule"]["world_b"]["overrides"],d["world_b_overrides"])
    def test_valid_flat_model_table_is_checked_by_same_core_gates(self):
        p=FlatMock();r=self.run_case(p)
        self.assertEqual(r["raw_flat_model_outputs"]["q1"],p.outputs[0])
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"PASSED_EXACT_CONSTRUCTION")
        self.assertEqual(r["identification"]["results"][0]["status"],"UNSUPPORTED")
        self.assertFalse(r["estimation_handoff_allowed"]);self.assertFalse(r["numeric_values_repaired"])
    def test_prompt_no_long_nested_output_contract(self):
        p=FlatMock();self.run_case(p);data=json.loads(p.calls[0][1])
        self.assertIn("world_a_default_outcomes",data["output_schema"]["properties"])
        self.assertNotIn("two_world_schedule",data["output_schema"]["properties"])
        self.assertNotIn("candidate_expression",p.calls[0][1])
    def test_unknown_all_null_roundtrips(self):
        p=FlatMock("unknown");r=self.run_case(p)
        self.assertEqual(flat.flat_to_nested(p.outputs[0])["two_world_schedule"],None)
        self.assertEqual(r["schedule_diagnostics"]["q1"]["status"],"MODEL_UNDETERMINED")
    def test_duplicate_override_rejected_without_edit(self):
        d=self.sample();d["world_b_overrides"]*=2
        with self.assertRaises(ValueError):flat.flat_to_nested(d)
    def test_extra_field_or_missing_close_level_not_silently_fixed(self):
        d=self.sample();d["proof_text"]="unverified proof"
        with self.assertRaises(ValueError):flat.flat_to_nested(d)
        d=self.sample();d.pop("unresolved_reason")
        with self.assertRaises(ValueError):flat.flat_to_nested(d)
    def test_representation_limit_is_explicit(self):
        d=self.sample();d["world_b_overrides"]*=17
        with self.assertRaises(ValueError):flat.flat_to_nested(d)
    def test_valid_prior_prevents_call_in_flat_pipeline(self):
        p=FlatMock();r=self.run_case(p);prior=r["structured_attempt_records"]["q1"]["attempts"]
        p2=FlatMock("equal");r=self.run_case(p2,prior_attempts={"q1":prior},allow_feedback=True)
        self.assertEqual(p2.calls,[]);self.assertEqual(r["candidate_model_calls"],0)
    def test_one_feedback_uses_same_flat_output_format(self):
        bad=FlatMock("equal");r=self.run_case(bad);prior=r["structured_attempt_records"]["q1"]["attempts"]
        p=FlatMock();r=self.run_case(p,prior_attempts={"q1":prior},allow_feedback=True)
        data=json.loads(p.calls[0][1]);old=data["one_explicit_feedback_revision"]["previous_output"]
        self.assertEqual(old["schema_version"],flat.VERSION)
        self.assertNotIn("two_world_schedule",old)
        self.assertEqual(len(p.calls),1);self.assertEqual(r["structured_attempt_records"]["q1"]["selected_attempt_index"],1)
if __name__=="__main__":unittest.main()

