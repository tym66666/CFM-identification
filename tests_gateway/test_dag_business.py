"""Natural-language bridge gates and frozen references, with no model API calls."""
from copy import deepcopy
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from examples.dag_business_reference import cases,assess,reference_reviews,semantic_score
from cfm_id_llm.dag_reading import parse,make_request,ReadingError
from cfm_id.dag_business import inspect_candidate,submit_reviewed,DagReadingReview,READING_DECISIONS
from cfm_id.dag_backdoor_contract import BackdoorProblem
from cfm_id.dag_backdoor_verify import replay
from evaluation.dag_business_workflow import read_once,main


class DagBusinessTests(unittest.TestCase):
    def setUp(self):
        self.case=cases()[0];self.bundle=self.case['bundle'];self.wire=self.case['reference']

    def submit(self,wire=None,reading=None,science=None,selected=True):
        r,s=reference_reviews(self.bundle,self.wire)
        return submit_reviewed(self.bundle,self.wire if wire is None else wire,
            reading_review=r if reading is None else reading,science_review=s if science is None else science,
            research_protocol_selected=selected)

    def test_frozen_business_positive_and_negative_cases(self):
        for c in cases():
            with self.subTest(c['bundle']['case_id']):
                a=assess(c,c['reference']);self.assertTrue(a['passed'],a)
                self.assertFalse(a['result']['production_admission'])

    def test_inspection_cannot_solve_or_approve(self):
        with patch('cfm_id.dag_backdoor.solve',side_effect=AssertionError('solver called')):
            r=inspect_candidate(self.bundle,self.wire)
            self.assertEqual(r['state'],'REVIEW_REQUIRED');self.assertFalse(r['backend_called'])
            self.assertIsNone(r['certificate']);self.assertFalse(r['reading_worksheet']['is_approval'])
            self.assertTrue(all(v=='PENDING' for v in r['reading_worksheet']['decisions'].values()))

    def test_either_missing_review_or_selection_does_not_submit(self):
        r,s=reference_reviews(self.bundle,self.wire)
        with patch('cfm_id.dag_business.run_route',side_effect=AssertionError('backend called')):
            for reading,science,selected in [(None,s,True),(r,None,True),(r,s,False),(r,s,1)]:
                result=submit_reviewed(self.bundle,self.wire,reading_review=reading,science_review=science,research_protocol_selected=selected)
                self.assertEqual(result['state'],'REVIEW_REQUIRED');self.assertFalse(result['backend_called'])

    def test_reading_review_pending_rejected_and_missing_checks(self):
        r,s=reference_reviews(self.bundle,self.wire)
        with patch('cfm_id.dag_business.run_route',side_effect=AssertionError('backend called')):
            for value,state in [('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED')]:
                changed=r.model_copy(update={'decisions':{**r.decisions,READING_DECISIONS[0]:value}})
                self.assertEqual(self.submit(reading=changed)['state'],state)
            self.assertEqual(self.submit(reading=r.model_copy(update={'decisions':{}}))['state'],'CHECK_BLOCKED')

    def test_scientific_review_pending_and_rejected_never_solve(self):
        r,s=reference_reviews(self.bundle,self.wire)
        with patch('cfm_id.dag_backdoor.solve',side_effect=AssertionError('solver called')):
            key=next(iter(s.decisions))
            for value,state in [('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED')]:
                self.assertEqual(self.submit(science=s.model_copy(update={'decisions':{**s.decisions,key:value}}))['state'],state)

    def test_review_is_bound_to_full_candidate_and_materials(self):
        r,s=reference_reviews(self.bundle,self.wire)
        changed=deepcopy(self.wire);changed['variables'].reverse()
        self.assertEqual(self.submit(wire=changed)['reason_code'],'STALE_DAG_READING_REVIEW')
        bundle=deepcopy(self.bundle);bundle['question']+=' 请重复确认。'
        result=submit_reviewed(bundle,self.wire,reading_review=r,science_review=s,research_protocol_selected=True)
        self.assertEqual(result['state'],'CHECK_BLOCKED');self.assertFalse(result['backend_called'])

    def test_stale_scientific_problem_and_authority_mismatch(self):
        r,s=reference_reviews(self.bundle,self.wire)
        self.assertEqual(self.submit(science=s.model_copy(update={'problem_sha256':'0'*64}))['state'],'CHECK_BLOCKED')
        self.assertEqual(self.submit(science=s.model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'}))['state'],'CHECK_BLOCKED')

    def test_schema_rejects_injected_approvals_and_certificates(self):
        for key in ('certificate','review','assumptions_accepted','expected_state'):
            wire={**self.wire,key:True}
            self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'CHECK_BLOCKED')

    def test_unknown_source_duplicate_and_wrong_variable_rejected(self):
        wire=deepcopy(self.wire);wire['relations'][0]['source_ids']=['not-a-source']
        self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'CHECK_BLOCKED')
        wire=deepcopy(self.wire);wire['variables'].append(wire['variables'][0])
        self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'CHECK_BLOCKED')
        wire=deepcopy(self.wire);wire['target']['treatment']='another object'
        self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'CHECK_BLOCKED')

    def test_valid_citation_is_not_semantic_approval(self):
        wire=deepcopy(self.wire);wire['relations'][0]['cause'],wire['relations'][0]['effect']=wire['relations'][0]['effect'],wire['relations'][0]['cause']
        result=assess(self.case,wire)
        self.assertFalse(result['score']['passed']);self.assertTrue(result['result']['reference_review_withheld'])
        self.assertFalse(result['result']['backend_called'])

    def test_missing_scientific_declarations_never_default_true(self):
        for name in self.wire['scope']:
            wire=deepcopy(self.wire);wire['scope'][name]={'value':None,'source_ids':[]}
            result=inspect_candidate(self.bundle,wire)
            self.assertEqual(result['state'],'NEEDS_INPUT');self.assertIsNone(result['proposed_problem'])
        for name in ('graph_complete','latent_causes_accounted'):
            wire=deepcopy(self.wire);wire['scope'][name]['value']=False
            self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'NEEDS_INPUT')

    def test_scope_denial_nonbinary_and_extra_restrictions_not_dropped(self):
        variants=[]
        wire=deepcopy(self.wire);wire['scope']['independent_errors']['value']=False;variants.append(wire)
        wire=deepcopy(self.wire);wire['variables'][0]['domain']='OTHER';variants.append(wire)
        wire=deepcopy(self.wire);wire['additional_restrictions']=[{'text':'额外单调限制','source_ids':wire['variables'][0]['source_ids']}];variants.append(wire)
        for wire in variants:
            r=inspect_candidate(self.bundle,wire);self.assertEqual(r['state'],'UNSUPPORTED');self.assertFalse(r['backend_called'])

    def test_missing_target_context_and_measurement_have_questions(self):
        variants=[]
        for name in ('treatment','outcome','context'):
            wire=deepcopy(self.wire);wire['target'][name]=None;variants.append(wire)
        wire=deepcopy(self.wire);wire['variables'][0]['observation']='UNKNOWN';variants.append(wire)
        for wire in variants:
            r=inspect_candidate(self.bundle,wire);self.assertEqual(r['state'],'NEEDS_INPUT');self.assertTrue(r['clarification_questions'])

    def test_sample_marginals_and_unknown_positive_support_stay_blocked(self):
        for kind in ('FINITE_SAMPLE','MARGINALS_ONLY','UNKNOWN'):
            wire=deepcopy(self.wire);wire['information']['kind']=kind
            self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'NEEDS_INPUT')
        wire=deepcopy(self.wire);wire['information']['positivity']={'value':None,'source_ids':[]}
        self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'NEEDS_INPUT')

    def test_cycle_and_wrong_requested_adjustment_not_repaired(self):
        wire=deepcopy(self.wire);wire['relations'].append(dict(cause='业绩达标',effect='资深员工',kind='DIRECT_CAUSE',source_ids=wire['relations'][0]['source_ids']))
        self.assertEqual(inspect_candidate(self.bundle,wire)['reason_code'],'DIRECTED_CYCLE')
        wire=deepcopy(self.wire);wire['adjustment']=[];wire['adjustment_source_ids']=wire['target']['source_ids']
        r,s=reference_reviews(self.bundle,wire)
        result=submit_reviewed(self.bundle,wire,reading_review=r,science_review=s,research_protocol_selected=True)
        self.assertEqual(result['state'],'UNSUPPORTED');self.assertIsNone(result['certificate'])

    def test_target_reversal_and_source_change_cannot_reuse_proof(self):
        r=self.submit();p=BackdoorProblem.model_validate(r['proposed_problem'])
        self.assertTrue(replay(r['certificate'],problem=p))
        self.assertFalse(replay(r['certificate'],problem=p.model_copy(update={'treatment':p.outcome,'outcome':p.treatment})))
        self.assertFalse(replay(r['certificate'],problem=p.model_copy(update={'materials_sha256':'0'*64})))

    def test_replay_failure_withholds_business_result(self):
        with patch('cfm_id.dag_backdoor.replay',return_value=False):
            result=self.submit();self.assertEqual(result['state'],'CHECK_BLOCKED');self.assertIsNone(result['certificate'])

    def test_read_once_requires_permissions_and_never_approves(self):
        class Provider:
            calls=0
            def generate_json(s,**kw):s.calls+=1;return deepcopy(self.wire)
        provider=Provider()
        with self.assertRaises(ReadingError):read_once(self.bundle,provider)
        self.assertEqual(provider.calls,0)
        result=read_once(self.bundle,provider,allow_external=True,allow_document_sharing=True)
        self.assertEqual(provider.calls,1);self.assertEqual(result['state'],'REVIEW_REQUIRED');self.assertFalse(result['backend_called'])

    def test_provider_error_message_not_exposed(self):
        class Broken:
            def generate_json(s,**kw):raise ValueError('PRIVATE_CREDENTIAL_ERROR_TEXT')
        with self.assertRaisesRegex(ReadingError,'^LLM_REQUEST_FAILED_NO_REPLY$'):
            read_once(self.bundle,Broken(),allow_external=True,allow_document_sharing=True)

    def test_public_request_rejects_private_references_and_prompt_has_no_cases(self):
        with self.assertRaises(ReadingError):make_request({**self.bundle,'reference':self.wire})
        request=make_request(self.bundle);self.assertNotIn('参加培训',request['system'])
        self.assertEqual(set(json.loads(request['user'])),{'case_id','question','source_catalog','output_schema'})

    def test_cli_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
            base=Path(folder)
            for name,data in [('bundle',self.bundle),('candidate',self.wire)]:
                (base/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
            common=['--bundle',str(base/'bundle.json'),'--candidate',str(base/'candidate.json')]
            self.assertEqual(main(['inspect',*common,'--output',str(base/'inspection.json')]),0)
            self.assertEqual(main(['inspect',*common,'--output',str(base/'inspection.json')]),2)
            r,s=reference_reviews(self.bundle,self.wire)
            for name,data in [('reading',r.model_dump()),('science',s.model_dump())]:
                (base/(name+'.json')).write_text(json.dumps(data),encoding='utf8')
            args=['submit',*common,'--reading-review',str(base/'reading.json'),'--science-review',str(base/'science.json'),'--output',str(base/'result.json')]
            self.assertEqual(main(args),2);self.assertFalse((base/'result.json').exists())
            self.assertEqual(main([*args,'--select-research-protocol']),0)
            self.assertEqual(json.loads((base/'result.json').read_text(encoding='utf8'))['state'],'POINT')

    def test_clarification_requires_new_reading_then_can_reach_point(self):
        missing=next(c for c in cases() if c['bundle']['case_id']=='missing_graph_closure')
        before=inspect_candidate(missing['bundle'],missing['reference'])
        self.assertEqual(before['state'],'NEEDS_INPUT');self.assertTrue(before['clarification_questions'])
        complete=deepcopy(self.bundle);complete['case_id']=missing['bundle']['case_id']
        # Added graph-closure facts change document hashes: old locators cannot be reused.
        self.assertEqual(inspect_candidate(complete,missing['reference'])['state'],'CHECK_BLOCKED')
        r,s=reference_reviews(complete,self.wire)
        result=submit_reviewed(complete,self.wire,reading_review=r,science_review=s,research_protocol_selected=True)
        self.assertEqual(result['state'],'POINT');self.assertTrue(result['independent_replay'])

    def test_new_business_names_and_context_share_same_interface(self):
        from cfm_id_llm.dag_reading import documents
        from cfm_id.source_locations import build_catalog
        mapping={'参加培训':'设备保养','业绩达标':'故障发生','资深员工':'高负荷','本季度销售团队':'本月仓储设备'}
        def replace(text):
            for a,b in mapping.items():text=text.replace(a,b)
            return text
        bundle=deepcopy(self.bundle);bundle['question']=replace(bundle['question'])
        bundle['documents']={k:replace(v) for k,v in bundle['documents'].items()}
        original=list(build_catalog(documents(self.bundle)));renamed=list(build_catalog(documents(bundle)))
        sources=dict(zip(original,renamed))
        def transform(v):
            if type(v) is str:return sources.get(v,replace(v))
            if type(v) is list:return [transform(x) for x in v]
            if type(v) is dict:return {k:transform(x) for k,x in v.items()}
            return v
        wire=transform(self.wire);r,s=reference_reviews(bundle,wire)
        result=submit_reviewed(bundle,wire,reading_review=r,science_review=s,research_protocol_selected=True)
        self.assertEqual(result['state'],'POINT');self.assertEqual(result['certificate']['adjustment'],['高负荷'])

    def test_real_extra_restriction_is_preserved_with_current_prompt(self):
        from cfm_id_llm.dag_reading import documents
        from cfm_id.source_locations import build_catalog
        bundle=deepcopy(self.bundle);bundle['documents']['extra']='研究另行假定：培训对每个人的达标结果都不会有负面影响。'
        source=next(k for k,v in build_catalog(documents(bundle)).items() if v['doc_id']=='extra')
        wire=deepcopy(self.wire);wire['additional_restrictions']=[dict(text=bundle['documents']['extra'],source_ids=[source])]
        result=inspect_candidate(bundle,wire)
        self.assertEqual(result['state'],'UNSUPPORTED');self.assertEqual(result['wire_candidate'],wire)

    def test_raw_unresolved_notes_never_silently_removed(self):
        wire=deepcopy(self.wire);wire['unresolved']=[dict(text='存在尚未解决的材料问题。',source_ids=[])]
        result=inspect_candidate(self.bundle,wire)
        self.assertEqual(result['state'],'NEEDS_INPUT');self.assertEqual(result['wire_candidate'],wire)


if __name__=='__main__':unittest.main()
