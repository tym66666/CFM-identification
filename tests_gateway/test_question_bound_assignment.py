"""ID/source binding and existing scientific gates, all offline."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from pydantic import ValidationError
import cfm_id_bridge.bridge as bridge
import pfn_pipeline.identification_business as core
from cfm_id import question_bound_assignment as qbound
from cfm_id.business_entry import prepare_request, preview, read_once
from cfm_id.intent_submission import submit
from cfm_id.assignment_review import (assignment_worksheet, ReviewedQuestionBoundAssignmentFacts)
from tests_gateway.test_fixed_assignment_submission import quota_full_fixture, approved_assignment
import tests_gateway.test_fixed_assignment_submission as fixture_module


def bind_fixture(b, old):
    raw=deepcopy(old)
    for qid, record in qbound.question_catalog(b).items():
        raw['reading']['intents'][qid].pop('quote')
        raw['reading']['intents'][qid]['question_id']=record['question_id']
    return raw


def review_for(b,raw,p,c):
    return ReviewedQuestionBoundAssignmentFacts(**assignment_worksheet(b,raw,p,c,contract=qbound.CONTRACT),
        reviewer='Independent synthetic ID reviewer', evidence='Original model candidate, located question and scientific context separately reviewed.',
        reviewed_original_assignment_and_sources=True,synthetic_fixture=True)


class QuestionBoundTests(unittest.TestCase):
    def setUp(self):
        self.b,self.old,self.p,self.c,self.ir=quota_full_fixture()
        self.raw=bind_fixture(self.b,self.old)

    def call(self,raw=None,review=None,**kwargs):
        raw=self.raw if raw is None else raw
        options=dict(packet=self.p,context=self.c,submission_review=self.ir,assignment_review=review,synthetic_protocol_selected=True,contract=qbound.CONTRACT)
        options.update(kwargs)
        with patch.object(bridge,'identify_network_business_query',wraps=bridge.identify_network_business_query) as bs, patch.object(core,'identify_network_business_query',wraps=core.identify_network_business_query) as ds:
            result=submit(self.b,raw,'FIXED_POLICY',**options)
        return result,(bs.call_count,ds.call_count)

    def test_resolves_original_without_mutating_model_fields(self):
        b=deepcopy(self.b);raw=deepcopy(self.raw)
        resolved,receipt=qbound.resolve_reading(b,raw)
        self.assertEqual(resolved,self.old)
        self.assertEqual(raw,self.raw);self.assertEqual(b,self.b)
        self.assertFalse(receipt['model_quote_supplied']);self.assertFalse(receipt['scientific_approval'])
        for record in receipt['question_sources'].values():
            for loc in record['locations']:
                self.assertEqual(b['documents'][loc['doc_id']][loc['start']:loc['end']],record['text'])

    def test_prompt_has_id_schema_and_no_copy_quote_instruction(self):
        req=prepare_request(self.b,'FIXED_POLICY',contract=qbound.CONTRACT);m=json.loads(req['user'])
        schema=m['output_schema']['$defs']['Intent']
        self.assertEqual(set(schema['properties']),{'kind','question_id'})
        self.assertNotIn('quote完整照抄',req['system'])
        self.assertNotIn('gold',m);self.assertNotIn('science',m)
        self.assertEqual(m['question_catalog'],qbound.question_catalog(self.b))

    def test_unknown_stale_swapped_and_missing_ids_block(self):
        for new in ('q1','question_'+'0'*64,None,123,' '+self.raw['reading']['intents']['q1']['question_id']):
            with self.subTest(value=new):
                raw=deepcopy(self.raw);raw['reading']['intents']['q1']['question_id']=new
                out,counts=self.call(raw);self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertEqual(counts,(0,0))

    def test_material_or_goal_or_roster_update_invalidates_id(self):
        for field in ('material','goal','roster','case_id'):
            b=deepcopy(self.b)
            if field=='material':b['documents']['study.txt']+='\n补充说明。'
            elif field=='goal':
                b['question_slots']['q1']=b['question_slots']['q1'].replace('问题1：','业务问题：')
                b['documents']['goal.txt']=b['question_slots']['q1']
            elif field=='roster':b['node_order'].reverse()
            else:b['case_id']+='changed'
            self.assertEqual(preview(b,self.raw,'FIXED_POLICY',contract=qbound.CONTRACT)['state'],'CHECK_BLOCKED')

    def test_repeated_text_different_slots_have_different_ids(self):
        b=deepcopy(self.b);b['question_slots']['q2']=b['question_slots']['q1'];old=deepcopy(self.old)
        old['reading']['intents']['q2']=deepcopy(old['reading']['intents']['q1'])
        old['reading']['questions']['q2']=deepcopy(old['reading']['questions']['q1'])
        raw=bind_fixture(b,old);cat=qbound.question_catalog(b)
        self.assertNotEqual(cat['q1']['question_id'],cat['q2']['question_id'])
        qbound.resolve_reading(b,raw)
        raw['reading']['intents']['q2']['question_id']=cat['q1']['question_id']
        self.assertEqual(preview(b,raw,'FIXED_POLICY',contract=qbound.CONTRACT)['state'],'CHECK_BLOCKED')

    def test_invented_question_slot_rejected(self):
        b=deepcopy(self.b);b['question_slots']['q1']='材料里没有这一句话'
        with self.assertRaisesRegex(ValueError,'NOT_IN_CURRENT'):qbound.question_catalog(b)

    def test_old_quote_wrapper_cannot_silently_upgrade(self):
        old=deepcopy(self.old);old['reading']['intents']['q1']['quote']=old['reading']['intents']['q1']['quote'].removeprefix('问题1：')
        self.assertEqual(preview(self.b,old,'FIXED_POLICY',contract='fixed-assignment')['state'],'CHECK_BLOCKED')
        self.assertEqual(preview(self.b,old,'FIXED_POLICY',contract=qbound.CONTRACT)['state'],'CHECK_BLOCKED')

    def test_extra_quote_or_scientific_fields_rejected(self):
        for where,key,value in (('intent','quote','问题1'),('outer','scientific_approval',True),('outer','question_binding',{})):
            raw=deepcopy(self.raw)
            target=raw['reading']['intents']['q1'] if where=='intent' else raw
            target[key]=value
            self.assertEqual(self.call(raw)[0]['state'],'CHECK_BLOCKED')

    def test_missing_population_never_filled(self):
        raw=deepcopy(self.raw);raw['reading']['questions']['q1']['population']=None
        out,counts=self.call(raw,review_for(self.b,self.raw,self.p,self.c))
        self.assertEqual(out['state'],'NEEDS_INPUT');self.assertEqual(counts,(0,0))
        self.assertIsNone(out['reading_candidate']['reading']['questions']['q1']['population'])

    def test_missing_design_and_conflict_block_even_if_target_ready(self):
        for conflict in (False,True):
            raw=deepcopy(self.raw)
            if conflict:raw['reported_assignment']['reported_conflict']=True
            else:raw['reported_assignment'].update(mechanism='NOT_FULLY_SPECIFIED',fixed_count=None,uniform_subset_declared=None)
            out,counts=self.call(raw,review_for(self.b,self.raw,self.p,self.c))
            self.assertEqual(out['state'],'NEEDS_INPUT');self.assertEqual(counts,(0,0))
            self.assertEqual(out['query_views'][0]['state'],'REVIEW_REQUIRED')

    def test_no_new_or_no_old_review_never_calls_core(self):
        rev=review_for(self.b,self.raw,self.p,self.c)
        for options in ({'review':None},{'review':rev,'submission_review':None},{'review':rev,'packet':None},{'review':rev,'context':None},{'review':rev,'synthetic_protocol_selected':False}):
            out,counts=self.call(**options);self.assertEqual(counts,(0,0));self.assertNotEqual(out['state'],'CORE_POINT')

    def test_old_fact_review_does_not_approve_new_wire_contract(self):
        out,counts=self.call(review=approved_assignment(self.b,self.old,self.p,self.c))
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertEqual(counts,(0,0))

    def test_worksheet_is_unapproved_and_strict_true(self):
        sheet=assignment_worksheet(self.b,self.raw,self.p,self.c,contract=qbound.CONTRACT)
        self.assertNotIn('reviewer',sheet);self.assertNotIn('reviewed_original_assignment_and_sources',sheet)
        self.assertIn('question_binding_sha256',sheet)
        with self.assertRaises(ValidationError):ReviewedQuestionBoundAssignmentFacts.model_validate(sheet)
        data=review_for(self.b,self.raw,self.p,self.c).model_dump();data['synthetic_fixture']=1
        with self.assertRaises(ValidationError):ReviewedQuestionBoundAssignmentFacts.model_validate(data)

    def test_changed_raw_target_or_fact_invalidates_review(self):
        rev=review_for(self.b,self.raw,self.p,self.c)
        for kind in ('target','population','facts'):
            raw=deepcopy(self.raw)
            if kind=='target':raw['reading']['questions']['q1']['first']['A']=0
            elif kind=='population':raw['reading']['questions']['q1']['population']=['B']
            else:raw['reported_assignment']['fixed_count']=3
            out,counts=self.call(raw,rev);self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertEqual(counts,(0,0))

    def test_fresh_id_review_cannot_override_independent_target(self):
        raw=deepcopy(self.raw);raw['reading']['questions']['q1']['population']=['B']
        rev=review_for(self.b,raw,self.p,self.c)
        out,counts=self.call(raw,rev);self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertEqual(counts,(0,0))

    def test_packet_change_invalidates_review(self):
        rev=review_for(self.b,self.raw,self.p,self.c);packet=deepcopy(self.p)
        packet['queries']['q1']['study_sha256']='0'*64
        self.assertEqual(self.call(review=rev,packet=packet)[1],(0,0))

    def test_r1b_point_preserves_raw_candidate_and_source_origin(self):
        raw=deepcopy(self.raw);out,counts=self.call(review=review_for(self.b,self.raw,self.p,self.c))
        self.assertEqual(out['state'],'CORE_POINT');self.assertEqual(counts,(1,1))
        self.assertTrue(out['query_views'][0]['certificate_replayed'])
        self.assertEqual(out['reading_candidate'],raw)
        self.assertEqual(out['assignment_fact_review_receipt']['contract'],qbound.CONTRACT)
        self.assertFalse(out['question_binding']['model_quote_supplied'])

    def test_r2_and_zero_support_keep_existing_core_results(self):
        fixture=fixture_module.FixedAssignmentSubmissionTests()
        for route,state in (('r2','CORE_POINT'),('zero','UNSUPPORTED')):
            b,old,p,c,ir=fixture.fixture(route);raw=bind_fixture(b,old)
            out=submit(b,raw,'FIXED_POLICY',contract=qbound.CONTRACT,packet=p,context=c,submission_review=ir,
                assignment_review=review_for(b,raw,p,c),synthetic_protocol_selected=True)
            self.assertEqual(out['state'],state)
            self.assertEqual(out['query_views'][0]['certificate_replayed'],state=='CORE_POINT')

    def test_read_once_one_mock_and_no_retry(self):
        from unittest.mock import Mock
        provider=Mock();provider.generate_json.return_value=deepcopy(self.raw)
        out=read_once(self.b,provider,'FIXED_POLICY',contract=qbound.CONTRACT)
        self.assertEqual(out['state'],'REVIEW_REQUIRED');self.assertFalse(out['core_called'])
        provider.generate_json.assert_called_once()
        provider.generate_json.side_effect=RuntimeError('failure')
        with self.assertRaises(RuntimeError):read_once(self.b,provider,'FIXED_POLICY',contract=qbound.CONTRACT)
        self.assertEqual(provider.generate_json.call_count,2)

    def test_contract_is_explicit_and_fixed_policy_only(self):
        self.assertEqual(preview(self.b,self.raw,'FIXED_POLICY',contract='fixed-assignment')['state'],'CHECK_BLOCKED')
        with self.assertRaises(ValueError):prepare_request(self.b,'D1_EFFECTS',contract=qbound.CONTRACT)

if __name__=='__main__':unittest.main()
