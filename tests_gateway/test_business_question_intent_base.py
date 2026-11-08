from copy import deepcopy
import json
from pathlib import Path
import unittest
from evaluation import business_question_intent_base as api

K = Path(__file__).resolve().parents[1] / 'examples/legacy/business_extension'
def read(p): return json.loads((K/p).read_text(encoding='utf8'))
def split(bundle, raw, kind):
    raw=deepcopy(raw)
    raw['intents']={q:dict(kind=kind,quote=t) for q,t in bundle['question_slots'].items()}
    for q in raw['questions'].values():q.pop('operation')
    return raw

class IntentContractTests(unittest.TestCase):
    def setUp(self):
        self.bundle=read('public/negative_bundle.json')
        self.raw=split(self.bundle,read('recorded/negative_candidate.json'),'水平')
        self.envelope=read('recorded/study_envelope.json')
    def test_missing_coordinate_does_not_erase_intent(self):
        r=api.identify(self.bundle,self.raw,'D2_ARM',self.envelope)
        self.assertEqual(r['state'],'NEEDS_INPUT')
        self.assertEqual(r['intent_condition_review']['q1']['intent']['kind'],'水平')
        self.assertIn('first.own',r['intent_condition_review']['q1']['missing_conditions'])
        self.assertEqual(r['reading_candidate'],self.raw)
        self.assertFalse(r['core_called'])
    def test_comparison_kept_with_unknown_endpoints(self):
        self.raw['intents']['q1']['kind']='比较'
        q=self.raw['questions']['q1'];q['first']['neighbors']='不明确';q['second']=None
        before=deepcopy(self.raw);projected,receipt=api.project_intents(self.bundle,self.raw)
        self.assertEqual(projected['questions']['q1']['operation'],'差值')
        self.assertEqual(receipt['q1']['coordinate_status'],'INCOMPLETE')
        self.assertIsNone(projected['questions']['q1']['second'])
        self.assertEqual(self.raw,before)
    def test_unknown_intent_is_not_promoted_to_comparison(self):
        self.raw['intents']['q1']['kind']='不明确'
        p,r=api.project_intents(self.bundle,self.raw)
        self.assertEqual(p['questions']['q1']['operation'],'不明确')
        self.assertEqual(r['q1']['coordinate_status'],'NOT_ASSESSED')
    def test_duplicate_operation_rejected(self):
        self.raw['questions']['q1']['operation']='差值'
        self.assertEqual(api.identify(self.bundle,self.raw,'D2_ARM',self.envelope)['state'],'READING_REVIEW_REQUIRED')
    def test_wrong_question_quote_rejected(self):
        self.raw['intents']['q1']['quote']='另一问'
        with self.assertRaises(ValueError):api.project_intents(self.bundle,self.raw)
    def test_missing_intent_question_rejected(self):
        self.raw['intents']={}
        with self.assertRaises(ValueError):api.project_intents(self.bundle,self.raw)
    def test_prompt_has_two_sections_and_no_duplicate_operation(self):
        s,u=api.make_request(self.bundle,'D2_ARM',self.envelope);m=json.loads(u)
        self.assertIn('intents',m['output_schema']['required'])
        self.assertNotIn('operation',m['output_schema']['$defs']['Question']['properties'])
        self.assertNotIn('science_packet',u)
    def test_complete_reading_still_requires_review(self):
        b=read('public/positive_bundle.json');r=split(b,read('recorded/positive_candidate.json'),'水平')
        out=api.identify(b,r,'D2_ARM',self.envelope)
        self.assertEqual(out['state'],'REVIEW_REQUIRED')
        self.assertEqual(out['intent_condition_review']['q1']['coordinate_status'],'COMPLETE_REQUIRES_REVIEW')
        self.assertFalse(out['core_called'])

if __name__=='__main__':unittest.main()
