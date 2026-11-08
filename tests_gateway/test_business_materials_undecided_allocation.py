from copy import deepcopy
import json
import unittest
from evaluation import business_materials_undecided_allocation as current
from evaluation.nbib_acceptance import DATA,material_input,read

class RemainingEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs=read(DATA/'research_only/formal_references.json')

    def fixture(self,cid):
        r=deepcopy(self.refs[cid])
        return material_input(cid),r['raw_reading'],r['science_packet']

    def test_observed_false_positive_is_withheld_before_core(self):
        b,raw,p=self.fixture('H25-missing_remaining')
        raw['questions']['q1']['remaining_source']='business_question.md:L3'
        original=deepcopy(raw)
        result=current.evaluate_draft(b,raw,p,synthetic_protocol_selected=True)
        self.assertEqual(raw,original)
        self.assertEqual(result['results'][0]['status'],'NEEDS_INPUT')
        self.assertFalse(result['results'][0]['core_called'])
        self.assertFalse(result['results'][0]['certificate_replay'])
        self.assertEqual(len(result['remaining_evidence_vetoes']),1)

    def test_negative_paraphrases_do_not_become_positive_declarations(self):
        for text in ('其他安排尚未确定。','其他人的安排没有说明。','其余安排待定。',
                     '其余对象不沿用原抽签办法。','The remaining allocation is not yet specified.'):
            with self.subTest(text=text):
                b,raw,_=self.fixture('H25-missing_remaining')
                lines=b['documents']['business_question.md'].splitlines()
                lines[2]=text
                b['documents']['business_question.md']='\n'.join(lines)
                raw['questions']['q1']['remaining_source']='business_question.md:L3'
                normalized,actions=current.normalize(b,raw)
                self.assertIsNone(normalized['questions']['q1']['remaining_source'])
                self.assertTrue(actions)

    def test_negative_treatment_state_does_not_veto_allocation(self):
        b,raw,_=self.fixture('H25-service_arm')
        ref=raw['questions']['q1']['remaining_source']
        self.assertIsNotNone(ref)
        name,line=ref.rsplit(':L',1)
        lines=b['documents'][name].splitlines()
        lines[int(line)-1]='没有启用的网点也包含在内；其余照原抽签规则，在符合情形的结果里按原概率平均。'
        b['documents'][name]='\n'.join(lines)
        normalized,actions=current.normalize(b,raw)
        self.assertEqual(normalized,raw)
        self.assertFalse(actions)

    def test_all_frozen_references_preserve_coordinates_and_decisions(self):
        for cid,ref in self.refs.items():
            with self.subTest(case=cid):
                b=material_input(cid)
                normalized,actions=current.normalize(b,ref['raw_reading'])
                self.assertEqual(normalized,ref['raw_reading'])
                self.assertFalse(actions)
                actual=current.evaluate_draft(b,ref['raw_reading'],ref['science_packet'],synthetic_protocol_selected=True)
                actual.pop('remaining_evidence_vetoes')
                actual.pop('remaining_evidence_gate')
                actual['version']=ref['expected_result']['version']
                self.assertEqual(json.loads(json.dumps(actual)),ref['expected_result'])

    def test_no_candidate_fallback_or_production_admission(self):
        for cid in ('H25-missing_remaining','H25-factory_offsupport'):
            b,raw,p=self.fixture(cid)
            result=current.evaluate_draft(b,raw,p,synthetic_protocol_selected=True)
            self.assertFalse(result['production_admission'])
            for field in ('candidate_generator_called','estimation_called','policy_called'):
                self.assertFalse(result[field])

    def test_prompt_preserves_materials_and_calls_out_evidence_polarity(self):
        b,_,_=self.fixture('H25-missing_remaining')
        system,user=current.make_request(b)
        m=json.loads(user)
        self.assertEqual(m['documents'],b['documents'])
        self.assertIn('尚未决定',system)
        self.assertIn('必须null',m['output_schema']['$defs']['Question']['properties']['remaining_source']['description'])

if __name__=='__main__':
    unittest.main()
