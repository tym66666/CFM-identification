"""New quotation requests agree with the unchanged evidence admission boundary."""
from copy import deepcopy
import json,unittest
from cfm_id.business_entry import prepare_request,preview
from evaluation import business_condition_evidence as gate
from examples import nbib_d1_fixture as d1
from tests_gateway.test_business_question_intent_base import read,split

class EvidenceRequestAlignment(unittest.TestCase):
    def make_d1(self):
        item=deepcopy(d1.load_case());b,r=item['bundle'],item['raw']
        r['intents']={q:dict(kind='比较',quote=t) for q,t in b['question_slots'].items()}
        for q,c in r['questions'].items():
            c.pop('operation');c['peer_evidence']={s:b['question_slots'][q] for s in ('first','second')}
        return b,r,prepare_request(b,'D1_EFFECTS')

    def test_full_question_passes_request_and_existing_gate(self):
        b,r,request=self.make_d1();schema=json.loads(request['user'])['output_schema']
        for qid, goal in b['question_slots'].items():
            constraints=schema['properties']['questions']['properties'][qid]['allOf']
            quote_fields=constraints[-1]['properties']['peer_evidence']['properties']
            for side in ('first','second'):
                self.assertIn(r['questions'][qid]['peer_evidence'][side],quote_fields[side]['enum'])
                self.assertIn(None,quote_fields[side]['enum'])
        self.assertEqual(preview(b,r,'D1_EFFECTS')['state'],'REVIEW_REQUIRED')
        self.assertNotIn('完整原句或完整分句',request['system'])
        self.assertNotIn('science_packet',request['user'])

    def test_new_requests_exclude_location_half_clause_and_wrong_question(self):
        b,r,request=self.make_d1()
        for quote in ('target_clarification.txt:L2','协作同事中过半获得权限',b['question_slots']['q2']):
            wrong=deepcopy(r);wrong['questions']['q1']['peer_evidence']['first']=quote
            out=preview(b,wrong,'D1_EFFECTS')
            self.assertEqual(out['state'],'READING_REVIEW_REQUIRED');self.assertFalse(out['core_called'])

    def test_null_evidence_keeps_known_own_state_and_unknown_peers(self):
        b=read('public/negative_bundle.json');e=read('recorded/study_envelope.json')
        r=split(b,read('recorded/negative_candidate.json'),'水平')
        r['questions']['q1']['first'].update(own='开通',neighbors='不明确',neighbor_count=None)
        r['questions']['q1']['peer_evidence']['first']=None
        out=preview(b,r,'D2_ARM',e)
        self.assertFalse(out['core_called']);self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertEqual(out['reading_candidate'],r)

    def test_full_quote_cannot_neutralize_negation_or_create_threshold(self):
        for goal in ('问题1：不是要求同事过半开通时的效果。','问题1：同事使用是否有帮助？'):
            b={'question_slots':{'q1':goal}};raw={'questions':{'q1':{'first':{'own':'开通','neighbors':'超过一半','neighbor_count':None},
                'second':None,'peer_evidence':{'first':goal,'second':None}}}}
            self.assertFalse(gate.project_evidence(b,raw)[1]['passed'])

    def test_legacy_complete_clause_still_valid_without_output_repair(self):
        goal='同事过半开通时，业绩如何？';raw={'questions':{'q1':{'first':{'own':'开通','neighbors':'超过一半','neighbor_count':None},
            'second':None,'peer_evidence':{'first':'同事过半开通时','second':None}}}}
        before=deepcopy(raw);self.assertTrue(gate.project_evidence({'question_slots':{'q1':goal}},raw)[1]['passed'])
        self.assertEqual(raw,before)

if __name__=='__main__':unittest.main()
