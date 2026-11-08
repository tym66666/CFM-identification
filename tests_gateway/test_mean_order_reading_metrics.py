from copy import deepcopy
import unittest
from evaluation.mean_order_reading_metrics import compare_order_readings
from examples.mean_order_business_fixture import make_case

class OrderReadingMetricTests(unittest.TestCase):
    def setUp(self):
        self.c=make_case()
        self.bundle=self.c['bundle']
        self.ref=self.c['candidate']['order_reading']

    def test_complete_reference_passes_without_approval(self):
        result=compare_order_readings(self.bundle,self.ref,self.ref)
        self.assertTrue(result['semantic_passed']);self.assertTrue(result['counts_in_denominator'])
        self.assertFalse(result['scientific_approval'])

    def test_missing_object_unknown_axis_and_omitted_claim_count_as_failures(self):
        for kind in ('null_nodes','unknown_axis','omitted_claim'):
            raw=deepcopy(self.ref)
            if kind=='null_nodes':raw['claims'][0]['nodes']=None
            elif kind=='unknown_axis':raw['claims'][0]['axis']='UNKNOWN'
            else:raw['claims'].pop(0)
            before=deepcopy(raw)
            with self.subTest(kind=kind):
                r=compare_order_readings(self.bundle,raw,self.ref)
                self.assertTrue(r['valid_reading']);self.assertFalse(r['semantic_passed'])
                self.assertTrue(r['counts_in_denominator']);self.assertEqual(r['reading_state'],'NEEDS_INPUT')
                self.assertEqual(r['error_code'],'INCOMPLETE_OBJECT_AXES');self.assertEqual(raw,before)

    def test_direction_error_stays_wrong_and_unsupported(self):
        raw=deepcopy(self.ref);raw['claims'][1]['relation']='NONINCREASING';before=deepcopy(raw)
        r=compare_order_readings(self.bundle,raw,self.ref)
        self.assertFalse(r['order_fields']);self.assertTrue(r['source_evidence'])
        self.assertEqual(r['reading_state'],'UNSUPPORTED');self.assertEqual(raw,before)

    def test_scope_unknown_stays_unknown(self):
        raw=deepcopy(self.ref);raw['claims'][1]['scope']='UNKNOWN'
        r=compare_order_readings(self.bundle,raw,self.ref)
        self.assertTrue(r['object_axes_complete']);self.assertFalse(r['order_fields'])
        self.assertEqual(r['reading_state'],'NEEDS_INPUT');self.assertEqual(raw['claims'][1]['scope'],'UNKNOWN')

    def test_invalid_candidate_is_recorded_instead_of_raising(self):
        approval=deepcopy(self.ref);approval['scientific_approval']=True
        source=deepcopy(self.ref);source['claims'][0]['source_ids']=['missing_source']
        for raw in (None,{},approval,source):
            with self.subTest(raw_type=type(raw).__name__):
                r=compare_order_readings(self.bundle,raw,self.ref)
                self.assertFalse(r['valid_reading']);self.assertFalse(r['semantic_passed'])
                self.assertTrue(r['counts_in_denominator']);self.assertEqual(r['error_code'],'INVALID_ORDER_READING')

    def test_broken_reference_raises_instead_of_hiding_gold_error(self):
        broken=deepcopy(self.ref);broken['claims'][0]['nodes']=None
        with self.assertRaises(ValueError):compare_order_readings(self.bundle,self.ref,broken)

    def test_batch_continues_after_incomplete_candidate(self):
        bad=deepcopy(self.ref);bad['claims'][0]['nodes']=None
        results=[compare_order_readings(self.bundle,c,self.ref) for c in (bad,self.ref)]
        self.assertEqual(len(results),2)
        self.assertEqual(sum(r['counts_in_denominator'] for r in results),2)
        self.assertEqual(sum(r['semantic_passed'] for r in results),1)

if __name__=='__main__':unittest.main()

