"""Shared reader, explicit route choice, strict approvals and business regression."""
from copy import deepcopy
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cfm_id_llm.dag_reading import make_request
from cfm_id.dag_business import inspect_candidate,submit_reviewed,ADJUSTMENT_ROUTE,CLASSICAL_ROUTE
from cfm_id.dag_adjustment_contract import AdjustmentProblem
from cfm_id.dag_adjustment_verify import replay
from evaluation.dag_business_workflow import read_once,main
from examples.dag_adjustment_business_reference import cases,assess,reference_reviews
from examples.dag_business_reference import reference_reviews as classical_reviews


class AdjustmentBusinessTests(unittest.TestCase):
    def setUp(self):
        self.case=cases()[0];self.b=self.case['bundle'];self.w=self.case['reference']

    def submit(self,reading=None,science=None,route=ADJUSTMENT_ROUTE):
        r,s=reference_reviews(self.b,self.w)
        return submit_reviewed(self.b,self.w,reading_review=r if reading is None else reading,
            science_review=s if science is None else science,research_protocol_selected=True,route_id=route)

    def test_frozen_business_reference_cases(self):
        for case in cases():
            with self.subTest(case=case['bundle']['case_id']):
                outcome=assess(case,case['reference'])
                self.assertTrue(outcome['passed'],outcome)
                self.assertEqual(outcome['result']['route_id'],ADJUSTMENT_ROUTE)
                self.assertFalse(outcome['result']['production_admission'])

    def test_same_candidate_distinct_problem_binding_and_worksheets(self):
        a=inspect_candidate(self.b,self.w,route_id=CLASSICAL_ROUTE)
        b=inspect_candidate(self.b,self.w,route_id=ADJUSTMENT_ROUTE)
        self.assertEqual(a['wire_candidate'],b['wire_candidate'])
        self.assertEqual(a['candidate_sha256'],b['candidate_sha256'])
        self.assertNotEqual(a['reading_worksheet']['problem_sha256'],b['reading_worksheet']['problem_sha256'])
        self.assertEqual(a['proposed_problem']['version'],'dag-backdoor-1')
        self.assertEqual(b['proposed_problem']['version'],'dag-adjustment-1')
        for view in (a,b):
            self.assertFalse(view['backend_called'])
            self.assertTrue(all(x=='PENDING' for x in view['science_worksheet']['decisions'].values()))

    def test_classical_default_preserved_and_new_route_is_explicit(self):
        r,s=classical_reviews(self.b,self.w)
        old=submit_reviewed(self.b,self.w,reading_review=r,science_review=s,research_protocol_selected=True)
        self.assertEqual(old['route_id'],CLASSICAL_ROUTE)
        self.assertEqual(old['state'],'UNSUPPORTED')
        self.assertEqual(old['reason_code'],'ADJUSTMENT_CONTAINS_TREATMENT_DESCENDANT')
        new=self.submit()
        self.assertEqual(new['state'],'POINT')
        self.assertEqual(new['certificate']['adjustment'],['打开资料'])

    def test_cross_route_reviews_cannot_be_reused(self):
        old_r,old_s=classical_reviews(self.b,self.w)
        new_r,new_s=reference_reviews(self.b,self.w)
        for r,s,route in [(old_r,old_s,ADJUSTMENT_ROUTE),(new_r,old_s,ADJUSTMENT_ROUTE),
                          (old_r,new_s,ADJUSTMENT_ROUTE),(new_r,new_s,CLASSICAL_ROUTE)]:
            with patch('cfm_id.dag_business.run_route',side_effect=AssertionError('cross-route approval')):
                result=submit_reviewed(self.b,self.w,reading_review=r,science_review=s,
                    research_protocol_selected=True,route_id=route)
                self.assertEqual(result['state'],'CHECK_BLOCKED')
                self.assertFalse(result['backend_called'])

    def test_missing_reviews_and_pending_science_do_not_solve(self):
        r,s=reference_reviews(self.b,self.w)
        with patch('cfm_id.dag_adjustment.solve',side_effect=AssertionError('premature solve')):
            for reading,science,selected in [(None,s,True),(r,None,True),(r,s,False),(r,s,1)]:
                out=submit_reviewed(self.b,self.w,reading_review=reading,science_review=science,
                    research_protocol_selected=selected,route_id=ADJUSTMENT_ROUTE)
                self.assertEqual(out['state'],'REVIEW_REQUIRED')
                self.assertFalse(out['backend_called'])
            key=next(iter(s.decisions))
            out=self.submit(science=s.model_copy(update={'decisions':{**s.decisions,key:'PENDING'}}))
            self.assertEqual(out['state'],'REVIEW_REQUIRED')

    def test_candidate_and_source_changes_invalidate_reviews(self):
        r,s=reference_reviews(self.b,self.w)
        wire=deepcopy(self.w);wire['variables'].reverse()
        out=submit_reviewed(self.b,wire,reading_review=r,science_review=s,
            research_protocol_selected=True,route_id=ADJUSTMENT_ROUTE)
        self.assertEqual(out['reason_code'],'STALE_DAG_READING_REVIEW')
        b=deepcopy(self.b);b['question']+=' 请确认这个研究问题。'
        self.assertEqual(submit_reviewed(b,self.w,reading_review=r,science_review=s,
            research_protocol_selected=True,route_id=ADJUSTMENT_ROUTE)['state'],'CHECK_BLOCKED')

    def test_wrong_set_reading_is_withheld_even_if_backend_could_identify(self):
        wire=deepcopy(self.w);wire['adjustment']=None;wire['adjustment_source_ids']=[]
        out=assess(self.case,wire)
        self.assertFalse(out['passed'])
        self.assertTrue(out['result']['reference_review_withheld'])
        self.assertFalse(out['result']['backend_called'])
        self.assertIsNone(out['result']['certificate'])

    def test_false_positive_assumption_is_not_approved_by_reference(self):
        case=next(c for c in cases() if c['bundle']['case_id']=='AB06_unknown_positive')
        wire=deepcopy(case['reference'])
        wire['information']['positivity']={'value':True,'source_ids':wire['information']['source_ids']}
        out=assess(case,wire)
        self.assertFalse(out['passed'])
        self.assertFalse(out['result']['backend_called'])
        self.assertIsNone(out['result']['certificate'])

    def test_unknown_route_fails_before_provider_call(self):
        class Never:
            def generate_json(self,**kwargs):raise AssertionError('must not call provider')
        with self.assertRaisesRegex(ValueError,'EXPLICIT_SUPPORTED_DAG_ROUTE_REQUIRED'):
            read_once(self.b,Never(),allow_external=True,allow_document_sharing=True,route_id='AUTO')
        self.assertEqual(inspect_candidate(self.b,self.w,route_id='AUTO')['state'],'CHECK_BLOCKED')

    def test_provider_requests_identical_across_dag_routes(self):
        calls=[]
        wire=self.w
        class Provider:
            def generate_json(self,**kwargs):
                calls.append(kwargs);return deepcopy(wire)
        for route in (CLASSICAL_ROUTE,ADJUSTMENT_ROUTE):
            out=read_once(self.b,Provider(),allow_external=True,allow_document_sharing=True,route_id=route)
            self.assertEqual(out['state'],'REVIEW_REQUIRED')
            self.assertFalse(out['backend_called'])
        self.assertEqual(calls[0],calls[1])
        request=make_request(self.b)
        self.assertEqual(calls[0],dict(system_prompt=request['system'],user_prompt=request['user']))
        self.assertEqual(set(json.loads(request['user'])),{'case_id','question','source_catalog','output_schema'})

    def test_invalid_api_response_is_not_repaired(self):
        class Broken:
            def generate_json(self,**kwargs):return {'certificate':'fabricated'}
        result=read_once(self.b,Broken(),allow_external=True,allow_document_sharing=True,route_id=ADJUSTMENT_ROUTE)
        self.assertEqual(result['state'],'CHECK_BLOCKED')
        self.assertFalse(result['backend_called'])

    def test_independent_replay_and_fail_closed(self):
        result=self.submit();p=AdjustmentProblem.model_validate(result['proposed_problem'])
        self.assertTrue(replay(result['certificate'],problem=p))
        self.assertFalse(replay(result['certificate'],problem=p.model_copy(update={'materials_sha256':'0'*64})))
        with patch('cfm_id.dag_adjustment.replay',return_value=False):
            out=self.submit()
            self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertIsNone(out['certificate'])

    def test_unchanged_specified_empty_and_unspecified_semantics(self):
        by_id={c['bundle']['case_id']:c for c in cases()}
        empty=by_id['AB07_explicit_empty'];search=by_id['AB08_unspecified']
        self.assertEqual(assess(empty,empty['reference'])['result']['state'],'UNSUPPORTED')
        a=assess(search,search['reference'])['result']
        self.assertIsNone(a['proposed_problem']['adjustment'])
        self.assertEqual(a['certificate']['adjustment'],[])

    def test_cli_route_selection_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
            base=Path(folder);r,s=reference_reviews(self.b,self.w)
            for name,data in [('bundle',self.b),('wire',self.w),('reading',r.model_dump()),('science',s.model_dump())]:
                (base/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
            common=['--bundle',str(base/'bundle.json'),'--candidate',str(base/'wire.json'),'--route',ADJUSTMENT_ROUTE]
            args=['submit',*common,'--reading-review',str(base/'reading.json'),
                  '--science-review',str(base/'science.json'),'--output',str(base/'out.json')]
            self.assertEqual(main(args),2)
            self.assertEqual(main([*args,'--select-research-protocol']),0)
            out=json.loads((base/'out.json').read_text(encoding='utf8'))
            self.assertEqual(out['state'],'POINT');self.assertEqual(out['route_id'],ADJUSTMENT_ROUTE)
            self.assertEqual(main([*args,'--select-research-protocol']),2)


if __name__=='__main__':unittest.main()
