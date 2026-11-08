import unittest
from copy import deepcopy
from evaluation.reading_target_audit import compare_target_projections
from cfm_id.business_entry import preview
from tests_gateway import test_material_reading_contract as material_tests


class ReadingTargetAuditTests(unittest.TestCase):
    def test_same_stop_state_can_hide_lost_known_remaining_rule(self):
        fixture=material_tests.MaterialReadingContractTests();fixture.setUp()
        reference=deepcopy(fixture.raw)
        reference['study'].update(declared_independent=None,independence_source=None)
        answer=deepcopy(reference)
        answer['questions']['q1'].update(remaining_source=None,remaining_evidence_span=None)
        expected=preview(fixture.bundle,reference,'D1_EFFECTS');actual=preview(fixture.bundle,answer,'D1_EFFECTS')
        self.assertEqual(expected['state'],actual['state'])
        self.assertEqual(actual['state'],'NEEDS_INPUT')
        audit=compare_target_projections(expected,actual)
        self.assertFalse(audit['passed'])
        self.assertEqual(audit['issues'],[dict(query_index=1,field='remaining',expected='original_randomization',actual=None)])

    def test_missing_projection_does_not_pass_by_empty_equality(self):
        self.assertFalse(compare_target_projections({}, {})['passed'])

    def test_query_loss_rejected(self):
        self.assertFalse(compare_target_projections({'proposed_targets':[{'kind':'arm'},{'kind':'arm'}]}, {'proposed_targets':[{'kind':'arm'}]})['passed'])

    def test_equal_cohort_permutation_is_not_semantic_error(self):
        expected={'proposed_targets':[{'nodes':['a','b'],'remaining':'original_randomization'}]}
        actual={'proposed_targets':[{'nodes':['b','a'],'remaining':'original_randomization'}]}
        self.assertTrue(compare_target_projections(expected,actual)['passed'])

    def test_contrast_direction_change_rejected(self):
        expected={'proposed_targets':[{'situation':[1,1],'reference':[0,1]}]}
        actual={'proposed_targets':[{'situation':[0,1],'reference':[1,1]}]}
        self.assertFalse(compare_target_projections(expected,actual)['passed'])


if __name__=='__main__':unittest.main()
