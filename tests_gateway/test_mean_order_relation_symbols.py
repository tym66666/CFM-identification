from copy import deepcopy
import json
import unittest
from evaluation import mean_order_relation_symbols as codec
from examples.mean_order_business_fixture import make_case,run
from cfm_id import mean_order_reading as reading

class RelationSymbolTests(unittest.TestCase):
    def setUp(self):self.c=make_case()

    def test_all_five_relations_roundtrip_without_mutation(self):
        for relation in codec.TO_SYMBOL:
            with self.subTest(relation=relation):
                candidate=deepcopy(self.c['candidate']);row=candidate['order_reading']['claims'][0]
                row['relation']=relation
                if relation=='NOT_ASSUMED':row.update(level=None,scope=None)
                original=deepcopy(candidate)
                wire=codec.to_wire(self.c['bundle'],candidate,encoding='symbol');before=deepcopy(wire)
                self.assertEqual(wire['order_reading']['claims'][0]['relation'],codec.TO_SYMBOL[relation])
                self.assertEqual(codec.from_wire(self.c['bundle'],wire,encoding='symbol'),candidate)
                self.assertEqual(candidate,original);self.assertEqual(wire,before)
                receipt=codec.codec_receipt(self.c['bundle'],wire,candidate,encoding='symbol')
                self.assertFalse(receipt['scientific_approval']);self.assertFalse(receipt['mathematical_certificate'])

    def test_english_arm_is_identity_and_default_request_unchanged(self):
        base=reading.make_request(self.c['bundle'])
        wire=codec.to_wire(self.c['bundle'],self.c['candidate'],encoding='english')
        self.assertEqual(wire,self.c['candidate'])
        self.assertEqual(codec.from_wire(self.c['bundle'],wire,encoding='english'),wire)
        codec.make_request(self.c['bundle'],encoding='english');codec.make_request(self.c['bundle'],encoding='symbol')
        self.assertEqual(base,reading.make_request(self.c['bundle']))

    def test_request_arms_differ_only_in_declared_labels_and_version(self):
        es,eu=codec.make_request(self.c['bundle'],encoding='english')
        ss,su=codec.make_request(self.c['bundle'],encoding='symbol')
        for old,new in codec.TO_SYMBOL.items():
            if old!=new:es=es.replace(json.dumps(old),json.dumps(new))
        es=es.replace('version 为 '+reading.VERSION+'。','version 为 '+codec.SYMBOL_VERSION+'。')
        self.assertEqual(es,ss)
        e,s=json.loads(eu),json.loads(su);defs=s['output_schema']['$defs']
        defs['OrderClaim']['properties']['relation']['enum']=[codec.FROM_SYMBOL[x] for x in defs['OrderClaim']['properties']['relation']['enum']]
        s['output_schema']['properties']['order_reading']['properties']['version']['const']=reading.VERSION
        self.assertEqual(e,s)

    def test_wrong_direction_is_not_corrected(self):
        wire=codec.to_wire(self.c['bundle'],self.c['candidate'],encoding='symbol')
        wire['order_reading']['claims'][1]['relation']='<='
        canonical=codec.from_wire(self.c['bundle'],wire,encoding='symbol')
        self.assertEqual(canonical['order_reading']['claims'][1]['relation'],'NONINCREASING')
        result=run(self.c,canonical)
        self.assertEqual(result['state'],'UNSUPPORTED');self.assertFalse(result['bounded_backend_called'])

    def test_scope_unknown_remains_unknown_and_blocks(self):
        wire=codec.to_wire(self.c['bundle'],self.c['candidate'],encoding='symbol')
        wire['order_reading']['claims'][1]['scope']='UNKNOWN'
        canonical=codec.from_wire(self.c['bundle'],wire,encoding='symbol')
        self.assertEqual(canonical['order_reading']['claims'][1]['scope'],'UNKNOWN')
        result=run(self.c,canonical)
        self.assertEqual(result['state'],'NEEDS_INPUT');self.assertFalse(result['bounded_backend_called'])

    def test_wrong_dialect_and_non_exact_symbols_rejected(self):
        for value in ('NONDECREASING','≥','>','>= ',None):
            with self.subTest(value=value):
                wire=codec.to_wire(self.c['bundle'],self.c['candidate'],encoding='symbol')
                wire['order_reading']['claims'][0]['relation']=value
                with self.assertRaises(ValueError):codec.from_wire(self.c['bundle'],wire,encoding='symbol')
        with self.assertRaises(ValueError):codec.from_wire(self.c['bundle'],self.c['candidate'],encoding='symbol')
        with self.assertRaises(ValueError):codec.from_wire(self.c['bundle'],self.c['candidate'],encoding='auto')

    def test_extra_approval_bad_source_and_stale_question_rejected(self):
        for kind in ('approval','source','question'):
            wire=codec.to_wire(self.c['bundle'],self.c['candidate'],encoding='symbol')
            if kind=='approval':wire['order_reading']['scientific_approval']=True
            elif kind=='source':wire['order_reading']['claims'][0]['source_ids']=['src_'+'0'*64]
            else:wire['comparison']['reading']['intents']['q1']['question_id']='question_'+'0'*64
            with self.subTest(kind=kind),self.assertRaises(ValueError):codec.from_wire(self.c['bundle'],wire,encoding='symbol')

    def test_full_reviewed_chain_uses_the_decoded_actual_candidate(self):
        wire=codec.to_wire(self.c['bundle'],self.c['candidate'],encoding='symbol')
        canonical=codec.from_wire(self.c['bundle'],wire,encoding='symbol');result=run(self.c,canonical)
        self.assertEqual(result['state'],'PARTIAL');self.assertTrue(result['bounded_certificate_replayed'])
        self.assertEqual(result['reading_candidate'],canonical)
        self.assertEqual([result['bounded_result']['lower'],result['bounded_result']['upper']],['1/5','1'])

if __name__=='__main__':unittest.main()
