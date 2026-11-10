import unittest
import tempfile
import json
from pathlib import Path
from evaluation.task6.scripts.verify_final import verify
from evaluation.task6.scripts.n01_fullchain import session
from cfm_id_bridge.scientific_binding import sha


class FinalEvidenceTests(unittest.TestCase):
    def test_experimental_unbound_prompt_cannot_enter_full_chain(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'result.json').write_text(json.dumps({'internal_binding_is_unmodified_request':False}),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'绑定不一致'):session(p)

    def test_review_stop_never_passes_positive_case(self):
        result={'state':'REVIEW_REQUIRED','backend_called':False,'independent_replay':False,
                'certificate':None,'mathematical_claim':None}
        self.assertFalse(verify(result,{'expected_state':'POINT'})['execution_evidence_gate_passed'])

    def test_partial_requires_replay_and_nondegenerate_sharp_interval(self):
        certificate={'status':'PARTIAL','lower':'3/7','upper':'4/7'}
        certificate['certificate_sha256']=sha(certificate)
        result={'state':'PARTIAL','backend_called':True,'independent_replay':True,'certificate':certificate,
                'mathematical_claim':{'kind':'PARTIAL','interval':['3/7','4/7'],'sharp':True}}
        self.assertTrue(verify(result,{'expected_state':'PROVEN_NON_POINT','expected_interval':['3/7','4/7']})['execution_evidence_gate_passed'])
        result['independent_replay']=False
        self.assertFalse(verify(result,{'expected_state':'PROVEN_NON_POINT'})['execution_evidence_gate_passed'])
        result['independent_replay']=True
        result['certificate']['upper']='5/7'
        self.assertFalse(verify(result,{'expected_state':'PROVEN_NON_POINT'})['execution_evidence_gate_passed'])

    def test_unsupported_is_not_nonidentification(self):
        result={'state':'UNSUPPORTED','backend_called':False,'independent_replay':False}
        self.assertFalse(verify(result,{'expected_state':'PROVEN_NON_POINT'})['execution_evidence_gate_passed'])
        self.assertFalse(verify(result,{'expected_state':'MISSING_STOP'})['execution_evidence_gate_passed'])

    def test_true_stop_needs_question_and_no_claim(self):
        result={'state':'NEEDS_INPUT','backend_called':False,'independent_replay':False,
                'certificate':None,'mathematical_claim':None,'clarification_questions':['哪个条件？']}
        self.assertTrue(verify(result,{'expected_state':'MISSING_STOP'})['execution_evidence_gate_passed'])
        result['mathematical_claim']={'kind':'POINT'}
        self.assertFalse(verify(result,{'expected_state':'MISSING_STOP'})['execution_evidence_gate_passed'])


if __name__=='__main__':unittest.main()
