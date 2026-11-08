"""Offline review-chain acceptance. Mock readings are not LLM accuracy tests."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
import json
import unittest
from unittest.mock import patch
from cfm_id_bridge.scientific_binding import sha
from cfm_id import mean_order_business as entry,mean_order_reading as reading
from cfm_id.mean_order_verify import replay
from examples.mean_order_business_fixture import make_case,run,endpoint_reviews,business_review,matches_reference


class MeanOrderBusinessTests(unittest.TestCase):
    def test_paraphrases_full_chain_and_ladder(self):
        for wording in range(3):
            for mode,bounds in [('BOTH',('1/5','1')),('OWN',('-1/5','1')),('NONE',('-1','1'))]:
                with self.subTest(wording=wording,mode=mode):
                    c=make_case(mode=mode,wording=wording); raw=deepcopy(c['candidate']);result=run(c)
                    self.assertEqual(result['state'],'PARTIAL');self.assertTrue(result['core_called'])
                    cert=result['bounded_result'];self.assertEqual((cert['lower'],cert['upper']),bounds)
                    self.assertTrue(replay(cert,problem=c['expected_problem']))
                    self.assertEqual(result['reading_candidate'],raw)
                    self.assertEqual(c['candidate'],raw)
                    self.assertFalse(result['production_admission']);self.assertFalse(result['estimation_handoff_allowed'])

    def test_own_peer_none_both_scope_and_population_are_separate(self):
        c=make_case(mode={'A':'OWN','B':'PEERS','C':'BOTH','D':'NONE'},population=['A'])
        r=run(c);self.assertEqual(r['state'],'PARTIAL')
        self.assertEqual(r['proposed_model']['node_orders'],c['expected_problem'].model_dump()['node_orders'])
        self.assertEqual(r['proposed_model']['weights'],['1','0','0','0'])

    def test_reverse_point_and_other_graphs(self):
        cases=[make_case(first=[0]*4,second=[1]*4),
            make_case(first=[1,1,0,0],second=[0,0,1,1],population=['A']),
            make_case(nodes=list('ABC'),edges=[['A','B'],['B','C']],quota=1),
            make_case(nodes=list('ABC'),edges=[['A','B']],quota=1,mode='PEERS')]
        for c in cases:
            r=run(c);self.assertIn(r['state'],('POINT','PARTIAL'))
            self.assertTrue(replay(r['bounded_result'],problem=c['expected_problem']))
        self.assertEqual(run(cases[0])['bounded_result']['upper'],'-1/5')
        self.assertEqual(run(cases[1])['bounded_result']['lower'],'1/5')
        self.assertEqual(run(cases[1])['state'],'POINT')

    def test_semantic_incompleteness_and_unadapted_restrictions_stop(self):
        edits=[({'nodes':None},'NEEDS_INPUT'),({'axis':'UNKNOWN'},'NEEDS_INPUT'),
            ({'level':'UNKNOWN'},'NEEDS_INPUT'),({'scope':'UNKNOWN'},'NEEDS_INPUT'),
            ({'scope':'HISTORICAL_SUPPORT'},'NEEDS_INPUT'),({'basis':'OBSERVED_PATTERN'},'NEEDS_INPUT'),
            ({'level':'EACH_OUTCOME'},'UNSUPPORTED'),({'relation':'NO_EFFECT'},'UNSUPPORTED'),
            ({'relation':'NONINCREASING'},'UNSUPPORTED'),({'relation':'UNKNOWN'},'NEEDS_INPUT')]
        for fields,state in edits:
            c=make_case();c['candidate']['order_reading']['claims'][0].update(fields)
            with self.subTest(fields=fields),patch('cfm_id.mean_order_business.analyze',side_effect=AssertionError('backend')):
                r=run(c);self.assertEqual(r['state'],state);self.assertFalse(r['core_called']);self.assertFalse(r['bounded_backend_called'])

    def test_omitted_peer_is_not_automatically_none(self):
        c=make_case();c['candidate']['order_reading']['claims'].pop()
        r=run(c);self.assertEqual(r['state'],'NEEDS_INPUT')
        self.assertTrue(r['order_view']['clarification_questions'])

    def test_reported_conflict_and_duplicate_axes_stop(self):
        c=make_case();c['candidate']['order_reading']['reported_conflict']=True
        self.assertEqual(run(c)['state'],'NEEDS_INPUT')
        c=make_case();c['candidate']['order_reading']['claims'].append(deepcopy(c['candidate']['order_reading']['claims'][0]))
        self.assertEqual(run(c)['state'],'CHECK_BLOCKED')

    def test_null_conflict_still_blocks_without_automatic_repair(self):
        c=make_case();c['candidate']['order_reading']['reported_conflict']=None
        r=run(c);self.assertEqual(r['state'],'NEEDS_INPUT')
        self.assertIsNone(r['reading_candidate']['order_reading']['reported_conflict'])

    def test_incomplete_target_and_population_keep_original_blocks(self):
        for field in ('second','population'):
            c=make_case();c['candidate']['comparison']['reading']['questions']['q1'][field]=(
                {n:None for n in c['bundle']['node_order']} if field=='second' else None)
            self.assertEqual(run(c)['state'],'NEEDS_INPUT')

    def test_malformed_comparison_shape_remains_schema_blocked(self):
        c=make_case();c['candidate']['comparison']['reading']['questions']['q1']['second']=None
        self.assertEqual(run(c)['state'],'CHECK_BLOCKED')

    def test_additional_restriction_is_not_silently_dropped(self):
        c=make_case();c['candidate']['order_reading']['other_restriction_source_ids']=c['candidate']['order_reading']['claims'][0]['source_ids']
        self.assertEqual(run(c)['state'],'UNSUPPORTED')

    def test_bad_sources_stale_text_and_extra_model_approval_rejected(self):
        c=make_case();c['candidate']['order_reading']['claims'][0]['source_ids']=['src_'+'0'*64]
        self.assertEqual(run(c)['state'],'CHECK_BLOCKED')
        c=make_case();c['bundle']['documents']['conditions.txt']+='\n新增一句'
        self.assertEqual(run(c)['state'],'CHECK_BLOCKED')
        c=make_case();c['candidate']['order_reading']['scientific_approval']=True
        self.assertEqual(run(c)['state'],'CHECK_BLOCKED')

    def test_source_id_does_not_prove_semantic_meaning(self):
        c=make_case();row=c['candidate']['order_reading']['claims'][1]
        row.update(relation='NOT_ASSUMED',level=None,scope=None)
        self.assertEqual(entry.prepare(c['bundle'],c['candidate'],query_id='q1',science=c['science'])['state'],'REVIEW_REQUIRED')
        self.assertFalse(matches_reference(c,c['candidate']))
        r=run(c);self.assertEqual(r['state'],'REVIEW_REQUIRED');self.assertFalse(r['bounded_backend_called'])

    def test_scientific_packet_cannot_override_actual_model_target_or_order(self):
        for field,value in [('first',[0]*4),('node_orders',[]),('lipschitz','1')]:
            c=make_case();c['science']['model'][field]=value
            self.assertEqual(run(c)['state'],'CHECK_BLOCKED')

    def test_no_review_or_opt_in_no_core_calls(self):
        c=make_case();chain=endpoint_reviews(c,c['candidate']);r=business_review(c,c['candidate'],chain)
        for kwargs in [dict(chain,review=None),dict(chain,review=r,synthetic_protocol_selected=False)]:
            result=entry.submit(c['bundle'],c['candidate'],query_id='q1',science=c['science'],**kwargs)
            self.assertEqual(result['state'],'REVIEW_REQUIRED');self.assertFalse(result['core_called'])

    def test_each_axis_pending_rejected_missing_or_disagreeing_confirmation(self):
        for mode in ('pending','rejected','missing','wrong_modes'):
            c=make_case();chain=endpoint_reviews(c,c['candidate']);r=business_review(c,c['candidate'],chain)
            data=r.model_dump();key=next(iter(data['axis_decisions']))
            if mode=='pending':data['axis_decisions'][key]='PENDING'
            if mode=='rejected':data['axis_decisions'][key]='REJECTED'
            if mode=='missing':data['axis_decisions'].pop(key)
            if mode=='wrong_modes':data['confirmed_node_modes']['A']='OWN'
            result=entry.submit(c['bundle'],c['candidate'],query_id='q1',science=c['science'],review=entry.ReviewedMeanOrderBusiness.model_validate(data),**chain)
            self.assertEqual(result['state'],'REVIEW_REQUIRED' if mode in ('pending','missing') else 'CHECK_BLOCKED')
            self.assertFalse(result['core_called']);self.assertFalse(result['bounded_backend_called'])

    def test_stale_science_values_outcome_units_and_direction_review(self):
        for field in ('values','outcome_unit','bounds'):
            c=make_case();chain=endpoint_reviews(c,c['candidate']);r=business_review(c,c['candidate'],chain)
            if field=='values':c['science']['model'][field][0]['value']='1/2'
            if field=='outcome_unit':c['science']['model'][field]='分'
            if field=='bounds':c['science']['model'][field][0]['upper']='9/10'
            result=entry.submit(c['bundle'],c['candidate'],query_id='q1',science=c['science'],review=r,**chain)
            self.assertEqual(result['state'],'CHECK_BLOCKED');self.assertFalse(result['core_called'])

    def test_old_inner_reviews_are_still_required(self):
        for omission in ('assignment','business_intent','science_admission','endpoint_source'):
            c=make_case();chain=endpoint_reviews(c,c['candidate'])
            if omission=='business_intent':
                port=chain['context']['second'].core_port;b=port.bindings['q1'];port.bindings['q1']=replace(b,business_intent=None)
            if omission=='science_admission':
                port=chain['context']['second'].core_port;b=port.bindings['q1']
                port.bindings['q1']=replace(b,admission=b.admission.model_copy(update={'approved_scientific_binding':None}))
            if omission=='endpoint_source':chain['context']['second'].core_port.comparison_endpoint_sources={}
            # Even a fresh outer review must not replace missing inner evidence.
            r=business_review(c,c['candidate'],chain)
            if omission=='assignment':chain['assignment_review']['second']=None
            result=entry.submit(c['bundle'],c['candidate'],query_id='q1',science=c['science'],review=r,**chain)
            self.assertEqual(result['state'],'CHECK_BLOCKED');self.assertFalse(result['bounded_backend_called'])

    def test_joint_model_cannot_ignore_extra_or_full_law_information(self):
        c=make_case();c['science']['model']['model_scope']='FULL_JOINT_LAW'
        self.assertEqual(run(c)['state'],'CHECK_BLOCKED')

    def test_combined_request_schema_references_and_no_private_science(self):
        c=make_case();system,user=reading.make_request(c['bundle']);payload=json.loads(user);schema=payload['output_schema']
        def check(x):
            if isinstance(x,dict):
                if '$ref' in x:self.assertIn(x['$ref'].split('/')[-1],schema['$defs'])
                for v in x.values():check(v)
            if isinstance(x,list):
                for v in x:check(v)
        check(schema)
        from cfm_id.source_locations import build_catalog
        allowed=schema['$defs']['CurrentOrderSourceId']['enum']
        self.assertEqual(set(allowed),set(build_catalog(c['bundle']['documents'])))
        used=[]
        def source_fields(x):
            if isinstance(x,dict):
                for k,v in x.get('properties',{}).items():
                    if k in ('source_ids','other_restriction_source_ids'):used.append(v['items'])
                for v in x.values():source_fields(v)
            elif isinstance(x,list):
                for v in x:source_fields(v)
        source_fields(schema)
        self.assertEqual(len(used),3)
        self.assertTrue(all(x=={'$ref':'#/$defs/CurrentOrderSourceId'} for x in used))
        for value in ('expected_problem','axis_decisions','confirmed_node_modes','certificate','EXACT_SYNTHETIC_POPULATION'):
            self.assertNotIn(value,user)
        self.assertIn('不能把未提及',system.replace('原文未提及的轴不要补 NOT_ASSUMED','不能把未提及'))


if __name__=='__main__':unittest.main()
