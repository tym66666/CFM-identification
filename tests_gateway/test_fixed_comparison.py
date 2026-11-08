"""Acceptance, review isolation and directional algebra; no API requests."""
from copy import deepcopy
from fractions import Fraction
from unittest.mock import Mock, patch
import unittest
from pydantic import ValidationError
import cfm_id_bridge.bridge as bridge
import pfn_pipeline.identification_business as core
from cfm_id_bridge.scientific_binding import sha
from cfm_id import fixed_comparison as comparison
from cfm_id.business_entry import prepare_request, preview, read_once
from cfm_id.intent_submission import submit
from examples.fixed_comparison_fixture import (
    public_bundle, reference, reviews, declared_targets, independent_oracle, CONTRACT)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.b=public_bundle();self.raw=reference(self.b)

    def call(self, raw=None, options=None):
        raw=self.raw if raw is None else raw
        options=reviews(self.b,raw) if options is None else options
        with patch.object(bridge,'identify_network_business_query',wraps=bridge.identify_network_business_query) as bs, patch.object(core,'identify_network_business_query',wraps=core.identify_network_business_query) as ds:
            out=submit(self.b,raw,'FIXED_COMPARISON',contract=CONTRACT,**options)
        return out,(bs.call_count,ds.call_count)

    def endpoints(self,q='q1'):
        opts=reviews(self.b,self.raw)
        return tuple(core.identify_network_business_query(opts['context'][s].core_port.bindings[q].inquiry) for s in comparison.SIDES)

    def test_full_chain_and_independent_finite_population_oracle(self):
        before=deepcopy(self.raw);out,counts=self.call()
        self.assertEqual(counts,(6,6));self.assertEqual(self.raw,before)
        self.assertEqual(out['reading_candidate'],before)
        views={v['query_id']:v for v in out['query_views']}
        self.assertEqual([v['state'] for v in views.values()],['CORE_POINT','CORE_POINT','NEEDS_INPUT','UNSUPPORTED','NEEDS_INPUT'])
        results={}
        for q in ('q1','q2'):
            v=views[q];self.assertTrue(v['composition_replayed']);self.assertTrue(v['certificate_replayed'])
            self.assertFalse(v['composition']['new_core_theorem'])
            self.assertFalse(v['composition']['estimation_handoff_allowed'])
            results[q]=independent_oracle(declared_targets(self.b)[q],v['composition'])
        for i in (0,1):
            a=Fraction(results['q1']['schedules'][i]['causal']);b=Fraction(results['q2']['schedules'][i]['causal'])
            self.assertNotEqual(a,0);self.assertEqual(a,-b)
        for q in ('q3','q5'):
            self.assertFalse(views[q]['core_called']);self.assertNotIn('composition',views[q])
        v=views['q4'];self.assertFalse(v['nonidentification_proved']);self.assertFalse(v['certificate_replayed'])
        self.assertEqual(v['endpoints']['first']['state'],'UNSUPPORTED')
        self.assertEqual(v['endpoints']['second']['state'],'CORE_POINT')
        self.assertTrue(independent_oracle(declared_targets(self.b)['q4'],None)['passed'])

    def test_natural_wording_uses_same_frozen_targets(self):
        self.b=public_bundle('natural');self.raw=reference(self.b)
        out,counts=self.call()
        self.assertEqual(counts,(6,6))
        self.assertEqual([v['state'] for v in out['query_views']],['CORE_POINT','CORE_POINT','NEEDS_INPUT','UNSUPPORTED','NEEDS_INPUT'])

    def test_preview_is_not_approval_and_legacy_entry_stays_unsupported(self):
        new=preview(self.b,self.raw,'FIXED_COMPARISON',contract=CONTRACT)
        old=preview(self.b,self.raw,'FIXED_POLICY',contract=CONTRACT)
        self.assertEqual(new['query_views'][0]['state'],'REVIEW_REQUIRED')
        self.assertEqual(old['query_views'][0]['state'],'UNSUPPORTED')
        self.assertFalse(new['core_called'])
        self.assertNotIn('reviewer',comparison.worksheet(self.b,self.raw,**{
            'packets':reviews(self.b,self.raw)['packet'],'contexts':reviews(self.b,self.raw)['context']}))

    def test_entry_and_contract_are_explicit(self):
        for contract in ('intent-v0561','legacy-v0551','fixed-assignment'):
            with self.subTest(contract=contract),self.assertRaises(ValueError):
                prepare_request(self.b,'FIXED_COMPARISON',contract=contract)
        with self.assertRaises(ValueError):prepare_request(self.b,'FIXED_COMPARISON',{},contract=CONTRACT)
        request=prepare_request(self.b,'FIXED_COMPARISON',contract=CONTRACT)
        self.assertIn('first减second',request['system'])
        self.assertNotIn('COMPARISON_A4_FULL_LAW',request['user'])

    def test_mock_reads_once_and_never_grants_review(self):
        provider=Mock();provider.generate_json.return_value=deepcopy(self.raw)
        out=read_once(self.b,provider,'FIXED_COMPARISON',contract=CONTRACT)
        provider.generate_json.assert_called_once();self.assertFalse(out['core_called'])
        provider.generate_json.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError):read_once(self.b,provider,'FIXED_COMPARISON',contract=CONTRACT)
        self.assertEqual(provider.generate_json.call_count,2)

    def test_each_missing_review_or_opt_in_prevents_calls(self):
        for key in ('packet','context','submission_review','assignment_review','synthetic_protocol_selected'):
            with self.subTest(key=key):
                opts=reviews(self.b,self.raw);opts[key]=False if key=='synthetic_protocol_selected' else None
                out,counts=self.call(options=opts)
                self.assertEqual(counts,(0,0));self.assertFalse(out['core_called'])

    def test_both_endpoint_packets_contexts_and_fact_reviews_required(self):
        for key in ('packet','context','assignment_review'):
            for side in comparison.SIDES:
                with self.subTest(key=key,side=side):
                    opts=reviews(self.b,self.raw);del opts[key][side]
                    out,counts=self.call(options=opts)
                    self.assertEqual(counts,(0,0));self.assertEqual(out['state'],'CHECK_BLOCKED')

    def test_stale_reading_review_blocks_target_direction_and_population_changes(self):
        for field in ('first','second','population'):
            with self.subTest(field=field):
                opts=reviews(self.b,self.raw);raw=deepcopy(self.raw);q=raw['reading']['questions']['q1']
                if field=='population':q[field]=['B']
                else:q[field]['F']=1
                out,counts=self.call(raw,opts)
                self.assertEqual(counts,(0,0));self.assertEqual(out['state'],'CHECK_BLOCKED')

    def test_new_outer_review_cannot_override_independently_declared_endpoints(self):
        for mutation in ('direction','population','assignment'):
            with self.subTest(mutation=mutation):
                raw=deepcopy(self.raw);q=raw['reading']['questions']['q1']
                if mutation=='direction':q['first'],q['second']=q['second'],q['first']
                elif mutation=='population':q['population']=['B']
                else:q['first']['F']=1
                out,counts=self.call(raw,reviews(self.b,raw))
                self.assertEqual(counts,(0,0));self.assertEqual(out['state'],'CHECK_BLOCKED')

    def test_swapped_endpoints_or_packet_scientific_hashes_block(self):
        for mutation in ('swap','study','a4','a5'):
            with self.subTest(mutation=mutation):
                opts=reviews(self.b,self.raw)
                if mutation=='swap':
                    opts['context']['first'],opts['context']['second']=opts['context']['second'],opts['context']['first']
                else:
                    name={'study':'study_sha256','a4':'a4_sources_sha256','a5':'a5_licenses_sha256'}[mutation]
                    opts['packet']['second']['queries']['q1'][name]='0'*64
                out,counts=self.call(options=opts)
                self.assertEqual(counts,(0,0));self.assertEqual(out['state'],'CHECK_BLOCKED')

    def test_malformed_or_stale_ids_block_all_calls(self):
        for value in ({},None,'bad','question_'+'0'*64):
            with self.subTest(value=value):
                raw=deepcopy(self.raw)
                raw['reading']['intents']['q1']['question_id']=value
                out,counts=self.call(raw,{})
                self.assertEqual(counts,(0,0));self.assertEqual(out['state'],'CHECK_BLOCKED')

    def test_invalid_population_not_normalized_to_all(self):
        for value in ([],['B','B'],['UNKNOWN']):
            raw=deepcopy(self.raw);raw['reading']['questions']['q1']['population']=value
            out,counts=self.call(raw,{})
            self.assertEqual(counts,(0,0));self.assertNotEqual(out['state'],'CORE_POINT')

    def test_missing_conditions_and_design_conflicts_remain_unknown(self):
        for field in ('first','second','population'):
            b=public_bundle(only=['q1']);raw=reference(b)
            if field=='population':raw['reading']['questions']['q1'][field]=None
            else:raw['reading']['questions']['q1'][field]['F']=None
            out=submit(b,raw,'FIXED_COMPARISON',contract=CONTRACT)
            self.assertEqual(out['state'],'NEEDS_INPUT');self.assertFalse(out['core_called'])
        for field,value in (('reported_conflict',True),('uniform_subset_declared',None)):
            raw=deepcopy(self.raw);raw['reported_assignment'][field]=value
            out,counts=self.call(raw,{})
            self.assertEqual(counts,(0,0));self.assertEqual(out['state'],'NEEDS_INPUT')

    def test_noncomparison_and_unequal_aggregation_not_admitted(self):
        for field,value in (('kind','水平'),('kind','选最优'),('aggregation','其他')):
            b=public_bundle(only=['q1']);raw=reference(b)
            target=raw['reading']['intents']['q1'] if field=='kind' else raw['reading']['questions']['q1']
            target[field]=value
            out=submit(b,raw,'FIXED_COMPARISON',contract=CONTRACT)
            self.assertNotEqual(out['state'],'CORE_POINT');self.assertFalse(out['core_called'])

    def test_unknown_population_does_not_erase_declared_equal_mean(self):
        b=public_bundle(only=['q5']);raw=reference(b)
        out=preview(b,raw,'FIXED_COMPARISON',contract=CONTRACT)
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertEqual(out['reading_candidate']['reading']['questions']['q5']['aggregation'],'等权平均')
        self.assertEqual(out['intent_condition_review']['q5']['missing_conditions'],['population'])
        prompt=prepare_request(b,'FIXED_COMPARISON',contract=CONTRACT)['system']
        self.assertIn('评价名单与汇总方式必须分别判断',prompt)

    def test_unknown_aggregation_not_filled_from_other_questions(self):
        raw=deepcopy(self.raw);raw['reading']['questions']['q5']['aggregation']='不明确'
        out=preview(self.b,raw,'FIXED_COMPARISON',contract=CONTRACT)
        self.assertEqual(out['reading_candidate']['reading']['questions']['q5']['aggregation'],'不明确')
        self.assertEqual(set(out['intent_condition_review']['q5']['missing_conditions']),{'population','aggregation'})
        self.assertFalse(out['core_called'])

    def test_review_requires_strict_true_and_no_extra_fields(self):
        data=reviews(self.b,self.raw)['submission_review'].model_dump()
        for value in (False,1,'true'):
            d=dict(data,reviewed_comparison_direction_and_population=value)
            with self.assertRaises(ValidationError):comparison.ReviewedComparison.model_validate(d)
        with self.assertRaises(ValidationError):comparison.ReviewedComparison.model_validate(dict(data,approval=True))

    def test_independent_replay_rejects_rehashed_forgery(self):
        a,b=self.endpoints();t=declared_targets(self.b)['q1'];binding={'query_id':'q1'}
        receipt=comparison.compose(a,b,target=t,binding=binding)
        self.assertTrue(comparison.replay(receipt,a,b,target=t,binding=binding))
        for kind in ('sign','order','formula','endpoint','binding','target','extra','approval'):
            with self.subTest(kind=kind):
                r=deepcopy(receipt)
                if kind=='sign':r['terms'][2]['coefficient']='1/2'
                elif kind=='order':r['terms'].reverse()
                elif kind=='formula':r['identified_functional']='0'
                elif kind=='endpoint':r['endpoint_sha256']['second']='0'*64
                elif kind=='binding':r['binding']['query_id']='q2'
                elif kind=='target':r['target']['first'],r['target']['second']=r['target']['second'],r['target']['first']
                elif kind=='extra':r['extra']=True
                else:r['estimation_handoff_allowed']=True
                r.pop('receipt_sha256');r['receipt_sha256']=sha(r)
                self.assertFalse(comparison.replay(r,a,b,target=t,binding=binding))
        self.assertFalse(comparison.replay(receipt,b,a,target=t,binding=binding))

    def test_nonpoint_endpoint_cannot_be_composed(self):
        a,b=self.endpoints('q4')
        with self.assertRaisesRegex(ValueError,'TWO_REPLAYED'):
            comparison.compose(a,b,target=declared_targets(self.b)['q4'],binding={})

    def test_identical_endpoints_have_exact_zero_contrast(self):
        a,_=self.endpoints();t=declared_targets(self.b)['q1'];t['second']=list(t['first'])
        r=comparison.compose(a,a,target=t,binding={})
        self.assertTrue(comparison.replay(r,a,a,target=t,binding={}))
        oracle=independent_oracle(t,r)
        self.assertTrue(all(v['causal']=='0' for v in oracle['schedules']))

    def test_common_study_and_target_weights_are_verified(self):
        a,b=self.endpoints();t=declared_targets(self.b)['q1']
        bad=deepcopy(t);bad['unit_weights']=['0','1/3','0','2/3','0','0']
        with self.assertRaises(ValueError):comparison.compose(a,b,target=bad,binding={})
        self.b=public_bundle('natural');self.raw=reference(self.b)
        _,other=self.endpoints()
        with self.assertRaisesRegex(ValueError,'COMMON_ENDPOINT_MODEL'):
            comparison.compose(a,other,target=t,binding={})


if __name__=='__main__':unittest.main()
