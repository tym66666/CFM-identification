from copy import deepcopy
import unittest
from tests_gateway.test_business_question_intent_base import read,split
from evaluation import business_question_intent as api

class PartialStateTests(unittest.TestCase):
    def test_comparison_cannot_silently_drop_partial_states(self):
        b=read('public/negative_bundle.json');r=split(b,read('recorded/negative_candidate.json'),'比较')
        r['questions']['q1']['first']=r['questions']['q1']['second']=None
        with self.assertRaisesRegex(ValueError,'PARTIAL'):api.project_intents(b,r)
        out=api.identify(b,r,'D2_ARM',read('recorded/study_envelope.json'))
        self.assertFalse(out['core_called']);self.assertEqual(out['state'],'READING_REVIEW_REQUIRED')
    def test_partial_comparison_keeps_known_values_without_filling_others(self):
        b=read('public/negative_bundle.json');r=split(b,read('recorded/negative_candidate.json'),'比较')
        q=r['questions']['q1'];q['first']=dict(own='不开通',neighbors='不明确',neighbor_count=None);q['second']=deepcopy(q['first'])
        before=deepcopy(r);p,receipt=api.project_intents(b,r)
        self.assertEqual(r,before);self.assertEqual(p['questions']['q1']['first'],q['first'])
        self.assertEqual(receipt['q1']['missing_conditions'],['first.neighbors','second.neighbors'])
    def test_unknown_intent_still_allows_inapplicable_states(self):
        b=read('public/negative_bundle.json');r=split(b,read('recorded/negative_candidate.json'),'不明确')
        r['questions']['q1']['first']=r['questions']['q1']['second']=None
        self.assertEqual(api.project_intents(b,r)[1]['q1']['coordinate_status'],'NOT_ASSESSED')

if __name__=='__main__':unittest.main()
