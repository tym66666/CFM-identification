from copy import deepcopy
import json,unittest
from examples.mean_order_business_fixture import make_case,run
from cfm_id import mean_order_reading as legacy
from evaluation import mean_order_factored_reading as f

class FactoredReadingTests(unittest.TestCase):
    def setUp(self):
        self.c=make_case();self.b=self.c['bundle'];self.raw=f.reference_wire(self.b,self.c['candidate'])
    def test_default_unchanged_and_only_order_protocol_changes(self):
        before=legacy.make_request(self.b);system,user=f.make_request(self.b)
        a,b=json.loads(before[1]),json.loads(user)
        self.assertEqual({k:v for k,v in a.items() if k!='output_schema'},{k:v for k,v in b.items() if k!='output_schema'})
        self.assertEqual(a['output_schema']['properties']['comparison'],b['output_schema']['properties']['comparison'])
        self.assertNotIn('OrderClaim',b['output_schema']['$defs'])
        def check_refs(x):
            if isinstance(x,dict):
                if '$ref' in x:self.assertIn(x['$ref'].split('/')[-1],b['output_schema']['$defs'])
                for y in x.values():check_refs(y)
            elif isinstance(x,list):
                for y in x:check_refs(y)
        check_refs(b['output_schema'])
        self.assertEqual(legacy.make_request(self.b),before)
        self.assertEqual(system.split('\n现在填写独立的 order_reading')[0],before[0].split('\n现在填写独立的 order_reading')[0])
    def test_positive_chain_three_modes_preserves_inputs(self):
        for mode,bounds in [('BOTH',['1/5','1']),('OWN',['-1/5','1']),('NONE',['-1','1'])]:
            c=make_case(mode=mode);wire=f.reference_wire(c['bundle'],c['candidate']);original=deepcopy(wire)
            canonical=f.to_canonical(c['bundle'],wire);r=run(c,canonical)
            with self.subTest(mode=mode):
                self.assertEqual(canonical,c['candidate']);self.assertEqual(wire,original)
                self.assertEqual([r['bounded_result']['lower'],r['bounded_result']['upper']],bounds)
                self.assertTrue(r['bounded_certificate_replayed'])
    def test_pathwise_is_preserved_and_not_weakened(self):
        raw=deepcopy(self.raw);raw['order_reading']['claims'][1]['quantity']='每次潜在结果'
        canonical=f.to_canonical(self.b,raw);r=run(self.c,canonical)
        self.assertEqual(canonical['order_reading']['claims'][1]['level'],'EACH_OUTCOME')
        self.assertEqual(r['state'],'UNSUPPORTED');self.assertFalse(r['bounded_backend_called'])
    def test_observed_statistics_are_explicitly_lossy_and_blocked(self):
        raw=deepcopy(self.raw);raw['order_reading']['claims'][1].update(declaration='仅报告观察',quantity='历史样本统计',scope='HISTORICAL_SUPPORT')
        before=deepcopy(raw);canonical=f.to_canonical(self.b,raw);receipt=f.projection_receipt(self.b,raw,canonical)
        self.assertEqual(canonical['order_reading']['claims'][1]['level'],'UNKNOWN')
        self.assertFalse(receipt['legacy_projection_is_lossless']);self.assertFalse(receipt['scientific_approval'])
        self.assertEqual(run(self.c,canonical)['state'],'NEEDS_INPUT');self.assertEqual(raw,before)
    def test_wire_metric_does_not_hide_lossy_quantity_errors(self):
        ref=deepcopy(self.raw);ref['order_reading']['claims'][1].update(declaration='仅报告观察',quantity='历史样本统计',scope='HISTORICAL_SUPPORT')
        wrong=deepcopy(ref);wrong['order_reading']['claims'][1]['quantity']='尚不明确'
        self.assertEqual(f.to_canonical(self.b,ref),f.to_canonical(self.b,wrong))
        self.assertFalse(f.wire_metrics(self.b,wrong,ref)['passed'])
        self.assertTrue(f.wire_metrics(self.b,ref,ref)['passed'])
    def test_incoherent_declarations_are_rejected_not_fixed(self):
        for change in [dict(declaration='明确不作假设'),dict(declaration='仅报告观察'),dict(quantity='历史样本统计'),dict(quantity=None)]:
            raw=deepcopy(self.raw);raw['order_reading']['claims'][0].update(change);before=deepcopy(raw)
            with self.subTest(change=change),self.assertRaises(ValueError):f.to_canonical(self.b,raw)
            self.assertEqual(raw,before)
    def test_unknown_fields_stay_unknown_and_block(self):
        for key,value in [('nodes',None),('axis','UNKNOWN'),('quantity','尚不明确'),('scope','UNKNOWN')]:
            raw=deepcopy(self.raw);raw['order_reading']['claims'][1][key]=value
            canonical=f.to_canonical(self.b,raw);result=run(self.c,canonical)
            with self.subTest(key=key):
                self.assertEqual(result['state'],'NEEDS_INPUT');self.assertFalse(result['bounded_backend_called'])
                self.assertFalse(f.wire_metrics(self.b,raw,self.raw)['passed'])
    def test_wrong_direction_and_nonassumption_are_not_repaired(self):
        for change in [dict(direction='<='),dict(declaration='明确不作假设',direction=None,quantity=None,scope=None)]:
            raw=deepcopy(self.raw);raw['order_reading']['claims'][1].update(change)
            canonical=f.to_canonical(self.b,raw);result=run(self.c,canonical)
            self.assertFalse(f.wire_metrics(self.b,raw,self.raw)['passed']);self.assertFalse(result['bounded_backend_called'])
    def test_invalid_id_version_approval_and_old_label_rejected(self):
        for kind in ('source','version','approval','old_direction','boolean'):
            raw=deepcopy(self.raw)
            if kind=='source':raw['order_reading']['claims'][0]['source_ids']=['bad_source']
            elif kind=='version':raw['order_reading']['version']=legacy.VERSION
            elif kind=='approval':raw['order_reading']['scientific_approval']=True
            elif kind=='boolean':raw['order_reading']['reported_conflict']='false'
            else:raw['order_reading']['claims'][0]['direction']='NONDECREASING'
            with self.subTest(kind=kind),self.assertRaises(ValueError):f.to_canonical(self.b,raw)
            self.assertFalse(f.wire_metrics(self.b,raw,self.raw)['passed'])
    def test_grouping_order_does_not_change_meaning(self):
        raw=deepcopy(self.raw);claims=[]
        for row in raw['order_reading']['claims']:
            for n in reversed(row['nodes']):
                one=deepcopy(row);one['nodes']=[n];claims.append(one)
        raw['order_reading']['claims']=list(reversed(claims))
        self.assertTrue(f.wire_metrics(self.b,raw,self.raw)['passed'])
    def test_reference_unknown_is_not_guessed_from_basis(self):
        canonical=deepcopy(self.c['candidate'])
        canonical['order_reading']['claims'][1].update(basis='OBSERVED_PATTERN',level='UNKNOWN')
        raw=f.reference_wire(self.b,canonical)
        self.assertEqual(raw['order_reading']['claims'][1]['quantity'],'尚不明确')
        self.assertEqual(f.to_canonical(self.b,raw),canonical)

if __name__=='__main__':unittest.main()

