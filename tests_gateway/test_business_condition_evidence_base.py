import unittest
from copy import deepcopy
from unittest.mock import Mock
from evaluation import business_condition_evidence_base as gate
from evaluation import business_evidence_entries as entries
from examples import nbib_d1_fixture, nbib_d2_fixture, nbib_arm_fixture, nbib_core_peers_fixture


def candidate(text, condition='超过一半', count=None, quote=None):
    bundle={'question_slots':{'q1':text}}
    raw={'questions':{'q1':{'first':{'own':'不开通','neighbors':condition,'neighbor_count':count},
        'second':None,'peer_evidence':{'first':text if quote is None else quote,'second':None}}}}
    return bundle,raw


class EvidenceTests(unittest.TestCase):
    def test_four_business_reference_readings_preserved(self):
        for fixture in (nbib_d1_fixture,nbib_d2_fixture,nbib_arm_fixture,nbib_core_peers_fixture):
            with self.subTest(fixture=fixture.__name__):
                i=fixture.load_case(); raw=deepcopy(i['raw'])
                for qid,q in raw['questions'].items():
                    q['peer_evidence']={side:i['bundle']['question_slots'][qid] if q.get(side) else None for side in ('first','second')}
                before=deepcopy(raw);p,r=gate.project_evidence(i['bundle'],raw)
                self.assertTrue(r['passed'],r);self.assertEqual(p,i['raw']);self.assertEqual(raw,before)

    def test_history_threshold_cannot_fill_vague_current_target(self):
        b,r=candidate('没有助手的人是否会因核心合作者使用助手而受益')
        b['documents']={'study_protocol.md':'系统按核心伙伴过半分组'}
        self.assertFalse(gate.project_evidence(b,r)[1]['passed'])

    def test_other_question_cannot_supply_threshold(self):
        b,r=candidate('同事用助手是否对我有帮助？',quote='同事过半开通时，效果如何？')
        self.assertFalse(gate.project_evidence(b,r)[1]['passed'])

    def test_negation_and_uncertainty_cannot_be_removed(self):
        for t in ('不是要求同事过半开通时的效果','还没决定是否要比较同事过半开通的效果','并非同事过半开通，效果如何？'):
            with self.subTest(text=t):
                b,r=candidate(t);self.assertFalse(gate.project_evidence(b,r)[1]['passed'])
                r['questions']['q1']['peer_evidence']['first']='过半'
                self.assertFalse(gate.project_evidence(b,r)[1]['passed'])

    def test_non_strict_upper_bound_does_not_support_majority(self):
        b,r=candidate('在同事不超过一半开通时，效果如何？')
        self.assertFalse(gate.project_evidence(b,r)[1]['passed'])

    def test_half_or_more_not_silently_strict(self):
        b,r=candidate('同事半数以上开通时，效果如何？')
        self.assertFalse(gate.project_evidence(b,r)[1]['passed'])

    def test_exact_count_and_any_are_distinct(self):
        for text,cond,n,passed in [('恰好一个站点使用时怎样？','恰好人数',1,True),('至少一个站点使用时怎样？','恰好人数',1,False),
            ('正好两家门店发券时怎样？','恰好人数',2,True),('正好两家门店发券时怎样？','恰好人数',1,False),
            ('恰好一个站点使用时怎样？','至少一个',None,False)]:
            with self.subTest(text=text,condition=cond,count=n):
                b,r=candidate(text,cond,n);self.assertEqual(gate.project_evidence(b,r)[1]['passed'],passed)

    def test_malformed_and_missing_fields_block_consumer(self):
        b,r=candidate('在同事过半使用时怎样？');del r['questions']['q1']['peer_evidence']
        consume=Mock(side_effect=AssertionError('must not call Core'))
        out=gate.guarded_dispatch(b,r,consume)
        consume.assert_not_called();self.assertFalse(out['core_called']);self.assertEqual(out['reading_candidate'],r)

    def test_unknown_condition_keeps_other_fields(self):
        b,r=candidate('同伴使用是否有帮助？','不明确');r['questions']['q1']['peer_evidence']['first']=None
        p,receipt=gate.project_evidence(b,r);self.assertTrue(receipt['passed']);self.assertEqual(p['questions']['q1']['first']['own'],'不开通')

    def test_query_coverage_not_weakened(self):
        b,r=candidate('在同事过半使用时怎样？');b['question_slots']['q2']='另一问'
        self.assertFalse(gate.project_evidence(b,r)[1]['passed'])

    def test_scope_of_check_explicit_not_full_semantic_proof(self):
        b,r=candidate('经理自己过半时间开通，效果如何？')
        # Literal words alone cannot establish that they describe the peers.
        receipt=gate.project_evidence(b,r)[1]
        self.assertTrue(receipt['passed']);self.assertFalse(receipt['semantic_proof'])

    def test_no_science_inferred_after_valid_evidence(self):
        i=nbib_d1_fixture.load_case();raw=deepcopy(i['raw'])
        for qid,q in raw['questions'].items():q['peer_evidence']={side:i['bundle']['question_slots'][qid] for side in ('first','second')}
        r=entries.identify(i['bundle'],raw,'D1_EFFECTS')
        self.assertFalse(r['core_called']);self.assertEqual(r['state'],'REVIEW_REQUIRED')

    def test_guarded_mock_uses_augmented_schema(self):
        i=nbib_d1_fixture.load_case();raw=deepcopy(i['raw'])
        for qid,q in raw['questions'].items():q['peer_evidence']={side:i['bundle']['question_slots'][qid] for side in ('first','second')}
        class Provider:
            def generate_json(self,**kw):
                import json
                schema=json.loads(kw['user_prompt'])['output_schema']['$defs']['Question']
                assert 'peer_evidence' in schema['required']
                return raw
        out=entries.normalize(i['bundle'],Provider(),'D1_EFFECTS');self.assertFalse(out['core_called'])


if __name__=='__main__':unittest.main()
