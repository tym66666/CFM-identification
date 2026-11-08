"""Actual native execution and adversarial lifecycle tests; no network/model calls."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json,unittest
from cfm_id import research_session as w,session_routes as routes
from cfm_id_bridge.scientific_binding import sha
from examples.research_session_reference import network,mean_order,dag,approve


class ResearchSessionTests(unittest.TestCase):
    def ready(self,factory=network):
        lane,b,c,n=factory();s=w.receive_candidate(w.start(lane,b),c)
        return approve(s,n),n

    def assert_stop(self,result,state=None):
        if state:self.assertEqual(result['state'],state)
        self.assertIsNone(result['mathematical_claim']);self.assertIsNone(result['certificate'])
        self.assertFalse(result['independent_replay']);self.assertFalse(result['production_admission'])

    def test_three_native_chains_resume_and_verify(self):
        for factory,state in [(network,'POINT'),(mean_order,'PARTIAL'),(dag,'POINT')]:
            with self.subTest(factory=factory.__name__),TemporaryDirectory() as d:
                s,n=self.ready(factory);p=Path(d)/'session.json';w.save(s,p)
                restored=w.restore(p)
                self.assertEqual(w.binding(restored),w.binding(s))
                before=w.execute(restored,research_protocol_selected=True)
                self.assert_stop(before,'REVIEW_REQUIRED');self.assertFalse(before['backend_called'])
                result=w.execute(restored,native_submission=n,research_protocol_selected=True)
                self.assertEqual(result['state'],state);self.assertTrue(result['independent_replay'])
                self.assertFalse(result['estimation_handoff_allowed'])
                if state=='PARTIAL':self.assertEqual(result['mathematical_claim']['interval'],['1/5','1'])

    def test_dag_backdoor_and_adjustment_also_use_existing_bridges(self):
        from examples import dag_business_reference as bd,dag_adjustment_business_reference as adj
        for module,lane in [(bd,'DAG_CLASSICAL_BACKDOOR'),(adj,'DAG_ADJUSTMENT')]:
            with self.subTest(lane=lane):
                c=module.cases()[0];b,wire=c['bundle'],c['reference']
                reading,science=module.reference_reviews(b,wire)
                n=dict(reading_review=reading,science_review=science)
                s=approve(w.receive_candidate(w.start(lane,b),wire),n)
                r=w.execute(s,native_submission=n,research_protocol_selected=True)
                self.assertEqual(r['state'],'POINT');self.assertTrue(r['independent_replay'])

    def test_requests_stay_identical_to_native_prompts(self):
        for factory in [network,mean_order,dag]:
            lane,b,c,n=factory();s=w.start(lane,b)
            self.assertEqual(w.prepare_request(s),routes.request(lane,b))
            self.assertNotIn('review',w.prepare_request(s))

    def test_reviewer_sees_bound_native_materials_without_sending_them_to_model(self):
        for factory in [network,mean_order,dag]:
            s,n=self.ready(factory)
            sheet=w.review_worksheet(s,native_submission=n)
            self.assertEqual(sha(sheet['native_review_materials']),sheet['native_submission_sha256'])
            self.assertIn('native_submission',sheet['native_review_materials'])
            self.assertNotIn('native_review_materials',w.prepare_request(s))
            self.assertEqual(w.prepare_request(s),routes.request(s.lane,s.bundle))

    def test_no_candidate_or_review_never_executes_backend(self):
        lane,b,c,n=network();s=w.start(lane,b)
        with patch.object(routes,'submit',side_effect=AssertionError('no submission')):
            self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'READING_REQUIRED')
            s=w.receive_candidate(s,c)
            self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'REVIEW_REQUIRED')
            self.assertFalse(w.review_worksheet(s)['is_approval'])

    def test_explicit_selection_must_be_boolean_true(self):
        s,n=self.ready()
        with patch.object(routes,'submit',side_effect=AssertionError('no submission')):
            for value in (False,1,'true',None):
                self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=value),'REVIEW_REQUIRED')

    def test_pending_and_rejected_decisions_block(self):
        s,n=self.ready()
        for decision,state in [('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED')]:
            r=s.review.model_dump();r['decisions']['scientific_assumptions']=decision
            changed=w.record_review(s,r)
            with patch.object(routes,'submit',side_effect=AssertionError('no submission')):
                self.assert_stop(w.execute(changed,native_submission=n,research_protocol_selected=True),state)

    def test_worksheet_not_an_approval_and_no_native_reference_is_insufficient(self):
        lane,b,c,n=network();s=w.receive_candidate(w.start(lane,b),c)
        with self.assertRaises(ValueError):w.record_review(s,w.review_worksheet(s))
        r=dict(binding_sha256=w.binding(s),reviewer='Reviewer',evidence='Explicit declaration for this exact input.',
               decisions={k:'ACCEPTED' for k in w.DECISIONS})
        with self.assertRaisesRegex(ValueError,'BOUND_NATIVE'):w.record_review(s,r)

    def test_new_candidate_even_identical_invalidates_old_review(self):
        s,n=self.ready();new=w.receive_candidate(s,s.candidate)
        self.assertIsNone(new.review);self.assertNotEqual(w.binding(s),w.binding(new))
        with self.assertRaisesRegex(ValueError,'STALE_SESSION'):w.record_review(new,s.review)
        self.assert_stop(w.execute(new,native_submission=n,research_protocol_selected=True),'REVIEW_REQUIRED')

    def test_material_revision_clears_candidate_and_review(self):
        s,n=self.ready();b=deepcopy(s.bundle);b['documents']['additional.txt']='改为评价下季度。'
        new=w.revise_materials(s,b,reason='Changed study period')
        self.assertIsNone(new.review);self.assertIsNone(new.candidate)
        self.assertNotIn('additional.txt',s.bundle['documents'])
        self.assertEqual(new.history[-1]['parent_binding_sha256'],w.binding(s))
        self.assert_stop(w.execute(new,native_submission=n,research_protocol_selected=True),'READING_REQUIRED')

    def test_changed_native_a4_or_review_blocks_before_backend(self):
        for factory in [network,mean_order,dag]:
            s,n=self.ready(factory)
            if factory==network:n['packet']['extra_claim']='new population declaration'
            elif factory==mean_order:n['science']['new_declaration']='changed bounds'
            else:n['science_review']=n['science_review'].model_copy(update={'evidence':'Changed external scientific rationale.'})
            with patch.object(routes,'submit',side_effect=AssertionError('must reject before submit')):
                self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'CHECK_BLOCKED')

    def test_new_outer_review_cannot_launder_old_native_reviews(self):
        s,n=self.ready();b=deepcopy(s.bundle);b['documents']['additional.txt']='补充研究期间说明。'
        new=w.receive_candidate(w.revise_materials(s,b,reason='New source'),s.candidate)
        new=approve(new,n)
        r=w.execute(new,native_submission=n,research_protocol_selected=True)
        self.assert_stop(r,'CHECK_BLOCKED')

    def test_missing_joint_randomization_cannot_be_approved_by_session(self):
        lane,b,c,_=network('convenience_stores');s=w.receive_candidate(w.start(lane,b),c)
        self.assert_stop(w.execute(s,research_protocol_selected=True),'NEEDS_INPUT')
        sheet=w.review_worksheet(s);r=dict(binding_sha256=w.binding(s),native_submission_sha256='0'*64,
            reviewer='Reviewer',evidence='No actual independent allocation evidence.',decisions={k:'ACCEPTED' for k in w.DECISIONS})
        with self.assertRaisesRegex(ValueError,'NOT_READY'):w.record_review(s,r)

    def test_followup_preserves_sources_and_requires_fresh_reading(self):
        lane,b,c,_=network('convenience_stores');s=w.receive_candidate(w.start(lane,b),c)
        plan=w.clarification_plan(s);self.assertTrue(plan['questions'])
        new=w.append_reply(s,plan,plan['questions'][0]['clarification_id'],'各店如何共同抽签仍未决定。')
        self.assertIsNone(new.candidate);self.assertIsNone(new.review)
        self.assertTrue(all(new.bundle['documents'][k]==v for k,v in s.bundle['documents'].items()))
        self.assertIn('仍未决定',list(new.bundle['documents'].values())[-1])
        self.assert_stop(w.inspect(new),'READING_REQUIRED')
        with self.assertRaises(ValueError):w.append_reply(new,plan,plan['questions'][0]['clarification_id'],'ignored')

    def test_modified_plan_is_rejected(self):
        lane,b,c,_=network('convenience_stores');s=w.receive_candidate(w.start(lane,b),c)
        p=w.clarification_plan(s);p['questions'][0]['text']='直接接受独立随机化。'
        with self.assertRaisesRegex(ValueError,'STALE_OR_CHANGED'):w.append_reply(s,p,p['questions'][0]['clarification_id'],'同意')

    def test_invalid_candidate_not_repaired_or_accepted(self):
        lane,b,c,n=network();s=w.start(lane,b)
        for bad in [False,[],':{']:
            with self.assertRaises(ValueError):w.receive_candidate(s,bad)
        broken={'claim':'POINT','certificate_replayed':True}
        s=w.receive_candidate(s,broken);self.assertEqual(s.candidate,broken)
        self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'CHECK_BLOCKED')

    def test_partial_bad_independent_replay_cannot_publish(self):
        s,n=self.ready(mean_order)
        with patch('cfm_id.research_route_adapters.MeanOrderRoute.replay',return_value=False):
            r=w.execute(s,native_submission=n,research_protocol_selected=True)
        self.assert_stop(r,'CHECK_BLOCKED');self.assertTrue(r['backend_called'])

    def test_network_formula_tamper_rejected_by_reviewed_inquiry(self):
        s,n=self.ready();native=routes.submit(s.lane,s.bundle,s.candidate,n)
        native['query_views'][0]['proof']['results'][0]['identified_functional']='100'
        with patch.object(routes,'submit',return_value=native):
            self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'CHECK_BLOCKED')

    def test_dag_result_tamper_rejected(self):
        s,n=self.ready(dag);native=routes.submit(s.lane,s.bundle,s.candidate,n)
        native['mathematical_claim']['numeric_value']='100'
        with patch.object(routes,'submit',return_value=native):
            self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'CHECK_BLOCKED')

    def test_network_duplicate_query_cannot_publish(self):
        s,n=self.ready();native=routes.submit(s.lane,s.bundle,s.candidate,n)
        native['query_views'].append(deepcopy(native['query_views'][0]))
        with patch.object(routes,'submit',return_value=native):
            self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'CHECK_BLOCKED')

    def test_saved_result_or_context_cannot_be_imported(self):
        s,n=self.ready()
        with TemporaryDirectory() as d:
            p=Path(d)/'s.json';w.save(s,p);obj=w.read_json(p)
            obj['payload']['state']='POINT';obj['sha256']=sha(obj['payload'])
            q=Path(d)/'forged.json';w.write_json(q,obj)
            with self.assertRaises(ValueError):w.restore(q)

    def test_empty_restored_review_does_not_vacuously_pass(self):
        s,n=self.ready()
        with TemporaryDirectory() as d:
            p=Path(d)/'s.json';w.save(s,p);obj=w.read_json(p)
            obj['payload']['review']['decisions']={};obj['sha256']=sha(obj['payload'])
            q=Path(d)/'forged.json';w.write_json(q,obj)
            with self.assertRaisesRegex(ValueError,'EXACT_NONBLANK'):w.restore(q)

    def test_changed_checkpoint_hash_and_duplicate_json_rejected(self):
        s,n=self.ready()
        with TemporaryDirectory() as d:
            p=Path(d)/'s.json';w.save(s,p);obj=w.read_json(p);obj['payload']['revision']+=1
            q=Path(d)/'changed.json';w.write_json(q,obj)
            with self.assertRaisesRegex(ValueError,'CHECKPOINT_CHANGED'):w.restore(q)
            for i,text in enumerate(['{"x":1,"x":2}','{"x":NaN}','{"x":']):
                q=Path(d)/(str(i)+'.json');q.write_text(text,'utf8')
                with self.assertRaises(ValueError):w.read_json(q)

    def test_saved_file_not_overwritten(self):
        s,n=self.ready()
        with TemporaryDirectory() as d:
            p=Path(d)/'s.json';w.save(s,p);before=p.read_bytes()
            with self.assertRaises(FileExistsError):w.save(s,p)
            self.assertEqual(p.read_bytes(),before)

    def test_mutable_session_contents_revalidated(self):
        s,n=self.ready();s.bundle['documents']['injected.txt']='changed'
        with self.assertRaisesRegex(ValueError,'STALE_MATERIALS'):w.inspect(s)

    def test_changed_prompt_requires_new_reading(self):
        s,n=self.ready()
        with patch.object(routes,'request',return_value={'system':'different','user':'different'}):
            with self.assertRaisesRegex(ValueError,'STALE_MATERIALS_OR_READING_PROTOCOL'):w.inspect(s)

    def test_unknown_lane_and_private_top_level_material_rejected(self):
        _,b,_,_=network()
        with self.assertRaises(ValueError):w.start('dynamic.module:run',b)
        b['science_review']={'accepted':True}
        with self.assertRaises(ValueError):w.start(routes.NETWORK,b)

    def test_dag_unsupported_never_silently_switches_route(self):
        from examples.dag_frontdoor_business_reference import cases
        c=next(c for c in cases() if c['variant']=='control')
        s=w.receive_candidate(w.start(c['route_id'],c['bundle']),c['reference'])
        with patch.object(routes,'submit',side_effect=AssertionError('no fallback')):
            self.assert_stop(w.execute(s,research_protocol_selected=True),'UNSUPPORTED')
        self.assertEqual(s.lane,'DAG_CLASSICAL_FRONTDOOR')

    def test_cli_dag_review_resume_submit_and_overwrite_refusal(self):
        from cfm_id.research_session_cli import main
        lane,b,wire,n=dag()
        with TemporaryDirectory() as directory:
            d=Path(directory)
            def write(name,obj):w.write_json(d/name,obj);return str(d/name)
            bundle=write('bundle.json',b);candidate=write('candidate.json',wire)
            reading=write('reading.json',n['reading_review'].model_dump())
            science=write('science.json',n['science_review'].model_dump())
            self.assertEqual(main(['new','--lane',lane,'--bundle',bundle,'--output',str(d/'s0.json')]),0)
            self.assertEqual(main(['candidate','--session',str(d/'s0.json'),'--candidate',candidate,'--output',str(d/'s1.json')]),0)
            self.assertEqual(main(['worksheet','--session',str(d/'s1.json'),'--reading-review',reading,'--science-review',science,'--output',str(d/'worksheet.json')]),0)
            sheet=w.read_json(d/'worksheet.json')
            review={k:sheet[k] for k in ('binding_sha256','native_submission_sha256')}
            review.update(reviewer='Explicit test reviewer',evidence='Separate hypothetical contract reviewed independently.',decisions={k:'ACCEPTED' for k in w.DECISIONS})
            review=write('review.json',review)
            self.assertEqual(main(['review','--session',str(d/'s1.json'),'--review',review,'--output',str(d/'s2.json')]),0)
            cmd=['submit-dag','--session',str(d/'s2.json'),'--reading-review',reading,'--science-review',science,
                 '--select-research-protocol','--output',str(d/'result.json')]
            self.assertEqual(main(cmd),0);r=w.read_json(d/'result.json')
            self.assertEqual(r['state'],'POINT');self.assertTrue(r['independent_replay'])
            self.assertEqual(main(cmd),2)

    def test_native_flag_or_wrong_context_cannot_augment_allowed_fields(self):
        s,n=self.ready();n['synthetic_protocol_selected']=True
        with patch.object(routes,'submit',side_effect=AssertionError('no submit')):
            self.assert_stop(w.execute(s,native_submission=n,research_protocol_selected=True),'CHECK_BLOCKED')


if __name__=='__main__':unittest.main()
