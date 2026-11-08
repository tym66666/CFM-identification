"""Protocol checks for declaration paraphrases; no LLM or API in these tests."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from examples.dag_declaration_review_reference import cases,assess
from cfm_id_llm.dag_reading import documents
from cfm_id.source_locations import build_catalog

class DeclarationReviewTests(unittest.TestCase):
    def test_paraphrase_reference_semantics_and_states(self):
        for c in cases():
            with self.subTest(slot=c['slot']):
                a=assess(c,c['reference'])
                self.assertTrue(a['passed'],a)
                self.assertFalse(a['inspection']['backend_called'])

    def test_control_contains_exactly_the_same_public_material(self):
        control,current=cases()[:2]
        self.assertEqual(control['bundle'],current['bundle'])
        self.assertEqual(control['reference'],current['reference'])
        self.assertNotEqual(control['prompt_variant'],current['prompt_variant'])

    def test_adopted_hypothesis_without_approval_does_not_invoke_solver(self):
        for c in cases():
            if c['science_decision']!='PENDING':continue
            with self.subTest(slot=c['slot']),patch('cfm_id.dag_adjustment.solve',side_effect=AssertionError('unapproved science reached solver')):
                a=assess(c,c['reference'])
                self.assertTrue(a['passed'])
                self.assertEqual(a['result']['state'],'REVIEW_REQUIRED')
                self.assertFalse(a['result']['backend_called'])
                self.assertIsNone(a['result']['certificate'])

    def test_not_yet_adopted_is_not_promoted_by_plausible_citations(self):
        c=next(c for c in cases() if c['group']=='new_not_adopted')
        w=deepcopy(c['reference']);cat=build_catalog(documents(c['bundle']))
        for claim,doc in [(w['scope']['graph_complete'],'model'),(w['information']['positivity'],'information')]:
            claim['value']=True
            claim['source_ids']=[[k for k,v in cat.items() if v['doc_id']==doc][1]]
        a=assess(c,w)
        self.assertFalse(a['score']['passed'])
        self.assertFalse(a['result']['backend_called'])
        self.assertTrue(a['result']['reference_review_withheld'])
        self.assertIsNone(a['result']['certificate'])

if __name__=='__main__':unittest.main()

