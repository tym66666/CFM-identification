"""Front-door role reading, separate reviews and shared business workflow."""
from copy import deepcopy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from cfm_id_llm import dag_reading
from cfm_id_llm.dag_frontdoor_reading import make_request,parse,SYSTEM
from cfm_id.dag_business import (
    FRONTDOOR_ROUTE,CLASSICAL_ROUTE,ADJUSTMENT_ROUTE,inspect_candidate,submit_reviewed,
    reading_contract,DagFrontdoorReadingReview,DagReadingReview,FRONTDOOR_READING_DECISIONS)
from cfm_id.dag_frontdoor_contract import FrontdoorProblem
from evaluation.dag_business_workflow import read_once,main
from examples.dag_frontdoor_business_reference import cases,assess,reference_reviews,semantic_score


class FrontdoorBusinessTests(unittest.TestCase):
    def setUp(self):
        self.rows={c['bundle']['case_id']:c for c in cases()}
        self.case=self.rows['FB01_specified']
        self.b,self.w=self.case['bundle'],self.case['reference']

    def inspect(self,wire=None,bundle=None):
        return inspect_candidate(bundle or self.b,wire or self.w,route_id=FRONTDOOR_ROUTE)

    def test_fourteen_frozen_business_expectations(self):
        self.assertEqual(len(self.rows),14)
        for name,c in self.rows.items():
            with self.subTest(case=name):
                result=assess(c,c['reference'])
                self.assertTrue(result['passed'],result)
                self.assertFalse(result['result']['production_admission'])

    def test_explicit_role_search_and_undecided_are_different(self):
        p=self.inspect()['proposed_problem']
        self.assertEqual(p['frontdoor_variable'],self.w['frontdoor_choice']['variable'])
        c=self.rows['FB02_search'];view=self.inspect(c['reference'],c['bundle'])
        self.assertIsNone(view['proposed_problem']['frontdoor_variable'])
        c=self.rows['FB04_undecided'];view=self.inspect(c['reference'],c['bundle'])
        self.assertEqual(view['state'],'NEEDS_INPUT')
        self.assertTrue(view['clarification_questions'])
        self.assertIsNone(view['proposed_problem'])

    def test_adjustment_is_never_dropped_or_reinterpreted(self):
        for name in ('FB03_control','FB08_both'):
            c=self.rows[name];v=self.inspect(c['reference'],c['bundle'])
            self.assertEqual(v['reason_code'],'FRONTDOOR_WITH_ADJUSTMENT_REQUEST_NOT_ADAPTED')
            self.assertIsNone(v['proposed_problem']);self.assertFalse(v['backend_called'])
        w=deepcopy(self.w);w['adjustment']=[];w['adjustment_source_ids']=w['target']['source_ids']
        self.assertEqual(self.inspect(w)['state'],'UNSUPPORTED')

    def test_no_scientific_or_reading_review_from_a_complete_candidate(self):
        with patch('cfm_id.dag_frontdoor.solve',side_effect=AssertionError('unexpected solver')):
            v=self.inspect()
            self.assertEqual(v['state'],'REVIEW_REQUIRED')
            self.assertEqual(set(v['reading_worksheet']['decisions']),set(FRONTDOOR_READING_DECISIONS))
            self.assertEqual(set(v['reading_worksheet']['decisions'].values()),{'PENDING'})
            self.assertFalse(v['reading_worksheet']['is_approval'])
            self.assertFalse(v['backend_called']);self.assertIsNone(v['certificate'])

    def test_both_explicit_reviews_and_literal_selection_are_required(self):
        rr,sr=reference_reviews(self.b,self.w)
        with patch('cfm_id.dag_frontdoor.solve',side_effect=AssertionError('unexpected solver')):
            for reading,science,selected in [(None,sr,True),(rr,None,True),(rr,sr,False),(rr,sr,1)]:
                v=submit_reviewed(self.b,self.w,reading_review=reading,science_review=science,
                                  research_protocol_selected=selected,route_id=FRONTDOOR_ROUTE)
                self.assertEqual(v['state'],'REVIEW_REQUIRED');self.assertFalse(v['backend_called'])

    def test_requested_roles_have_a_separate_pending_or_rejected_decision(self):
        rr,sr=reference_reviews(self.b,self.w)
        with patch('cfm_id.dag_frontdoor.solve',side_effect=AssertionError('unexpected solver')):
            for decision,state in [('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED')]:
                reading=rr.model_copy(update={'decisions':{**rr.decisions,'requested_identification_roles':decision}})
                v=submit_reviewed(self.b,self.w,reading_review=reading,science_review=sr,
                                  research_protocol_selected=True,route_id=FRONTDOOR_ROUTE)
                self.assertEqual(v['state'],state);self.assertFalse(v['backend_called'])
            missing=rr.model_dump();missing['decisions'].pop('requested_identification_roles')
            v=submit_reviewed(self.b,self.w,reading_review=DagFrontdoorReadingReview.model_validate(missing),
                science_review=sr,research_protocol_selected=True,route_id=FRONTDOOR_ROUTE)
            self.assertEqual(v['state'],'CHECK_BLOCKED')

    def test_old_reading_review_cannot_be_relabelled_as_new_review(self):
        rr,sr=reference_reviews(self.b,self.w)
        data=rr.model_dump();data['version']='dag-reading-review-1'
        old=DagReadingReview.model_validate(data)
        v=submit_reviewed(self.b,self.w,reading_review=old,science_review=sr,
                          research_protocol_selected=True,route_id=FRONTDOOR_ROUTE)
        self.assertEqual(v['state'],'CHECK_BLOCKED');self.assertFalse(v['backend_called'])

    def test_candidate_and_material_changes_invalidate_both_review_bindings(self):
        rr,sr=reference_reviews(self.b,self.w)
        w=deepcopy(self.w);w['frontdoor_choice']=dict(status='UNSPECIFIED',variable=None,source_ids=[])
        v=submit_reviewed(self.b,w,reading_review=rr,science_review=sr,research_protocol_selected=True,route_id=FRONTDOOR_ROUTE)
        self.assertEqual(v['state'],'CHECK_BLOCKED');self.assertFalse(v['backend_called'])
        b=deepcopy(self.b);b['case_id']='new-material-version'
        v=submit_reviewed(b,self.w,reading_review=rr,science_review=sr,research_protocol_selected=True,route_id=FRONTDOOR_ROUTE)
        self.assertEqual(v['state'],'CHECK_BLOCKED');self.assertFalse(v['backend_called'])

    def test_wrong_model_role_never_gets_a_reference_approval(self):
        w=deepcopy(self.w);w['frontdoor_choice']=dict(status='UNSPECIFIED',variable=None,source_ids=[])
        a=assess(self.case,w)
        self.assertFalse(a['passed'])
        self.assertFalse(a['score']['fields']['frontdoor_choice'])
        self.assertTrue(a['result']['reference_review_withheld'])
        self.assertIsNone(a['result']['certificate'])

    def test_source_validation_and_choice_shape_cannot_be_bypassed(self):
        variants=[
            dict(status='SPECIFIED',variable=None,source_ids=self.w['target']['source_ids']),
            dict(status='UNSPECIFIED',variable='掌握方法',source_ids=[]),
            dict(status='SPECIFIED',variable='掌握方法',source_ids=[]),
            dict(status='SPECIFIED',variable='unknown',source_ids=self.w['target']['source_ids']),
            dict(status='SPECIFIED',variable='掌握方法',source_ids=['invented']),
        ]
        for choice in variants:
            w=deepcopy(self.w);w['frontdoor_choice']=choice
            self.assertEqual(self.inspect(w)['state'],'CHECK_BLOCKED')
        w=deepcopy(self.w);w['approved_by_llm']=True
        self.assertEqual(self.inspect(w)['state'],'CHECK_BLOCKED')

    def test_v1_v2_candidates_do_not_cross_route_boundaries(self):
        old=deepcopy(self.w);old.pop('frontdoor_choice');old['version']='dag-reading-1'
        self.assertEqual(self.inspect(old)['state'],'CHECK_BLOCKED')
        for route in (CLASSICAL_ROUTE,ADJUSTMENT_ROUTE):
            v=inspect_candidate(self.b,self.w,route_id=route)
            self.assertEqual(v['state'],'CHECK_BLOCKED')

    def test_old_requests_are_preserved_and_new_schema_binds_all_sources(self):
        from examples.dag_business_reference import cases as old_cases
        old=old_cases()[0]['bundle']
        for route in (CLASSICAL_ROUTE,ADJUSTMENT_ROUTE):
            self.assertEqual(reading_contract(route)[0](old),dag_reading.make_request(old))
        request=make_request(self.b);data=json.loads(request['user'])
        schema=data['output_schema']
        self.assertEqual(schema['properties']['version']['const'],'dag-frontdoor-reading-2')
        self.assertEqual(schema['$defs']['FrontdoorChoice']['properties']['source_ids']['items'],
                         {'$ref':'#/$defs/SourceId'})
        self.assertEqual(set(schema['$defs']['SourceId']['enum']),set(data['source_catalog']))
        self.assertNotIn('reference',data);self.assertNotIn('expected_state',data)
        self.assertNotIn('decisions',schema['properties'])

    def test_read_once_uses_new_prompt_once_and_stops_at_review(self):
        provider=Mock();provider.generate_json.return_value=self.w
        out=read_once(self.b,provider,route_id=FRONTDOOR_ROUTE,allow_external=True,allow_document_sharing=True)
        self.assertEqual(provider.generate_json.call_count,1)
        self.assertEqual(provider.generate_json.call_args.kwargs['system_prompt'],SYSTEM)
        self.assertEqual(out['state'],'REVIEW_REQUIRED');self.assertIsNone(out['certificate'])

    def test_read_once_sharing_and_provider_failures_cannot_invoke_core(self):
        provider=Mock()
        with self.assertRaises(ValueError):read_once(self.b,provider,route_id=FRONTDOOR_ROUTE)
        provider.generate_json.assert_not_called()
        provider.generate_json.side_effect=RuntimeError('private transport text')
        with self.assertRaisesRegex(ValueError,'LLM_REQUEST_FAILED_NO_REPLY') as caught:
            read_once(self.b,provider,route_id=FRONTDOOR_ROUTE,allow_external=True,allow_document_sharing=True)
        self.assertNotIn('private transport',str(caught.exception))

    def test_business_result_keeps_exact_native_certificate(self):
        result=assess(self.case,self.w)['result']
        self.assertEqual(result['state'],'POINT');self.assertTrue(result['independent_replay'])
        self.assertEqual(result['certificate'],result['route_result']['certificate'])
        p=FrontdoorProblem.model_validate(result['proposed_problem'])
        from cfm_id.dag_frontdoor_verify import replay
        self.assertTrue(replay(result['certificate'],problem=p))

    def test_replay_failure_withholds_business_proof(self):
        rr,sr=reference_reviews(self.b,self.w)
        with patch('cfm_id.dag_frontdoor.replay',return_value=False):
            v=submit_reviewed(self.b,self.w,reading_review=rr,science_review=sr,
                              research_protocol_selected=True,route_id=FRONTDOOR_ROUTE)
        self.assertEqual(v['state'],'CHECK_BLOCKED')
        self.assertIsNone(v['mathematical_claim']);self.assertIsNone(v['certificate'])

    def test_cli_frontdoor_request_inspect_and_reviewed_submit(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            rr,sr=reference_reviews(self.b,self.w)
            for name,value in [('bundle',self.b),('candidate',self.w),('reading',rr.model_dump()),('science',sr.model_dump())]:
                (folder/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False),encoding='utf8')
            common=['--route',FRONTDOOR_ROUTE,'--bundle',str(folder/'bundle.json')]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['request',*common,'--output',str(folder/'request.json')]),0)
                self.assertEqual(main(['inspect',*common,'--candidate',str(folder/'candidate.json'),
                                       '--output',str(folder/'inspect.json')]),0)
                self.assertEqual(main(['submit',*common,'--candidate',str(folder/'candidate.json'),
                    '--reading-review',str(folder/'reading.json'),'--science-review',str(folder/'science.json'),
                    '--select-research-protocol','--output',str(folder/'result.json')]),0)
            request=json.loads((folder/'request.json').read_text(encoding='utf8'))
            self.assertEqual(request,make_request(self.b))
            self.assertEqual(json.loads((folder/'inspect.json').read_text(encoding='utf8'))['state'],'REVIEW_REQUIRED')
            self.assertEqual(json.loads((folder/'result.json').read_text(encoding='utf8'))['state'],'POINT')


if __name__=='__main__':
    unittest.main()

