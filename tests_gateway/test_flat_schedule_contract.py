import copy,json,unittest
from pydantic import ValidationError
from examples.materials_candidate_fixture import load_case,synthetic_context
from tests_gateway.test_structured_witness_flat_candidate import FlatMock
from tests_gateway.test_structured_witness_candidate import hours
from evaluation.business_submission import identify_submission
from evaluation.structured_witness_flat_candidate import FlatAttemptV0391
from cfm_id_llm.providers.flat_schedule_contract import ExplicitFlatScheduleProviderV0421,TABLE_FIELDS

class ExplicitContractTests(unittest.TestCase):
    def run_case(self,p):
        i=load_case()
        return identify_submission(i["bundle"],i["raw"],i["packet"],context=synthetic_context(i),
            synthetic_protocol_selected=True,enable_candidates=True,hours_review=hours(i),
            candidate_provider=ExplicitFlatScheduleProviderV0421(p))
    def test_valid_arrays_pass_unchanged(self):
        p=FlatMock();r=self.run_case(p)
        self.assertEqual(r["state"],"CANDIDATE_CHECKED")
        self.assertEqual(r["identification"]["raw_flat_model_outputs"]["q1"],p.outputs[0])
    def test_two_branches_are_explicit(self):
        p=FlatMock();self.run_case(p)
        schema=json.loads(p.calls[0][1])["output_schema"]
        a,b=schema["oneOf"]
        for field in TABLE_FIELDS:
            self.assertEqual(a["properties"][field]["type"],"array")
            self.assertEqual(b["properties"][field]["type"],"null")
        self.assertIn("没有任何覆盖项",p.calls[0][0])
    def test_null_override_still_rejected_never_repaired(self):
        class Null(FlatMock):
            def generate_json(self,**kw):
                x=super().generate_json(**kw);x["world_a_overrides"]=None
                return x
        p=Null();r=self.run_case(p)
        self.assertEqual(r["state"],"CANDIDATE_OUTPUT_INVALID")
        self.assertIsNone(r["identification"]["raw_flat_model_outputs"]["q1"]["world_a_overrides"])
        self.assertEqual(len(p.calls),1)
    def test_undetermined_all_null_still_allowed(self):
        p=FlatMock("unknown");r=self.run_case(p)
        self.assertEqual(r["state"],"CANDIDATE_UNDETERMINED")
    def test_binding_mismatch_not_overwritten(self):
        r=self.run_case(FlatMock("stale"))
        self.assertNotEqual(r["state"],"CANDIDATE_CHECKED")
    def test_numeric_error_not_repaired(self):
        r=self.run_case(FlatMock("observable"))
        self.assertEqual(r["state"],"CANDIDATE_CHECK_FAILED")
if __name__=="__main__":unittest.main()

