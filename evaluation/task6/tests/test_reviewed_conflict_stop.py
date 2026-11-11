import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cfm_id.business_intake import BusinessCase
from cfm_id import intake_conflict_review
from evaluation.task6.scripts import reviewed_conflict_stop as stop
from evaluation.task6.scripts.verify_final import verify


class ConflictStopTests(unittest.TestCase):
    def test_reviewer_intervention_requires_real_rejection_and_does_not_certify(self):
        case=BusinessCase.model_validate(json.loads((stop.ROOT/'pilot_cases/materials/conflict.json').read_text(encoding='utf8')))
        review={'authority':'SYNTHETIC_TEST','reviewer':'Review test',
                'decisions':{'queries.q1.semantics.first_arrangement':{'value_state':'REJECTED'}}}
        reference=json.loads((stop.ROOT/'pilot_cases/references/conflict.json').read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            for name,value in [('intake_snapshot',{}),('result',{'internal_binding_is_unmodified_request':True,'response_received':True}),
                               ('known_issue_review',{'review':review}),('model_candidate',{'target':'model output'})]:
                (d/(name+'.json')).write_text(json.dumps(value),encoding='utf8')
            snapshot=SimpleNamespace(case=case,model_dump=lambda **kw:{'case':case.model_dump(mode='json')})
            catalog={'s0001':{'doc_id':'business_question','text':case.business_question},
                     's0025':{'doc_id':'email','text':next(s.text for s in case.sources if s.source_id=='contradictory_business_email')}}
            with patch.object(stop.business_intake,'_checked',return_value=snapshot), \
                 patch.object(intake_conflict_review,'sources',return_value=catalog), \
                 patch.object(stop.business_field_review,'submit',return_value={'state':'CHECK_BLOCKED','reason_code':'DISPATCH_REVIEW_REJECTED'}):
                result=stop.build(d)
                self.assertTrue(verify(result,reference)['execution_evidence_gate_passed'])
                self.assertEqual(result['stage'],'REVIEWER_INTERVENTION_NOT_MODEL_FIRST_PASS')
                self.assertFalse(result['backend_called'])
                self.assertIsNone(result['mathematical_claim'])
            with patch.object(stop.business_intake,'_checked',return_value=snapshot), \
                 patch.object(stop.business_field_review,'submit',return_value={'state':'READY_TO_READ'}):
                with self.assertRaisesRegex(ValueError,'rejection required'):stop.build(d)

    def test_native_stop_rejects_unlocated_or_unreviewed_evidence(self):
        field='queries.q1.semantics.first_arrangement'
        review={'authority':'SYNTHETIC_TEST','decisions':{field:{'value_state':'REJECTED'}}}
        conflict={'query_id':'q1','field':field,'authority':'SYNTHETIC_TEST','reviewer':'Reviewer',
                  'reason':'Two source documents report conflicting policy choices.',
                  'sources':[{'source_id':'s1','quote':'original'}, {'source_id':'s2','quote':'tampered'}]}
        snapshot=SimpleNamespace(model_dump=lambda **kw:{'id':'case'})
        catalog={'s1':{'doc_id':'first','text':'original'},'s2':{'doc_id':'second','text':'other'}}
        with patch.object(intake_conflict_review.business_intake,'_checked',return_value=snapshot), \
             patch.object(intake_conflict_review,'sources',return_value=catalog), \
             patch.object(intake_conflict_review.business_field_review,'submit',return_value={'state':'CHECK_BLOCKED','reason_code':'DISPATCH_REVIEW_REJECTED'}):
            with self.assertRaisesRegex(ValueError,'SOURCES_INVALID'):intake_conflict_review.review_conflict(snapshot,'q1',field_review=review,conflict_review=conflict)
            conflict['sources'][1]['quote']='other'
            review['decisions'][field]['value_state']='ACCEPTED'
            with self.assertRaisesRegex(ValueError,'REJECTION_REQUIRED'):intake_conflict_review.review_conflict(snapshot,'q1',field_review=review,conflict_review=conflict)


if __name__=='__main__':unittest.main()
