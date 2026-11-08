from copy import deepcopy
import json
import unittest
from evaluation import business_materials_whole_clause_evidence as current
from evaluation.nbib_acceptance import DATA,material_input,read
from evaluation.business_materials_intake import sources
from evaluation.business_core_pilot_base import canonical_hash

class EvidenceSpanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.refs=read(DATA/'research_only/formal_references.json')

    def fixture(self,cid):
        ref=deepcopy(self.refs[cid]);b=material_input(cid);raw=ref['raw_reading']
        for q in raw['questions'].values():
            q['remaining_evidence_span']=sources(b)[q['remaining_source']] if q['remaining_source'] else None
        return b,raw,ref['science_packet']

    def test_unrelated_uncertainty_does_not_change_known_target(self):
        b,raw,p=self.fixture('H25-service_arm')
        lines=b['documents']['business_question.md'].splitlines()
        text=lines[2].rstrip('。')
        lines[2]=text+'；明年的采购预算还没决定。'
        b['documents']['business_question.md']='\n'.join(lines)+'\n'
        p['bundle_sha256']=canonical_hash(b)
        raw['questions']['q1']['remaining_evidence_span']=text
        result=current.evaluate_draft(b,raw,p,synthetic_protocol_selected=True)
        self.assertEqual(result['results'][0]['status'],'POINT')
        self.assertTrue(result['results'][0]['certificate_replay'])
        self.assertFalse(result['remaining_evidence_vetoes'])

    def test_actual_negative_sentence_is_still_withheld(self):
        b,raw,p=self.fixture('H25-missing_remaining');q=raw['questions']['q1']
        q['remaining_source']='business_question.md:L3'
        q['remaining_evidence_span']=sources(b)[q['remaining_source']]
        result=current.evaluate_draft(b,raw,p,synthetic_protocol_selected=True)
        self.assertEqual(result['results'][0]['status'],'NEEDS_INPUT')
        self.assertFalse(result['results'][0]['core_called'])
        self.assertTrue(result['remaining_evidence_vetoes'])

    def test_substrings_cannot_drop_negation_or_qualification(self):
        b,raw,p=self.fixture('H25-service_arm')
        for span in ('照试验的抽签办法安排','按原来的概率取平均','肯定按试验分配'):
            with self.subTest(span=span):
                raw['questions']['q1']['remaining_evidence_span']=span
                result=current.evaluate_draft(b,raw,p,synthetic_protocol_selected=True)
                self.assertEqual(result['reason_code'],'REMAINING_EVIDENCE_COMPLETE_SOURCE_CLAUSE_REQUIRED')
                self.assertFalse(result['results'])

    def test_source_span_pair_is_required_and_bound(self):
        b,raw,p=self.fixture('H25-service_arm');q=raw['questions']['q1']
        for edit,reason in [('missing','REMAINING_EVIDENCE_SPAN_REQUIRED'),('null','REMAINING_EVIDENCE_COMPLETE_SOURCE_CLAUSE_REQUIRED'),('other','REMAINING_EVIDENCE_COMPLETE_SOURCE_CLAUSE_REQUIRED'),('orphan','SPAN_WITHOUT_REMAINING_SOURCE')]:
            with self.subTest(edit=edit):
                changed=deepcopy(raw);x=changed['questions']['q1']
                if edit=='missing':x.pop('remaining_evidence_span')
                if edit=='null':x['remaining_evidence_span']=None
                if edit=='other':x['remaining_evidence_span']=b['question_slots']['q1']
                if edit=='orphan':x['remaining_source']=None
                self.assertEqual(current.evaluate_draft(b,changed,p)['reason_code'],reason)

    def test_original_references_keep_all_decisions_and_coordinates(self):
        for cid,ref in self.refs.items():
            with self.subTest(case=cid):
                b,raw,p=self.fixture(cid)
                result=current.evaluate_draft(b,raw,p,synthetic_protocol_selected=True)
                for key in ('remaining_evidence_citations','remaining_evidence_vetoes','remaining_evidence_gate'):result.pop(key)
                result['version']=ref['expected_result']['version']
                result['model_draft_sha256']=ref['expected_result']['model_draft_sha256']
                self.assertEqual(json.loads(json.dumps(result)),ref['expected_result'])

    def test_prompt_keeps_public_documents_and_adds_only_source_clauses(self):
        b,_,_=self.fixture('H25-service_arm');_,user=current.make_request(b)
        m=json.loads(user)
        self.assertEqual(m['documents'],b['documents'])
        for ref,choices in m['remaining_evidence_clause_choices'].items():
            for choice in choices:self.assertIn(choice,sources(b)[ref])
        self.assertIn('remaining_evidence_span',m['output_schema']['$defs']['Question']['required'])

if __name__=='__main__':unittest.main()
