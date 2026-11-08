import copy
import unittest
from evaluation.witness_schedule import inspect_two_worlds as frozen
from evaluation.witness_hours_schedule import inspect_two_worlds as reviewed_inspector
from tests_gateway import test_witness_schedule as baseline

def inspect_two_worlds(math, proposal, artifact):
    # Explicit eight-week fixture review; not inferred from the variable name.
    return reviewed_inspector(math, proposal, artifact, max_downtime_hours="1344")

class NonnegativeDowntimeTests(unittest.TestCase):
    def setUp(self):
        f=baseline.WitnessScheduleTests();f.setUp()
        self.math,self.proposal,self.witness=f.math,f.proposal,f.witness
        target=self.math["target_assignment"];n=len(target)
        self.witness["world_a"]["overrides"]=[dict(assignment=target,outcomes=["5"]*n)]
        self.witness["world_b"]["overrides"]=[dict(assignment=target,outcomes=["3"]*n)]
    def check(self):
        return inspect_two_worlds(self.math,self.proposal,self.witness)
    def test_five_and_three_hours_are_valid_without_rescaling(self):
        before=copy.deepcopy(self.witness)
        r=self.check()
        self.assertEqual(r["status"],"PASSED_EXACT_CONSTRUCTION")
        self.assertEqual((r["theta_a"],r["theta_b"]),("5","3"))
        self.assertEqual(self.witness,before)
        self.assertFalse(r["core_certified"]);self.assertFalse(r["full_candidate_text_verified"])
        self.assertFalse(r["estimation_handoff_allowed"])
    def test_historical_frozen_checker_still_reports_its_narrow_range(self):
        self.assertEqual(frozen(self.math,self.proposal,self.witness)["status"],"INVALID_INPUT")
        self.assertEqual(self.check()["status"],"PASSED_EXACT_CONSTRUCTION")
    def test_negative_hours_remain_rejected(self):
        self.witness["world_a"]["default_outcomes"][0]="-1"
        self.assertEqual(self.check()["status"],"INVALID_INPUT")
    def test_missing_reviewed_time_window_is_rejected(self):
        for bound in (None,"0","-1","NaN",True):
            with self.subTest(bound=bound):
                self.assertEqual(reviewed_inspector(self.math,self.proposal,self.witness,max_downtime_hours=bound)["status"],"UNSUPPORTED_SCOPE")
    def test_hours_cannot_exceed_reviewed_time_window(self):
        self.witness["world_a"]["overrides"][0]["outcomes"][0]="1345"
        self.assertEqual(self.check()["status"],"INVALID_INPUT")
    def test_invalid_rational_and_nonfinite_inputs_remain_rejected(self):
        for value in ("NaN","inf","1/0",3.0,True):
            with self.subTest(value=value):
                w=copy.deepcopy(self.witness);w["world_a"]["default_outcomes"][0]=value
                self.assertEqual(inspect_two_worlds(self.math,self.proposal,w)["status"],"INVALID_ARTIFACT")
    def test_different_observed_hours_are_still_a_failure(self):
        self.witness["world_a"]["default_outcomes"]=["10"]*24
        self.assertEqual(self.check()["status"],"OBSERVABLE_LAWS_DIFFER")
    def test_repair_to_equal_targets_is_not_an_improvement(self):
        self.witness["world_a"]=copy.deepcopy(self.witness["world_b"])
        self.assertEqual(self.check()["status"],"TARGETS_EQUAL")
    def test_missing_artifact_is_not_filled_in(self):
        self.assertEqual(inspect_two_worlds(self.math,self.proposal,None)["status"],"NO_ARTIFACT")
    def test_single_node_weights_are_respected(self):
        self.math["target_unit_weights"]=["0"]*23+["1"]
        self.witness["world_a"]["overrides"][0]["outcomes"]=["7"]*23+["4"]
        r=self.check();self.assertEqual(r["theta_a"],"4");self.assertEqual(r["theta_b"],"3")
    def test_domain_extension_does_not_admit_new_a5(self):
        self.math["a5_admitted_names"].append("no_interference")
        self.assertEqual(self.check()["status"],"UNSUPPORTED_SCOPE")
    def test_domain_extension_does_not_relax_a4_or_outcome_domain(self):
        for key,value in (("outcome","unknown_outcome"),("synthetic_hypothetical_scope",False)):
            math=copy.deepcopy(self.math);math[key]=value
            self.assertEqual(inspect_two_worlds(math,self.proposal,self.witness)["status"],"UNSUPPORTED_SCOPE")
        math=copy.deepcopy(self.math);math["a4_operators"][0]["availability"]="FINITE_SAMPLE"
        self.assertEqual(inspect_two_worlds(math,self.proposal,self.witness)["status"],"UNSUPPORTED_SCOPE")
if __name__=="__main__":unittest.main()

