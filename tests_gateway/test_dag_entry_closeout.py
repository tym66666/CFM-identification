"""Declaration truth values and scientific approval are different interfaces."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from examples.dag_entry_closeout_reference import cases,assess
from cfm_id.dag_business import inspect_candidate,ADJUSTMENT_ROUTE
from cfm_id_llm.dag_reading import documents
from cfm_id.source_locations import build_catalog


class DagEntryCloseoutTests(unittest.TestCase):
    def test_frozen_reference_outcomes(self):
        for case in cases():
            with self.subTest(slot=case['slot']):
                result=assess(case,case['reference'])
                self.assertTrue(result['passed'],result)

    def test_proposed_true_is_not_scientific_approval(self):
        case=next(c for c in cases() if c['slot']=='CL04_proposed_pending')
        self.assertIs(case['reference']['scope']['graph_complete']['value'],True)
        self.assertIs(case['reference']['information']['positivity']['value'],True)
        with patch('cfm_id.dag_adjustment.solve',side_effect=AssertionError('pending scientific review reached solver')):
            result=assess(case,case['reference'])
            self.assertEqual(result['inspection']['state'],'REVIEW_REQUIRED')
            self.assertEqual(result['result']['state'],'REVIEW_REQUIRED')
            self.assertFalse(result['result']['backend_called'])
            self.assertTrue(all(v=='PENDING' for v in result['result']['review_records']['science']['decisions'].values()))

    def test_matching_stop_state_does_not_excuse_wrong_declaration(self):
        case=next(c for c in cases() if c['slot']=='CL05_prior_unknown')
        wire=deepcopy(case['reference'])
        ids=[k for k,v in build_catalog(documents(case['bundle'])).items() if v['doc_id']=='model']
        wire['scope']['graph_complete']={'value':False,'source_ids':[ids[1]]}
        result=assess(case,wire)
        self.assertEqual(result['result']['state'],'NEEDS_INPUT')
        self.assertFalse(result['score']['passed']);self.assertFalse(result['passed'])
        self.assertFalse(result['result']['backend_called'])

    def test_scientific_unknown_cannot_be_promoted_by_well_formed_citations(self):
        case=next(c for c in cases() if c['slot']=='CL03_unknown')
        wire=deepcopy(case['reference'])
        cat=build_catalog(documents(case['bundle']))
        for claim,doc in [(wire['scope']['graph_complete'],'model'),(wire['information']['positivity'],'information')]:
            claim['value']=True
            claim['source_ids']=[[k for k,v in cat.items() if v['doc_id']==doc][1]]
        result=assess(case,wire)
        self.assertFalse(result['passed']);self.assertFalse(result['result']['backend_called'])
        self.assertIsNone(result['result']['certificate'])

    def test_negated_joint_positivity_is_not_treated_as_unknown(self):
        case=next(c for c in cases() if c['slot']=='CL02_denied')
        view=inspect_candidate(case['bundle'],case['reference'],route_id=ADJUSTMENT_ROUTE)
        self.assertEqual(view['state'],'UNSUPPORTED')
        self.assertEqual(view['reason_code'],'NONPOSITIVE_LAW_NOT_ADAPTED')
        self.assertFalse(view['backend_called'])

    def test_pending_candidate_cannot_inject_approval_fields(self):
        case=next(c for c in cases() if c['slot']=='CL04_proposed_pending')
        for key in ('science_review','approved','certificate'):
            view=inspect_candidate(case['bundle'],{**case['reference'],key:True},route_id=ADJUSTMENT_ROUTE)
            self.assertEqual(view['state'],'CHECK_BLOCKED');self.assertFalse(view['backend_called'])


if __name__=='__main__':unittest.main()
